"""
It can be very convenient for an approval to know the endpoint used to DELETE its `Stamp`.
In fact, the default renderers assume an approval knows the URL for revoke requests.

This component can be extended to provide flexible url services to approval instances.
They are generally "injected" into the Approval Type using a `ApprovalUrlsManager` service descriptor
"""
from django.urls import reverse

from signoffs.core.utils import service


class ApprovalInstanceUrls:
    """
    Defines the urls for Revoking an Approval instance
    """

    # Define URL patterns for revoking approvals
    revoke_url_name: str = ""

    def __init__(self, approval_instance, revoke_url_name=None):
        """Override default actions, or leave parameter None to use class default"""
        self.approval = approval_instance
        self.revoke_url_name = revoke_url_name or self.revoke_url_name

    def get_revoke_url(self, args=None, kwargs=None):
        """Return the URL for requests to revoke the approval"""
        args = args or [
            self.approval.stamp.pk,
        ]
        kwargs = kwargs or {}
        return (
            reverse(self.revoke_url_name, args=args, kwargs=kwargs)
            if self.revoke_url_name
            else ""
        )


class ApprovalUrlsManager(service(ApprovalInstanceUrls)):
    """
    A descriptor class that "injects" a ApprovalInstanceUrls instance into a Approval instance.

    To inject custom URL services:
      - provide a custom service_class:  `urls=ApprovalUrlsManager(service_class=MyInstanceUrls)`
      - OR specialize class attributes:
        `MyApprovalUrlsManager = utils.service(ApprovalInstanceUrls, revoke_url_name="my:app:revoke_view")`
      - OR both... `ApprovalUrlsManager = utils.service(MyInstanceUrls)`

    """
