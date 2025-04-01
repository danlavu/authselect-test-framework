"""Authselect predefined well-known topologies."""

from __future__ import annotations

from enum import unique
from typing import final

from pytest_mh import KnownTopologyBase, Topology, TopologyDomain

from .config import AuthselectTopologyMark
from .controllers import (
    LocalController,
    SSSDController,
    WinbindController,
)

__all__ = [
    "Profile",
]


@final
@unique
class Profile(KnownTopologyBase):
    Local = AuthselectTopologyMark(
        name="local",
        topology=Topology(TopologyDomain("sssd", client=1)),
        controller=LocalController(),
        fixtures=dict(client="sssd.client[0]"),
    )

    SSSD = AuthselectTopologyMark(
        name="sssd",
        topology=Topology(TopologyDomain("sssd", client=1, ipa=1)),
        controller=SSSDController(),
        domains=dict(test="sssd.ipa[0]"),
        fixtures=dict(client="sssd.client[0]", ipa="sssd.ipa[0]", server="sssd.ipa[0]"),
    )

    Winbind = AuthselectTopologyMark(
        name="winbind",
        topology=Topology(TopologyDomain("sssd", client=1, samba=1)),
        controller=WinbindController(),
        fixtures=dict(client="sssd.client[0]", samba="sssd.samba[0]", server="sssd.samba[0]"),
    )
