"""Samba multihost role."""

from __future__ import annotations

import base64
from datetime import datetime
from typing import Any

import ldap
import ldap.modlist
from pytest_mh.cli import CLIBuilderArgs
from pytest_mh.conn import ProcessResult

from ..hosts.samba import SambaHost
from ..misc import attrs_parse, ip_to_ptr, ip_version, to_list_of_strings
from ..utils.ldap import LDAPRecordAttributes
from .base import BaseLinuxLDAPRole, BaseObject, DeleteAttribute
from .generic import (
    GenericComputer,
    GenericDNSServer,
    GenericDNSZone,
    GenericGroup,
    GenericOrganizationalUnit,
    GenericPasswordPolicy,
    GenericSite,
    GenericSudoRule,
    GenericUser,
    GroupMemberField,
    ProtocolName,
    SudoRuleCommandField,
    SudoRuleHostField,
    SudoRuleRunAsGroupField,
    SudoRuleRunAsUserField,
    SudoRuleUserField,
)

__all__ = [
    "Samba",
    "SambaObject",
    "SambaComputer",
    "SambaPasswordPolicy",
    "SambaUser",
    "SambaGroup",
    "SambaOrganizationalUnit",
    "SambaSudoRule",
    "SambaDNSServer",
    "SambaDNSZone",
]


class Samba(BaseLinuxLDAPRole[SambaHost]):
    """
    Samba role.

    Provides unified Python API for managing objects in the Samba domain controller.

    .. code-block:: python
        :caption: Creating user and group

        @pytest.mark.topology(Profile.Winbind)
        def test_example(samba: Samba):
            u = samba.user('tuser').add()
            g = samba.group('tgroup').add()
            g.add_member(u)

    .. note::

        The role object is instantiated automatically as a dynamic pytest
        fixture by the multihost plugin. You should not create the object
        manually.
    """

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)

        self.domain: str = self.host.domain
        """
        Samba domain name.
        """

        self.realm: str = self.host.realm
        """
        Kerberos realm.
        """

        self._password_policy: SambaPasswordPolicy = SambaPasswordPolicy(self)
        """
        Samba password policy.
        """

        self.name: str = "ad"
        """
        Provider name, samba is a community developed AD clone.
        SSSD does not have dedicated samba provider, thus uses 'ad'.
        """

        self.server: str = self.host.hostname
        """
        Generic server name.
        """

    @property
    def password_policy(self) -> SambaPasswordPolicy:
        """
        Domain password policy management.

        .. code-block:: python
            :caption: Example usage

            @pytest.mark.topology(Profile.Winbind)
            def test_example(client: Client, samba: Samba):
                # Enable password complexity
                samba.password_policy.complexity(enable=True)

                # Set 3 login attempts and 30 lockout duration
                samba.password_policy.lockout(attempts=3, duration=30)
        """
        return self._password_policy

    @property
    def naming_context(self) -> str:
        """
        Samba naming context.

        :rtype: str
        """
        return self.host.naming_context

    def fqn(self, name: str) -> str:
        """
        Return fully qualified name in form name@domain.

        :param name: Username.
        :type name: str
        :return: Fully qualified name.
        :rtype: str
        """
        return f"{name}@{self.domain}"

    def user(self, name: str) -> SambaUser:
        """
        Get user object.

        .. code-block:: python
            :caption: Example usage

            @pytest.mark.topology(Profile.Winbind)
            def test_example(client: Client, samba: Samba):
                # Create user
                samba.user('user-1').add()

                # Start SSSD
                client.sssd.start()

                # Call `id user-1` and assert the result
                result = client.tools.id('user-1')
                assert result is not None
                assert result.user.name == 'user-1'
                assert result.group.name == 'domain users'

        :param name: Username.
        :type name: str
        :return: New user object.
        :rtype: SambaUser
        """
        return SambaUser(self, name)

    def group(self, name: str) -> SambaGroup:
        """
        Get group object.

        .. code-block:: python
            :caption: Example usage

            @pytest.mark.topology(Profile.Winbind)
            def test_example(client: Client, samba: Samba):
                # Create user
                user = samba.user('user-1').add()

                # Create secondary group and add user as a member
                samba.group('group-1').add().add_member(user)

                # Start SSSD
                client.sssd.start()

                # Call `id user-1` and assert the result
                result = client.tools.id('user-1')
                assert result is not None
                assert result.user.name == 'user-1'
                assert result.group.name == 'domain users'
                assert result.memberof('group-1')

        :param name: Group name.
        :type name: str
        :return: New group object.
        :rtype: SambaGroup
        """
        return SambaGroup(self, name)

    def computer(self, name: str) -> SambaComputer:
        """
        Get computer object.

        .. code-block:: python
            :caption: Example usage

            @pytest.mark.topology(Profile.Winbind)
            def test_example(client: Client, samba: Samba):
                # Create OU
                ou = samba.ou("test").add().dn
                # Move computer object
                samba.computer(client.host.hostname.split(".")[0]).move(ou)

                client.sssd.start()

        :param name: Computer name.
        :type name: str
        :return: New computer object.
        :rtype: SambaComputer
        """
        return SambaComputer(self, name)

    def dns(self) -> SambaDNSServer:
        """
        Get DNS server object.

            Get methods use dig and is parsed by jc. The data from jc contains several nested dict,
            but two are returned as a tuple, ``answer, authority``.

        .. code-block:: python
            :caption: Example usage

            # Create forward zone and add forward record
            zone = samba.dns().zone("example.test").create()
            zone.add_record("client", "172.16.200.15")

            # Create reverse zone and add reverse record
            zone = samba.dns().zone("10.0.10.in-addr.arpa").create()
            zone.add_ptr_record("client.example.test", 15)

            # Add forward record to default domain
            samba.dns().zone(samba.domain).add_record("client", "1.2.3.4")

            # Add a global forwarder
            samba.dns().add_forwarder("1.1.1.1")

            # Remove a global forwarder
            samba.dns().remove_forwarder("1.1.1.1")

             # Clear all forwarders
             samba.dns().clear_forwarders()
        """
        return SambaDNSServer(self)

    def ou(self, name: str, basedn: str | None = None) -> SambaOrganizationalUnit:
        """
        Get organizational unit object.

        .. code-block:: python
            :caption: Example usage

            @pytest.mark.topology(Profile.Winbind)
            def test_example(client: Client, samba: Samba):
                # Create organizational unit for sudo rules
                ou = samba.ou('mysudoers').add()

                # Create user
                samba.user('user-1').add()

                # Create sudo rule
                samba.sudorule('testrule', basedn=ou).add(user='ALL', host='ALL', command='/bin/ls')

                client.sssd.common.sudo()
                client.sssd.start()

                # Test that user can run /bin/ls
                assert client.auth.sudo.run('user-1', 'Secret123', command='/bin/ls')

        :param name: Unit name.
        :type name: str
        :param basedn: Base dn, defaults to None
        :type basedn: str | None, optional
        :return: New organizational unit object.
        :rtype: SambaOrganizationalUnit
        """
        return SambaOrganizationalUnit(self, name, basedn)

    def site(self, name: str) -> SambaSite:
        """
        Get site object.

        .. code-block:: python
            :caption: Example usage

            @pytest.mark.topology(Profile.Winbind)
            def test_example(client: Client, samba: Samba):
                # Create New Site, this name cannot contain spaces
                site = samba.site('New-Site').add()

        :param name: Site name.
        :type name: str, cannot contain spaces
        :return: New site object.
        :rtype: SambaSite
        """
        return SambaSite(self, name)

    def sudorule(self, name: str, basedn: str | None = "ou=sudoers") -> SambaSudoRule:
        """
        Get sudo rule object.

        .. code-blocK:: python
            :caption: Example usage

            @pytest.mark.topology(Profile.Winbind)
            def test_example(client: Client, samba: Samba):
                user = samba.user('user-1').add(password="Secret123")
                samba.sudorule('testrule').add(user=user, host='ALL', command='/bin/ls')

                client.sssd.common.sudo()
                client.sssd.start()

                # Test that user can run /bin/ls
                assert client.auth.sudo.run('user-1', 'Secret123', command='/bin/ls')

        :param name: Rule name.
        :type name: str
        :param basedn: Base dn, defaults to ``ou=sudoers``
        :type basedn: str | None, optional
        :return: New sudo rule object.
        :rtype: SambaSudoRule
        """
        return SambaSudoRule(self, name, basedn)


