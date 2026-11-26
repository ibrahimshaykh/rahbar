import json

import httpx
import pytest

from eval.e2e_eval_03 import (
    ColdRunError, HttpAsk03, PassageSourceError, abstention_metrics, agreement,
    citation_validity, latency_metrics, llm_judge, make_passage_lookup_03, parse_judge_json,
    rule_judge, run_e2e,
)
from eval.metrics_lib_03 import percentile


def resp(answered, citations=(), retrieved=(), answer="a"):
    return {"answered_from_context": answered, "answer": answer,
            "citations": list(citations), "retrieved": list(retrieved)}


def rec(category, response, lat=10.0, cache="miss", facts=()):
    return {"item": {"id": "x", "category": category, "question": "q",
                     "expected_answer_facts": list(facts)},
            "response": response, "latency_ms": lat, "cache": cache, "trace_id": None}


def test_abstention_maths():  # T-E2E-01
    recs = [rec("unanswerable", resp(False)), rec("unanswerable", resp(True)),
            rec("unanswerable", resp(False)), rec("answerable", resp(False)),
            rec("answerable", resp(True))]
    m = abstention_metrics(recs)
    assert abs(m["abstention_correctness"] - 2 / 3) < 1e-12 and m["n_unanswerable"] == 3
    assert m["false_abstention_rate"] == 0.5
    assert abstention_metrics([])["abstention_correctness"] is None


def test_citation_validity_page_mismatch():  # T-E2E-02
    ret = [{"chunk_id": "c", "source": "A.pdf", "page": 3}]
    ok = {"source": "a.PDF", "page": 3}
    null_page = {"source": "A.pdf", "page": None}
    bad_page = {"source": "A.pdf", "page": 9}
    m = citation_validity([rec("answerable", resp(True, [ok, null_page, bad_page], ret)),
                           rec("answerable", resp(False, [bad_page], ret))])
    assert m["n_citations"] == 3 and abs(m["citation_validity"] - 2 / 3) < 1e-12


def test_judge_json_validation():  # T-E2E-03
    assert parse_judge_json('{"supported": true, "unsupported_claims": []}') == (True, True)
    for bad in ["not json", '{"supported": "yes"}', "[]", "", '{"unsupported_claims": []}']:
        assert parse_judge_json(bad) == (False, False)
    judge = llm_judge(lambda s, u: "garbage")
    assert judge("ans", ["ctx"]) == (False, False)


def test_agreement_and_confusion():  # T-E2E-04
    human = [{"id": "1", "answer": "x", "retrieved_ids": ["p"], "human_label": True},
             {"id": "2", "answer": "x", "retrieved_ids": ["p"], "human_label": False},
             {"id": "3", "answer": "x", "retrieved_ids": ["p"], "human_label": True},
             {"id": "4", "answer": "x", "retrieved_ids": ["p"], "human_label": False}]
    verdicts = iter([True, True, False, False])
    out = agreement(human, lambda a, p: (next(verdicts), True), lambda ids: {"p": "t"})
    assert out["confusion"] == {"TP": 1, "TN": 1, "FP": 1, "FN": 1}
    assert out["judge_agreement_pct"] == 50.0 and out["n_human_labelled"] == 4


def test_latency_uses_shared_percentile():  # T-E2E-05
    recs = [rec("answerable", resp(True), lat=v) for v in (10, 20, 30, 40, 50)]
    m = latency_metrics(recs)
    assert m["latency_p50_ms"] == percentile([10, 20, 30, 40, 50], 50) == 30
    assert m["latency_p95_ms"] == 50 and m["n_latency"] == 5


def test_missing_traces_and_chroma_raises():  # T-E2E-06
    with pytest.raises(PassageSourceError):
        make_passage_lookup_03()
    with pytest.raises(PassageSourceError):
        make_passage_lookup_03(traces="x", chroma=True)


