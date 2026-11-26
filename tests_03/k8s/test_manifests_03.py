"""Static checks for the Assignment 03 Kubernetes manifests (T-K8S-01..17). No cluster needed."""
import re
import subprocess
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
K8S = ROOT / "k8s"
FILES = sorted(K8S.glob("*_03.yaml"))
POD_KINDS = {"Pod", "Deployment", "StatefulSet", "Job", "CronJob", "DaemonSet"}
PVC = "rahbar-ragops-pvc-03"
SECRET_RE = re.compile(r"gsk_[A-Za-z0-9]{20,}|AIza[A-Za-z0-9_-]{25,}|sk-[A-Za-z0-9]{30,}")


def load(path):
    with open(path, encoding="utf-8") as fh:
        return [d for d in yaml.safe_load_all(fh) if d]


def objects():
    out = []
    for f in FILES:
        if f.name.startswith("patch_"):
            continue  # strategic-merge patches carry no kind/metadata; tested separately
        for d in load(f):
            out.append((f, d))
    return out


def by_name(kind, name):
    for _, d in objects():
        if d["kind"] == kind and d["metadata"]["name"] == name:
            return d
    raise AssertionError(f"{kind}/{name} not found")


def pod_spec(d):
    if d["kind"] == "Pod":
        return d["spec"]
    if d["kind"] == "CronJob":
        return d["spec"]["jobTemplate"]["spec"]["template"]["spec"]
    return d["spec"]["template"]["spec"]


def pod_specs():
    return [(f, d, pod_spec(d)) for f, d in objects() if d["kind"] in POD_KINDS]


def test_k8s_01_all_files_parse():
    expected = {"pvc", "serviceaccount", "networkpolicy", "ingest_job", "ingest_cronjob", "eval_job",
                "gate_configmap", "api_candidate", "config_candidate", "patch_api_rollout", "helper_pod"}
    assert {f.name.replace("_03.yaml", "") for f in FILES} >= expected
    for f in FILES:
        assert load(f), f"{f.name} is empty"


def test_k8s_02_namespace_rahbar():
    for f, d in objects():
        if f.name.startswith("patch_"):
            continue
        assert d["metadata"]["namespace"] == "rahbar", (f.name, d["metadata"]["name"])


def test_k8s_03_requests_and_limits():
    specs = pod_specs()
    assert len(specs) >= 5
    for f, d, spec in specs:
        for c in spec["containers"]:
            for kind in ("requests", "limits"):
                res = c.get("resources", {}).get(kind, {})
                assert "cpu" in res and "memory" in res, (f.name, c["name"], kind)


def test_k8s_04_no_latest_hostpath_nodeport():
    for f in FILES:
        text = f.read_text(encoding="utf-8")
        assert ":latest" not in text, f.name
        assert "hostPath" not in text, f.name
        assert "NodePort" not in text and "LoadBalancer" not in text, f.name
    for f, d in objects():
        if d["kind"] == "Service":
            assert d["spec"].get("type", "ClusterIP") == "ClusterIP"
    for f, d, spec in pod_specs():
        for c in spec["containers"]:
            assert ":" in c["image"] and not c["image"].endswith(":latest"), c["image"]


def test_k8s_05_file_names_end_in_03():
    for f in K8S.glob("*"):
        if f.is_file():
            assert re.search(r"_03\.[A-Za-z0-9]+$", f.name), f.name


def test_k8s_06_pvc_and_mounts():
    pvc = by_name("PersistentVolumeClaim", PVC)
    assert pvc["spec"]["resources"]["requests"]["storage"] == "2Gi"
    assert pvc["spec"]["accessModes"] == ["ReadWriteOnce"]
    claims = 0
    for f, d, spec in pod_specs():
        mounts_data = any(m["mountPath"] == "/data" for c in spec["containers"] for m in c.get("volumeMounts", []))
        if mounts_data:
            names = {v["name"]: v for v in spec["volumes"]}
            assert names["ragops-data"]["persistentVolumeClaim"]["claimName"] == PVC
            claims += 1
    assert claims >= 5


def _selects(policy, app):
    return policy["spec"]["podSelector"].get("matchLabels", {}).get("app") == app


