"""Angular momentum deficit (AMD) indicator.

The AMD of a planetary system (Laskar & Petit 2017, their Sect. 3) is

    C = sum_k Lambda_k (1 - sqrt(1 - e_k^2) cos i_k),   Lambda_k = m_k sqrt(G M_* a_k),

the difference between the angular momentum of circular, coplanar orbits and the actual one. It is
conserved by the secular (orbit-averaged) dynamics, so it bounds how eccentric the orbits can ever
become.

Unknown mutual inclinations (Laskar & Petit 2017, Sect. 6)
    exostab models coplanar systems, so it computes the coplanar AMD C_p (cos i_k = 1). Since cos i_k <= 1,
    the true AMD is C >= C_p for any mutual inclinations, and coefficients computed from C_p are lower
    bounds. For catalogue systems whose inclinations are unknown, Laskar & Petit (2017) "assume that the
    AMD contribution of mutual inclinations is equal to that of the eccentricities" (equipartition): "The
    total AMD is thus twice the measured AMD, and in this study we use beta = 2 beta_p", and "similarly we
    set beta_S = 2 beta_Sp". Petit, Laskar & Boué (2017, Sect. 5) "define the total AMD-stability
    coefficients as beta = 2 beta_p" for the resonance-overlap criterion as well. exostab follows them:
    beta, beta_S and beta_H below use C = 2 C_p, and the coplanar values beta_p = beta / 2 etc. are
    reported next to them. The factor 2 is a statistical assumption, not a bound: in Laskar & Petit's
    Table 1 the inclination AMD of the Solar System is 1.04 times the eccentricity AMD for the four inner
    planets but only 0.37 times for all eight.

AMD stability (Laskar & Petit 2017)
    A pair of adjacent planets (inner m, a; outer m', a'; alpha = a/a', gamma = m/m') is AMD-stable if
    the total AMD, even if absorbed entirely by this pair, cannot make the orbits cross:
    beta = C / (Lambda' C_c(alpha, gamma)) < 1, where the critical relative AMD C_c is the smallest AMD
    allowing a(1 + e) = a'(1 - e'). The critical inner eccentricity e_c solves

        alpha e + gamma e / sqrt(alpha (1 - e^2) + gamma^2 e^2) - 1 + alpha = 0,

    with e'_c = 1 - alpha - alpha e_c and C_c = gamma sqrt(alpha) (1 - sqrt(1 - e_c^2)) + 1 - sqrt(1 - e'_c^2)
    (their Eqs. for the collision line, the Lagrange condition and the relative AMD). The system is
    AMD-stable if every adjacent pair is; it is *strongly* AMD-stable if in addition the AMD cannot
    bring the innermost planet to the star, beta_S = C / Lambda_1 < 1.

Mean-motion-resonance overlap (Petit, Laskar & Boué 2017)
    Close pairs can become chaotic through overlapping first-order mean-motion resonances before their
    orbits cross. With eps = (m + m') / M_* and r = 0.80199, the overlap condition defines

        g(alpha, eps) = 3^4 (1 - alpha)^5 / (2^9 r eps) - 32 r eps / (9 (1 - alpha)^2)  (0 if alpha > alpha_cir),
        C_MMR = g^2 / 2 * gamma sqrt(alpha) / (1 + gamma sqrt(alpha)),

    where 1 - alpha_cir = 1.46 eps^(2/7) is the circular-orbit overlap limit. The critical AMD is C_c for
    alpha < alpha_R and C_MMR for alpha > alpha_R, alpha_R being the root of
    3^6 (1 - alpha)^7 - 3^2 2^9 r eps (1 - alpha)^3 - 2^14 (r eps)^2 = 0.

    Domain. C_MMR "was obtained thanks to the assumption that alpha was close to 1. Particularly, it
    makes no sense to talk about first-order MMR overlap for alpha<0.63 which corresponds to the center of
    the MMR 2:1. Therefore, the collision criterion should be used for small alpha" (Petit et al. 2017,
    Sect. 4.2). For their catalogue they "discard systems such that a pair of planets has
    eps > eps_lim = 8.20e-3", for which alpha_cir lies below the 2:1 resonance (Sect. 5.1). For
    eps > 3.1e-3, alpha_R is below 2^(-2/3) = 0.630, so the switching rule alone would apply C_MMR to
    pairs wide of the 2:1 resonance. exostab therefore uses C_MMR only for eps <= eps_lim and
    alpha > max(alpha_R, 2^(-2/3)), and C_c otherwise. A pair with alpha <= alpha_R is in the collision
    regime whatever its eps: Petit et al.'s switching rule itself gives C_c there, the criterion with which
    Laskar & Petit (2017) classified their catalogue, pairs with eps > eps_lim included (the strongly
    AMD-stable systems of their Fig. 5 include HD 147018, HD 168443, HD 169830 and nu Oph, whose wide giant
    pairs have eps > eps_lim). A pair with alpha > alpha_R and either eps > eps_lim or alpha <= 2^(-2/3)
    lies outside the domain Petit et al. state, and no published AMD criterion accounts for resonance
    overlap there: its beta is computed with C_c and reported, but the system is never called AMD-stable
    (at most marginal). eps_lim = 8.11e-3 is the exact root of alpha_cir(eps) = 2^(-2/3); the paper's
    8.20e-3 follows from the rounded 1.46 and 0.63.

Hill stability in the AMD framework (Petit, Laskar & Boué 2018)
    For two planets (eps = (m + m') / M_*), the pair is Hill stable if its relative AMD C / Lambda' is below

        C_H = gamma sqrt(alpha) + 1 - (1 + gamma)^(3/2) sqrt(alpha / (gamma + alpha) (1 + 3^(4/3) eps^(2/3) gamma / (1 + gamma)^2)).

    The authors note that this criterion does not carry over to tightly packed systems of three or
    more planets, so it is only used for two-planet systems.

Verdicts
    * stable: strongly AMD-stable with C = 2 C_p (all beta < 1, including the MMR-overlap refinement, and
      beta_S < 1), with every pair inside the domain of Petit et al. (2017);
    * unstable: a two-planet system that is neither AMD-stable nor Hill stable even for exactly coplanar
      orbits (beta_p >= 1 and beta_H,p >= 1). The coplanar values are lower bounds for any inclinations, so
      the equipartition assumption is never used to strengthen a claim of instability;
    * marginal: anything else. AMD instability means only that collisions are not excluded by AMD
      conservation; the Solar System itself is AMD-unstable (Laskar & Petit 2017).

Assumed eccentricities
    A planet whose eccentricity was not measured gets e = 0 in every run (``Provenance.ASSUMED``). It then adds
    no AMD, so beta and beta_S are lower limits for any real eccentricity. The notes name such planets, and if
    every eccentricity is assumed the summary says that the AMD-stable verdict rests on that assumption alone.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from typing import Any

from .._numerics import bisect
from ..models import UnusableParametersError
from ..sampling import Realization
from . import DrawStats, IndicatorResult, Verdict, combine


def _b(x: float) -> str:
    return "∞" if math.isinf(x) else f"{x:.3g}"


R_MMR = 0.80199  # Petit et al. (2017), r = (K_1(2/3) + 2 K_0(2/3)) / pi
# C = 2 C_p: the unknown mutual inclinations carry as much AMD as the eccentricities (equipartition;
# Laskar & Petit 2017, Sect. 6; Petit et al. 2017, Sect. 5). See DECISIONS.md (D14).
EQUIPARTITION = 2.0
# Domain of the resonance-overlap criterion (Petit et al. 2017, Sects. 4.2 and 5.1): alpha above the centre
# of the 2:1 resonance ("0.63"), and eps <= eps_lim, where alpha_cir(eps_lim) = 2^(-2/3) (8.11e-3; the
# paper rounds it to 8.20e-3). See DECISIONS.md (D14).
ALPHA_2_1 = 2 ** (-2 / 3)
EPS_LIM = float(((1 - ALPHA_2_1) * 3 ** (6 / 7) / (4 * R_MMR ** (2 / 7))) ** 3.5)
REFERENCES = ["laskar2017", "petit2017", "petit2018"]


def relative_amd(e_in: float, e_out: float, alpha: float, gamma: float) -> float:
    """Relative AMD C / Lambda' of a coplanar pair (Laskar & Petit 2017)."""
    return gamma * math.sqrt(alpha) * (1 - math.sqrt(1 - e_in**2)) + 1 - math.sqrt(1 - e_out**2)


