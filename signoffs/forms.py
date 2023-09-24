"""
Proxy for signoffs.core.forms to simplify import statements and hide core package structure from client code.

    isort:skip_file
"""
from django.apps import apps

from signoffs.core.forms import (
    AbstractSignoffForm,
    AbstractSignoffRevokeForm,
    SignoffFormsManager,
    SignoffTypeForms,
    revoke_form_factory,
    signoff_form_factory,
)

if apps.is_installed("signoffs.contrib.approvals"):
    from signoffs.contrib.approvals.forms import ApprovalSignoffForm