def test_k8s_07_networkpolicy_rules():
    pols = [d for _, d in objects() if d["kind"] == "NetworkPolicy"]
    names = {p["metadata"]["name"] for p in pols}
    assert {"70-ragops-ingest-03", "71-ragops-eval-03", "72-api-candidate-03", "73-allow-eval-to-api-03",
            "74-allow-ragops-to-chroma-03", "75-allow-ragops-to-redis-03", "76-ragops-helper-03"} <= names
    # no A03 policy lets ui reach chroma or redis
    for p in pols:
        for rule in p["spec"].get("ingress", []):
            for src in rule.get("from", []):
                assert src.get("podSelector", {}).get("matchLabels", {}).get("app") != "ui"
    # helper pod: no rules at all
    helper = by_name("NetworkPolicy", "76-ragops-helper-03")
    assert not helper["spec"].get("ingress") and not helper["spec"].get("egress")
    # ingest egress reaches chroma:8000, redis:6379, Ollama:11434
    ing = by_name("NetworkPolicy", "70-ragops-ingest-03")
    ports = {p["port"] for r in ing["spec"]["egress"] for p in r["ports"]}
    assert {8000, 6379, 11434, 53} <= ports
    # candidate ingress only from eval
    cand = by_name("NetworkPolicy", "72-api-candidate-03")
    srcs = [s["podSelector"]["matchLabels"]["app"] for r in cand["spec"]["ingress"] for s in r["from"]]
    assert srcs == ["ragops-eval-03"]
    # additive live-api policy selects the A02 label
    live = by_name("NetworkPolicy", "73-allow-eval-to-api-03")
    assert _selects(live, "api")


def test_k8s_08_no_secret_objects_or_keys():
    for f, d in objects():
        assert d["kind"] != "Secret", f.name
        assert "stringData" not in d and not (d["kind"] == "Secret" and "data" in d)
    for f in FILES:
        assert not SECRET_RE.search(f.read_text(encoding="utf-8")), f.name


def test_k8s_09_patch_rollout_zero_unavailable():
    (patch,) = load(K8S / "patch_api_rollout_03.yaml")
    ru = patch["spec"]["strategy"]["rollingUpdate"]
    assert ru["maxUnavailable"] == 0 and ru["maxSurge"] == 1
    c = patch["spec"]["template"]["spec"]["containers"][0]
    assert c["name"] == "api" and c["image"] == "rahbar-ragops-03:dev"
    assert {"name": "CHROMA_COLLECTION", "value": "rahbar_ragops_03"} in c["env"]


def test_k8s_10_no_placeholders():
    for f in FILES:
        for i, line in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
            assert line.strip() != "...", (f.name, i)
            assert "<copy" not in line, (f.name, i)
            assert "PENDING-HUMAN" not in line, (f.name, i)
            assert not re.search(r"(^|\s)\.\.\.(\s|$)", line), (f.name, i)


def test_k8s_11_gate_configmap_matches_repo_yaml():
    cm = by_name("ConfigMap", "rahbar-gate-03")
    embedded = yaml.safe_load(cm["data"]["gate_thresholds_03.yaml"])
    expected = {"recall_at_5_max_drop_pp": 2.0, "min_faithfulness": 0.80,
                "max_p95_latency_ms": 100000, "abstention_correctness_min_vs_baseline": 0.0}
    assert embedded == expected
    repo = ROOT / "config" / "gate_thresholds_03.yaml"
    assert repo.exists(), "config/gate_thresholds_03.yaml missing (Builder-2 artefact)"
    assert yaml.safe_load(repo.read_text(encoding="utf-8")) == embedded


def test_k8s_12_ingest_job():
    job = by_name("Job", "ragops-ingest-03")
    spec = job["spec"]
    assert spec["completions"] == 1 and spec["backoffLimit"] == 2
    assert spec.get("parallelism", 1) <= 1
    c = spec["template"]["spec"]["containers"][0]
    assert c["command"] == ["python", "-m", "indexer.run_ingest_03"]
    args = c["args"]
    assert args.count("--corpus") == 2 and "/corpus-baked" in args and "/app/corpus/batch_b_03" in args
    assert args[args.index("--corpus-optional") + 1] == "/data/incoming"
    assert args[args.index("--collection") + 1] == "rahbar_ragops_03"
    assert c["envFrom"][0]["configMapRef"]["name"] == "rahbar-config"


def test_k8s_13_cronjob():
    cj = by_name("CronJob", "ragops-ingest-cron-03")
    assert cj["spec"]["concurrencyPolicy"] == "Forbid"
    assert len(cj["spec"]["schedule"].split()) == 5
    job = by_name("Job", "ragops-ingest-03")
    assert pod_spec(cj)["containers"] == job["spec"]["template"]["spec"]["containers"]
    assert pod_spec(cj)["volumes"] == job["spec"]["template"]["spec"]["volumes"]


def test_k8s_14_eval_job():
    job = by_name("Job", "ragops-eval-03")
    assert job["spec"]["backoffLimit"] == 0
    spec = job["spec"]["template"]["spec"]
    assert spec["restartPolicy"] == "Never"
    c = spec["containers"][0]
    mount = next(m for m in c["volumeMounts"] if m["mountPath"] == "/config")
    vol = next(v for v in spec["volumes"] if v["name"] == mount["name"])
    assert vol["configMap"]["name"] == "rahbar-gate-03"
    env = {e["name"]: e["value"] for e in c["env"]}
    assert env["GATE_THRESHOLDS_PATH"].startswith("/config/")
    assert env["EVAL_TARGET_URL"] == "http://api-candidate-03:8000"
    assert env["EVAL_BASELINE_URL"] == "http://api:8000"