def critical_eccentricity(alpha: float, gamma: float) -> float:
    """Inner-orbit eccentricity e_c at the AMD-critical collision (Laskar & Petit 2017)."""
    if not 0 < alpha < 1:
        raise ValueError(f"alpha must be in (0, 1), got {alpha}")

    def F(e: float) -> float:
        return alpha * e + gamma * e / math.sqrt(alpha * (1 - e**2) + gamma**2 * e**2) - 1 + alpha

    return bisect(F, 0.0, min(1.0, 1 / alpha - 1))


def critical_amd_collision(alpha: float, gamma: float) -> float:
    """Critical relative AMD C_c(alpha, gamma) for orbit crossing (Laskar & Petit 2017)."""
    e_c = critical_eccentricity(alpha, gamma)
    e_c_out = 1 - alpha - alpha * e_c
    return relative_amd(e_c, e_c_out, alpha, gamma)


def alpha_circular_overlap(eps: float) -> float:
    """alpha above which first-order resonances overlap even for circular orbits (Petit et al. 2017).

    Exact root of 3^6 (1 - alpha)^7 = 2^14 r^2 eps^2, i.e. 1 - alpha = 4 r^(2/7) eps^(2/7) / 3^(6/7) = 1.46 eps^(2/7).
    """
    return float(1 - 4 * R_MMR ** (2 / 7) * eps ** (2 / 7) / 3 ** (6 / 7))


