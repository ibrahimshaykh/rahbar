"""Single runner for the three offline-test levels (Assignment 03, Part B).

    python -m eval.run_suite_03 --api URL --golden eval/golden_03.jsonl --seed 1337 --runs 2
        --out-dir eval/results [--mode live|offline] [--traces PATH|--chroma] [--require-cold]
        [--tag NAME]

Exit codes: 0 ok, 2 bad args / missing passage source, 3 cache hits under --require-cold,
4 a deterministic metric differs between runs, 5 request errors (never a baseline).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter

from eval import config_03
from eval.component_eval_03 import run_component
from eval.e2e_eval_03 import (
    ColdRunError, HttpAsk03, PassageSourceError, make_live_judge_03, make_passage_lookup_03,
    rule_judge, run_e2e,
)
from eval.module_eval_03 import load_corpus_chunks, load_pairs, run_module
from indexer.pipeline.hashing_03 import cosine, dummy_embed_03

ROOT = Path(__file__).resolve().parent.parent
OFFLINE_DOCS = [
    "eval/fixtures/academic-rules-2026.md", "eval/fixtures/fees-2026.md",
    "corpus/batch_b_03/hostel_rules_03.md", "corpus/batch_b_03/library_policy_03.md",
    "corpus/batch_b_03/transport_policy_03.md", "corpus/batch_b_03/scholarship_rules_03.md",
    "corpus/batch_b_03/exam_conduct_03.md", "corpus/batch_b_03/student_notice_injected_03.md",
    "corpus/batch_b_03/academic_rules_handbook_v2026-11_03.md",
]
DISTRACTOR_DOCS = [f"corpus/noise_03/distractor_{i}_03.md" for i in (1, 2, 3)]
LIVE_TIMING_DOCS = ["corpus/raw/fee-structure-page.html", "corpus/raw/grading-page.html",
                    "corpus/raw/student-handbook-jun-2026.pdf"]
DETERMINISTIC_MODULE = ("paraphrase_mean_cos", "unrelated_mean_cos", "separation_gap",
                        "n_paraphrase", "n_unrelated", "n_timed_chunks")


@dataclass
class _P:
    chunk_id: str
    text: str
    score: float


class StubApi03:
    """Scripted offline API: dummy_embed_03 + in-memory cosine retrieval + a floor.
    Plumbing and tests only; results carry mode 'offline'."""

    def __init__(self, paths: list[str], size: int = 400, overlap: int = 50, top_k: int = 5,
                 floor: float = 0.45, rerank_pool: int = 0) -> None:
        config_03.ensure_paths()
        from pipeline.chunk import chunk
        from pipeline.extract import extract

        self.top_k, self.floor, self.rerank_pool = top_k, floor, rerank_pool
        self.size, self.overlap = size, overlap
        self.chunks = []
        for p in paths:
            fp = ROOT / p
            if fp.exists():
                self.chunks += chunk(extract(str(fp), "offline", False), size, overlap)
        self.vecs = dummy_embed_03([c.text for c in self.chunks])
        self._by_id = {c.id: c.text for c in self.chunks}

    def config(self) -> dict:
        return {"top_k": self.top_k, "chunk_size": self.size, "chunk_overlap": self.overlap,
                "rerank": bool(self.rerank_pool), "prompt_template": "offline-stub"}

    def lookup(self, ids: list[str]) -> dict[str, str]:
        return {i: self._by_id[i] for i in ids if i in self._by_id}

    def __call__(self, question: str) -> dict:
        t0 = perf_counter()
        qv = dummy_embed_03([question])[0]
        scored = sorted(((cosine(qv, v), i) for i, v in enumerate(self.vecs)),
                        key=lambda t: (-t[0], t[1]))
        pool = scored[: max(self.rerank_pool, self.top_k)]
        passages = [_P(self.chunks[i].id, self.chunks[i].text, s) for s, i in pool]
        if self.rerank_pool:
            from api.rerank_03 import LexicalReranker03

            passages, _ = LexicalReranker03(self.rerank_pool, self.top_k).rerank(question, passages)
        else:
            passages = passages[: self.top_k]
        meta = {c.id: c for c in self.chunks}
        retrieved = [{"chunk_id": p.chunk_id, "source": meta[p.chunk_id].source,
                      "section": meta[p.chunk_id].section, "page": meta[p.chunk_id].page,
                      "score": p.score} for p in passages]
        top = passages[0] if passages else None
        answered = bool(top and max(p.score for p in passages) >= self.floor)
        resp = {"request_id": "offline", "provider": "offline-stub", "retrieved": retrieved,
                "answered_from_context": answered,
                "confidence": "low", "citations": [], "answer": "I could not find this."}
        if answered and top:
            m = meta[top.chunk_id]
            resp["answer"] = " ".join(top.text.split()[:30])
            resp["citations"] = [{"source": m.source, "section": m.section, "page": m.page}]
        return {"response": resp, "latency_ms": (perf_counter() - t0) * 1000.0, "cache": "miss",
                "trace_id": None, "error": None}


# ---------------------------------------------------------------- helpers

def sha256_file(path: str | Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def git_sha() -> str:
    try:
        return subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True,
                              text=True, check=True, cwd=ROOT).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def load_golden(path: str | Path) -> list[dict]:
    return [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines()
            if line.strip()]


def flatten(d: dict, prefix: str = "") -> dict[str, float]:
    out: dict[str, float] = {}
    for k, v in d.items():
        key = f"{prefix}{k}"
        if isinstance(v, bool):
            continue
        if isinstance(v, (int, float)):
            out[key] = float(v)
        elif isinstance(v, dict):
            out.update(flatten(v, key + "."))
    return out


def is_deterministic(key: str) -> bool:
    level, _, rest = key.partition(".")
    if level == "component":
        return True
    return level == "module" and rest in DETERMINISTIC_MODULE


def _explain(key: str) -> str:
    if "latency" in key or "embed_ms" in key:
        return "network/CPU scheduling and model decode time vary run to run"
    if is_deterministic(key):
        return "WARNING: index or cache changed between runs"
    return ("LLM sampling variance (temperature>0 in the API) and judge nondeterminism")


def fetch_config(api: str) -> dict:
    import httpx

    try:
        r = httpx.get(f"{api.rstrip('/')}/api/config_03", timeout=10.0)
        return r.json() if r.status_code == 200 else {}
    except (httpx.HTTPError, ValueError):
        return {}


def render_summary(runs: list[dict], tag: str) -> tuple[str, list[str]]:
    """Returns (markdown, deterministic keys that differ). Numbers come from data only."""
    flat = [flatten({lv: r[lv] for lv in ("module", "component", "e2e")}) for r in runs]
    keys = sorted(set().union(*flat))
    lines = [f"# Suite summary ({tag}, mode {runs[0]['mode']})", "",
             "| metric | " + " | ".join(f"run{i + 1}" for i in range(len(runs))) + " | abs delta |",
             "| --- | " + " | ".join("---:" for _ in runs) + " | ---: |"]
    diffs: list[tuple[str, float]] = []
    for k in keys:
        vals = [f.get(k) for f in flat]
        nums = [v for v in vals if v is not None]
        delta = (max(nums) - min(nums)) if len(nums) == len(vals) and nums else None
        cells = ["n/a" if v is None else f"{v:.6g}" for v in vals]
        lines.append(f"| {k} | " + " | ".join(cells) + f" | {'n/a' if delta is None else f'{delta:.6g}'} |")
        if delta:
            diffs.append((k, delta))
    lines += ["", "## Differences and explanation", ""]
    bad: list[str] = []
    if not diffs:
        lines.append("All metrics identical between runs.")
    for k, delta in diffs:
        lines.append(f"- `{k}`: |delta| = {delta:.6g}. {_explain(k)}.")
        if is_deterministic(k) and delta > 1e-12:
            bad.append(k)
    if not any(is_deterministic(k) for k, _ in diffs):
        lines.append("- recall_*, mrr, ndcg: identical between runs; retrieval is deterministic "
                     "given a fixed index and embeddings, so delta = 0 is expected.")
    return "\n".join(lines) + "\n", bad


def build_context(args: argparse.Namespace, golden: list[dict]) -> dict:
    pairs = load_pairs(ROOT / "eval" / "module_pairs_03.json")
    human_path = Path(args.human)
    human = json.loads(human_path.read_text(encoding="utf-8")) if human_path.exists() else []
    if args.mode == "offline":
        api = StubApi03(OFFLINE_DOCS)
        noise_api = StubApi03(OFFLINE_DOCS + DISTRACTOR_DOCS)
        return {"ask": api, "noise_ask": noise_api, "lookup": api.lookup, "judge": rule_judge,
                "judge_name": "rule", "embed": dummy_embed_03, "pairs": pairs, "human": human,
                "timing": load_corpus_chunks(OFFLINE_DOCS[:2] + OFFLINE_DOCS[2:], 60, 10, 50),
                "config": api.config(), "collection": "offline-memory",
                "embed_model": "dummy_embed_03", "n_distractors": len(DISTRACTOR_DOCS)}
    # live
    lookup = make_passage_lookup_03(
        traces=args.traces, chroma=args.chroma,
        chroma_cfg={"host": config_03.env_str("CHROMA_HOST", "chroma"),
                    "port": config_03.env_str("CHROMA_PORT", "8000"),
                    "collection": config_03.env_str("CHROMA_COLLECTION", "rahbar_ragops_03")})
    config_03.ensure_paths()
    from pipeline.config import get_settings
    from pipeline.embed import embed as real_embed

    settings = get_settings()
    cfg = fetch_config(args.api)
    judge = rule_judge if args.judge == "rule" else make_live_judge_03()
    return {"ask": HttpAsk03(args.api), "noise_ask": HttpAsk03(args.noise_api) if args.noise_api else None,
            "lookup": lookup, "judge": judge, "judge_name": args.judge,
            "embed": lambda texts: real_embed(texts, settings), "pairs": pairs, "human": human,
            "timing": load_corpus_chunks(LIVE_TIMING_DOCS, int(cfg.get("chunk_size") or 400),
                                         int(cfg.get("chunk_overlap") or 50), 50),
            "config": {k: cfg.get(k) for k in ("top_k", "chunk_size", "chunk_overlap", "rerank",
                                               "prompt_template")},
            "collection": cfg.get("collection") or config_03.env_str("CHROMA_COLLECTION", ""),
            "embed_model": cfg.get("embed_model") or config_03.env_str("EMBED_MODEL", ""),
            "n_distractors": 3 if args.noise_api else 0}


def run_once(args: argparse.Namespace, golden: list[dict], ctx: dict, run_idx: int,
             golden_hash: str) -> tuple[dict, int]:
    random.seed(args.seed)
    started = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    module = run_module(ctx["pairs"], ctx["embed"], ctx["timing"])
    component, err_c = run_component(golden, ctx["ask"], args.seed, noise_ask=ctx["noise_ask"],
                                     n_distractor_docs=ctx["n_distractors"])
    e2e, _, err_e = run_e2e(golden, ctx["ask"], ctx["judge"], ctx["lookup"], ctx["human"],
                            ctx["judge_name"], args.require_cold)
    suite = {"schema": "suite_03/1", "tag": args.tag, "run": run_idx, "mode": args.mode,
             "seed": args.seed, "git_sha": git_sha(), "api": args.api,
             "collection": ctx["collection"], "embed_model": ctx["embed_model"],
             "golden_sha256": golden_hash, "config": ctx["config"],
             "module": module, "component": component, "e2e": e2e, "errors": err_c + err_e,
             "started_at": started,
             "finished_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}
    return suite, err_c + err_e


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="run_suite_03")
    ap.add_argument("--api", required=True)
    ap.add_argument("--golden", default="eval/golden_03.jsonl")
    ap.add_argument("--seed", type=int, default=1337)
    ap.add_argument("--runs", type=int, default=2)
    ap.add_argument("--out-dir", default="eval/results")
    ap.add_argument("--mode", choices=["live", "offline"], default="live")
    ap.add_argument("--traces")
    ap.add_argument("--chroma", action="store_true")
    ap.add_argument("--require-cold", action="store_true")
    ap.add_argument("--tag", default="untagged")
    ap.add_argument("--judge", choices=["rule", "llm"], default="llm")
    ap.add_argument("--noise-api")
    ap.add_argument("--human", default="eval/human_faithfulness_03.json")
    try:
        args = ap.parse_args(argv)
    except SystemExit:
        return 2
    if args.runs < 1:
        print("--runs must be >= 1", file=sys.stderr)
        return 2
    try:
        golden = load_golden(args.golden)
        golden_hash = sha256_file(args.golden)
        ctx = build_context(args, golden)
    except PassageSourceError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except (OSError, ValueError) as exc:
        print(f"bad input: {exc}", file=sys.stderr)
        return 2
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    suites, total_errors = [], 0
    for k in range(1, args.runs + 1):
        try:
            suite, errs = run_once(args, golden, ctx, k, golden_hash)
        except ColdRunError as exc:
            print(f"cold-run violation: {exc}", file=sys.stderr)
            return 3
        total_errors += errs
        (out_dir / f"suite_03_{args.tag}_{ts}_run{k}.json").write_text(
            json.dumps(suite, indent=2), encoding="utf-8")
        suites.append(suite)
    summary, bad = render_summary(suites, args.tag)
    (out_dir / f"summary_03_{ts}.md").write_text(summary, encoding="utf-8")
    print(summary)
    if total_errors:
        print(f"FAIL: {total_errors} request error(s); not a valid baseline", file=sys.stderr)
        return 5
    if bad:
        print(f"WARNING: index or cache changed between runs: {bad}", file=sys.stderr)
        return 4
    return 0


if __name__ == "__main__":
    sys.exit(main())
