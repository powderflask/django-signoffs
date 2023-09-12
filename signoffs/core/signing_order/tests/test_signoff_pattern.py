"""
    Test Suite for regex_match pattern matching language
"""
from types import SimpleNamespace

from django.test import SimpleTestCase

from ..signoff_pattern import (
    AnyOneOf,
    AtLeastN,
    ExactlyN,
    ExactlyOne,
    InParallel,
    InSeries,
    OneOrMore,
    Optional,
    PatternSet,
    SigningOrderPattern,
    ZeroOrMore,
)

#
#  Pluggable encode/decode logic for pattern objects and token objects
#
# For test cases:
#   Pattern objects are classes and tokens are instances of those classes
obj_repr = SimpleNamespace(
    pattern_to_str=lambda obj: obj.__name__,
    pattern_from_str=lambda name: globals()[name]
    if name in globals()
    else __builtins__[name],
    to_str=lambda obj: type(obj).__name__,
)


class SignoffPatternTests(SimpleTestCase):
    def assertMatch(self, m, is_valid, is_complete, next_tokens):
        self.assertEqual(m.is_valid, is_valid)
        self.assertEqual(m.is_complete, is_complete)
        self.assertSetEqual(set(m.next), set(next_tokens))

    def test_exactly_one(self):
        s = ExactlyOne(str, token_repr=obj_repr)
        self.assertEqual(
            s.terms(),
            {
                str,
            },
        )
        match = s.match("ABC")
        self.assertMatch(match, True, True, [])
        match = s.match(123, "ABC")
        self.assertMatch(match, False, False, [])
        match = s.match()
        self.assertMatch(
            match,
            True,
            False,
            [
                str,
            ],
        )

    def test_optional(self):
        s = Optional(str, token_repr=obj_repr)
        self.assertEqual(
            s.terms(),
            {
                str,
            },
        )
        match = s.match()
        self.assertMatch(
            match, True, False, [str]
        )  # No pattern is complete unless it has at least one token!
        match = s.match("ABC")
        self.assertMatch(match, True, True, [])
        match = s.match(123, "ABC")
        self.assertMatch(match, False, False, [])

    def test_zero_or_more(self):
        s = ZeroOrMore(str, token_repr=obj_repr)
        self.assertEqual(
            s.terms(),
            {
                str,
            },
        )
        match = s.match()
        self.assertMatch(
            match, True, False, [str]
        )  # no pattern is compelte without at least one token
        match = s.match("ABC")
        self.assertMatch(match, True, True, [str])
        match = s.match("ABC", "ABC")
        self.assertMatch(match, True, True, [str])

    def test_series_with_optionals(self):
        s = InSeries(
            ExactlyOne(str, token_repr=obj_repr),
            Optional(str, token_repr=obj_repr),
            ZeroOrMore(int, token_repr=obj_repr),
            token_repr=obj_repr,
        )
        self.assertEqual(s.terms(), {str, int})
        match = s.match("ABC")
        self.assertMatch(
            match, True, True, [str, int]
        )  # pattern complete, but optionals are possible
        match = s.match("ABC", "DEF")
        self.assertMatch(match, True, True, [int])
        match = s.match("ABC", "DEF", 123)
        self.assertMatch(match, True, True, [int])
        match = s.match("ABC", "DEF", 123, 456)
        self.assertMatch(match, True, True, [int])
        match = s.match("ABC", 123)
        self.assertMatch(match, True, True, [int])

    def test_one_or_more(self):
        s = OneOrMore(str, token_repr=obj_repr)
        self.assertEqual(
            s.terms(),
            {
                str,
            },
        )
        match = s.match()
        self.assertMatch(match, True, False, [str])
        match = s.match("ABC")
        self.assertMatch(match, True, True, [str])
        match = s.match("ABC", "ABC")
        self.assertMatch(match, True, True, [str])

    def test_at_least_n(self):
        s = AtLeastN(str, n=3, token_repr=obj_repr)
        self.assertEqual(
            s.terms(),
            {
                str,
            },
        )
        match = s.match("ABC", "DEF", "HIJ")
        self.assertMatch(
            match,
            True,
            True,
            [
                str,
            ],
        )
        match = s.match(123, "ABC")
        self.assertMatch(match, False, False, [])
        match = s.match(
            "ABC",
            "DEF",
        )
        self.assertMatch(match, True, False, [str])

    def test_exactly_n(self):
        s = ExactlyN(str, n=3, token_repr=obj_repr)
        self.assertEqual(
            s.terms(),
            {
                str,
            },
        )
        match = s.match("ABC", "DEF", "HIJ")
        self.assertMatch(match, True, True, [])
        match = s.match(123, "ABC")
        self.assertMatch(match, False, False, [])
        match = s.match(
            "ABC",
            "DEF",
        )
        self.assertMatch(match, True, False, [str])
        match = s.match("ABC", "DEF", "HIJ")
        self.assertMatch(match, True, True, [])

    def test_pattern_set(self):
        s = PatternSet(
            AtLeastN(int, n=2, token_repr=obj_repr),
            str,
            AtLeastN(object, n=1, token_repr=obj_repr),
            int,
            token_repr=obj_repr,
        )
        self.assertEqual(len(s), 4)
        self.assertTrue(all(isinstance(t, SigningOrderPattern) for t in s))
        self.assertEqual(
            tuple(type(t) for t in s), (AtLeastN, ExactlyOne, AtLeastN, ExactlyOne)
        )

    def test_in_series(self):
        s = InSeries(
            ExactlyOne(int, token_repr=obj_repr),
            AtLeastN(str, n=2, token_repr=obj_repr),
            AtLeastN(int, n=1, token_repr=obj_repr),
            token_repr=obj_repr,
        )
        self.assertEqual(
            s.terms(),
            {
                int,
                str,
            },
        )
        match = s.match(123, "ABC", "DEF", "HIJ", 456, 789)
        self.assertMatch(match, True, True, [int])
        match = s.match(123, 456, "ABC", "DEF", 789)
        self.assertMatch(match, False, False, [])
        match = s.match(
            123,
            "ABC",
            "DEF",
        )
        self.assertMatch(match, True, False, [str, int])
        match = s.match(123, "ABC", "DEF", "HIJ", 456, 789)
        self.assertMatch(match, True, True, [int])

    def test_in_parallel(self):
        s = InParallel(
            ExactlyOne(int, token_repr=obj_repr),
            AtLeastN(str, n=2, token_repr=obj_repr),
            AtLeastN(object, n=1, token_repr=obj_repr),
            token_repr=obj_repr,
        )
        self.assertEqual(s.terms(), {int, str, object})
        match = s.match(object(), "ABC", "DEF", "HIJ", 456)
        self.assertMatch(match, True, True, [])
        match = s.match(123, "ABC", 456, "DEF", object(), 789)
        self.assertMatch(match, False, False, [])
        match = s.match(
            "ABC",
            "DEF",
            object(),
            object(),
        )
        self.assertMatch(match, True, False, [object, int])

    def test_any_one_of(self):
        s = AnyOneOf(
            ExactlyOne(int, token_repr=obj_repr),
            OneOrMore(str, token_repr=obj_repr),
            ExactlyN(object, n=2, token_repr=obj_repr),
            token_repr=obj_repr,
        )
        self.assertEqual(s.terms(), {int, str, object})
        match = s.match()
        self.assertMatch(match, True, False, [int, str, object])
        match = s.match(
            object(),
        )
        self.assertMatch(match, True, False, [object])
        match = s.match(object(), object())
        self.assertMatch(match, True, True, [])
        match = s.match(42)
        self.assertMatch(match, True, True, [])
        match = s.match("ABC", "DEF")
        self.assertMatch(match, True, True, [str])


