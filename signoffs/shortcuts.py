"""
    Convenience methods for common tasks
"""
from django.http import Http404
from django.shortcuts import get_object_or_404

from signoffs import registry


def get_signet_or_404(signoff_id, signet_pk):
    """ return Signet with given pk for the given Signoff Type or raise Http404 """
    signoff = registry.signoffs.get(signoff_id)
    if signoff is None:
        raise Http404('No registered signoff with id: {}'.format(signoff_id))
    return get_object_or_404(signoff.get_signetModel(), pk=signet_pk, signoff_id=signoff_id)


def get_approval_stamp_or_404(approval_id, stamp_pk):
    """ return ApprovalStamp instance with given pk for the given Approval Type or raise Http404 """
    approval = registry.approvals.get(approval_id)
    if approval is None:
        raise Http404('No registered approval with id: {}'.format(approval_id))
    return get_object_or_404(approval.get_stampModel(), pk=stamp_pk, approval_id=approval_id)
