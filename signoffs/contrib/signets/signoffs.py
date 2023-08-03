"""
    Some basic Signoff Types backed by the Signet models defined in this package
"""

from signoffs.registry import register
from signoffs.core.signoffs import BaseSignoff, SignoffLogic
from .models import Signet, RevokedSignet


@register(id='signoffs.simple-signoff')
class SimpleSignoff(BaseSignoff):
    """
    A basic Signoff Type that can be used out-of-the-box for simple use-cases where any user can sign off.
    Uses Default Signoff Business Logic - unrestricted: anyone can sign or revoke.
    Backed by signoffs.contrib.signets.models.Signet model.
    """
    signetModel = Signet
    revokeModel = None               # revoking a SimpleSignoff just deletes it
    label = 'I consent'


@register(id='signoffs.revokable-signoff')
class RevokableSignoff(SimpleSignoff):
    """ A SimpleSignoff that stores a "receipt" when a signoff is revoked """
    revokeModel = RevokedSignet


@register(id='signoffs.irrevokable-signoff')
class IrrevokableSignoff(SimpleSignoff):
    """ A SimpleSignoff that can never be revoked """
    revoke_perm = False
    logic = SignoffLogic(perm=None, revoke_perm=False)  # restrict revoke
