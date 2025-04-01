"""Client multihost role."""

from __future__ import annotations

from pytest_mh.conn import ProcessResult

from ..hosts.client import ClientHost
from ..topology import AuthselectTopologyMark
from ..utils.local_users import (
    LocalGroup,
    LocalNetgroup,
    LocalSudoAlias,
    LocalSudoAliasKind,
    LocalSudoRule,
    LocalUser,
    LocalUsersUtils,
)
from ..utils.sssd import SSSDUtils
from .base import BaseLinuxRole

__all__ = [
    "Client",
]


class Client(BaseLinuxRole[ClientHost]):
    """
    SSSD Client role.

    Provides unified Python API for managing and testing SSSD.

    .. code-block:: python
        :caption: Starting SSSD

        @pytest.mark.topology(Profile.Local)
        def test_example(client: Client):
            client.sssd.start()

    .. note::

        The role object is instantiated automatically as a dynamic pytest
        fixture by the multihost plugin. You should not create the object
        manually.
    """

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)

        self.sssd: SSSDUtils = SSSDUtils(self.host, self.fs, self.svc, self.authselect, load_config=False)
        """
        Managing and configuring SSSD.
        """

        self.local: LocalUsersUtils = LocalUsersUtils(self.host, self.fs, client=self)
        """
        Managing local users and groups.
        """

    def setup(self) -> None:
        """
        Called before execution of each test.

        Setup client host:

        #. stop sssd
        #. clear sssd cache, logs and configuration
        #. import implicit domains from topology marker
        """
        super().setup()
        self.sssd.stop()
        self.sssd.clear(db=True, memcache=True, logs=True, config=True)

        if self.mh.data.topology_mark is not None:
            if not isinstance(self.mh.data.topology_mark, AuthselectTopologyMark):
                raise ValueError("Multihost data does not have AuthselectTopologyMark")

            for domain, path in self.mh.data.topology_mark.domains.items():
                role = self.mh._lookup(path)
                if isinstance(role, list):
                    raise ValueError("List is not expected")

                self.sssd.import_domain(domain, role)

    def sss_ssh_knownhosts(self, *args: str) -> ProcessResult:
        """
        Execute sss_ssh_knownhosts.

        :param `*args`: Command arguments.
        :type `*args`: str
        :return: Command result.
        :rtype: ProcessResult
        """
        return self.host.conn.exec(["sss_ssh_knownhosts", *args])

    def sss_ssh_authorizedkeys(self, *args: str) -> ProcessResult:
        """
        Execute sss_ssh_authorizedkeys.

        :param `*args`: Command arguments.
        :type `*args`: str
        :return: Command result.
        :rtype: ProcessResult
        """
        return self.host.conn.exec(["sss_ssh_authorizedkeys", *args], raise_on_error=False)

    def user(self, name: str) -> LocalUser:
        """
        Get user object.

        :param name: User name.
        :type name: str
        :return: New user object.
        :rtype: LocalUser
        """

        return LocalUser(self.local, name)

    def group(self, name: str) -> LocalGroup:
        """
        Get group object.
        :param name: Group name.
        :type name: str
        :return: New group object.
        :rtype: LocalGroup
        """

        return LocalGroup(self.local, name)

    def sudoalias(self, name: str, kind: LocalSudoAliasKind) -> LocalSudoAlias:
        """
        Get sudo alias object.
        :param name: Sudo alias name.
        :type name: str
        :param kind: Alias kind.
        :type kind: LocalSudoAliasKind
        :return: New sudo alias object.
        :rtype: LocalSudoAlias
        """

        return self.local.sudoalias(name, kind)

    def netgroup(self, name: str) -> LocalNetgroup:
        """
        Get netgroup object.
        :param name: Netgroup name.
        :type name: str
        :return: New netgroup object.
        :rtype: LocalNetgroup
        """

        return self.local.netgroup(name)

    def sudorule(self, name: str) -> LocalSudoRule:
        """
        Get sudo rule object.
        :param name: Sudo rule name.
        :type name: str
        :return: New sudo rule object.
        :rtype: LocalSudoRule
        """

        return self.local.sudorule(name)