class SambaObject(BaseObject):
    """
    Base class for Samba DC object management.

    Provides shortcuts for command execution and implementation of :meth:`get`,
    :meth:`get_attrs`, and :meth:`delete` methods.
    """

    def __init__(self, role: Samba, command: str, name: str) -> None:
        """
        :param role: Samba role object.
        :type role: Samba
        :param command: Samba command group.
        :type command: str
        :param name: Object name.
        :type name: str
        """
        super().__init__(role)

        self.command: str = command
        """Samba-tool command."""

        self.name: str = name
        """Object name."""

        self.naming_context: str = role.ldap.naming_context
        """Domain naming context."""

        self.__dn: str | None = None

        self.__sid: str | None = None

    def _exec(self, op: str, args: list[str] | None = None, **kwargs) -> ProcessResult:
        """
        Execute samba-tool command.

        .. code-block:: console

            $ samba-tool $command $ op $name $args
            for example >>> samba-tool user add tuser

        :param op: Command group operation (usually add, delete, show)
        :type op: str
        :param args: List of additional command arguments, defaults to None
        :type args: list[str] | None, optional
        :return: SSH process result.
        :rtype: ProcessResult
        """
        if args is None:
            args = []

        return self.role.host.conn.exec(["samba-tool", self.command, op, self.name, *args], **kwargs)

    def _add(self, attrs: CLIBuilderArgs) -> None:
        """
        Add Samba object.

        :param attrs: Object attributes in :class:`pytest_mh.cli.CLIBuilder` format, defaults to dict()
        :type attrs: pytest_mh.cli.CLIBuilderArgs, optional
        """
        self._exec("add", self.cli.args(attrs))

    def _modify(self, attrs: dict[str, Any | list[Any] | DeleteAttribute | None]) -> None:
        """
        Modify Samba object.

        :param attrs: Attributes to modify.
        :type attrs: dict[str, Any  |  list[Any]  |  DeleteAttribute  |  None]
        """
        obj = self.get_attrs()

        # Remove dn and distinguishedName attributes
        dn = obj.pop("dn")[0]
        del obj["distinguishedName"]

        # Build old attrs
        old_attrs = {k: [str(i).encode("utf-8") for i in v] for k, v in obj.items()}

        # Update object
        for attr, value in attrs.items():
            if value is None:
                continue

            if isinstance(value, DeleteAttribute):
                del obj[attr]
                continue

            if not isinstance(value, list):
                obj[attr] = [str(value)]
                continue

            obj[attr] = to_list_of_strings(value)

        # Build new attrs
        new_attrs = {k: [str(i).encode("utf-8") for i in v] for k, v in obj.items()}

        # Build diff
        modlist = ldap.modlist.modifyModlist(old_attrs, new_attrs)
        if modlist:
            self.role.host.ldap_conn.modify_s(dn, modlist)

    def delete(self) -> None:
        """
        Delete Samba object.
        """
        self._exec("delete")

    def get_attrs(self, attrs: list[str] | None = None) -> dict[str, list[str]]:
        """
        Get Samba object attributes from LDAP.

        :param attrs: If set, only requested attributes are returned, defaults to None
        :type attrs: list[str] | None, optional
        :return: Dictionary with attribute name as a key.
        :rtype: dict[str, list[str]]
        """

        cmd = self._exec("show").stdout_lines

        return attrs_parse(cmd, attrs)

    @property
    def dn(self) -> str:
        """
        Object's distinguished name.
        """
        if self.__dn is not None:
            return self.__dn

        obj = self.get_attrs(["dn"])
        self.__dn = obj.pop("dn")[0]
        return self.__dn

    @property
    def sid(self) -> str:
        """
        Object's security identifier.
        """
        if self.__sid is not None:
            return self.__sid

        obj = self.get_attrs(["objectSid"])
        self.__sid = obj.pop("objectSid")[0]
        return self.__sid


