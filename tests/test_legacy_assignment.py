"""Earlier accessor names stay assignable so existing test doubles keep working.

Assignment lands on the name it was written to: ``c.ai`` reads back the double
and ``c.photo_mockups`` stays the resource the client was built with. Writing
one name does not move the other, so a suite that saves and restores an
accessor leaves the client where it found it.
"""

import warnings

import sudomock


class _Stub:
    def __init__(self):
        self.calls = []


def _read(client, name):
    """Read a deprecated accessor without the warning reaching the report."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        return getattr(client, name)


def test_legacy_ai_assignment_still_works():
    c = sudomock.SudoMock(api_key="sm_test")
    current = c.photo_mockups
    stub = _Stub()
    c.ai = stub  # must not raise
    assert _read(c, "ai") is stub
    assert c.photo_mockups is current


def test_legacy_mockups_assignment_still_works():
    c = sudomock.SudoMock(api_key="sm_test")
    current = c.psd_mockups
    stub = _Stub()
    c.mockups = stub
    assert _read(c, "mockups") is stub
    assert c.psd_mockups is current


def test_async_legacy_assignment_still_works():
    c = sudomock.AsyncSudoMock(api_key="sm_test")
    photo, psd = c.photo_mockups, c.psd_mockups
    stub = _Stub()
    c.ai = stub
    assert _read(c, "ai") is stub
    assert c.photo_mockups is photo
    c.mockups = stub
    assert _read(c, "mockups") is stub
    assert c.psd_mockups is psd
