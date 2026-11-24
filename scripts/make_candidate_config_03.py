#!/usr/bin/env python3
"""Render a candidate preset (config/candidate_*_03.env) as the ConfigMap rahbar-config-candidate-03.

    python scripts/make_candidate_config_03.py config/candidate_fail_03.env > k8s/config_candidate_03.yaml
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

FORBIDDEN = re.compile(r"(KEY|TOKEN|SECRET|PASSWORD|CREDENTIAL)", re.I)
LINE = re.compile(r"^([A-Z][A-Z0-9_]*)=(.*)$")


def parse_env(text: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for n, raw in enumerate(text.splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        m = LINE.match(line)
        if not m:
            raise ValueError(f"line {n}: expected KEY=value, got {raw!r}")
        key, val = m.group(1), m.group(2).strip().strip('"').strip("'")
        if FORBIDDEN.search(key):
            raise ValueError(f"line {n}: secret-looking key {key!r} is not allowed")
        out[key] = val
    return out


def render(env: dict[str, str], collection: str = "rahbar_candidate_03",
           name: str = "rahbar-config-candidate-03", namespace: str = "rahbar") -> str:
    data = {"CHROMA_COLLECTION": collection, **env}
    lines = ["apiVersion: v1", "kind: ConfigMap", "metadata:", f"  name: {name}",
             f"  namespace: {namespace}",
             "  labels: {app.kubernetes.io/part-of: rahbar, ragops: \"03\"}", "data:"]
    for k in sorted(data):
        lines.append(f"  {k}: \"{data[k]}\"")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("env_file")
    ap.add_argument("--collection", default="rahbar_candidate_03")
    args = ap.parse_args(argv)
    try:
        env = parse_env(Path(args.env_file).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    sys.stdout.write(render(env, args.collection))
    return 0


if __name__ == "__main__":
    sys.exit(main())
