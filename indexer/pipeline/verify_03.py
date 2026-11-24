"""Part A1: the data verification gate (harness_03/03).

Runs after extraction/cleaning and before chunking. Four checks per document
(quality, completeness, recency, uniqueness); a failing document is physically
moved to $RAGOPS_ROOT/quarantine/<ts>/ and never reaches embed/store.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Literal

from .chunk import HEADING_PATTERN
from .config_03 import IndexerSettings03, load_settings_03
from .hashing_03 import cosine, dummy_embed_03, sha256_text
from .state_03 import ManifestState03, load_manifest_03, manifest_path_03

SUPPORTED_03 = {".pdf", ".md", ".html", ".htm", ".txt"}
TERMINAL_PUNCT_03 = (".", "!", "?", ")", '"', "'", "]")
REPO_ROOT_03 = Path(__file__).resolve().parents[2]
DOC_IDS_YAML_03 = REPO_ROOT_03 / "config" / "doc_ids_03.yaml"
EmbedFn = Callable[[list[str]], list[list[float]]]


# ----------------------------------------------------------------- data model
@dataclass(frozen=True)
class DocMeta03:
    path: Path
    source: str
    doc_id: str
    title: str | None
    date: str | None
    version: str | None
    page_count: int | None
    extra: dict[str, str] = field(default_factory=dict)


@dataclass
class ExtractedDoc03:
    meta: DocMeta03
    text: str
    pages: list[str]
    extraction_error: str | None = None


@dataclass
class CheckResult03:
    check: Literal["quality", "completeness", "recency", "uniqueness"]
    passed: bool
    reason_code: str | None
    detail: str
    value: float | None = None


@dataclass
class Verdict03:
    doc: DocMeta03
    text_sha256: str
    checks: list[CheckResult03]
    decision: Literal["accept", "quarantine", "supersede"]
    supersedes: str | None = None
    unchanged: bool = False
    doc_vec: list[float] | None = None

    def codes(self) -> list[str]:
        return [c.reason_code for c in self.checks if c.reason_code]

    def failure_codes(self) -> list[str]:
        return [c.reason_code for c in self.checks if c.reason_code and not c.passed]


# --------------------------------------------------------------- small helpers
def utc_ts_03() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def log_03(msg: str, logger: str = "rahbar.indexer.verify_03", **fields: object) -> None:
    print(json.dumps({"ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                      "logger": logger, "msg": msg, **fields}), flush=True)


def slug_03(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def parse_front_matter_03(raw: str) -> tuple[dict[str, str], str]:
    """`key: value` lines between leading '---' markers; returns (meta, body)."""
    lines = raw.split("\n")
    if not lines or lines[0].strip() != "---":
        return {}, raw
    meta: dict[str, str] = {}
    for idx in range(1, len(lines)):
        if lines[idx].strip() == "---":
            return meta, "\n".join(lines[idx + 1:]).lstrip("\n")
        key, sep, value = lines[idx].partition(":")
        if sep:
            meta[key.strip()] = value.strip()
    return {}, raw  # unterminated front matter: treat everything as body


_ISO_RE = re.compile(r"^(\d{4})(?:-(\d{2}))?(?:-(\d{2}))?$")


def _iso_tuple(value: str | None) -> tuple[int, int, int] | None:
    m = _ISO_RE.match((value or "").strip())
    if not m:
        return None
    return (int(m.group(1)), int(m.group(2) or 0), int(m.group(3) or 0))


def _natural(value: str) -> tuple[tuple[int, Any], ...]:
    return tuple((0, int(p)) if p.isdigit() else (1, p) for p in re.split(r"[.\-]", value) if p)


def compare_versions_03(a: str, b: str) -> int:
    """-1 / 0 / 1. ISO dates (YYYY, YYYY-MM, YYYY-MM-DD) compare as dates, else natural sort."""
    ta, tb = _iso_tuple(a), _iso_tuple(b)
    if ta is not None and tb is not None:
        return (ta > tb) - (ta < tb)
    na, nb = _natural(a), _natural(b)
    return (na > nb) - (na < nb)


def compare_incoming_03(date_a: str | None, ver_a: str | None,
                        date_b: str | None, ver_b: str | None) -> int:
    """Prefer date over version when both sides have a parseable date."""
    if _iso_tuple(date_a) is not None and _iso_tuple(date_b) is not None:
        c = compare_versions_03(date_a or "", date_b or "")
        if c != 0:
            return c
    if ver_a and ver_b:
        return compare_versions_03(ver_a, ver_b)
    return 0


def doc_vector_03(text: str, embed_fn: EmbedFn, chars: int = 2000) -> list[float]:
    """Mean of embed_fn over the first `chars` characters split into <=4 segments of <=512."""
    head = text[:chars]
    segments = [head[i:i + 512] for i in range(0, len(head), 512)][:4] or [""]
    vecs = embed_fn(segments)
    n = len(vecs)
    return [sum(v[i] for v in vecs) / n for i in range(len(vecs[0]))]


# ----------------------------------------------------------------- extraction
def load_doc_ids_03(path: Path | None = None) -> dict[str, dict[str, Any]]:
    p = path or DOC_IDS_YAML_03
    if not p.exists():
        return {}
    import yaml  # type: ignore[import-untyped]
    data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    return {str(k): {kk: ("" if vv is None else str(vv)) for kk, vv in v.items()}
            for k, v in data.items() if isinstance(v, dict)}


def _read_index_03(directory: Path) -> dict[str, dict[str, Any]]:
    idx = directory / "_index.json"
    if not idx.exists():
        return {}
    return {e["file"]: e for e in json.loads(idx.read_text(encoding="utf-8"))}


def _first(*values: Any) -> Any:
    for v in values:
        if v not in (None, ""):
            return v
    return None


def extract_doc_03(path: Path, index_entry: dict[str, Any] | None = None,
                   yaml_entry: dict[str, Any] | None = None) -> ExtractedDoc03:
    """Extract one file. .md/.txt are read directly (front matter + form-feed pages);
    .pdf/.html go through A02 `pipeline.extract.extract`."""
    index_entry = index_entry or {}
    yaml_entry = yaml_entry or {}
    fm: dict[str, str] = {}
    pages: list[str] = []
    error: str | None = None
    suffix = path.suffix.lower()
    try:
        if suffix in {".md", ".txt"}:
            raw = path.read_bytes().decode("utf-8", errors="replace")
            fm, body = parse_front_matter_03(raw)
            pages = [p.strip() for p in body.split("\f")] or [""]
        else:
            from .extract import extract
            doc = extract(str(path), str(index_entry.get("doc_version", "unknown")),
                          bool(index_entry.get("superseded", False)))
            pages = [p.text for p in doc.pages]
    except Exception as exc:  # noqa: BLE001 - recorded as EXTRACT_FAILED, never fatal
        error = type(exc).__name__
        pages = []

    declared = _first(fm.get("page_count"), yaml_entry.get("page_count"))
    if suffix in {".pdf", ".html", ".htm"}:
        page_count: int | None = len(pages) if pages else None
    else:
        page_count = int(declared) if declared and str(declared).isdigit() else None
    superseded = str(_first(fm.get("superseded"), index_entry.get("superseded"), "false")).lower()
    extra = {k: v for k, v in fm.items() if k in {"lang", "expected_words"}}
    extra["superseded"] = "true" if superseded == "true" else "false"
    meta = DocMeta03(
        path=path,
        source=str(_first(fm.get("source"), path.name)),
        doc_id=str(_first(fm.get("doc_id"), yaml_entry.get("doc_id"), slug_03(path.stem))),
        title=_first(fm.get("title"), index_entry.get("title"), yaml_entry.get("title")),
        date=_first(fm.get("date"), index_entry.get("date"), yaml_entry.get("date")),
        version=_first(fm.get("version"), fm.get("doc_version"),
                       index_entry.get("doc_version"), yaml_entry.get("version")),
        page_count=page_count, extra=extra)
    return ExtractedDoc03(meta=meta, text="\n\n".join(pages), pages=pages,
                          extraction_error=error)


def collect_docs_03(corpus_dir: str | Path, lake_root: str | Path | None,
                    doc_ids: dict[str, dict[str, Any]] | None = None
                    ) -> list[ExtractedDoc03]:
    """Stage (copy) the corpus into <lake_root>/lake/<batch>/ and extract the lake copies.
    lake_root=None reads the corpus in place (dry runs). The repo files are never modified."""
    src = Path(corpus_dir)
    if not src.is_dir():
        raise FileNotFoundError(str(src))
    doc_ids = doc_ids if doc_ids is not None else load_doc_ids_03()
    index = _read_index_03(src)
    work = src
    if lake_root is not None:
        work = Path(lake_root) / "lake" / src.name
        work.mkdir(parents=True, exist_ok=True)
    out: list[ExtractedDoc03] = []
    for path in sorted(src.iterdir()):
        if path.name == "_index.json" and lake_root is not None:
            shutil.copy2(path, work / path.name)
            continue
        if (path.suffix.lower() not in SUPPORTED_03 or path.name.lower().startswith("readme")
                or not path.is_file()):
            continue
        target = path
        if lake_root is not None:
            target = work / path.name
            shutil.copy2(path, target)
        out.append(extract_doc_03(target, index.get(path.name), doc_ids.get(path.name)))
    return out


# --------------------------------------------------------------------- checks
def check_quality_03(doc: ExtractedDoc03, cfg: IndexerSettings03) -> CheckResult03:
    text = doc.text
    if doc.extraction_error is not None:
        return CheckResult03("quality", False, "EXTRACT_FAILED",
                             f"extraction raised {doc.extraction_error}")
    words = len(text.split())
    if len(text.strip()) < cfg.min_chars or words < cfg.min_words:
        return CheckResult03("quality", False, "EMPTY",
                             f"chars={len(text.strip())} words={words}", float(len(text.strip())))
    n = len(text)
    non_ascii = sum(1 for ch in text if ord(ch) > 127) / n
    repl = text.count("�") / n
    has_nul = "\x00" in text
    if doc.meta.extra.get("lang") != "ur" and (
            non_ascii > cfg.non_ascii_max or repl > cfg.replacement_char_max or has_nul):
        return CheckResult03("quality", False, "GARBLED_NON_ASCII",
                             f"non_ascii_ratio={non_ascii:.3f} replacement_ratio={repl:.3f}"
                             f" nul={has_nul}", non_ascii)
    alpha = sum(1 for ch in text if ch.isalpha()) / n
    if alpha < cfg.alpha_min:
        return CheckResult03("quality", False, "GARBLED_SYMBOLS",
                             f"alpha_ratio={alpha:.3f}", alpha)
    return CheckResult03("quality", True, None,
                         f"non_ascii_ratio={non_ascii:.3f} alpha_ratio={alpha:.3f}", non_ascii)


def _looks_cut_off(text: str) -> bool:
    """True when the text ends without terminal punctuation on a lower-case word,
    i.e. the last word looks cut (`...students whose attend`)."""
    stripped = text.rstrip()
    if not stripped or stripped.endswith(TERMINAL_PUNCT_03):
        return False
    last_line = stripped.splitlines()[-1]
    if HEADING_PATTERN.match(last_line):
        return False
    last = stripped.split()[-1]
    return last.isalpha() and last.islower()


def check_completeness_03(doc: ExtractedDoc03) -> CheckResult03:
    m = doc.meta
    missing = []
    if not m.source:
        missing.append("source")
    if not m.title:
        missing.append("title")
    if not (m.date or m.version):
        missing.append("date|version")
    if m.page_count is None:
        missing.append("page_count")
    if missing:
        return CheckResult03("completeness", False, "MISSING_METADATA",
                             "missing: " + ", ".join(sorted(missing)))
    if doc.extraction_error is not None or not doc.text.strip():
        return CheckResult03("completeness", True, None, "no text to test for truncation")
    assert m.page_count is not None
    if m.page_count > len(doc.pages):
        return CheckResult03("completeness", False, "TRUNCATED",
                             f"declared page_count={m.page_count} but extracted {len(doc.pages)}",
                             float(len(doc.pages)))
    expected = doc.meta.extra.get("expected_words")
    if expected and expected.isdigit():
        actual = len(doc.text.split())
        if actual < 0.6 * int(expected):
            return CheckResult03("completeness", False, "TRUNCATED",
                                 f"words={actual} < 0.6 x expected_words={expected}", float(actual))
    if _looks_cut_off(doc.text):
        return CheckResult03("completeness", False, "TRUNCATED",
                             f"text ends mid-word: ...{doc.text.rstrip()[-30:]!r}")
    return CheckResult03("completeness", True, None,
                         f"pages={len(doc.pages)} declared={m.page_count}")


def check_recency_03(doc: ExtractedDoc03, state: ManifestState03
                     ) -> tuple[CheckResult03, str | None]:
    entry = state.doc(doc.meta.doc_id)
    if not entry:
        return CheckResult03("recency", True, None, "new doc_id"), None
    cmp = compare_incoming_03(doc.meta.date, doc.meta.version,
                              entry.get("date"), entry.get("active_version"))
    old = str(entry.get("active_version"))
    if cmp > 0:
        return (CheckResult03("recency", True, "NEWER_VERSION",
                              f"incoming {doc.meta.version} is newer than indexed {old}"), old)
    if cmp < 0:
        return (CheckResult03("recency", False, "STALE_VERSION",
                              f"incoming {doc.meta.version} is older than indexed {old}"), None)
    return CheckResult03("recency", True, None, f"same version {old}"), None


def check_uniqueness_03(doc: ExtractedDoc03, text_hash: str, state: ManifestState03,
                        retained: list[tuple[str, str, list[float] | None]],
                        embed_fn: EmbedFn, cfg: IndexerSettings03
                        ) -> tuple[CheckResult03, bool, list[float] | None]:
    """Returns (result, unchanged, doc_vec). `retained` = earlier accepted batch docs."""
    did = doc.meta.doc_id
    entry = state.doc(did)
    if (entry and entry.get("content_hash") == text_hash
            and str(entry.get("active_version")) == str(doc.meta.version)):
        return (CheckResult03("uniqueness", True, "UNCHANGED",
                              "same doc_id, version and hash as the indexed copy"),
                True, entry.get("doc_vec"))
    others = [(d, h, v) for d, h, v in retained if d != did]
    others += [(d, str(e.get("content_hash")), e.get("doc_vec"))
               for d, e in sorted(state.documents.items()) if d != did]
    for other_id, other_hash, _ in others:
        if other_hash == text_hash:
            return (CheckResult03("uniqueness", False, "DUPLICATE_EXACT",
                                  f"identical text to doc_id={other_id}"), False, None)
    vec = doc_vector_03(doc.text, embed_fn, cfg.near_dup_chars)
    best, best_id = -1.0, ""
    for other_id, _, other_vec in others:
        if other_vec is not None and len(other_vec) == len(vec):
            c = cosine(vec, other_vec)
            if c > best:
                best, best_id = c, other_id
    if best >= cfg.near_dup_cosine:
        return (CheckResult03("uniqueness", False, "DUPLICATE_NEAR",
                              f"cosine={best:.4f} with doc_id={best_id}", best), False, vec)
    return (CheckResult03("uniqueness", True, None,
                          f"max_cosine={max(best, 0.0):.4f}", max(best, 0.0)), False, vec)


def verify_documents(docs: list[ExtractedDoc03], state: ManifestState03,
                     embed_fn: EmbedFn, cfg: IndexerSettings03) -> list[Verdict03]:
    """Pure: no file moves, no network. All four checks for every document.
    Processing order is (date, path) so the earlier document of a duplicate pair stays."""
    ordered = sorted(docs, key=lambda d: (d.meta.date or d.meta.version or "",
                                          str(d.meta.path.name)))
    retained: list[tuple[str, str, list[float] | None]] = []
    out: list[Verdict03] = []
    for doc in ordered:
        text_hash = sha256_text(doc.text)
        quality = check_quality_03(doc, cfg)
        completeness = check_completeness_03(doc)
        recency, supersedes = check_recency_03(doc, state)
        if quality.reason_code in {"EXTRACT_FAILED", "EMPTY", "GARBLED_NON_ASCII"}:
            unique = CheckResult03("uniqueness", True, None, "skipped: unreadable text")
            unchanged, vec = False, None
        else:
            unique, unchanged, vec = check_uniqueness_03(doc, text_hash, state, retained,
                                                         embed_fn, cfg)
        checks = [quality, completeness, recency, unique]
        decision: Literal["accept", "quarantine", "supersede"]
        if all(c.passed for c in checks):
            decision = "supersede" if supersedes is not None else "accept"
            retained.append((doc.meta.doc_id, text_hash, vec))
        else:
            decision, supersedes, unchanged = "quarantine", None, False
        out.append(Verdict03(doc=doc.meta, text_sha256=text_hash, checks=checks,
                             decision=decision, supersedes=supersedes,
                             unchanged=unchanged, doc_vec=vec))
    return out


# -------------------------------------------------------------- apply + report
def _move_03(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    try:
        os.replace(src, dst)
    except OSError:
        shutil.move(str(src), str(dst))


def totals_03(verdicts: list[Verdict03]) -> dict[str, int]:
    return {"documents": len(verdicts),
            "accepted": sum(v.decision in {"accept", "supersede"} for v in verdicts),
            "superseded_accepted": sum(v.decision == "supersede" for v in verdicts),
            "quarantined": sum(v.decision == "quarantine" for v in verdicts),
            "unchanged": sum(v.unchanged for v in verdicts)}


def apply_verdicts_03(verdicts: list[Verdict03], cfg: IndexerSettings03, *, ts: str,
                      corpus: str, embedding: str, move: bool = True,
                      results_dir: str | Path | None = None, write_report: bool = True
                      ) -> dict[str, Any]:
    """Move quarantined files out of the lake and write the report pair."""
    root = Path(cfg.ragops_root)
    qdir = root / "quarantine" / ts
    quarantined_paths: list[str] = []
    if move:
        for v in verdicts:
            if v.decision != "quarantine":
                continue
            dest = qdir / v.doc.path.name
            if dest.exists():
                dest = qdir / f"{v.doc.path.parent.name}__{v.doc.path.name}"
            if v.doc.path.exists():
                _move_03(v.doc.path, dest)
            sidecar = dest.with_name(dest.name + ".reason_03.json")
            sidecar.write_text(json.dumps({
                "codes": v.failure_codes(), "sha256": v.text_sha256,
                "checks": [c.__dict__ for c in v.checks]}, indent=1), encoding="utf-8")
            quarantined_paths.append(str(dest))
    by_reason: dict[str, int] = {}
    for v in verdicts:
        for code in v.codes():
            by_reason[code] = by_reason.get(code, 0) + 1
    report: dict[str, Any] = {
        "generated_at": ts, "corpus": corpus, "embedding": embedding,
        "totals": totals_03(verdicts), "by_reason": dict(sorted(by_reason.items())),
        "documents": [{"file": v.doc.path.name, "doc_id": v.doc.doc_id, "sha256": v.text_sha256,
                       "decision": v.decision, "supersedes": v.supersedes,
                       "unchanged": v.unchanged,
                       "checks": [c.__dict__ for c in v.checks]} for v in verdicts],
        "quarantined_paths": quarantined_paths}
    paths: dict[str, str] = {}
    if write_report:
        rdir = Path(results_dir or cfg.results_dir)
        rdir.mkdir(parents=True, exist_ok=True)
        jpath = rdir / f"verification_report_03_{ts}.json"
        mpath = rdir / f"verification_report_03_{ts}.md"
        jpath.write_text(json.dumps(report, indent=1), encoding="utf-8")
        mpath.write_text(render_markdown_03(report), encoding="utf-8")
        paths = {"json": str(jpath), "md": str(mpath)}
    return {"report": report, "paths": paths, "quarantined_paths": quarantined_paths}


def render_markdown_03(report: dict[str, Any]) -> str:
    t = report["totals"]
    lines = [f"# Verification report {report['generated_at']}", "",
             f"Corpus: `{report['corpus']}` - embedding: `{report['embedding']}`", "",
             "| documents | accepted | superseded_accepted | quarantined | unchanged |",
             "|---|---|---|---|---|",
             f"| {t['documents']} | {t['accepted']} | {t['superseded_accepted']} | "
             f"{t['quarantined']} | {t['unchanged']} |", "",
             "| file | quality | completeness | recency | uniqueness | decision |",
             "|---|---|---|---|---|---|"]
    for d in report["documents"]:
        cells = []
        for c in d["checks"]:
            mark = "✔" if c["passed"] else "✘"
            cells.append(f"{mark} {c['reason_code']}" if c["reason_code"] else mark)
        lines.append(f"| {d['file']} | " + " | ".join(cells) + f" | {d['decision']} |")
    lines += ["", "## Quarantined", ""]
    q = report["quarantined_paths"]
    lines += [f"- `{p}`" for p in q] if q else ["(none moved)"]
    return "\n".join(lines) + "\n"


# ------------------------------------------------------------------------ CLI
def make_embed_fn_03(cfg: IndexerSettings03, dummy: bool) -> tuple[EmbedFn, str]:
    if dummy:
        return dummy_embed_03, "dummy-256"
    from .embed import embed
    return (lambda texts: embed(texts, cfg)), cfg.embed_model


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Assignment 03 data verification gate.")
    ap.add_argument("--corpus", required=True)
    ap.add_argument("--lake")
    ap.add_argument("--results-dir")
    ap.add_argument("--dummy-embed", action="store_true")
    ap.add_argument("--no-move", action="store_true")
    ap.add_argument("--state")
    args = ap.parse_args(argv)
    cfg = load_settings_03()
    if args.lake:
        cfg = load_settings_03(ragops_root=args.lake)
    if not Path(args.corpus).is_dir():
        print(f"unreadable corpus dir: {args.corpus}", file=sys.stderr)
        return 2
    state_path = Path(args.state) if args.state else manifest_path_03(cfg.ragops_root)
    state = load_manifest_03(state_path)
    embed_fn, label = make_embed_fn_03(cfg, args.dummy_embed)
    docs = collect_docs_03(args.corpus, None if args.no_move else cfg.ragops_root)
    verdicts = verify_documents(docs, state, embed_fn, cfg)
    res = apply_verdicts_03(verdicts, cfg, ts=utc_ts_03(), corpus=args.corpus, embedding=label,
                            move=not args.no_move, results_dir=args.results_dir)
    log_03("verification finished", totals=res["report"]["totals"],
           by_reason=res["report"]["by_reason"], **res["paths"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
