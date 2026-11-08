"""Library folders on both clients, and folder_uuid on the mockup surfaces."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import httpx
import pytest

from sudomock import AsyncSudoMock, SudoMock
from sudomock.models import Folder, FolderDelete, FolderDetail, FolderList, FolderMove

from .conftest import TEST_API_KEY, TEST_BASE_URL

if TYPE_CHECKING:
    import respx

FOLDER_ID = "c4f1a7d2-3b85-4e60-9a1f-7d2c5e8b4061"
CHILD_ID = "2f8b4a17-5c93-4e21-b7d0-61a3c8e5f920"
PARENT_ID = "9e3b6c14-27af-4d58-b0e1-5c8a2f9d7340"
MOCKUP_ID = "8f2c1d90-6b4e-4a37-9e55-0d1c7a3f21b8"
PHOTO_ID = "7d1e4c09-2a68-4f35-9b4e-3c0f8a2d6517"

FOLDER = {
    "uuid": FOLDER_ID,
    "name": "Frames",
    "parent_uuid": None,
    "folder_count": 1,
    "psd_mockup_count": 12,
    "photo_mockup_count": 4,
    "created_at": "2026-11-08T10:00:00Z",
    "updated_at": "2026-11-08T10:00:00Z",
    "unexpected": "dropped",
}

FOLDER_LIST = {"success": True, "data": {"folders": [FOLDER], "total": 1, "limit": 20, "offset": 0}}
FOLDER_ONE = {"success": True, "data": FOLDER}
FOLDER_FULL = {
    "success": True,
    "data": {
        **FOLDER,
        "path": [{"uuid": PARENT_ID, "name": "My mockups"}],
        "total_folder_count": 4,
        "total_psd_mockup_count": 31,
        "total_photo_mockup_count": 8,
    },
}
FOLDER_GONE = {
    "success": True,
    "data": {
        "deleted": FOLDER_ID,
        "deleted_folders": 4,
        "deleted_psd_mockups": 12,
        "deleted_photo_mockups": 3,
        "unexpected": "dropped",
    },
}
FOLDER_MOVED = {
    "success": True,
    "data": {
        "target_folder_uuid": FOLDER_ID,
        "moved_psd_mockups": 1,
        "moved_photo_mockups": 0,
        "moved_folders": 0,
        "unexpected": "dropped",
    },
}


@pytest.fixture()
def client() -> SudoMock:
    return SudoMock(api_key=TEST_API_KEY, base_url=TEST_BASE_URL, max_retries=1)


class TestFolderList:
    def test_list_pages_and_drops_undocumented_fields(
        self, client: SudoMock, mock_api: respx.MockRouter
    ) -> None:
        route = mock_api.get("/api/v1/folders").mock(
            return_value=httpx.Response(200, json=FOLDER_LIST)
        )

        result = client.folders.list(parent_uuid="root", limit=50)

        assert isinstance(result, FolderList)
        assert result.total == 1
        assert result.folders[0].psd_mockup_count == 12
        assert result.folders[0].parent_uuid is None
        assert not hasattr(result.folders[0], "unexpected")
        params = route.calls.last.request.url.params
        assert params["parent_uuid"] == "root"
        assert params["limit"] == "50"
        assert "offset" not in params

    def test_no_parent_means_every_folder(
        self, client: SudoMock, mock_api: respx.MockRouter
    ) -> None:
        route = mock_api.get("/api/v1/folders").mock(
            return_value=httpx.Response(200, json=FOLDER_LIST)
        )

        client.folders.list()

        assert "parent_uuid" not in route.calls.last.request.url.params


class TestFolderCreate:
    def test_create_sends_the_name_alone_then_the_parent(
        self, client: SudoMock, mock_api: respx.MockRouter
    ) -> None:
        route = mock_api.post("/api/v1/folders").mock(
            return_value=httpx.Response(201, json=FOLDER_ONE)
        )

        folder = client.folders.create(name="Frames")

        assert isinstance(folder, Folder)
        assert folder.name == "Frames"
        assert not hasattr(folder, "unexpected")
        assert json.loads(route.calls.last.request.content) == {"name": "Frames"}

        client.folders.create(name="8x10", parent_uuid=FOLDER_ID)
        assert json.loads(route.calls.last.request.content) == {
            "name": "8x10",
            "parent_uuid": FOLDER_ID,
        }

    def test_a_blank_name_never_reaches_the_api(
        self, client: SudoMock, mock_api: respx.MockRouter
    ) -> None:
        route = mock_api.post("/api/v1/folders").mock(
            return_value=httpx.Response(201, json=FOLDER_ONE)
        )

        with pytest.raises(ValueError, match="blank"):
            client.folders.create(name="   ")

        assert not route.called


class TestFolderGet:
    def test_get_returns_the_trail_and_the_counts_a_delete_would_remove(
        self, client: SudoMock, mock_api: respx.MockRouter
    ) -> None:
        mock_api.get(f"/api/v1/folders/{FOLDER_ID}").mock(
            return_value=httpx.Response(200, json=FOLDER_FULL)
        )

        folder = client.folders.get(FOLDER_ID)

        assert isinstance(folder, FolderDetail)
        assert [entry.name for entry in folder.path] == ["My mockups"]
        assert folder.total_psd_mockup_count == 31
        assert not hasattr(folder, "unexpected")


class TestFolderUpdate:
    def test_a_field_left_out_differs_from_one_sent_as_none(
        self, client: SudoMock, mock_api: respx.MockRouter
    ) -> None:
        route = mock_api.patch(f"/api/v1/folders/{FOLDER_ID}").mock(
            return_value=httpx.Response(200, json=FOLDER_FULL)
        )

        client.folders.update(FOLDER_ID, name="Frames 8x10")
        assert json.loads(route.calls.last.request.content) == {"name": "Frames 8x10"}

        # None is the top of the library, not "leave it where it is".
        client.folders.update(FOLDER_ID, parent_uuid=None)
        assert json.loads(route.calls.last.request.content) == {"parent_uuid": None}

        client.folders.update(FOLDER_ID, name="Frames", parent_uuid=CHILD_ID)
        assert json.loads(route.calls.last.request.content) == {
            "name": "Frames",
            "parent_uuid": CHILD_ID,
        }

    def test_an_update_that_changes_nothing_never_reaches_the_api(
        self, client: SudoMock, mock_api: respx.MockRouter
    ) -> None:
        route = mock_api.patch(f"/api/v1/folders/{FOLDER_ID}").mock(
            return_value=httpx.Response(200, json=FOLDER_FULL)
        )

        with pytest.raises(ValueError, match="parent_uuid"):
            client.folders.update(FOLDER_ID)

        assert not route.called


class TestFolderDelete:
    def test_delete_reports_what_went(self, client: SudoMock, mock_api: respx.MockRouter) -> None:
        route = mock_api.delete(f"/api/v1/folders/{FOLDER_ID}").mock(
            return_value=httpx.Response(200, json=FOLDER_GONE)
        )

        gone = client.folders.delete(FOLDER_ID, recursive=True)

        assert isinstance(gone, FolderDelete)
        assert gone.deleted_psd_mockups == 12
        assert gone.deleted_folders == 4
        assert not hasattr(gone, "unexpected")
        assert route.calls.last.request.url.params["recursive"] == "true"

    def test_a_uuid_stays_one_path_segment(
        self, client: SudoMock, mock_api: respx.MockRouter
    ) -> None:
        """An id an application took from its own end user cannot turn on
        recursive, which would delete the folder's whole contents."""
        route = mock_api.delete(path__startswith="/api/v1/folders/").mock(
            return_value=httpx.Response(200, json=FOLDER_GONE)
        )

        client.folders.delete(f"{FOLDER_ID}?recursive=true")

        assert route.calls.last.request.url.params["recursive"] == "false"


