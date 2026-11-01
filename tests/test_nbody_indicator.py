"""The N-body/MEGNO indicator, the verdict combination rules and the overall verdict."""

import math
from dataclasses import replace

import pytest

from conftest import V, two_planet_system
from exostab.analysis import CheckSettings, check_system, overall_verdict, upper_limit_inputs
from exostab.data import archive, system_from_rows
from exostab.data.store import TableInfo
from exostab.indicators import AGREEMENT, DrawStats, IndicatorResult, Verdict, combine
from exostab.indicators import megno as nb
from exostab.integrate import RunResult
from exostab.models import Provenance
from exostab.sampling import realizations

S, M, U, INC = Verdict.STABLE, Verdict.MARGINAL, Verdict.UNSTABLE, Verdict.INCONCLUSIVE


def result(**kw: object) -> RunResult:
    base: dict[str, object] = {
        "label": "nominal",
        "integrator": "whfast",
        "dt": 0.001,
        "t_target": 100.0,
        "t_end": 100.0,
        "status": "completed",
        "megno": 2.0,
        "lyapunov": 0.0,
        "energy_error": 1e-9,
        "walltime": 0.1,
        "encounter_distance": 0.01,
        "n_orbits_innermost": 1e4,
        "n_orbits_outermost": 1e3,
    }
    base.update(kw)
    return RunResult(**base)  # type: ignore[arg-type]


# ------------------------------------------------------------------------------------------ combination rules


def test_combine_rules() -> None:
    assert combine(S, []) is S
    assert combine(S, [S] * 20) is S
    assert combine(S, [S] * 19 + [M]) is S  # 95% agreement
    assert combine(S, [S] * 18 + [M, M]) is M
    assert combine(U, [U] * 20) is U
    assert combine(INC, [S] * 20) is INC
    assert combine(S, [S] * 15 + [INC] * 5) is INC  # more than 20% inconclusive
    assert AGREEMENT == 0.95


def test_draw_stats() -> None:
    d = DrawStats.from_verdicts([S, S, M, U, INC])
    assert (d.n, d.stable, d.marginal, d.unstable, d.inconclusive) == (5, 2, 1, 1, 1)
    assert d.count(M) == 1


@pytest.mark.parametrize(
    ("kw", "expected"),
    [
        ({}, "regular"),
        ({"megno": 3.0}, "chaotic"),
        ({"megno": nb.MEGNO_CHAOTIC}, "chaotic"),
        ({"status": "encounter"}, "unstable"),
        ({"status": "escape", "energy_error": 1.0}, "unstable"),
        ({"status": "star_approach", "star_approach": "b"}, "inconclusive"),
        ({"energy_error": 1e-3}, "inconclusive"),
        ({"status": "error"}, "inconclusive"),
        ({"megno": math.nan}, "inconclusive"),
        ({"megno": None}, "inconclusive"),
    ],
)
def test_classify_run(kw: dict[str, object], expected: str) -> None:
    assert nb.classify_run(result(**kw)) == expected


def test_evaluate_counts_and_notes() -> None:
    runs = [result()] + [result(label=f"draw {k}") for k in range(19)] + [result(label="draw 20", megno=4.0)]
    ind = nb.evaluate(runs, result(integrator="ias15"))
    assert ind.verdict is S and ind.draws is not None and ind.draws.marginal == 1
    assert ind.details["classification_counts"] == {
        "regular": 19,
        "chaotic": 1,
        "unstable": 0,
        "inconclusive": 0,
    }
    assert "19 regular, 1 chaotic" in ind.summary
    ind = nb.evaluate(runs, result(integrator="ias15", status="encounter"))
    assert ind.verdict is M and any("disagree" in n for n in ind.notes)
    ind = nb.evaluate([result(n_orbits_outermost=20)], None)
    assert ind.verdict is M and any("fewer than" in n for n in ind.notes)
    ind = nb.evaluate([result(energy_error=1e-3)], None)
    assert ind.verdict is INC and any("energy error" in n for n in ind.notes)
    star = result(label="draw 3", status="star_approach", star_approach="X b")
    ind = nb.evaluate([result(), *[result(label=f"draw {k}") for k in range(19)], star], None)
    assert ind.verdict is S and ind.details["classification_counts"]["inconclusive"] == 1  # 1 of 20 draws
    assert "0 close encounter/escape, 1 inconclusive of 20" in ind.summary
    assert any("draw 3: X b came closer to the star" in n and "1 of 21 runs" in n for n in ind.notes)
    assert not any("energy error" in n for n in ind.notes)
    assert ind.details["draws"][-1]["star_approach"] == "X b"
    ind = nb.evaluate([result(status="encounter", t_end=5.0)], None, random_phases=["X b"])
    assert ind.verdict is U and "close encounter after 5 yr" in ind.summary
    assert any("X b" in n and "random" in n for n in ind.notes)
    ind = nb.evaluate([result()] + [result(megno=5.0)] * 5, None)
    assert ind.verdict is M and any("draws disagree" in n for n in ind.notes)


