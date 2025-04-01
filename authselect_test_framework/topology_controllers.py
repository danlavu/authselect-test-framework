from __future__ import annotations

import re

from pytest_mh import BackupTopologyController

from .config import AuthselectMultihostConfig
from .hosts.client import ClientHost
from .hosts.ipa import IPAHost
from .hosts.samba import SambaHost

__all__ = [
    "LocalTopologyController",
    "SSSDTopologyController",
    "WinbindTopologyController",
]


class ProvisionedBackupTopologyController(BackupTopologyController[AuthselectMultihostConfig]):
    """
    Provide basic restore functionality for topologies.
    """

    def __init__(self) -> None:
        super().__init__()

        self.provisioned: bool = False

    def init(self, *args, **kwargs):
        super().init(*args, **kwargs)
        self.provisioned = self.name in self.multihost.provisioned_topologies

    def topology_setup(self, *args, **kwargs) -> None:
        if self.provisioned:
            self.logger.info(f"Topology '{self.name}' is already provisioned")
            return

        super().topology_setup(*args, **kwargs)

    def topology_teardown(self, *args, **kwargs) -> None:
        if self.provisioned:
            return

        super().topology_teardown(*args, **kwargs)

    def teardown(self) -> None:
        if self.provisioned:
            self.restore_vanilla()
            return

        super().teardown()

    def join_domain(self, client: ClientHost, provider: IPAHost | SambaHost):
        """
        Helper method for joining domains.
        """
        self.logger.info(f"Enrolling {client.hostname} into {provider.domain}")

        client.fs.rm("/etc/krb5.conf")
        client.fs.rm("/etc/krb5.keytab")

        result = client.conn.exec(["realm", "list"])
        self.logger.info(f"REALM_LIST STDOUT: \n{result.stdout}")
        self.logger.info(f"REALM_LIST STDERR: \n{result.stderr}")
        pattern = rf"^{re.escape(provider.domain)}$"
        if re.search(pattern, result.stdout, re.MULTILINE):
            self.logger.info(f"Found {provider.domain} in realm list.  Leaving.")
            client.conn.exec(["realm", "leave", provider.domain], input=provider.adminpw, raise_on_error=False)

        if isinstance(provider, IPAHost):
            client.fs.backup("/etc/ipa")
            client.fs.backup("/var/lib/ipa-client")

        result = client.conn.exec(["realm", "join", provider.domain], input=provider.adminpw, raise_on_error=False)
        if result.rc != 0:
            self.logger.info(f"Running realm join failed with:\n{result.stdout}\n{result.stderr}")
            self.logger.info("Trying uninstall and join again.")
            if isinstance(provider, IPAHost):
                client.conn.exec(["ipa-client-install", "--uninstall", "-U"])
            else:
                client.conn.exec(["realm", "leave", "--unattended", provider.domain], input=provider.adminpw)
            client.conn.exec(["realm", "join", provider.domain], input=provider.adminpw)


class LocalTopologyController(ProvisionedBackupTopologyController):
    """
    Local profile topology controller.
    """

    pass


class SSSDTopologyController(ProvisionedBackupTopologyController):
    """
    SSSD profile topology controller.
    """

    @BackupTopologyController.restore_vanilla_on_error
    def topology_setup(self, client: ClientHost, ipa: IPAHost) -> None:
        short_hostname = client.conn.run("hostname").stdout.split(".")[0].strip()
        hostname = f"{short_hostname}.{ipa.domain}"
        client.fs.backup("/etc/hostname")
        client.fs.backup("/etc/hosts")
        client.conn.run(f"echo {hostname} > /etc/hostname")
        client.fs.write("/etc/hosts", client.fs.read("/etc/hosts").replace("client.test", hostname))

        self.logger.info(f"Changing hostname to {hostname}")
        client.conn.run(f"hostname {hostname}")

        client.fs.backup("/etc/resolv.conf")

        if self.provisioned:
            self.logger.info(f"Topology '{self.name}' is already provisioned")
            return

        self.join_domain(client, ipa)

        super().topology_setup()


class WinbindTopologyController(ProvisionedBackupTopologyController):
    """
    Winbind profile topology controller.
    """

    @BackupTopologyController.restore_vanilla_on_error
    def topology_setup(self, client: ClientHost, provider: SambaHost) -> None:
        short_hostname = client.conn.run("hostname").stdout.split(".")[0].strip()
        hostname = f"{short_hostname}.{provider.domain}"

        self.logger.info(f"Changing hostname to {hostname}")
        client.conn.run(f"hostname {hostname}")

        if "127.0.0.1" not in provider.fs.read("/etc/resolv.conf"):
            provider.fs.backup("/etc/resolv.conf")
            provider.fs.write("/etc/resolv.conf", f"search {provider.domain}\nnameserver 127.0.0.1\n\n")

        if self.provisioned:
            self.logger.info(f"Topology '{self.name}' is already provisioned")
            return

        self.join_domain(client, provider)

        super().topology_setup()
