"""
    Basic concrete implementations for ApprovalStamp related models
"""

from signoffs.core.models import (
    AbstractApprovalSignet,
    AbstractApprovalStamp,
    AbstractRevokedSignet,
)


class Signet(AbstractApprovalSignet):
    """A concrete persistence layer for a basic Signet with a relation to an ApprovalStamp"""

    pass


class RevokedSignet(AbstractRevokedSignet):
    """
    A concrete persistence layer for tracking revoked Approval Signets.
    May be declared on Approval Types to provide persistence / tracking of revoked signoffs.
    """

    pass


class Stamp(AbstractApprovalStamp):
    """A concrete persistence layer for basic Approval Types"""

    pass
