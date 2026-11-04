"""The embedding pin (section 4.4). A rule is a sentence someone breaks in
week nine; this makes the broken state unreachable."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PinStatus:
    ok: bool
    collection_model: str | None
    collection_dimension: int | None
    api_model: str
    conflict: str | None


def check_pin(collection_metadata: dict[str, object], api_model: str) -> PinStatus:
    raw = collection_metadata.get("embed_model")
    model = str(raw) if raw is not None else None
    dim_raw = collection_metadata.get("dimension")
    dimension = (
        int(dim_raw)
        if isinstance(dim_raw, (int, float, str)) and str(dim_raw).isdigit()
        else None
    )

    if model is None:
        return PinStatus(
            ok=False, collection_model=None, collection_dimension=dimension,
            api_model=api_model,
            conflict="collection carries no embed_model metadata; it was not "
                     "written by this indexer")
    if model != api_model:
        return PinStatus(
            ok=False, collection_model=model, collection_dimension=dimension,
            api_model=api_model,
            conflict=f"collection indexed with {model!r} but EMBED_MODEL is "
                     f"{api_model!r}; re-index or revert the ConfigMap")
    return PinStatus(ok=True, collection_model=model, collection_dimension=dimension,
                     api_model=api_model, conflict=None)
