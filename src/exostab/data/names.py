"""Matching user-typed system names to archive host names."""

from __future__ import annotations

import difflib
import re
from collections.abc import Iterable, Mapping, Sequence

from .archive import Row

_NON_ALNUM = re.compile(r"[^0-9a-z]+")
_PLANET_LETTER = re.compile(r"\s*[a-z]$", re.IGNORECASE)
_GLIESE = re.compile(r"(?:gliese|gl|gj)\W*(\d+)", re.IGNORECASE)
# For the command line. The web app replaces it, because it has its own list of the names in the sidebar.
LIST_HINT = "Run exostab list to see the names."


class SystemNotFoundError(LookupError):
    """No archive system matches the name."""

    def __init__(self, query: str, suggestions: Sequence[str], *, where: str = "the archive table"):
        self.query = query
        self.suggestions = list(suggestions)
        hint = f"Did you mean: {', '.join(self.suggestions)}?" if self.suggestions else LIST_HINT
        super().__init__(f"No multi-planet system named {query!r} in {where}. {hint}")


class AmbiguousNameError(SystemNotFoundError):
    """The name matches more than one system once case and punctuation are ignored."""

    def __init__(self, query: str, matches: Mapping[str, str]):
        self.query = query
        self.suggestions = list(matches)
        what = " and ".join(matches.values())
        LookupError.__init__(
            self,
            f"{query!r} is ambiguous: it matches {what}. Type the name exactly as the archive writes it.",
        )


def normalize(name: str) -> str:
    """Case-, space- and punctuation-insensitive key: "TRAPPIST-1" and "trappist 1" both give "trappist1"."""
    return _NON_ALNUM.sub("", name.lower())


def _stem(row: Row) -> str:
    """The planet name without its final letter: "Kepler-90" for "Kepler-90 i". "TOI-836.01" has no letter."""
    return str(row["pl_name"]).removesuffix(f" {row['pl_letter']}")


def _may_mean(query: str, name: str) -> bool:
    """Whether ``query`` may mean ``name``, a host name or a planet name without its letter.

    It may if it is the same name with a planet letter ("Kepler-90 h", "Kepler-90h"), has the same Gliese
    number ("Gl 876" for "GJ 876"), or is a long form of "<x> <Con>": x begins the first word (a number must
    be the whole word), and the letters of Con occur in order in the rest, which starts with the same letter
    ("Upsilon Andromedae" for "ups And", "47 Ursae Majoris" for "47 UMa").
    """
    if normalize(_PLANET_LETTER.sub("", query)) == normalize(name):
        return True
    gliese = _GLIESE.match(query)
    if gliese:
        return re.match(rf"(?:GJ|Gl) {gliese[1]}\b", name) is not None
    x, _, con = name.lower().partition(" ")
    first, _, rest = query.lower().partition(" ")
    if not (first == x if x.isdigit() else first.startswith(x)):
        return False
    letters = iter(rest)  # each "in" goes on from the previous match
    return con[:1].isalpha() and con[0] == rest[:1] and all(c in letters for c in con)


def _suggestions(query: str, hosts: Mapping[str, Sequence[Row]]) -> list[str]:
    """Hosts for the error message: the ones ``query`` may mean, or else the ones spelled like it."""
    query = " ".join(query.split())
    found = sorted(h for h, rows in hosts.items() if any(_may_mean(query, n) for n in {h, *map(_stem, rows)}))
    if found:
        return found
    by_key = {normalize(h): h for h in hosts}
    return [by_key[c] for c in difflib.get_close_matches(normalize(query), list(by_key), n=5, cutoff=0.75)]


def resolve_host(query: str, hosts: Mapping[str, Sequence[Row]]) -> str:
    """Host name for ``query``, which may be a host name ("Kepler-11") or a planet name ("Kepler-11 b").

    An exact host or planet name wins. Otherwise case, spaces and punctuation are ignored; a planet name can
    then coincide with another host's name ("55 cnc b": the planet 55 Cnc b of 55 Cnc, or the companion star
    55 Cnc B), and such a query raises :class:`AmbiguousNameError` instead of picking one. If nothing matches,
    the query is compared with the planet names without their final letter: the archive's host of Kepler-90 i
    is KOI-351, so "Kepler-90" gives KOI-351. Other forms of a name ("Gliese 876") are guesses: they are only
    suggested in the error, never resolved.
    """
    exact = query.strip()
    if exact in hosts:
        return exact
    with_planet = [h for h, rows in hosts.items() if any(str(r["pl_name"]) == exact for r in rows)]
    if len(with_planet) == 1:
        return with_planet[0]
    key = normalize(query)
    matches: dict[str, str] = {}  # host -> what matched, for the error message
    for host, rows in hosts.items():
        if normalize(host) == key:
            matches[host] = f"the host {host!r}"
            continue
        planet = next((str(r["pl_name"]) for r in rows if normalize(str(r["pl_name"])) == key), None)
        if planet is not None:
            matches[host] = f"the planet {planet!r} of {host!r}"
    if not matches:
        matches = {
            host: f"the planet {r['pl_name']!r} of {host!r}"
            for host, rows in hosts.items()
            for r in rows
            if normalize(_stem(r)) == key
        }
    if len(matches) == 1:
        return next(iter(matches))
    if matches:
        raise AmbiguousNameError(query, matches)
    raise SystemNotFoundError(query, _suggestions(query, hosts))


def all_names(hosts: Iterable[str]) -> list[str]:
    return sorted(hosts, key=str.lower)
