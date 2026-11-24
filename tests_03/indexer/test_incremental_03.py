"""Part A2 tests: incremental ingest, versioning, delete/orphans, rollback (harness_03/04 section 8)."""

from __future__ import annotations

import hashlib
import json
import random
import string
from pathlib import Path

import pytest

from indexer import delete_doc_03, rollback_03, run_ingest_03
from indexer.pipeline.config import IndexerSettings
from indexer.pipeline.config_03 import embed_version_03, load_settings_03
from indexer.pipeline.hashing_03 import dummy_embed_03
from indexer.pipeline.incremental_store_03 import PinMismatch03, reconcile
from indexer.pipeline.memory_collection_03 import MemoryClient03
from indexer.pipeline.state_03 import ManifestCorrupt03, ManifestState03, load_manifest_03, manifest_path_03
from indexer.pipeline.verify_03 import compare_versions_03


def make_cfg(root: Path, **kw):
    base = IndexerSettings(embed_model="dummy-256", chroma_host="x", chroma_port=1,
                           collection="coll_test_03", corpus_dir="", chunk_size=400,
                           chunk_overlap=50, ollama_url="")
    return load_settings_03(base, ragops_root=str(root / "root"), results_dir=str(root / "res"), **kw)


def words(tag: str, n: int = 70) -> str:
    rng = random.Random(tag)
    toks = ["".join(rng.choice(string.ascii_lowercase) for _ in range(rng.randint(4, 9)))
            for _ in range(n)]
    return " ".join((w.capitalize() if i % 10 == 0 else w) + ("." if i % 10 == 9 else "")
                    for i, w in enumerate(toks))


def write_doc(dirp: Path, fname: str, doc_id: str, version: str = "2026-06", sections: int = 3,
              revs: dict[int, int] | None = None, date: str | None = None) -> Path:
    dirp.mkdir(parents=True, exist_ok=True)
    date = date or f"{version}-01"
    body = "\n\n".join(f"## 1.{i} Topic {string.ascii_uppercase[i]}\n\n"
                       f"{words(f'{doc_id}-{i}-{(revs or {}).get(i, 0)}')}" for i in range(sections))
    p = dirp / fname
    p.write_text(f"---\ndoc_id: {doc_id}\ntitle: Title {doc_id}\nsource: {fname}\ndate: {date}\n"
                 f"version: {version}\npage_count: 1\n---\n\n{body}\n", encoding="utf-8")
    return p


class Env:
    def __init__(self, tmp_path: Path, **kw):
        self.tmp = tmp_path
        self.cfg = make_cfg(tmp_path, **kw)
        self.client = MemoryClient03()
        self.embed_calls: list[list[str]] = []
        self.bumps: list[int] = []

    def embed(self, texts):
        self.embed_calls.append(list(texts))
        return dummy_embed_03(texts)

    def bump(self):
        self.bumps.append(1)
        return len(self.bumps)

    def ingest(self, *dirs, **kw):
        return run_ingest_03.run_ingest(self.cfg, [str(d) for d in dirs], dummy=True,
                                        client=self.client, embed_fn=self.embed, bump_fn=self.bump,
                                        results_dir=str(self.tmp / "res"), **kw)

    @property
    def col(self):
        return self.client.get_collection(self.cfg.collection)

    @property
    def root(self) -> Path:
        return Path(self.cfg.ragops_root)

    def state(self) -> ManifestState03:
        return load_manifest_03(manifest_path_03(self.root))

    def ids_of(self, doc_id: str) -> list[str]:
        return sorted(self.col.get(where={"document_id": doc_id}, include=["metadatas"])["ids"])


@pytest.fixture
def env(tmp_path):
    return Env(tmp_path)


@pytest.fixture
def corpus(tmp_path):
    d = tmp_path / "corpus_a"
    write_doc(d, "alpha.md", "alpha")
    write_doc(d, "beta.md", "beta")
    return d


# ---------------------------------------------------------------- state
def test_T_A2_ST_01_round_trip_is_atomic(tmp_path):
    s = ManifestState03(path=manifest_path_03(tmp_path))
    s.documents["a"] = {"active_version": "1", "chunks": {"a:1:0000": "h"}}
    s.save()
    assert not list(manifest_path_03(tmp_path).parent.glob("*.tmp_03"))
    assert load_manifest_03(manifest_path_03(tmp_path)).documents == s.documents


