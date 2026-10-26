import math

import pytest
from hypothesis import given
from hypothesis import strategies as st

from conftest import hill_limit_ratio, two_planet_system
from exostab.indicators import Verdict, amd, hill
from exostab.sampling import Body, Realization, realizations
from exostab.units import MEARTH_IN_MSUN, MJUP_IN_MSUN

masses = st.floats(1e-8, 1e-3)


def real_of(
    ms: list[float], periods: list[float], es: list[float] | None = None, m_star: float = 1.0
) -> Realization:
    es = es or [0.0] * len(ms)
    return Realization(
        label="x",
        m_star=m_star,
        bodies=tuple(Body(f"p{k}", m, P, e, 0.0, 0.0) for k, (m, P, e) in enumerate(zip(ms, periods, es))),
    )


def test_circular_limit_tends_to_two_sqrt_three() -> None:
    assert hill.gladman_critical_separation(1e-10, 1e-10, 1.0) == pytest.approx(2 * math.sqrt(3), rel=1e-3)


def test_circular_limit_values_quoted_in_the_module_docstring() -> None:
    """In mean-a mutual Hill radii the limit differs from 2 sqrt(3) only at order (m / M_*)^(2/3)."""
    doc = hill.__doc__ or ""
    earth = hill.gladman_critical_separation(MEARTH_IN_MSUN, MEARTH_IN_MSUN, 1.0)
    jupiter = hill.gladman_critical_separation(MJUP_IN_MSUN, MJUP_IN_MSUN, 1.0)
    assert f"{earth:.3f}" == "3.463" and "3.463 for two Earth-mass" in doc
    assert f"{jupiter:.3f}" == "3.429" and "3.429 for two Jupiter-mass" in doc
    # the deviation scales as mu^(2/3), not mu^(1/3)
    dev = [2 * math.sqrt(3) - hill.gladman_critical_separation(m, m, 1.0) for m in (1e-8, 1e-6)]
    assert dev[1] / dev[0] == pytest.approx(100 ** (2 / 3), rel=0.01)


def test_circular_limit_beyond_a_ratio_of_ten() -> None:
    """A very massive inner body puts the limit beyond a_2 / a_1 = 10; it is still found (issue #26)."""
    m1, m2 = 0.8, 1e-3
    crit = hill.gladman_critical_separation(m1, m2, 1.0)
    assert math.isfinite(crit) and crit > 0
    # convert back to a_2 / a_1 = (1 + x) / (1 - x) with x = crit * ((m1 + m2) / 3)^(1/3) / 2
    x = crit * ((m1 + m2) / 3) ** (1 / 3) / 2
    ratio = (1 + x) / (1 - x)
    assert ratio > 10
    assert hill.gladman_margin(m1, m2, 1.0, ratio, 0.0, 0.0, 1.0) == pytest.approx(0.0, abs=1e-9)
    assert hill.gladman_margin(m1, m2, 1.0, ratio * 0.99, 0.0, 0.0, 1.0) < 0
    assert hill.gladman_margin(m1, m2, 1.0, ratio * 1.01, 0.0, 0.0, 1.0) > 0


def test_pair_table_with_a_very_massive_inner_body() -> None:
    """The heavy-inner-body file of issue #26 (0.16 M_sun around a 0.2 M_sun star) no longer raises."""
    real = real_of([0.16, 10 * MEARTH_IN_MSUN], [10.0, 200.0], m_star=0.2)
    (row,) = hill.pair_table(real)
    assert math.isfinite(row["gladman_critical_hill"]) and row["gladman_critical_hill"] > 0


@given(m1=masses, m2=masses, ratio=st.floats(1.01, 3.0), m_star=st.floats(0.08, 3.0))
def test_hill_spacing_is_symmetric_in_the_two_masses(
    m1: float, m2: float, ratio: float, m_star: float
) -> None:
    a1, a2 = 1.0, ratio
    assert hill.separation_in_hill_radii(m1, m2, a1, a2, m_star) == pytest.approx(
        hill.separation_in_hill_radii(m2, m1, a1, a2, m_star)
    )
    assert hill.mutual_hill_radius(m1, m2, a1, a2, m_star) > 0


@given(m1=masses, m2=masses, alpha=st.floats(0.3, 0.999), e1=st.floats(0, 0.5), e2=st.floats(0, 0.5))
def test_gladman_equals_petit_2018_amd_form(m1: float, m2: float, alpha: float, e1: float, e2: float) -> None:
    """Gladman's criterion and the AMD form of Petit et al. (2018) are the same inequality (to O(eps))."""
    gm = hill.gladman_margin(m1, m2, alpha, 1.0, e1, e2, 1.0)
    gamma, eps = m1 / m2, m1 + m2
    rel = amd.relative_amd(e1, e2, alpha, gamma)
    ch = amd.critical_amd_hill(alpha, gamma, eps)
    if abs(gm) > 1e-6 and abs(rel - ch) > 1e-6 * max(1.0, abs(ch)):
        assert (gm > 0) == (rel < ch)


@given(e=st.floats(0, 0.3), de=st.floats(0.001, 0.2))
def test_gladman_margin_decreases_with_eccentricity(e: float, de: float) -> None:
    m = 1e-5
    lo = hill.gladman_margin(m, m, 1.0, 1.2, e, e, 1.0)
    hi = hill.gladman_margin(m, m, 1.0, 1.2, min(e + de, 0.99), min(e + de, 0.99), 1.0)
    assert hi < lo


