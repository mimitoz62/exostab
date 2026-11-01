import math

import numpy as np
import pytest
import rebound
from hypothesis import given
from hypothesis import strategies as st

from conftest import V, two_planet_system
from exostab import sampling
from exostab.integrate import RunConfig, build_simulation
from exostab.models import (
    DataSource,
    MassKind,
    Phase,
    PhaseKind,
    Planet,
    Provenance,
    Star,
    System,
    UnusableParametersError,
)
from exostab.units import days_to_years, mearth_to_msun


def test_nominal_uses_central_values() -> None:
    s = two_planet_system(err=True, m_earth=(10.0, 20.0), e=(0.1, 0.2))
    nom = sampling.realizations(s, 0, seed=1)[0]
    assert nom.label == "nominal"
    assert nom.m_star == 1.0
    assert [b.m for b in nom.bodies] == pytest.approx([mearth_to_msun(10.0), mearth_to_msun(20.0)])
    assert [b.e for b in nom.bodies] == [0.1, 0.2]
    assert nom.bodies[0].P == pytest.approx(days_to_years(100.0))


def test_realizations_are_reproducible_and_prefix_stable() -> None:
    s = two_planet_system(err=True)
    a = sampling.realizations(s, 5, seed=3)
    b = sampling.realizations(s, 8, seed=3)
    assert a == b[:6]
    c = sampling.realizations(s, 5, seed=4)
    assert a[1:] != c[1:]


def test_draws_vary_within_errors() -> None:
    s = two_planet_system(err=True)
    draws = sampling.realizations(s, 200, seed=0)[1:]
    ms = np.array([d.bodies[0].m for d in draws]) / mearth_to_msun(1.0)
    assert ms.mean() == pytest.approx(10.0, abs=0.3)
    assert ms.std() == pytest.approx(1.0, rel=0.2)
    assert all(d.bodies[0].e >= 0 for d in draws)


def test_split_normal_is_asymmetric() -> None:
    rng = np.random.default_rng(0)
    x = np.array([sampling.split_normal(rng, 0.0, 2.0, 0.5) for _ in range(20000)])
    assert np.std(x[x > 0]) > 2 * np.std(x[x < 0])


def test_upper_limit_nominal_is_limit_and_draws_are_below() -> None:
    s = two_planet_system()
    p = s.planets[1].model_copy(update={"eccentricity": V(0.3, provenance=Provenance.UPPER_LIMIT)})
    s = s.model_copy(update={"planets": (s.planets[0], p)})
    reals = sampling.realizations(s, 50, seed=0)
    assert reals[0].bodies[1].e == 0.3
    es = [r.bodies[1].e for r in reals[1:]]
    assert all(0 <= e <= 0.3 for e in es)
    assert np.std(es) > 0.05


def test_eccentricity_capped() -> None:
    s = two_planet_system()
    p = s.planets[1].model_copy(update={"eccentricity": V(0.9, 0.5)})
    s = s.model_copy(update={"planets": (s.planets[0], p)})
    assert max(r.bodies[1].e for r in sampling.realizations(s, 100, seed=0)) <= sampling.E_MAX


def test_nominal_eccentricity_above_the_cap_is_refused() -> None:
    # The nominal run used to be capped silently: the verdict was for e = 0.95 while the card showed 0.97.
    s = two_planet_system()
    p = s.planets[1].model_copy(update={"eccentricity": V(0.97)})
    with pytest.raises(ValueError, match=r"above 0\.95"):
        sampling.realizations(s.model_copy(update={"planets": (s.planets[0], p)}), 0, seed=0)


def test_true_to_mean_anomaly() -> None:
    assert sampling.true_to_mean_anomaly(0.0, 0.3) == pytest.approx(0.0)
    assert sampling.true_to_mean_anomaly(math.pi, 0.3) == pytest.approx(math.pi)
    assert sampling.true_to_mean_anomaly(1.0, 0.0) == pytest.approx(1.0)
    # agrees with REBOUND's own conversion
    sim = rebound.Simulation()
    sim.add(m=1.0)
    sim.add(m=0.0, a=1.0, e=0.4, f=2.0)
    assert sampling.true_to_mean_anomaly(2.0, 0.4) == pytest.approx(sim.particles[1].M)