def test_T_A2_ST_02_missing_file_is_empty_state(tmp_path):
    s = load_manifest_03(manifest_path_03(tmp_path))
    assert s.documents == {} and s.collection_version == 0


def test_T_A2_ST_03_corrupt_json_raises_never_resets(tmp_path):
    p = manifest_path_03(tmp_path)
    p.parent.mkdir(parents=True)
    p.write_text("{not json", encoding="utf-8")
    with pytest.raises(ManifestCorrupt03):
        load_manifest_03(p)
    assert p.read_text(encoding="utf-8") == "{not json"


# ---------------------------------------------------------------- plan
def test_T_A2_PLAN_01_new_docs_all_added(env, corpus):
    out = env.ingest(corpus, dry_run=True)
    assert out["embedded_chunks"] == 6 and out["kept_chunks"] == 0 and out["quarantined"] == 0


def test_T_A2_PLAN_02_unchanged_is_empty_plan(env, corpus):
    env.ingest(corpus)
    out = env.ingest(corpus, dry_run=True)
    assert (out["embedded_chunks"], out["deleted_chunks"], out["deactivated_chunks"]) == (0, 0, 0)
    assert out["unchanged_docs"] == 2 and out["kept_chunks"] == 6


def test_T_A2_PLAN_03_one_edited_paragraph_touches_only_that_chunk(env, corpus):
    env.ingest(corpus)
    beta_before = env.ids_of("beta")
    write_doc(corpus, "alpha.md", "alpha", revs={1: 1})
    out = env.ingest(corpus, dry_run=True)
    assert (out["embedded_chunks"], out["deleted_chunks"], out["kept_chunks"]) == (1, 1, 5)
    env.ingest(corpus)
    assert env.ids_of("beta") == beta_before and len(env.ids_of("alpha")) == 3


def test_T_A2_PLAN_04_embed_version_change_reembeds_everything(env, corpus):
    env.ingest(corpus)
    env.cfg = make_cfg(env.tmp, embed_version_suffix="-v2")
    out = env.ingest(corpus, dry_run=True)
    assert out["embedded_chunks"] == 6 and out["unchanged_docs"] == 0


def test_T_A2_PLAN_05_newer_version_deactivates_old_and_adds_new(env, corpus, tmp_path):
    env.ingest(corpus)
    new = tmp_path / "corpus_new"
    write_doc(new, "alpha_v2.md", "alpha", version="2026-11", revs={0: 7})
    out = env.ingest(new, dry_run=True)
    assert (out["embedded_chunks"], out["deactivated_chunks"], out["deleted_chunks"]) == (3, 3, 0)


def test_T_A2_PLAN_06_absent_doc_without_prune_is_not_deleted(env, corpus, tmp_path):
    env.ingest(corpus)
    only_alpha = tmp_path / "only_alpha"
    write_doc(only_alpha, "alpha.md", "alpha")
    assert env.ingest(only_alpha, dry_run=True)["deleted_chunks"] == 0
    assert env.ingest(only_alpha, dry_run=True, prune=True)["deleted_chunks"] == 3
    env.ingest(only_alpha)
    assert len(env.ids_of("beta")) == 3


def test_dry_run_writes_nothing(env, corpus):
    env.ingest(corpus, dry_run=True)
    assert not env.root.exists() or not list(env.root.rglob("*.json"))
    with pytest.raises(ValueError):
        env.client.get_collection(env.cfg.collection)   # no collection was created


# ---------------------------------------------------------------- apply
def test_T_A2_APPLY_01_add_writes_metadata_superset(env, corpus):
    env.ingest(corpus)
    got = env.col.get(ids=["alpha:2026-06:0000"], include=["metadatas"])["metadatas"][0]
    for k in ("source", "section", "page", "doc_version", "superseded", "document_id",
              "document_version", "content_hash", "chunk_hash", "chunk_index", "is_active",
              "ingested_at"):
        assert k in got, k
    assert got["is_active"] is True and got["superseded"] is False
    assert got["document_version"] == got["doc_version"] == "2026-06"


def test_T_A2_APPLY_02_replace_touches_only_own_ids(env, corpus):
    env.ingest(corpus)
    env.col.calls.clear()
    write_doc(corpus, "alpha.md", "alpha", revs={2: 3})
    env.ingest(corpus)
    touched = {i for op, kw in env.col.calls for i in (kw.get("ids") or [])}
    assert touched and all(i.startswith("alpha:") for i in touched)


