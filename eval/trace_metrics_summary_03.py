"""Time-window summary of the five Part D metrics, computed from trace JSONL (Assignment 03 D3).

    python -m eval.trace_metrics_summary_03 [--file PATH] [--since 1h|30m|2d | --from ISO --to ISO]
           [--json] [--kubectl]

A stage that did not run (0.0 ms) is excluded from that stage's p95 so skipped stages
cannot drag it down.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime, timedelta, timezone

try:  # repo-root run
    from eval.metrics_lib_03 import percentile
except ModuleNotFoundError:  # cwd=eval
    from metrics_lib_03 import percentile  # type: ignore[no-redef]

MARK = '"schema":"trace_03/1"'
STAGES = ("cache_ms", "embed_ms", "retrieve_ms", "guardrail_ms", "rerank_ms",
          "generate_ms", "total_ms")
BINS = [f"{i / 10:.1f}-{(i + 1) / 10:.1f}" for i in range(10)]


def parse_since(text: str) -> timedelta:
    m = re.fullmatch(r"(\d+)([mhd])", text.strip())
    if not m:
        raise ValueError(f"bad --since {text!r}; use e.g. 30m, 1h, 2d")
    n, unit = int(m.group(1)), m.group(2)
    return timedelta(**{{"m": "minutes", "h": "hours", "d": "days"}[unit]: n})


def parse_ts(text: str) -> datetime:
    dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def load_records(lines: list[str]) -> list[dict]:
    out = []
    for raw in lines:
        try:
            rec = json.loads(raw)
        except ValueError:
            continue
        if isinstance(rec, dict) and rec.get("schema") == "trace_03/1":
            out.append(rec)
    return out


def _round(v: float | None) -> float:
    return 0.0 if v is None else round(v, 4)


def summarise(records: list[dict], start: datetime, end: datetime) -> dict:
    inside = []
    for r in records:
        try:
            ts = parse_ts(r["timestamp"])
        except (KeyError, ValueError):
            continue
        if start <= ts <= end:
            inside.append(r)
    n = len(inside)

    tops = []
    for r in inside:
        scores = [c["score"] for c in r.get("retrieved_chunks") or []
                  if isinstance(c.get("score"), (int, float))]
        if scores:
            tops.append(max(scores))
    hist = dict.fromkeys(BINS, 0)
    for v in tops:
        hist[BINS[min(9, int(v * 10))]] += 1

    reasons: dict[str, int] = {}
    for r in inside:
        if r.get("abstained"):
            key = str(r.get("abstain_reason") or "unknown")
            reasons[key] = reasons.get(key, 0) + 1

    lat = {}
    for stage in STAGES:
        vals = [float(r["latency_per_stage"][stage]) for r in inside
                if isinstance(r.get("latency_per_stage", {}).get(stage), (int, float))
                and r["latency_per_stage"][stage] > 0]
        lat[stage] = _round(percentile(vals, 95))

    flagged = blocked = 0
    for r in inside:
        for a in r.get("guardrail_actions") or []:
            flagged += a.get("action") == "flagged"
            blocked += a.get("action") == "blocked"

    return {
        "window": {"from": start.isoformat(), "to": end.isoformat()},
        "n_queries": n,
        "top1_similarity": {
            "n": len(tops), "min": _round(min(tops, default=None)),
            "p25": _round(percentile(tops, 25)), "p50": _round(percentile(tops, 50)),
            "p75": _round(percentile(tops, 75)), "max": _round(max(tops, default=None)),
            "histogram": hist},
        "abstention_rate": round(sum(reasons.values()) / n, 4) if n else 0.0,
        "abstention_by_reason": reasons,
        "cache_hit_rate": round(sum(1 for r in inside if r.get("cache_hit")) / n, 4) if n else 0.0,
        "latency_p95_ms_per_stage": lat,
        "injection_attempts": {"total": flagged + blocked, "flagged": flagged,
                               "blocked": blocked},
    }


def render_text(s: dict) -> str:
    t = s["top1_similarity"]
    rows = [
        ("top-1 similarity", f"n={t['n']} min={t['min']} p25={t['p25']} p50={t['p50']} "
                             f"p75={t['p75']} max={t['max']}"),
        ("abstention rate", f"{s['abstention_rate']} by reason {s['abstention_by_reason']}"),
        ("cache hit rate", str(s["cache_hit_rate"])),
        ("p95 latency per stage (ms)",
         " ".join(f"{k.removesuffix('_ms')}={v}" for k, v in s["latency_p95_ms_per_stage"].items())),
        ("injection attempts", f"total={s['injection_attempts']['total']} "
                               f"flagged={s['injection_attempts']['flagged']} "
                               f"blocked={s['injection_attempts']['blocked']}"),
    ]
    lines = [f"window: {s['window']['from']} .. {s['window']['to']}   n_queries={s['n_queries']}",
             "top-1 histogram: " + " ".join(f"{k}:{v}" for k, v in t["histogram"].items()), ""]
    width = max(len(k) for k, _ in rows)
    lines += [f"{k.ljust(width)} | {v}" for k, v in rows]
    return "\n".join(lines)


def _kubectl_lines() -> list[str]:
    lines: list[str] = []
    for target in ("deploy/api", "deploy/api-candidate-03"):
        try:
            out = subprocess.run(["kubectl", "-n", "rahbar", "logs", target, "--since=24h"],
                                 capture_output=True, text=True, timeout=120, check=False)
        except (OSError, subprocess.SubprocessError):
            continue
        lines += [ln for ln in out.stdout.splitlines() if MARK in ln]
    return lines


def _default_file() -> str:
    try:
        from api.config_03 import get_settings_03
        return get_settings_03().trace_file
    except ModuleNotFoundError:
        return "traces/traces_03.jsonl"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="trace_metrics_summary_03")
    ap.add_argument("--file", default=None)
    ap.add_argument("--since", default=None)
    ap.add_argument("--from", dest="start", default=None)
    ap.add_argument("--to", dest="end", default=None)
    ap.add_argument("--json", action="store_true", dest="as_json")
    ap.add_argument("--kubectl", action="store_true")
    args = ap.parse_args(argv)

    now = datetime.now(timezone.utc)
    try:
        if args.since:
            start, end = now - parse_since(args.since), now
        else:
            start = parse_ts(args.start) if args.start else datetime.min.replace(tzinfo=timezone.utc)
            end = parse_ts(args.end) if args.end else now
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    try:
        if args.kubectl:
            lines = _kubectl_lines()
        else:
            with open(args.file or _default_file(), encoding="utf-8") as fh:
                lines = fh.readlines()
    except OSError as exc:
        print(f"cannot read trace file: {exc}", file=sys.stderr)
        return 2
    summary = summarise(load_records(lines), start, end)
    if args.start is None and not args.since:
        summary["window"]["from"] = "beginning"
    print(json.dumps(summary, indent=2) if args.as_json else render_text(summary))
    return 0


if __name__ == "__main__":
    sys.exit(main())