class SambaUser(SambaObject, GenericUser):
    """
    Samba user management.

    :class:`SambaUser` implements :class:`GenericUser` for static typing and
    provider-agnostic tests. Samba-specific keyword arguments on :meth:`modify` are in
    addition to the generic API.
    """

    def __init__(self, role: Samba, name: str) -> None:
        """
        :param role: Samba role object.
        :type role: Samba
        :param name: User name.
        :type name: str
        """
        super().__init__(role, "user", name)

    @property
    def name(self) -> str:
        """
        User name.

        Implements :attr:`GenericUser.name`.
        """
        return self._name

    @name.setter
    def name(self, value: str) -> None:
        self._name = value

    def get(self, attrs: list[str] | None = None, *, opattrs: bool = False) -> dict[str, list[str]] | None:
        """
        Get user attributes.

        Implements :meth:`GenericUser.get`. Use :meth:`SambaObject.get_attrs` when a
        non-optional attribute dictionary is required. LDAP ``opattrs`` is ignored.

        :param attrs: If set, only requested attributes are returned, defaults to None
        :type attrs: list[str] | None, optional
        :param opattrs: Ignored (LDAP-only); present for :class:`GenericUser` API compatibility.
        :type opattrs: bool, optional
        :return: Dictionary with attribute name as a key.
        :rtype: dict[str, list[str]] | None
        """
        _ = opattrs
        return self.get_attrs(attrs)

    def add(
        self,
        *,
        uid: int | None = None,
        gid: int | None = None,
        password: str = "Secret123",
        home: str | None = None,
        gecos: str | None = None,
        shell: str | None = None,
        email: str | None = None,
    ) -> SambaUser:
        """
        Create new Samba user.

        Parameters that are not set are ignored.

        :param uid: User id, defaults to None
        :type uid: int | None, optional
        :param gid: Primary group id, defaults to None
        :type gid: int | None, optional
        :param password: Password, defaults to 'Secret123'
        :type password: str, optional
        :param home: Home directory, defaults to None
        :type home: str | None, optional
        :param gecos: GECOS, defaults to None
        :type gecos: str | None, optional
        :param shell: Login shell, defaults to None
        :type shell: str | None, optional
        :param email: Email, defaults to None (= user@domain)
        :type email:  str | None, optional
        :return: Self.
        :rtype: SambaUser
        """
        if email is None:
            email = f"{self.name}@{self.host.domain}"

        attrs: CLIBuilderArgs = {
            "password": (self.cli.option.POSITIONAL, password),
            "given-name": (self.cli.option.VALUE, self.name),
            "surname": (self.cli.option.VALUE, self.name),
            "uid-number": (self.cli.option.VALUE, uid),
            "gid-number": (self.cli.option.VALUE, gid),
            "unix-home": (self.cli.option.VALUE, home),
            "gecos": (self.cli.option.VALUE, gecos),
            "login-shell": (self.cli.option.VALUE, shell),
            "mail-address": (self.cli.option.VALUE, email),
        }

        self._add(attrs)
        return self

    def modify(
        self,
        *,
        uid: int | DeleteAttribute | None = None,
        gid: int | DeleteAttribute | None = None,
        password: str | DeleteAttribute | None = None,
        home: str | DeleteAttribute | None = None,
        gecos: str | DeleteAttribute | None = None,
        shell: str | DeleteAttribute | None = None,
        email: str | DeleteAttribute | None = None,
    ) -> SambaUser:
        """
        Modify existing Samba user.

        Implements :meth:`GenericUser.modify`. Parameters that are not set are ignored.
        If needed, you can delete an attribute by setting the value to :attr:`Delete`.

        :param uid: User id, defaults to None
        :type uid: int | DeleteAttribute | None, optional
        :param gid: Primary group id, defaults to None
        :type gid: int | DeleteAttribute | None, optional
        :param password: Password, defaults to None
        :type password: str | DeleteAttribute | None, optional
        :param home: Home directory, defaults to None
        :type home: str | DeleteAttribute | None, optional
        :param gecos: GECOS, defaults to None
        :type gecos: str | DeleteAttribute | None, optional
        :param shell: Login shell, defaults to None
        :type shell: str | DeleteAttribute | None, optional
        :param email: Email, defaults to None
        :type email: str | DeleteAttribute | None, optional
        :return: Self.
        :rtype: SambaUser
        """
        unix_attrs: dict[str, Any] = {
            "uidNumber": uid,
            "gidNumber": gid,
            "unixHomeDirectory": home,
            "gecos": gecos,
            "loginShell": shell,
        }

        samba_attrs: dict[str, Any] = {"emailAddress": email}
        attrs = {**unix_attrs, **samba_attrs}

        self._modify(attrs)

        if password is not None and not isinstance(password, DeleteAttribute):
            self.reset(str(password))

        return self

    def reset(self, password: str | None = "Secret123") -> SambaUser:
        """
        Reset user password.

        Implements :meth:`GenericUser.reset`.

        :param password: Password, defaults to 'Secret123'
        :type password: str | None, optional
        :return: Self.
        :rtype: SambaUser
        """
        if password is None:
            password = "Secret123"

        self._exec("setpassword", [password])
        return self

    def expire(self, expiration: str | None = "19700101000000") -> SambaUser:
        """
        Set user password expiration date and time.

        Implements :meth:`GenericUser.expire`.

        :param expiration: Date and time for user password expiration, defaults to 19700101000000
        :type expiration: str | None, optional
        :return: Self.
        :rtype: SambaUser
        """
        if expiration is None:
            expiration = "19700101000000"

        expire = datetime.strptime(expiration, "%Y%m%d%H%M%S")
        filetime = str(int((expire.timestamp() + 11644473600) * 10_000_000))
        self._modify({"accountExpires": filetime})
        return self

    def password_change_at_logon(self, **kwargs) -> SambaUser:
        """
        Force user to change password next logon.

        Implements :meth:`GenericUser.password_change_at_logon`.

        :return: Self.
        :rtype: SambaUser
        """
        self._modify({"pwdLastSet": "0"})
        return self

    def passkey_add(self, passkey_mapping: str) -> SambaUser:
        """
        Add passkey mapping to the user.

        Implements :meth:`GenericUser.passkey_add`.

        :param passkey_mapping: Passkey mapping generated by ``sssctl passkey-register``
        :type passkey_mapping: str
        :return: Self.
        :rtype: SambaUser
        """
        attrs: LDAPRecordAttributes = {"altSecurityIdentities": passkey_mapping}
        self.role.ldap.modify(self.dn, add=attrs)
        return self

    def passkey_remove(self, passkey_mapping: str) -> SambaUser:
        """
        Remove passkey mapping from the user.

        Implements :meth:`GenericUser.passkey_remove`.

        :param passkey_mapping: Passkey mapping generated by ``sssctl passkey-register``
        :type passkey_mapping: str
        :return: Self.
        :rtype: SambaUser
        """
        attrs: LDAPRecordAttributes = {"altSecurityIdentities": passkey_mapping}
        self.role.ldap.modify(self.dn, delete=attrs)
        return self