def test_T_A2_APPLY_03_supersede_flags_are_complementary(env, corpus, tmp_path):
    env.ingest(corpus)
    new = tmp_path / "n"
    write_doc(new, "alpha_v2.md", "alpha", version="2026-11", revs={0: 5})
    env.ingest(new)
    got = env.col.get(where={"document_id": "alpha"}, include=["metadatas"])
    for m in got["metadatas"]:
        assert m["is_active"] is (not m["superseded"])
    by_ver = {m["document_version"]: m["is_active"] for m in got["metadatas"]}
    assert by_ver == {"2026-06": False, "2026-11": True}


def test_T_A2_APPLY_04_modify_omits_hnsw_and_keeps_pin(env, corpus):
    env.ingest(corpus)
    mods = [kw["metadata"] for op, kw in env.col.calls if op == "modify"]
    assert mods and all("hnsw:space" not in m for m in mods)
    meta = env.col.metadata
    assert meta["embed_model"] == "dummy-256" and meta["dimension"] == 256
    assert meta["hnsw:space"] == "cosine" and meta["embed_version"] == "dummy-256@256"
    assert meta["chunk_size"] == 400 and meta["chunk_count"] == 6


def test_T_A2_APPLY_05_every_delete_carries_ids(env, corpus, tmp_path):
    env.ingest(corpus)
    write_doc(corpus, "alpha.md", "alpha", revs={1: 9})
    env.ingest(corpus)
    only = tmp_path / "only"
    write_doc(only, "alpha.md", "alpha", revs={1: 9})
    env.ingest(only, prune=True)
    deletes = [kw for op, kw in env.col.calls if op == "delete"]
    assert deletes and all(kw["ids"] and kw["where"] is None for kw in deletes)


def test_T_A2_APPLY_06_collection_version_increments_only_on_change(env, corpus):
    env.ingest(corpus)
    v1 = env.state().collection_version
    env.ingest(corpus)
    assert env.state().collection_version == v1 == 1
    write_doc(corpus, "beta.md", "beta", revs={0: 4})
    env.ingest(corpus)
    assert env.state().collection_version == 2 and env.col.metadata["collection_version"] == 2


def test_pin_mismatch_is_refused(env, corpus):
    env.ingest(corpus)
    env.cfg = make_cfg(env.tmp, embed_model="some-other-model")
    write_doc(corpus, "beta.md", "beta", revs={0: 6})
    with pytest.raises(PinMismatch03):
        env.ingest(corpus)


def test_refuses_empty_index(env, tmp_path):
    empty = tmp_path / "junk"
    empty.mkdir()
    (empty / "stub.md").write_text("---\ndoc_id: s\ntitle: S\nversion: 1\npage_count: 1\n---\n",
                                   encoding="utf-8")
    with pytest.raises(ValueError, match="refusing empty index"):
        env.ingest(empty)


# ---------------------------------------------------------------- versioning
def test_T_A2_VER_01_and_03_archive_has_source_and_meta_with_same_hash(env, corpus, tmp_path):
    original = (env.tmp / "corpus_a" / "alpha.md").read_bytes()
    env.ingest(corpus)
    new = tmp_path / "n"
    write_doc(new, "alpha_v2.md", "alpha", version="2026-11", revs={0: 5})
    env.ingest(new)
    arch = env.root / "archive" / "alpha" / "2026-06"
    assert (arch / "alpha.md").exists() and (arch / "meta_03.json").exists()
    meta = json.loads((arch / "meta_03.json").read_text(encoding="utf-8"))
    assert meta["doc_id"] == "alpha" and len(meta["chunk_ids"]) == 3
    assert hashlib.sha256((arch / "alpha.md").read_bytes()).hexdigest() == hashlib.sha256(original).hexdigest()


def test_T_A2_VER_02_lake_copy_removed_only_after_archive_copy(env, corpus, tmp_path):
    env.ingest(corpus)
    lake_alpha = env.root / "lake" / "corpus_a" / "alpha.md"
    assert lake_alpha.exists()
    env.ingest(corpus)                       # unchanged run: lake copy stays
    assert lake_alpha.exists()
    new = tmp_path / "n"
    write_doc(new, "alpha_v2.md", "alpha", version="2026-11", revs={0: 5})
    env.ingest(new)
    assert not lake_alpha.exists() and (env.root / "archive/alpha/2026-06/alpha.md").exists()