class TestFolderMove:
    def test_move_sends_every_list_and_reads_no_target_as_the_top(
        self, client: SudoMock, mock_api: respx.MockRouter
    ) -> None:
        route = mock_api.post("/api/v1/folders/move").mock(
            return_value=httpx.Response(200, json=FOLDER_MOVED)
        )

        moved = client.folders.move(target_folder_uuid=FOLDER_ID, psd_mockup_uuids=[MOCKUP_ID])

        assert isinstance(moved, FolderMove)
        assert moved.moved_psd_mockups == 1
        assert not hasattr(moved, "unexpected")
        assert json.loads(route.calls.last.request.content) == {
            "target_folder_uuid": FOLDER_ID,
            "psd_mockup_uuids": [MOCKUP_ID],
            "photo_mockup_uuids": [],
            "folder_uuids": [],
        }

        client.folders.move(folder_uuids=[CHILD_ID])
        assert json.loads(route.calls.last.request.content)["target_folder_uuid"] is None

    def test_a_move_that_names_nothing_or_too_much_never_reaches_the_api(
        self, client: SudoMock, mock_api: respx.MockRouter
    ) -> None:
        route = mock_api.post("/api/v1/folders/move").mock(
            return_value=httpx.Response(200, json=FOLDER_MOVED)
        )

        with pytest.raises(ValueError, match="at least one"):
            client.folders.move(target_folder_uuid=FOLDER_ID)

        with pytest.raises(ValueError, match="at most 500"):
            client.folders.move(psd_mockup_uuids=[MOCKUP_ID] * 501)

        assert not route.called


