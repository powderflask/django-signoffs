"""
    Some basic Approval Types backed by the Stamp model defined in this package.
"""

from signoffs.core.approvals import BaseApproval
from signoffs.core.signoffs import BaseSignoff, SignoffLogic
from signoffs.registry import register

from .models import Stamp, Signet as ApprovalSignet


def approval_signoff_form():
    """ Avoid circular imports that might arise from importing form before models are finished loading """
    from . import forms
    return forms.ApprovalSignoffForm


class ApprovalSignoffLogic(SignoffLogic):
    sign_form = approval_signoff_form


class ApprovalSignoff(BaseSignoff):
    """ An abstract, base Signoff Type backed by a ApprovalSignet - a Signet with a FK relation to an ApprovalStamp """
    signetModel = ApprovalSignet

    logic = ApprovalSignoffLogic()

    @property
    def approval(self):
        """ The approval this signoff is signed on """
        return self.signet.stamp.approval


@register(id='signoffs.simple-approval')
class SimpleApproval(BaseApproval):
    """
    A base Approval Type that can be used out-of-the-box for simple use-cases where any user can sign off
    Backed by signoffs.contrib.approvals.models.Stamp model.
    """
    stampModel = Stamp
    label = 'Approve'


@register(id='signoffs.irrevokable-approval')
class IrrevokableApproval(SimpleApproval):
    """ A SimpleApproval that can never be revoked """
    revoke_perm = False
