"""The 2D placement boundary: two independent size axes, no scale factor.

`public_2d_render_targets` is a client-side whitelist, so anything it does not
recognise never reaches the API at all. That makes it the one place where a
placement field can be lost without any HTTP response to explain it -- which is
exactly how a free-transform placement would have failed silently before the
whitelist learned about width/height.
"""

from __future__ import annotations

import pytest

from sudomock._public_contract import public_2d_render_targets


def _target(**placement: object) -> list[dict[str, object]]:
    return [{"uuid": "pa-1", "artwork_url": "https://example.test/a.png", "placement": placement}]


def test_free_transform_size_survives_the_boundary() -> None:
    """A one-axis stretch is transmitted as drawn."""
    out = public_2d_render_targets(_target(width=800, height=200))

    assert out[0]["placement"] == {"width": 800, "height": 200}


def test_ratio_breaking_size_is_not_normalised_back_to_the_artwork_ratio() -> None:
    """The boundary copies the numbers; it must not have an opinion on aspect.

    Fails if anyone ever "helpfully" re-derives one axis from the other here.
    """
    out = public_2d_render_targets(_target(width=1000, height=17))

    assert out[0]["placement"]["width"] == 1000
    assert out[0]["placement"]["height"] == 17


def test_uniform_size_is_just_both_axes_equal() -> None:
    """There is no separate uniform path to break."""
    out = public_2d_render_targets(_target(width=500, height=500))

    assert out[0]["placement"] == {"width": 500, "height": 500}


def test_scale_is_rejected_rather_than_dropped() -> None:
    """The retired field must fail loudly.

    A caller still sending `scale` has to learn that here, at the SDK boundary.
    Silently stripping it would send a request that renders at the default
    coverage and returns 200 -- a wrong image with no error anywhere.
    """
    with pytest.raises(ValueError, match="documented placement options"):
        public_2d_render_targets(_target(scale=2.0))


def test_retired_size_object_is_rejected() -> None:
    """The old deprecated `size: {width, height}` object is gone too."""
    with pytest.raises(ValueError, match="documented placement options"):
        public_2d_render_targets(_target(size={"width": 800, "height": 200}))


def test_each_target_kind_takes_only_its_own_placement_options() -> None:
    """A percentage spans a surface; a fit meets a print area. Never crossed."""
    surface = public_2d_render_targets(
        [
            {
                "surface_uuid": "surface-1",
                "artwork_url": "https://e.test/a.png",
                "placement": {"position": "center", "coverage": 80},
            }
        ]
    )
    assert surface[0]["placement"] == {"position": "center", "coverage": 80}

    area = public_2d_render_targets(_target(position="center", fit="contain"))
    assert area[0]["placement"] == {"position": "center", "fit": "contain"}

    # Crossed, both ways. The API answers each with a 422, so refusing here
    # spends no call and names the mistake where the caller made it.
    with pytest.raises(ValueError):
        public_2d_render_targets(_target(coverage=80))
    with pytest.raises(ValueError):
        public_2d_render_targets(
            [
                {
                    "surface_uuid": "surface-1",
                    "artwork_url": "https://e.test/a.png",
                    "placement": {"fit": "contain"},
                }
            ]
        )


def test_placement_is_copied_not_aliased() -> None:
    """Mutating the caller's dict afterwards must not change what we send."""
    caller_placement: dict[str, object] = {"width": 800, "height": 200}
    out = public_2d_render_targets(
        [{"uuid": "pa-1", "artwork_url": "https://e.test/a.png", "placement": caller_placement}]
    )
    caller_placement["width"] = 1

    assert out[0]["placement"]["width"] == 800
