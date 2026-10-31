"""Command-line interface: ``exostab check | sweep | list | catalog build``."""

from __future__ import annotations

import re
import shlex
import sys
import time
from enum import Enum
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.markup import escape
from rich.table import Table

from . import __version__
from .models import System

REPO = "https://github.com/mimitoz62/exostab"
SPOCK_ENV_SCRIPT = f"{REPO}/blob/main/scripts/make_spock_env.sh"  # not part of the package
QUICKSTART = "https://mimitoz62.github.io/exostab/quickstart/"  # install commands (exostab is not on PyPI)

app = typer.Typer(
    name="exostab",
    help="Is this planetary system dynamically stable? Hill spacing, AMD and N-body/MEGNO indicators for "
    "known exoplanet systems, with every assumption shown.",
    epilog=f"Web app: python -m exostab.web (needs the \\[web] extra: {QUICKSTART}).",
    no_args_is_help=True,
    add_completion=False,
    rich_markup_mode="rich",
)
catalog_app = typer.Typer(help="Batch stability catalog of archive systems.", no_args_is_help=True)
app.add_typer(catalog_app, name="catalog")

console = Console()
err_console = Console(stderr=True)


class Prior(str, Enum):
    none = "none"
    isotropic = "isotropic"


class SweepParam(str, Enum):
    e = "e"
    mass = "mass"
    period = "period"
    omega = "omega"


def _version_callback(value: bool) -> None:
    if value:
        console.print(f"exostab {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: Annotated[
        bool,
        typer.Option(
            "--version", callback=_version_callback, is_eager=True, help="Show the version and exit."
        ),
    ] = False,
) -> None:
    """exostab command-line interface."""


def slug(name: str) -> str:
    return re.sub(r"[^0-9A-Za-z]+", "-", name).strip("-").lower() or "system"


def _print_error(message: object) -> None:
    # The message can quote what was typed, and "[/red]" in a name is text here, not markup.
    err_console.print(f"[red]{escape(str(message))}[/red]")


def _load(name: str | None, from_file: Path | None, refresh: bool, offline: bool) -> System:
    from .data import (
        IncompleteSystemError,
        SystemFileError,
        SystemNotFoundError,
        load_system,
        load_system_file,
    )
    from .data.archive import ArchiveError

    if (name is None) == (from_file is None):
        err_console.print("[red]Give either a system name or --from-file (not both).[/red]")
        raise typer.Exit(2)
    try:
        if from_file is not None:
            return load_system_file(from_file)
        assert name is not None
        return load_system(name, refresh=refresh, offline=offline)
    except (SystemNotFoundError, IncompleteSystemError, SystemFileError, ArchiveError) as exc:
        _print_error(exc)
        raise typer.Exit(1) from exc


def _command() -> str:
    return "exostab " + " ".join(shlex.quote(a) for a in sys.argv[1:])


OrbitsOpt = Annotated[
    float, typer.Option("--orbits", help="N-body run length, in orbits of the innermost planet.", min=10)
]
SeedOpt = Annotated[
    int,
    # numpy's SeedSequence takes only non-negative integers
    typer.Option(
        "--seed",
        help="Random seed: the same seed gives the same draws and, on the same platform and software "
        "versions, the same results.",
        min=0,
    ),
]
JobsOpt = Annotated[
    int | None, typer.Option("--jobs", "-j", help="Worker processes (default: all cores but one).", min=1)
]
RefreshOpt = Annotated[
    bool, typer.Option("--refresh", help="Query the archive again instead of using the disk cache.")
]
OfflineOpt = Annotated[
    bool, typer.Option("--offline", help="Use only the bundled offline snapshot (22 systems).")
]
FileOpt = Annotated[
    Path | None,
    typer.Option(
        "--from-file",
        help="Read the system from a YAML file instead of the archive.",
        exists=True,
        dir_okay=False,
    ),
]


