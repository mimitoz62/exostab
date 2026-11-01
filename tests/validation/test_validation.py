"""Validation suite (``pytest -m slow``). Every tolerance is documented in docs/validation.md.

These tests compare exostab with physical expectations and with published results. They are slow
(minutes) and run nightly in CI rather than on every push.
"""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pytest
import yaml

from exostab._numerics import bisect
from exostab.analysis import CheckSettings, check_system
from exostab.data import load_system, load_system_file
from exostab.indicators import Verdict, amd, hill
from exostab.indicators.megno import MEGNO_CHAOTIC, classify_run
from exostab.integrate import RunConfig, build_simulation, run
from exostab.sampling import Body, Realization, realizations

pytestmark = pytest.mark.slow

HERE = Path(__file__).resolve().parent
EXAMPLES = HERE.parents[1] / "examples"


# ------------------------------------------------------------------------------------ 1. energy conservation


def inner_solar_system() -> Realization:
    """Sun + Mercury, Venus, Earth-Moon barycentre, Mars (coplanar).

    Approximate J2000 mean elements (a in AU, e, longitude of perihelion and mean longitude in degrees)
    and masses from the IAU sun/planet mass ratios. Exact values do not matter for this test: it checks
    that the integrator conserves energy, not that it reproduces the ephemeris.
    """
    planets = [
        ("Mercury", 1 / 6023600, 0.387098, 0.205630, 77.456, 252.251),
        ("Venus", 1 / 408523.71, 0.723332, 0.006773, 131.564, 181.980),
        ("Earth", 1 / 328900.56, 1.000000, 0.016710, 102.937, 100.464),
        ("Mars", 1 / 3098708, 1.523662, 0.093412, 336.060, 355.453),
    ]
    bodies = tuple(
        Body(n, m, a**1.5, e, math.radians(w), math.radians(L - w) % (2 * math.pi))
        for n, m, a, e, w, L in planets
    )
    return Realization("inner solar system", 1.0, bodies)


def test_inner_solar_system_energy_conservation_over_1e4_years() -> None:
    r = inner_solar_system()
    n_orbits = 1e4 / r.bodies[0].P  # 10,000 years
    wh = run(r, RunConfig(n_orbits=n_orbits, n_samples=100))
    assert wh.status == "completed" and wh.t_end >= 1e4 - 0.01
    assert wh.energy_error < 1e-7  # measured 1.4e-9 (WHFast, dt = T_p(Mercury) / 30)
    ias = run(r, RunConfig(n_orbits=n_orbits, integrator="ias15"))
    assert ias.energy_error < 1e-12  # measured 9e-15
    assert classify_run(wh) == classify_run(ias) == "regular"


# ------------------------------------------------------------------------------------ 2. Hill limit


def pair_at(delta: float, m: float = 1e-5, phase: float = 0.3) -> Realization:
    """Two equal circular planets exactly ``delta`` mutual Hill radii apart (as in the Note's notebook 02)."""
    x = 0.5 * ((2 * m) / 3) ** (1 / 3)
    a2 = (1 + delta * x) / (1 - delta * x)
    return Realization(
        "pair", 1.0, (Body("b", m, 1.0, 0.0, 0.0, 0.0), Body("c", m, a2**1.5, 0.0, 0.0, phase))
    )


def test_synthetic_pair_past_the_hill_limit_is_unstable() -> None:
    from exostab.models import DataSource, Phase, PhaseKind, Planet, Star, System, Value

    m_earth = 1e-5 / 3.0034896e-6
    ratio = ((1 + 2.5 * 0.5 * (2e-5 / 3) ** (1 / 3)) / (1 - 2.5 * 0.5 * (2e-5 / 3) ** (1 / 3))) ** 1.5
    planets = tuple(
        Planet(
            name=f"Synthetic {c}",
            period_days=Value(value=P, err_plus=1e-4, err_minus=1e-4),
            mass_earth=Value(value=m_earth, err_plus=0.1, err_minus=0.1),
            eccentricity=Value(value=0.0),
            omega_deg=Value(value=0.0),
            phase=Phase(kind=PhaseKind.MEAN_LONGITUDE, value=Value(value=lam, err_plus=180, err_minus=180)),
        )
        for c, P, lam in (("b", 365.25, 0.0), ("c", 365.25 * ratio, 17.0))
    )
    s = System(
        name="Synthetic",
        star=Star(name="S", mass_msun=Value(value=1.0)),
        planets=planets,
        source=DataSource(kind="file"),
    )
    res = check_system(s, CheckSettings(orbits=5000, draws=20, seed=3))
    assert hill.pair_table(res.realizations[0])[0]["separation_hill"] == pytest.approx(2.5, rel=1e-3)
    assert res.report.indicators["hill"].verdict is Verdict.UNSTABLE
    assert res.report.indicators["nbody"].verdict is Verdict.UNSTABLE
    assert res.report.overall.verdict is Verdict.UNSTABLE