def _timed_system(kind: PhaseKind, t_ref: float, omega: float = 90.0, e: float = 0.0) -> System:
    base = two_planet_system()
    p0 = base.planets[0].model_copy(
        update={"phase": Phase(kind=kind, value=V(t_ref, 0.001)), "omega_deg": V(omega), "eccentricity": V(e)}
    )
    p1 = base.planets[1].model_copy(update={"phase": Phase(kind=kind, value=V(t_ref + 30.0, 0.001))})
    return base.model_copy(update={"planets": (p0, p1)})


def test_transit_phase_puts_planet_on_line_of_sight_at_mid_transit() -> None:
    s = _timed_system(PhaseKind.TRANSIT, 2460000.0, omega=90.0)
    t0 = sampling.choose_epoch(s)
    assert t0 in (2460000.0, 2460030.0)
    nom = sampling.realizations(s, 0, seed=0)[0]
    b0 = nom.bodies[0]
    # at t0 the true longitude of a planet that transits at t0 is pi/2 (omega + f = pi/2)
    if t0 == 2460000.0:
        assert (b0.pomega + b0.M) % (2 * math.pi) == pytest.approx(math.pi / 2)


def test_periastron_phase() -> None:
    s = _timed_system(PhaseKind.PERIASTRON, 2460000.0, e=0.2)
    nom = sampling.realizations(s, 0, seed=0)[0]
    t0 = sampling.choose_epoch(s)
    expected = 2 * math.pi * (t0 - 2460000.0) / 100.0 % (2 * math.pi)
    assert nom.bodies[0].M == pytest.approx(expected)


def test_epoch_prefers_small_propagated_uncertainty() -> None:
    s = _timed_system(PhaseKind.TRANSIT, 2460000.0)
    p1 = s.planets[1].model_copy(update={"period_days": V(250.0, 5.0)})
    s = s.model_copy(update={"planets": (s.planets[0], p1)})
    # planet c has a poorly known period, so the epoch should be c's own transit time
    assert sampling.choose_epoch(s) == 2460030.0
    assert sampling.phase_sigma_rad(s.planets[1], 2460030.0) < 0.01


def test_epoch_given_or_absent() -> None:
    s = two_planet_system()
    assert sampling.choose_epoch(s) is None
    assert sampling.choose_epoch(s.model_copy(update={"epoch_jd": 5.0})) == 5.0


def test_mean_longitudes_next_to_reference_times_need_an_epoch() -> None:
    # Planet b's mean longitude has no stated epoch, so its phase relative to c's transit time is undefined.
    s = two_planet_system()
    c = s.planets[1].model_copy(update={"phase": Phase(kind=PhaseKind.TRANSIT, value=V(2460000.0, 0.001))})
    mixed = s.model_copy(update={"planets": (s.planets[0], c)})
    with pytest.raises(ValueError, match="epoch_jd"):
        sampling.choose_epoch(mixed)
    with pytest.raises(ValueError, match="epoch_jd"):
        sampling.realizations(mixed, 0, seed=0)
    assert sampling.choose_epoch(mixed.model_copy(update={"epoch_jd": 2460003.0})) == 2460003.0


def test_random_phase_and_omega_are_uniform() -> None:
    s = two_planet_system(phases=None)
    p = s.planets[0].model_copy(update={"omega_deg": V(None, provenance=Provenance.RANDOMIZED)})
    s = s.model_copy(update={"planets": (p, s.planets[1])})
    reals = sampling.realizations(s, 400, seed=0)
    Ms = np.array([r.bodies[0].M for r in reals])
    ws = np.array([r.bodies[0].pomega for r in reals])
    for x in (Ms, ws):
        assert 0 <= x.min() and x.max() < 2 * math.pi
        assert np.histogram(x, bins=4, range=(0, 2 * math.pi))[0].min() > 60


def test_isotropic_prior_scales_minimum_masses_only() -> None:
    s = two_planet_system()
    p0 = s.planets[0].model_copy(update={"mass_kind": MassKind.MINIMUM})
    s = s.model_copy(update={"planets": (p0, s.planets[1])})
    reals = sampling.realizations(s, 300, seed=0, inclination_prior="isotropic")
    assert reals[0].sin_i == 1.0
    sin_i = np.array([r.sin_i for r in reals[1:]])
    assert sin_i.min() >= sampling.SIN_I_MIN - 1e-12 and sin_i.max() <= 1
    for r in reals[1:]:
        assert r.bodies[0].m == pytest.approx(mearth_to_msun(10.0) / r.sin_i)
        assert r.bodies[1].m == pytest.approx(mearth_to_msun(10.0))