# Each command has a short help for the command lists (exostab --help, docs/cli.md): without one, Typer's docs
# generator cuts the docstring's first sentence at about 45 characters and ends it with "...".
@app.command(short_help="Stability report card for one system.")
def check(
    name: Annotated[str | None, typer.Argument(help='Host or planet name, e.g. "TRAPPIST-1".')] = None,
    from_file: FileOpt = None,
    orbits: Annotated[
        float | None,
        typer.Option(
            "--orbits",
            help="N-body run length, in orbits of the innermost planet \\[default: 10000].",
            min=10,
        ),
    ] = None,
    draws: Annotated[
        int | None,
        typer.Option(
            "--draws",
            help="Monte Carlo draws within the published uncertainties \\[default: 20]. With 0 nothing is "
            "tested against the uncertainties, and the overall verdict is never stable or unstable.",
            min=0,
        ),
    ] = None,
    budget: Annotated[
        str | None,
        typer.Option(
            "--budget",
            help="Choose --orbits and --draws to fit a wall-clock budget: 'fast' (about 10 s), 'thorough' "
            "(about 2 min) or a number of seconds.",
        ),
    ] = None,
    seed: SeedOpt = 0,
    out: Annotated[
        Path | None, typer.Option("--out", help="Output folder (default: exostab-results/<system>).")
    ] = None,
    inclination_prior: Annotated[
        Prior,
        typer.Option(
            "--inclination-prior",
            help="For minimum masses: 'none' uses m sin i as the mass; "
            "'isotropic' draws the inclination (cos i uniform, sin i >= 0.1) in every draw.",
        ),
    ] = Prior.none,
    no_ias15: Annotated[
        bool, typer.Option("--no-ias15", help="Skip the IAS15 check of the nominal run.")
    ] = False,
    no_plots: Annotated[bool, typer.Option("--no-plots", help="Do not write PNG figures.")] = False,
    spock: Annotated[
        bool,
        typer.Option(
            "--spock",
            help="Add SPOCK's machine-learned classifier (3+ planets). Needs a separate SPOCK environment, built "
            f"by scripts/make_spock_env.sh ({SPOCK_ENV_SCRIPT}); its python is taken from --spock-python or "
            "EXOSTAB_SPOCK_PYTHON.",
        ),
    ] = False,
    spock_python: Annotated[
        str | None, typer.Option("--spock-python", help="Python interpreter of the SPOCK environment.")
    ] = None,
    jobs: JobsOpt = None,
    refresh: RefreshOpt = False,
    offline: OfflineOpt = False,
) -> None:
    """Stability report card for one system (archive name or --from-file)."""
    from .analysis import CheckSettings, check_system, settings_for_budget
    from .budget import parse_budget
    from .plots import check_figures
    from .report import render, write_json

    if budget is not None and (orbits is not None or draws is not None):
        err_console.print(
            "[red]--budget chooses --orbits and --draws; give either --budget or those options.[/red]"
        )
        raise typer.Exit(2)
    python = None
    if spock or spock_python:
        from .indicators.spock import spock_python as find_spock

        python = find_spock(spock_python)
        if python is None:
            err_console.print(
                "[red]--spock needs a SPOCK environment: build one with scripts/make_spock_env.sh (in a clone of "
                f"the repository, or download it from {SPOCK_ENV_SCRIPT}) and pass its python with --spock-python "
                "or EXOSTAB_SPOCK_PYTHON.[/red]"
            )
            raise typer.Exit(2)
    system = _load(name, from_file, refresh, offline)
    if python and len(system.planets) < 3:
        console.print(
            "[yellow]SPOCK applies to three or more planets; it is skipped for this system.[/yellow]"
        )
    settings = CheckSettings(
        spock_python=python,
        orbits=orbits if orbits is not None else 1e4,
        draws=draws if draws is not None else 20,
        seed=seed,
        inclination_prior=inclination_prior.value,
        ias15_check=not no_ias15,
        jobs=jobs,
    )
    if budget is not None:
        try:
            seconds = parse_budget(budget)
        except ValueError as exc:
            _print_error(exc)
            raise typer.Exit(2) from exc
        with console.status(f"Measuring integration speed for a {seconds:g} s budget…"):
            settings, p = settings_for_budget(system, seconds, settings)
        console.print(
            f"[dim]Budget {seconds:g} s: {settings.orbits:,.0f} orbits, {settings.draws} draws "
            f"(estimated {p.estimated_s:.0f} s).[/dim]"
        )
        if p.warning:
            console.print(f"[yellow]{p.warning}[/yellow]")
    from .indicators.spock import SpockUnavailableError

    with console.status(
        f"Integrating {system.name}: {settings.draws + 1} runs of {settings.orbits:.3g} orbits…"
    ):
        try:
            result = check_system(system, settings, command=_command())
        except SpockUnavailableError as exc:
            _print_error(exc)
            raise typer.Exit(1) from exc
    out_dir = out or Path("exostab-results") / slug(system.name)
    out_dir.mkdir(parents=True, exist_ok=True)
    outputs = [write_json(result.report, out_dir / "report.json")]
    if not no_plots:
        outputs += check_figures(result, out_dir)
    render(result.report, console, outputs=outputs)
    console.print(f"[dim]Finished in {result.report.runtime_s:.1f} s.[/dim]")


