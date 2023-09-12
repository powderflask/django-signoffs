"""
    Test Suite for regex_match pattern matching language
"""
from django.test import SimpleTestCase

from ..regex_match import (
    Pattern,
    PatternMatcher,
    all_of,
    exactly_n,
    exactly_one,
    in_series,
    n_or_more,
    one_of,
    one_or_more,
    wrap,
    zero_or_more,
    zero_or_one,
)


class RegexMatchTests(SimpleTestCase):
    def test_pattern_class(self):
        p = Pattern(regex="xyz", tokens=[1, 2, 3])
        self.assertEqual(p.regex, "xyz")
        self.assertEqual(p.tokens, [1, 2, 3])

    def test_wrap(self):
        self.assertEqual(wrap("A"), Pattern(regex="((?P<A>A) )", tokens=["A"]))
        self.assertEqual(
            wrap("A.B-C**"),
            Pattern(regex="((?P<ABC>A\\.B\\-C\\*\\*) )", tokens=["A.B-C**"]),
        )

    def test_exacly_one(self):
        self.assertEqual(
            exactly_one("A.B"), Pattern(regex="((?P<AB>A\\.B) )", tokens=["A.B"])
        )

    def test_zero_or_one(self):
        self.assertEqual(
            zero_or_one("A.B"), Pattern(regex="(((?P<AB>A\\.B) ){0,1})", tokens=["A.B"])
        )

    def test_zero_or_more(self):
        self.assertEqual(
            zero_or_more("A.B"), Pattern(regex="(((?P<AB>A\\.B) )*)", tokens=["A.B"])
        )

    def test_exactly_n(self):
        self.assertEqual(
            exactly_n("A.B", 2), Pattern(regex="((?P<AB>A\\.B) ){2,2}", tokens=["A.B"])
        )

    def test_one_or_more(self):
        self.assertEqual(
            one_or_more("A.B"), Pattern(regex="(((?P<AB>A\\.B) )+)", tokens=["A.B"])
        )
        self.assertEqual(
            one_or_more(Pattern(regex="xx", tokens=["xx"])),
            Pattern(regex="(xx+)", tokens=["xx"]),
        )

    def test_n_or_more(self):
        self.assertEqual(
            n_or_more("A.B", 2), Pattern(regex="(((?P<AB>A\\.B) ){2,})", tokens=["A.B"])
        )

    def test_in_series(self):
        self.assertEqual(
            in_series("A", "B"),
            Pattern(regex="(((?P<A>A) )((?P<B>B) ))", tokens=["A", "B"]),
        )
        self.assertEqual(
            in_series(exactly_one("A"), one_or_more("B")),
            Pattern(regex="(((?P<A>A) )(((?P<B>B) )+))", tokens=["A", "B"]),
        )

    def test_all_of(self):
        self.assertEqual(
            all_of("A", "B"),
            Pattern(
                regex="(((?P<A>A) )((?P<B>B) )|((?P<B>B) )((?P<A>A) ))",
                tokens=["A", "B"],
            ),
        )
        self.assertEqual(
            all_of("A", in_series("B", one_or_more("C"))),
            Pattern(
                regex="(((?P<A>A) )(((?P<B>B) )(((?P<C>C) )+))|(((?P<B>B) )(((?P<C>C) )+))((?P<A>A) ))",
                tokens=["A", "B", "C"],
            ),
        )

    def test_one_of(self):
        self.assertEqual(
            one_of("A", "B", "C"),
            Pattern(
                regex="(((?P<A>A) )|((?P<B>B) )|((?P<C>C) ))", tokens=["A", "B", "C"]
            ),
        )


