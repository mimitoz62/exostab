"""Print the numbers quoted in docs/validation.md (run: PYTHONPATH=. python scripts/validation_summary.py).

Uses the same settings as tests/validation/test_validation.py and the bundled offline snapshot, so the
output is reproducible on any machine up to floating-point differences in chaotic runs. The Hill-limit
fractions of section 2 are printed by scripts/validation_figures.py, which computes that figure.
"""

from __future__ import annotations

import math
import os
from pathlib import Path

os.environ.setdefault("EXOSTAB_OFFLINE", "1")

from exostab._numerics import bisect
from exostab.analysis import CheckSettings, check_system
from exostab.data import load_system, load_system_file
from exostab.indicators import amd, hill
from exostab.indicators.hill import gladman_critical_separation
from exostab.indicators.megno import classify_run
from exostab.integrate import RunConfig, run
from exostab.report import software_record

ROOT = Path(__file__).resolve().parents[1]


def summary(name: str, res) -> None:  # type: ignore[no-untyped-def]
    rep = res.report
    counts = rep.indicators["nbody"].details["classification_counts"]
    print(f"\n## {name}")
    print(f"overall: {rep.overall.verdict.value}")
    for k, ind in rep.indicators.items():
        print(f"  {k}: {ind.verdict.value} (nominal {ind.nominal_verdict.value})")
    n = res.runs[0]
    print(
        f"  nominal run: {n.status}, <Y> = {n.megno:.4f}, energy error {n.energy_error:.2e}, "
        f"{n.n_orbits_innermost:.0f} inner orbits = {n.t_end:.1f} yr, wall {n.walltime:.1f} s"
    )
    if res.ias15 is not None:
        print(
            f"  IAS15 check: {res.ias15.status}, <Y> = {res.ias15.megno:.4f}, energy error {res.ias15.energy_error:.2e}"
        )
    print(f"  draws: {counts}")
    pairs = rep.indicators["hill"].details["pairs"]
    failing = [p["pair"] for p in pairs if p["orbits_cross"] or p["gladman_margin"] <= 0]
    if failing:
        print(f"  nominal pairs inside the Gladman limit: {', '.join(failing)}")
    limits = [f"{f.planet} ({f.rule})" for f in rep.system.flags if f.rule.endswith("upper_limit")]
    if limits:
        print(f"  upper limits used as nominal values: {', '.join(limits)}")
    print(f"  total runtime {rep.runtime_s:.1f} s")


def hd127195_note(res) -> None:  # type: ignore[no-untyped-def]
    """The Research Note's geometry and AMD numbers, computed as the validation tests compute them, and the
    same quantities in exostab's own AMD convention (twice the coplanar AMD, Petit et al. 2017 domain)."""
    nom = res.realizations[0]
    a = nom.semi_major_axes()
    b, c = nom.bodies
    print("\n## HD 127195: geometry and AMD (Research Note inputs)")
    print(f"  a_b = {a[0]:.5f} AU, a_c = {a[1]:.5f} AU, period ratio {c.P / b.P:.5f}")
    print(f"  separation {hill.pair_table(nom)[0]['separation_hill']:.4f} mutual Hill radii")
    # The Note's convention (as in the tests): alpha from the period ratio, coplanar AMD, collision criterion.
    al, ga = _alpha_gamma(nom)
    cc = amd.critical_amd_collision(al, ga)
    e_note = bisect(lambda e: amd.relative_amd(e, e, al, ga) - cc, 0.0, 0.9)
    passing = sum(
        amd.relative_amd(r.bodies[0].e, r.bodies[1].e, *_alpha_gamma(r))
        < amd.critical_amd_collision(*_alpha_gamma(r))
        for r in res.realizations
    )
    print(
        f"  Note's convention: equal-eccentricity AMD limit {e_note:.4f}; collision test passed by {passing} of "
        f"{len(res.realizations)} realizations (nominal + draws)"
    )
    # exostab's AMD indicator: Jacobi semi-major axes, twice the coplanar AMD, critical AMD within its domain.
    info = amd.analyse(nom)["pairs"][0]
    eps = info["epsilon"]
    print(
        f"  exostab: alpha = {info['alpha']:.4f}, alpha_R = {amd.alpha_resonance_switch(eps):.4f}, "
        f"epsilon = {eps:.2e} (eps_lim {amd.EPS_LIM:.2e}), critical AMD branch {info['critical_branch']}"
    )
    e_ind = bisect(
        lambda e: (
            amd.EQUIPARTITION * amd.relative_amd(e, e, info["alpha"], info["gamma"]) - info["critical_amd"]
        ),
        0.0,
        0.9,
    )
    strong_p = sum(
        all(p["beta_coplanar"] < 1 for p in x["pairs"]) and x["beta_star_coplanar"] < 1
        for x in (amd.analyse(r) for r in res.realizations[1:])
    )
    print(
        f"  exostab: equal-eccentricity limit for beta = 1: {e_ind:.4f}; AMD indicator draws "
        f"{res.report.indicators['amd'].draws}; draws strongly AMD-stable with the coplanar AMD alone: {strong_p}"
    )
    bad = [r for r in res.runs[1:] if classify_run(r) == "inconclusive"]
    if bad:
        print(
            f"  inconclusive draws: {len(bad)}, statuses {sorted({r.status for r in bad})}, energy error "
            f"{min(r.energy_error for r in bad):.2e} to {max(r.energy_error for r in bad):.2e}, <Y> "
            f"{min(r.megno or math.nan for r in bad):.0f} to {max(r.megno or math.nan for r in bad):.0f}"
        )
    print(
        f"  WHFast step of the nominal run {res.runs[0].dt * 365.25:.2f} d; P_b / 30 = {b.P * 365.25 / 30:.2f} d"
    )


