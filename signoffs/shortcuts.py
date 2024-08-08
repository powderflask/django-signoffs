"""
    Convenience methods for common tasks
"""
from __future__ import annotations
from typing import TYPE_CHECKING

from django.http import Http404
from django.shortcuts import get_object_or_404

from signoffs import registry

if TYPE_CHECKING:
    from signoffs.core.signoffs import AbstractSignoff
    from signoffs.core.models.signets import AbstractSignet
    from signoffs.core.models.stamps import AbstractApprovalStamp
    from signoffs.core.approvals import AbstractApproval


def get_signet_or_404(signoff_type, signet_pk):
    """Return Signet with given pk, for the given Signoff Type or id, or raise Http404"""
    kwargs.update(pk=signet_pk) if signet_pk else None
    signoff = registry.get_signoff_type(signoff_type)
    if signoff is None:
        raise Http404(f"No registered signoff with id: {signoff_type}")
    kwargs.update(signoff_id=signoff.id)
    return get_object_or_404(
        signoff.get_signetModel(), **kwargs
    )


def get_signoff_or_404(signoff_type: str | AbstractSignoff, signet_pk=None, **kwargs) -> AbstractSignoff:
    """Return Signoff of given type or id, backed by Signet with the given pk, or raise Http404"""
    kwargs.update(pk=signet_pk) if signet_pk else None
    signet = get_signet_or_404(signoff_type, **kwargs)
    return signet.signoff


def get_approval_stamp_or_404(approval_type: str | AbstractApproval, stamp_pk=None, **kwargs) -> AbstractApprovalStamp:
    """Return ApprovalStamp instance with given pk for the given Approval Type or id, or raise Http404"""
    kwargs.update(pk=stamp_pk) if stamp_pk else None
    approval = registry.get_approval_type(approval_type)
    if approval is None:
        raise Http404(f"No registered approval with id: {approval_type}")
    kwargs.update(approval_id=approval.id)
    return get_object_or_404(
        approval.get_stampModel(), **kwargs
    )


def get_approval_or_404(approval_type: str | AbstractApproval, stamp_pk=None, **kwargs) -> AbstractApproval:
    """Return Approval of given type or id, backed by StampModel with given pk, or raise Http404"""
    kwargs.update(pk=stamp_pk) if stamp_pk else None
    stamp = get_approval_stamp_or_404(approval_type, **kwargs)
    return stamp.approval
