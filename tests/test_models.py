"""Tests for Pydantic response models."""

from __future__ import annotations

import pytest

from sudomock.models import (
    Account,
    AccountInfo,
    AIRender,
    ApiKeyInfo,
    Job,
    JobAccepted,
    Mockup,
    MockupList,
    PrintFile,
    Render,
    Size,
    SmartObject,
    Subscription,
    Usage,
    VideoOptions,
    WebhookDelivery,
    WebhookEndpoint,
)


class TestAccount:
    def test_parse_full(self) -> None:
        acct = Account(
            uuid="abc-123",
            email="dev@example.com",
            name="Acme",
            created_at="2025-06-15T10:30:00Z",
        )
        assert acct.uuid == "abc-123"
        assert acct.email == "dev@example.com"
        assert acct.name == "Acme"

    def test_name_optional(self) -> None:
        acct = Account(uuid="x", email="a@b.com", created_at="2025-01-01T00:00:00Z")
        assert acct.name is None

    def test_extra_fields_allowed(self) -> None:
        """New API fields should not break the SDK."""
        acct = Account(
            uuid="x",
            email="a@b.com",
            created_at="2025-01-01T00:00:00Z",
            new_field="surprise",
        )
        assert acct.uuid == "x"


class TestSubscription:
    def test_parse(self) -> None:
        sub = Subscription(plan="pro", status="active")
        assert sub.plan == "pro"
        assert sub.cancel_at_period_end is False


class TestUsage:
    def test_credits_remaining(self) -> None:
        usage = Usage(
            credits_used_this_month=100,
            credits_limit=1000,
            credits_remaining=900,
            billing_period_start="2026-01-01T00:00:00Z",
            billing_period_end="2026-02-01T00:00:00Z",
        )
        assert usage.credits_remaining == 900


class TestAccountInfo:
    def test_full_parse(self) -> None:
        info = AccountInfo(
            account=Account(uuid="u1", email="a@b.com", created_at="2025-01-01T00:00:00Z"),
            subscription=Subscription(plan="free", status="active"),
            usage=Usage(
                credits_used_this_month=0,
                credits_limit=100,
                credits_remaining=100,
                billing_period_start="2026-01-01T00:00:00Z",
                billing_period_end="2026-02-01T00:00:00Z",
            ),
            api_key=ApiKeyInfo(
                name="Test",
                created_at="2025-01-01T00:00:00Z",
                total_requests=0,
            ),
        )
        assert info.account.uuid == "u1"
        assert info.subscription.plan == "free"


class TestSmartObject:
    def test_minimal(self) -> None:
        so = SmartObject(uuid="so-1")
        assert so.uuid == "so-1"
        assert so.name is None

    def test_with_size(self) -> None:
        so = SmartObject(uuid="so-1", size=Size(width=800, height=600))
        assert so.size is not None
        assert so.size.width == 800


class TestMockup:
    def test_parse(self) -> None:
        m = Mockup(
            uuid="m-1",
            name="T-Shirt",
            smart_objects=[SmartObject(uuid="so-1")],
            width=2000,
            height=2400,
        )
        assert m.name == "T-Shirt"
        assert len(m.smart_objects) == 1

    def test_empty_smart_objects(self) -> None:
        m = Mockup(uuid="m-1", name="Empty")
        assert m.smart_objects == []

    def test_thumbnail_field(self) -> None:
        # The API returns the main 720px preview under `thumbnail` (upload /
        # list / get), which is now a typed field.
        m = Mockup.model_validate(
            {
                "uuid": "m-1",
                "name": "T-Shirt",
                "thumbnail": "https://cdn.sudomock.com/thumbnails/m-1_720.webp",
            }
        )
        assert m.thumbnail == "https://cdn.sudomock.com/thumbnails/m-1_720.webp"
        assert m.thumbnail_url is None


class TestMockupList:
    def test_pagination(self) -> None:
        ml = MockupList(
            mockups=[Mockup(uuid="m-1", name="A")],
            total=50,
            limit=20,
            offset=0,
        )
        assert ml.total == 50
        assert ml.limit == 20
        assert len(ml.mockups) == 1