def test_megno_seed_is_deterministic_and_distinct() -> None:
    assert nb.megno_seed(3, 1) == nb.megno_seed(3, 1)
    assert len({nb.megno_seed(3, k) for k in range(50)}) == 50


def test_integrate_all_serial_and_parallel_agree() -> None:
    reals = realizations(two_planet_system(err=True), 3, seed=2)
    settings = nb.NBodySettings(orbits=200, n_samples=5, jobs=1)
    serial, ias = nb.integrate_all(reals, settings, seed=2)
    parallel, ias2 = nb.integrate_all(reals, replace(settings, jobs=2), seed=2)
    assert [r.megno for r in serial] == [r.megno for r in parallel]
    assert ias is not None and ias2 is not None and ias.integrator == "ias15"
    assert serial[0].series["t"] and not serial[1].series
    none, no_ias = nb.integrate_all(reals[:1], replace(settings, ias15_check=False), seed=2)
    assert no_ias is None and len(none) == 1


# ------------------------------------------------------------------------------------------ overall verdict


def ind(name: str, v: Verdict, draws: list[Verdict] | None = None) -> IndicatorResult:
    """An indicator result whose draws (20 sharing its verdict by default; [] for none) are as given."""
    d = [v] * 20 if draws is None else draws
    stats = DrawStats.from_verdicts(d) if d else None
    return IndicatorResult(name=name, title=name, verdict=v, nominal_verdict=v, summary="", draws=stats)


def nbody_ind(regular: int, encounters: int = 0, chaotic: int = 0, **nominal: object) -> IndicatorResult:
    """N-body result from a nominal run (``nominal`` overrides), the given draws and an agreeing IAS15 run."""
    runs = [result(**nominal)]
    runs += [result(label="draw")] * regular + [result(label="draw", megno=5.0)] * chaotic
    runs += [result(label="draw", status="encounter", t_end=5.0)] * encounters
    return nb.evaluate(runs, result(**{**nominal, "integrator": "ias15"}))


@pytest.mark.parametrize(
    ("hill", "amd", "nbody", "expected"),
    [
        (S, S, S, S),
        (U, M, S, M),  # resonance-protected, like GJ 876
        (S, S, M, M),
        (S, S, U, U),
        (U, U, U, U),
        (S, S, INC, INC),
        (U, S, INC, INC),
        (M, S, S, M),
    ],
)
def test_overall_verdict_is_conservative(
    hill: Verdict, amd: Verdict, nbody: Verdict, expected: Verdict
) -> None:
    o = overall_verdict({"hill": ind("hill", hill), "amd": ind("amd", amd), "nbody": ind("nbody", nbody)})
    assert o.verdict is expected
    if expected is not S:
        assert o.reasons


def test_plot_samples_never_change_the_result() -> None:
    """The catalog keeps no time series (n_samples=0), the web app 300 and the CLI 400: same numbers, same verdicts."""
    s = two_planet_system(err=True, e=(0.3, 0.2), period_ratio=2.0)
    results = [
        check_system(s, CheckSettings(orbits=600, draws=2, seed=4, jobs=1, n_samples=n))
        for n in (0, 300, 400)
    ]
    for res in results:
        assert [r.energy_error for r in res.runs] == [r.energy_error for r in results[-1].runs]
        assert res.ias15 is not None and res.ias15.energy_error == results[-1].ias15.energy_error  # type: ignore[union-attr]
        assert {k: v.verdict for k, v in res.report.indicators.items()} == {
            k: v.verdict for k, v in results[-1].report.indicators.items()
        }
        assert res.report.overall.verdict is results[-1].report.overall.verdict


def test_overall_unstable_states_the_draw_counts() -> None:
    o = overall_verdict(
        {"hill": ind("hill", U), "amd": ind("amd", U), "nbody": nbody_ind(1, 19, status="encounter")}
    )
    assert o.verdict is U
    assert "for the nominal parameters and for 19 of 20 draws within the published uncertainties" in o.summary