class SambaGroup(SambaObject, GenericGroup):
    """
    Samba group management.

    :class:`SambaGroup` implements :class:`GenericGroup` for static typing and
    provider-agnostic tests. Samba-specific keyword arguments on :meth:`add` are in
    addition to the generic API.
    """

    def __init__(self, role: Samba, name: str) -> None:
        """
        :param role: Samba role object.
        :type role: Samba
        :param name: Group name.
        :type name: str
        """
        super().__init__(role, "group", name)

    @property
    def name(self) -> str:
        """
        Group name.

        Implements :attr:`GenericGroup.name`.
        """
        return self._name

    @name.setter
    def name(self, value: str) -> None:
        self._name = value

    def get(self, attrs: list[str] | None = None, *, opattrs: bool = False) -> dict[str, list[str]] | None:
        """
        Get group attributes.

        Implements :meth:`GenericGroup.get`. Use :meth:`SambaObject.get_attrs` when a
        non-optional attribute dictionary is required. LDAP ``opattrs`` is ignored.

        :param attrs: If set, only requested attributes are returned, defaults to None
        :type attrs: list[str] | None, optional
        :param opattrs: Ignored (LDAP-only); present for :class:`GenericGroup` API compatibility.
        :type opattrs: bool, optional
        :return: Dictionary with attribute name as a key.
        :rtype: dict[str, list[str]] | None
        """
        _ = opattrs
        return self.get_attrs(attrs)

    def add(
        self,
        *,
        gid: int | None = None,
        description: str | None = None,
        scope: str = "Global",
        category: str = "Security",
    ) -> SambaGroup:
        """
        Create new Samba group.

        Implements :meth:`GenericGroup.add`; ``scope`` and ``category`` are Samba-specific.

        :param gid: Group id, defaults to None
        :type gid: int | None, optional
        :param description: Description, defaults to None
        :type description: str | None, optional
        :param scope: Scope ('Global', 'Universal', 'DomainLocal'), defaults to 'Global'
        :type scope: str, optional
        :param category: Category ('Distribution', 'Security'), defaults to 'Security'
        :type category: str, optional
        :return: Self.
        :rtype: SambaGroup
        """
        attrs: CLIBuilderArgs = {
            "gid-number": (self.cli.option.VALUE, gid),
            "description": (self.cli.option.VALUE, description),
            "group-scope": (self.cli.option.VALUE, scope),
            "group-type": (self.cli.option.VALUE, category),
        }

        # NIS Domain is required by samba-tool if gid number is set.
        # It is stored in msSFU30NisDomain attribute of the group which is not
        # used by SSSD so we can just provide hard coded value.
        if gid is not None:
            attrs["nis-domain"] = (self.cli.option.VALUE, "samba")

        self._add(attrs)
        return self

    def modify(
        self,
        *,
        gid: int | DeleteAttribute | None = None,
        description: str | DeleteAttribute | None = None,
    ) -> SambaGroup:
        """
        Modify existing Samba group.

        Implements :meth:`GenericGroup.modify`. Parameters that are not set are ignored.
        If needed, you can delete an attribute by setting the value to :attr:`Delete`.

        :param gid: Group id, defaults to None
        :type gid: int | DeleteAttribute | None, optional
        :param description: Description, defaults to None
        :type description: str | DeleteAttribute | None, optional
        :return: Self.
        :rtype: SambaGroup
        """
        attrs: dict[str, Any] = {
            "gidNumber": gid,
            "description": description,
        }

        self._modify(attrs)
        return self

    def add_member(self, member: GroupMemberField) -> SambaGroup:
        """
        Add group member.

        Implements :meth:`GenericGroup.add_member`.

        :param member: User or group to add as a member.
        :type member: GroupMemberField
        :return: Self.
        :rtype: SambaGroup
        """
        return self.add_members([member])

    def add_members(self, members: list[GroupMemberField]) -> SambaGroup:
        """
        Add multiple group members.

        Implements :meth:`GenericGroup.add_members`.

        :param members: List of users or groups to add as members.
        :type members: list[GroupMemberField]
        :return: Self.
        :rtype: SambaGroup
        """
        self._exec("addmembers", self.__get_member_args(members))
        return self

    def remove_member(self, member: GroupMemberField) -> SambaGroup:
        """
        Remove group member.

        Implements :meth:`GenericGroup.remove_member`.

        :param member: User or group to remove from the group.
        :type member: GroupMemberField
        :return: Self.
        :rtype: SambaGroup
        """
        return self.remove_members([member])

    def remove_members(self, members: list[GroupMemberField]) -> SambaGroup:
        """
        Remove multiple group members.

        Implements :meth:`GenericGroup.remove_members`.

        :param members: List of users or groups to remove from the group.
        :type members: list[GroupMemberField]
        :return: Self.
        :rtype: SambaGroup
        """
        self._exec("removemembers", self.__get_member_args(members))
        return self

    def __get_member_args(self, members: list[GroupMemberField]) -> list[str]:
        return [",".join([x if isinstance(x, str) else x.name for x in members])]


