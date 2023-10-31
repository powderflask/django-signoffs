"""
Concrete models, signoffs, approvals, etc. used by  test suite
"""
import django.forms
from django.db import models

import signoffs.core.signing_order as so
from signoffs.core.approvals import BaseApproval
from signoffs.core.forms import AbstractSignoffForm, SignoffFormsManager
from signoffs.core.models import (
    AbstractApprovalSignet,
    AbstractApprovalStamp,
    AbstractRevokedSignet,
    AbstractSignet,
)
from signoffs.core.models.fields import ApprovalField, SignoffField, SignoffSet
from signoffs.core.signoffs import BaseSignoff
from signoffs.registry import register

# Concrete Signet Models


class Signet(AbstractSignet):
    pass


class RevokedSignet(AbstractRevokedSignet):
    pass


class OtherSignet(AbstractSignet):
    pass


class LeaveSignet(AbstractSignet):
    object = models.ForeignKey(
        "signoffs.LeaveRequest", on_delete=models.CASCADE, related_name="signatories"
    )


class RevokedLeaveSignet(AbstractRevokedSignet):
    signet = models.OneToOneField(
        LeaveSignet, on_delete=models.CASCADE, related_name="revoked"
    )


class ApprovalSignet(AbstractApprovalSignet):
    pass


class RevokedApprovalSignet(AbstractRevokedSignet):
    signet = models.OneToOneField(
        "ApprovalSignet", on_delete=models.CASCADE, related_name="revoked"
    )


# Signoffs backed by the Signet models above


class BasicSignoff(BaseSignoff):
    signetModel = Signet
    label = "Consent?"


simple_signoff_type = BasicSignoff.register(id="test.signoffs.simple_signoff")


class RevokableSignoff(BasicSignoff):
    revokeModel = RevokedSignet


simple_revokable_signoff_type = RevokableSignoff.register(
    id="test.signoffs.simple_revokable_signoff"
)


def approval_signoff_form():
    class ApprovalSignoffForm(AbstractSignoffForm):
        """Form for collecting approval signoffs"""

        class Meta(AbstractSignoffForm.Meta):
            model = ApprovalSignet
            widgets = {"stamp": django.forms.HiddenInput}

    return ApprovalSignoffForm


class ApprovalSignoff(BaseSignoff):
    signetModel = ApprovalSignet
    revokeModel = RevokedApprovalSignet
    forms = SignoffFormsManager(signoff_form=approval_signoff_form)


class LeaveSignoff(BaseSignoff):
    signetModel = "signoffs.LeaveSignet"
    revokeModel = "signoffs.RevokedLeaveSignet"
    label = "Consent?"


class InvalidModel(models.Model):
    invalid_signet = SignoffSet("test.signoffs.simple_signoff")
    invalid_relation = SignoffSet("test.approval.leave.employee_signoff")


# Concrete Stamp models


class Stamp(AbstractApprovalStamp):
    pass


class OtherStamp(AbstractApprovalStamp):
    pass


# A LeaveRequest model with a LeaveApproval process defined in 2 different ways


class AbstractLeaveApproval(BaseApproval):
    stampModel = Stamp


@register(id="test.approval.fields.leave_approval")
class LeaveApproval(AbstractLeaveApproval):
    label = "Approve Leave of Absence"

    employee_signoff_type = ApprovalSignoff.register(
        id="test.approval.leave.employee_signoff"
    )
    hr_signoff_type = ApprovalSignoff.register(id="test.approval.leave.hr_signoff")
    mngmt_signoff_type = ApprovalSignoff.register(
        id="test.approval.leave.mngmt_signoff"
    )

    signing_order = so.SigningOrder(
        employee_signoff_type, so.AtLeastN(hr_signoff_type, n=1), mngmt_signoff_type
    )


class LeaveRequest(models.Model):
    """Demonstrates 2 ways to manage a group of signoffs on a model (wouldn't normally use both!!)"""

    # (1) directly on the Model class (signing order is managed by model business logic) (e.g., see signoff tests)
    employee_signoff_type = BasicSignoff.register(id="test.leave.employee_signoff")
    hr_signoff_type = LeaveSignoff.register(id="test.leave.hr_signoff")
    mngmt_signoff_type = LeaveSignoff.register(id="test.leave.mngmt_signoff")

    # One-to-One "forward" relation - the OneToOneField is named employee_signet
    employee_signoff, employee_signet = SignoffField(employee_signoff_type)
    # One-to-Many "reverse" relation based on relation defined by LeaveSignet
    hr_signoffs = SignoffSet(hr_signoff_type)
    mngmt_signoffs = SignoffSet(mngmt_signoff_type)

    # (2) a One-to-One "forward" approval relation (managed by the Approval.signing_order) (e.g., see approval tests)
    approval, approval_stamp = ApprovalField(LeaveApproval)