@app.command(short_help="Vary one parameter of one planet.")
def sweep(
    name: Annotated[str | None, typer.Argument(help="Host or planet name.")] = None,
    planet: Annotated[str, typer.Option("--planet", help="Planet letter or full name, e.g. 'b'.")] = "b",
    param: Annotated[
        SweepParam,
        typer.Option("--param", help="e (eccentricity), mass (Earth masses), period (days) or omega (deg)."),
    ] = SweepParam.e,
    value_range: Annotated[
        tuple[float, float] | None,
        typer.Option(
            "--range",
            help="Start and end values, in the unit of --param \\[default for e: 0 0.5; required for mass, "
            "period and omega].",
        ),
    ] = None,
    steps: Annotated[int, typer.Option("--steps", help="Number of values.", min=2)] = 25,
    from_file: FileOpt = None,
    orbits: OrbitsOpt = 1e4,
    seed: SeedOpt = 0,
    out: Annotated[
        Path | None, typer.Option("--out", help="Output folder (default: exostab-results/<system>).")
    ] = None,
    jobs: JobsOpt = None,
    refresh: RefreshOpt = False,
    offline: OfflineOpt = False,
) -> None:
    """Vary one parameter of one planet and record every indicator (nominal parameters otherwise)."""
    from .sweep import check_value, run_sweep, write_sweep

    if value_range is None:
        if param is not SweepParam.e:
            err_console.print(f"[red]--range is required with --param {param.value}.[/red]")
            raise typer.Exit(2)
        value_range = (0.0, 0.5)
    try:
        for end in value_range:
            check_value(param.value, end)
    except ValueError as exc:
        _print_error(f"--range: {exc}.")
        raise typer.Exit(2) from exc
    system = _load(name, from_file, refresh, offline)
    try:
        system.planet(planet)
    except KeyError as exc:
        _print_error(exc.args[0])
        raise typer.Exit(1) from exc
    with console.status(f"Sweeping {param.value} of {planet} over {steps} values…"):
        rows = run_sweep(system, planet, param.value, value_range, steps, orbits=orbits, seed=seed, jobs=jobs)
    out_dir = out or Path("exostab-results") / slug(system.name)
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = write_sweep(
        rows,
        system,
        planet,
        param.value,
        out_dir,
        value_range=value_range,
        steps=steps,
        orbits=orbits,
        seed=seed,
        command=_command(),
    )
    t = Table(title=f"{system.name}: sweep of {param.value} for planet {planet}", header_style="bold")
    for col in ("value", "N-body", "<Y>", "Hill", "AMD"):
        t.add_column(col)
    for r in rows:
        # <Y> of a run stopped by a close encounter or escape is not meaningful
        show_megno = r["megno"] is not None and r["nbody_class"] != "unstable"
        t.add_row(
            f"{r['value']:.4g}",
            r["nbody_class"],
            f"{r['megno']:.3g}" if show_megno else "—",
            r["hill_verdict"],
            r["amd_verdict"],
        )
    console.print(t)
    console.print(f"[dim]Saved: {', '.join(str(p) for p in paths)}[/dim]")