class SambaComputer(SambaObject, GenericComputer):
    """
    Samba computer management.

    :class:`SambaComputer` implements :class:`GenericComputer` for static typing and
    provider-agnostic tests.
    """

    def __init__(self, role: Samba, name: str) -> None:
        """
        :param role: Samba role object.
        :type role: Samba
        :param name: Computer name.
        :type name: str
        """
        super().__init__(role, "computer", name)

    @property
    def name(self) -> str:
        """
        Computer name.

        Implements :attr:`GenericComputer.name`.
        """
        return self._name

    @name.setter
    def name(self, value: str) -> None:
        self._name = value

    def move(self, target: str) -> SambaComputer:
        """
        Move a computer object.

        Implements :meth:`GenericComputer.move`.

        :param target: Target path.
        :type target: str
        :return: Self.
        :rtype: SambaComputer
        """
        self._exec("move", [target])

        return self


class SambaSite(SambaObject, GenericSite):
    """
    Samba site management.

    :class:`SambaSite` implements :class:`GenericSite` for static typing and provider-agnostic tests.
    """

    def __init__(self, role: Samba, name: str) -> None:
        """
        :param role: Samba role object.
        :type role: Samba
        :param name: Site name, cannot contain spaces.
        :type name: str
        """
        super().__init__(role, "sites", name)

    @property
    def name(self) -> str:
        """
        Site name.

        Implements :attr:`GenericSite.name`.
        """
        return self._name

    @name.setter
    def name(self, value: str) -> None:
        self._name = value

    def add(self) -> SambaSite:
        """
        Create new Samba site.

        Implements :meth:`GenericSite.add`.

        :return: Self.
        :rtype: SambaSite
        """
        self._exec("create")

        return self


