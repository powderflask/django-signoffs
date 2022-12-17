"""
django-signoffs does not provide any views or url mappings.
However, it can be very convenient for a signoff or approval to know the URL's used to manipluate them.
In fact, even the default renders assume a signoff knows the URL for submiting sign and revoke requests.

These components can be extended to provide flexible url services to signoff and approval instances.
They are generally "injected" into the Signoff or Approval Type using a service descriptor
"""
from django.urls import reverse

from signoffs.core.utils import service


class SignoffInstanceUrls:
    """
    Defines the urls for Signing and Revoking a Signoff instance
    """
    # Define URL patterns for saving and revoking signoffs
    save_url_name: str = ''
    revoke_url_name: str = ''

    def __init__(self, signoff_instance, save_url_name=None, revoke_url_name=None):
        """ Override default actions, or leave parameter None to use class default """
        self.signoff = signoff_instance
        self.save_url_name = save_url_name or self.save_url_name
        self.revoke_url_name = revoke_url_name or self.revoke_url_name

    def get_save_url(self, args=None, kwargs=None):
        """ Return the URL for requests to save the signoff """
        args = args or ()
        kwargs = kwargs or {}
        return reverse(self.save_url_name, args=args, kwargs=kwargs) if self.save_url_name else ''

    def get_revoke_url(self, args=None, kwargs=None):
        """ Return the URL for requests to revoke this signoff """
        args = args or (self.signoff.signet.pk,)
        kwargs = kwargs or {}
        return reverse(self.revoke_url_name, args=args, kwargs=kwargs) if self.revoke_url_name else ''


"""
A descriptor class that "injects" a SignoffInstanceUrls instance into a Signoff instance.
To inject custom urls services:
  - provide a custom service_class:  SignoffUrls(service_class=MyInstanceUrls);
  - OR specialize class attributes: MyUrls = utils.service(SignoffInstanceUrls, save_url_name='my:app:sigoff:save')
  - OR both... MyUrls = utils.service(MyInstanceUrls)
"""
SignoffUrlsManager = service(SignoffInstanceUrls)


class ApprovalInstanceUrls:
    """
    Defines the urls for Signing and Revoking an Approval instance
    """
    # Define URL patterns for revoking approvals
    revoke_url_name: str = ''

    def __init__(self, approval_instance, revoke_url_name=None):
        """ Override default actions, or leave parameter None to use class default """
        self.approval = approval_instance
        self.revoke_url_name = revoke_url_name or self.revoke_url_name

    def get_revoke_url(self, args=None, kwargs=None):
        """ Return the URL for requests to revoke the approval """
        args = args or [self.approval.stamp.pk, ]
        kwargs = kwargs or {}
        return reverse(self.revoke_url_name, args=args, kwargs=kwargs) if self.revoke_url_name else ''


"""
A descriptor class that "injects" a ApprovalInstanceUrls instance into a Approval instance.
see SignoffUrls for ways to extend / customize this service
"""
ApprovalUrlsManager = service(ApprovalInstanceUrls)