def alpha_resonance_switch(eps: float) -> float:
    """alpha_R: the MMR-overlap critical AMD replaces the collision one for alpha > alpha_R (Petit et al. 2017)."""

    def P(x: float) -> float:  # x = 1 - alpha
        return 3**6 * x**7 - 3**2 * 2**9 * R_MMR * eps * x**3 - 2**14 * (R_MMR * eps) ** 2

    x = bisect(P, 1e-12, 1.0) if P(1.0) > 0 else 1.0
    return 1 - x


def critical_amd_mmr(alpha: float, gamma: float, eps: float) -> float:
    """Critical relative AMD from first-order MMR overlap, C_c^(1) of Petit et al. (2017)."""
    if alpha >= alpha_circular_overlap(eps):
        return 0.0
    x = 1 - alpha
    g = 3**4 * x**5 / (2**9 * R_MMR * eps) - 32 * R_MMR * eps / (9 * x**2)
    g = max(g, 0.0)
    s = gamma * math.sqrt(alpha)
    return g**2 / 2 * s / (1 + s)


def critical_amd(alpha: float, gamma: float, eps: float) -> tuple[float, str]:
    """Piece-wise critical relative AMD of Petit et al. (2017) within its stated domain, and the branch used.

    Their Eq. (amd_crit): C_c = C_c^coll for alpha < alpha_R and C_MMR for alpha > alpha_R; the resonance
    branch is restricted to eps <= eps_lim and alpha above the 2:1 resonance (see the module docstring).
    """
    if eps <= EPS_LIM and alpha > max(alpha_resonance_switch(eps), ALPHA_2_1):
        return critical_amd_mmr(alpha, gamma, eps), "mmr_overlap"
    return critical_amd_collision(alpha, gamma), "collision"