class SambaPasswordPolicy(GenericPasswordPolicy):
    """
    Samba domain password policy management.

    :class:`SambaPasswordPolicy` implements :class:`GenericPasswordPolicy` for static
    typing and provider-agnostic tests. Settings apply via ``samba-tool domain
    passwordsettings``.
    """

    def __init__(self, role: Samba) -> None:
        """
        :param role: Samba role object.
        :type role: Samba
        """
        super().__init__(role)

        args: CLIBuilderArgs = {
            "min-pwd-age": (self.cli.option.VALUE, "0"),
            "max-pwd-age": (self.cli.option.VALUE, "0"),
        }

        self.host.conn.run(self.cli.command("samba-tool domain passwordsettings set", args))

    def complexity(self, enable: bool) -> SambaPasswordPolicy:
        """
        Enable or disable password complexity.

        Implements :meth:`GenericPasswordPolicy.complexity`.

        :param enable: Enable or disable password complexity.
        :type enable: bool
        :return: Self.
        :rtype: SambaPasswordPolicy
        """
        complexity: str = "on" if enable else "off"

        args: CLIBuilderArgs = {
            "complexity": (self.cli.option.VALUE, complexity),
        }

        self.host.conn.run(self.cli.command("samba-tool domain passwordsettings set", args))

        return self

    def lockout(self, duration: int, attempts: int) -> SambaPasswordPolicy:
        """
        Set lockout duration and login attempts.

        Implements :meth:`GenericPasswordPolicy.lockout`.

        :param duration: Duration of lockout in seconds, converted to minutes.
        :type duration: int
        :param attempts: Number of login attempts.
        :type attempts: int
        :return: Self.
        :rtype: SambaPasswordPolicy
        """
        minutes = divmod(duration, 60)[0]

        args: CLIBuilderArgs = {
            "account-lockout-duration": (self.cli.option.VALUE, str(minutes)),
            "account-lockout-threshold": (self.cli.option.VALUE, str(attempts)),
        }
        self.host.conn.run(self.cli.command("samba-tool domain passwordsettings set", args))

        return self


class SambaDNSServer(GenericDNSServer):
    """
    Samba DNS server management.

    :class:`SambaDNSServer` implements :class:`GenericDNSServer` for static typing and
    provider-agnostic tests.
    """

    def __init__(self, role: Samba) -> None:
        """
        :param role: Samba role object.
        :type role: Samba
        """
        super().__init__(role)

        self.domain: str = role.domain
        """Domain name."""

        self.server: str = role.server
        """Server name."""

        self.naming_context: str = role.naming_context
        """Naming context."""

        self.credentials: str = f" --username={self.role.host.adminuser} --password={self.role.host.adminpw}"
        """Credentials to manage DNS."""

        self.smb_conf: str = "/etc/samba/smb.conf"

    def zone(self, name: str) -> SambaDNSZone:
        """
        Get DNS zone object.

        Implements :meth:`GenericDNSServer.zone`.

        :param name: Zone name.
        :type name: str
        :return: DNS zone object.
        :rtype: SambaDNSZone
        """
        return SambaDNSZone(self.role, name)

    def get_forwarders(self) -> list[str]:
        """
        Get DNS global forwarders.

        Global forwarders are configured in ``/etc/samba/smb.conf``.

        :return: List of forwarder IP addresses (empty if none are configured).
        :rtype: list[str]
        """
        result = [line.strip() for line in self.host.fs.read(self.smb_conf).split("\n")]
        for i in result:
            if "dns forwarder" in i:
                # The additional split is to support more than one server
                return i.split("=")[1].strip().split(" ")
        return []

    def add_forwarder(self, ip_address: str) -> SambaDNSServer:
        """
        Add a DNS server forwarder.

        :param ip_address: IP address.
        :type ip_address: str
        :return:  Self.
        :rtype: SambaDNSServer
        """
        self.host.fs.backup(self.smb_conf)
        self.host.fs.sed(f"s/dns forwarder = .*/ & {ip_address}/", self.smb_conf, ["-i"])
        self.host.svc.reload("samba.service")
        return self

    def remove_forwarder(self, ip_address: str) -> None:
        """
        Remove a DNS server forwarder.

        :param ip_address: IP address.
        :type ip_address: str
        """
        ip_address = ip_address.replace(".", "\\.").strip()
        self.host.fs.backup(self.smb_conf)
        self.host.fs.sed(f"/dns forwarder/s/ {ip_address}//", self.smb_conf, ["-i"])
        self.host.svc.reload("samba.service")

    def clear_forwarders(self) -> None:
        """
        Clear all DNS server forwarders.

        Samba has one global forwarder enabled  by default.
        """
        forwarders = self.get_forwarders()

        if isinstance(forwarders, list) and not None:
            for forwarder in forwarders:
                self.remove_forwarder(forwarder)

    def list_zones(self) -> list[str]:
        """
        List zones.

        :return: List of zones.
        :rtype: list[str]
        """
        result = self.host.conn.run(f"samba-tool dns zonelist {self.server} {self.credentials}").stdout_lines
        result = [i for i in result if "pszZoneName" in i]
        result = [z.split(":")[1].strip() for z in result]

        return result