PHASES = np.linspace(0.3, 2 * np.pi, 8, endpoint=False)  # starting phases of planet c (notebook 02)


@pytest.mark.parametrize(("delta", "expect_encounter"), [(2.2, True), (4.0, False), (4.5, False)])
def test_close_encounters_inside_and_none_beyond_the_gladman_limit(
    delta: float, expect_encounter: bool
) -> None:
    """Well inside the limit every phase meets at its first conjunction (within 15 orbits); beyond it
    (3.46 mutual Hill radii, Hill stable) no phase ever meets. Neither outcome depends on rounding."""
    met = [
        run(pair_at(delta, phase=p), RunConfig(n_orbits=5000, megno=False)).status == "encounter"
        for p in PHASES
    ]
    assert all(met) if expect_encounter else not any(met)
    # the criterion itself: 3.46 mutual Hill radii for these masses (full form, see indicators/hill.py)
    assert hill.gladman_critical_separation(1e-5, 1e-5, 1.0) == pytest.approx(3.462, abs=0.001)


def test_pairs_inside_the_gladman_limit_are_unstable_or_chaotic() -> None:
    """At 3.0 mutual Hill radii the motion is chaotic, and the time to the first close encounter is a chaotic
    transient with a long tail that depends on the last bit of the initial conditions: which phases meet
    within a finite horizon differs between machines (docs/validation.md). What holds everywhere is that no
    phase is regular and nearly all meet. Over 8 phases x 500 relative perturbations of 1e-14, 99.4-99.6% met
    within 2e4 orbits, never more than 2 of 8 did not, and those stayed chaotic (<Y> > 13)."""
    classes = [classify_run(run(pair_at(3.0, phase=p), RunConfig(n_orbits=2e4))) for p in PHASES]
    assert all(c in ("unstable", "chaotic") for c in classes), classes
    assert classes.count("unstable") >= 6, classes


# ------------------------------------------------------------------------------------ 3. known systems


def test_trappist1_is_never_unstable() -> None:
    res = check_system(load_system("TRAPPIST-1", offline=True), CheckSettings(draws=20, seed=0))
    rep = res.report
    assert rep.overall.verdict in (Verdict.STABLE, Verdict.MARGINAL)
    assert rep.indicators["nbody"].verdict is not Verdict.UNSTABLE
    assert res.runs[0].status == "completed"
    assert res.ias15 is not None and res.ias15.status == "completed"
    assert res.runs[0].energy_error < 1e-6


def test_gj876_laplace_resonance_is_stable_with_published_phases() -> None:
    s = load_system_file(HERE / "systems" / "gj876_rivera2010.yaml")
    res = check_system(s, CheckSettings(draws=20, seed=0))
    rep = res.report
    assert rep.indicators["nbody"].verdict is Verdict.STABLE
    assert classify_run(res.runs[0]) == "regular" and res.runs[0].megno == pytest.approx(2.0, abs=0.1)
    assert res.ias15 is not None and classify_run(res.ias15) == "regular"
    # The analytic criteria fail for this resonance-protected system, so the conservative overall verdict
    # is marginal, never unstable (see docs/validation.md).
    assert rep.indicators["hill"].verdict is Verdict.UNSTABLE
    assert rep.overall.verdict is Verdict.MARGINAL


