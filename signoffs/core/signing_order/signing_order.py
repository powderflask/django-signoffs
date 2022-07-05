"""
    Signoff sequence ordering automation, based on pattern matching Signoff instances to expected Types.
"""
from django.core.exceptions import ImproperlyConfigured

from signoffs.core.signoffs import AbstractSignoff
from . import signoff_pattern as pm


def validate_signing_order_pattern(pattern):
    """ Raise Improperly configured if the given signing order pattern is not valid. """
    terms = list(pattern.terms())
    if not len(terms) > 0 and not all(issubclass(AbstractSignoff, t) for t in terms):
        raise ImproperlyConfigured('SigningOrder: at least one pattern term required; all terms must be Signoff Types')
    # The following constraint is not needed in theory, but is a practical and performance reality
    if not all(a.get_signetModel() == b.get_signetModel() for a, b in zip(terms, terms[1:])):
        raise ImproperlyConfigured('SigningOrder: all pattern Signoff Types must share the same Signet model.')
    return True


class SigningOrderManager:
    """
    Match a pattern of Signoff Types defining a "signing order" against a signets queryset.
    match result object can answer questions like:
        - does the sequence of signoffs satisfy the pattern defined; and
        - what SignoffType(s) could be added to the sequence next?
    """
    def __init__(self, pattern: pm.SigningOrderPattern, signets_queryset):
        """
        Match the signets queryset against the Singing Order pattern
        signet_set must be ordered chronologically (by timestamp), which is default ordering for Signet
        """
        validate_signing_order_pattern(pattern)
        self.pattern = pattern
        self.signets_queryset = signets_queryset

    @property
    def match(self):
        """ Return a pm.MatchResult object for matching pattern against queryset (lazy evaluation) """
        return self.pattern.match(*list(self.signets_queryset))


class SigningOrder:
    def __init__(self, *pattern, signet_set_accessor='signatories'):
        """
        Pattern object is a sequence of Signoff Types defining the signing order, typically for an Approval.
        This descriptor injects a SigningOrderManager object to manage the signing order for an instance.
        signet_set_accessor is string with name of callable or attribute for a Signets manager on that instance.
        """
        pattern = pattern if len(pattern) == 1 and isinstance(pattern[0], pm.SigningOrderPattern) else \
            pm.InSeries(*pattern)
        validate_signing_order_pattern(pattern)
        self.pattern = pattern
        self.signet_set_accessor = signet_set_accessor

    def __get__(self, instance, owner=None):
        """
        Use the enclosing instance to instantiate and return a SigningOrderManager for the instance.signet_set
        """
        if instance is None:  # class access - nada - nothing useful?
            return self
        else:  # return a SigningOrderManager to match this SigningOrder against the instance's signet_set
            signet_set_accessor = getattr(instance, self.signet_set_accessor)
            signoffs_pattern = SigningOrderManager(pattern=self.pattern, signets_queryset=signet_set_accessor.all())
            return signoffs_pattern