def _alpha_gamma(r) -> tuple[float, float]:  # type: ignore[no-untyped-def]
    """alpha from the period ratio and the mass ratio gamma, as in tests/validation/test_validation.py."""
    return (r.bodies[0].P / r.bodies[1].P) ** (2 / 3), r.bodies[0].m / r.bodies[1].m


def main() -> None:
    print("software:", software_record().model_dump())
    from tests.validation.test_validation import inner_solar_system  # type: ignore[import-not-found]

    r = inner_solar_system()
    wh = run(r, RunConfig(n_orbits=1e4 / r.bodies[0].P, n_samples=300))
    ias = run(r, RunConfig(n_orbits=1e4 / r.bodies[0].P, integrator="ias15", n_samples=300))
    print(
        f"\n## inner Solar System, 1e4 yr\n  WHFast: energy error {wh.energy_error:.2e}, <Y> {wh.megno:.4f}, "
        f"dt {wh.dt * 365.25:.3f} d\n  IAS15: energy error {ias.energy_error:.2e}, <Y> {ias.megno:.4f}"
    )
    print(
        f"\n## Gladman limit for two 1e-5 Msun planets: {gladman_critical_separation(1e-5, 1e-5, 1.0):.4f} "
        f"mutual Hill radii (2 sqrt 3 = {2 * math.sqrt(3):.4f})"
    )
    summary("TRAPPIST-1 (snapshot)", check_system(load_system("TRAPPIST-1"), CheckSettings(draws=20, seed=0)))
    print("\n## TRAPPIST-1 (snapshot), nominal <Y> with seeds 0 to 7 (WHFast)")
    for seed in range(8):
        nominal = check_system(
            load_system("TRAPPIST-1"), CheckSettings(draws=0, seed=seed, ias15_check=False)
        ).runs[0]
        print(f"  seed {seed}: <Y> = {nominal.megno:.3f}, {classify_run(nominal)}")
    summary(
        "TRAPPIST-1 (Agol et al. 2021, Table 2)",
        check_system(
            load_system_file(ROOT / "examples/trappist1_agol2021.yaml"), CheckSettings(draws=20, seed=0)
        ),
    )
    summary(
        "GJ 876 (Rivera et al. 2010)",
        check_system(
            load_system_file(ROOT / "tests/validation/systems/gj876_rivera2010.yaml"),
            CheckSettings(draws=20, seed=0),
        ),
    )
    summary(
        "GJ 876 (snapshot, archive phases)",
        check_system(load_system("GJ 876"), CheckSettings(draws=20, seed=0)),
    )
    summary("Kepler-11 (snapshot)", check_system(load_system("Kepler-11"), CheckSettings(draws=20, seed=0)))
    note = check_system(
        load_system_file(ROOT / "examples/hd127195_note.yaml"),
        CheckSettings(orbits=2e4, draws=200, seed=42),
    )
    summary("HD 127195 (Research Note inputs, 200 draws, 2e4 orbits)", note)
    hd127195_note(note)


if __name__ == "__main__":
    main()
