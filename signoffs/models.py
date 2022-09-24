"""
    Proxy for core.models to simplify import statements
"""
from django.apps import apps

from signoffs.core.models import (
    AbstractSignet, AbstractRevokedSignet,
)

from signoffs.core.models.fields import (
    SignoffField, SignoffSet, SignoffSingle,
    RelatedSignoffDescriptor as RelatedSignoff,
)

from signoffs.core.models import (
    AbstractApprovalStamp, AbstractApprovalSignet,
)

from signoffs.core.models.fields import (
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
