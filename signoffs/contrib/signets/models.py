"""
    Basic concrete implementation for Signet models
"""

from signoffs.models import (
    AbstractSignet, AbstractRevokedSignet,
)


class Signet(AbstractSignet):
    """
    A concrete persistence layer for basic Signoffs with no relations
    Suitable for use out-of-the-box with signoffs.models.SignoffOneToOneField
    """
    pass


class RevokedSignet(AbstractRevokedSignet):
    """
    A concrete persistence layer for revoked Signoffs.
    May be declared on Signoff Types to provide persistence and tracking of revoked signoffs.
    """
    pass