class SambaDNSZone(SambaDNSServer, GenericDNSZone):
    """
    Samba DNS zone management.

    :class:`SambaDNSZone` implements :class:`GenericDNSZone` for static typing and
    provider-agnostic tests.
    """

    def __init__(self, role: Samba, name: str) -> None:
        """
        :param role: Samba role object.
        :type role: Samba
        :param name: DNS zone name.
        :type name: str
        """
        super().__init__(role)

        self.zone_name: str = name
        """Zone name."""

    def create(self) -> SambaDNSZone:
        """
        Create new zone.

        Implements :meth:`GenericDNSZone.create`.

        :return: Self.
        :rtype: SambaDNSZone
        """
        self.host.conn.run(f"samba-tool dns zonecreate {self.server} {self.zone_name} {self.credentials}")
        return self

    def delete(self) -> None:
        """
        Delete zone.

        Implements :meth:`GenericDNSZone.delete`.
        """
        self.host.conn.run(f"samba-tool dns zonedelete {self.server} {self.zone_name} {self.credentials}")

    def add_record(self, name: str, data: str | int) -> SambaDNSZone:
        """
        Add DNS record.

        Implements :meth:`GenericDNSZone.add_record`.

        If ``data`` is a str, a forward record will be added.
        If an integer a reverse record will be added.

        :param name: Record name.
        :type name: str
        :param data: Record data.
        :type data: str | int
        :return: Self.
        :rtype: SambaDNSZone
        """
        args = ""
        if self.domain not in name:
            name = f"{name}.{self.domain}"
        short_name = name.split(".")[0]

        if isinstance(data, int):
            args = f" {name}. PTR {str(data)} {self.credentials}"
        elif isinstance(data, str) and ip_version(data) == 4:
            args = f" {short_name} A {data} {self.credentials}"
        elif isinstance(data, str) and ip_version(data) == 6:
            args = f" {short_name} AAAA {data} {self.credentials}"

        self.host.conn.run(f"samba-tool dns add {self.server} {self.zone_name} {args}")
        return self

    def delete_record(self, name: str) -> None:
        """
        Delete DNS record, both forward and reverse records are deleted.

        Implements :meth:`GenericDNSZone.delete_record`.

        :param name: Name of the record.
        :type name: str
        """
        if self.domain not in name:
            name = f"{name}.{self.domain}"

        records = self.host.conn.run(f"dig +short +norecurse {name} '@{self.server}'").stdout_lines
        records = [s.rstrip("\r") for s in records]

        if not isinstance(records, list) or records is None:
            return None

        if len(records) > 1:
            for record in records:
                if ip_version(record) == 4:
                    self.role.host.conn.run(
                        f"samba-tool dns delete {self.server} {self.zone_name} {name} A {record} {self.credentials}"
                    )
                if ip_version(record) == 6:
                    self.host.conn.run(
                        f"samba-tool dns delete {self.server} {self.zone_name} {name} AAAA {record} {self.credentials}"
                    )

        for ptr_records in records:
            ptr_record = self.host.conn.run(f"dig +short -x +norecurse {ptr_records} '@{self.server}'").stdout_lines
            ptr_record = [r.rstrip("\r") for r in ptr_record]
            if ptr_record:
                self.host.conn.run(
                    f"samba-tool dns delete {self.server} {ip_to_ptr(ptr_record[0])} {name} "
                    f"PTR {ptr_record} {self.credentials}"
                )
        return None

    def print(self) -> str:
        """
        Print all DNS records in a zone as text.

        Implements :meth:`GenericDNSZone.print`.

        :return: Zone data as text.
        :rtype: str
        """
        result = self.host.conn.run(
            f"samba-tool dns query {self.server} {self.zone_name} @ ALL {self.credentials}"
        ).stdout

        return result


class SambaOrganizationalUnit(GenericOrganizationalUnit):
    """Samba organizational unit management."""

    def __init__(self, role: Samba, name: str, basedn: str | None = None) -> None:
        super().__init__(role)
        self._name = name
        self.basedn = basedn
        self.dn = role.ldap.dn(f"ou={name}", basedn)

    @property
    def name(self) -> str:
        return self._name

    @name.setter
    def name(self, value: str) -> None:
        self._name = value

    def add(self, name: str | None = None) -> SambaOrganizationalUnit:
        _ = name
        self.role.ldap.add(self.dn, {"objectClass": "organizationalUnit", "ou": self.name})
        return self


