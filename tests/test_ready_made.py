"""SudoMock's ready-made catalogue on both clients."""

from __future__ import annotations

from typing import TYPE_CHECKING
from urllib.parse import parse_qs, urlparse

import httpx
import pytest

from sudomock import AsyncSudoMock, SudoMock
from sudomock.exceptions import NotFoundError
from sudomock.models import ReadyMadeTemplateDetail, ReadyMadeTemplatePage

from .conftest import TEST_API_KEY, TEST_BASE_URL

if TYPE_CHECKING:
    import respx

SLUG = "accent-coffee-mug-11-15oz-mockup-5afc"

# The shape the live endpoints answer with: bare, no {success, data} envelope.
TEMPLATE = {
    "slug": SLUG,
    "title": "Accent Coffee Mug (11, 15oz) Mockup",
    "description": "Accent mug mockup shown in 9 views.",
    "category": "drinkware",
    "subcategory": "mugs",
    "product_type": "two-tone-mug",
    "tags": ["two-tone-mug-mockup", "coffee-mug-mockup"],
    "is_featured": False,
    "mockup_count": 9,
    "mockups": [
        {
            "name": "Lifestyle Scene",
            "view": "lifestyle-scene",
            "source_url": "https://assets.example.invalid/a.png",
        }
    ],
}

PAGE = {
    "templates": [TEMPLATE],
    "total_templates": 12,
    "total_mockups": 97,
    "page": 1,
    "limit": 20,
    "pages": 1,
}

DETAIL = {
    **TEMPLATE,
    "long_description": "The scene described at length.",
    "features": ["9 views, including Handle Left"],
    "visual_style": ["lifestyle", "overhead"],
    "target_audience": [],
    "compatible_platforms": ["etsy", "shopify"],
    "industries": [],
    "use_cases": [],
    "seasons": [],
    "published_at": "2026-10-31T13:09:06.177196Z",
}


def _query(route: respx.Route) -> dict[str, list[str]]:
    return parse_qs(urlparse(str(route.calls[0].request.url)).query)


class TestSearch:
    def test_returns_the_page_with_every_view_and_its_render_address(
        self, mock_api: respx.MockRouter
    ) -> None:
        mock_api.get("/api/v1/library/templates").mock(return_value=httpx.Response(200, json=PAGE))

        with SudoMock(api_key=TEST_API_KEY, base_url=TEST_BASE_URL) as client:
            page = client.ready_made_mockups.search(search="coffee mug")

        assert isinstance(page, ReadyMadeTemplatePage)
        assert page.total_templates == 12
        assert page.total_mockups == 97
        assert page.pages == 1
        template = page.templates[0]
        assert template.slug == SLUG
        assert template.product_type == "two-tone-mug"
        assert template.is_featured is False
        assert template.mockup_count == 9
        assert template.mockups[0].source_url == "https://assets.example.invalid/a.png"
        assert template.mockups[0].view == "lifestyle-scene"

    def test_sends_every_filter_in_the_spelling_the_api_reads(
        self, mock_api: respx.MockRouter
    ) -> None:
        route = mock_api.get("/api/v1/library/templates").mock(
            return_value=httpx.Response(200, json=PAGE)
        )

        with SudoMock(api_key=TEST_API_KEY, base_url=TEST_BASE_URL) as client:
            client.ready_made_mockups.search(
                search="oversized tee",
                category="apparel",
                subcategory="t-shirts",
                product_type="crewneck-short-sleeve",
                tags=["t-shirt-mockup", "unisex"],
                platforms=["etsy", "shopify"],
                industries=["fashion"],
                use_cases=["product-listing"],
                is_featured=True,
                page=2,
                limit=5,
                sort_by="title",
                sort_order="asc",
            )

        query = _query(route)
        assert query["search"] == ["oversized tee"]
        assert query["category"] == ["apparel"]
        assert query["subcategory"] == ["t-shirts"]
        assert query["product_type"] == ["crewneck-short-sleeve"]
        assert query["tags"] == ["t-shirt-mockup,unisex"]
        assert query["platforms"] == ["etsy,shopify"]
        assert query["industries"] == ["fashion"]
        assert query["use_cases"] == ["product-listing"]
        assert query["is_featured"] == ["true"]
        assert query["page"] == ["2"]
        assert query["limit"] == ["5"]
        assert query["sort_by"] == ["title"]
        assert query["sort_order"] == ["asc"]

    def test_sends_no_query_when_nothing_is_filtered(self, mock_api: respx.MockRouter) -> None:
        route = mock_api.get("/api/v1/library/templates").mock(
            return_value=httpx.Response(200, json=PAGE)
        )

        with SudoMock(api_key=TEST_API_KEY, base_url=TEST_BASE_URL) as client:
            client.ready_made_mockups.search()

        assert _query(route) == {}

    def test_leaves_an_empty_filter_list_out(self, mock_api: respx.MockRouter) -> None:
        route = mock_api.get("/api/v1/library/templates").mock(
            return_value=httpx.Response(200, json=PAGE)
        )

        with SudoMock(api_key=TEST_API_KEY, base_url=TEST_BASE_URL) as client:
            client.ready_made_mockups.search(tags=[], platforms=[])

        assert _query(route) == {}

    def test_sends_is_featured_false_when_the_caller_asks_for_the_rest(
        self, mock_api: respx.MockRouter
    ) -> None:
        route = mock_api.get("/api/v1/library/templates").mock(
            return_value=httpx.Response(200, json=PAGE)
        )

        with SudoMock(api_key=TEST_API_KEY, base_url=TEST_BASE_URL) as client:
            client.ready_made_mockups.search(is_featured=False)

        assert _query(route)["is_featured"] == ["false"]