def test_k8s_15_pvc_only_through_claim():
    for f, d, spec in pod_specs():
        for v in spec.get("volumes", []):
            assert "hostPath" not in v
            if "persistentVolumeClaim" in v:
                assert v["persistentVolumeClaim"]["claimName"] == PVC, f.name


def test_k8s_16_candidate_deployment_and_service():
    dep = by_name("Deployment", "api-candidate-03")
    assert dep["spec"]["strategy"]["rollingUpdate"]["maxUnavailable"] == 0
    svc = by_name("Service", "api-candidate-03")
    assert svc["spec"]["type"] == "ClusterIP"
    labels = dep["spec"]["template"]["metadata"]["labels"]
    assert all(labels.get(k) == v for k, v in svc["spec"]["selector"].items())
    assert dep["spec"]["selector"]["matchLabels"].items() <= labels.items()
    c = dep["spec"]["template"]["spec"]["containers"][0]
    assert c["readinessProbe"]["httpGet"]["path"] == "/readyz"
    assert c["livenessProbe"]["httpGet"]["path"] == "/healthz"
    ref = next(e for e in c["env"] if e["name"] == "LLM_API_KEY")["valueFrom"]["secretKeyRef"]
    assert ref["name"] == "rahbar-secret" and ref["key"] == "LLM_API_KEY"
    assert [e["configMapRef"]["name"] for e in c["envFrom"]] == ["rahbar-config", "rahbar-config-candidate-03"]


def test_k8s_17_candidate_configmap_rules():
    cm = by_name("ConfigMap", "rahbar-config-candidate-03")
    for key in cm["data"]:
        assert key != "EMBED_MODEL"
        assert "KEY" not in key.upper() and "TOKEN" not in key.upper()
    assert cm["data"]["CHROMA_COLLECTION"] == "rahbar_candidate_03"


def test_k8s_18_helper_pod_resources():
    pod = by_name("Pod", "ragops-helper-03")
    c = pod["spec"]["containers"][0]
    assert c["resources"]["requests"] == {"cpu": "10m", "memory": "16Mi"}
    assert c["resources"]["limits"] == {"cpu": "100m", "memory": "64Mi"}


def test_k8s_19_security_context():
    for f, d, spec in pod_specs():
        assert spec["securityContext"]["runAsNonRoot"] is True
        assert spec["securityContext"]["fsGroup"] == 10001
        for c in spec["containers"]:
            sc = c["securityContext"]
            assert sc["allowPrivilegeEscalation"] is False
            assert sc["readOnlyRootFilesystem"] is True
            assert sc["capabilities"]["drop"] == ["ALL"]


def test_k8s_20_a02_base_untouched_and_dockerfile():
    text = (ROOT / "Dockerfile_03").read_text(encoding="utf-8")
    assert "FROM python:3.12-slim-bookworm" in text and ":latest" not in text
    assert "tesseract-ocr" in text and "poppler-utils" in text
    assert "COPY corpus/batch_b_03 /app/corpus/batch_b_03" in text
    assert "corpus/raw" not in text


def test_k8s_16b_job_entry_syntax_if_present():
    entry = ROOT / "eval" / "job_entry_03.sh"
    assert entry.exists(), "eval/job_entry_03.sh missing (Builder-2 artefact)"
    r = subprocess.run(["sh", "-n", str(entry)], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr


def test_k8s_16c_job_entry_can_reuse_baseline_and_limit_candidate_runs():
    """Each real suite run costs ~25 min on a CPU-only LLM, so a gate demo must be able to
    reuse the stored baseline and run the candidate once (defaults keep the full protocol)."""
    text = (ROOT / "eval" / "job_entry_03.sh").read_text(encoding="utf-8")
    assert "REUSE_BASELINE" in text and "CANDIDATE_RUNS" in text
    assert '${CANDIDATE_RUNS:-2}' in text           # default stays 2 runs
    assert '${REUSE_BASELINE:-0}' in text           # default stays "run the baseline"


def test_k8s_09b_patch_relaxes_api_probes_for_a_loaded_node():
    """During evals the single-node cluster stalls for minutes; the base probes (5 s, 3 misses)
    restarted every api pod mid-suite and 17 requests got 'connection refused'."""
    (patch,) = load(K8S / "patch_api_rollout_03.yaml")
    c = patch["spec"]["template"]["spec"]["containers"][0]
    assert c["livenessProbe"]["timeoutSeconds"] >= 10 and c["livenessProbe"]["failureThreshold"] >= 6
    assert c["readinessProbe"]["timeoutSeconds"] >= 10
    assert c["startupProbe"]["failureThreshold"] >= 120
