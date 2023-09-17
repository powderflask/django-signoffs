# Django Signoffs

[![PyPI Version](https://img.shields.io/pypi/v/django-signoffs.svg)](https://pypi.python.org/pypi/django-signoffs)
[![Docs Status](https://readthedocs.org/projects/django-signoffs/badge/?version=latest)](https://django-signoffs.readthedocs.io/en/latest/?version=latest)
[![Tests](https://github.com/powderflask/django-signoffs/actions/workflows/pytest.yaml/badge.svg)](https://github.com/powderflask/django-signoffs/actions/workflows/pytest.yaml)

A mico-framework for collecting lightweight, non-crypto "signatures" for virtually anything.
 * `Signoff` - a permitted user agrees to something at a time.
 * `Approval` - a set of `Signoffs` that trigger a state change when the `SigningOrder` is complete.
 * `Approval Process` - a sequence of `Approvals` that drive a Finite State Machine.

## Quick Start

1. Install the `django-signoffs` package from PyPI
    ```bash
    $ pip install django-signoffs
    ```

2. Add `signoffs` to `INSTALLED_APPS`:
    ```python
    INSTALLED_APPS = [
        ...,
        "signoffs",
        ...,
    ]
    ```

## Features
`django-signoffs` has 3 tiers. Import and use only the features you need...

### signoffs.signoffs
A `Signoff` records that a user agreed to some statement at a time.
`signoffs.signoffs` provides a framework for defining use-cases 
that fall within this broad requirement.

Core features:
- `AbstractSignet` and `AbstractRevokedSignet` Models (persistence layer)
- Base `Signoff` Types, with injectable business and presentation logic...
  - `SignoffLogic`  (permissions and buisness logic)
  - `SignoffFormsManager` and `SignoffRenderer` (presentation layer)
  - `SignoffUrlsManager` (custom end-points)
- Signoff "forward" relation: `SignoffOneToOneField`
- Signoff "reverse" relation Manager: `SignoffSet` (many-to-one)
- Declarative signing order automation: `SigningOrder` 
- Template tag: `{% render_signoff my_signoff %}`

### signoffs.approvals
An `Approval` records whether some condition was met at some point in time.
Essentially, it is a 2-state machine, designed to change states 
when one or more `Signoffs` are completed, in some defined `SigningOrder`.

Core features:
- `AbstractApprovalSignet` and `AbstractApprovalStamp` Models (persistence layer)
- Base `Approval` Types, with injectable business and presentation logic...
  - `ApprovalLogic`  (business logic)
  - `ApprovalStatus` and `ApprovalRenderer` (presentation layer)
  - `ApprovalUrlsManager` (custom end-points)
- Approval "forward" relation: `ApprovalOneToOneField`
- Approval "reverse" relation Manager: `ApprovalSet` (experimental)
- Template tag: `{% render_approval my_approval %}`

### signoffs.process
An `ApprovalsProcess` defines a sequence of `Approvals` and the state changes and/or
side effects triggered by approving or revoking each of them.

Core Features:
- `ApprovalsProcess` (a basic linear sequence of `Approvals`)
- `FsmApprovalsProcess` (state-changes and sequencing defined by `django-fsm`)

## Opt-in

### Contrib Models

#### signoffs.contrib.signets
Signoffs core defines only abstract models, no migrations.
`signoffs.contrib.signets` provide concrete models that cover the basic use-cases.  To opt-in, you must:

   ```python
    INSTALLED_APPS = [
        ...,
        "signoffs.contrib.signets",
         ...,
    ]
   ```
   ```bash
    $ python manage.py migrate signoffs_signets
   ```

Core Features:
 - Concrete Models: `Signet`, and `RevokedSignet` provide persistence layer for
 - Concrete Signoffs: `SimpleSignoff`, `RevokableSignoff`, and `IrrevokableSignoff` 

#### signoffs.contrib.approvals
Approvals core defines only abstract models, no migrations.
`signoffs.contrib.approvals` provide concrete models with basic relations.  To opt-in you must:

   ```python
    INSTALLED_APPS = [
        ...,
        "signoffs.contrib.approvals",
         ...,
    ]
   ```
   ```bash
    $ python manage.py migrate signoffs_approvals
   ```

Core Features:
 - Concrete Models: `ApprovalSignet`, and `RevokedApprovalSignet` define a FK relation to...
 - `Stamp` which provides persistence layer for...
 - `SimpleApproval` and `IrrevokableApproval`, which play nicely with...
 - `ApprovalSignoff`, which uses the Concrete Models for persistence.

### FsmApprovalsProcess
Signoffs is integrated with [django-fsm](https://pypi.org/project/django-fsm/), 
allowing approval processes to drive a finite state machine.
To opt-in:
   ```bash
    $ pip install django-signoffs[fsm]
   ```

## Get Me Some of That
* [Source Code](https://github.com/powderflask/django-signoffs)
* [Read The Docs](https://django-signoffs.readthedocs.io/en/latest/)
* [Issues](https://github.com/powderflask/django-signoffs/issues)
* [PyPI](https://pypi.org/project/django-signoffs)

[MIT License](https://github.com/powderflask/django-signoffs/blob/master/LICENSE)

### Check Out the Demo App

1. `pip install -e git+https://github.com/powderflask/django-signoffs.git#egg=django-signoffs`
1. `python django-signoffs/manage.py install_demo`
1. `python django-signoffs/manage.py runserver`


### Acknowledgments
Special thanks to BC Hydro, [Chartwell](https://crgl.ca/),
and all [Contributors](https://github.com/powderflask/django-signoffs/graphs/contributors)

#### Technology Colophon

Without django and the django dev team, the universe would have fewer rainbows and ponies.
Signoffs approval process can be integrated on the deceptively clever [`django_fsm`][1] Friendly Finite State Machine.
Signoffs uses a global registry as store for singleton code objects - thanks [`persisting_theory`][2]!

This package was originally created with [`cookiecutter`][3] and the [`cookiecutter-pypackage`][4] project template.

[1]: <https://github.com/viewflow/django-fsm>
[2]: <https://github.com/kiwnix/persisting-theory>
[3]: <https://github.com/audreyr/cookiecutter>
[4]: <https://github.com/audreyr/cookiecutter-pypackage>

## For Developers
   ```bash
   $  pip install -r reqirements_dev.txt
   ```

### Tests
   ```bash
   $ pytest
   ```
or
   ```bash
   $ tox
   ```

### Code Style / Linting
   ```bash
   $ isort
   $ black
   $ flake8
   ```

### Versioning
 * [Semantic Versioning](https://semver.org/)
   ```bash
   $ bumpver show
   ```

### Docs
 * [Sphinx](https://www.sphinx-doc.org/en/master/) + [MyST parser](https://myst-parser.readthedocs.io/en/latest/intro.html)
 * [Read The Docs](https://readthedocs.org/projects/django-signoffs/)

### Build / Deploy Automation
 * [invoke](https://www.pyinvoke.org/)
   ```bash
   $ invoke -l
   ```
 * [GitHub Actions](https://docs.github.com/en/actions) (see [.github/workflows](https://github.com/powderflask/django-signoffs/tree/master/.github/workflows))
 * [GitHub Webhooks](https://docs.github.com/en/webhooks)  (see [settings/hooks](https://github.com/powderflask/django-signoffs/settings/hooks))
