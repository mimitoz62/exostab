import math

import pytest
from hypothesis import assume, given
from hypothesis import strategies as st

from conftest import V, two_planet_system
from exostab._numerics import bisect
from exostab.analysis import CheckSettings, check_system
from exostab.indicators import Verdict, amd
from exostab.models import Provenance, UnusableParametersError
from exostab.sampling import Body, Realization

alphas = st.floats(0.05, 0.98)
gammas = st.floats(0.01, 100.0)
ecc = st.floats(0.0, 0.95)


def real_of(ms: list[float], periods: list[float], es: list[float], m_star: float = 1.0) -> Realization:
    return Realization(
        label="x",
        m_star=m_star,
        bodies=tuple(Body(f"p{k}", m, P, e, 0.0, 0.0) for k, (m, P, e) in enumerate(zip(ms, periods, es))),
    )


def test_reproduces_hd127195_research_note_amd_limits() -> None:
    """paper_analysis.py of the HD 127195 Research Note: AMD limits 0.148 / 0.215 / 0.203 (N11)."""
    al, ga = 1.5659307764265669 ** (-2 / 3), 0.67 / 0.65
    cc = amd.critical_amd_collision(al, ga)
    e_eq = bisect(lambda e: amd.relative_amd(e, e, al, ga) - cc, 0, 0.9)
    e_b = bisect(lambda e: amd.relative_amd(e, 0, al, ga) - cc, 0, 0.9)
    e_c = bisect(lambda e: amd.relative_amd(0, e, al, ga) - cc, 0, 0.9)
    assert (e_eq, e_b, e_c) == pytest.approx((0.1478176, 0.2148879, 0.2025903), abs=1e-6)


@given(e1=ecc, e2=ecc, alpha=alphas, gamma=gammas)
def test_amd_is_non_negative_and_zero_only_for_circular(
    e1: float, e2: float, alpha: float, gamma: float
) -> None:
    c = amd.relative_amd(e1, e2, alpha, gamma)
    assert c >= 0
    if e1 == 0 and e2 == 0:
        assert c == 0


@given(alpha=alphas, gamma=gammas)
def test_critical_eccentricity_lies_on_collision_line(alpha: float, gamma: float) -> None:
    e_c = amd.critical_eccentricity(alpha, gamma)
    assert 0 < e_c < min(1.0, 1 / alpha - 1)
    e_out = 1 - alpha - alpha * e_c
    assert 0 <= e_out < 1
    # C_c is the minimum of the relative AMD along the collision line (Laskar & Petit 2017, Sect. 3)
    cc = amd.critical_amd_collision(alpha, gamma)
    for f in (0.9, 0.97, 1.03, 1.1):
        e = e_c * f
        if 0 <= e <= min(1.0, 1 / alpha - 1):
            e2 = 1 - alpha - alpha * e
            if 0 <= e2 < 1:
                assert amd.relative_amd(e, e2, alpha, gamma) >= cc - 1e-12


@given(alpha=st.floats(0.1, 0.95), g1=gammas, g2=gammas)
def test_critical_amd_increases_with_gamma(alpha: float, g1: float, g2: float) -> None:
    assume(abs(g1 - g2) > 1e-6 * max(g1, g2))
    lo, hi = sorted((g1, g2))
    assert amd.critical_amd_collision(alpha, lo) < amd.critical_amd_collision(alpha, hi)


@given(a1=st.floats(0.1, 0.95), a2=st.floats(0.1, 0.95), gamma=gammas)
def test_critical_amd_decreases_with_alpha(a1: float, a2: float, gamma: float) -> None:
    assume(abs(a1 - a2) > 1e-6)
    lo, hi = sorted((a1, a2))
    assert amd.critical_amd_collision(lo, gamma) > amd.critical_amd_collision(hi, gamma)


def test_close_pair_asymptote() -> None:
    # Laskar & Petit (2017): C_c ~ gamma / (gamma + 1) * eta^2 / 2 for eta = 1 - alpha -> 0
    eta, gamma = 1e-3, 2.0
    assert amd.critical_amd_collision(1 - eta, gamma) == pytest.approx(
        gamma / (gamma + 1) * eta**2 / 2, rel=1e-2
    )


def test_invalid_alpha() -> None:
    with pytest.raises(ValueError, match="alpha"):
        amd.critical_eccentricity(1.2, 1.0)