def test_unstable_nbody_resting_on_upper_limits_is_not_overall_unstable() -> None:
    """HD 215152 was "unstable" with its masses set to astrometric upper limits about 300 x m sin i."""
    inds = {"hill": ind("hill", U), "amd": ind("amd", M), "nbody": nbody_ind(0, 20, status="encounter")}
    o = overall_verdict(inds, upper_limits=["masses of X b and X c"])
    assert o.verdict is M
    assert "(masses of X b and X c)" in o.summary and "does not show that the system is unstable" in o.summary
    assert "within the published uncertainties" not in o.summary
    assert "Only upper limits are published for: masses of X b and X c." in o.reasons
    # A limit is the worst case for stability, so a stable result at the limits stands.
    stable = {"hill": ind("hill", S), "amd": ind("amd", S), "nbody": nbody_ind(20)}
    assert overall_verdict(stable, upper_limits=["mass of X b"]).verdict is S


def test_upper_limit_inputs() -> None:
    s = two_planet_system()
    assert upper_limit_inputs(s) == []
    ul = Provenance.UPPER_LIMIT
    b, c = s.planets
    s = s.model_copy(
        update={
            "star": s.star.model_copy(update={"mass_msun": V(1.0, provenance=ul)}),
            "planets": (
                b.model_copy(
                    update={"mass_earth": V(10.0, provenance=ul), "eccentricity": V(0.1, provenance=ul)}
                ),
                c.model_copy(update={"mass_earth": V(10.0, provenance=ul)}),
            ),
        }
    )
    assert upper_limit_inputs(s) == ["stellar mass", "masses of Test b and Test c", "eccentricity of Test b"]


def test_check_system_with_upper_limit_masses_is_never_unstable() -> None:
    """Two planets 5% apart in period with masses below 1000 Earth masses: every run has a close encounter."""
    s = two_planet_system(period_ratio=1.05, m_earth=(1000.0, 1000.0))
    planets = tuple(
        p.model_copy(update={"mass_earth": V(1000.0, provenance=Provenance.UPPER_LIMIT)}) for p in s.planets
    )
    s = s.model_copy(update={"planets": planets})
    res = check_system(s, CheckSettings(orbits=300, draws=3, seed=0, jobs=1, n_samples=5, ias15_check=False))
    assert res.report.indicators["nbody"].verdict is U
    assert res.report.overall.verdict is M
    assert "masses of Test b and Test c" in res.report.overall.summary


def test_unstable_nbody_of_a_multiple_star_system_is_not_overall_unstable() -> None:
    """Kepler-132 (two stars): b and c, 4% apart in period, cannot orbit one star, yet exostab integrated both
    around the host and called the system "unstable ... within the published uncertainties"."""
    inds = {"hill": ind("hill", U), "amd": ind("amd", M), "nbody": nbody_ind(0, 20, status="encounter")}
    assert overall_verdict(inds).verdict is U
    o = overall_verdict(inds, n_stars=2)
    assert o.verdict is M and "within the published uncertainties" not in o.summary
    assert (
        "may orbit different stars" in o.summary and "does not show that the system is unstable" in o.summary
    )
    assert "The system has 2 stars; only the host star is modelled." in o.reasons
    # with upper limits as well, both reasons are given
    o = overall_verdict(inds, upper_limits=["mass of X b"], n_stars=3)
    assert o.verdict is M and "(mass of X b)" in o.summary and "The system has 3 stars" in o.summary
    # a stable result is not changed by the number of stars
    stable = {"hill": ind("hill", S), "amd": ind("amd", S), "nbody": nbody_ind(20)}
    assert overall_verdict(stable, n_stars=2).verdict is S


def test_check_system_passes_the_number_of_stars() -> None:
    # Kepler-132 b and c: about 2 Earth masses, period ratio 1.038, 1.5 mutual Hill radii apart
    s = two_planet_system(period_ratio=1.0383, m_earth=(1.92, 2.18))
    settings = CheckSettings(orbits=300, draws=3, seed=0, jobs=1, n_samples=5, ias15_check=False)
    res = check_system(s, settings)
    assert res.report.indicators["nbody"].verdict is U and res.report.overall.verdict is U
    binary = s.model_copy(update={"star": s.star.model_copy(update={"n_stars": 2})})
    res = check_system(binary, settings)
    assert res.report.indicators["nbody"].verdict is U and res.report.overall.verdict is M
    assert "may orbit different stars" in res.report.overall.summary


