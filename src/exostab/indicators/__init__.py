"""Stability indicators.

Each indicator returns an :class:`IndicatorResult` with one of four verdicts:

* ``stable`` – the indicator's condition for stability holds for the nominal parameters and for at least
  95% of the Monte Carlo draws;
* ``unstable`` – the indicator predicts instability for the nominal parameters and for at least 95% of
  the draws;
* ``marginal`` – anything in between: a borderline value, or draws that disagree with the nominal run;
* ``inconclusive`` – the indicator could not be evaluated reliably (for example, the integration's
  energy error was too large).

Without Monte Carlo draws (``--draws 0``) an indicator reports its nominal verdict, untested against the
uncertainties (its ``draws`` is None), and the overall verdict is at most ``marginal``
(:func:`exostab.analysis.overall_verdict`). The report card then says "no draws" in each indicator's heading, and
the overall summary says once what that means.

When the 95% rule keeps a stable or unstable verdict although some draws differ from it, the indicator adds a note
that says what those draws show (:func:`kept_note`); otherwise they would show only in the draw counts.

The analytic indicators (Hill spacing and AMD) are *sufficient* conditions or heuristics: failing them
means stability is not guaranteed, not that the system must fall apart. Resonant systems such as
GJ 876 fail both and are nevertheless long-lived. The report explains this next to every verdict.
"""

from __future__ import annotations

from collections.abc import Sequence
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict

AGREEMENT = 0.95  # fraction of draws that must share the nominal verdict for it to stand


class Verdict(str, Enum):
    STABLE = "stable"
    MARGINAL = "marginal"
    UNSTABLE = "unstable"
    INCONCLUSIVE = "inconclusive"


class DrawStats(BaseModel):
    """How the Monte Carlo draws were classified by one indicator."""

    model_config = ConfigDict(extra="forbid")

    n: int
    stable: int
    marginal: int
    unstable: int
    inconclusive: int

    @classmethod
    def from_verdicts(cls, verdicts: Sequence[Verdict]) -> DrawStats:
        return cls(
            n=len(verdicts),
            stable=sum(v is Verdict.STABLE for v in verdicts),
            marginal=sum(v is Verdict.MARGINAL for v in verdicts),
            unstable=sum(v is Verdict.UNSTABLE for v in verdicts),
            inconclusive=sum(v is Verdict.INCONCLUSIVE for v in verdicts),
        )

    def count(self, verdict: Verdict) -> int:
        return int(getattr(self, verdict.value))


class IndicatorResult(BaseModel):
    """Outcome of one indicator for one system."""

    model_config = ConfigDict(extra="forbid")

    name: str  # "hill", "amd", "nbody"
    title: str
    verdict: Verdict
    summary: str  # one plain-language sentence
    nominal_verdict: Verdict
    draws: DrawStats | None = None
    details: dict[str, Any] = {}
    notes: list[str] = []
    references: list[str] = []  # keys into docs/references.bib


def combine(nominal: Verdict, draws: Sequence[Verdict]) -> Verdict:
    """Combine the nominal verdict with the verdicts of the Monte Carlo draws.

    The nominal verdict stands only if at least ``AGREEMENT`` of the draws share it; otherwise the
    result is ``marginal``. An inconclusive nominal run makes the whole indicator inconclusive, and so
    does a set of draws of which more than 20% are inconclusive. Without draws the nominal verdict is
    returned unchanged: nothing tested it, and the overall verdict accounts for that.
    """
    if nominal is Verdict.INCONCLUSIVE:
        return Verdict.INCONCLUSIVE
    if not draws:
        return nominal
    n = len(draws)
    if sum(v is Verdict.INCONCLUSIVE for v in draws) > 0.2 * n:
        return Verdict.INCONCLUSIVE
    agree = sum(v is nominal for v in draws)
    if agree >= AGREEMENT * n:
        return nominal
    return Verdict.MARGINAL


def kept_despite(nominal: Verdict, verdict: Verdict, draws: Sequence[Verdict]) -> list[int]:
    """The draws (their indices) that differ from the nominal verdict when the 95% rule keeps it anyway.

    Empty unless ``verdict``, the indicator's final verdict, is the nominal one and that is stable or unstable.
    Marginal is also what the rule gives when too many draws differ, so the rule never keeps a marginal verdict.
    """
    if verdict is not nominal or nominal not in (Verdict.STABLE, Verdict.UNSTABLE):
        return []
    return [k for k, v in enumerate(draws) if v is not nominal]


def join_words(items: Sequence[str]) -> str:
    """Join words as in prose: a; a and b; a, b and c."""
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " and " + items[-1]


def kept_note(verdict: Verdict, n_draws: int, reasons: Sequence[tuple[str, str, Sequence[str]]]) -> str:
    """Say what the draws that differ show, and that the 95% rule keeps ``verdict`` all the same.

    ``reasons`` has one entry for each draw that differs: what it shows, worded for one draw and for several
    ("has β ≥ 1", "have β ≥ 1"), and the pairs of planets concerned. Draws with the same reason are counted together:
    "1 of 20 draws has a pair inside the Gladman (1993) limit (b / c); the verdict stays stable under the 95% rule."
    """
    counts: dict[tuple[str, str], int] = {}
    pairs: dict[tuple[str, str], list[str]] = {}
    for one, many, names in reasons:
        counts[(one, many)] = counts.get((one, many), 0) + 1
        seen = pairs.setdefault((one, many), [])
        for name in names:
            if name not in seen:
                seen.append(name)
    parts = []
    for i, ((one, many), k) in enumerate(counts.items()):
        who = f"{k} of {n_draws} draws" if i == 0 else str(k)
        named = f" ({', '.join(pairs[(one, many)])})" if pairs[(one, many)] else ""
        parts.append(f"{who} {one if k == 1 else many}{named}")
    return f"{join_words(parts)}; the verdict stays {verdict.value} under the 95% rule."