@pytest.mark.parametrize("eps", [1e-6, 1e-5, 1e-4, 1e-3])
def test_mmr_overlap_limits_match_petit_2017_developments(eps: float) -> None:
    # the paper rounds the exact coefficient 4 r^(2/7) / 3^(6/7) = 1.4646 to 1.46
    assert 1 - amd.alpha_circular_overlap(eps) == pytest.approx(1.46 * eps ** (2 / 7), rel=5e-3)
    assert 1 - amd.alpha_resonance_switch(eps) == pytest.approx(1.50 * eps**0.25 + 0.316 * eps**0.5, rel=0.02)


def test_mmr_critical_amd_branches() -> None:
    eps = 1e-4
    a_cir = amd.alpha_circular_overlap(eps)
    assert amd.critical_amd_mmr(a_cir + 1e-3, 1.0, eps) == 0.0
    a_r = amd.alpha_resonance_switch(eps)
    assert amd.critical_amd(a_r - 0.01, 1.0, eps)[1] == "collision"
    assert amd.critical_amd(a_r + 0.01, 1.0, eps)[1] == "mmr_overlap"
    # near alpha_R the two critical AMDs are close (that is how alpha_R is defined)
    c0 = amd.critical_amd_collision(a_r, 1.0)
    c1 = amd.critical_amd_mmr(a_r, 1.0, eps)
    assert c1 == pytest.approx(c0, rel=0.15)
    assert amd.alpha_resonance_switch(10.0) == 0.0


def test_mmr_overlap_restricted_to_petit_2017_domain() -> None:
    """First-order overlap only above the 2:1 resonance and for eps <= eps_lim (Petit et al. 2017)."""
    assert amd.ALPHA_2_1 == pytest.approx(0.63, abs=1e-3)
    assert amd.alpha_circular_overlap(amd.EPS_LIM) == pytest.approx(amd.ALPHA_2_1, rel=1e-12)
    assert amd.EPS_LIM == pytest.approx(8.20e-3, rel=0.015)  # the paper's value uses rounded constants
    # eps = 5e-3: alpha_R = 0.58 lies below the 2:1 resonance; the switching rule alone would use C_MMR
    eps = 5e-3
    assert amd.alpha_resonance_switch(eps) < 0.60 < amd.ALPHA_2_1
    assert amd.critical_amd(0.60, 1.0, eps) == (amd.critical_amd_collision(0.60, 1.0), "collision")
    assert amd.outside_domain(0.60, eps) == "wide_of_2_1"
    assert amd.critical_amd(0.70, 1.0, eps)[1] == "mmr_overlap" and amd.outside_domain(0.70, eps) is None
    assert amd.critical_amd(0.40, 1.0, eps)[1] == "collision" and amd.outside_domain(0.40, eps) is None
    # eps = 1e-2 > eps_lim: no resonance branch at all; pairs with alpha > alpha_R = 0.50, where the switching
    # rule would use resonance overlap, are flagged, and wider pairs are in the collision regime
    for alpha in (0.30, 0.55, 0.62, 0.80):
        assert amd.critical_amd(alpha, 1.0, 1e-2)[1] == "collision"
    assert amd.alpha_resonance_switch(1e-2) == pytest.approx(0.50, abs=5e-3)
    assert amd.outside_domain(0.30, 1e-2) is None
    for alpha in (0.55, 0.62, 0.80):
        assert amd.outside_domain(alpha, 1e-2) == "eps_above_limit"
    # small eps: the domain covers every alpha
    assert all(amd.outside_domain(alpha, 1e-4) is None for alpha in (0.1, 0.5, 0.63, 0.9))


