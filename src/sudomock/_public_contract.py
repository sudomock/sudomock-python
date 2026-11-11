"""Small boundary helpers for outcome-only public SDK payloads."""

from __future__ import annotations

import math
from typing import Any, Optional

_TARGET_FIELDS = {
    "uuid",
    "surface_uuid",
    "base64",
    "artwork_url",
    "color",
    "adjustments",
    "placement",
    "remove_background",
}
_ADJUSTMENT_FIELDS = {
    "brightness",
    "contrast",
    "opacity",
    "saturation",
    "vibrance",
    "blur",
}
# Sizing is "width" + "height" in print-area pixels, and the two axes are
# independent: a one-axis stretch is a supported placement, not an error.
# There is deliberately no single scale factor -- one number cannot express two
# free axes, and keeping it alongside would give callers two ways to say a size
# that disagree the moment the ratio is broken.
_PLACEMENT_FIELDS = {
    "position",
    "rotation",
    "offset_x",
    "offset_y",
    "tile",
    "tile_spacing",
}
# Sizing is the one option that belongs to a kind of target, and the API answers
# the crossed pair with a 422. A surface is spanned by a percentage; a print area
# is met by a fit against its bounds. An explicit box belongs to BOTH: a
# percentage cannot express a box whose proportions differ from the surface, so
# refusing width/height on a surface makes every all-over print somebody resized
# on canvas unsendable.
_SIZE_AXES = ("width", "height")
_SURFACE_PLACEMENT_FIELDS = _PLACEMENT_FIELDS | {"coverage", *_SIZE_AXES}
_PRINT_AREA_PLACEMENT_FIELDS = _PLACEMENT_FIELDS | {"fit", *_SIZE_AXES}
# Whichever kind of target it is, sizing has exactly one answer per request.
_SIZING_MODES = ("coverage", "fit")


def _check_sizing(placement: dict[str, Any]) -> None:
    """Refuse a placement that answers the sizing question twice, or half.

    Both of these are a 422 at the API. Naming them here costs no call and
    names the mistake where the caller made it.
    """
    named_axes = [axis for axis in _SIZE_AXES if axis in placement]
    if len(named_axes) == 1:
        raise ValueError(
            "Render target placement width and height must be provided together: "
            "half a size is not a size."
        )
    crossed = [mode for mode in _SIZING_MODES if mode in placement]
    if named_axes and crossed:
        raise ValueError(
            "Render target placement gives two different ways to size: "
            f"an explicit width and height, and {crossed[0]}. Send one."
        )


def seam_tile_body(
    name: str,
    url: Optional[str],
    base64_data: Optional[str],
    content_type: Optional[str],
    crop_aspect: Optional[float],
) -> dict[str, Any]:
    """Build the body of a seam check or seam fix: exactly one image source,
    and a crop aspect above 0 when one is given. Both are a 422 at the API;
    refusing them here costs no call."""
    if bool(url) == bool(base64_data):
        raise ValueError(f"{name} requires exactly one of url or base64")
    body: dict[str, Any] = {"url": url} if url else {"base64": base64_data}
    if content_type is not None:
        body["content_type"] = content_type
    if crop_aspect is not None:
        if (
            isinstance(crop_aspect, bool)
            or not isinstance(crop_aspect, (int, float))
            or not math.isfinite(crop_aspect)
            or crop_aspect <= 0
        ):
            raise ValueError(f"{name} crop_aspect must be a number greater than 0")
        body["crop_aspect"] = crop_aspect
    return body


def public_error_text(value: Any, fallback: Optional[str] = None) -> Optional[str]:
    """Return the API's own message, or the fallback when it sent none.

    The field is typed as a string but arrives from JSON, where it can be a
    dict, a list or null. Anything that is not a non-empty string becomes the
    fallback, so a caller never meets a message of the wrong type.
    """
    if not isinstance(value, str) or not value:
        return fallback
    return value


def public_error_code(value: Any) -> Optional[str]:
    """Return the API's own error code, or None when it sent none."""
    if not isinstance(value, str) or not value:
        return None
    return value


def public_2d_render_targets(targets: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Validate and copy only the documented 2D render target fields."""
    normalized: list[dict[str, Any]] = []
    for target in targets:
        if not isinstance(target, dict) or not set(target) <= _TARGET_FIELDS:
            raise ValueError("Each render target must use only documented options.")
        if ("uuid" in target) == ("surface_uuid" in target):
            raise ValueError("Each render target requires exactly one target UUID.")

        adjustments = target.get("adjustments")
        if adjustments is not None and (
            not isinstance(adjustments, dict) or not set(adjustments) <= _ADJUSTMENT_FIELDS
        ):
            raise ValueError("Each render target must use only documented adjustments.")

        placement = target.get("placement")
        allowed = (
            _SURFACE_PLACEMENT_FIELDS if "surface_uuid" in target else _PRINT_AREA_PLACEMENT_FIELDS
        )
        if placement is not None and (
            not isinstance(placement, dict) or not set(placement) <= allowed
        ):
            raise ValueError("Each render target must use only documented placement options.")
        if isinstance(placement, dict):
            _check_sizing(placement)

        normalized.append(
            {
                key: (
                    dict(value)
                    if key in {"adjustments", "placement"} and isinstance(value, dict)
                    else value
                )
                for key, value in target.items()
            }
        )
    return normalized
