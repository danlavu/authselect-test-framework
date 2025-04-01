from __future__ import annotations

from pytest_mh import BackupTopologyController
from sssd_test_framework.hosts.client import ClientHost
from sssd_test_framework.hosts.ipa import IPAHost
from sssd_test_framework.hosts.samba import SambaHost

from .config import AuthselectMultihostConfig

__all__ = [
    "LocalTopologyController",
    "SSSTopologyController",
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

    def topology_teardown(self) -> None:
        if self.provisioned:
            return

        super().topology_teardown()

    def teardown(self) -> None:
        if self.provisioned:
            self.restore_vanilla()
            return

        super().teardown()


class LocalTopologyController(ProvisionedBackupTopologyController):
    """
    Local Topology Controller.
    """

    pass


class SSSTopologyController(ProvisionedBackupTopologyController):
    """
    SSS Topology Controller.
    """

    @BackupTopologyController.restore_vanilla_on_error
    def topology_setup(self, client: ClientHost, ipa: IPAHost) -> None:
        if self.provisioned:
            self.logger.info(f"Topology '{self.name}' is already provisioned")
            return

        self.logger.info(f"Enrolling {client.hostname} into {ipa.domain}")

        # Remove any existing Kerberos configuration and keytab
        client.fs.rm("/etc/krb5.conf")
        client.fs.rm("/etc/krb5.keytab")

        # Backup ipa-client-install files
        client.fs.backup("/etc/ipa")
        client.fs.backup("/var/lib/ipa-client")

        # Join ipa domain
        client.conn.exec(["realm", "join", ipa.domain], input=ipa.adminpw)

        # Backup so we can restore to this state after each test
        super().topology_setup()


class WinbindTopologyController(ProvisionedBackupTopologyController):
    """
    Winbind Topology Controller.
    """

    @BackupTopologyController.restore_vanilla_on_error
    def topology_setup(self, client: ClientHost, samba: SambaHost) -> None:
        if self.provisioned:
            self.logger.info(f"Topology '{self.name}' is already provisioned")
            return

        self.logger.info(f"Enrolling {client.hostname} into {samba.domain}")

        # Remove any existing Kerberos configuration and keytab
        client.fs.rm("/etc/krb5.conf")
        client.fs.rm("/etc/krb5.keytab")

        # Configure winbind domain
        # client.conn.exec(["realm", "join", ipa.domain], input = ipa.adminpw)

        # Backup so we can restore to this state after each test
        super().topology_setup()

    pass