def hd215152_rows(mass_limit: int) -> list[dict[str, object]]:
    """HD 215152 b-e as in the archive cache of 2026-09-28: Delisle et al. (2018) orbits, Kiefer et al. (2021)
    astrometric mass upper limits (Earth masses, ``pl_bmasselim = 1``) about 300 times the m sin i."""
    rows: list[dict[str, object]] = []
    for letter, period_days, err_plus, err_minus, mass_earth in (
        ("b", 5.75999, 0.00157, -0.00175, 565.42),
        ("c", 7.28243, 0.00451, -0.00827, 468.80),
        ("d", 10.86499, 0.00564, -0.00613, 770.42),
        ("e", 25.1967, 0.0476, -0.0505, 975.42),
    ):
        r: dict[str, object] = dict.fromkeys(archive.COLUMN_NAMES)
        r.update(
            pl_name=f"HD 215152 {letter}",
            hostname="HD 215152",
            pl_letter=letter,
            sy_pnum=4,
            sy_snum=1,
            cb_flag=0,
            tran_flag=0,
            pl_orbper=period_days,
            pl_orbpererr1=err_plus,
            pl_orbpererr2=err_minus,
            pl_orbperlim=0,
            pl_orbeccen=0.0,
            pl_orbeccenlim=0,
            pl_bmasse=mass_earth,
            pl_bmasselim=mass_limit,
            pl_bmassprov="Mass",
            st_mass=0.77,
            st_masserr1=0.015,
            st_masserr2=-0.015,
            st_masslim=0,
        )
        rows.append(r)
    return rows


def test_hd215152_with_upper_limit_masses_is_not_overall_unstable() -> None:
    """The reported case: exostab called HD 215152 "unstable" with its masses set to the upper limits."""
    info = TableInfo(kind="archive-cache", retrieved_utc="2026-09-28T14:30:00+00:00", path=None)
    settings = CheckSettings(orbits=300, draws=3, seed=0, jobs=1, n_samples=5, ias15_check=False)
    res = check_system(system_from_rows(hd215152_rows(mass_limit=1), info), settings)
    assert res.report.indicators["nbody"].verdict is U  # every run with masses at or below the limits
    assert res.report.overall.verdict is M
    assert "masses of HD 215152 b, HD 215152 c, HD 215152 d and HD 215152 e" in res.report.overall.summary
    # The same masses published as measurements would be direct evidence of instability.
    res = check_system(system_from_rows(hd215152_rows(mass_limit=0), info), settings)
    assert res.report.overall.verdict is U


def test_no_draws_never_give_a_confident_overall_verdict() -> None:
    """With --draws 0 nothing was tested against the uncertainties."""
    o = overall_verdict({"hill": ind("hill", S, []), "amd": ind("amd", S, []), "nbody": nbody_ind(0)})
    assert o.verdict is M and "--draws 0" in o.summary and o.reasons
    o = overall_verdict(
        {"hill": ind("hill", U, []), "amd": ind("amd", U, []), "nbody": nbody_ind(0, status="encounter")}
    )
    assert o.verdict is M and "--draws 0" in o.summary
    assert "draws within" not in o.summary and "almost all draws" not in o.summary
    o = overall_verdict(
        {"hill": ind("hill", S, []), "amd": ind("amd", S, []), "nbody": nbody_ind(0, energy_error=1e-3)}
    )
    assert o.verdict is INC  # an untrustworthy integration stays inconclusive
    res = check_system(two_planet_system(err=True), CheckSettings(orbits=300, draws=0, jobs=1, n_samples=5))
    assert res.report.indicators["nbody"].verdict is S and res.report.overall.verdict is M


def test_stable_summary_never_hides_failing_draws() -> None:
    every = overall_verdict({"hill": ind("hill", S), "amd": ind("amd", S), "nbody": nbody_ind(20)})
    assert every.verdict is S and every.reasons == []
    assert "no sign of instability for the nominal parameters or any of the 20 draws" in every.summary
    # One draw fails the Hill criterion (a sufficient condition): still stable, but said so.
    o = overall_verdict(
        {"hill": ind("hill", S, [S] * 19 + [U]), "amd": ind("amd", S), "nbody": nbody_ind(20)}
    )
    assert o.verdict is S and "no sign of instability" not in o.summary
    assert o.reasons == ["hill: of 20 draws, 1 unstable"] and "hill: of 20 draws, 1 unstable" in o.summary
    o = overall_verdict({"hill": ind("hill", S), "amd": ind("amd", S), "nbody": nbody_ind(19, chaotic=1)})
    assert o.verdict is S and o.reasons == ["N-body + MEGNO: of 20 draws, 1 chaotic"]


