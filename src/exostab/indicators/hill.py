"""Hill-spacing indicator.

Two planets
    Gladman (1993) applied the Hill-stability criterion of Marchal & Bozis (1982) for the general
    three-body problem to two planets: if it holds, two planets on coplanar orbits can never have a close
    encounter. For initially circular orbits and small masses it reduces to a separation of 2*sqrt(3) mutual Hill
    radii. We evaluate the eccentric form as restated by Veras & Armitage (2004, their Eqs. 2.5 and
    2.8, without the next-order mass term) and Giuppone et al. (2013, Eq. 3), see :func:`gladman_margin`.
    Petit, Laskar & Boué (2018, Eq. 26) showed that the same inequality can be written with the AMD;
    ``tests/test_hill.py`` checks that the two forms agree. For two planets on coplanar orbits this is a
    rigorous sufficient condition for the absence of close encounters. It does not exclude the escape of the
    outer planet.

Three or more planets
    No analytic criterion exists. Chambers, Wetherill & Boss (1996) found that the time to the first
    close encounter grows roughly exponentially with the spacing measured in mutual Hill radii. We use
    the spacing of each adjacent pair as a heuristic: any pair that fails the two-planet criterion or
    has crossing orbits is flagged unstable; the system is called stable only if every adjacent pair is
    as widely spaced as Pu & Wu (2015) find necessary for its eccentricities; anything in between is
    marginal. For 7-planet systems of 3 to 9 Earth masses around a solar-mass star, Pu & Wu find that
    half survive 1 Gyr if K_eff >= K_50 = 10.2 on circular, coplanar orbits (their Eq. 12, extrapolated
    from 10 Myr), and that eccentricities raise the requirement (measured at 1 Myr):
    "K_50(sigma_e, sigma_inc) ~ K_50(0, 0) + (sigma_e / 0.01) + (sigma_inc / 0.04)" (their Eq. 14;
    "an eccentricity dispersion of a mere one percent requires the spacing to expand by one Hill
    sphere"), or, in units of the Hill eccentricity e_H = R_H / a = ((m_j + m_k) / (3 M_*))^(1/3),
    "K_50(sigma_e, sigma_inc) ~ K_50(0, 0) + 2.4 [(sigma_e / e_H) + (sigma_inc / (4.0 e_H))]" (their
    Eq. 15 as corrected in the erratum, Pu & Wu 2016). exostab requires, for every adjacent pair,

        Delta >= max(DELTA_MULTI, K_50(0, 0) + 2.4 max(e_j, e_k) / e_H),   DELTA_MULTI = 12,

    using the larger eccentricity of the pair in place of the Rayleigh dispersion sigma_e (conservative)
    and the coplanar orbits exostab models (sigma_inc = 0). DELTA_MULTI = 12 is Pu & Wu's value for
    sigma_e ~ 0.02 and is kept as a floor. Pu & Wu drew each eccentricity from a Rayleigh distribution
    with dispersion sigma_e <= 0.05, so single eccentricities somewhat above 0.05 were common in their
    sample (61% of them for sigma_e = 0.05). As a conservative choice, exostab compares every planet's
    eccentricity with that largest simulated dispersion, ``E_CALIBRATED`` = 0.05, and never calls a system
    stable by this indicator if any eccentricity exceeds it (DECISIONS.md, D12).

The mutual Hill radius of planets j and k is ((m_j + m_k) / (3 M_*))^(1/3) (a_j + a_k) / 2, the
convention of Chambers et al. (1996) and Pu & Wu (2015). In these units the circular-orbit Gladman
limit evaluated here is 2*sqrt(3) up to terms of order (m / M_*)^(2/3): 3.463 for two Earth-mass
planets and 3.429 for two Jupiter-mass planets around a solar-mass star. Lower values quoted
elsewhere, such as 3.39 for Earth masses (Obertas et al. 2017, Eq. 5), come from the lowest-order
criterion normalised to a_1, whose reference semi-major axis differs at order (m / M_*)^(1/3). Keeping
the next-order Marchal-Bozis mass term of Veras & Armitage (2004, Eq. 2.5), omitted here, would lower
the limit slightly (to 3.441 for Earth masses); omitting it is the conservative choice (DECISIONS.md,
D12).
"""

from __future__ import annotations

import math
from typing import Any

from .._numerics import bisect
from ..models import UnusableParametersError
from ..sampling import Realization
from . import DrawStats, IndicatorResult, Verdict, combine

