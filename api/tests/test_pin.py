"""T-PIN-01..04 - the embedding pin: the API's half of section 4.4."""
from __future__ import annotations

from app.services.pin import check_pin


def test_matching_model_is_ok() -> None:                               # T-PIN-01
    status = check_pin({"embed_model": "nomic-embed-text", "dimension": 768},
                       "nomic-embed-text")
    assert status.ok is True
    assert status.conflict is None


def test_mismatched_model_is_not_ok_and_names_both() -> None:          # T-PIN-02
    status = check_pin({"embed_model": "dummy-768", "dimension": 768},
                       "nomic-embed-text")
    assert status.ok is False
    assert "dummy-768" in status.conflict
    assert "nomic-embed-text" in status.conflict
    assert "re-index or revert" in status.conflict


def test_missing_metadata_is_not_ok() -> None:                          # T-PIN-03
    status = check_pin({}, "nomic-embed-text")
    assert status.ok is False
    assert "no embed_model metadata" in status.conflict


def test_dimension_is_carried_through() -> None:                       # T-PIN-04
    status = check_pin({"embed_model": "nomic-embed-text", "dimension": 768},
                       "nomic-embed-text")
    assert status.collection_dimension == 768