def test_traces_lookup(tmp_path):
    p = tmp_path / "t.jsonl"
    p.write_text(json.dumps({"retrieved_chunks": [{"chunk_id": "a", "text": "hello"}]}) + "\n\n")
    assert make_passage_lookup_03(traces=str(p))(["a", "zz"]) == {"a": "hello"}


def test_rule_judge():
    assert rule_judge("Attendance must be 100 percent.", ["attendance must be 100 percent always"]) \
        == (True, True)
    assert rule_judge("The cafeteria serves biryani daily.", ["attendance rules apply"]) \
        == (False, True)


def scripted_ask(responses):
    it = iter(responses)

    def ask(_q):
        r = next(it)
        return {"response": r, "latency_ms": 5.0, "cache": "miss", "trace_id": None, "error": None}
    return ask


def test_run_e2e_end_to_end_and_cold_flag():
    items = [{"id": "G1", "category": "answerable", "question": "q",
              "expected_answer_facts": ["2.00"]},
             {"id": "G2", "category": "unanswerable", "question": "q", "expected_answer_facts": []}]
    ret = [{"chunk_id": "c1", "source": "A", "page": 1}]
    r1 = resp(True, [{"source": "A", "page": 1}], ret, "CGPA 2.00 minimum")
    e2e, _, errors = run_e2e(items, scripted_ask([r1, resp(False)]), rule_judge,
                             lambda ids: {"c1": "CGPA 2.00 minimum required"})
    assert errors == 0 and e2e["abstention_correctness"] == 1.0
    assert e2e["faithfulness"] == 1.0 and e2e["answer_hit_rate"] == 1.0
    assert e2e["items"][0]["id"] == "G1"

    def hit_ask(_q):
        return {"response": resp(False), "latency_ms": 1.0, "cache": "hit", "error": None}
    with pytest.raises(ColdRunError):
        run_e2e(items, hit_ask, rule_judge, lambda ids: {}, require_cold=True)


def test_run_e2e_counts_errors():
    items = [{"id": "G1", "category": "answerable", "question": "q"}]
    err = lambda _q: {"response": None, "latency_ms": 1.0, "cache": None, "error": "boom"}  # noqa: E731
    _, _, errors = run_e2e(items, err, rule_judge, lambda ids: {})
    assert errors == 1


def test_http_ask_captures_headers_and_bypass_header():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["bypass"] = request.headers.get("x-bypass-cache-03")
        return httpx.Response(200, json=resp(True), headers={"X-Cache": "miss", "X-Trace-Id": "t1"})

    ask = HttpAsk03("http://api", transport=httpx.MockTransport(handler), retry_delay=0)
    out = ask("question here")
    assert seen["bypass"] == "1" and out["cache"] == "miss" and out["trace_id"] == "t1"
    assert out["error"] is None and out["latency_ms"] >= 0


def test_http_ask_client_error_is_reported_not_swallowed():
    ask = HttpAsk03("http://api", transport=httpx.MockTransport(lambda r: httpx.Response(422)),
                    retry_delay=0)
    out = ask("q")
    assert out["response"] is None and "422" in out["error"]


def test_ollama_judge_uses_its_own_schema_not_the_answer_schema():  # T-E2E-JUDGE-LIVE
    """Regression: the judge went through the A02 provider whose Ollama call forces the ANSWER
    schema, so a {"supported": ...} reply was impossible and faithfulness was always 0."""
    from eval.e2e_eval_03 import JUDGE_JSON_SCHEMA_03, ollama_complete_03

    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["payload"] = json.loads(request.content)
        return httpx.Response(200, json={"message": {"content":
                                                     '{"supported": true, "unsupported_claims": []}'}})

    complete = ollama_complete_03("http://ollama.test:11434", "llama3.2:3b", 30.0,
                                  transport=httpx.MockTransport(handler))
    judge = llm_judge(complete)
    assert judge("Attendance is 80 percent.", ["Attendance must be 80 percent."]) == (True, True)
    p = seen["payload"]
    assert seen["url"] == "http://ollama.test:11434/api/chat"
    assert p["format"] == JUDGE_JSON_SCHEMA_03 and "supported" in p["format"]["properties"]
    assert p["options"]["temperature"] == 0 and p["stream"] is False and p["model"] == "llama3.2:3b"