# Mean transit periods of Ducrot et al. (2020, A&A 640, A112), Table 4, in days.
DUCROT_2020_PERIODS = (1.51088432, 2.42179346, 4.04978035, 6.09956479, 9.20659399, 12.3535557, 18.7672745)


def _largest_transit_period_difference(path: Path) -> float:
    """Largest difference, in days, between a planet's mean transit period over 1,500 d (IAS15) and Ducrot et al."""
    real = realizations(load_system_file(path), 0, 0)[0]
    sim = build_simulation(real, RunConfig(integrator="ias15"))
    dt = 0.05  # days
    times: list[list[float]] = [[] for _ in real.bodies]
    last = [math.inf] * len(real.bodies)
    for step in range(1, int(1500 / dt) + 1):
        sim.integrate(step * dt / 365.25, exact_finish_time=1)
        star = sim.particles[0]
        for i in range(len(real.bodies)):
            planet = sim.particles[i + 1]
            x = planet.x - star.x
            # exostab's line of sight points along +y, where every planet transits (sampling.py)
            if last[i] > 0 >= x and last[i] != math.inf and planet.y > star.y:
                times[i].append((step - 1 + last[i] / (last[i] - x)) * dt)
            last[i] = x
    fitted = [np.polyfit(np.arange(len(t)), t, 1)[0] for t in times]
    return max(abs(p - q) for p, q in zip(fitted, DUCROT_2020_PERIODS, strict=True))


def test_trappist1_agol2021_file_fits_the_transits_and_is_regular(tmp_path: Path) -> None:
    path = EXAMPLES / "trappist1_agol2021.yaml"
    system = load_system_file(path)
    for seed in (0, 1, 2):
        res = check_system(system, CheckSettings(draws=0, seed=seed, ias15_check=False))
        assert classify_run(res.runs[0]) == "regular"
    assert _largest_transit_period_difference(path) < 2e-3  # measured: 8.5e-4 d
    # The table's own omega, typed unchanged, misses it (f = 90 deg - omega against their 270 deg - omega).
    table = yaml.safe_load(path.read_text(encoding="utf-8"))
    for planet in table["planets"]:
        planet["omega_deg"]["value"] = (planet["omega_deg"]["value"] + 180) % 360
    as_typed = tmp_path / "as_typed.yaml"
    as_typed.write_text(yaml.safe_dump(table), encoding="utf-8")
    assert _largest_transit_period_difference(as_typed) > 1e-2  # measured: 0.019 d


def test_kepler11_nominal_configuration_is_stable_over_the_test_horizon() -> None:
    res = check_system(load_system("Kepler-11", offline=True), CheckSettings(draws=20, seed=0))
    nominal = res.runs[0]
    assert nominal.status == "completed" and nominal.n_orbits_innermost >= 1e4 - 1
    assert classify_run(nominal) == "regular"
    # regular with both integrators, as docs/validation.md states
    assert res.ias15 is not None and res.ias15.status == "completed" and classify_run(res.ias15) == "regular"
    assert res.report.indicators["nbody"].verdict is not Verdict.UNSTABLE
    assert res.report.overall.verdict is not Verdict.UNSTABLE


# ------------------------------------------------------------------------------------ 4. HD 127195 Research Note


@pytest.fixture(scope="module")
def hd127195():  # type: ignore[no-untyped-def]
    s = load_system_file(EXAMPLES / "hd127195_note.yaml")
    # The Note: 200 draws, 2e4 orbits of planet b, WHFast at P_b/30, MEGNO < 2.2 regular. exostab steps at
    # 1/30 of the shortest pericentre timescale instead: T_p/30 = 16.43 d against P_b/30 = 17.82 d.
    return check_system(s, CheckSettings(orbits=2e4, draws=200, seed=42))


def test_hd127195_geometry_matches_the_note(hd127195) -> None:  # type: ignore[no-untyped-def]
    nom = hd127195.realizations[0]
    a = nom.semi_major_axes()
    assert a[0] == pytest.approx(1.421249, rel=1e-5)  # Note results.json: a_b
    assert a[1] == pytest.approx(1.916839, rel=1e-5)  # a_c
    assert nom.bodies[1].P / nom.bodies[0].P == pytest.approx(1.56593, rel=1e-5)
    assert hill.pair_table(nom)[0]["separation_hill"] == pytest.approx(4.3709, rel=1e-3)  # mutual_hill