# EXAMPLE USAGE


# Some example classes for which objects will be gathered in a Pattern
class A:
    pass


class B:
    pass


class C:
    pass


class SignoffPatternExampleUsageTests(SimpleTestCase):
    # Example Pattern Specification:
    pattern = InSeries(
        InParallel(
            ExactlyOne(A, token_repr=obj_repr),
            AtLeastN(B, n=1, token_repr=obj_repr),
            token_repr=obj_repr,
        ),
        ExactlyOne(C, token_repr=obj_repr),
        AtLeastN(A, n=3, token_repr=obj_repr),
        token_repr=obj_repr,
    )

    def test_pattern_terms(self):
        self.assertEqual(self.pattern.terms(), {A, B, C})

    def assertMatch(self, m, is_valid, is_complete, next_tokens):
        self.assertEqual(m.is_valid, is_valid)
        self.assertEqual(m.is_complete, is_complete)
        self.assertSetEqual(set(m.next), set(next_tokens))

    def test_objective_function(self):
        """given a list of tokens, do the tokens match the pattern?  If not, what is the next token needed?"""

        match = self.pattern.match(B(), B(), A(), C(), A(), A(), A())
        self.assertMatch(
            match,
            True,
            True,
            [
                A,
            ],
        )
        match = self.pattern.match(
            B(),
            B(),
            A(),
            C(),
            A(),
            A(),
        )
        self.assertMatch(
            match,
            True,
            False,
            [
                A,
            ],
        )
        match = self.pattern.match(
            B(),
            A(),
        )
        self.assertMatch(
            match,
            True,
            False,
            [
                C,
            ],
        )
        match = self.pattern.match(
            A(),
            B(),
        )
        self.assertMatch(match, True, False, [B, C])