def test_T_A2_VER_04_default_filter_excludes_superseded(env, corpus, tmp_path):
    env.ingest(corpus)
    new = tmp_path / "n"
    write_doc(new, "alpha_v2.md", "alpha", version="2026-11", revs={0: 5})
    env.ingest(new)
    active = env.col.get(where={"is_active": True}, include=["metadatas"])
    assert not any(i.startswith("alpha:2026-06") for i in active["ids"])
    q = env.col.query(dummy_embed_03(["anything"]), n_results=50, where={"superseded": False})
    assert not any(i.startswith("alpha:2026-06") for i in q["ids"][0])


def test_T_A2_VER_05_version_ordering():
    assert compare_versions_03("2026-11", "2026-06") == 1 and compare_versions_03("2023-08", "2026") == -1


# ---------------------------------------------------------------- idempotency
def test_T_A2_IDEM_01_second_run_embeds_nothing(env, corpus):
    first = env.ingest(corpus)
    assert first["embedded_chunks"] == 6
    calls, bumps, version = len(env.embed_calls), len(env.bumps), env.state().collection_version
    second = env.ingest(corpus)
    assert second["embedded_chunks"] == 0
    assert all(c == [] for c in env.embed_calls[calls:]) and len(env.embed_calls) == calls
    assert len(env.bumps) == bumps and env.state().collection_version == version


# ---------------------------------------------------------------- delete / orphans
def test_T_A2_ORPH_01_delete_leaves_zero_orphans(env, corpus, tmp_path):
    env.ingest(corpus)
    before = delete_doc_03.orphan_report(env.col, env.state())
    assert before["chunks_by_document"] == {"alpha": 3, "beta": 3} and before["orphans"] == 0
    state = env.state()
    res = delete_doc_03.delete_doc(env.col, state, "alpha", env.root, "test", env.bump)
    after = delete_doc_03.orphan_report(env.col, env.state())
    assert res["deleted_chunks"] == 3 and after["chunks_by_document"] == {"beta": 3}
    assert after["orphans"] == 0 and (env.root / "archive/alpha/2026-06/alpha.md").exists()


def test_T_A2_ORPH_02_seeded_orphan_is_reported(env, corpus):
    env.ingest(corpus)
    env.col.add(ids=["ghost:1:0000"], documents=["x"], embeddings=[[0.0] * 256],
                metadatas=[{"document_id": "ghost"}])
    rep = delete_doc_03.orphan_report(env.col, env.state())
    assert rep["orphans"] == 1 and rep["orphan_ids"] == ["ghost:1:0000"]


def test_T_A2_ORPH_03_cli_exit_codes(env, corpus, monkeypatch):
    monkeypatch.setenv("RAGOPS_ROOT", str(env.root))
    monkeypatch.setenv("RAGOPS_COLLECTION", env.cfg.collection)
    run_ingest_03.main(["--corpus", str(corpus), "--dummy-embed", "--collection-double",
                        "--results-dir", str(env.tmp / "res")])
    assert delete_doc_03.main(["--orphan-report", "--collection-double"]) == 0
    assert delete_doc_03.main(["--doc-id", "nope", "--collection-double"]) == 3
    assert delete_doc_03.main(["--doc-id", "alpha", "--collection-double"]) == 0
    assert delete_doc_03.main(["--orphan-report", "--collection-double"]) == 0


def test_reconcile_deletes_orphans_and_invalidates_missing(env, corpus):
    env.ingest(corpus)
    env.col.add(ids=["ghost:1:0000"], documents=["x"], embeddings=[[0.0] * 256],
                metadatas=[{"document_id": "ghost"}])
    env.col.delete(ids=["beta:2026-06:0001"])
    state = env.state()
    drift = reconcile(env.col, state)
    assert drift["orphan_ids"] == ["ghost:1:0000"] and drift["missing_from_chroma"] == ["beta:2026-06:0001"]
    assert "ghost:1:0000" not in env.col.get()["ids"] and state.doc("beta")["content_hash"] == ""
    state.save()
    assert env.ingest(corpus)["embedded_chunks"] == 1    # the missing chunk is re-added


