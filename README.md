# Django Signoffs

[![PyPI Version](https://img.shields.io/pypi/v/django_signoffs.svg)](https://pypi.python.org/pypi/django_signoffs)
[![Documentation Status](https://readthedocs.org/projects/django-signoffs/badge/?version=latest)](https://django-signoffs.readthedocs.io/en/latest/?version=latest)

Version: 0.2.0

Generic signoffs, approvals, and approval processes to collect lightweight, non-crypto "signatures" for virtually anything.

Documentation: [https://django-signoffs.readthedocs.io](https://django-signoffs.readthedocs.io)

Django Signoffs is free software distributed under the MIT License.


## Install

### Requirements

`pip install django-fsm` to use FsmApprovalProcess

## Features

### signoffs.signoffs

- Signet Models
- Signet Relations: One-to-One and Many-to-One
- Signoff Types & instances
- Signoff Relations: SignoffOneToOneField & SignoffSet (many-to-one)
- Signoff Form
- Signoff permissions and renderers

### signoffs.approvals

- Approval Stamp Models
- Approval Types & instances
- Approval Relations: ApprovalOneToOneField (experimental: ApprovalSet)
- Approval permissions and renderers
- Approval Processes & FSM Approval Processes

### signoffs.contrib

- Base models, signoffs, approvals
- Generic models (experimental)

## TODO

- add tests for SignoffOneToOneField and SignoffSet to testapps, with and without revoke models
- add generic JSON API views for getting and posting signoffs and revokes
- add test cases and infrastructure for working with formsets of signoffs

## Credits

Without django and the django dev team, the universe would have fewer rainbows and ponies.
Signoffs approval process can be integrated on the deceptively clever [`django_fsm`][1] Friendly Finite State Machine.
Signoffs uses a global registry as store for singleton code objects - thanks [`persisting_theory`][2]!

This package was created with [`cookiecutter`][3] and the [`cookiecutter-pypackage`][4] project template.

[1]: <https://github.com/viewflow/django-fsm>
[2]: <https://github.com/kiwnix/persisting-theory>
[3]: <https://github.com/audreyr/cookiecutter>
[4]: <https://github.com/audreyr/cookiecutter-pypackage>