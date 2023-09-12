"""
    contrib.approvals adds basic concrete ApprovalStamp-related models, signoffs, and approvals.
"""
from django.apps import AppConfig


class ContribApprovalsConfig(AppConfig):
    name = "signoffs.contrib.approvals"
    label = "signoffs_approvals"
    default = True
    default_auto_field = "django.db.models.BigAutoField"
