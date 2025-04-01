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

__all__ = ["KnownTopology", "KnownTopologyGroup"]


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
        def test_authselect(client: Client, provider: IPA):
            assert True
    """

    Local = AuthselectTopologyMark(
        name="local",
        topology=Topology(TopologyDomain("sssd", client=1)),
        controller=LocalTopologyController(),
        fixtures=dict(client="sssd.client[0]"),
    )
    """
    .. topology-mark:: KnownTopology.Local
    """

    SSS = AuthselectTopologyMark(
        name="sss",
        topology=Topology(TopologyDomain("sssd", client=1, ipa=1)),
        controller=SSSTopologyController(),
        domains={"test": "sssd.ipa[0]"},
        fixtures=dict(client="sssd.client[0]", ipa="sssd.ipa[0]", provider="sssd.ipa[0]"),
    )
    """
    .. topology-mark:: KnownTopology.SSS
    """

    Winbind = AuthselectTopologyMark(
        name="winbind",
        topology=Topology(TopologyDomain("sssd", client=1, samba=1)),
        controller=WinbindTopologyController(),
        domains={"test": "sssd.samba[0]"},
        fixtures=dict(client="sssd.client[0]", samba="sssd.samba[0]", provider="sssd.samba[0]"),
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

        @pytest.mark.topology(KnownTopologyGroup.Any)
        def test_ldap(client: Client, provider: GenericProvider):
            assert True
    """

    Any = [KnownTopology.Local, KnownTopology.SSS, KnownTopology.Winbind]
    """
    .. topology-mark:: KnownTopologyGroup.Any
    """
