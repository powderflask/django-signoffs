"""
    Some basic Approval Types backed by the Stamp model defined in this package.
"""

from signoffs.core.approvals import BaseApproval
from signoffs.core.forms import SignoffFormsManager
from signoffs.core.signoffs import BaseSignoff, SignoffLogic
from signoffs.registry import register

from .models import Signet as ApprovalSignet
from .models import Stamp


def approval_signoff_form():
    """Avoid circular imports that might arise from importing form before models are finished loading"""
    from . import forms

    return forms.ApprovalSignoffForm


class ApprovalSignoffLogic(SignoffLogic):
    """
    Logic specific to Signoffs related to an Approval
    No checks here for ordering - if your approval uses SigningOrder, add logic to verify signoff is next / last
    """

    @staticmethod
    def _is_approved(approval):
        return approval.is_approved() if approval is not None else False

    def can_sign(self, signoff, user):
        """Can't sign an approved approval"""
        return super().can_sign(signoff, user) and not self._is_approved(
            signoff.approval
        )

    def can_revoke(self, signoff, user):
        """Can't revoke a signoff from an approved approval (got to revoke the whole approval)"""
        return super().can_revoke(signoff, user) and not self._is_approved(
            signoff.approval
        )


class ApprovalSignoff(BaseSignoff):
    """An abstract, base Signoff Type backed by a ApprovalSignet - a Signet with a FK relation to an ApprovalStamp"""

    signetModel = ApprovalSignet

    logic = ApprovalSignoffLogic()

    forms = SignoffFormsManager(signoff_form=approval_signoff_form)

    @property
    def subject(self):
        """Subject is the approval being signed off on."""
        return self._subject or self.signet.stamp.approval

    @subject.setter
    def subject(self, subject):
        self._subject = subject

    @property
    def approval(self):
        """friendly name for subject"""
        return self.subject


@register(id="signoffs.simple-approval")
class SimpleApproval(BaseApproval):
    """
    A base Approval Type that can be used out-of-the-box for simple use-cases where any user can sign off
    Backed by signoffs.contrib.approvals.models.Stamp model.
    """

    stampModel = Stamp
    label = "Approve"


@register(id="signoffs.irrevokable-approval")
class IrrevokableApproval(SimpleApproval):
    """A SimpleApproval that can never be revoked"""

    revoke_perm = False