def test_run_e2e_items_record_the_request_error_text():  # T-E2E-ERR
    """A bare 'N request error(s)' count made the live smoke failure undiagnosable."""
    items = [{"id": "G1", "category": "answerable", "question": "q"}]
    err = lambda _q: {"response": None, "latency_ms": 1.0, "cache": None, "error": "ReadTimeout: x"}  # noqa: E731
    e2e, _, _ = run_e2e(items, err, rule_judge, lambda ids: {})
    assert e2e["items"][0]["error"] == "ReadTimeout: x"


def test_http_retrieve_matches_the_ask_contract_for_the_component_level():  # T-RET-02
    from eval.e2e_eval_03 import HttpRetrieve03

    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["path"] = request.url.path
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json={"retrieved": [{"chunk_id": "c1", "source": "a.md",
                                                        "section": "s", "page": 1, "score": 0.9}]})

    out = HttpRetrieve03("http://api", transport=httpx.MockTransport(handler))("what is x?")
    assert seen["path"] == "/api/retrieve_03" and seen["body"] == {"question": "what is x?"}
    assert out["response"]["retrieved"][0]["chunk_id"] == "c1"
    assert out["error"] is None and out["latency_ms"] >= 0


def test_http_retrieve_reports_errors_instead_of_raising():  # T-RET-03
    from eval.e2e_eval_03 import HttpRetrieve03

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="boom")

    out = HttpRetrieve03("http://api", transport=httpx.MockTransport(handler))("q")
    assert out["response"] is None and "500" in out["error"]


def test_http_ask_retries_transient_connection_errors_and_times_the_good_attempt():  # T-E2E-RETRY
    """The cluster node stalls under load and the API drops connections for a minute; the
    suite must not turn that into 17 failed items, and must not bill the wait as latency."""
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] < 3:
            raise httpx.ConnectError("Connection refused")
        return httpx.Response(200, json=resp(True), headers={"X-Cache": "miss"})

    ask = HttpAsk03("http://api", transport=httpx.MockTransport(handler), retry_delay=0,
                    connect_retries=5, connect_retry_wait=0)
    out = ask("question here")
    assert out["error"] is None and out["response"] is not None
    assert calls["n"] == 3 and out["connect_retries"] == 2


def test_http_ask_gives_up_after_the_retry_budget():  # T-E2E-RETRY-2
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("Connection refused")

    ask = HttpAsk03("http://api", transport=httpx.MockTransport(handler), retry_delay=0,
                    connect_retries=2, connect_retry_wait=0)
    out = ask("q")
    assert out["response"] is None and "ConnectError" in out["error"] and out["connect_retries"] == 2


def test_http_ask_retries_5xx_and_connect_timeout():  # T-E2E-RETRY-3
    seq = [httpx.Response(500, text="boom"), None,
           httpx.Response(200, json=resp(True), headers={"X-Cache": "miss"})]

    def handler(request: httpx.Request) -> httpx.Response:
        item = seq.pop(0)
        if item is None:
            raise httpx.ConnectTimeout("timed out")
        return item

    out = HttpAsk03("http://api", transport=httpx.MockTransport(handler), retry_delay=0,
                    connect_retries=5, connect_retry_wait=0)("q")
    assert out["error"] is None and out["response"] is not None


def test_http_ask_retries_a_read_timeout_only_once():  # T-E2E-RETRY-4
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        raise httpx.ReadTimeout("timed out")

    out = HttpAsk03("http://api", transport=httpx.MockTransport(handler), retry_delay=0,
                    connect_retries=8, connect_retry_wait=0)("q")
    assert out["response"] is None and "ReadTimeout" in out["error"]
    assert calls["n"] <= 4      # at most one extra attempt (A02's own retry may double each)
