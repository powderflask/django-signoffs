"""
    Signoff sequence ordering automation, based on pattern matching Signoff instances to expected Types.
"""
from typing import Protocol

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


class SigningOrderProtocol(Protocol):
    """ Protocol for defining the API required to define a signing order for a sequence of signoffs """

    def next_signoffs(self) -> list:
        """ Return a list of the next Signoff Type(s) available for signing in this signing order """
        ...

    def is_complete(self) -> bool:
        """ Return True iff this signing order is complete (all required signoffs have been signed) """
        ...


class SigningOrderPatternMatcher:
    """
    Match a pattern of Signoff Types defining a "signing order" against a signets queryset.
    Implements SigningOrderProtocol
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

    def next_signoffs(self) -> list:
        """ Return a list of the next Signoff Type(s) available for signing in this signing order """
        return self.match.next

    def is_complete(self) -> bool:
        """ Return True iff this signing order is complete (all required signoffs have been signed) """
        return self.match.is_complete



class SigningOrder:
    """
    A descriptor used to "inject" instances of a SigningOrderProtocol "service" class into its owner's instances.
    The serivce_class provides a strategy for sequencing the owner's signoffs (signet_set).
    """
    default_service_class = SigningOrderPatternMatcher  # default service is a general-purpose pattern matcher

    def __init__(self, *pattern, signet_set_accessor='signatories', service_class=None):
        """
        This descriptor injects a SigningOrderProtocol object to manage the signing order for the owner's signet_set
        pattern is a sequence of SigningOrderPattern objects (or Signoff Types, which are also legal Pattern tokens)
            defining the signing order, typically for an Approval, but any kind of owner object.
        pattern is passed directly through to the signing_order_service constructor, so could, in theory, be anything.
        signet_set_accessor is string with name of callable or attribute for a Signets manager on that owner instance.
        service_class allows this descriptor to be re-used with other implementations of SigningOrderProtocol
        """
        pattern = pattern if len(pattern) == 1 and isinstance(pattern[0], pm.SigningOrderPattern) else \
            pm.InSeries(*pattern)
        validate_signing_order_pattern(pattern)
        self.pattern = pattern
        self.signet_set_accessor = signet_set_accessor
        self.service_class = service_class or self.default_service_class

    def __get__(self, instance, owner=None):
        """
        Use the enclosing instance to instantiate and return a SigningOrderPatternMatcher for the instance.signet_set
        """
        if instance is None:  # class access - nada - nothing useful?
            return self
        else:  # return a SigningOrderPatternMatcher to match this SigningOrder against the instance's signet_set
            signet_set_accessor = getattr(instance, self.signet_set_accessor)
            signoffs_pattern = self.service_class(pattern=self.pattern, signets_queryset=signet_set_accessor.all())
            return signoffs_pattern
