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
            return f"{name} ({self.assigned_to.username})"
        else:
            return self.assigned_to.username

    def assigner(self):
        name = self.assigned_by.get_full_name()
        if name:
            return f"{name} ({self.assigned_by.username})"
        else:
            return self.assigned_by.username

    def bump_status(self, commit=True, increase: bool = True):
        direction = 1 if increase else -1  # [-1, 1][increase]  # 1 if increase else - 1
        current_index = self.STATUS_OPTS.index([status for status in self.STATUS_OPTS if status[0] == self.status][0])
        num_opts = len(self.STATUS_OPTS)
        if num_opts - 1 == current_index and increase:
            self.status = self.STATUS_OPTS[num_opts - 1][0]  # Don't go past the last index
        else:
            self.status = self.STATUS_OPTS[current_index + direction][0]
        if commit:
            self.save()

    def erase_progress(self):
        self.approval.stamp.delete()
        self.approval_stamp = None
        self.status = self.STATUS_OPTS[0][0]
        self.save()


