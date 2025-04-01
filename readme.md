# Authselect Test Framework

This framework provides high-level API used by Authselect [system tests](https://github.com/authselect/authselect).

It implements functionality such as:

* System, IPA, Active Directory, Samba Directory users, groups and other objects management
* Authselect, SSSD, PAM, Winbind configuration and management
* Automatic backup and restore of all hosts

This framework can be used by other projects as well.

## Documentation

**See the full documentation here: https://tests.sssd.io**.

## Submitting changes

Changes to this framework may be submitted, but a great care must be taken in
order to not introduce any breaking API changes.

All tests must pass and changes must be validated with:

* black
* flake8
* isort
* mypy
* pycodestyle

You can run all checks using ``tox``.
