"""
    Objects that know how to assess the status of an Approval
"""
from signoffs.core import utils


class ApprovalInstanceStatus:
    """Access status info about an Approval instance"""

    def __init__(self, approval_instance, **kwargs):
        """A status instance for given approval instance"""
        self.approval = approval_instance

    # Note: there is an intermediate state in which a pre-condition to approval is not yet met,
    #       so the approval is not yet "awaiting".  Controlled at approval-process level, not available on approval.
    def get_status(self):
        """Return a short status indicator, e.g., for use as a CSS class, dictionary key, etc."""
        return "complete" if self.approval.is_approved() else "awaiting"

    def get_label(self):
        """Return a string with a pithy label indicating the status of the approval."""
        return (
            "Approval Complete" if self.approval.is_approved() else "Awaiting Approval"
        )

    def get_css_class(self):
        """Return a CSS class used, e.g., to style the approval label in templates"""
        return "success" if self.approval.is_approved() else "warning"


class ApprovalStatus(utils.service(ApprovalInstanceStatus)):
    """
    A descriptor that "injects" a ApprovalInstanceStatus instance into a Approval instance.

    To inject custom rendering services:
      - provide a custom service_class:  `status=ApprovalStatus(service_class=MyInstanceStatus)`
      - OR specialize class attributes:
        `MyApprovalStatus = utils.service(ApprovalInstanceStatus, signet_template='my.tmpl.html')`
      - OR both... `MyApprovalStatus = utils.service(MyInstanceStatus)`

    """
