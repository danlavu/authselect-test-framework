Using Roles
###########

Multihost roles are the main interface to remote hosts. Role objects automatically
back up remote state at test start and restore it when the test ends.

Available roles
***************

* ``client`` — authselect and SSSD client
* ``ipa`` — FreeIPA server
* ``samba`` — Samba AD domain controller

Provider roles
**************

IPA and Samba implement :class:`~authselect_test_framework.roles.generic.GenericProvider`.
Use the ``provider`` fixture for tests that run on both profiles:

.. code-block:: python

    from authselect_test_framework.roles.generic import GenericProvider
    from authselect_test_framework.topology import Profile


    @pytest.mark.topology(Profile.SSSD)
    @pytest.mark.topology(Profile.Winbind)
    def test_example(provider: GenericProvider):
        provider.user("user-1").add()
        provider.group("group-1").add().add_member(provider.user("user-2").add())
        provider.sudorule("test").add(user="user-1", host="ALL", command="/bin/ls")

Client role
***********

The client role provides access to authselect, SSSD, authentication and local users:

.. code-block:: python

    from authselect_test_framework.roles.client import Client
    from authselect_test_framework.topology import Profile


    @pytest.mark.topology(Profile.SSSD)
    def test_example(client: Client):
        client.authselect.select("sssd", ["with-mkhomedir"])
        client.sssd.start()
        client.local.user("local-user").add()
        assert client.auth.ssh.password("user-1", "Secret123")

Common client utilities:

* ``client.authselect`` — select profiles and features
* ``client.sssd`` — configure and start SSSD
* ``client.auth`` — test su, ssh and sudo authentication
* ``client.local`` — manage local users and groups
* ``client.tools`` — getent, faillock and other CLI tools
* ``client.fs`` — file system operations with automatic backup/restore

.. seealso::

    :class:`~authselect_test_framework.roles.client.Client`
    :class:`~authselect_test_framework.roles.ipa.IPA`
    :class:`~authselect_test_framework.roles.samba.Samba`