def outside_domain(alpha: float, eps: float) -> str | None:
    """Why a pair lies outside the domain of Petit et al. (2017), or None if it does not.

    Only pairs with alpha > alpha_R, where their switching rule would use first-order resonance overlap, can
    lie outside it; for alpha <= alpha_R the rule gives the collision criterion of Laskar & Petit (2017) for
    any eps.

    "eps_above_limit": eps > eps_lim, so alpha_cir lies wide of the 2:1 resonance and Petit et al. excluded
    such pairs from their study of resonance overlap;
    "wide_of_2_1": alpha <= 2^(-2/3), where their text says first-order resonance overlap makes no sense
    (only possible for 3.1e-3 < eps <= eps_lim).
    """
    if alpha <= alpha_resonance_switch(eps):
        return None
    if eps > EPS_LIM:
        return "eps_above_limit"
    if alpha <= ALPHA_2_1:
        return "wide_of_2_1"
    return None


def critical_amd_hill(alpha: float, gamma: float, eps: float) -> float:
    """Critical relative AMD for Hill stability of two planets, C_H of Petit et al. (2018)."""
    term = alpha / (gamma + alpha) * (1 + 3 ** (4 / 3) * eps ** (2 / 3) * gamma / (1 + gamma) ** 2)
    return float(gamma * math.sqrt(alpha) + 1 - (1 + gamma) ** 1.5 * math.sqrt(term))


def analyse(real: Realization) -> dict[str, Any]:
    """Per-pair coefficients beta (and beta_H for two planets) and beta_S, for C = 2 C_p and for C_p alone."""
    a = real.semi_major_axes()
    ms = [b.m for b in real.bodies]
    # Lambda_k / sqrt(G M_*): the common factor cancels in every ratio below.
    lam = [m * math.sqrt(float(ak)) for m, ak in zip(ms, a, strict=True)]
    # coplanar AMD C_p (cos i_k = 1): a lower bound on the AMD for any mutual inclinations
    amd_k = [lam[k] * (1 - math.sqrt(1 - b.e**2)) for k, b in enumerate(real.bodies)]
    coplanar = sum(amd_k)
    pairs = []
    for k in range(len(real.bodies) - 1):
        alpha = float(a[k] / a[k + 1])
        gamma = ms[k] / ms[k + 1]
        eps = (ms[k] + ms[k + 1]) / real.m_star
        try:
            cc, branch = critical_amd(alpha, gamma, eps)
        except (ValueError, ArithmeticError) as exc:
            raise UnusableParametersError(
                f"{real.bodies[k].name} / {real.bodies[k + 1].name}: the critical AMD cannot be evaluated for these "
                f"values (a/a' = {alpha:.6g}, m/m' = {gamma:.3g})"
            ) from exc
        rel = coplanar / lam[k + 1]  # coplanar relative AMD C_p / Lambda'
        beta_p = rel / cc if cc > 0 else math.inf
        row: dict[str, Any] = {
            "pair": f"{real.bodies[k].name} / {real.bodies[k + 1].name}",
            "alpha": alpha,
            "gamma": gamma,
            "epsilon": eps,
            "relative_amd": rel,
            "critical_amd": cc,
            "critical_branch": branch,
            "beta": EQUIPARTITION * beta_p,
            "beta_coplanar": beta_p,
            "circular_overlap": eps <= EPS_LIM and alpha >= alpha_circular_overlap(eps),
            "outside_domain": outside_domain(alpha, eps),
        }
        if len(real.bodies) == 2:
            ch = critical_amd_hill(alpha, gamma, eps)
            beta_hp = rel / ch if ch > 0 else math.inf
            row["critical_amd_hill"] = ch
            row["beta_hill"] = EQUIPARTITION * beta_hp
            row["beta_hill_coplanar"] = beta_hp
        pairs.append(row)
    beta_sp = coplanar / lam[0]  # beta_Sp = C_p / Lambda_1 (alpha = 0 and C_c = 1 for the star)
    return {
        "equipartition_factor": EQUIPARTITION,
        "beta_star": EQUIPARTITION * beta_sp,
        "beta_star_coplanar": beta_sp,
        "pairs": pairs,
    }


