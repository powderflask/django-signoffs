"""
    Convenience methods for common tasks
"""
from django.http import Http404
from django.shortcuts import get_object_or_404

from signoffs import registry


def get_signet_or_404(signoff_type, signet_pk):
    """Return Signet with given pk, for the given Signoff Type or id, or raise Http404"""
    signoff = registry.get_signoff_type(signoff_type)
    if signoff is None:
        raise Http404(f"No registered signoff with id: {signoff_type}")
    return get_object_or_404(
        signoff.get_signetModel(), pk=signet_pk, signoff_id=signoff.id
    )


def get_signoff_or_404(signoff_type, signet_pk):
    """Return Signoff of given type or id, backed by Signet with the given pk, or raise Http404"""
    signet = get_signet_or_404(signoff_type, signet_pk)
    return signet.signoff


def get_approval_stamp_or_404(approval_type, stamp_pk):
    """Return ApprovalStamp instance with given pk for the given Approval Type or id, or raise Http404"""
    approval = registry.get_approval_type(approval_type)
    if approval is None:
        raise Http404(f"No registered approval with id: {approval_type}")
    return get_object_or_404(
        approval.get_stampModel(), pk=stamp_pk, approval_id=approval.id
    )


def get_approval_or_404(approval_type, stamp_pk):
    """Return Approval of given type or id, backed by StampModel with given pk, or raise Http404"""
    stamp = get_approval_stamp_or_404(approval_type, stamp_pk)
    return stamp.approval