# Spacing (in mutual Hill radii) below which an adjacent pair in a system of three or more planets is never
# treated as widely spaced (Pu & Wu 2015, K_50 for sigma_e ~ 0.02), and the eccentricity-dependent requirement
# above it (Pu & Wu 2015, Eq. 12 at 1 Gyr, and their Eq. 15 as corrected by Pu & Wu 2016). See DECISIONS.md
# (D12) for the choices and their uncertainty.
DELTA_MULTI = 12.0
K50_CIRCULAR = 10.2  # K_50(0, 0) for 1 Gyr (tau ~ 10^10.5 inner orbits), circular and coplanar orbits
K50_ECC_SLOPE = 2.4  # rise of K_50 per Hill eccentricity of eccentricity dispersion
E_CALIBRATED = 0.05  # largest dispersion sigma_e in Pu & Wu's simulations, compared with each planet's e
_RATIO_MAX = 1e6  # the search for the circular-orbit Gladman limit stops doubling a_2 / a_1 past this

REFERENCES = [
    "gladman1993",
    "marchal1982",
    "veras2004",
    "giuppone2013",
    "petit2018",
    "chambers1996",
    "pu2015",
    "pu2015erratum",
]


def mutual_hill_radius(m1: float, m2: float, a1: float, a2: float, m_star: float) -> float:
    return float(((m1 + m2) / (3 * m_star)) ** (1 / 3) * (a1 + a2) / 2)


def separation_in_hill_radii(m1: float, m2: float, a1: float, a2: float, m_star: float) -> float:
    return (a2 - a1) / mutual_hill_radius(m1, m2, a1, a2, m_star)


def required_separation(m1: float, m2: float, e1: float, e2: float, m_star: float) -> float:
    """Spacing (mutual Hill radii) an adjacent pair of a 3+ planet system needs to count as widely spaced.

    max(DELTA_MULTI, K_50(0, 0) + 2.4 max(e_1, e_2) / e_H) with e_H = ((m_1 + m_2) / (3 M_*))^(1/3), Pu & Wu
    (2015, Eq. 15, corrected in Pu & Wu 2016) with the pair's larger eccentricity in place of sigma_e.
    """
    e_hill = ((m1 + m2) / (3 * m_star)) ** (1 / 3)
    return float(max(DELTA_MULTI, K50_CIRCULAR + K50_ECC_SLOPE * max(e1, e2) / e_hill))


def gladman_margin(m1: float, m2: float, a1: float, a2: float, e1: float, e2: float, m_star: float) -> float:
    """Relative margin of the Gladman (1993) two-planet Hill-stability criterion.

    With mu_i = m_i / M_*, alpha = mu_1 + mu_2, gamma_i = sqrt(1 - e_i^2) and delta = sqrt(a_2 / a_1),
    the pair is Hill stable when (Veras & Armitage 2004, Eqs. 2.5 and 2.8; Giuppone et al. 2013, Eq. 3)

        alpha^-3 (mu_1 + mu_2 / delta^2) (mu_1 gamma_1 + mu_2 gamma_2 delta)^2
            > 1 + 3^(4/3) mu_1 mu_2 / alpha^(4/3).

    Returns LHS / RHS - 1: positive means Hill stable. Planet 1 must be the inner one.
    """
    mu1, mu2 = m1 / m_star, m2 / m_star
    alpha = mu1 + mu2
    g1, g2 = math.sqrt(1 - e1**2), math.sqrt(1 - e2**2)
    delta = math.sqrt(a2 / a1)
    lhs = alpha**-3 * (mu1 + mu2 / delta**2) * (mu1 * g1 + mu2 * g2 * delta) ** 2
    rhs = 1 + 3 ** (4 / 3) * mu1 * mu2 / alpha ** (4 / 3)
    return float(lhs / rhs - 1)


def gladman_critical_separation(m1: float, m2: float, m_star: float) -> float:
    """Separation (mutual Hill radii) at which two circular orbits become Hill stable (Gladman 1993).

    The limit is searched in a_2 / a_1 between 1 and 10 first. For a very massive inner body (above about
    0.7 M_* with a planet-mass outer body) it lies beyond 10, so the upper end is doubled until the margin
    changes sign, up to ``_RATIO_MAX``.
    """

    def f(ratio: float) -> float:
        return gladman_margin(m1, m2, 1.0, ratio, 0.0, 0.0, m_star)

    hi = 10.0
    while f(hi) <= 0 and hi < _RATIO_MAX:
        hi *= 2
    ratio = bisect(f, 1.0 + 1e-12, hi)
    return separation_in_hill_radii(m1, m2, 1.0, ratio, m_star)


def pair_table(real: Realization) -> list[dict[str, Any]]:
    """Spacing diagnostics for every adjacent pair of planets."""
    a = real.semi_major_axes()
    rows = []
    for k in range(len(real.bodies) - 1):
        b1, b2 = real.bodies[k], real.bodies[k + 1]
        a1, a2 = float(a[k]), float(a[k + 1])
        try:
            rows.append(
                {
                    "pair": f"{b1.name} / {b2.name}",
                    "separation_hill": separation_in_hill_radii(b1.m, b2.m, a1, a2, real.m_star),
                    "gladman_critical_hill": gladman_critical_separation(b1.m, b2.m, real.m_star),
                    "gladman_margin": gladman_margin(b1.m, b2.m, a1, a2, b1.e, b2.e, real.m_star),
                    "orbits_cross": a1 * (1 + b1.e) >= a2 * (1 - b2.e),
                    "required_separation_hill": required_separation(b1.m, b2.m, b1.e, b2.e, real.m_star),
                    "e_max": max(b1.e, b2.e),
                }
            )
        except (ValueError, ArithmeticError) as exc:
            raise UnusableParametersError(
                f"{b1.name} / {b2.name}: the Hill limit cannot be evaluated in double precision for these masses "
                f"({b1.m:.3g} and {b2.m:.3g} solar masses around {real.m_star:.3g})"
            ) from exc
    return rows


