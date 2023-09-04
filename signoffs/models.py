"""
    Proxy for core.models to simplify import statements
"""
from django.apps import apps

from signoffs.core.models import (
    AbstractSignet, AbstractRevokedSignet,
    AbstractApprovalSignet, AbstractApprovalStamp,
)

from signoffs.core.models.fields import (
    SignoffField, SignoffSet, SignoffSingle,
    ApprovalSignoffSet, ApprovalSignoffSingle,
    RelatedSignoffDescriptor as RelatedSignoff,
    ApprovalField,
    RelatedApprovalDescriptor as RelatedApproval,
)

if apps.is_installed("signoffs.contrib.signets"):
    from signoffs.contrib.signets.models import (
        Signet, RevokedSignet,
    )

if apps.is_installed("signoffs.contrib.approvals"):
    from signoffs.contrib.approvals.models import (
        Signet as ApprovalSignet, RevokedSignet as RevokedApprovalSignet,
        Stamp
    )