class RegexPatternMatcherTests(SimpleTestCase):
    def assertMatch(self, m, is_valid, is_complete, next):
        self.assertEqual(m.is_valid, is_valid)
        self.assertEqual(m.is_complete, is_complete)
        self.assertSetEqual(set(m.next), set(next))

    def test_0(self):
        matcher = PatternMatcher(one_or_more("ABC"))
        m = matcher.match("")
        self.assertMatch(m, True, False, ["ABC"])
        m = matcher.match("ABC")
        self.assertMatch(m, True, True, ["ABC"])
        m = matcher.match("ABC ABC")
        self.assertMatch(m, True, True, ["ABC"])

    def test_1(self):
        matcher = PatternMatcher(one_or_more("A-B.C"))
        m = matcher.match("A-B.C")
        self.assertMatch(m, True, True, ["A-B.C"])
        m = matcher.match("A-B.C ")
        self.assertMatch(m, True, True, ["A-B.C"])
        m = matcher.match("B")
        self.assertMatch(m, False, False, [])

    def test_2(self):
        matcher = PatternMatcher(n_or_more("A*B.xy", 2))
        m = matcher.match("A*B.xy")
        self.assertMatch(m, True, False, ["A*B.xy"])
        m = matcher.match("A*B.xy A*B.xy")
        self.assertMatch(m, True, True, ["A*B.xy"])
        m = matcher.match("A*B.xy A*B.xy ")
        self.assertMatch(m, True, True, ["A*B.xy"])
        m = matcher.match("A*B.xy A*B.xy B*B.xy ")
        self.assertMatch(m, False, False, [])
        m = matcher.match("B A*B.xy A*B.xy")
        self.assertMatch(m, False, False, [])

    def test_3(self):
        matcher = PatternMatcher(exactly_one("A.B"))
        m = matcher.match("A.B ")
        self.assertMatch(m, True, True, [])
        m = matcher.match("A.B")
        self.assertMatch(m, True, True, [])
        m = matcher.match(".B")
        self.assertMatch(m, False, False, [])

    def test_4(self):
        matcher = PatternMatcher(exactly_n("A", 2))
        m = matcher.match("A")
        self.assertMatch(m, True, False, ["A"])
        m = matcher.match("A A")
        self.assertMatch(m, True, True, [])
        m = matcher.match("B")
        self.assertMatch(m, False, False, [])

    def test_5(self):
        matcher = PatternMatcher(
            in_series(one_or_more("A.B"), exactly_one("B-B"), n_or_more("C*C", 2))
        )
        m = matcher.match("A.B")
        self.assertMatch(m, True, False, ["A.B", "B-B"])
        m = matcher.match("A.B B-B")
        self.assertMatch(m, True, False, ["C*C"])
        m = matcher.match("A.B A.B B-B")
        self.assertMatch(m, True, False, ["C*C"])
        m = matcher.match("A.B A.B B-B C*C C*C")
        self.assertMatch(m, True, True, ["C*C"])
        m = matcher.match("B")
        self.assertMatch(m, False, False, [])

    def test_6(self):
        matcher = PatternMatcher(
            all_of(one_or_more("A"), exactly_one("B"), n_or_more("C", 2))
        )
        m = matcher.match("A")
        self.assertMatch(m, True, False, ["A", "B", "C"])
        m = matcher.match("B")
        self.assertMatch(m, True, False, ["A", "C"])
        m = matcher.match("C")
        self.assertMatch(m, True, False, ["C"])
        m = matcher.match("C B A")
        self.assertMatch(m, False, False, [])
        m = matcher.match("B C C A A")
        self.assertMatch(m, True, True, ["A"])
        m = matcher.match("C C A B")
        self.assertMatch(m, True, True, [])
        m = matcher.match("B C A B")
        self.assertMatch(m, False, False, [])

    def test_7(self):
        matcher = PatternMatcher(
            all_of(one_or_more("A"), in_series(exactly_one("B"), n_or_more("C", 2)))
        )
        m = matcher.match("A")
        self.assertMatch(m, True, False, ["A", "B"])
        m = matcher.match("B C")
        self.assertMatch(m, True, False, ["C"])
        m = matcher.match("C")
        self.assertMatch(m, False, False, [])

    def test_8(self):
        matcher = PatternMatcher(
            in_series(one_or_more("A"), all_of(exactly_one("B"), n_or_more("C", 2)))
        )
        m = matcher.match("A")
        self.assertMatch(m, True, False, ["A", "B", "C"])
        m = matcher.match("A A C")
        self.assertMatch(m, True, False, ["C"])
        m = matcher.match("A B C")
        self.assertMatch(m, True, False, ["C"])
        m = matcher.match("A C C B")
        self.assertMatch(m, True, True, [])

    def test_9(self):
        matcher = PatternMatcher(
            all_of(exactly_one("A"), n_or_more("B", 2), one_or_more("C"))
        )
        m = matcher.match("C B B B A")
        self.assertMatch(m, True, True, [])

    def test_10(self):
        matcher = PatternMatcher(
            one_of(exactly_one("A"), n_or_more("B", 2), one_or_more("C"))
        )
        m = matcher.match("A")
        self.assertMatch(m, True, True, [])
        m = matcher.match("B B")
        self.assertMatch(m, True, True, ["B"])
        m = matcher.match("C")
        self.assertMatch(m, True, True, ["C"])
        m = matcher.match("A B")
        self.assertMatch(m, False, False, [])

    def test_11(self):
        matcher = PatternMatcher(zero_or_one("A"))
        m = matcher.match("")
        self.assertMatch(
            m, True, False, ["A"]
        )  # No pattern is complete without at least one token!
        m = matcher.match("A")
        self.assertMatch(m, True, True, [])
        m = matcher.match("A A")
        self.assertMatch(m, False, False, [])

    def test_12(self):
        matcher = PatternMatcher(zero_or_more("A"))
        m = matcher.match("")
        self.assertMatch(m, True, False, ["A"])
        m = matcher.match("A")
        self.assertMatch(m, True, True, ["A"])
        m = matcher.match("A A")
        self.assertMatch(m, True, True, ["A"])