def test_bodies_sorted_after_period_draws() -> None:
    s = two_planet_system(period_ratio=1.01, err=True)
    p1 = s.planets[1].model_copy(update={"period_days": V(101.0, 5.0)})
    s = s.model_copy(update={"planets": (s.planets[0], p1)})
    for r in sampling.realizations(s, 100, seed=0):
        assert r.bodies[0].P <= r.bodies[1].P


@given(
    m1=st.floats(1e-7, 1e-3),
    m2=st.floats(1e-7, 1e-3),
    ratio=st.floats(1.2, 5.0),
    m_star=st.floats(0.1, 2.0),
)
def test_semi_major_axes_match_rebound(m1: float, m2: float, ratio: float, m_star: float) -> None:
    real = sampling.Realization(
        label="x",
        m_star=m_star,
        bodies=(
            sampling.Body("b", m1, 0.1, 0.0, 0.0, 0.0),
            sampling.Body("c", m2, 0.1 * ratio, 0.05, 1.0, 2.0),
        ),
    )
    sim = build_simulation(real, RunConfig())
    a = real.semi_major_axes()
    assert a[0] == pytest.approx(sim.particles[1].a, rel=1e-9)
    assert a[1] == pytest.approx(sim.particles[2].a, rel=1e-9)


def test_orbits_to_years_and_period_ratios() -> None:
    nom = sampling.realizations(two_planet_system(period_ratio=3.0), 0, seed=0)[0]
    assert sampling.orbits_to_years(nom, 10) == pytest.approx(10 * days_to_years(100.0))
    assert sampling.period_ratios(nom.bodies) == pytest.approx([3.0])


def test_with_body() -> None:
    nom = sampling.realizations(two_planet_system(), 0, seed=0)[0]
    changed = nom.with_body(1, e=0.3)
    assert changed.bodies[1].e == 0.3 and nom.bodies[1].e == 0.0


def test_star_and_period_missing_errors_are_fixed_in_draws() -> None:
    s = System(
        name="x",
        star=Star(name="x", mass_msun=V(1.0)),
        planets=(
            Planet(name="x b", period_days=V(10.0), mass_earth=V(1.0)),
            Planet(name="x c", period_days=V(20.0), mass_earth=V(1.0)),
        ),
        source=DataSource(kind="file"),
    )
    reals = sampling.realizations(s, 3, seed=0)
    assert {r.m_star for r in reals} == {1.0}
    assert {r.bodies[1].P for r in reals} == {days_to_years(20.0)}


def test_upper_limits_outside_masses_and_eccentricities_are_refused() -> None:
    # A stellar mass drawn uniformly from 0 to its limit inflates the planet-to-star mass ratios many times,
    # and the limit is the most stable choice, not the worst case.
    s = two_planet_system()
    star = s.star.model_copy(update={"mass_msun": V(1.0, provenance=Provenance.UPPER_LIMIT)})
    with pytest.raises(ValueError, match="upper limit"):
        sampling.realizations(s.model_copy(update={"star": star}), 3, seed=0)
    p = s.planets[1].model_copy(update={"period_days": V(250.0, provenance=Provenance.UPPER_LIMIT)})
    with pytest.raises(ValueError, match="Test c period"):
        sampling.realizations(s.model_copy(update={"planets": (s.planets[0], p)}), 3, seed=0)


def test_a_draw_that_is_not_finite_is_refused() -> None:
    # An omega error of 1e308 overflows in about 7% of the draws. The NaN angle stopped those runs at once, and 5 of 60
    # were reported as unstable.
    p = two_planet_system().planets[0]
    wild = p.model_copy(update={"omega_deg": V(90.0, 1e308)})
    system = two_planet_system().model_copy(update={"planets": (wild, two_planet_system().planets[1])})
    with pytest.raises(UnusableParametersError, match="Test b: an error bar is so large"):
        sampling.realizations(system, 60, seed=0)
    assert all(
        math.isfinite(b.M) for r in sampling.realizations(two_planet_system(), 60, seed=0) for b in r.bodies
    )