def test_hd127195_best_fit_is_regular(hd127195) -> None:  # type: ignore[no-untyped-def]
    assert classify_run(hd127195.runs[0]) == "regular"
    assert hd127195.runs[0].megno == pytest.approx(2.00, abs=0.02)  # Note: 2.000 at P_b/30
    assert classify_run(hd127195.ias15) == "regular"  # Note: 2.000 with IAS15


def test_hd127195_monte_carlo_matches_the_note(hd127195) -> None:  # type: ignore[no-untyped-def]
    counts = hd127195.report.indicators["nbody"].details["classification_counts"]
    n = sum(counts.values())
    assert n == 200
    # Note: 134 regular (67%), 57 chaotic, 9 close encounters (4.5%). Tolerance: 3 binomial sigmas.
    p_reg, p_enc = 0.67, 0.045
    assert counts["regular"] / n == pytest.approx(p_reg, abs=3 * math.sqrt(p_reg * (1 - p_reg) / n))
    assert counts["unstable"] / n == pytest.approx(p_enc, abs=3 * math.sqrt(p_enc * (1 - p_enc) / n))
    # The Note has no energy criterion. exostab checks the energy error over the whole run (DECISIONS.md, D8),
    # and a few chaotic draws exceed 1e-5 at a pericentre passage (11 of 200 measured): they are inconclusive.
    # Each of them is chaotic by MEGNO, so they belong to the Note's chaotic draws and leave the comparison
    # above unchanged; there are far fewer than the 20% that would make the indicator inconclusive.
    inconclusive = [r for r in hd127195.runs[1:] if classify_run(r) == "inconclusive"]
    assert len(inconclusive) == counts["inconclusive"] <= 0.1 * n
    assert all(r.status == "completed" and r.megno >= MEGNO_CHAOTIC for r in inconclusive)


def test_hd127195_every_draw_passes_the_collision_amd_test(hd127195) -> None:  # type: ignore[no-untyped-def]
    """Note N7: all 200 draws pass the Laskar & Petit (2017) collision criterion."""
    for r in hd127195.realizations:
        al = r.bodies[0].P ** (2 / 3) / r.bodies[1].P ** (2 / 3)
        ga = r.bodies[0].m / r.bodies[1].m
        assert amd.relative_amd(r.bodies[0].e, r.bodies[1].e, al, ga) < amd.critical_amd_collision(al, ga)


def test_hd127195_conclusion(hd127195) -> None:  # type: ignore[no-untyped-def]
    """The Note's conclusion: the published fit is regular, but a substantial part of the allowed
    parameter space is chaotic (and some of it has close encounters) although it is AMD-stable."""
    rep = hd127195.report
    assert rep.indicators["nbody"].nominal_verdict is Verdict.STABLE
    assert rep.indicators["nbody"].verdict is Verdict.MARGINAL
    assert rep.overall.verdict is Verdict.MARGINAL


def test_hd127195_amd_limits(hd127195) -> None:  # type: ignore[no-untyped-def]
    """Note N11: AMD limit e = 0.15 (equal e) / 0.21 (e_b alone) / 0.20 (e_c alone)."""
    nom = hd127195.realizations[0]
    al = (nom.bodies[0].P / nom.bodies[1].P) ** (2 / 3)
    ga = nom.bodies[0].m / nom.bodies[1].m
    cc = amd.critical_amd_collision(al, ga)
    e_eq = bisect(lambda e: amd.relative_amd(e, e, al, ga) - cc, 0, 0.9)
    assert e_eq == pytest.approx(0.1478, abs=5e-4)


def test_seeds_give_reproducible_reports() -> None:
    s = load_system_file(EXAMPLES / "two_planet.yaml")
    a = check_system(s, CheckSettings(orbits=2000, draws=5, seed=11))
    b = check_system(s, CheckSettings(orbits=2000, draws=5, seed=11))
    assert [r.megno for r in a.runs] == [r.megno for r in b.runs]
    assert [r.label for r in realizations(s, 5, 11)] == [r.label for r in a.realizations]
