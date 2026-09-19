"""Earlier accessor names stay assignable so existing test doubles keep working."""

import sudomock


class _Stub:
    def __init__(self):
        self.calls = []


def test_legacy_ai_assignment_still_works():
    c = sudomock.SudoMock(api_key="sm_test")
    stub = _Stub()
    c.ai = stub  # must not raise
    assert c.photo_mockups is stub


def test_legacy_mockups_assignment_still_works():
    c = sudomock.SudoMock(api_key="sm_test")
    stub = _Stub()
    c.mockups = stub
    assert c.psd_mockups is stub


def test_async_legacy_assignment_still_works():
    c = sudomock.AsyncSudoMock(api_key="sm_test")
    stub = _Stub()
    c.ai = stub
    assert c.photo_mockups is stub
    c.mockups = stub
    assert c.psd_mockups is stub