def widely_spaced(row: dict[str, Any]) -> bool:
    """Pair of a 3+ planet system spaced as Pu & Wu (2015) require, with no eccentricity above E_CALIBRATED."""
    return bool(row["e_max"] <= E_CALIBRATED and row["separation_hill"] >= row["required_separation_hill"])


def classify(real: Realization) -> Verdict:
    rows = pair_table(real)
    if any(r["orbits_cross"] or r["gladman_margin"] <= 0 for r in rows):
        return Verdict.UNSTABLE
    if len(rows) == 1:
        return Verdict.STABLE
    if all(widely_spaced(r) for r in rows):
        return Verdict.STABLE
    return Verdict.MARGINAL


def evaluate(nominal: Realization, draws: list[Realization]) -> IndicatorResult:
    """Hill-spacing verdict for the nominal parameters and the Monte Carlo draws."""
    rows = pair_table(nominal)
    v_nom = classify(nominal)
    v_draws = [classify(r) for r in draws]
    verdict = combine(v_nom, v_draws)
    two = len(rows) == 1
    closest = min(rows, key=lambda r: r["separation_hill"])
    tight = [r for r in rows if r["separation_hill"] < r["required_separation_hill"]]
    failing = [r["pair"] for r in rows if r["orbits_cross"] or r["gladman_margin"] <= 0]
    if failing:
        summary = (
            f"Not Hill stable: {', '.join(failing)} "
            f"{'is' if len(failing) == 1 else 'are'} inside the Gladman (1993) limit, so close encounters "
            "are not excluded (a mean-motion resonance can still protect the pair)."
        )
    elif two:
        summary = (
            f"Hill stable: separation {closest['separation_hill']:.2f} mutual Hill radii, above the "
            f"Gladman (1993) limit of {closest['gladman_critical_hill']:.2f} for circular orbits "
            "(eccentricities included in the test)."
        )
    elif v_nom is Verdict.STABLE:
        tightest = min(rows, key=lambda r: r["separation_hill"] / r["required_separation_hill"])
        summary = (
            f"Every adjacent pair is at least {DELTA_MULTI:g} mutual Hill radii apart and as widely spaced as "
            f"Pu & Wu (2015) require for its eccentricities (tightest: {tightest['pair']}, "
            f"{tightest['separation_hill']:.1f} for {tightest['required_separation_hill']:.1f} required)."
        )
    elif tight:
        worst = min(tight, key=lambda r: r["separation_hill"] / r["required_separation_hill"])
        source = "Pu & Wu 2015" + (
            f", extrapolated beyond σ_e = {E_CALIBRATED:g}" if worst["e_max"] > E_CALIBRATED else ""
        )
        summary = (
            f"Every pair passes the two-planet limit, but {worst['pair']} is only "
            f"{worst['separation_hill']:.1f} mutual Hill radii apart, where the heuristic threshold for its "
            f"eccentricities is {worst['required_separation_hill']:.1f} ({source}); long-term stability is "
            "not guaranteed by spacing alone."
        )
    else:
        hot = [r["pair"] for r in rows if r["e_max"] > E_CALIBRATED]
        summary = (
            f"Every pair passes the two-planet limit and the spacing threshold, but {', '.join(hot)} "
            f"{'has' if len(hot) == 1 else 'have'} an eccentricity above {E_CALIBRATED:g}, the largest "
            "eccentricity dispersion in the simulations of Pu & Wu (2015); exostab does not call such pairs "
            "stable on spacing alone (a conservative choice)."
        )
    notes = []
    if verdict is not v_nom:
        notes.append(f"The nominal parameters give '{v_nom.value}', but the draws disagree.")
    if not two:
        notes.append(
            "For three or more planets the spacing test is a heuristic (Chambers et al. 1996; "
            "Pu & Wu 2015), not a proof."
        )
    return IndicatorResult(
        name="hill",
        title="Hill spacing",
        verdict=verdict,
        nominal_verdict=v_nom,
        summary=summary,
        draws=DrawStats.from_verdicts(v_draws) if draws else None,
        details={"pairs": rows, "delta_multi": DELTA_MULTI, "e_calibrated": E_CALIBRATED},
        notes=notes,
        references=REFERENCES,
    )