class TestPrintFile:
    def test_url_property(self) -> None:
        pf = PrintFile(
            export_path="https://cdn.sudomock.com/render.webp",
            smart_object_uuid="so-1",
        )
        assert pf.url == "https://cdn.sudomock.com/render.webp"


class TestRender:
    def test_url_shortcut(self) -> None:
        r = Render(
            print_files=[
                PrintFile(
                    export_path="https://cdn.sudomock.com/r1.webp",
                    smart_object_uuid="so-1",
                )
            ]
        )
        assert r.url == "https://cdn.sudomock.com/r1.webp"

    def test_url_empty_raises(self) -> None:
        r = Render(print_files=[])
        with pytest.raises(ValueError, match="no print files"):
            _ = r.url


class TestAIRender:
    def test_url_shortcut(self) -> None:
        r = AIRender(
            print_files=[
                PrintFile(
                    export_path="https://cdn.sudomock.com/ai.webp",
                    smart_object_uuid="auto",
                )
            ]
        )
        assert r.url == "https://cdn.sudomock.com/ai.webp"

    def test_url_empty_raises(self) -> None:
        r = AIRender(print_files=[])
        with pytest.raises(ValueError, match="no print files"):
            _ = r.url


class TestJobAccepted:
    def test_parse(self) -> None:
        j = JobAccepted(
            job_id="r-1",
            kind="render",
            status="queued",
            status_url="/api/v1/jobs/r-1",
        )
        assert j.job_id == "r-1"
        assert j.status_url == "/api/v1/jobs/r-1"

    def test_minimal(self) -> None:
        j = JobAccepted(job_id="r-1")
        assert j.job_id == "r-1"
        assert j.status is None


class TestJob:
    def test_queued_not_terminal(self) -> None:
        job = Job(status="queued")
        assert not job.is_terminal
        assert not job.succeeded
        assert not job.failed

    def test_running_not_terminal(self) -> None:
        assert not Job(status="running").is_terminal

    def test_succeeded(self) -> None:
        job = Job(
            status="succeeded",
            result_url="https://cdn.sudomock.com/r.webp",
            credits_charged=1,
        )
        assert job.is_terminal
        assert job.succeeded
        assert job.url == "https://cdn.sudomock.com/r.webp"
        assert job.credits_charged == 1
        assert job.payg is None

    def test_payg_nested_cost(self) -> None:
        """PAYG jobs surface the real cost in a nested payg object."""
        job = Job(
            job_id="payg-1",
            kind="render",
            status="succeeded",
            result_url="https://cdn.sudomock.com/r.webp",
            credits_charged=2,
            payg={"credits": 2, "unit_price": 0.0035, "cost": 0.007},
        )
        assert job.credits_charged == 2
        assert job.payg is not None
        assert job.payg.credits == 2
        assert job.payg.unit_price == 0.0035
        assert job.payg.cost == 0.007

    def test_failed(self) -> None:
        job = Job(status="failed", error="boom")
        assert job.is_terminal
        assert job.failed
        assert job.error == "boom"

    def test_url_without_result_raises(self) -> None:
        job = Job(status="running")
        with pytest.raises(ValueError, match="no result_url"):
            _ = job.url


class TestVideoOptions:
    def test_defaults(self) -> None:
        v = VideoOptions(duration_seconds=5)
        assert v.duration_seconds == 5
        assert v.audio is False
        assert v.advanced_model is None


class TestWebhookModels:
    def test_endpoint(self) -> None:
        wh = WebhookEndpoint(
            id="wh-1",
            url="https://x.com/wh",
            event_types=["render.succeeded"],
        )
        assert wh.id == "wh-1"
        assert wh.enabled is True
        assert wh.event_types == ["render.succeeded"]

    def test_delivery(self) -> None:
        d = WebhookDelivery(
            id="d-1",
            endpoint_id="wh-1",
            job_uuid="job-1",
            event_type="render.succeeded",
            status="delivered",
            http_status=200,
            attempt=0,
        )
        assert d.id == "d-1"
        assert d.http_status == 200
        assert d.attempt == 0
