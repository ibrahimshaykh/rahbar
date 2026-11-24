"""Part A1 tests: the verification gate (harness_03/03 section 7)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from pipeline.config import IndexerSettings
from pipeline.config_03 import load_settings_03
from pipeline.hashing_03 import cosine, dummy_embed_03, sha256_text
from pipeline.state_03 import ManifestState03
from pipeline.verify_03 import (DocMeta03, ExtractedDoc03, apply_verdicts_03, collect_docs_03,
                                compare_versions_03, extract_doc_03, parse_front_matter_03,
                                utc_ts_03, verify_documents)

REPO = Path(__file__).resolve().parents[2]
BATCH_B = REPO / "corpus" / "batch_b_03"

GOOD = ("The Examination Office publishes the date sheet two weeks before the first paper. "
        "Students must read the notice carefully and report any clash to their department. "
        "Each paper lasts ninety minutes and begins at nine in the morning. Late arrivals are "
        "not admitted after thirty minutes. The office is open on working days from nine to four.")


def base_settings() -> IndexerSettings:
    return IndexerSettings(embed_model="dummy-256", chroma_host="x", chroma_port=1,
                           collection="c", corpus_dir="", chunk_size=400, chunk_overlap=50,
                           ollama_url="")


def cfg(tmp_path: Path, **kw: object):
    return load_settings_03(base_settings(), ragops_root=str(tmp_path / "root"),
                            results_dir=str(tmp_path / "results"), **kw)


def mk(text: str = GOOD, *, doc_id: str = "d1", title: str | None = "T", date: str | None = "2026-01-01",
       version: str | None = "2026-01", page_count: int | None = 1, pages: list[str] | None = None,
       error: str | None = None, extra: dict[str, str] | None = None,
       path: Path | None = None) -> ExtractedDoc03:
    meta = DocMeta03(path=path or Path(f"{doc_id}.md"), source=f"{doc_id}.md", doc_id=doc_id,
                     title=title, date=date, version=version, page_count=page_count,
                     extra=extra or {})
    return ExtractedDoc03(meta=meta, text=text, pages=pages if pages is not None else [text],
                          extraction_error=error)


def run(docs, tmp_path, state=None):
    return verify_documents(docs, state or ManifestState03(), dummy_embed_03, cfg(tmp_path))


def codes(v):
    return {c.check: c.reason_code for c in v.checks}


def state_with(doc_id="d1", version="2026-01", date="2026-01-01", text=GOOD, vec=None):
    s = ManifestState03()
    s.documents[doc_id] = {"active_version": version, "date": date,
                           "content_hash": sha256_text(text), "doc_vec": vec, "chunks": {}}
    return s


# ---- hashing / cosine
def test_T_A1_HASH_01_whitespace_insensitive():
    assert sha256_text("Hello   World\n\nfoo") == sha256_text(" hello world foo ")


def test_T_A1_HASH_02_different_text_different_hash():
    assert sha256_text("alpha beta") != sha256_text("alpha gamma")


def test_T_A1_HASH_03_cosine_identity_and_orthogonal():
    v = dummy_embed_03(["alpha beta gamma"])[0]
    assert abs(cosine(v, v) - 1.0) < 1e-9
    assert cosine([1.0, 0.0], [0.0, 1.0]) == 0.0


# ---- quality
def test_T_A1_Q_01_empty(tmp_path):
    v = run([mk("   ")], tmp_path)[0]
    assert codes(v)["quality"] == "EMPTY" and v.decision == "quarantine"


def test_T_A1_Q_02_non_ascii(tmp_path):
    text = "çñжæ " * 60 + GOOD[:120]
    v = run([mk(text)], tmp_path)[0]
    assert codes(v)["quality"] == "GARBLED_NON_ASCII"


def test_T_A1_Q_03_nul_bytes(tmp_path):
    v = run([mk(GOOD + "\x00\x00")], tmp_path)[0]
    assert codes(v)["quality"] == "GARBLED_NON_ASCII"


def test_T_A1_Q_04_extraction_error(tmp_path):
    v = run([mk("", error="ValueError", pages=[])], tmp_path)[0]
    assert codes(v)["quality"] == "EXTRACT_FAILED"


def test_T_A1_Q_05_normal_text_passes(tmp_path):
    v = run([mk()], tmp_path)[0]
    assert codes(v) == {"quality": None, "completeness": None, "recency": None, "uniqueness": None}
    assert v.decision == "accept"


def test_T_A1_Q_06_symbol_noise(tmp_path):
    v = run([mk("#@$% 1234 !!?? " * 40)], tmp_path)[0]
    assert codes(v)["quality"] == "GARBLED_SYMBOLS"


def test_T_A1_Q_07_urdu_declared_skips_non_ascii_rule(tmp_path):
    text = ("السلام عليكم " * 40)
    v = run([mk(text, extra={"lang": "ur"})], tmp_path)[0]
    assert codes(v)["quality"] is None


# ---- completeness
def test_T_A1_C_01_missing_title(tmp_path):
    v = run([mk(title=None)], tmp_path)[0]
    assert codes(v)["completeness"] == "MISSING_METADATA"
    assert "title" in v.checks[1].detail


def test_T_A1_C_02_neither_date_nor_version(tmp_path):
    v = run([mk(date=None, version=None)], tmp_path)[0]
    assert codes(v)["completeness"] == "MISSING_METADATA" and "date|version" in v.checks[1].detail


def test_T_A1_C_03_declared_pages_exceed_extracted(tmp_path):
    v = run([mk(page_count=5, pages=[GOOD] * 3)], tmp_path)[0]
    assert codes(v)["completeness"] == "TRUNCATED"


def test_T_A1_C_04_cut_mid_word(tmp_path):
    v = run([mk(GOOD + " The Registrar lists the students whose attend")], tmp_path)[0]
    assert codes(v)["completeness"] == "TRUNCATED" and v.decision == "quarantine"


def test_T_A1_C_05_complete_doc_no_false_positive(tmp_path):
    v = run([mk(GOOD), mk(GOOD + "\n\n## 2. Heading Only", doc_id="d2")], tmp_path)
    assert all(codes(x)["completeness"] is None for x in v)


def test_T_A1_C_06_expected_words(tmp_path):
    v = run([mk(extra={"expected_words": "500"})], tmp_path)[0]
    assert codes(v)["completeness"] == "TRUNCATED"


def test_T_A1_C_07_all_metadata_missing_lists_alphabetically(tmp_path):
    v = run([mk(title=None, date=None, version=None, page_count=None)], tmp_path)[0]
    assert v.checks[1].detail == "missing: date|version, page_count, title"


# ---- recency
def test_T_A1_R_01_new_doc_id_passes(tmp_path):
    v = run([mk()], tmp_path, state_with("other", text="something else entirely"))[0]
    assert codes(v)["recency"] is None and v.decision == "accept"


def test_T_A1_R_02_newer_supersedes(tmp_path):
    v = run([mk(version="2026-11", date="2026-11-01")], tmp_path, state_with(text="old text"))[0]
    assert v.decision == "supersede" and v.supersedes == "2026-01"
    assert codes(v)["recency"] == "NEWER_VERSION" and v.checks[2].passed


def test_T_A1_R_03_older_is_stale(tmp_path):
    v = run([mk(version="2025-01", date="2025-01-01")], tmp_path, state_with(text="old text"))[0]
    assert codes(v)["recency"] == "STALE_VERSION" and v.decision == "quarantine"


def test_T_A1_R_04_version_ordering():
    assert compare_versions_03("2026-11", "2026-06") == 1
    assert compare_versions_03("2026-06", "2026-11") == -1
    assert compare_versions_03("2026", "2026") == 0
    assert compare_versions_03("1.10", "1.9") == 1     # natural sort, not lexicographic


# ---- uniqueness
def test_T_A1_U_01_exact_duplicate_later_is_quarantined(tmp_path):
    a, b = mk(doc_id="a"), mk(doc_id="b")
    vs = {v.doc.doc_id: v for v in run([b, a], tmp_path)}
    assert vs["a"].decision == "accept"
    assert codes(vs["b"])["uniqueness"] == "DUPLICATE_EXACT" and vs["b"].decision == "quarantine"


def test_T_A1_U_02_same_doc_same_hash_is_unchanged(tmp_path):
    v = run([mk()], tmp_path, state_with())[0]
    assert v.unchanged and v.decision == "accept" and codes(v)["uniqueness"] == "UNCHANGED"


def test_T_A1_U_03_deterministic_tie_break(tmp_path):
    docs = [mk(doc_id=n) for n in ("z", "m", "a")]
    first = [(v.doc.doc_id, v.decision) for v in run(docs, tmp_path)]
    second = [(v.doc.doc_id, v.decision) for v in run(list(reversed(docs)), tmp_path)]
    assert sorted(first) == sorted(second)
    assert dict(first)["a"] == "accept" and dict(first)["m"] == "quarantine"


def test_T_A1_U_04_near_duplicate(tmp_path):
    text = (BATCH_B / "hostel_rules_03.md").read_text(encoding="utf-8")
    body = parse_front_matter_03(text)[1]
    tweaked = body.replace("must", "shall", 1).replace("Hostel Office", "Hostel Bureau", 1)
    vs = {v.doc.doc_id: v for v in run([mk(body, doc_id="a"), mk(tweaked, doc_id="b")], tmp_path)}
    assert codes(vs["b"])["uniqueness"] == "DUPLICATE_NEAR"
    assert vs["b"].checks[3].value >= 0.95


def test_T_A1_U_05_unrelated_docs_pass(tmp_path):
    a = parse_front_matter_03((BATCH_B / "hostel_rules_03.md").read_text(encoding="utf-8"))[1]
    b = parse_front_matter_03((BATCH_B / "library_policy_03.md").read_text(encoding="utf-8"))[1]
    vs = run([mk(a, doc_id="a"), mk(b, doc_id="b")], tmp_path)
    assert all(v.decision == "accept" for v in vs)
    assert vs[1].checks[3].value < 0.95


def test_T_A1_U_06_all_four_checks_reported_even_after_failure(tmp_path):
    v = run([mk("", title=None, pages=[""])], tmp_path)[0]
    assert [c.check for c in v.checks] == ["quality", "completeness", "recency", "uniqueness"]


# ---- extraction / staging
def test_extract_markdown_front_matter_and_form_feed_pages(tmp_path):
    p = tmp_path / "x.md"
    p.write_text("---\ndoc_id: x\ntitle: X\nversion: 1\npage_count: 2\n---\n\nPage one.\n\f\nPage two.\n",
                 encoding="utf-8")
    ex = extract_doc_03(p)
    assert ex.meta.doc_id == "x" and ex.meta.page_count == 2 and ex.pages == ["Page one.", "Page two."]


def test_extract_falls_back_to_yaml_metadata(tmp_path):
    p = tmp_path / "plain.md"
    p.write_text("body only", encoding="utf-8")
    ex = extract_doc_03(p, None, {"doc_id": "from-yaml", "title": "Y", "version": "3"})
    assert (ex.meta.doc_id, ex.meta.title, ex.meta.version) == ("from-yaml", "Y", "3")


def test_collect_docs_stages_copies_and_leaves_repo_untouched(tmp_path):
    before = {p.name: p.read_bytes() for p in BATCH_B.iterdir()}
    docs = collect_docs_03(BATCH_B, tmp_path / "lake_root")
    staged = tmp_path / "lake_root" / "lake" / "batch_b_03"
    assert all(d.meta.path.parent == staged for d in docs) and (staged / "exam_conduct_03.md").exists()
    assert {p.name: p.read_bytes() for p in BATCH_B.iterdir()} == before


# ---- quarantine mover + report
def _verdicts_for_batch_b(tmp_path, state=None):
    c = cfg(tmp_path)
    docs = collect_docs_03(BATCH_B, c.ragops_root)
    return c, verify_documents(docs, state or ManifestState03(), dummy_embed_03, c)


def test_T_A1_QR_01_quarantined_file_moved_original_absent(tmp_path):
    c, vs = _verdicts_for_batch_b(tmp_path)
    ts = utc_ts_03()
    res = apply_verdicts_03(vs, c, ts=ts, corpus="b", embedding="dummy-256")
    lake = Path(c.ragops_root) / "lake" / "batch_b_03"
    assert not (lake / "exam_conduct_copy_03.md").exists()
    assert (Path(c.ragops_root) / "quarantine" / ts / "exam_conduct_copy_03.md").exists()
    assert (lake / "exam_conduct_03.md").exists() and len(res["quarantined_paths"]) == 7


def test_T_A1_QR_02_sidecar_reason_json(tmp_path):
    c, vs = _verdicts_for_batch_b(tmp_path)
    ts = utc_ts_03()
    apply_verdicts_03(vs, c, ts=ts, corpus="b", embedding="dummy-256")
    side = Path(c.ragops_root) / "quarantine" / ts / "exam_conduct_copy_03.md.reason_03.json"
    data = json.loads(side.read_text(encoding="utf-8"))
    assert data["codes"] == ["DUPLICATE_EXACT"] and len(data["sha256"]) == 64


def test_T_A1_QR_03_never_indexed(tmp_path):
    from indexer.run_ingest_03 import run_ingest
    from pipeline.memory_collection_03 import MemoryClient03
    c = cfg(tmp_path)
    client = MemoryClient03()
    summary = run_ingest(c, [str(BATCH_B)], dummy=True, client=client,
                         bump_fn=lambda: None, results_dir=str(tmp_path / "res"))
    got = client.get_collection(c.collection).get(include=["metadatas"])
    quarantined = {"exam-conduct-copy", "library-policy-mirror", "hostel-rules-reworded",
                   "attendance-notice", "corrupt-scan", "no-metadata-circular", "empty-stub"}
    assert summary["quarantined"] == 7 and got["ids"]
    assert not {m["document_id"] for m in got["metadatas"]} & quarantined
    assert not any("copy" in m["source"] or "mirror" in m["source"] for m in got["metadatas"])


def test_T_A1_REP_01_json_parses_and_totals_sum(tmp_path):
    c, vs = _verdicts_for_batch_b(tmp_path)
    res = apply_verdicts_03(vs, c, ts=utc_ts_03(), corpus="b", embedding="dummy-256")
    rep = json.loads(Path(res["paths"]["json"]).read_text(encoding="utf-8"))
    t = rep["totals"]
    assert t["accepted"] + t["quarantined"] == t["documents"] == 14
    assert sum(rep["by_reason"].values()) >= t["quarantined"]
    assert all(len(d["checks"]) == 4 for d in rep["documents"])


def test_T_A1_REP_02_markdown_has_one_row_per_doc(tmp_path):
    c, vs = _verdicts_for_batch_b(tmp_path)
    res = apply_verdicts_03(vs, c, ts=utc_ts_03(), corpus="b", embedding="dummy-256")
    md = Path(res["paths"]["md"]).read_text(encoding="utf-8")
    rows = [ln for ln in md.splitlines() if ln.startswith("| ") and "_03." in ln]
    assert len(rows) == 14


def test_T_A1_REP_03_pair_shares_timestamp(tmp_path):
    c, vs = _verdicts_for_batch_b(tmp_path)
    ts = utc_ts_03()
    res = apply_verdicts_03(vs, c, ts=ts, corpus="b", embedding="dummy-256")
    assert Path(res["paths"]["json"]).stem == Path(res["paths"]["md"]).stem == f"verification_report_03_{ts}"


def test_no_move_leaves_files_in_place(tmp_path):
    c = cfg(tmp_path)
    docs = collect_docs_03(BATCH_B, None)
    vs = verify_documents(docs, ManifestState03(), dummy_embed_03, c)
    res = apply_verdicts_03(vs, c, ts=utc_ts_03(), corpus="b", embedding="x", move=False)
    assert res["quarantined_paths"] == [] and (BATCH_B / "exam_conduct_copy_03.md").exists()


@pytest.mark.parametrize("name", ["hostel_rules_03.md", "student_notice_injected_03.md"])
def test_clean_controls_not_flagged(tmp_path, name):
    _, vs = _verdicts_for_batch_b(tmp_path)
    assert {v.doc.path.name: v.decision for v in vs}[name] == "accept"
