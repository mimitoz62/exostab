import math
from dataclasses import replace

import pytest

from exostab.integrate import (
    ENERGY_CHECKS,
    RunConfig,
    build_simulation,
    hill_radii,
    pericentre_timescale,
    run,
    timestep,
)
from exostab.sampling import Body, Realization


def pair(ratio: float = 2.5, m: float = 3e-5, e: tuple[float, float] = (0.0, 0.0)) -> Realization:
    return Realization(
        label="nominal",
        m_star=1.0,
        bodies=(Body("b", m, 0.1, e[0], 0.0, 0.0), Body("c", m, 0.1 * ratio, e[1], 1.0, math.pi)),
    )


def test_pericentre_timescale_and_timestep() -> None:
    assert pericentre_timescale(1.0, 0.0) == 1.0
    # 2 pi / (true-anomaly rate at pericentre)
    e = 0.3
    assert pericentre_timescale(2.0, e) == pytest.approx(2.0 * (1 - e) ** 1.5 / math.sqrt(1 + e))
    r = pair(e=(0.0, 0.6))
    # the eccentric outer planet sets the step, and the step never exceeds P_min / 20
    assert timestep(r, 1 / 30) == pytest.approx(pericentre_timescale(0.25, 0.6) / 30)
    assert timestep(pair(), 1 / 30) <= 0.1 / 20


def test_build_simulation_units_and_exit_conditions() -> None:
    r = pair()
    sim = build_simulation(r, RunConfig())
    assert sim.G == pytest.approx(4 * math.pi**2, rel=1e-4)  # yr, AU, Msun
    assert sim.integrator.name in (b"whfast", "whfast")  # REBOUND 5 returns bytes
    assert sim.dt == pytest.approx(0.1 / 30)
    assert sim.collision == "line"
    assert [p.r for p in sim.particles[1:]] == pytest.approx([0.5 * h for h in hill_radii(r)])
    assert sim.particles[0].r == 0
    assert sim.exit_max_distance == pytest.approx(100 * sim.particles[2].a)
    assert sim.particles[1].P == pytest.approx(0.1)
    # mean longitude = pomega + M (Omega = 0 in the coplanar frame)
    assert math.remainder(sim.particles[2].l - (math.pi + 1.0), 2 * math.pi) == pytest.approx(0.0, abs=1e-6)


def test_regular_run_conserves_energy_and_megno_near_two() -> None:
    res = run(pair(), RunConfig(n_orbits=3000, n_samples=20, megno_seed=1))
    assert res.status == "completed"
    assert res.energy_error < 1e-6
    assert res.megno == pytest.approx(2.0, abs=0.1)
    assert res.n_orbits_innermost == pytest.approx(3000, rel=1e-3)
    assert res.n_orbits_outermost == pytest.approx(1200, rel=1e-3)
    assert len(res.series["t"]) == 21 and len(res.series["x0"]) == 21
    assert res.dt == pytest.approx(0.1 / 30)


def test_runs_are_deterministic() -> None:
    a = run(pair(ratio=1.3), RunConfig(n_orbits=2000, megno_seed=5))
    b = run(pair(ratio=1.3), RunConfig(n_orbits=2000, megno_seed=5))
    assert a.megno == b.megno and a.energy_error == b.energy_error


@pytest.mark.parametrize("integrator", ["whfast", "ias15"])
def test_sampling_never_integrates_backwards(integrator: str) -> None:
    # 10 orbits with 400 samples: the samples are 0.025 orbits apart, closer than one step (1/30 orbit).
    # Checkpoints a step has already passed are skipped instead of integrated to backwards.
    config = RunConfig(n_orbits=10, integrator=integrator, n_samples=400)  # type: ignore[arg-type]
    sampled, plain = run(pair(), config), run(pair(), replace(config, n_samples=0))
    t = sampled.series["t"]
    assert t == sorted(set(t))  # strictly increasing
    assert sampled.t_end >= sampled.t_target and sampled.status == "completed"
    # sampling leaves the trajectory alone
    assert (sampled.t_end, sampled.megno) == (plain.t_end, plain.megno)
    if integrator == "whfast":
        assert sampled.dt == pytest.approx(0.1 / 30)


