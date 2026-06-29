"""Manage winbind on the client."""

from __future__ import annotations

import shlex

from pytest_mh import MultihostHost, MultihostUtility
from pytest_mh.conn import ProcessResult
from pytest_mh.utils.services import SystemdServices

__all__ = [
    "WinbindUtils",
]


class WinbindUtils(MultihostUtility):
    """
    Management of winbind on the client host.

    .. code-block:: python
        :caption: Example usage

        @pytest.mark.topology(Profile.Winbind)
        def test_example(client: Client, provider: GenericServer):
            provider.user("user-1").add()
            client.authselect.select("winbind")
            client.winbind.start()
    """

    def __init__(self, host: MultihostHost, svc: SystemdServices) -> None:
        """
        :param host: Multihost object.
        :type host: MultihostHost
        :param svc: Systemd utils.
        :type svc: SystemdServices
        """
        super().__init__(host)

        self.svc: SystemdServices = svc

    def _wait_for_ready(self, *, timeout: int = 60) -> None:
        """
        Wait until winbindd responds to ping requests.

        :param timeout: Maximum wait time in seconds, defaults to 60
        :type timeout: int, optional
        :return: None
        """
        self.host.conn.run(
            f"timeout {timeout}s bash -c 'until wbinfo -p && wbinfo -t; do sleep 1; done'",
            raise_on_error=True,
        )

    def wait_for_user(self, user: str, *, timeout: int = 60) -> None:
        """
        Wait until a domain user is resolvable via NSS.

        :param user: User name to resolve.
        :type user: str
        :param timeout: Maximum wait time in seconds, defaults to 60
        :type timeout: int, optional
        :return: None
        """
        quoted_user = shlex.quote(user)
        self.host.conn.run(
            f"timeout {timeout}s bash -c 'until getent passwd {quoted_user}; do net cache flush; sleep 1; done'",
            raise_on_error=True,
        )

    def start(self, *, users: list[str] | None = None) -> ProcessResult:
        """
        Start winbind and refresh caches.

        :param users: Domain users that must be resolvable before returning, defaults to None
        :type users: list[str] | None, optional
        :return: SSH process result.
        :rtype: ProcessResult
        """
        result = self.svc.start("winbind.service")
        self.host.conn.exec(["net", "cache", "flush"])
        self._wait_for_ready()
        if users:
            for user in users:
                self.wait_for_user(user)
        return result

    def stop(self) -> ProcessResult:
        """
        Stop winbind.

        :return: SSH process result.
        :rtype: ProcessResult
        """
        return self.svc.stop("winbind.service")

    def enable(self, *, now: bool = False) -> ProcessResult:
        """
        Enable winbind.

        :param now: Enable and start the unit immediately, defaults to False
        :type now: bool, optional
        :return: SSH process result.
        :rtype: ProcessResult
        """
        args = ["systemctl", "enable"]
        if now:
            args.append("--now")
        args.append("winbind.service")
        return self.host.conn.exec(args)

    def disable(self, *, now: bool = False) -> ProcessResult:
        """
        Disable winbind.

        :param now: Disable and stop the unit immediately, defaults to False
        :type now: bool, optional
        :return: SSH process result.
        :rtype: ProcessResult
        """
        args = ["systemctl", "disable"]
        if now:
            args.append("--now")
        args.append("winbind.service")
        return self.host.conn.exec(args)