# ---------------------------------------------------------------- rollback
def _superseded(env, corpus, tmp_path):
    env.ingest(corpus)
    new = tmp_path / "n"
    write_doc(new, "alpha_v2.md", "alpha", version="2026-11", revs={0: 5})
    env.ingest(new)


def test_T_A2_RB_01_rollback_reactivates_and_deactivates(env, corpus, tmp_path):
    _superseded(env, corpus, tmp_path)
    code, res = rollback_03.rollback(env.col, env.state(), "alpha", "2026-06", env.cfg, env.root,
                                     env.embed, env.bump)
    assert code == 0 and res["reactivated_chunks"] == 3 and res["reembedded_chunks"] == 0
    flags = {m["document_version"]: m["is_active"]
             for m in env.col.get(where={"document_id": "alpha"}, include=["metadatas"])["metadatas"]}
    assert flags == {"2026-06": True, "2026-11": False}
    st = env.state().doc("alpha")
    assert st["active_version"] == "2026-06" and "2026-11" in st["versions"]
    code2, _ = rollback_03.rollback(env.col, env.state(), "alpha", "2026-11", env.cfg, env.root,
                                    env.embed, env.bump)
    assert code2 == 0
    assert env.state().doc("alpha")["active_version"] == "2026-11"


def test_T_A2_RB_02_unknown_version_exits_3(env, corpus):
    env.ingest(corpus)
    code, res = rollback_03.rollback(env.col, env.state(), "alpha", "1999", env.cfg, env.root,
                                     env.embed)
    assert code == 3 and res["error"] == "UNKNOWN_VERSION"
    assert rollback_03.rollback(env.col, env.state(), "zzz", "1", env.cfg, env.root, env.embed)[0] == 3


def test_T_A2_RB_03_rollback_after_prune_reembeds_from_archive(env, corpus, tmp_path):
    _superseded(env, corpus, tmp_path)
    env.col.delete(ids=env.ids_of("alpha") and [i for i in env.ids_of("alpha") if "2026-06" in i])
    calls = len(env.embed_calls)
    code, res = rollback_03.rollback(env.col, env.state(), "alpha", "2026-06", env.cfg, env.root,
                                     env.embed, env.bump)
    assert code == 0 and res["reembedded_chunks"] == 3 and len(env.embed_calls) == calls + 1
    got = env.col.get(where={"document_id": "alpha", "document_version": "2026-06"},
                      include=["metadatas"])
    assert len(got["ids"]) == 3 and all(m["is_active"] for m in got["metadatas"])


def test_T_A2_RB_04_rollback_is_idempotent(env, corpus, tmp_path):
    _superseded(env, corpus, tmp_path)
    rollback_03.rollback(env.col, env.state(), "alpha", "2026-06", env.cfg, env.root, env.embed)
    version = env.state().collection_version
    code, res = rollback_03.rollback(env.col, env.state(), "alpha", "2026-06", env.cfg, env.root,
                                     env.embed)
    assert code == 0 and res["status"] == "already_active" and env.state().collection_version == version


def test_rollback_changes_the_retrieved_text_then_reingest_restores_new(env, corpus, tmp_path):
    _superseded(env, corpus, tmp_path)
    q = dummy_embed_03([words("alpha-0-0")])    # text of the OLD version's first section
    top = lambda: env.col.query(q, n_results=1, where={"is_active": True})["ids"][0][0]  # noqa: E731
    assert top() != "alpha:2026-06:0000"
    rollback_03.rollback(env.col, env.state(), "alpha", "2026-06", env.cfg, env.root, env.embed)
    assert top() == "alpha:2026-06:0000"
    new = tmp_path / "n"                           # re-ingest of the newer file supersedes again
    out = env.ingest(new)
    assert out["deactivated_chunks"] == 3 and top() != "alpha:2026-06:0000"


# ---------------------------------------------------------------- CLI / config
def test_T_A2_CLI_01_optional_corpus_missing_or_empty_is_skipped(env, corpus, tmp_path):
    empty = tmp_path / "empty_dir"
    empty.mkdir()
    out = env.ingest(corpus, optional=[str(tmp_path / "nope"), str(empty)]) if False else \
        run_ingest_03.run_ingest(env.cfg, [str(corpus)], [str(tmp_path / "nope"), str(empty)],
                                 dummy=True, client=env.client, embed_fn=env.embed, bump_fn=env.bump,
                                 results_dir=str(env.tmp / "res"))
    assert out["embedded_chunks"] == 6


