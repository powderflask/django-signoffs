Django Signoffs
===============

[![Package Version](https://img.shields.io/pypi/v/django_signoffs.svg)](https://pypi.python.org/pypi/django_signoffs)

[![Documentation Status](https://readthedocs.org/projects/django-signoffs/badge/?version=latest)](https://django-signoffs.readthedocs.io/en/latest/?version=latest)

Generic signoffs, approvals, and approval processes
to collect light-weight, non-crypto "signatures" for virtually anything.


* Free software: MIT license
* [Documentation on ReadTheDocs](https://django-signoffs.readthedocs.io)


## Install
```{note}
django-fsm will need to be installed to use FsmApprovalProcess:
`pip install django-fsm`
```

## Features

**signoffs.signoffs**

[//]: # (TODO: add links to feature references that direct to module doc)

* Signet Models
* Signet Relations:  One-to-One and Many-to-One
* Signoff Types & instances
* Signoff Relations:  SignoffOneToOneField & SignoffSet (many-to-one)
* Signoff Form
* Signoff permissions and renderers


**signoffs.approvals**

* Approval Stamp Models
* Approval Types & instances
* Approval Relations:  ApprovalOneToOneField (experimental: ApprovalSet)
* Approval permissions and renderers
* Approval Processes & FSM Approval Processes


**signoffs.contrib**

* Base models, signoffs, approvals
* Generic models (experimental)


**TODO**

* add tests for SignoffOneToOneField and SignoffSet to testapps, with and without revoke models

* add generic JSON API views for getting and posting signoffs and revokes

* add test cases and infrastructure for working with formsets of signoffs


-------
## Credits

Without django and the django dev team, the universe would have fewer rainbows and ponies.
signoffs approval process can be integrated on the deceptively clever django_fsm_ Friendly Finite State Machine.
signoffs uses a global registry as store for singleton code objects - thanks persisting_theory_!

This package was created with Cookiecutter_ and the `audreyr/cookiecutter-pypackage`_ project template.

* django_fsm: https://github.com/viewflow/django-fsm
* persisting_theory: https://github.com/kiwnix/persisting-theory
* Cookiecutter: https://github.com/audreyr/cookiecutter
* `audreyr/cookiecutter-pypackage`: https://github.com/audreyr/cookiecutter-pypackage
