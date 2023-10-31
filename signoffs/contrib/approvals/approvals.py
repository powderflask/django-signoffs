"""
    Some basic Approval Types backed by the Stamp model defined in this package.
"""

from signoffs.core.approvals import ApprovalLogic, BaseApproval
from signoffs.core.forms import SignoffFormsManager
from signoffs.core.signoffs import BaseSignoff
from signoffs.registry import register

from .models import Signet as ApprovalSignet
from .models import Stamp


def approval_signoff_form():
    """Avoid circular imports that might arise from importing form before models are finished loading"""
    from . import forms

    return forms.ApprovalSignoffForm


class ApprovalSignoff(BaseSignoff):
    """An abstract, base Signoff Type backed by a ApprovalSignet - a Signet with a FK relation to an ApprovalStamp"""

    signetModel = ApprovalSignet

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

    # Encode "irrevocable" in Approval business logic...
    logic = ApprovalLogic(revoke_perm=False)
