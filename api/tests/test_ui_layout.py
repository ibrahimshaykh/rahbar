"""Static checks on ui/index.html that no browser-free test could otherwise see.

Bug found in the live demo on 2026-11-07: `main` has `z-index: 1` and the fixed
question `form` had no z-index, so main's bottom padding was painted over the
question box and a mouse click never reached the textarea.
"""

import re
from pathlib import Path

UI = Path(__file__).resolve().parents[2] / "ui" / "index.html"


def _z_index(css: str, selector: str) -> int:
    rule = re.search(rf"(?m)^\s*{selector}\s*\{{([^}}]*)\}}", css)
    assert rule, f"no top-level CSS rule for {selector!r}"
    z = re.search(r"z-index:\s*(-?\d+)", rule.group(1))
    return int(z.group(1)) if z else 0


def test_question_form_is_stacked_above_main() -> None:
    css = UI.read_text(encoding="utf-8")
    assert _z_index(css, "form") > _z_index(css, "main")


INGRESS = Path(__file__).resolve().parents[2] / "k8s" / "base" / "ingress.yaml"


def test_every_api_path_the_ui_fetches_is_routed_to_the_api() -> None:
    """Second bug from the same demo: the UI's status chip fetches /readyz, but
    the Ingress only sent /api to the api Service, so /readyz reached the ui's
    nginx, got a 404 page, and the chip always said "service unreachable"."""
    fetched = set(re.findall(r"fetch\(`\$\{API_BASE\}(/[^`]*)`", UI.read_text(encoding="utf-8")))
    assert fetched, "found no fetch() calls in ui/index.html"
    ingress = INGRESS.read_text(encoding="utf-8")
    api_paths = re.findall(r"- path: (\S+)\s+pathType: (\w+)\s+backend:\s+service:\s+name: api\b", ingress)
    assert api_paths, "found no Ingress paths for the api Service"
    for path in fetched:
        routed = any(
            path == p if kind == "Exact" else path == p or path.startswith(p.rstrip("/") + "/")
            for p, kind in api_paths
        )
        assert routed, f"{path} is fetched by the UI but not routed to the api Service"
