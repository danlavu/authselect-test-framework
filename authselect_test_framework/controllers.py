from __future__ import annotations

import re

from pytest_mh import BackupTopologyController

from .config import AuthselectMultihostConfig
from .hosts.client import ClientHost
from .hosts.ipa import IPAHost
from .hosts.samba import SambaHost

__all__ = [
    "LocalController",
    "SSSDController",
    "WinbindController",
]


class ProvisionedBackupController(BackupTopologyController[AuthselectMultihostConfig]):
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


class LocalController(ProvisionedBackupController):
    """
    Local profile controller.
    """

    pass


class SSSDController(ProvisionedBackupController):
    """
    SSSD profile controller.
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

        self.logger.info(f"Enrolling {client.hostname} into {ipa.domain}")

        client.fs.rm("/etc/krb5.conf")
        client.fs.rm("/etc/krb5.keytab")

        result = client.conn.exec(["realm", "list"])
        self.logger.info(f"REALM_LIST STDOUT: \n{result.stdout}")
        self.logger.info(f"REALM_LIST STDERR: \n{result.stderr}")
        pattern = rf"^{re.escape(ipa.domain)}$"
        if re.search(pattern, result.stdout, re.MULTILINE):
            self.logger.info(f"Found {ipa.domain} in realm list.  Leaving.")
            client.conn.exec(["realm", "leave", ipa.domain], input=ipa.adminpw, raise_on_error=False)

        client.fs.backup("/etc/ipa")
        client.fs.backup("/var/lib/ipa-client")

        result = client.conn.exec(["realm", "join", ipa.domain], input=ipa.adminpw, raise_on_error=False)
        if result.rc != 0:
            self.logger.info(f"Running realm join failed with:\n{result.stdout}\n{result.stderr}")
            self.logger.info("Trying uninstall and join again.")
            client.conn.exec(["ipa-client-install", "--uninstall", "-U"])
            client.conn.exec(["realm", "join", ipa.domain], input=ipa.adminpw)

        client.svc.stop("winbind.service")
        client.svc.stop("sssd.service")

        super().topology_setup()


class WinbindController(ProvisionedBackupController):
    """
    Winbind profile controller.
    """

    @BackupTopologyController.restore_vanilla_on_error
    def topology_setup(self, client: ClientHost, server: SambaHost) -> None:
        short_hostname = client.conn.run("hostname").stdout.split(".")[0].strip()
        hostname = f"{short_hostname}.{server.domain}"
        client.fs.backup("/etc/hostname")
        client.fs.backup("/etc/hosts")
        client.conn.run(f"echo {hostname} > /etc/hostname")
        client.fs.write("/etc/hosts", client.fs.read("/etc/hosts").replace("client.test", hostname))

        self.logger.info(f"Changing hostname to {hostname}")
        client.conn.run(f"hostname {hostname}")

        if "127.0.0.1" not in server.fs.read("/etc/resolv.conf"):
            server.fs.backup("/etc/resolv.conf")
            server.fs.write("/etc/resolv.conf", f"search {server.domain}\nnameserver 127.0.0.1\n\n")

        self.logger.info(f"Setting up winbind on {client.hostname} for {server.domain}")

        workgroup = server.domain.split(".", maxsplit=1)[0].upper()
        client.conn.run(
            "cat > '/etc/samba/smb.conf' <<'EOF'\n"
            + "\n".join(
                [
                    "[global]",
                    f"workgroup = {workgroup}",
                    "security = ads",
                    f"realm = {server.realm}",
                    "kerberos method = secrets and keytab",
                    "winbind use default domain = yes",
                    "template homedir = /home/%U",
                    "template shell = /bin/bash",
                    "idmap config * : backend = tdb",
                    "idmap config * : range = 3000-7999",
                    f"idmap config {workgroup} : backend = rid",
                    f"idmap config {workgroup} : range = 1000-999999",
                    "",
                ]
            )
            + "EOF"
        )
        client.fs.backup("/etc/samba/smb.conf")

        client.svc.stop("sssd.service")
        client.conn.run('systemctl disable "sssd.service"', raise_on_error=False)
        client.conn.run('systemctl enable "winbind.service"', raise_on_error=False)
        client.svc.restart("winbind.service", raise_on_error=False)
        client.svc.stop("winbind.service")

        # Always take topology backups, even for provisioned environments.
        super(ProvisionedBackupController, self).topology_setup()
