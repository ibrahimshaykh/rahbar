"""Reconstruct one query from its trace line (Assignment 03 D2). Needs only the JSONL file:
no Chroma, no network, no app.* import.

    python -m api.trace_tool_03 --trace-id ID [--file PATH] [--json] [--kubectl]

Exit codes: 0 found, 1 not found, 2 unreadable file / ambiguous prefix / bad input.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from typing import Any

try:  # run as `python -m api.x_03` from the repo root
    from api.config_03 import get_settings_03
except ModuleNotFoundError:  # cwd=api/
    from config_03 import get_settings_03  # type: ignore[no-redef]

MARK = '"schema":"trace_03/1"'
KUBECTL_TARGETS = ("deploy/api", "deploy/api-candidate-03")


class TraceFileError(Exception):
    pass


def _parse_lines(lines: list[str]) -> tuple[list[dict], int]:
    records, bad = [], 0
    for raw in lines:
        raw = raw.strip()
        if not raw:
            continue
        try:
            rec = json.loads(raw)
        except ValueError:
            bad += 1
            continue
        if isinstance(rec, dict) and "trace_id" in rec:
            records.append(rec)
        else:
            bad += 1
    return records, bad


def load_from_file(path: str) -> tuple[list[dict], int]:
    try:
        with open(path, encoding="utf-8") as fh:
            return _parse_lines(fh.readlines())
    except OSError as exc:
        raise TraceFileError(f"cannot read {path}: {exc}") from exc


def load_from_kubectl() -> tuple[list[dict], int]:
    lines: list[str] = []
    for target in KUBECTL_TARGETS:
        try:
            out = subprocess.run(["kubectl", "-n", "rahbar", "logs", target, "--since=24h"],
                                 capture_output=True, text=True, timeout=120, check=False)
        except (OSError, subprocess.SubprocessError) as exc:
            print(f"kubectl failed for {target}: {type(exc).__name__}", file=sys.stderr)
            continue
        lines += [ln for ln in out.stdout.splitlines() if MARK in ln]
    if not lines:
        raise TraceFileError("no trace lines found via kubectl logs")
    return _parse_lines(lines)


def find_record(records: list[dict], trace_id: str) -> tuple[dict | None, str | None]:
    """(record, error). Exact match wins; otherwise a unique prefix of >= 8 chars."""
    for rec in records:
        if rec.get("trace_id") == trace_id:
            return rec, None
    if len(trace_id) >= 8:
        hits = [r for r in records if str(r.get("trace_id", "")).startswith(trace_id)]
        if len(hits) == 1:
            return hits[0], None
        if len(hits) > 1:
            ids = ", ".join(str(h["trace_id"]) for h in hits)
            return None, f"ambiguous prefix {trace_id!r} matches: {ids}"
    return None, None


def render(rec: dict) -> str:
    out: list[str] = []
    add = out.append

    def section(title: str) -> None:
        add("")
        add(f"== {title} ==")

    add(f"trace_id: {rec.get('trace_id')}")
    add(f"timestamp: {rec.get('timestamp')}")
    add(f"model: {rec.get('model')}")
    add(f"collection: {rec.get('collection_name')}@{rec.get('collection_version')}")
    add(f"embedding: {rec.get('embedding_model')} ({rec.get('embedding_version')})")
    add(f"cache_hit: {rec.get('cache_hit')}")
    add(f"outcome: {rec.get('outcome')}")
    section("USER QUERY")
    add(str(rec.get("user_query")))
    if rec.get("rewritten_query") != rec.get("user_query"):
        add(f"(rewritten: {rec.get('rewritten_query')})")
    section("RETRIEVED CONTEXT")
    chunks = rec.get("retrieved_chunks") or []
    if not chunks:
        add("(no chunks retrieved)")
    for i, c in enumerate(chunks, start=1):
        add(f"[{i}] {c.get('chunk_id')} {c.get('document_id')}@{c.get('document_version')} "
            f"score={c.get('score')} source={c.get('source')} section={c.get('section')} "
            f"p.{c.get('page')}")
        add(str(c["text"]) if c.get("text") is not None else "(text not recorded: cache hit)")
    section("FILTERS")
    add(json.dumps(rec.get("filters_applied"), ensure_ascii=False))
    section("RERANKED ORDER")
    add(f"rerank_enabled={rec.get('rerank_enabled')} order={rec.get('reranked_order')}")
    section("GUARDRAILS")
    acts = rec.get("guardrail_actions") or []
    if not acts:
        add("(none)")
    for a in acts:
        add(json.dumps(a, ensure_ascii=False))
    section("FULL PROMPT")
    if rec.get("full_prompt") is not None:
        add(f"prompt_hash: {rec.get('prompt_hash')}")
        add(str(rec["full_prompt"]))
    else:
        add(f"(not sent to the LLM: {rec.get('prompt_skipped_reason')})")
    section("RESPONSE")
    add(json.dumps(rec.get("response"), indent=2, ensure_ascii=False))
    section("CITATIONS")
    add(json.dumps(rec.get("citations"), ensure_ascii=False))
    section("LATENCY PER STAGE")
    for k, v in (rec.get("latency_per_stage") or {}).items():
        add(f"{k}: {v}")
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="trace_tool_03", description=__doc__.splitlines()[0])
    ap.add_argument("--trace-id", required=True)
    ap.add_argument("--file", default=None)
    ap.add_argument("--json", action="store_true", dest="as_json")
    ap.add_argument("--kubectl", action="store_true")
    args = ap.parse_args(argv)

    try:
        if args.kubectl:
            records, bad = load_from_kubectl()
        else:
            path = args.file or get_settings_03().trace_file
            records, bad = load_from_file(path)
    except TraceFileError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    if bad:
        print(f"skipped {bad} malformed line(s)", file=sys.stderr)

    rec, err = find_record(records, args.trace_id)
    if err:
        print(err, file=sys.stderr)
        return 2
    if rec is None:
        print(f"trace {args.trace_id} not found", file=sys.stderr)
        return 1
    _emit(rec, args.as_json)
    return 0


def _emit(rec: dict[str, Any], as_json: bool) -> None:
    text = json.dumps(rec, indent=2, ensure_ascii=False) if as_json else render(rec)
    try:
        print(text)
    except UnicodeEncodeError:  # legacy Windows console
        sys.stdout.buffer.write((text + "\n").encode("utf-8"))


if __name__ == "__main__":
    sys.exit(main())
