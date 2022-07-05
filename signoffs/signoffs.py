"""
    Proxy for Signoff Types to simplify import statements
"""
from django.apps import apps

from signoffs.core.signoffs import (
    BaseSignoff,
)

from signoffs.core.renderers import (
    SignoffRenderer,
)

if apps.is_installed("signoffs.contrib.signets"):
    from signoffs.contrib.signets.signoffs import (
        SimpleSignoff, RevokableSignoff,
    )