class TestFolderUuidOnMockups:
    def test_both_lists_filter_and_report_where_each_mockup_sits(
        self, client: SudoMock, mock_api: respx.MockRouter
    ) -> None:
        psd = mock_api.get("/api/v1/psd-mockups").mock(
            return_value=httpx.Response(
                200,
                json={
                    "success": True,
                    "data": {
                        "mockups": [
                            {"uuid": MOCKUP_ID, "name": "Oak frame 8x10", "folder_uuid": FOLDER_ID}
                        ],
                        "total": 1,
                        "limit": 20,
                        "offset": 0,
                    },
                },
            )
        )
        photo = mock_api.get("/api/v1/photo-mockups").mock(
            return_value=httpx.Response(
                200,
                json={
                    "success": True,
                    "data": [
                        {
                            "mockup_id": PHOTO_ID,
                            "name": "Oak frame on a wall",
                            "folder_uuid": None,
                            "customizable": False,
                        }
                    ],
                    "total": 1,
                    "limit": 20,
                    "offset": 0,
                },
            )
        )

        psd_page = client.psd_mockups.list(folder_uuid=FOLDER_ID)
        assert psd.calls.last.request.url.params["folder_uuid"] == FOLDER_ID
        assert psd_page.mockups[0].folder_uuid == FOLDER_ID

        photo_page = client.photo_mockups.list(folder_uuid="root")
        assert photo.calls.last.request.url.params["folder_uuid"] == "root"
        assert photo_page.mockups[0].folder_uuid is None

        client.psd_mockups.list()
        assert "folder_uuid" not in psd.calls.last.request.url.params

    def test_update_moves_one_mockup_and_tells_none_from_left_out(
        self, client: SudoMock, mock_api: respx.MockRouter
    ) -> None:
        route = mock_api.patch(f"/api/v1/psd-mockups/{MOCKUP_ID}").mock(
            return_value=httpx.Response(
                200,
                json={
                    "success": True,
                    "data": {"uuid": MOCKUP_ID, "name": "Oak frame 8x10", "folder_uuid": None},
                },
            )
        )

        client.psd_mockups.update(MOCKUP_ID, name="Renamed")
        assert json.loads(route.calls.last.request.content) == {"name": "Renamed"}

        moved = client.psd_mockups.update(MOCKUP_ID, folder_uuid=None)
        assert json.loads(route.calls.last.request.content) == {"folder_uuid": None}
        assert moved.folder_uuid is None

        with pytest.raises(ValueError, match="folder_uuid"):
            client.psd_mockups.update(MOCKUP_ID)

    def test_a_new_mockup_lands_in_a_folder_on_upload_and_on_create(
        self, client: SudoMock, mock_api: respx.MockRouter
    ) -> None:
        upload = mock_api.post("/api/v1/psd/upload").mock(
            return_value=httpx.Response(
                200,
                json={
                    "success": True,
                    "data": {
                        "uuid": MOCKUP_ID,
                        "name": "Oak frame 8x10",
                        "folder_uuid": FOLDER_ID,
                    },
                },
            )
        )
        create = mock_api.post("/api/v1/photo-mockups").mock(
            return_value=httpx.Response(
                201,
                json={
                    "success": True,
                    "data": {
                        "mockup_id": PHOTO_ID,
                        "name": "Oak frame on a wall",
                        "folder_uuid": FOLDER_ID,
                        "customizable": False,
                    },
                },
            )
        )

        uploaded = client.psd.upload(
            url="https://example.com/frame.psd", name="Oak frame 8x10", folder_uuid=FOLDER_ID
        )
        assert json.loads(upload.calls.last.request.content)["folder_uuid"] == FOLDER_ID
        assert uploaded.folder_uuid == FOLDER_ID

        created = client.photo_mockups.create(
            source_url="https://example.com/frame-photo.jpg", folder_uuid=FOLDER_ID
        )
        assert json.loads(create.calls.last.request.content)["folder_uuid"] == FOLDER_ID
        assert created.folder_uuid == FOLDER_ID


class TestAsyncFolders:
    async def test_the_async_client_serves_the_same_folder_calls(
        self, mock_api: respx.MockRouter
    ) -> None:
        mock_api.get("/api/v1/folders").mock(return_value=httpx.Response(200, json=FOLDER_LIST))
        move = mock_api.post("/api/v1/folders/move").mock(
            return_value=httpx.Response(200, json=FOLDER_MOVED)
        )
        patch = mock_api.patch(f"/api/v1/folders/{FOLDER_ID}").mock(
            return_value=httpx.Response(200, json=FOLDER_FULL)
        )

        async with AsyncSudoMock(
            api_key=TEST_API_KEY, base_url=TEST_BASE_URL, max_retries=1
        ) as client:
            page = await client.folders.list(parent_uuid="root")
            assert page.folders[0].name == "Frames"

            await client.folders.update(FOLDER_ID, parent_uuid=None)
            assert json.loads(patch.calls.last.request.content) == {"parent_uuid": None}

            moved = await client.folders.move(psd_mockup_uuids=[MOCKUP_ID])
            assert moved.moved_psd_mockups == 1
            assert json.loads(move.calls.last.request.content)["target_folder_uuid"] is None

            with pytest.raises(ValueError, match="at least one"):
                await client.folders.move()
