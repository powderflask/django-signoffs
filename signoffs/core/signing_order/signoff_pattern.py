"""
Signing Order pattern matching language. Defines the pattern for a Signing Order using Signoff Types

Pattern Matching is backed by regex_match backend (currently not replaceable, but that'd be a nice idea :-)
"""
import collections.abc
from functools import cached_property
from itertools import chain
from types import SimpleNamespace

from signoffs import registry

from .regex_match import (
    PatternMatcher,
    all_of,
    exactly_n,
    exactly_one,
    in_series,
    n_or_more,
    one_of,
    one_or_more,
    zero_or_more,
    zero_or_one,
)

#
#  Pluggable encode/decode logic for pattern and token objects
#

# Pattern objects are classes and tokens are instances of those classes (useful for testing)
obj_repr = SimpleNamespace(
    pattern_to_str=lambda obj: obj.__name__,
    pattern_from_str=lambda name: globals()[name]
    if name in globals()
    else __builtins__[name],
    to_str=lambda obj: type(obj).__name__,
)

# Default: Pattern objects are Signoff Types and tokens are signoff instances - id's are used for pattern matching
signoff_repr = SimpleNamespace(
    pattern_to_str=lambda obj: obj.id,
    pattern_from_str=lambda name: registry.signoffs.get(name),
    to_str=lambda obj: obj.signoff_id,
)


def regex_pattern(pattern, to_str):
    """Return the equivalent regex pattern matching function for given pattern"""
    # recurse nested patterns, stopping recursion when pattern is a simple object and returning its string rep.
    pattern = [
        p.regex_pattern() if isinstance(p, SigningOrderPattern) else to_str(p)
        for p in pattern
    ]
    return pattern


# Singing Order Pattern Specifiers


class SigningOrderPattern(collections.abc.Sequence):
    """
    A abstract pattern is a hierarchically nested sequence of terms used to match a concrete linear sequence of tokens
    Terms for a Signing Order are Signoff Type classes and tokens are signoff instances.

    This class adapts the Signoff pattern and match API to the implementation provided by regex_match.PatternMatcher
    """

    regex_pattern_constructor = in_series

    def __init__(self, *pattern, token_repr=signoff_repr, **kwargs):
        """Initialize with sequence of SigningOrderPattern objects (or any of its subclasses)"""
        self.pattern = pattern
        self.token_repr = token_repr
        self.kwargs = kwargs  # allow subclasses to pass arguments through to regex pattern constructors

    @cached_property
    def pattern_matcher(self):
        return PatternMatcher(self.regex_pattern())

    def regex_pattern(self):
        """Return the equivalent regex pattern matching function for this pattern"""
        # TODO: replace with type(self).regex...
        construct = self.regex_pattern_constructor.__func__  # don't bind  self.
        return construct(
            *regex_pattern(self.pattern, self.token_repr.pattern_to_str), **self.kwargs
        )

    def match(self, *tokens):
        """Returns a MatchResult object that compares iterable of tokens to this pattern"""
        token_str = " ".join(self.token_repr.to_str(s) for s in tokens)
        match = self.pattern_matcher.match(token_str)
        if match.is_valid:
            match.next = [self.token_repr.pattern_from_str(id) for id in match.next]
        return match

    def __str__(self):
        return str(self.pattern)

    def __getitem__(self, index):
        return self.pattern[index]

    def __len__(self):
        return len(self.pattern)

    def terms(self):
        """Return a flat set of pattern terms used in this pattern"""
        return set(chain(t for term in self.pattern for t in term.terms()))


class TokenPattern(SigningOrderPattern):
    """Abstract base for simple, un-nested patterns specified by a single token."""

    def terms(self):
        """Return a flat set of pattern terms used in this pattern"""
        return set(self.pattern)


class ExactlyOne(TokenPattern):
    """A pattern that is complete when there is exactly one matching token"""

    regex_pattern_constructor = exactly_one


class Optional(TokenPattern):
    """A pattern that matches zero or one optional token"""

    regex_pattern_constructor = zero_or_one


class ZeroOrMore(TokenPattern):
    """A pattern that matches zero or more matching tokens"""

    regex_pattern_constructor = zero_or_more


class OneOrMore(TokenPattern):
    """A pattern that is complete when there are one or more matching tokens"""

    regex_pattern_constructor = one_or_more


class NTokenPattern(TokenPattern):
    """Abstract base for patterns where some number, n, tokens are required"""

    def __init__(self, *pattern, n=1, **kwargs):
        super().__init__(*pattern, n=n, **kwargs)


class ExactlyN(NTokenPattern):
    """A pattern that is complete with exactly n tokens"""

    regex_pattern_constructor = exactly_n


class AtLeastN(NTokenPattern):
    """
    A pattern that is complete when pattern has at least some min. number of tokens.
    Note: match algorithm consumes all consecutive matching tokens (greedy)
    """

    regex_pattern_constructor = n_or_more


# Pattern Sets


class PatternSet(SigningOrderPattern):
    """Abstract base for nested patterns where terms are themselves patterns"""

    def __init__(self, *pattern, **kwargs):
        """Wrap any "naked" tokens in an ExactlyOne"""
        pattern = tuple(
            token if isinstance(token, SigningOrderPattern) else ExactlyOne(token)
            for token in pattern
        )
        super().__init__(*pattern, **kwargs)


class AnyOneOf(PatternSet):
    """A pattern that matches any one of a set of alternate patterns"""

    regex_pattern_constructor = one_of


class InSeries(PatternSet):
    """A pattern where tokens must be in sequential order"""

    regex_pattern_constructor = in_series


class InParallel(PatternSet):
    """
    A pattern where tokens can be in any order
    Notes:
        Experimental - only works for straight-forward, unambiguous cases.
        Terms from InSeries and AtLeastN patterns match sequential tokens, even when wrapped within InParallel
          It may be possible to handle AtLeastN terms as non-sequential, but a look-ahead match algorithm is needed?
    """

    regex_pattern_constructor = all_of


__all__ = [
    "AnyOneOf",
    "AtLeastN",
    "ExactlyN",
    "ExactlyOne",
    "InParallel",
    "InSeries",
    "OneOrMore",
    "Optional",
]