@app.command("list", short_help="List multi-planet systems in the archive.")
def list_cmd(
    min_planets: Annotated[int, typer.Option("--min-planets", help="Minimum number of planets.", min=2)] = 2,
    max_period_days: Annotated[
        float | None,
        typer.Option(
            "--max-period-days", help="Only systems whose planets all have periods below this (days)."
        ),
    ] = None,
    limit: Annotated[
        int, typer.Option("--limit", help="Show at most this many systems (0: all).", min=0)
    ] = 0,
    refresh: RefreshOpt = False,
    offline: OfflineOpt = False,
) -> None:
    """List multi-planet systems in the archive table."""
    from .data import list_systems, load_rows
    from .data.archive import ArchiveError

    try:
        rows, info = load_rows(refresh=refresh, offline=offline)
    except ArchiveError as exc:
        _print_error(exc)
        raise typer.Exit(1) from exc
    systems = list_systems(rows, min_planets=min_planets, max_period_days=max_period_days)
    shown = systems[:limit] if limit else systems
    t = Table(
        header_style="bold",
        title=f"{len(systems)} systems (data: {info.kind}, {(info.retrieved_utc or '')[:10]})",
    )
    for col, just in (
        ("System", "left"),
        ("Planets", "right"),
        ("Periods (d)", "right"),
        ("M* (M☉)", "right"),
        ("m sin i", "right"),
        ("est. mass", "right"),
        ("no e", "right"),
        ("Discovery", "left"),
    ):
        t.add_column(col, justify=just, no_wrap=col in ("System", "Periods (d)"))  # type: ignore[arg-type]
    for s in shown:
        periods = f"{s.min_period_days:.4g}–{s.max_period_days:.4g}" if s.min_period_days is not None else "—"
        t.add_row(
            s.host,
            str(s.n_planets),
            periods,
            f"{s.star_mass_msun:.3g}" if s.star_mass_msun else "—",
            str(s.minimum_masses),
            str(s.estimated_masses),
            str(s.missing_eccentricities),
            s.discovery_methods,
        )
    console.print(t)
    if info.note:
        console.print(f"[yellow]{info.note}[/yellow]")
    if limit and len(systems) > limit:
        console.print(f"[dim]… {len(systems) - limit} more; use --limit 0 to show all.[/dim]")


@catalog_app.command("build", short_help="Compute the catalog of multi-planet systems.")
def catalog_build(
    limit: Annotated[
        int, typer.Option("--limit", help="Process at most this many systems (0: all).", min=0)
    ] = 0,
    out: Annotated[Path, typer.Option("--out", help="Output folder.")] = Path("catalog"),
    orbits: OrbitsOpt = 1e4,
    draws: Annotated[
        int,
        typer.Option(
            "--draws",
            help="Monte Carlo draws per system (with 0 no overall verdict is stable or unstable).",
            min=0,
        ),
    ] = 10,
    seed: SeedOpt = 0,
    max_seconds: Annotated[
        float,
        typer.Option(
            "--max-seconds",
            help="Wall-clock cap per system; systems that exceed it are recorded as 'timeout'.",
            min=1,
        ),
    ] = 120.0,
    jobs: JobsOpt = None,
    refresh: RefreshOpt = False,
    offline: OfflineOpt = False,
) -> None:
    """Compute indicators for the multi-planet systems and write catalog.csv (+ catalog.parquet)."""
    from .catalog.build import CatalogSettings, build_catalog

    settings = CatalogSettings(orbits=orbits, draws=draws, seed=seed, max_seconds=max_seconds, jobs=jobs)
    t0 = time.perf_counter()
    paths, rows = build_catalog(settings, out, limit=limit, refresh=refresh, offline=offline, console=console)
    counts: dict[str, int] = {}
    for r in rows:
        key = str(r["overall"] or r["status"])
        counts[key] = counts.get(key, 0) + 1
    console.print(
        f"{len(rows)} systems in {time.perf_counter() - t0:.0f} s: "
        + ", ".join(f"{k} {v}" for k, v in sorted(counts.items()))
    )
    console.print(f"[dim]Saved: {', '.join(str(p) for p in paths)}[/dim]")


if __name__ == "__main__":  # pragma: no cover
    app()
