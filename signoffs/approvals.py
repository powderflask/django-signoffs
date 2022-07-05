"""
    Proxy for Approval Types to simplify import statements
"""
from django.apps import apps

from signoffs.core.approvals import (
    BaseApproval
)
from signoffs.core.renderers import (
    ApprovalRenderer,
)

from signoffs.core import signing_order

if apps.is_installed("signoffs.contrib.approvals"):
    from signoffs.contrib.approvals.approvals import (
        ApprovalSignoff, SimpleApproval, IrrevokableApproval
    )
