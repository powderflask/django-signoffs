"""
    Proxy for Signoff Types to simplify import statements and hide core package structure from client code.

    isort:skip_file
"""
from django.apps import apps

from signoffs.core import signing_order

from signoffs.core import utils

from signoffs.core.forms import (
    SignoffFormsManager,
    SignoffTypeForms,
)
from signoffs.core.renderers import (
    SignoffInstanceRenderer,
    SignoffRenderer,
)
from signoffs.core.signoffs import (
    AbstractSignoff,
    BaseSignoff,
    SignoffLogic,
)
from signoffs.core.urls import (
    SignoffInstanceUrls,
    SignoffUrlsManager,
)

if apps.is_installed("signoffs.contrib.signets"):
    from signoffs.contrib.signets.signoffs import (
        IrrevokableSignoff,
        RevokableSignoff,
        SimpleSignoff,
    )
