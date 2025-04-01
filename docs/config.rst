Multihost configuration
#######################

The multihost configuration file defines domains, hosts and roles available to
run authselect system tests. It uses `YAML <https://en.wikipedia.org/wiki/YAML>`__.

Basic definition
****************

.. code-block:: yaml

    provisioned_topologies:
    - <list-of-profiles>
    domains:
    - id: <domain id>
      hosts:
      - hostname: <dns host name>
        role: <host role>
        conn:
          type: ssh
          host: <ssh host> (optional, defaults to host name)
          port: <ssh port> (optional, defaults to 22)
          username: <ssh username> (optional, defaults to "root")
          password: <ssh password> (optional, defaults to "Secret123")
        config: <additional configuration> (optional, defaults to {})
        artifacts: <list of produced artifacts> (optional, defaults to {})

The ``provisioned_topologies`` field lists profile names that are already
provisioned. If a profile is listed, tests run directly without topology
controller setup. Otherwise the profile controller provisions the environment
before tests run.

.. _available-roles:

Available roles
***************

The authselect test framework supports three roles:

* ``client`` — host running authselect and SSSD
* ``ipa`` — FreeIPA server
* ``samba`` — Samba AD domain controller

client
======

SSSD client used for authselect functional tests.

.. code-block:: yaml
    :caption: Client role example

    - hostname: client.test
      role: client
      artifacts:
      - /etc/sssd/*
      - /var/log/sssd/*
      - /var/lib/sss/db/*

ipa
===

FreeIPA server. The client is enrolled into the IPA domain by the
:class:`~authselect_test_framework.topology_controllers.SSSDTopologyController`.

.. code-block:: yaml
    :caption: IPA role example

    - hostname: master.ipa.test
      role: ipa
      config:
        client:
          ipa_domain: ipa.test
          krb5_keytab: /var/enrollment/ipa.test.keytab
          ldap_krb5_keytab: /var/enrollment/ipa.test.keytab

samba
=====

Samba AD domain controller. The client is enrolled via winbind by the
:class:`~authselect_test_framework.topology_controllers.WinbindTopologyController`.

.. code-block:: yaml
    :caption: Samba role example

    - hostname: dc.samba.test
      role: samba
      config:
        binddn: CN=Administrator,CN=Users,DC=samba,DC=test
        bindpw: Secret123
        client:
          ad_domain: samba.test
          krb5_keytab: /var/enrollment/samba.test.keytab
          ldap_krb5_keytab: /var/enrollment/samba.test.keytab

Example configuration
*********************

A minimal configuration for all authselect profiles:

.. code-block:: yaml

    provisioned_topologies:
    - local
    - sssd
    - winbind
    domains:
    - id: sssd
      hosts:
      - hostname: client.test
        role: client
        artifacts:
        - /etc/sssd/*
        - /var/log/sssd/*
        - /var/lib/sss/db/*
      - hostname: master.ipa.test
        role: ipa
        config:
          client:
            ipa_domain: ipa.test
            krb5_keytab: /var/enrollment/ipa.test.keytab
            ldap_krb5_keytab: /var/enrollment/ipa.test.keytab
      - hostname: dc.samba.test
        role: samba
        config:
          binddn: CN=Administrator,CN=Users,DC=samba,DC=test
          bindpw: Secret123
          client:
            ad_domain: samba.test
            krb5_keytab: /var/enrollment/samba.test.keytab
            ldap_krb5_keytab: /var/enrollment/samba.test.keytab

.. seealso::

    The bundled example is in the authselect repository at
    ``src/tests/system/mhc.yaml``.
