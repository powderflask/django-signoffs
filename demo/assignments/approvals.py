from django.contrib.auth.models import User
from django.utils.functional import SimpleLazyObject

from signoffs.approvals import ApprovalSignoff, SimpleApproval
from signoffs.registry import register
from signoffs.signing_order import SigningOrder


@register("assignments.approvals.NewAssignmentApproval")
class NewAssignmentApproval(SimpleApproval):
    S = ApprovalSignoff
    label = "Signoff for New Assignment"

    assign_project_signoff = S.register(
        id="assign_project_signoff",
        label="Assign Project",
        perm="is_staff",
    )

    accept_project_signoff = S.register(
        id="accept_project_signoff",
        label="Accept Assignment",
    )

    submit_completed_signoff = S.register(
        id="submit_completed_signoff",
        label="Submit Completed",
    )

    confirm_completion_signoff = S.register(
        id="confirm_completion_signoff",
        label="Confirm Completion",
        perms="is_staff",
    )

    signing_order = SigningOrder(
        assign_project_signoff,  # pending
        accept_project_signoff,  # In-Progress
        submit_completed_signoff,  # submitted
        confirm_completion_signoff,  # completed - unrevokable?
    )

    def next_signoffs(self, for_user=None):
        if not for_user:
            return super().next_signoffs()
        if not type(for_user) in (User, SimpleLazyObject):
            raise TypeError(f"var \"for_user\" must be User instance, instead got {type(for_user)}\n")

        assignment = self.subject
        if (for_user == assignment.assigned_by and assignment.status in ['draft', 'pending_review']) or (for_user == assignment.assigned_to and assignment.status in ['requested', 'in_progress']):
            return super().next_signoffs(for_user=for_user)
        else:
            return []

