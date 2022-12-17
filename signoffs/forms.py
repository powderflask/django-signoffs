"""
Proxy for signoffs.core.forms to simplify import statements
"""
from django.apps import apps

from signoffs.core.forms import (
    AbstractSignoffForm, signoff_form_factory,
    AbstractSignoffRevokeForm, revoke_form_factory,
    SignoffTypeForms, SignoffFormsManager
)

if apps.is_installed("signoffs.contrib.approvals"):
    from signoffs.contrib.approvals.forms import (
        ApprovalSignoffForm,
    )
