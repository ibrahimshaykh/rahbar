"""Drift and query-coverage checking (Assignment 03, Part E).

    python -m eval.drift_coverage_03 --live eval/live_queries_03.jsonl --golden eval/golden_03.jsonl
        [--sim-threshold F] [--coverage-threshold 0.85] [--embed dummy|real]
        [--expand eval/golden_expanded_03.jsonl] [--apply-expansion] [--out-dir eval/results]
        [--check-only] [--data-drift --mode live|offline --before-api URL --after-api URL]

Exit codes: 0 ok, 1 coverage below threshold (the gap gate), 2 bad input,
3 data-drift run requested but collection/API unavailable.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from eval import config_03
from eval.metrics_lib_03 import cosine, mean
from indexer.pipeline.hashing_03 import dummy_embed_03

EmbedFn = Callable[[list[str]], list[list[float]]]
TOL = 1e-12
STOP = frozenset("""a an the of to in on for and or is are was were be been by with at as that this it its
from not no do does did i me my we our you your can could should would will shall may might must how what
when where which who whom why there their they them he she his her if then than so such into over under
about after before between during per any each other some more most also only own same too very just get
got have has had having need needs want wants tell please much many one two""".split())
_WORD = re.compile(r"[a-z0-9]+")


class DriftInputError(ValueError):
    """Bad or missing input (CLI exit 2)."""


# ---------------------------------------------------------------- loading

def load_jsonl(path: str | Path) -> list[dict]:
    try:
        text = Path(path).read_text(encoding="utf-8")
    except OSError as exc:
        raise DriftInputError(f"cannot read {path}: {exc}") from exc
    rows = []
    for n, line in enumerate(text.splitlines(), 1):
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except ValueError as exc:
            raise DriftInputError(f"{path}:{n}: invalid JSON") from exc
    if not rows:
        raise DriftInputError(f"{path}: no rows")
    return rows


def dummy_embed_nostop(texts: list[str]) -> list[list[float]]:
    """dummy_embed_03 over stop-word-stripped tokens. The raw hashed bag-of-words is dominated by
    question words (how/what/the), which made unrelated queries look covered; stripping them gives
    a usable lexical stand-in for plumbing and the offline coverage demo. Not a real embedder."""
    return dummy_embed_03([" ".join(_tokens(t)) for t in texts])


def real_embed_fn() -> EmbedFn:
    config_03.ensure_paths()
    from pipeline.config import get_settings
    from pipeline.embed import embed

    settings = get_settings()
    return lambda texts: embed(texts, settings)


# ---------------------------------------------------------------- core steps

def max_sims(live_vecs: list[list[float]], gold_vecs: list[list[float]],
             gold_ids: list[str]) -> list[tuple[float, str]]:
    """Per live query: (max cosine over golden questions, nearest golden id)."""
    out = []
    for lv in live_vecs:
        best, best_id = -2.0, ""
        for gv, gid in zip(gold_vecs, gold_ids):
            s = cosine(lv, gv)
            if s > best:
                best, best_id = s, gid
        out.append((best, best_id))
    return out


def coverage(sims: list[float], threshold: float) -> float:
    """Share of queries with max_sim >= threshold (equality counts as covered)."""
    if not sims:
        return 0.0
    return sum(1 for s in sims if s >= threshold - TOL) / len(sims)


def has_gap(cov: float, coverage_threshold: float) -> bool:
    return cov < coverage_threshold - TOL


def _mean_vec(vs: list[list[float]]) -> list[float]:
    return [sum(c) / len(vs) for c in zip(*vs)]


def _tokens(text: str) -> list[str]:
    return [t for t in _WORD.findall(text.lower()) if t not in STOP and len(t) > 2]


def cluster_queries(ids: list[str], texts: list[str], vecs: list[list[float]],
                    sim: float) -> list[dict]:
    """Deterministic leader clustering + one refinement pass + singleton merge. Returns
    [{"members": [idx...]}] ordered by size desc then first id."""
    order = sorted(range(len(ids)), key=lambda i: ids[i])
    clusters: list[list[int]] = []
    cents: list[list[float]] = []
    for i in order:
        for ci, c in enumerate(cents):
            if cosine(vecs[i], c) >= sim - TOL:
                clusters[ci].append(i)
                cents[ci] = _mean_vec([vecs[j] for j in clusters[ci]])
                break
        else:
            clusters.append([i])
            cents.append(list(vecs[i]))
    if len(clusters) > 1:                                     # refinement pass
        assign = [[] for _ in clusters]
        for i in order:
            ci = max(range(len(cents)), key=lambda c: (cosine(vecs[i], cents[c]), -c))
            assign[ci].append(i)
        clusters = [a for a in assign if a]
        cents = [_mean_vec([vecs[j] for j in a]) for a in clusters]
    while len(clusters) > 1 and any(len(c) == 1 for c in clusters):   # merge singletons
        si = next(k for k, c in enumerate(clusters) if len(c) == 1)
        others = [k for k in range(len(clusters)) if k != si]
        tgt = max(others, key=lambda k: (cosine(cents[si], cents[k]), -k))
        clusters[tgt] = sorted(clusters[tgt] + clusters[si], key=lambda i: ids[i])
        cents[tgt] = _mean_vec([vecs[j] for j in clusters[tgt]])
        del clusters[si], cents[si]
    clusters.sort(key=lambda c: (-len(c), min(ids[i] for i in c)))
    return [{"members": sorted(c, key=lambda i: ids[i])} for c in clusters]


def topic_labels(cluster_texts: list[list[str]], top: int = 3) -> list[str]:
    """Top tokens by tf-idf over the clusters (stop-words excluded)."""
    docs = [Counter(t for q in qs for t in _tokens(q)) for qs in cluster_texts]
    n = len(docs)
    df = Counter(t for d in docs for t in d)
    labels = []
    for d in docs:
        scored = sorted(d, key=lambda t: (-(d[t] * (math.log((n + 1) / (df[t] + 1)) + 1.0)), t))
        labels.append(" ".join(scored[:top]))
    return labels


def analyse(live: list[dict], golden: list[dict], embed: EmbedFn, sim_threshold: float,
            coverage_threshold: float, cluster_sim: float) -> dict:
    live_vecs = embed([r["query"] for r in live])
    gold_vecs = embed([g["question"] for g in golden])
    ms = max_sims(live_vecs, gold_vecs, [g["id"] for g in golden])
    sims = [s for s, _ in ms]
    cov = coverage(sims, sim_threshold)
    unc = [i for i, s in enumerate(sims) if s < sim_threshold - TOL]
    topics = []
    if unc:
        cl = cluster_queries([live[i]["id"] for i in unc], [live[i]["query"] for i in unc],
                             [live_vecs[i] for i in unc], cluster_sim)
        labels = topic_labels([[live[unc[m]]["query"] for m in c["members"]] for c in cl])
        for c, lab in zip(cl, labels):
            qs = [unc[m] for m in c["members"]]
            topics.append({"topic": lab, "size": len(qs), "queries": [live[i]["id"] for i in qs],
                           "mean_max_sim": mean([sims[i] for i in qs])})
    return {
        "n_live": len(live), "n_golden": len(golden), "sim_threshold": sim_threshold,
        "coverage_threshold": coverage_threshold, "coverage": cov,
        "gap": has_gap(cov, coverage_threshold), "n_uncovered": len(unc), "clusters": topics,
        "per_query": [{"id": r["id"], "group": r.get("group"), "max_sim": s, "nearest_golden": g}
                      for r, (s, g) in zip(live, ms)],
    }


# ---------------------------------------------------------------- expansion merge

def merge_golden_text(golden_text: str, expanded_rows: list[dict]) -> str:
    """Append expansion rows; the original text is kept byte-identical (prefix)."""
    ids = [r.get("id", "") for r in expanded_rows]
    want = [f"G03-{101 + i:03d}" for i in range(len(ids))]
    if ids != want:
        raise DriftInputError(f"expansion ids must be contiguous from G03-101, got {ids}")
    base = golden_text if golden_text.endswith("\n") else golden_text + "\n"
    if golden_text and not golden_text.endswith("\n"):
        raise DriftInputError("golden file must end with a newline before appending")
    return base + "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in expanded_rows)


# ---------------------------------------------------------------- data drift

def is_batch_b(item: dict) -> bool:
    return str(item.get("ground_truth_source") or "").endswith("_03.md")


def bucket_split(items: list[dict]) -> dict[str, list[dict]]:
    return {"non_batch_b": [i for i in items if not is_batch_b(i)],
            "needs_batch_b": [i for i in items if is_batch_b(i)]}


def data_drift(items: list[dict], evaluate_before: Callable[[list[dict]], dict],
               evaluate_after: Callable[[list[dict]], dict]) -> dict:
    """`evaluate_*` map a list of golden items to a metrics dict (injected evaluator)."""
    out: dict = {}
    for name, subset in bucket_split(items).items():
        b, a = evaluate_before(subset), evaluate_after(subset)
        out[name] = {"n_items": len(subset), "before": b, "after": a,
                     "delta": {k: (None if b.get(k) is None or a.get(k) is None else a[k] - b[k])
                               for k in b if isinstance(b.get(k), (int, float))}}
    return out


def component_evaluator(ask) -> Callable[[list[dict]], dict]:
    from eval.component_eval_03 import aggregate, score_items

    def ev(subset: list[dict]) -> dict:
        rows, errors = score_items(subset, ask)
        if errors:
            raise ConnectionError(f"{errors} request(s) failed")
        m = aggregate(rows)
        un = [i for i in subset if i["category"] == "unanswerable"]
        if un:
            resp = [ask(i["question"])["response"] for i in un]
            # a retrieval-only response has no answer: report no abstention figure at all
            judged = [r for r in resp if r and "answered_from_context" in r]
            if judged:
                m["abstention_correctness"] = mean([0.0 if r["answered_from_context"] else 1.0
                                                    for r in judged])
        return m
    return ev


def top1_mean(ask, live: list[dict]) -> float | None:
    vals = []
    for r in live:
        resp = ask(r["query"]).get("response")
        if resp and resp.get("retrieved"):
            vals.append(resp["retrieved"][0]["score"])
    return mean(vals)


# ---------------------------------------------------------------- reporting

def render_md(rep: dict) -> str:
    def block(title: str, r: dict) -> list[str]:
        lines = [f"## {title}", "",
                 f"- coverage: {r['coverage']:.4f} (threshold {r['coverage_threshold']}, "
                 f"sim threshold {r['sim_threshold']}), live {r['n_live']}, golden {r['n_golden']}",
                 f"- gap flag: {'GAP' if r['gap'] else 'ok'}", ""]
        if r["clusters"]:
            lines += ["| topic | size | queries | mean max_sim |", "| --- | ---: | --- | ---: |"]
            for c in r["clusters"]:
                lines.append(f"| {c['topic']} | {c['size']} | {', '.join(c['queries'])} | "
                             f"{c['mean_max_sim']:.4f} |")
            lines.append("")
        return lines
    lines = [f"# Drift coverage ({rep['embed']})", ""] + block("Before" if "after" in rep else "Run", rep)
    if "after" in rep:
        lines += block("After expansion", rep["after"])
        lines.append(f"Delta coverage: {rep['after']['coverage'] - rep['coverage']:+.4f}")
    return "\n".join(lines) + "\n"


def write_reports(rep: dict, out_dir: Path, ts: str) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    j, m = out_dir / f"drift_coverage_03_{ts}.json", out_dir / f"drift_coverage_03_{ts}.md"
    j.write_text(json.dumps(rep, indent=2), encoding="utf-8")
    m.write_text(render_md(rep), encoding="utf-8")
    return [j, m]


# ---------------------------------------------------------------- CLI

def run_data_drift(args: argparse.Namespace, golden: list[dict], live: list[dict]) -> int:
    from eval.e2e_eval_03 import HttpRetrieve03

    try:
        if args.mode == "offline":
            from eval.run_suite_03 import OFFLINE_DOCS, StubApi03

            before = StubApi03(OFFLINE_DOCS[:2])
            after = StubApi03(OFFLINE_DOCS)
        else:
            if not (args.before_api and args.after_api):
                raise DriftInputError("--before-api and --after-api are required in live mode")
            # data drift compares retrieval only: no LLM answer per golden item
            before = HttpRetrieve03(args.before_api)
            after = HttpRetrieve03(args.after_api)
        res = data_drift(golden, component_evaluator(before), component_evaluator(after))
        shift = {"top1_mean_before": top1_mean(before, live), "top1_mean_after": top1_mean(after, live)}
    except (ConnectionError, OSError) as exc:
        print(f"data drift: collection/API unavailable: {exc}", file=sys.stderr)
        return 3
    rep = {"schema": "drift_data_03/1", "mode": args.mode, "buckets": res, "top1_shift": shift}
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / f"drift_data_03_{ts}.json").write_text(json.dumps(rep, indent=2), encoding="utf-8")
    print(json.dumps(rep, indent=2))
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="drift_coverage_03")
    ap.add_argument("--live", default="eval/live_queries_03.jsonl")
    ap.add_argument("--golden", default="eval/golden_03.jsonl")
    ap.add_argument("--sim-threshold", type=float)
    ap.add_argument("--coverage-threshold", type=float, default=0.85)
    ap.add_argument("--embed", choices=["dummy", "real"], default="dummy")
    ap.add_argument("--k-topics", default="auto")
    ap.add_argument("--expand")
    ap.add_argument("--apply-expansion", action="store_true")
    ap.add_argument("--out-dir", default="eval/results")
    ap.add_argument("--check-only", action="store_true")
    ap.add_argument("--data-drift", action="store_true")
    ap.add_argument("--mode", choices=["live", "offline"], default="offline")
    ap.add_argument("--before-api")
    ap.add_argument("--after-api")
    try:
        args = ap.parse_args(argv)
    except SystemExit:
        return 2
    try:
        live, golden = load_jsonl(args.live), load_jsonl(args.golden)
        expanded = load_jsonl(args.expand) if args.expand else None
        if args.apply_expansion:
            if expanded is None:
                raise DriftInputError("--apply-expansion needs --expand")
            gp = Path(args.golden)
            gp.write_text(merge_golden_text(gp.read_text(encoding="utf-8"), expanded),
                          encoding="utf-8", newline="")
            print(f"appended {len(expanded)} items to {args.golden}")
            return 0
        if args.data_drift:
            return run_data_drift(args, golden, live)
        embed = dummy_embed_nostop if args.embed == "dummy" else real_embed_fn()
    except DriftInputError as exc:
        print(f"bad input: {exc}", file=sys.stderr)
        return 2
    sim_t = args.sim_threshold if args.sim_threshold is not None \
        else config_03.sim_threshold_default(args.embed)
    cl_sim = config_03.cluster_sim_default(args.embed)
    rep = analyse(live, golden, embed, sim_t, args.coverage_threshold, cl_sim)
    rep["embed"] = args.embed
    final = rep
    if expanded is not None:
        rep["after"] = analyse(live, golden + expanded, embed, sim_t, args.coverage_threshold, cl_sim)
        final = rep["after"]
    if not args.check_only:
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        write_reports(rep, Path(args.out_dir), ts)
    print(f"coverage before: {rep['coverage']:.4f} (sim threshold {sim_t}, embed {args.embed})")
    if expanded is not None:
        print(f"coverage after:  {final['coverage']:.4f}  delta {final['coverage'] - rep['coverage']:+.4f}")
    for c in final["clusters"]:
        print(f"  uncovered topic '{c['topic']}' size {c['size']} queries {c['queries']}")
    if final["gap"]:
        print(f"GAP: coverage {final['coverage']:.2f} < {args.coverage_threshold}")
        return 1
    print(f"OK: coverage {final['coverage']:.2f} >= {args.coverage_threshold}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
