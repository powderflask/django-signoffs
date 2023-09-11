"""
    Proxy for core.models to simplify import statements and hide core package structure from client code.

    isort:skip_file
"""
from django.apps import apps

from signoffs.core.models import (
    AbstractApprovalSignet,
    AbstractApprovalStamp,
    AbstractRevokedSignet,
    AbstractSignet,
)
from signoffs.core.models.fields import (
    ApprovalField,
    ApprovalSignoffSet,
    ApprovalSignoffSingle,
)
from signoffs.core.models.fields import RelatedApprovalDescriptor as RelatedApproval
from signoffs.core.models.fields import RelatedSignoffDescriptor as RelatedSignoff
from signoffs.core.models.fields import SignoffField, SignoffSet, SignoffSingle

if apps.is_installed("signoffs.contrib.signets"):
    from signoffs.contrib.signets.models import RevokedSignet, Signet

if apps.is_installed("signoffs.contrib.approvals"):
    from signoffs.contrib.approvals.models import RevokedSignet as RevokedApprovalSignet
    from signoffs.contrib.approvals.models import Signet as ApprovalSignet
    from signoffs.contrib.approvals.models import Stamp
