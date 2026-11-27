import pytest
import yaml

from scripts.make_candidate_config_03 import parse_env, render


def test_fail_preset_values():
    env = parse_env(open("config/candidate_fail_03.env", encoding="utf-8").read())
    assert env == {"CHROMA_COLLECTION": "rahbar_ragops_03", "TOP_K": "1"}


def test_pass_preset_values():
    env = parse_env(open("config/candidate_pass_03.env", encoding="utf-8").read())
    assert env == {"CHROMA_COLLECTION": "rahbar_ragops_03", "RERANK_ENABLED": "true",
                   "RERANK_POOL": "8", "TOP_K": "5"}


def test_rendered_configmap_is_valid_yaml_in_namespace_rahbar():
    doc = yaml.safe_load(render({"CHUNK_SIZE": "60"}))
    assert doc["kind"] == "ConfigMap" and doc["metadata"]["namespace"] == "rahbar"
    assert doc["metadata"]["name"] == "rahbar-config-candidate-03"
    assert doc["data"] == {"CHROMA_COLLECTION": "rahbar_candidate_03", "CHUNK_SIZE": "60",
                           "ALLOW_CACHE_BYPASS_03": "true", "GUARDRAIL_MODE": "block"}


def test_secret_looking_keys_and_bad_lines_rejected():
    with pytest.raises(ValueError):
        parse_env("LLM_API_KEY=abc")
    with pytest.raises(ValueError):
        parse_env("not a pair")


def test_rendered_candidate_always_keeps_cache_bypass_and_guardrail():
    """Regression: re-rendering a preset dropped ALLOW_CACHE_BYPASS_03, so the candidate served
    cached answers and the cold-run suite aborted."""
    data = yaml.safe_load(render({"TOP_K": "1"}))["data"]
    assert data["ALLOW_CACHE_BYPASS_03"] == "true" and data["GUARDRAIL_MODE"] == "block"
    assert yaml.safe_load(render({"GUARDRAIL_MODE": "flag"}))["data"]["GUARDRAIL_MODE"] == "flag"