def test_a_close_encounter_in_any_draw_blocks_overall_stable() -> None:
    """19 regular draws and 1 close encounter keep the N-body verdict 'stable' (95% rule), not the overall one."""
    nbi = nbody_ind(19, 1)
    assert nbi.verdict is S
    o = overall_verdict({"hill": ind("hill", S), "amd": ind("amd", S), "nbody": nbi})
    assert o.verdict is M and "no sign of instability" not in o.summary
    assert "1 of 20 N-body draws had a close encounter or escape" in o.summary
    assert o.reasons == ["N-body + MEGNO: of 20 draws, 1 with a close encounter or escape"]
    # Kepler-19: the same N-body runs with marginal analytic criteria.
    o = overall_verdict({"hill": ind("hill", M), "amd": ind("amd", M), "nbody": nbi})
    assert o.verdict is M and "shows regular motion" not in o.summary
    assert "19 are regular, 0 chaotic and 1 had close encounters or escapes" in o.summary


def test_marginal_summary_names_the_actual_reason() -> None:
    # ups And: every run is regular, but the outermost planet completes only 36 orbits.
    nbi = nbody_ind(20, n_orbits_outermost=36)
    assert nbi.verdict is M
    o = overall_verdict({"hill": ind("hill", M), "amd": ind("amd", M), "nbody": nbi})
    assert o.verdict is M and "chaotic or unstable" not in o.summary and "disagree" not in o.summary
    assert "Every WHFast run is regular (the nominal parameters and all 20 draws)" in o.summary
    assert "only 36 orbits" in o.summary and "(hill: marginal, amd: marginal)" in o.summary
    # WHFast and IAS15 disagree on a nominal run that is otherwise regular.
    nbi = nb.evaluate([result()] + [result(label="draw")] * 20, result(integrator="ias15", megno=4.0))
    o = overall_verdict({"hill": ind("hill", S), "amd": ind("amd", S), "nbody": nbi})
    assert o.verdict is M and "chaotic or unstable" not in o.summary
    assert "WHFast and IAS15 disagree on the nominal run (regular vs chaotic)" in o.summary
    # Draws that really are chaotic or unstable (HD 127195 with random phases).
    o = overall_verdict(
        {"hill": ind("hill", M), "amd": ind("amd", S), "nbody": nbody_ind(13, 1, 6, megno=9.8)}
    )
    assert "the nominal run is chaotic; of 20 draws, 13 are regular, 6 chaotic and 1 had" in o.summary
    assert (
        "Part of the parameter range allowed by the published uncertainties is chaotic or unstable"
        in o.summary
    )
    # No regular draw: not "part of" the range. The words change, the verdict does not.
    o = overall_verdict(
        {"hill": ind("hill", M), "amd": ind("amd", S), "nbody": nbody_ind(0, 0, 20, megno=9.8)}
    )
    assert o.verdict is M and "of 20 draws, 0 are regular, 20 chaotic" in o.summary
    assert "No draw within the published uncertainties is regular." in o.summary
    assert "Part of the parameter range" not in o.summary
    # Draws below an upper limit are not "within the uncertainties".
    o = overall_verdict(
        {"hill": ind("hill", M), "amd": ind("amd", S), "nbody": nbody_ind(10, 5, 5)},
        upper_limits=["mass of X b"],
    )
    assert "allowed by the published uncertainties and upper limits is chaotic or unstable" in o.summary
    assert "upper limits (mass of X b)" in o.summary
    # GJ 876: regular N-body motion in every run, analytic criteria failing.
    o = overall_verdict({"hill": ind("hill", U), "amd": ind("amd", M), "nbody": nbody_ind(20)})
    assert o.verdict is M and "regular motion for the nominal parameters and all 20 draws" in o.summary
    assert "typical of" not in o.summary
    # Each failing indicator speaks for itself; an indicator whose nominal verdict is stable must not read as a pass.
    hill = ind("hill", U).model_copy(update={"summary": "Mars / Jupiter is too close."})
    amd = ind("amd", M).model_copy(update={"nominal_verdict": S, "summary": "AMD-stable."})
    o = overall_verdict({"hill": hill, "amd": amd, "nbody": nbody_ind(20)})
    assert o.verdict is M and "Mars / Jupiter is too close." in o.summary
    assert "amd is stable for the nominal parameters, but the draws disagree." in o.summary
    assert "AMD-stable." not in o.summary


def test_check_system_end_to_end_small() -> None:
    s = two_planet_system(err=True)
    res = check_system(s, CheckSettings(orbits=300, draws=3, seed=1, jobs=1, n_samples=10), command="test")
    rep = res.report
    assert set(rep.indicators) == {"hill", "amd", "nbody"}
    assert rep.overall.verdict is S
    assert rep.settings.seed == 1 and rep.settings.draws == 3 and rep.command == "test"
    assert rep.nominal.bodies[0].period_days == pytest.approx(100.0)
    assert len(res.runs) == 4 and res.ias15 is not None
