"""Framework smoke tests that do not require remote hosts."""

from __future__ import annotations

from authselect_test_framework.topology import Profile


def test_profiles_are_defined() -> None:
    assert Profile.Local.value.name == "local"
    assert Profile.SSSD.value.name == "sssd"
    assert Profile.Winbind.value.name == "winbind"
