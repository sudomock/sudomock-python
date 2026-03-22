"""Tests for Pydantic response models."""

from __future__ import annotations

import pytest

from sudomock.models import (
    Account,
    AccountInfo,
    AIRender,
    ApiKeyInfo,
    Mockup,
    MockupList,
    PrintFile,
    Render,
    Size,
    SmartObject,
    Subscription,
    Usage,
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