def test_pairs_outside_the_domain_are_never_amd_stable() -> None:
    # circular giants just wide of the 2:1 (eps = 5e-3, alpha = 0.60): beta = 0 with either critical AMD
    wide = real_of([2.5e-3, 2.5e-3], [1.0, 0.6**-1.5], [0.0, 0.0])
    p = amd.analyse(wide)["pairs"][0]
    assert p["critical_branch"] == "collision" and p["outside_domain"] == "wide_of_2_1" and p["beta"] == 0
    assert amd.classify(wide) is Verdict.MARGINAL
    r = amd.evaluate(wide, [])
    assert "outside the domain" in r.summary and any("2:1" in n for n in r.notes)
    # eps = 1e-2 > eps_lim at period ratio 2.05, where alpha_cir(eps) = 0.61 lies wide of the 2:1: no
    # circular-overlap claim from an extrapolated formula, and no AMD-stable verdict either
    heavy = real_of([5e-3, 5e-3], [1.0, 2.05], [0.0, 0.0])
    p = amd.analyse(heavy)["pairs"][0]
    assert p["alpha"] > amd.alpha_circular_overlap(1e-2)
    assert not p["circular_overlap"] and p["outside_domain"] == "eps_above_limit"
    assert amd.classify(heavy) is Verdict.MARGINAL
    r = amd.evaluate(heavy, [])
    assert not any("circular orbits" in n for n in r.notes) and any("ε_lim" in n for n in r.notes)
    # HD 204313 b / e-like pair (eps = 0.0185, period ratio 3.6): collision criterion, at most marginal
    far = real_of([9e-3, 9.5e-3], [1.0, 3.6], [0.05, 0.05])
    p = amd.analyse(far)["pairs"][0]
    assert p["critical_branch"] == "collision" and p["beta"] < 1
    assert amd.classify(far) is Verdict.MARGINAL
    # a light inner planet next to a heavy pair (period ratio 1.75, alpha > alpha_R): the summary keeps beta_S
    ups = real_of([1e-8, 5e-3, 5e-3], [1.0, 8.0, 14.0], [0.0, 0.1, 0.0])
    r = amd.evaluate(ups, [])
    assert [p["outside_domain"] for p in r.details["pairs"]] == [None, "eps_above_limit"]
    assert "outside the domain" in r.summary and "β_S = 1e+04" in r.summary


def test_wide_heavy_pairs_use_the_collision_criterion_of_laskar_petit_2017() -> None:
    """Pairs with eps > eps_lim but alpha <= alpha_R keep the AMD-stable verdict (Petit et al. 2017, Sect. 4.2).

    Laskar & Petit (2017, Fig. 5) list HD 168443, HD 147018, HD 169830 and nu Oph as strongly AMD-stable with
    beta = 2 beta_p; exostab called all four AMD "marginal" when every pair with eps > eps_lim was capped.
    """
    # HD 168443 b / c: 7.7 and 17.2 Jupiter masses (in M_sun) around a 1 M_sun star, period ratio 30.4
    hd168443 = real_of([7.35e-3, 1.64e-2], [1.0, 30.4], [0.53, 0.21])
    p = amd.analyse(hd168443)["pairs"][0]
    assert (
        p["epsilon"] > amd.EPS_LIM and p["alpha"] < amd.alpha_resonance_switch(p["epsilon"]) < amd.ALPHA_2_1
    )
    assert p["critical_branch"] == "collision" and p["outside_domain"] is None
    assert p["beta"] == pytest.approx(0.184, abs=1e-3)
    assert amd.classify(hd168443) is Verdict.STABLE
    r = amd.evaluate(hd168443, [])
    assert r.verdict is Verdict.STABLE and r.summary.startswith("AMD-stable")
    assert any("ε_lim" in n and "α ≤ α_R" in n for n in r.notes)
    # nu Oph-like pair (eps = 0.0171, period ratio 6.0): alpha = 0.30 < alpha_R = 0.43
    nu_oph = real_of([8.55e-3, 8.55e-3], [1.0, 6.0], [0.12, 0.18])
    assert amd.analyse(nu_oph)["pairs"][0]["outside_domain"] is None
    assert amd.classify(nu_oph) is Verdict.STABLE
    # the same masses at period ratio 1.75 (alpha = 0.69 > alpha_R) stay outside the domain: at most marginal
    close = real_of([8.55e-3, 8.55e-3], [1.0, 1.75], [0.0, 0.0])
    assert amd.analyse(close)["pairs"][0]["outside_domain"] == "eps_above_limit"
    assert amd.classify(close) is Verdict.MARGINAL


