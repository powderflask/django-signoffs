from django.contrib.auth.models import User
from django.db import models

from signoffs.models import ApprovalField
from .approvals import NewAssignmentApproval


class Assignment(models.Model):
    STATUS_OPTS = (
        ("draft", "Draft"),
        ("requested", "Requested"),
        ("in_progress", "In Progress"),
        ("pending_review", "Pending Review"),
        ("completed", "Completed"),
        )
    assignment_name = models.CharField(max_length=200)
    assigned_by = models.ForeignKey(User, on_delete=models.CASCADE, null=True, related_name="created_assignment")
    assigned_to = models.ForeignKey(User, on_delete=models.CASCADE, null=True, related_name="received_assignment")
    status = models.CharField(max_length=15, null=False, default=STATUS_OPTS[0][0], choices=STATUS_OPTS)
    details = models.TextField(max_length=1000)
    approval, approval_stamp = ApprovalField(NewAssignmentApproval)

    def assignee(self):
        name = self.assigned_to.get_full_name()
        if name:
            return name
        else:
            return self.assigned_to.username

    def bump_status(self, commit=True):
        current_index = self.STATUS_OPTS.index([status for status in self.STATUS_OPTS if status[0] == self.status][0]) #TODO: implement cleaner way of getting current index
        num_opts = len(self.STATUS_OPTS)
        if num_opts <= current_index + 1:
            self.status = self.STATUS_OPTS[num_opts - 1][0]
        else:
            self.status = self.STATUS_OPTS[current_index + 1][0]
        if commit:
            self.save()
