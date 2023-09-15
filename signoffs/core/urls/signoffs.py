"""
It can be very convenient for a signoff to know the endpoints to POST / DELETE their `Signet`.
In fact, the default renderers assume a signoff knows the URLs for sign and revoke requests.

This component can be extended to provide flexible url services to `Signoff` instances.
They are generally "injected" into the Signoff Type using a `SignoffUrlsManager` service descriptor
"""

from django.urls import reverse

from signoffs.core.utils import service


class SignoffInstanceUrls:
    """
    Defines the urls for Signing and Revoking a Signoff instance
    """

    # Define URL patterns for saving and revoking signoffs
    save_url_name: str = ""
    revoke_url_name: str = ""

    def __init__(self, signoff_instance, save_url_name=None, revoke_url_name=None):
        """Override default actions, or leave parameter None to use class default"""
        self.signoff = signoff_instance
        self.save_url_name = save_url_name or self.save_url_name
        self.revoke_url_name = revoke_url_name or self.revoke_url_name

    def get_save_url(self, args=None, kwargs=None):
        """Return the URL for requests to save the signoff"""
        args = args or ()
        kwargs = kwargs or {}
        return (
            reverse(self.save_url_name, args=args, kwargs=kwargs)
            if self.save_url_name
            else ""
        )

    def get_revoke_url(self, args=None, kwargs=None):
        """Return the URL for requests to revoke this signoff"""
        args = args or (self.signoff.signet.pk,)
        kwargs = kwargs or {}
        return (
            reverse(self.revoke_url_name, args=args, kwargs=kwargs)
            if self.revoke_url_name
            else ""
        )


class SignoffUrlsManager(service(SignoffInstanceUrls)):
    """
    A descriptor class that "injects" a SignoffInstanceUrls instance into a Signoff instance.

    To inject custom URL services:
      - provide a custom service_class:  `urls=SignoffUrlsManager(service_class=MyInstanceUrls)`
      - OR specialize class attributes:
        `SignoffUrlsManager = utils.service(SignoffInstanceUrls, revoke_url_name="my:app:revoke_view")`
      - OR both... `SignoffUrlsManager = utils.service(MyInstanceUrls)`

    """