def test_missing_required_corpus_exits_2(env, tmp_path, monkeypatch):
    monkeypatch.setenv("RAGOPS_ROOT", str(env.root))
    assert run_ingest_03.main(["--corpus", str(tmp_path / "missing"), "--dummy-embed",
                               "--collection-double"]) == 2


def test_T_A2_EV_01_embed_version_suffix_touches_only_embed_version(tmp_path, monkeypatch):
    monkeypatch.setenv("EMBED_VERSION_SUFFIX_03", "-cand")
    cfg = make_cfg(tmp_path)
    assert embed_version_03(cfg, 256) == "dummy-256@256-cand"
    assert cfg.embed_model == "dummy-256"


def test_T_A2_LOCK_01_second_ingest_exits_75(env, corpus, monkeypatch):
    monkeypatch.setenv("RAGOPS_ROOT", str(env.root))
    held = run_ingest_03.acquire_lock_03(env.root)
    assert held is not None
    try:
        assert run_ingest_03.main(["--corpus", str(corpus), "--dummy-embed", "--collection-double"]) == 75
    finally:
        run_ingest_03.release_lock_03(held)
    assert run_ingest_03.main(["--corpus", str(corpus), "--dummy-embed", "--collection-double",
                               "--results-dir", str(env.tmp / "res")]) == 0


def test_chunk_size_flags_are_applied(env, corpus):
    out = run_ingest_03.run_ingest(make_cfg(env.tmp, chunk_size=30, chunk_overlap=5), [str(corpus)],
                                   dummy=True, client=env.client, embed_fn=env.embed,
                                   bump_fn=env.bump, results_dir=str(env.tmp / "res"))
    assert out["embedded_chunks"] > 6 and env.col.metadata["chunk_size"] == 30


# ---------------------------------------------------------------- memory double
def test_memory_collection_rejects_duplicate_ids_and_empty_deletes():
    c = MemoryClient03().get_or_create_collection("c", {"hnsw:space": "cosine"})
    c.add(ids=["a"], documents=["x"], embeddings=[[1.0, 0.0]], metadatas=[{"k": 1}])
    with pytest.raises(ValueError):
        c.add(ids=["a"], documents=["x"], embeddings=[[1.0, 0.0]], metadatas=[{"k": 1}])
    with pytest.raises(ValueError):
        c.delete(ids=[])
    with pytest.raises(ValueError):
        c.modify(metadata={"hnsw:space": "l2"})


def test_memory_collection_where_filters_and_file_persistence(tmp_path):
    path = tmp_path / "m.json"
    client = MemoryClient03(path)
    c = client.get_or_create_collection("c", {"hnsw:space": "cosine"})
    c.add(ids=["a", "b", "c"], documents=["1", "2", "3"], embeddings=[[1.0, 0.0]] * 3,
          metadatas=[{"d": "x", "on": True}, {"d": "x", "on": False}, {"d": "y", "on": True}])
    assert c.get(where={"d": "x"})["ids"] == ["a", "b"]
    assert c.get(where={"$and": [{"d": "x"}, {"on": True}]})["ids"] == ["a"]
    assert c.get(where={"d": {"$in": ["y"]}})["ids"] == ["c"]
    reopened = MemoryClient03(path).get_collection("c")
    assert reopened.count() == 3 and reopened.metadata["hnsw:space"] == "cosine"


def test_two_versions_of_one_doc_in_one_run_only_newest_is_planned(env, corpus, tmp_path):
    env.ingest(corpus)
    new = tmp_path / "n"
    write_doc(new, "alpha_v2.md", "alpha", version="2026-11", revs={0: 5})
    out = env.ingest(corpus, new)          # old alpha (unchanged) and new alpha together
    assert (out["embedded_chunks"], out["deactivated_chunks"], out["kept_chunks"]) == (3, 3, 3)


def test_two_versions_in_one_run_on_empty_state_index_the_newer_only(env, corpus, tmp_path):
    new = tmp_path / "n"
    write_doc(new, "alpha_v2.md", "alpha", version="2026-11", revs={0: 5})
    env.ingest(corpus, new)
    assert {m["document_version"] for m in
            env.col.get(where={"document_id": "alpha"}, include=["metadatas"])["metadatas"]} == {"2026-11"}
