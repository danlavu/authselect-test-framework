"""SSSD predefined well-known topologies."""

from __future__ import annotations

from enum import unique
from typing import final

from pytest_mh import KnownTopologyBase, KnownTopologyGroupBase, Topology, TopologyDomain

from .config import AuthselectTopologyMark
from .topology_controllers import (
    LocalTopologyController,
    SSSTopologyController,
    WinbindTopologyController,
)

__all__ = [
    "KnownTopology",
]


@final
@unique
class KnownTopology(KnownTopologyBase):
    """
    Well-known topologies that can be given to ``pytest.mark.topology``
    directly. It is expected to use these values in favor of providing
    custom marker values.

    .. code-block:: python
        :caption: Example usage

        @pytest.mark.topology(KnownTopology.SSS)
        def test_authselect(client: Client, ldap: LDAP):
            assert True
    """

    LocalProfile = AuthselectTopologyMark(
        name="local",
        topology=Topology(TopologyDomain("authselect", client=1)),
        controller=LocalTopologyController(),
        fixtures=dict(client="authselect.client[0]"),
    )
    """
    .. topology-mark:: KnownTopology.Local
    """

    SSSProfile = AuthselectTopologyMark(
        name="sss",
        topology=Topology(TopologyDomain("authselect", client=1, ipa=1)),
        controller=SSSTopologyController(),
        domains={"test": "authselect.sss[0]"},
        fixtures=dict(client="authselect.client[0]", ipa="authselect.ipa[0]", provider="authselect.ipa[0]"),
    )
    """
    .. topology-mark:: KnownTopology.SSS
    """

    WinbindProfile = AuthselectTopologyMark(
        name="winbind",
        topology=Topology(TopologyDomain("authselect", client=1, samba=1)),
        controller=WinbindTopologyController(),
        domains={"test": "authselect.winbind[0]"},
        fixtures=dict(client="authselect.client[0]", samba="authselect.samba[0]", provider="authselect.winbind[0]"),
    )
    """
    .. topology-mark:: KnownTopology.Winbind
    """


class KnownTopologyGroup(KnownTopologyGroupBase):
    """
    Groups of well-known topologies that can be given to ``pytest.mark.topology``
    directly. It is expected to use these values in favor of providing
    custom marker values.

    The test is parametrized and runs multiple times, once per each topology.

    .. code-block:: python
        :caption: Example usage (runs on AD, IPA, LDAP and Samba topology)

        @pytest.mark.topology(KnownTopologyGroup.AnyProvider)
        def test_ldap(client: Client, provider: GenericProvider):
            assert True
    """

    AnyProfile = [KnownTopology.LocalProfile, KnownTopology.SSSProfile,  KnownTopology.WinbindProfile]
    """
    .. topology-mark:: KnownTopologyGroup.AnyProfile
    """
