"""
Simple Regular Expression Pattern Matching language for a sequence of tokens

Design Constraints:
    API needs to be simple and clear - no regular expressions leaking through.

    Partial matches are essential & need to obtain next unmatched tokens in sequence.
"""
import itertools
from dataclasses import dataclass, field

import regex


@dataclass
class Pattern:
    """
    A pattern consists of the regular expression for matching the pattern
        and the list of tokens matched in the regular expression
    """

    regex: str
    tokens: list


#
# PATTERN CONSTRUCTORS
#


def wrap(s):
    """
    Create a Pattern out of a single string token
        this is a helper function that would usually be called by one of the other pattern constructors
        if s is a Pattern that already has a regex and token(s) associated with it, simply pass it through
        otherwise, create a regular expression chunk that matches s and record s as the associated token
        the regular expression chunk puts s into a named group, so matched instances can later be retrieved by name
    """
    if isinstance(s, str):
        escape_set = ["-", ".", "|", "(", ")", "{", "}", "+", "*", "?"]
        group_name = s
        s_pat = s
        for e in escape_set:
            s_pat = s_pat.replace(e, "\\" + e)
            group_name = group_name.replace(e, "")
        return Pattern(r"((?P<" + group_name + r">" + s_pat + r") )", [s])
    else:
        return s


def exactly_one(s):
    """Given a string token or pattern s, create a pattern that matches exactly one occurrence of s"""
    return wrap(s)


def zero_or_one(s):
    ws = wrap(s)
    return Pattern("(" + ws.regex + "{0,1})", ws.tokens)


def zero_or_more(s):
    """Optionally match zero or one of token, s"""
    ws = wrap(s)
    return Pattern("(" + ws.regex + "*)", ws.tokens)


def exactly_n(s, n):
    """Given a string token or pattern s, create a pattern that matches exactly n occurrences of s"""
    ws = wrap(s)
    return Pattern(ws.regex + "{" + str(n) + "," + str(n) + "}", ws.tokens)


def one_or_more(s):
    """Given a string token or pattern s, create a pattern that matches one or more occurrences of s"""
    ws = wrap(s)
    return Pattern("(" + ws.regex + "+)", ws.tokens)


def n_or_more(s, n):
    """Given a string token or pattern s, create a pattern that matches n or more occurrences of s"""
    ws = wrap(s)
    return Pattern("(" + ws.regex + "{" + str(n) + ",})", ws.tokens)


def in_series(*lst):
    """Given a list lst with string tokens or patterns, create a pattern that matches the given list in order"""
    p = []
    tokens = []
    for e in lst:
        ws = wrap(e)
        p = p + [ws.regex]
        tokens = tokens + ws.tokens
    return Pattern("(" + "".join(p) + ")", tokens)


def all_of(*lst):
    """
    Given a list with string tokens or patterns, create a pattern that matches if and only if
    all of the elements of lst occur, in no particular order.
    Since there is no AND operator in regular expressions, the only way to implement this that doesn't
    potentially have unintended side effects on how the rest of the expression is matched
    is to chain all permutations with an OR - ugh!
    """
    p = []
    tokens = []
    for e in lst:
        ws = wrap(e)
        p = p + [ws.regex]
        tokens = tokens + ws.tokens
    permutations = list(itertools.permutations(p))
    return Pattern("(" + "|".join(list(map("".join, permutations))) + ")", tokens)


def one_of(*lst):
    """Given a list with string tokens or patterns, create a pattern that matches any one of the patterns/tokens"""
    p = []
    tokens = []
    for e in lst:
        ws = wrap(e)
        p = p + [ws.regex]
        tokens = tokens + ws.tokens
    return Pattern("(" + "|".join(p) + ")", tokens)


@dataclass
class MatchResult:
    """Defines the result from matching a pattern template against a concrete input sequence"""

    is_valid: bool = False  # True iff string does not violate pattern, but may only be a partial match
    is_complete: bool = False  # True iff the string is a complete match for pattern
    matched: dict = field(default_factory=lambda: {})  # a dict of matched tokens
    next: list = field(
        default_factory=lambda: []
    )  # list of token(s) that would match next


class PatternMatcher:
    """
    A special-purpose pattern matcher for a sequence of tokens
    Must be initialised with a Pattern template (see Pattern class above) to be matched against
        - the Pattern template would usually be produced by utilizing a combination
          of the pattern generator functions defined above
    """

    def __init__(self, pattern):
        self.template = regex.compile(pattern.regex)
        # extract and store unique tokens in the order they appear in the pattern
        self.tokens = list(dict.fromkeys(pattern.tokens))

    def match(self, token_str):
        """Match the string of concrete tokens against this matcher's pattern, return a MatchResult"""
        # add a space at the end if there isn't one - makes life easier if we can rely on that space always being there
        token_str = token_str + (
            "" if token_str.endswith(" ") or not token_str else " "
        )
        at_least_one_token = len(token_str) > 1
        regex_match = self.template.fullmatch(token_str, partial=True)
        if regex_match or not at_least_one_token:
            next = []
            for t in self.tokens:  # find tokens that may appear next in pattern
                if self.template.fullmatch(token_str + t + " ", partial=True):
                    next.append(t)
            return MatchResult(
                is_valid=True,
                is_complete=at_least_one_token and not regex_match.partial,
                matched=regex_match.capturesdict() if at_least_one_token else {},
                next=next,
            )
        else:
            return MatchResult()
