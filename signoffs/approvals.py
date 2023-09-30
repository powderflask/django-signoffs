"""
    Proxy for Approval Types to simplify import statements and hide core package structure from client code.

    isort:skip_file
"""
from django.apps import apps

from signoffs.core import signing_order

from signoffs.core.approvals import (
    AbstractApproval,
    ApprovalLogic,
    BaseApproval,
)
from signoffs.core.renderers import (
    ApprovalInstanceRenderer,
    ApprovalRenderer,
)
from signoffs.core.status import (
    ApprovalInstanceStatus,
    ApprovalStatus,
)
from signoffs.core.urls import (
    ApprovalInstanceUrls,
    ApprovalUrlsManager,
)

if apps.is_installed("signoffs.contrib.approvals"):
    from signoffs.contrib.approvals.approvals import (
        ApprovalSignoff,
        IrrevokableApproval,
        SimpleApproval,
    )
