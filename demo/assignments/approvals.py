from signoffs.approvals import ApprovalSignoff, SimpleApproval
from signoffs.models import ApprovalSignet
from signoffs.registry import register
from signoffs.signing_order import SigningOrder


@register("assignments.approvals.NewAssignmentApproval")
class NewAssignmentApproval(SimpleApproval):
    S = ApprovalSignoff
    label = "Signoff for New Assignment"

    assign_project_signoff = S.register(
        signetModel=ApprovalSignet,
        id="assign_project_signoff",
        label="Assign Project",
        perm="is_staff",
    )

    accept_project_signoff = S.register(
        signetModel=ApprovalSignet,
        id="accept_project_signoff",
        label="Accept Assignment",  # Add perm to check that the user is the assignee?
    )

    submit_completed_signoff = S.register(
        signetModel=ApprovalSignet,
        id="submit_completed_signoff",
        label="Submit Completed",  # Add perm to check that the user is the assignee?
    )

    confirm_completion_signoff = S.register(
        signetModel=ApprovalSignet,
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