def test_energy_error_is_checked_over_the_whole_run_whatever_is_kept_for_plots() -> None:
    # Eccentric orbits: WHFast's energy error peaks at pericentre, so the value at the end is not the maximum.
    r = pair(ratio=2.0, e=(0.3, 0.2))
    runs = {n: run(r, RunConfig(n_orbits=2000, n_samples=n)) for n in (0, 7, 300, ENERGY_CHECKS)}
    full = runs[ENERGY_CHECKS]
    assert full.energy_error == max(full.series["energy_error"]) > 3 * full.series["energy_error"][-1]
    for n, res in runs.items():
        # the same checks in every run (draws and catalog runs keep no time series), so the same verdict
        assert res.energy_error == full.energy_error and res.megno == full.megno
        if n:
            assert len(res.series["t"]) == n + 1 and max(res.series["energy_error"]) <= res.energy_error
    assert runs[300].series["t"][-1] == full.series["t"][-1]
    capped = run(r, RunConfig(n_orbits=2000, n_samples=ENERGY_CHECKS + 500))
    assert capped.series["t"] == full.series["t"]  # never more samples than energy checks


def test_close_encounter_is_detected() -> None:
    res = run(pair(ratio=1.1, m=1e-4), RunConfig(n_orbits=5000))
    assert res.status == "encounter" and res.star_approach is None
    assert res.t_end < res.t_target


@pytest.mark.parametrize("integrator", ["whfast", "ias15"])
def test_star_approach_is_not_a_close_encounter(integrator: str) -> None:
    # b: 0.01 Msun at P = 1 yr, e = 0.94: pericentre 0.060 AU, inside half its Hill radius (0.075 AU), so
    # REBOUND's collision search pairs it with the star at every pericentre. c is 9.7 AU away. No two planets
    # meet, so the run goes to the end, labelled as a star approach rather than as a close encounter.
    real = Realization(
        "grazer", 1.0, (Body("b", 0.01, 1.0, 0.94, 0.0, math.pi), Body("c", 1e-3, 30.0, 0.0, 0.0, 0.0))
    )
    assert real.semi_major_axes()[0] * 0.06 < 0.5 * hill_radii(real)[0]
    res = run(real, RunConfig(n_orbits=30, integrator=integrator))  # type: ignore[arg-type]
    assert res.status == "star_approach" and res.star_approach == "b"
    assert res.t_end >= res.t_target and res.megno is not None


@pytest.mark.parametrize("integrator", ["whfast", "ias15"])
def test_escape_is_detected(integrator: str) -> None:
    # Not an ejection: c (P = 1 yr, e = 0.5) stays bound, but the escape distance is lowered to 1.2 times its
    # semi-major axis, which c passes at about 0.24 yr on its way from pericentre to apocentre (1.5 AU). b and c
    # stay more than 0.28 AU apart, so nothing else can stop the run.
    real = Realization(
        "nominal", 1.0, (Body("b", 3e-5, 0.1, 0.0, 0.0, 0.0), Body("c", 3e-5, 1.0, 0.5, 0.0, 0.0))
    )
    res = run(real, RunConfig(n_orbits=100, integrator=integrator, escape_factor=1.2))  # type: ignore[arg-type]
    assert res.status == "escape" and res.star_approach is None
    assert 0 < res.t_end < 0.5 < res.t_target  # stopped on c's way out, in a run planned for 10 yr


def test_ias15_run() -> None:
    res = run(pair(), RunConfig(n_orbits=300, integrator="ias15"))
    assert res.status == "completed" and res.dt is None
    assert res.energy_error < 1e-12


def test_no_megno_mode() -> None:
    res = run(pair(), RunConfig(n_orbits=100, megno=False, n_samples=3))
    assert res.megno is None and res.lyapunov is None
    assert all(math.isnan(y) for y in res.series["megno"])
