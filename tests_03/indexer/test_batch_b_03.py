"""Batch B adversarial corpus tests (harness_03/05 section 4)."""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

from pipeline.config import IndexerSettings
from pipeline.config_03 import load_settings_03
from pipeline.hashing_03 import dummy_embed_03
from pipeline.state_03 import ManifestState03
from pipeline.verify_03 import collect_docs_03, parse_front_matter_03, verify_documents

REPO = Path(__file__).resolve().parents[2]
BATCH_B = REPO / "corpus" / "batch_b_03"
EXPECTED = json.loads((BATCH_B / "EXPECTED_03.json").read_text(encoding="utf-8"))
FILES = sorted(k for k in EXPECTED if not k.startswith("_"))


def _cfg(tmp_path):
    base = IndexerSettings(embed_model="dummy-256", chroma_host="x", chroma_port=1, collection="c",
                           corpus_dir="", chunk_size=400, chunk_overlap=50, ollama_url="")
    return load_settings_03(base, ragops_root=str(tmp_path))


def _verify(tmp_path, with_state: bool):
    state = ManifestState03()
    if with_state:
        state.documents["academic-rules-handbook"] = {
            "active_version": "2026-06", "date": None, "content_hash": "0" * 64,
            "doc_vec": None, "chunks": {}}
    docs = collect_docs_03(BATCH_B, None)
    return {v.doc.path.name: v for v in verify_documents(docs, state, dummy_embed_03, _cfg(tmp_path))}


def _check_mode(tmp_path, with_state: bool):
    got = _verify(tmp_path, with_state)
    assert sorted(got) == FILES and len(FILES) == 14
    for name in FILES:
        exp = EXPECTED[name]
        if with_state and "with_batch_a_state" in exp:
            exp = exp["with_batch_a_state"]
        assert got[name].decision == exp["decision"], name
        assert sorted(got[name].codes()) == sorted(exp["codes"]), name
    return got


def test_T_BB_01_standalone_matches_expected(tmp_path):
    got = _check_mode(tmp_path, with_state=False)
    assert sum(v.decision == "accept" for v in got.values()) == EXPECTED["_totals"]["standalone"]["accepted"] == 7
    assert sum(v.decision == "quarantine" for v in got.values()) == 7


def test_T_BB_01_with_batch_a_state_matches_expected(tmp_path):
    got = _check_mode(tmp_path, with_state=True)
    hb = got["academic_rules_handbook_v2026-11_03.md"]
    assert hb.decision == "supersede" and hb.supersedes == "2026-06"
    assert sum(v.decision in {"accept", "supersede"} for v in got.values()) == 7


def test_T_BB_02_names_counts_and_categories():
    names = [p.name for p in BATCH_B.iterdir()]
    assert all(re.search(r"_03\.[A-Za-z0-9]+$", n) for n in names)
    assert len(FILES) >= 10
    codes = [c for n in FILES for c in EXPECTED[n]["codes"]]
    assert codes.count("DUPLICATE_EXACT") >= 2 and codes.count("DUPLICATE_NEAR") >= 1
    assert codes.count("TRUNCATED") + codes.count("GARBLED_NON_ASCII") >= 2
    assert codes.count("MISSING_METADATA") >= 1
    assert any("with_batch_a_state" in EXPECTED[n] for n in FILES)


def test_T_BB_03_injected_notice_is_accepted_by_verification(tmp_path):
    v = _verify(tmp_path, False)["student_notice_injected_03.md"]
    assert v.decision == "accept"
    text = (BATCH_B / "student_notice_injected_03.md").read_text(encoding="utf-8")
    assert "ignore all previous instructions" in text


def test_clean_documents_meet_content_requirements():
    for name in ("hostel_rules_03.md", "library_policy_03.md", "transport_policy_03.md",
                 "scholarship_rules_03.md", "exam_conduct_03.md"):
        body = parse_front_matter_03((BATCH_B / name).read_text(encoding="utf-8"))[1]
        assert 350 <= len(body.split()) <= 900, name
        assert 3 <= len(re.findall(r"^## ", body, re.M)) <= 6, name
        assert len(re.findall(r"\d", body)) >= 4, name
        assert body.count("\f") == 1, name


def test_newer_handbook_changes_the_observable_rule():
    body = (BATCH_B / "academic_rules_handbook_v2026-11_03.md").read_text(encoding="utf-8")
    assert "10% of the total attendance" in body and "version: 2026-11" in body
    assert "date: 2026-11-01" in body and "doc_id: academic-rules-handbook" in body
    assert len(body.split()) >= 350


def test_generator_is_idempotent_and_manifest_hashes_are_computed():
    def snap():
        return {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in BATCH_B.iterdir()}
    before = snap()
    subprocess.run([sys.executable, str(REPO / "scripts" / "gen_batch_b_03.py")], check=True,
                   capture_output=True, cwd=REPO)
    assert snap() == before
    manifest = (REPO / "corpus" / "MANIFEST_batch_b_03.md").read_text(encoding="utf-8")
    for name, digest in before.items():
        if name != "EXPECTED_03.json":
            assert digest in manifest, name
    assert "synthetic test documents" in manifest


def test_generator_writes_lf_line_endings_on_every_platform():
    """Regression: on Windows write_text produced CRLF, so a fresh LF checkout changed under
    regeneration and the idempotence test failed there."""
    subprocess.run([sys.executable, str(REPO / "scripts" / "gen_batch_b_03.py")], check=True,
                   capture_output=True, cwd=REPO)
    outputs = [*BATCH_B.iterdir(), REPO / "corpus" / "MANIFEST_batch_b_03.md",
               *(REPO / "corpus" / "noise_03").glob("*")]
    assert [p.name for p in outputs if p.is_file() and b"\r\n" in p.read_bytes()] == []
