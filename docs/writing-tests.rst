Writing new tests
#################

Authselect system tests use `pytest`_, `pytest-mh`_ and
:mod:`authselect_test_framework`.

.. _pytest: https://docs.pytest.org
.. _pytest-mh: https://pytest-mh.readthedocs.io

Using profile markers
*********************

Each test that requires remote hosts must be marked with a topology marker.
Use predefined profiles from :class:`authselect_test_framework.topology.Profile`:

.. code-block:: python

    import pytest

    from authselect_test_framework.roles.client import Client
    from authselect_test_framework.topology import Profile


    @pytest.mark.topology(Profile.Local)
    def test_example(client: Client):
        client.authselect.select("local")
        assert True

Available profiles
==================

.. list-table::
   :header-rows: 1

   * - Profile
     - Hosts
     - Use case
   * - :attr:`~authselect_test_framework.topology.Profile.Local`
     - client
     - Local profile, presets, CLI tests
   * - :attr:`~authselect_test_framework.topology.Profile.SSSD`
     - client + ipa
     - SSSD profile with IPA provider
   * - :attr:`~authselect_test_framework.topology.Profile.Winbind`
     - client + samba
     - SSSD profile with Samba AD provider

.. topology-mark:: Profile.Local

.. topology-mark:: Profile.SSSD

.. topology-mark:: Profile.Winbind

Provider tests
==============

Tests that must run against both IPA and Samba use multiple topology markers.
pytest-mh clones the test for each profile:

.. code-block:: python

    import pytest

    from authselect_test_framework.roles.client import Client
    from authselect_test_framework.roles.generic import GenericProvider
    from authselect_test_framework.topology import Profile


    @pytest.mark.topology(Profile.SSSD)
    @pytest.mark.topology(Profile.Winbind)
    def test_example(client: Client, provider: GenericProvider):
        provider.user("user-1").add()
        client.authselect.select("sssd")
        client.sssd.start()
        assert client.auth.ssh.password("user-1", "Secret123")

The ``provider`` fixture points to ``sssd.ipa[0]`` or ``sssd.samba[0]`` depending
on the active profile.

conftest.py
===========

Authselect tests load the framework through ``conftest.py``:

.. code-block:: python

    from pytest_mh import MultihostPlugin
    from authselect_test_framework.config import AuthselectMultihostConfig

    pytest_plugins = (
        "pytest_importance",
        "pytest_mh",
        "pytest_ticket",
        "pytest_tier",
        "authselect_test_framework.fixtures",
        "authselect_test_framework.markers",
    )

    def pytest_plugin_registered(plugin) -> None:
        if isinstance(plugin, MultihostPlugin):
            plugin.config_class = AuthselectMultihostConfig

.. seealso::

    :doc:`guides/using-roles` for manipulating remote hosts through role objects.
    :doc:`api` for the full API reference.