@given(e=st.floats(0, 0.4), de=st.floats(0.001, 0.3))
def test_beta_grows_with_eccentricity_and_verdict_never_improves(e: float, de: float) -> None:
    order = {Verdict.STABLE: 0, Verdict.MARGINAL: 1, Verdict.UNSTABLE: 2}
    ms, ps = [3e-5, 3e-5], [1.0, 2.2]
    r1 = real_of(ms, ps, [e, e])
    r2 = real_of(ms, ps, [min(e + de, 0.9), min(e + de, 0.9)])
    b1 = max(p["beta"] for p in amd.analyse(r1)["pairs"])
    b2 = max(p["beta"] for p in amd.analyse(r2)["pairs"])
    assert b2 >= b1
    assert order[amd.classify(r2)] >= order[amd.classify(r1)]


def test_classification_cases() -> None:
    circ = real_of([3e-5, 3e-5], [1.0, 2.2], [0.0, 0.0])
    assert amd.classify(circ) is Verdict.STABLE
    ecc_pair = real_of([3e-5, 3e-5], [1.0, 2.2], [0.5, 0.5])
    assert amd.classify(ecc_pair) is Verdict.UNSTABLE
    # AMD-unstable (resonance-overlap branch) but Hill stable: the Hill criterion is stricter than the
    # collision criterion (Petit et al. 2018), so this only happens where C_MMR < C_H
    mid = real_of([1e-3, 1e-3], [1.0, 1.6], [0.035, 0.0])
    info = amd.analyse(mid)["pairs"][0]
    assert info["critical_branch"] == "mmr_overlap"
    assert info["beta"] > 1 > info["beta_hill"]
    assert amd.classify(mid) is Verdict.MARGINAL
    # neither criterion holds with C = 2 C_p, but the coplanar pair is Hill stable: not "unstable"
    hot = real_of([1e-3, 1e-3], [1.0, 1.6], [0.05, 0.0])
    info = amd.analyse(hot)["pairs"][0]
    assert info["beta"] > 1 and info["beta_hill"] > 1 > info["beta_hill_coplanar"]
    assert amd.classify(hot) is Verdict.MARGINAL
    # weakly AMD-stable: a light inner planet next to an eccentric giant
    weak = real_of([1e-8, 1e-3], [1.0, 8.0], [0.0, 0.15])
    w = amd.analyse(weak)
    assert all(p["beta"] < 1 for p in w["pairs"]) and w["beta_star"] > 1
    assert amd.classify(weak) is Verdict.MARGINAL
    three = real_of([3e-5] * 3, [1.0, 2.0, 4.0], [0.4, 0.4, 0.4])
    assert amd.classify(three) is Verdict.MARGINAL


def test_equipartition_convention_of_laskar_petit_2017() -> None:
    """beta = 2 beta_p and beta_S = 2 beta_Sp (Laskar & Petit 2017, Sect. 6; Petit et al. 2017, Sect. 5)."""
    ms, ps, es = [3e-5, 3e-5], [1.0, 2.2], [0.2, 0.2]
    r = real_of(ms, ps, es)
    info = amd.analyse(r)
    p = info["pairs"][0]
    # the coplanar AMD C_p, computed independently: Lambda_k / sqrt(G M_*) = m_k sqrt(a_k)
    a = r.semi_major_axes()
    lam = [m * math.sqrt(float(ak)) for m, ak in zip(ms, a)]
    c_p = sum(lk * (1 - math.sqrt(1 - e**2)) for lk, e in zip(lam, es))
    assert p["relative_amd"] == pytest.approx(c_p / lam[1])
    assert p["beta_coplanar"] == pytest.approx(c_p / lam[1] / p["critical_amd"])
    assert p["beta"] == pytest.approx(2 * p["beta_coplanar"])
    assert p["beta_hill"] == pytest.approx(2 * p["beta_hill_coplanar"])
    assert info["beta_star_coplanar"] == pytest.approx(c_p / lam[0])
    assert info["beta_star"] == pytest.approx(2 * c_p / lam[0])
    # AMD-stable for exactly coplanar orbits (beta_p = 0.61), but not with the AMD of the inclinations
    assert p["beta_coplanar"] < 1 <= p["beta"]
    assert amd.classify(r) is Verdict.MARGINAL
    res = amd.evaluate(r, [])
    assert any("largest β_p = 0.611" in n for n in res.notes)


