"""
Permissions logic
"""
from .signoffs import terms_signoff


def has_signed_terms(user):
    """Return True iff the user has signed ToS"""
    signoff = terms_signoff.get(user=user)
    return signoff.is_signed()