class TestGetTemplate:
    def test_reads_one_template_with_its_long_form_copy(self, mock_api: respx.MockRouter) -> None:
        mock_api.get(f"/api/v1/library/templates/{SLUG}").mock(
            return_value=httpx.Response(200, json=DETAIL)
        )

        with SudoMock(api_key=TEST_API_KEY, base_url=TEST_BASE_URL) as client:
            template = client.ready_made_mockups.get_template(SLUG)

        assert isinstance(template, ReadyMadeTemplateDetail)
        assert template.long_description == "The scene described at length."
        assert template.visual_style == ["lifestyle", "overhead"]
        assert template.compatible_platforms == ["etsy", "shopify"]
        assert template.published_at is not None
        assert template.mockups[0].source_url == "https://assets.example.invalid/a.png"

    def test_keeps_the_slug_to_one_path_segment(self, mock_api: respx.MockRouter) -> None:
        route = mock_api.get("/api/v1/library/templates/a-slug%3Flimit%3D100").mock(
            return_value=httpx.Response(200, json=DETAIL)
        )

        with SudoMock(api_key=TEST_API_KEY, base_url=TEST_BASE_URL) as client:
            client.ready_made_mockups.get_template("a-slug?limit=100")

        assert route.called
        assert urlparse(str(route.calls[0].request.url)).query == ""

    def test_raises_not_found_for_a_slug_the_catalogue_does_not_hold(
        self, mock_api: respx.MockRouter
    ) -> None:
        mock_api.get("/api/v1/library/templates/no-such-slug").mock(
            return_value=httpx.Response(
                404, json={"detail": "Template 'no-such-slug' not found", "success": False}
            )
        )

        with SudoMock(api_key=TEST_API_KEY, base_url=TEST_BASE_URL) as client:
            with pytest.raises(NotFoundError):
                client.ready_made_mockups.get_template("no-such-slug")


class TestAsyncClient:
    @pytest.mark.asyncio
    async def test_search_and_get_template_match_the_sync_contract(
        self, mock_api: respx.MockRouter
    ) -> None:
        mock_api.get("/api/v1/library/templates").mock(return_value=httpx.Response(200, json=PAGE))
        mock_api.get(f"/api/v1/library/templates/{SLUG}").mock(
            return_value=httpx.Response(200, json=DETAIL)
        )

        async with AsyncSudoMock(api_key=TEST_API_KEY, base_url=TEST_BASE_URL) as client:
            page = await client.ready_made_mockups.search(category="drinkware", limit=5)
            template = await client.ready_made_mockups.get_template(SLUG)

        assert page.total_mockups == 97
        assert page.templates[0].slug == SLUG
        assert template.long_description == "The scene described at length."

    @pytest.mark.asyncio
    async def test_sends_the_same_query_as_the_sync_client(
        self, mock_api: respx.MockRouter
    ) -> None:
        route = mock_api.get("/api/v1/library/templates").mock(
            return_value=httpx.Response(200, json=PAGE)
        )

        async with AsyncSudoMock(api_key=TEST_API_KEY, base_url=TEST_BASE_URL) as client:
            await client.ready_made_mockups.search(
                tags=["t-shirt-mockup", "unisex"], is_featured=True, page=3
            )

        query = _query(route)
        assert query["tags"] == ["t-shirt-mockup,unisex"]
        assert query["is_featured"] == ["true"]
        assert query["page"] == ["3"]


class TestReadmeWalkthrough:
    """The four steps the README's ready-made section prints, run end to end.

    The snippet is the contract a reader copies, so a wrong argument name or a
    field that moved has to fail here rather than on the reader's first run.
    """

    def test_search_read_create_render(self, mock_api: respx.MockRouter) -> None:
        created = {
            "mockup_id": "6f0b9d21-4c7e-4a85-9b3f-2d8c1e5a7043",
            "customizable": True,
            "surfaces": [
                {
                    "surface_uuid": "1b7e2c45-9a38-4d61-8f0c-5e3a7d9b2461",
                    "label": "mug",
                }
            ],
        }
        rendered = {
            "print_files": [
                {
                    "export_path": "https://cdn.example.invalid/render.webp",
                    "export_format": "webp",
                }
            ],
            "render_uuid": "9c4d1e78-3b52-4f09-a6d1-7e2b8c5f3042",
        }
        mock_api.get("/api/v1/library/templates").mock(return_value=httpx.Response(200, json=PAGE))
        mock_api.get(f"/api/v1/library/templates/{SLUG}").mock(
            return_value=httpx.Response(200, json=DETAIL)
        )
        mock_api.post("/api/v1/photo-mockups").mock(
            return_value=httpx.Response(200, json={"success": True, "data": created})
        )
        mock_api.post(f"/api/v1/photo-mockups/{created['mockup_id']}/render").mock(
            return_value=httpx.Response(200, json={"success": True, "data": rendered})
        )

        with SudoMock(api_key=TEST_API_KEY, base_url=TEST_BASE_URL) as client:
            page = client.ready_made_mockups.search(
                search="coffee mug", category="drinkware", limit=5
            )
            template = client.ready_made_mockups.get_template(page.templates[0].slug)
            view = template.mockups[0]
            mockup = client.photo_mockups.create(source_url=view.source_url)
            render = client.photo_mockups.render(
                mockup_uuid=mockup.mockup_id,
                print_areas=[
                    {
                        "surface_uuid": mockup.surfaces[0].surface_uuid,
                        "artwork_url": "https://example.com/artwork.png",
                        "placement": {"coverage": 60},
                    }
                ],
            )

        assert render.url == "https://cdn.example.invalid/render.webp"
