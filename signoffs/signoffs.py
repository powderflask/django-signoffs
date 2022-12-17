"""
    Proxy for Signoff Types to simplify import statements
"""
from django.apps import apps

from signoffs.core.forms import (
    SignoffTypeForms, SignoffFormsManager
)

from signoffs.core.signoffs import (
    BaseSignoff, SignoffLogic,
)

from signoffs.core.renderers import (
    SignoffInstanceRenderer, SignoffRenderer,
)

from signoffs.core.urls import (
    SignoffInstanceUrls, SignoffUrlsManager,
)

if apps.is_installed("signoffs.contrib.signets"):
    from signoffs.contrib.signets.signoffs import (
        SimpleSignoff, RevokableSignoff,
    )
