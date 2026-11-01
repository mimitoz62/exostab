"""Run every indicator on one system and combine the verdicts."""

from __future__ import annotations

import time
from collections.abc import Sequence
from dataclasses import dataclass, field, replace

from .budget import Plan, plan
from .indicators import AGREEMENT, IndicatorResult, Verdict
from .indicators import amd as amd_indicator
from .indicators import hill as hill_indicator
from .indicators import megno as nbody_indicator
from .indicators import spock as spock_indicator
from .integrate import RunResult
from .models import PhaseKind, Provenance, System
from .report import Overall, Report, build_report
from .sampling import InclinationPrior, Realization, choose_epoch, realizations
from .units import format_orbits


@dataclass(frozen=True)
class CheckSettings:
    """User-facing settings of ``exostab check``."""

    orbits: float = 1e4  # N-body run length in orbits of the innermost planet
    draws: int = 20  # Monte Carlo draws within the published uncertainties
    seed: int = 0
    inclination_prior: InclinationPrior = "none"
    ias15_check: bool = True
    dt_fraction: float = 1 / 30
    jobs: int | None = None  # worker processes (None: all cores but one)
    n_samples: int = 400  # time-series samples kept for the plots
    budget_s: float | None = None  # wall-clock budget that chose orbits and draws, if any
    spock_python: str | None = None  # interpreter of a SPOCK environment: adds the optional SPOCK indicator


def settings_for_budget(system: System, budget_s: float, base: CheckSettings) -> tuple[CheckSettings, Plan]:
    """Settings whose run length and number of draws fit a wall-clock budget (see :mod:`exostab.budget`)."""
    nominal = realizations(system, 0, base.seed, base.inclination_prior)[0]
    p = plan(nominal, budget_s, jobs=base.jobs, ias15_check=base.ias15_check)
    return replace(base, orbits=p.orbits, draws=p.draws, budget_s=budget_s), p


@dataclass
class CheckResult:
    report: Report
    realizations: list[Realization]
    runs: list[RunResult]
    ias15: RunResult | None
    extra: dict[str, object] = field(default_factory=dict)


NO_DRAWS = (
    "No Monte Carlo draws were run: the result holds for the nominal parameters only and was not tested against "
    "the published uncertainties."
)
EDITED_FLAGS = ("edited_in_web_app", "what_if_in_web_app")
EDITED = "This run uses values changed in the web app, not the published ones. "
HORIZON = " The N-body test covers only the integrated time span, not the age of the system."


def _join(items: Sequence[str]) -> str:
    """Join words as in prose: a; a and b; a, b and c."""
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " and " + items[-1]


def _draws(n: int) -> str:
    return "1 draw" if n == 1 else f"{n} draws"


def upper_limit_inputs(system: System) -> list[str]:
    """The inputs of the runs that are only published upper limits, e.g. ``["masses of X b and X c"]``.

    The nominal run uses each limit and the draws are uniform below it (:mod:`exostab.sampling`).
    """
    out = ["stellar mass"] if system.star.mass_msun.provenance is Provenance.UPPER_LIMIT else []
    names: dict[tuple[str, str], list[str]] = {
        ("period", "periods"): [],
        ("mass", "masses"): [],
        ("eccentricity", "eccentricities"): [],
        ("argument of periastron", "arguments of periastron"): [],
        ("orbital phase", "orbital phases"): [],
    }
    for p in system.planets:
        values = (p.period_days, p.mass_earth, p.eccentricity, p.omega_deg, p.phase.value)
        for planets, v in zip(names.values(), values, strict=True):
            if v is not None and v.provenance is Provenance.UPPER_LIMIT:
                planets.append(p.name)
    for (one, many), planets in names.items():
        if planets:
            out.append(f"{one if len(planets) == 1 else many} of {_join(planets)}")
    return out


def _failed_draws(r: IndicatorResult) -> str | None:
    """For an indicator with draws that are not stable, a line like "AMD: of 20 draws, 1 unstable"."""
    d = r.draws
    if d is None or d.stable == d.n:
        return None
    words = {Verdict.MARGINAL: "marginal", Verdict.UNSTABLE: "unstable", Verdict.INCONCLUSIVE: "inconclusive"}
    if r.name == "nbody":
        words |= {Verdict.MARGINAL: "chaotic", Verdict.UNSTABLE: "with a close encounter or escape"}
    return f"{r.title}: of {_draws(d.n)}, " + _join(
        [f"{d.count(v)} {w}" for v, w in words.items() if d.count(v)]
    )