def test_evaluate_texts() -> None:
    r = amd.evaluate(real_of([3e-5, 3e-5], [1.0, 2.2], [0.0, 0.01]), [])
    assert r.verdict is Verdict.STABLE and r.summary.startswith("AMD-stable")
    r = amd.evaluate(real_of([1e-8, 1e-3], [1.0, 8.0], [0.0, 0.15]), [])
    assert r.summary.startswith("Weakly")
    r = amd.evaluate(real_of([1e-3, 1e-3], [1.0, 1.6], [0.035, 0.0]), [])
    assert "Hill stable in the AMD framework" in r.summary
    r = amd.evaluate(real_of([1e-3, 1e-3], [1.0, 1.6], [0.05, 0.0]), [])
    assert r.verdict is Verdict.MARGINAL and "not 'unstable'" in r.summary and "β_H,p = 0.844" in r.summary
    r = amd.evaluate(real_of([3e-5, 3e-5], [1.0, 2.2], [0.5, 0.5]), [])
    assert r.summary.startswith("Neither") and "even for exactly coplanar orbits" in r.summary
    r = amd.evaluate(
        real_of([3e-5] * 3, [1.0, 1.1, 4.0], [0.4, 0.4, 0.4]),
        [real_of([3e-5] * 3, [1.0, 2.0, 4.0], [0.0] * 3)],
    )
    assert r.summary.startswith("AMD-unstable") and "β ≥ 1" in r.summary
    assert any("overlap" in n for n in r.notes)
    assert math.isinf(max(p["beta"] for p in r.details["pairs"]))
    r = amd.evaluate(
        real_of([3e-5, 3e-5], [1.0, 2.2], [0.0, 0.0]), [real_of([3e-5, 3e-5], [1.0, 2.2], [0.5, 0.5])]
    )
    assert r.nominal_verdict is Verdict.STABLE and r.verdict is Verdict.MARGINAL
    assert any("draws disagree" in n for n in r.notes)


def test_assumed_eccentricities_are_disclosed() -> None:
    """An eccentricity that was not measured is 0 in every run, so beta = 0 says nothing about the real orbits."""
    circ = real_of([3e-5, 3e-5], [1.0, 2.2], [0.0, 0.0])
    r = amd.evaluate(circ, [], assumed_eccentricities=["p0", "p1"])
    assert r.verdict is Verdict.STABLE  # the arithmetic is unchanged; what changes is the disclosure
    assert r.summary.startswith("AMD-stable only because no eccentricity is measured")
    assert "collisions are excluded" not in r.summary
    assert any(n.startswith("Eccentricity assumed, not measured") and "p0, p1" in n for n in r.notes)
    # one measured eccentricity: the usual summary, and a note on the other planet
    part = real_of([3e-5, 3e-5], [1.0, 2.2], [0.0, 0.01])
    r = amd.evaluate(part, [], assumed_eccentricities=["p0"])
    assert r.summary.startswith("AMD-stable: largest β")
    assert any("for: p0. This planet adds no AMD, so β and β_S are lower limits" in n for n in r.notes)
    # measured eccentricities: no such note
    assert not any("assumed, not measured" in n for n in amd.evaluate(part, []).notes)


def test_check_system_passes_the_assumed_eccentricities() -> None:
    s = two_planet_system()
    planets = tuple(
        p.model_copy(update={"eccentricity": V(0.0, provenance=Provenance.ASSUMED)}) for p in s.planets
    )
    s = s.model_copy(update={"planets": planets})
    res = check_system(s, CheckSettings(orbits=100, draws=2, jobs=1, n_samples=5, ias15_check=False))
    a = res.report.indicators["amd"]
    assert a.verdict is Verdict.STABLE and "no eccentricity is measured" in a.summary
    assert any("Test b, Test c" in n for n in a.notes)


@pytest.mark.parametrize(
    "ms",
    [
        [1e-200 * 3e-6, 5 * 3e-6],  # a ZeroDivisionError
        [1e-12 * 3e-6, 10 * 9.5e-4],  # at the period of a heavy planet: "alpha must be in (0, 1)"
    ],
)
def test_a_pair_the_critical_amd_cannot_handle_is_named(ms: list[float]) -> None:
    periods = [0.1, 0.3] if ms[0] < 1e-100 else [0.1, 0.1]
    with pytest.raises(UnusableParametersError, match="p0 / p1: the critical AMD cannot be evaluated"):
        amd.analyse(real_of(ms, periods, [0.0, 0.0]))