def test_two_planet_verdicts() -> None:
    m = 3e-5
    limit = hill_limit_ratio(m)
    wide = real_of([m, m], [1.0, 1.3 * limit])
    close = real_of([m, m], [1.0, 0.95 * limit])
    assert hill.classify(wide) is Verdict.STABLE
    assert hill.classify(close) is Verdict.UNSTABLE
    crossing = real_of([m, m], [1.0, 3.0], es=[0.6, 0.6])
    assert hill.pair_table(crossing)[0]["orbits_cross"]
    assert hill.classify(crossing) is Verdict.UNSTABLE


def test_multi_planet_heuristic() -> None:
    m = 3e-6
    spaced = real_of([m] * 3, [1.0, 2.0, 4.0])
    tight = real_of([m] * 3, [1.0, 1.2, 1.44])
    assert min(r["separation_hill"] for r in hill.pair_table(spaced)) > hill.DELTA_MULTI
    assert hill.classify(spaced) is Verdict.STABLE
    assert hill.classify(tight) is Verdict.MARGINAL


def evenly_spaced(n: int, m: float, k_hill: float, e: float) -> Realization:
    """n planets of mass m (M_sun) around a solar-mass star, k_hill mutual Hill radii apart, all with e."""
    x = k_hill * (2 * m / 3) ** (1 / 3) / 2
    return real_of([m] * n, [((1 + x) / (1 - x)) ** (1.5 * k) for k in range(n)], [e] * n)


def test_required_spacing_follows_pu_wu_eccentricity_scaling() -> None:
    # Pu & Wu (2015), Sect. 5: sigma_e ~ 0.02 "requires that K_eff >= 12.2" for mu_1 ~ mu_2 ~ 2e-5
    assert hill.required_separation(2e-5, 2e-5, 0.02, 0.0, 1.0) == pytest.approx(12.2, abs=0.05)
    # their Eq. 14: one more Hill radius per 0.01 of eccentricity at e_H = 0.024
    e_h = (4e-5 / 3) ** (1 / 3)
    assert e_h == pytest.approx(0.024, abs=1e-3)
    assert hill.required_separation(2e-5, 2e-5, 0.05, 0.01, 1.0) - hill.required_separation(
        2e-5, 2e-5, 0.04, 0.0, 1.0
    ) == pytest.approx(0.01 * 2.4 / e_h)
    # circular orbits: the 12 of DECISIONS.md D12 is a floor; giant planets have a larger e_H
    assert hill.required_separation(3e-6, 3e-6, 0.0, 0.0, 1.0) == hill.DELTA_MULTI
    assert hill.required_separation(1e-3, 1e-3, 0.04, 0.0, 1.0) == hill.DELTA_MULTI


def test_multi_planet_heuristic_respects_eccentricities() -> None:
    m = 10 * MEARTH_IN_MSUN
    # 13 mutual Hill radii apart and e = 0.12: N-body finds most such systems chaotic within 1e4 orbits
    hot = evenly_spaced(5, m, 13.0, 0.12)
    rows = hill.pair_table(hot)
    assert all(12 < r["separation_hill"] < 13.5 and r["gladman_margin"] > 0 for r in rows)
    assert hill.classify(hot) is Verdict.MARGINAL
    res = hill.evaluate(hot, [])
    assert "13.0" in res.summary and "20.8" in res.summary and "extrapolated beyond σ_e = 0.05" in res.summary
    # inside Pu & Wu's eccentricity range: e = 0.03 needs 12.9 mutual Hill radii for these masses
    assert hill.classify(evenly_spaced(5, m, 12.5, 0.03)) is Verdict.MARGINAL
    assert hill.classify(evenly_spaced(5, m, 13.5, 0.03)) is Verdict.STABLE
    assert hill.classify(evenly_spaced(5, m, 12.5, 0.0)) is Verdict.STABLE
    res = hill.evaluate(evenly_spaced(3, m, 12.5, 0.03), [])
    assert res.verdict is Verdict.MARGINAL and "12.9" in res.summary
    # an eccentricity above 0.05 is never called stable, even when widely spaced (conservative cap)
    wide_hot = evenly_spaced(3, m, 40.0, 0.06)
    assert hill.classify(wide_hot) is Verdict.MARGINAL
    summary = hill.evaluate(wide_hot, []).summary
    assert "above 0.05" in summary and "conservative" in summary
    # 0.05 is the largest Rayleigh dispersion Pu & Wu simulated, not a limit on single eccentricities, which
    # were often larger in their sample: the summary must not say they lie outside the calibrated range
    assert "calibrated" not in summary and "dispersion" in summary


def test_evaluate_summaries_and_draw_disagreement() -> None:
    res = hill.evaluate(real_of([3e-5, 3e-5], [1.0, 2.0]), [])
    assert res.verdict is Verdict.STABLE and "Hill stable" in res.summary and res.draws is None
    s = two_planet_system(period_ratio=1.2, m_earth=(10.0, 10.0), err=True)
    reals = realizations(s, 20, seed=0)
    res = hill.evaluate(reals[0], reals[1:])
    assert res.name == "hill" and res.draws is not None and res.draws.n == 20
    res = hill.evaluate(real_of([3e-5, 3e-5], [1.0, 1.01]), [])
    assert res.verdict is Verdict.UNSTABLE and "Not Hill stable" in res.summary
    res = hill.evaluate(real_of([3e-6] * 3, [1.0, 2.0, 4.0]), [real_of([3e-6] * 3, [1.0, 1.2, 1.44])] * 5)
    assert res.nominal_verdict is Verdict.STABLE
    assert res.verdict is Verdict.MARGINAL and any("draws disagree" in n for n in res.notes)
    assert "heuristic" in " ".join(res.notes)
    res = hill.evaluate(real_of([3e-6] * 3, [1.0, 2.0, 4.0]), [])
    assert res.verdict is Verdict.STABLE and "at least" in res.summary
