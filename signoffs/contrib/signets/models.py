"""
    Basic concrete implementation for Signet models
"""

from signoffs.models import AbstractRevokedSignet, AbstractSignet


class Signet(AbstractSignet):
    """
    A concrete persistence layer for basic Signoffs with no relations.

    Suitable for out-of-the-box use with `signoffs.models.SignoffField`
    """

    pass


class RevokedSignet(AbstractRevokedSignet):
    """
    A concrete persistence layer for revoked Signoffs.

    May be declared on Signoff Types to provide persistence and tracking of revoked signoffs.
    """

    pass
