from django.contrib.auth.models import User
from django.utils.functional import SimpleLazyObject

from signoffs.approvals import ApprovalSignoff, ApprovalRenderer, SimpleApproval
from signoffs.signoffs import SignoffRenderer, SignoffUrlsManager
from signoffs.registry import register
from signoffs.signing_order import SigningOrder


@register("assignments.approvals.NewAssignmentApproval")
class NewAssignmentApproval(SimpleApproval):
    render = ApprovalRenderer(approval_template="assignments/htmx_signoffs/approval.html")
    label = "Signoff for New Assignment"

    S = ApprovalSignoff
    S.render = SignoffRenderer(
        signoff_form_template="assignments/htmx_signoffs/signoff_form.html",
        signet_template="assignments/htmx_signoffs/signet.html",
    )
    S.urls = SignoffUrlsManager(
        save_url_name="assignment:sign-signoff",
        revoke_url_name="assignment:revoke-signoff",
    )


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

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def next_signoffs(self, for_user=None):
        if not for_user:
            return super().next_signoffs()
        if not type(for_user) in (User, SimpleLazyObject):
            raise TypeError(f"var \"for_user\" must be User instance, instead got {type(for_user)}\n")
        if not self.subject:

            raise ValueError(
                f"No Assignment found as subject in {self.id}. Must have subject to check sequential sign perm."
            )
        assignment = self.subject
        if (
                (for_user == assignment.assigned_by and assignment.status in ['draft', 'pending_review'])
                or (for_user == assignment.assigned_to and assignment.status in ['requested', 'in_progress'])
                or for_user.is_superuser  # FIXME: overwritten for simpler ui testing
        ):
            return super().next_signoffs(for_user=for_user)
        else:
            return []
