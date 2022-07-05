"""
    Some basic Signoff Types backed by the Signet models defined in this package
"""

from signoffs.registry import register
from signoffs.core.signoffs import BaseSignoff
from .models import Signet, RevokedSignet


@register(id='signoffs.simple-signoff')
class SimpleSignoff(BaseSignoff):
    """
    A basic Signoff Type that can be used out-of-the-box for simple use-cases where any user can sign off
    Backed by signoffs.contrib.signets.models.Signet model.
    """
    signetModel = Signet
    revokeModel = None               # revoking a SimpleSignoff just deletes it
    perm = None                      # unrestricted - any user can sign this
    label = 'I consent'


@register(id='signoffs.revokable-signoff')
class RevokableSignoff(SimpleSignoff):
    """ A SimpleSignoff that stores a "receipt" when a signoff is revoked """
    revokeModel = RevokedSignet
    revoke_perm = None               # same permission to sign the Signoff also used to revoke it


@register(id='signoffs.irrevokable-signoff')
class IrrevokableSignoff(SimpleSignoff):
    """ A SimpleSignoff that can never be revoked """
    revoke_perm = False