def _nbody_held(nb: IndicatorResult) -> list[str]:
    """Why the N-body verdict cannot be stable although the WHFast runs are regular (see megno.evaluate)."""
    nominal = nb.details.get("nominal") or {}
    ias15 = nb.details.get("ias15") or {}
    out = []
    if ias15 and ias15.get("classification") != nominal.get("classification"):
        out.append(
            f"WHFast and IAS15 disagree on the nominal run ({nominal.get('classification')} vs "
            f"{ias15.get('classification')})"
        )
    n_outer = nominal.get("n_orbits_outermost")
    if (
        nominal.get("status") == "completed"
        and n_outer is not None
        and n_outer < nbody_indicator.MIN_OUTER_ORBITS
    ):
        out.append(
            f"the outermost planet completes only {format_orbits(n_outer)} orbits, fewer than the "
            f"{nbody_indicator.MIN_OUTER_ORBITS} needed to judge it (a longer run is needed)"
        )
    return out


def _all_regular(nb: IndicatorResult) -> bool:
    """True if the nominal N-body run and every draw are regular."""
    return nb.nominal_verdict is Verdict.STABLE and (nb.draws is None or nb.draws.stable == nb.draws.n)


def _nbody_sentences(nb: IndicatorResult, allowed: str) -> list[str]:
    """What the N-body runs found, for a marginal overall verdict, without claiming more than the counts."""
    d = nb.draws
    held = _nbody_held(nb)
    if _all_regular(nb):
        runs = "the nominal parameters" + (
            "" if d is None else " and the 1 draw" if d.n == 1 else f" and all {d.n} draws"
        )
        if nb.verdict is Verdict.STABLE:
            return [f"The N-body integration shows regular motion for {runs}."]
        why = _join(held) if held else "see the N-body notes"
        return [f"Every WHFast run is regular ({runs}), but the N-body verdict is only marginal: {why}."]
    nominal = {
        Verdict.STABLE: "regular",
        Verdict.MARGINAL: "chaotic",
        Verdict.UNSTABLE: "stopped by a close encounter or escape",
        Verdict.INCONCLUSIVE: "inconclusive",
    }[nb.nominal_verdict]
    text = f"Direct integration: the nominal run is {nominal}"
    if d is not None:
        text += (
            f"; of {_draws(d.n)}, {d.stable} are regular, {d.marginal} chaotic and {d.unstable} had close "
            "encounters or escapes" + (f" ({d.inconclusive} inconclusive)" if d.inconclusive else "")
        )
    out = [text + "."]
    found = [w for w, k in (("chaotic", d.marginal), ("unstable", d.unstable)) if k] if d is not None else []
    if found:
        out.append(
            f"No draw within the {allowed} is regular."
            if d is not None and d.stable == 0
            else f"Part of the parameter range allowed by the {allowed} is {' or '.join(found)}."
        )
    if held:
        out.append(f"In addition, {_join(held)}.")
    return out