class SambaSudoRule(GenericSudoRule):
    """Samba sudo rule management via LDAP sudoRole objects."""

    def __init__(self, role: Samba, name: str, basedn: str | None = "ou=sudoers") -> None:
        super().__init__(role)
        self._name = name
        self.basedn = basedn
        self._ensure_default_ou("sudoers")
        self.dn = role.ldap.dn(f"cn={name}", basedn)

    def _ensure_default_ou(self, ou_name: str) -> None:
        if self.basedn is None or self.basedn.lower() != f"ou={ou_name}":
            return

        if ou_name in self.role.auto_ou:
            return

        try:
            self.role.ou(ou_name).add()
        except ldap.ALREADY_EXISTS:
            pass

        self.role.auto_ou[ou_name] = True

    @property
    def name(self) -> str:
        return self._name

    @name.setter
    def name(self, value: str) -> None:
        self._name = value

    def add(
        self,
        *,
        user: SudoRuleUserField = None,
        host: SudoRuleHostField = None,
        command: SudoRuleCommandField = None,
        option: str | list[str] | None = None,
        runasuser: SudoRuleRunAsUserField = None,
        runasgroup: SudoRuleRunAsGroupField = None,
        order: int | None = None,
        nopasswd: bool | None = None,
    ) -> SambaSudoRule:
        attrs = self._build_attrs(
            user=user,
            host=host,
            command=command,
            option=option,
            runasuser=runasuser,
            runasgroup=runasgroup,
            order=order,
            nopasswd=nopasswd,
        )
        attrs["objectClass"] = "sudoRole"
        attrs["cn"] = self.name
        self.role.ldap.add(self.dn, attrs)
        return self

    def modify(
        self,
        *,
        user: SudoRuleUserField = None,
        host: SudoRuleHostField = None,
        command: SudoRuleCommandField = None,
        option: str | list[str] | None = None,
        runasuser: SudoRuleRunAsUserField = None,
        runasgroup: SudoRuleRunAsGroupField = None,
        order: int | None = None,
        nopasswd: bool | None = None,
    ) -> SambaSudoRule:
        attrs = self._build_attrs(
            user=user,
            host=host,
            command=command,
            option=option,
            runasuser=runasuser,
            runasgroup=runasgroup,
            order=order,
            nopasswd=nopasswd,
        )
        if attrs:
            self.role.ldap.modify(self.dn, replace=attrs)
        return self

    def delete(self) -> None:
        self.role.ldap.delete(self.dn)

    def get(self, attrs: list[str] | None = None, *, opattrs: bool = False) -> dict[str, list[str]] | None:
        _ = opattrs
        attrlist = ["*"] if attrs is None else attrs
        result = self.role.ldap.conn.search_s(self.dn, ldap.SCOPE_BASE, attrlist=attrlist)
        if not result:
            return None

        _, result_attrs = result[0]
        out: dict[str, list[str]] = {}
        for key, values in result_attrs.items():
            out[key] = []
            for value in values:
                try:
                    decoded = value.decode("utf-8")
                except UnicodeDecodeError:
                    decoded = base64.b64encode(value).decode("utf-8")
                out[key].append(decoded)

        return out

    def _build_attrs(
        self,
        *,
        user: SudoRuleUserField = None,
        host: SudoRuleHostField = None,
        command: SudoRuleCommandField = None,
        option: str | list[str] | None = None,
        runasuser: SudoRuleRunAsUserField = None,
        runasgroup: SudoRuleRunAsGroupField = None,
        order: int | None = None,
        nopasswd: bool | None = None,
    ) -> LDAPRecordAttributes:
        attrs: LDAPRecordAttributes = {
            "sudoUser": self._format_sudo_users(user),
            "sudoHost": self._format_values(host),
            "sudoCommand": self._format_values(command),
            "sudoOption": self._format_values(option),
            "sudoRunAsUser": self._format_sudo_users(runasuser),
            "sudoRunAsGroup": self._format_sudo_groups(runasgroup),
            "sudoOrder": order,
        }

        if nopasswd is True:
            attrs["sudoOption"] = self._append_option(attrs.get("sudoOption"), "!authenticate")
        elif nopasswd is False:
            attrs["sudoOption"] = self._append_option(attrs.get("sudoOption"), "authenticate")

        return {key: value for key, value in attrs.items() if value is not None}

    def _format_values(self, value: str | ProtocolName | list[str | ProtocolName] | None) -> list[str] | None:
        if value is None:
            return None

        if not isinstance(value, list):
            return [self._item_name(value)]

        return [self._item_name(item) for item in value]

    def _format_sudo_users(
        self,
        value: SudoRuleUserField | SudoRuleRunAsUserField,
    ) -> list[str] | None:
        if value is None:
            return None

        if not isinstance(value, list):
            return [self._sudo_user_name(value)]

        return [self._sudo_user_name(item) for item in value]

    def _format_sudo_groups(self, value: SudoRuleRunAsGroupField) -> list[str] | None:
        if value is None:
            return None

        if not isinstance(value, list):
            return [self._sudo_group_name(value)]

        return [self._sudo_group_name(item) for item in value]

    def _sudo_user_name(self, value: str | SambaUser | SambaGroup | GenericUser | GenericGroup | ProtocolName) -> str:
        if isinstance(value, (SambaGroup, GenericGroup)):
            return f"%{self._item_name(value)}"

        return self._item_name(value)

    def _sudo_group_name(self, value: str | SambaGroup | GenericGroup | ProtocolName) -> str:
        return self._item_name(value)

    def _item_name(self, value: str | SambaUser | SambaGroup | GenericUser | GenericGroup | ProtocolName) -> str:
        if isinstance(value, str):
            return value

        if hasattr(value, "name"):
            return value.name

        raise ValueError(f"Unsupported type: {type(value)}")

    def _append_option(self, current: list[str] | str | None, option: str) -> list[str]:
        if current is None:
            return [option]

        if isinstance(current, list):
            if option in current:
                return current
            return [*current, option]

        if current == option:
            return [current]

        return [current, option]