def classify(real: Realization) -> Verdict:
    info = analyse(real)
    pairs = info["pairs"]
    in_domain = not any(p["outside_domain"] for p in pairs)
    if in_domain and all(p["beta"] < 1 for p in pairs) and info["beta_star"] < 1:
        return Verdict.STABLE
    # "unstable" uses the coplanar coefficients, which no choice of mutual inclinations can lower
    if len(pairs) == 1 and pairs[0]["beta_coplanar"] >= 1 and pairs[0]["beta_hill_coplanar"] >= 1:
        return Verdict.UNSTABLE
    return Verdict.MARGINAL


def evaluate(
    nominal: Realization, draws: list[Realization], *, assumed_eccentricities: Sequence[str] = ()
) -> IndicatorResult:
    """AMD verdict for the nominal parameters and the draws.

    ``assumed_eccentricities`` names the planets whose eccentricity is assumed, not measured (see the module
    docstring).
    """
    info = analyse(nominal)
    v_nom = classify(nominal)
    v_draws = [classify(r) for r in draws]
    verdict = combine(v_nom, v_draws)
    pairs = info["pairs"]
    worst = max(pairs, key=lambda p: p["beta"])
    amd_stable = all(p["beta"] < 1 for p in pairs)
    off = [p["pair"] for p in pairs if p["outside_domain"]]
    names = [b.name for b in nominal.bodies]
    assumed = [n for n in names if n in set(assumed_eccentricities)]
    if v_nom is Verdict.STABLE and len(assumed) == len(names) and worst["beta"] == 0:
        summary = (
            "AMD-stable only because no eccentricity is measured: every planet is assumed to be on a circular "
            "orbit, so the AMD and every β are 0. The test says nothing about the real eccentricities."
        )
    elif v_nom is Verdict.STABLE:
        summary = (
            f"AMD-stable: largest β = {_b(worst['beta'])} ({worst['pair']}), so collisions are excluded "
            "in the secular approximation, provided the mutual inclinations carry no more AMD than the "
            "eccentricities."
        )
    elif amd_stable and off:
        star = (
            f"; the AMD could also bring the innermost planet to the star (β_S = {_b(info['beta_star'])})"
            if info["beta_star"] >= 1
            else ""
        )
        summary = (
            f"β < 1 for every pair (largest {_b(worst['beta'])}), but {', '.join(off)} "
            f"{'lies' if len(off) == 1 else 'lie'} outside the domain Petit et al. (2017) state for the "
            f"critical AMD (see the notes), so AMD stability is not claimed{star}."
        )
    elif amd_stable:
        summary = (
            f"Weakly AMD-stable: no planet-planet collisions (largest β = {_b(worst['beta'])}), but the AMD "
            f"could in principle bring the innermost planet to the star (β_S = {_b(info['beta_star'])})."
        )
    elif len(pairs) == 1 and pairs[0]["beta_hill"] < 1:
        summary = (
            f"AMD-unstable (β = {_b(worst['beta'])}) but Hill stable in the AMD framework "
            f"(β_H = {_b(pairs[0]['beta_hill'])}): close encounters are impossible, chaos is not excluded."
        )
    elif v_nom is Verdict.UNSTABLE:
        summary = (
            f"Neither AMD-stable (β = {_b(worst['beta'])}) nor Hill stable (β_H = {_b(pairs[0]['beta_hill'])}), "
            f"even for exactly coplanar orbits (β_p = {_b(worst['beta_coplanar'])}, "
            f"β_H,p = {_b(pairs[0]['beta_hill_coplanar'])}): the AMD allows close encounters."
        )
    elif len(pairs) == 1:
        summary = (
            f"Neither AMD-stable (β = {_b(worst['beta'])}) nor Hill stable (β_H = {_b(pairs[0]['beta_hill'])}) "
            "if the mutual inclinations carry as much AMD as the eccentricities; not 'unstable', because the "
            f"coplanar values (β_p = {_b(worst['beta_coplanar'])}, β_H,p = {_b(pairs[0]['beta_hill_coplanar'])}) "
            "are not both ≥ 1."
        )
    else:
        n_bad = sum(p["beta"] >= 1 for p in pairs)
        summary = (
            f"AMD-unstable: {n_bad} of {len(pairs)} adjacent pairs have β ≥ 1 (largest {_b(worst['beta'])}, "
            f"{worst['pair']}); collisions are not excluded by AMD conservation, which does not imply they happen."
        )
    notes = []
    if verdict is not v_nom and v_nom is not Verdict.INCONCLUSIVE:
        notes.append(f"The nominal parameters give '{v_nom.value}', but the draws disagree.")
    if assumed:
        notes.append(
            f"Eccentricity assumed, not measured (e = 0 in every run), for: {', '.join(assumed)}. "
            f"{'These planets add' if len(assumed) > 1 else 'This planet adds'} no AMD, so β and β_S are lower "
            "limits for any real eccentricities, and an AMD-stable verdict holds only under that assumption."
        )
    notes.append(
        "β, β_S and β_H assume that the unknown mutual inclinations carry as much AMD as the eccentricities "
        "(twice the coplanar AMD; Laskar & Petit 2017, Petit et al. 2017). For exactly coplanar orbits they "
        f"are half as large (largest β_p = {_b(max(p['beta_coplanar'] for p in pairs))}, "
        f"β_S,p = {_b(info['beta_star_coplanar'])}); 'unstable' requires the coplanar values, lower bounds for "
        "any inclinations, to be ≥ 1."
    )
    mmr = [p["pair"] for p in pairs if p["critical_branch"] == "mmr_overlap"]
    if mmr:
        notes.append(
            "Critical AMD from first-order resonance overlap (Petit et al. 2017) used for: "
            + ", ".join(mmr)
            + "."
        )
    circ = [p["pair"] for p in pairs if p["circular_overlap"]]
    if circ:
        notes.append("Resonances overlap even for circular orbits for: " + ", ".join(circ) + ".")
    heavy = [p["pair"] for p in pairs if p["outside_domain"] == "eps_above_limit"]
    if heavy:
        notes.append(
            f"(m + m')/M★ is above ε_lim = {EPS_LIM * 1e3:.2f}e-3 and α > α_R for: {', '.join(heavy)}. Petit et "
            "al. (2017) excluded such pairs, whose circular-orbit resonance-overlap limit lies wide of the 2:1 "
            "resonance; β uses the collision criterion, and the AMD verdict is at most marginal."
        )
    wide_heavy = [p["pair"] for p in pairs if p["epsilon"] > EPS_LIM and p["outside_domain"] is None]
    if wide_heavy:
        notes.append(
            f"(m + m')/M★ is above ε_lim = {EPS_LIM * 1e3:.2f}e-3 for: {', '.join(wide_heavy)}, but α ≤ α_R, "
            "where Petit et al. (2017) use the collision criterion of Laskar & Petit (2017), as for any pair far "
            "from first-order resonance overlap."
        )
    wide = [p["pair"] for p in pairs if p["outside_domain"] == "wide_of_2_1"]
    if wide:
        notes.append(
            "At or wide of the 2:1 resonance, where Petit et al. (2017) consider first-order resonance overlap "
            f"meaningless although α > α_R: {', '.join(wide)}. β uses the collision criterion, and the AMD "
            "verdict is at most marginal."
        )
    return IndicatorResult(
        name="amd",
        title="AMD",
        verdict=verdict,
        nominal_verdict=v_nom,
        summary=summary,
        draws=DrawStats.from_verdicts(v_draws) if draws else None,
        details=info,
        notes=notes,
        references=REFERENCES,
    )