def overall_verdict(
    indicators: dict[str, IndicatorResult],
    *,
    upper_limits: Sequence[str] = (),
    n_stars: int = 1,
    edited: bool = False,
) -> Overall:
    """Conservative combination of the per-indicator verdicts.

    * unstable: the direct N-body integration is unstable (close encounters or escapes in the nominal run
      and in at least 95% of the draws), and that evidence rests neither on upper limits, nor on the nominal
      run alone, nor on a single-star model of a system with several stars;
    * inconclusive: the N-body integration could not be trusted;
    * stable: every indicator says stable (including SPOCK when it is enabled), no N-body draw had a close
      encounter or escape, and Monte Carlo draws were run;
    * marginal: everything else, i.e. whenever the indicators disagree or any of them is marginal.

    ``upper_limits`` lists the inputs that are only published upper limits (:func:`upper_limit_inputs`). The
    nominal run uses each limit and the draws are uniform below it, which does not sample a measurement
    uncertainty. For Hill spacing and the integration, a limit on a planet's mass or eccentricity is normally the
    hardest case; for AMD a mass limit need not be, because beta_S grows as the innermost planet gets lighter. So a
    stable result describes the values that were run, not every value below a mass limit (``docs/methods.md``,
    BD-06 1339). An N-body instability only constrains the limited values and gives "marginal", whichever input is
    limited. Without Monte Carlo draws (``--draws 0``) nothing was tested against the uncertainties, so the verdict
    is at most "marginal". ``n_stars`` is the number of stars in the system (the archive's ``sy_snum``); only the host star
    is modelled, so with more than one an N-body instability may come from the model and also gives "marginal":
    the planets may orbit different stars (Kepler-132 b and c, whose periods differ by 4%, cannot stably orbit
    one star), or a companion may change their orbits. The summary is built from the draw counts and never
    claims more than they show. With ``edited`` (values changed in the web app) it says so, and does not call the
    uncertainties published; the verdict is the same.
    """
    overall = _combined_verdict(indicators, upper_limits, n_stars, edited)
    if edited:
        return overall.model_copy(update={"summary": EDITED + overall.summary})
    return overall


def _combined_verdict(
    indicators: dict[str, IndicatorResult], upper_limits: Sequence[str], n_stars: int, edited: bool
) -> Overall:
    nb = indicators["nbody"]
    others = [r for k, r in indicators.items() if k != "nbody"]
    not_stable = [
        f"{r.title}: {r.verdict.value}" for r in indicators.values() if r.verdict is not Verdict.STABLE
    ]
    if nb.verdict is Verdict.INCONCLUSIVE:
        return Overall(
            verdict=Verdict.INCONCLUSIVE,
            summary="The N-body integrations could not be trusted (see the N-body notes), so no overall verdict "
            "is given.",
            reasons=not_stable,
        )
    n = nb.draws.n if nb.draws is not None else 0
    encounters = nb.draws.unstable if nb.draws is not None else 0
    # Draws that are not stable although their indicator's verdict is (the 95% rule lets up to 5% through).
    hidden = [f for r in indicators.values() if r.verdict is Verdict.STABLE and (f := _failed_draws(r))]
    limits = _join(upper_limits) if upper_limits else ""
    uncertainties = "uncertainties" if edited else "published uncertainties"
    allowed = uncertainties + (" and upper limits" if upper_limits else "")
    no_draws = NO_DRAWS.replace("published uncertainties", uncertainties)
    caveats = [no_draws] if n == 0 else []
    extra = [f"Only upper limits are published for: {limits}."] if upper_limits else []

    if nb.verdict is Verdict.UNSTABLE:
        found = "Direct integration finds close encounters or escapes for the nominal parameters" + (
            f" and for {encounters} of {_draws(n)}" if n else ""
        )
        if not upper_limits and n_stars == 1 and n:
            return Overall(
                verdict=Verdict.UNSTABLE,
                summary=found + f" within the {uncertainties}.",
                reasons=not_stable,
            )
        sentences = [found + "."]
        if upper_limits:
            sentences.append(
                f"These runs use values that are only published upper limits ({limits}): the nominal run "
                "takes each limit and the draws are uniform below it, so the instability may come from values "
                "the system does not have. It constrains those values; it does not show that the system is "
                "unstable."
            )
        stars = [f"The system has {n_stars} stars; only the host star is modelled."] if n_stars > 1 else []
        if stars:
            sentences.append(
                f"The system has {n_stars} stars, but every planet is integrated around the host star alone: "
                "the planets may orbit different stars, or a companion may change their orbits, so an "
                "instability of this single-star model does not show that the system is unstable."
            )
        return Overall(
            verdict=Verdict.MARGINAL,
            summary=" ".join(sentences + caveats),
            reasons=not_stable + extra + stars + caveats,
        )

    if nb.verdict is Verdict.STABLE and all(r.verdict is Verdict.STABLE for r in others):
        if n == 0:
            return Overall(
                verdict=Verdict.MARGINAL,
                summary="Every indicator is stable for the nominal parameters. " + no_draws,
                reasons=caveats,
            )
        if encounters:
            # A close encounter within the uncertainties is direct evidence of instability (DECISIONS.md, D15).
            return Overall(
                verdict=Verdict.MARGINAL,
                summary=f"Every indicator is stable for the nominal parameters and for at least {AGREEMENT:.0%} "
                f"of the draws, but {encounters} of {n} N-body draws had a close encounter or escape: part of "
                f"the parameter range allowed by the {allowed} is unstable.",
                reasons=hidden + extra,
            )
        if hidden:
            summary = (
                f"Every indicator is stable for the nominal parameters and for at least {AGREEMENT:.0%} of the "
                f"{_draws(n)}, but not for all of them ({'; '.join(hidden)})."
            )
        else:
            summary = "All indicators agree: no sign of instability for the nominal parameters or " + (
                "the 1 draw." if n == 1 else f"any of the {n} draws."
            )
        return Overall(verdict=Verdict.STABLE, summary=summary + HORIZON, reasons=hidden)

    sentences = _nbody_sentences(nb, allowed)
    bad = [f"{r.title}: {r.verdict.value}" for r in others if r.verdict is not Verdict.STABLE]
    if bad:
        sentences.append(f"The other indicators cannot guarantee stability ({', '.join(bad)}).")
        if nb.verdict is Verdict.STABLE and _all_regular(nb):
            sentences.extend(
                r.summary
                if r.nominal_verdict is not Verdict.STABLE
                else f"{r.title} is stable for the nominal parameters, but the draws disagree."
                for r in others
                if r.verdict is not Verdict.STABLE
            )
    if upper_limits:
        sentences.append(
            f"Some inputs are only published upper limits ({limits}): the nominal run takes each limit and the "
            "draws are uniform below it."
        )
    return Overall(
        verdict=Verdict.MARGINAL,
        summary=" ".join(sentences + caveats),
        reasons=not_stable + hidden + extra + caveats,
    )


def check_system(system: System, settings: CheckSettings, *, command: str | None = None) -> CheckResult:
    """Run the Hill, AMD and N-body indicators on ``system``."""
    t0 = time.perf_counter()
    reals = realizations(system, settings.draws, settings.seed, settings.inclination_prior)
    nominal, draws = reals[0], reals[1:]
    hill = hill_indicator.evaluate(nominal, draws)
    assumed_e = [p.name for p in system.planets if p.eccentricity.provenance is Provenance.ASSUMED]
    amd = amd_indicator.evaluate(nominal, draws, assumed_eccentricities=assumed_e)
    nb_settings = nbody_indicator.NBodySettings(
        orbits=settings.orbits,
        dt_fraction=settings.dt_fraction,
        ias15_check=settings.ias15_check,
        n_samples=settings.n_samples,
        jobs=settings.jobs,
    )
    runs, ias15 = nbody_indicator.integrate_all(reals, nb_settings, settings.seed)
    # A phase relative to the periastron needs its direction: with omega unknown (cleared in the web app), the
    # planet's longitude is random in every run as well.
    relative = (PhaseKind.PERIASTRON, PhaseKind.MEAN_ANOMALY)
    random_phases = [
        p.name
        for p in system.planets
        if p.phase.kind is PhaseKind.RANDOM or (p.phase.kind in relative and not p.omega_deg.is_known)
    ]
    nbody = nbody_indicator.evaluate(
        runs, ias15, random_phases=random_phases, from_file=system.source.kind == "file"
    )
    indicators = {"hill": hill, "amd": amd, "nbody": nbody}
    if settings.spock_python and len(nominal.bodies) >= 3:
        indicators["spock"] = spock_indicator.evaluate(nominal, draws, settings.spock_python)
    report = build_report(
        system=system,
        settings=settings,
        epoch_jd=choose_epoch(system),
        nominal=nominal,
        nominal_run=runs[0],
        indicators=indicators,
        overall=overall_verdict(
            indicators,
            upper_limits=upper_limit_inputs(system),
            n_stars=system.star.n_stars,
            edited=any(f.rule in EDITED_FLAGS for f in system.flags),
        ),
        runtime_s=time.perf_counter() - t0,
        command=command,
    )
    return CheckResult(report=report, realizations=reals, runs=runs, ias15=ias15)
