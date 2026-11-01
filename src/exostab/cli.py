"""Command-line interface: ``exostab check | sweep | list | catalog build``."""

from __future__ import annotations

import hashlib
import io
import itertools
import math
import os
import re
import shlex
import signal
import sys
import tempfile
import time
from collections.abc import Iterable, Iterator
from concurrent.futures.process import BrokenProcessPool
from contextlib import contextmanager
from enum import Enum
from pathlib import Path
from types import FrameType
from typing import Annotated, Any, NoReturn

import typer
from rich.console import Console
from rich.markup import escape
from rich.measure import Measurement
from rich.table import Table
from rich.text import Text

from . import __version__
from .models import System, UnusableParametersError

# The raw file, which can be downloaded; it is not part of the package.
SPOCK_ENV_SCRIPT = "https://raw.githubusercontent.com/mimitoz62/exostab/main/scripts/make_spock_env.sh"
QUICKSTART = "https://mimitoz62.github.io/exostab/quickstart/"  # install commands (exostab is not on PyPI)
# Far beyond any run that can finish; a larger number ends in a memory error or an overflow.
MAX_STEPS_OR_DRAWS = 1_000_000
MAX_CATALOG_SEED = 2**63 - 1  # the seed column of catalog.parquet is a signed 64-bit integer
LIST_WIDTH_WHEN_PIPED, LIST_DISCOVERY_MIN_WIDTH = 200, 16
OUTPUT_FILES = {
    "check": ("report.json", "orbits.png", "megno.png"),
    "sweep": ("sweep.csv", "sweep.json", "sweep.png"),
    "catalog": ("catalog.csv", "catalog.parquet", "catalog_meta.json"),
}


def _stop_on_signal(signum: int, frame: FrameType | None) -> NoReturn:
    raise SystemExit(128 + signum)


class _Exostab(typer.Typer):
    """The exostab command, with what must be in place before Typer parses the arguments."""

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        # A terminal or a redirected file that cannot encode "⊕" or "☉" gets "?" instead of a traceback.
        for stream in (sys.stdout, sys.stderr):
            if isinstance(stream, io.TextIOWrapper):
                stream.reconfigure(errors="replace")
        # By default these signals would end this process at once and leave its workers running.
        for name in ("SIGTERM", "SIGHUP"):
            if hasattr(signal, name):
                signal.signal(getattr(signal, name), _stop_on_signal)
        return super().__call__(*args, **kwargs)


app = _Exostab(
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

# Names and paths are text: emoji codes are switched off here, and square brackets are escaped wherever they are printed.
console = Console(emoji=False)
err_console = Console(stderr=True, emoji=False)


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
    """Name of the default output folder: the letters and digits of ``name``, in any script, short enough for
    every file system (with a short hash when it had to be cut, so that long names stay apart)."""
    full = re.sub(r"[\W_]+", "-", name).strip("-").lower() or "system"
    cut = full.encode()[:100].decode(errors="ignore").rstrip("-")
    return cut if cut == full else f"{cut}-{hashlib.sha256(full.encode()).hexdigest()[:8]}"


def _print_error(message: object) -> None:
    # The message can quote what was typed, and "[/red]" in a name is text here, not markup.
    err_console.print(f"[red]{escape(str(message))}[/red]")


def _plural(n: int, word: str) -> str:
    return f"{n} {word}" if n == 1 else f"{n} {word}s"


def _saved(paths: Iterable[Path]) -> None:
    """The saved files, on one line whatever the width, so that a long path can be copied or piped."""
    console.print(Text("Saved: " + ", ".join(str(p) for p in paths), style="dim"), soft_wrap=True)


def _finite_number(value: float | None) -> float | None:
    """Callback of numeric options: their minimums let NaN and infinity through, and a run never ends with them."""
    if value is not None and not math.isfinite(value):
        raise typer.BadParameter(f"must be a finite number, got {value}")
    return value


def path(value: str | Path) -> Path:
    """Parser of --out. Its name is what the help shows. An empty value is usually an unset shell variable in
    --out "$DIR", and would write into the current folder."""
    if str(value) == "":
        raise typer.BadParameter("the output folder is empty; give a path")
    return Path(value)


def _output_folder(out: Path, files: Iterable[str]) -> Path:
    """``out``, created and tested before any integration: finding out afterwards would lose the whole run."""
    try:
        out.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryFile(dir=out):
            pass
    except OSError as exc:
        _print_error(
            f"Cannot write to the output folder {out}: {exc.strerror or exc}. Choose another with --out."
        )
        raise typer.Exit(2) from exc
    for name in files:
        target = out / name
        if target.is_dir() or (target.exists() and not os.access(target, os.W_OK)):
            _print_error(f"Cannot write {target}. Choose another output folder with --out.")
            raise typer.Exit(2)
    return out


def _refuse_conflicting_sources(refresh: bool, offline: bool) -> None:
    from .data.store import offline_requested

    if refresh and offline:
        err_console.print(
            "[red]--offline uses only the bundled snapshot and --refresh the archive; give one.[/red]"
        )
        raise typer.Exit(2)
    if refresh and offline_requested():
        err_console.print(
            "[yellow]EXOSTAB_OFFLINE is set, so --refresh is ignored: the snapshot is used.[/yellow]"
        )


@contextmanager
def _analysis_errors() -> Iterator[None]:
    """One line, not a traceback, for parameters the analysis cannot use and for a worker that died."""
    try:
        yield
    except UnusableParametersError as exc:
        _print_error(exc)
        raise typer.Exit(1) from exc
    except BrokenProcessPool as exc:
        _print_error(
            "A worker process died, possibly because the computer ran out of memory, so the run was stopped. "
            "Try fewer draws or fewer workers (--jobs)."
        )
        raise typer.Exit(1) from exc


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
    float,
    typer.Option(
        "--orbits",
        help="N-body run length, in orbits of the innermost planet.",
        min=10,
        callback=_finite_number,
    ),
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
OutOpt = Annotated[
    Path | None,
    typer.Option(
        "--out",
        help="Output folder (default: a folder named after the system in exostab-results).",
        parser=path,
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
@app.command(
    short_help="Stability report card for one system.",
    epilog=f"Script that builds the SPOCK environment: {SPOCK_ENV_SCRIPT}",
)
def check(
    name: Annotated[str | None, typer.Argument(help='Host or planet name, e.g. "TRAPPIST-1".')] = None,
    from_file: FileOpt = None,
    orbits: Annotated[
        float | None,
        typer.Option(
            "--orbits",
            help="N-body run length, in orbits of the innermost planet \\[default: 10000].",
            min=10,
            callback=_finite_number,
        ),
    ] = None,
    draws: Annotated[
        int | None,
        typer.Option(
            "--draws",
            help="Monte Carlo draws within the published uncertainties \\[default: 20]. With 0 nothing is "
            "tested against the uncertainties, and the overall verdict is never stable or unstable.",
            min=0,
            max=MAX_STEPS_OR_DRAWS,
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
    out: OutOpt = None,
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
            help="Add SPOCK's machine-learned classifier (3+ planets). Needs a separate SPOCK environment (see "
            "below); its python is taken from --spock-python or EXOSTAB_SPOCK_PYTHON.",
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
    from .report import render, write_json

    _refuse_conflicting_sources(refresh, offline)
    if budget is not None and (orbits is not None or draws is not None):
        err_console.print(
            "[red]--budget chooses --orbits and --draws; give either --budget or those options.[/red]"
        )
        raise typer.Exit(2)
    if spock_python == "":  # an unset shell variable in --spock-python "$PY", which would run without SPOCK
        err_console.print("[red]--spock-python is empty; give the path of the interpreter.[/red]")
        raise typer.Exit(2)
    python = None
    if spock or spock_python:
        from .indicators.spock import SpockUnavailableError, probe
        from .indicators.spock import spock_python as find_spock

        python = find_spock(spock_python)
        if python is None:
            err_console.print(
                "[red]--spock needs a SPOCK environment: build one with scripts/make_spock_env.sh (in a clone of "
                f"the repository, or download it from {SPOCK_ENV_SCRIPT}) and pass its python with --spock-python "
                "or EXOSTAB_SPOCK_PYTHON.[/red]"
            )
            raise typer.Exit(2)
        try:
            probe(python)
        except SpockUnavailableError as exc:
            _print_error(exc)
            raise typer.Exit(2) from exc
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
    seconds = None
    if budget is not None:
        try:
            seconds = parse_budget(budget)
        except ValueError as exc:
            _print_error(exc)
            raise typer.Exit(2) from exc
    out_dir = _output_folder(
        out or Path("exostab-results") / slug(system.name),
        OUTPUT_FILES["check"][:1] if no_plots else OUTPUT_FILES["check"],
    )
    if seconds is not None:
        with _analysis_errors(), console.status(f"Measuring integration speed for a {seconds:g} s budget…"):
            settings, p = settings_for_budget(system, seconds, settings)
        console.print(
            f"[dim]Budget {seconds:g} s: {settings.orbits:,.0f} orbits, {settings.draws} draws "
            f"(estimated {p.estimated_s:.0f} s).[/dim]"
        )
        if p.warning:
            console.print(f"[yellow]{p.warning}[/yellow]")
    from .indicators.spock import SpockUnavailableError

    status = Text(f"Integrating {system.name}: {settings.draws + 1} runs of {settings.orbits:.3g} orbits…")
    with _analysis_errors(), console.status(status):
        try:
            result = check_system(system, settings, command=_command())
        except SpockUnavailableError as exc:
            _print_error(exc)
            raise typer.Exit(1) from exc
    try:
        outputs = [write_json(result.report, out_dir / "report.json")]
        if not no_plots:
            from .plots import check_figures  # here, so that --no-plots needs no working matplotlib

            outputs += check_figures(result, out_dir)
    except OSError as exc:
        _print_error(f"Could not write the results: {exc}")
        raise typer.Exit(1) from exc
    render(result.report, console, outputs=outputs)
    old_figures = [f for f in OUTPUT_FILES["check"][1:] if no_plots and (out_dir / f).exists()]
    if old_figures:
        console.print(
            f"[yellow]{' and '.join(old_figures)} here are from an earlier run: --no-plots left them.[/yellow]"
        )
    console.print(f"[dim]Finished in {result.report.runtime_s:.1f} s.[/dim]")


def _named_planet(name: str | None, system: System) -> str:
    """The planet a sweep varies by default: the one the first argument names ("TRAPPIST-1 c"), otherwise b."""
    from .data.names import normalize

    if name is not None:
        for p in system.planets:
            if normalize(p.name) == normalize(name):
                return p.name
    return "b"


def _sweep_digits(values: list[float]) -> int:
    """Significant digits that tell the rows of a sweep table apart: at least 4, more for a narrow range."""
    largest = max(abs(v) for v in values)
    step = min((abs(b - a) for a, b in itertools.pairwise(values)), default=0.0)
    return max(4, math.ceil(math.log10(largest / step)) + 1) if step > 0 and largest > 0 else 4


@app.command(short_help="Vary one parameter of one planet.")
def sweep(
    name: Annotated[str | None, typer.Argument(help="Host or planet name.")] = None,
    planet: Annotated[
        str | None,
        typer.Option(
            "--planet",
            help="Planet letter or full name, e.g. 'b' \\[default: the planet named in the first argument, else b].",
        ),
    ] = None,
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
    steps: Annotated[
        int, typer.Option("--steps", help="Number of values.", min=2, max=MAX_STEPS_OR_DRAWS)
    ] = 25,
    from_file: FileOpt = None,
    orbits: OrbitsOpt = 1e4,
    seed: SeedOpt = 0,
    out: OutOpt = None,
    jobs: JobsOpt = None,
    refresh: RefreshOpt = False,
    offline: OfflineOpt = False,
) -> None:
    """Vary one parameter of one planet and record every indicator (nominal parameters otherwise)."""
    from .report import flags_table
    from .sweep import check_range, run_sweep, write_sweep

    _refuse_conflicting_sources(refresh, offline)
    if value_range is None:
        if param is not SweepParam.e:
            err_console.print(f"[red]--range is required with --param {param.value}.[/red]")
            raise typer.Exit(2)
        value_range = (0.0, 0.5)
    try:
        check_range(param.value, value_range)
    except ValueError as exc:
        _print_error(f"--range: {exc}.")
        raise typer.Exit(2) from exc
    system = _load(name, from_file, refresh, offline)
    try:
        target = system.planet(_named_planet(name, system) if planet is None else planet).name
    except KeyError as exc:
        _print_error(exc.args[0])
        raise typer.Exit(1) from exc
    out_dir = _output_folder(out or Path("exostab-results") / slug(system.name), OUTPUT_FILES["sweep"])
    with _analysis_errors(), console.status(Text(f"Sweeping {param.value} of {target} over {steps} values…")):
        rows = run_sweep(system, target, param.value, value_range, steps, orbits=orbits, seed=seed, jobs=jobs)
    try:
        paths = write_sweep(
            rows,
            system,
            target,
            param.value,
            out_dir,
            value_range=value_range,
            steps=steps,
            orbits=orbits,
            seed=seed,
            command=_command(),
        )
    except OSError as exc:
        _print_error(f"Could not write the results: {exc}")
        raise typer.Exit(1) from exc
    t = Table(title=escape(f"{system.name}: sweep of {param.value} for planet {target}"), header_style="bold")
    for col in ("value", "N-body", "<Y>", "Hill", "AMD"):
        t.add_column(col)
    digits = _sweep_digits([r["value"] for r in rows])
    for r in rows:
        # <Y> of a run stopped by a close encounter or escape is not meaningful
        show_megno = r["megno"] is not None and r["nbody_class"] != "unstable"
        t.add_row(
            f"{r['value']:.{digits}g}",
            r["nbody_class"],
            f"{r['megno']:.3g}" if show_megno else "—",
            r["hill_verdict"],
            r["amd_verdict"],
        )
    console.print(t)
    if system.flags:
        console.print(Text("Data completion (applied automatically):", style="bold dim"))
        console.print(flags_table(system))
    _saved(paths)


def _list_table(systems: list[Any], title: str, *, one_line: bool, discovery: bool) -> Table:
    """The table of ``exostab list``. Nothing is ever cut: a number that does not fit goes on over two lines, unless
    ``one_line``, and then only the discovery methods can wrap."""
    t = Table(header_style="bold", title=escape(title))
    for col, just in (
        ("System", "left"),
        ("Planets", "right"),
        ("Periods (d)", "right"),
        ("M* (M☉)", "right"),
        ("m sin i", "right"),
        ("est. mass", "right"),
        ("no e", "right"),
    ):
        t.add_column(col, justify=just, overflow="fold", no_wrap=one_line)  # type: ignore[arg-type]
    if discovery:
        t.add_column("Discovery", overflow="fold")
    for s in systems:
        periods = f"{s.min_period_days:.4g}–{s.max_period_days:.4g}" if s.min_period_days is not None else "—"
        t.add_row(
            Text(s.host),
            str(s.n_planets),
            periods,
            f"{s.star_mass_msun:.3g}" if s.star_mass_msun else "—",
            str(s.minimum_masses),
            str(s.estimated_masses),
            str(s.missing_eccentricities),
            *([Text(s.discovery_methods)] if discovery else []),
        )
    return t


@app.command("list", short_help="List multi-planet systems in the archive.")
def list_cmd(
    min_planets: Annotated[int, typer.Option("--min-planets", help="Minimum number of planets.", min=2)] = 2,
    max_period_days: Annotated[
        float | None,
        typer.Option(
            "--max-period-days",
            help="Only systems whose planets all have periods below this (days).",
            callback=_finite_number,
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

    _refuse_conflicting_sources(refresh, offline)
    try:
        rows, info = load_rows(refresh=refresh, offline=offline)
    except ArchiveError as exc:
        _print_error(exc)
        raise typer.Exit(1) from exc
    systems = list_systems(rows, min_planets=min_planets, max_period_days=max_period_days)
    shown = systems[:limit] if limit else systems
    title = f"{_plural(len(systems), 'system')} (data: {info.kind}, {(info.retrieved_utc or '')[:10]})"
    # Piped into grep or a file, the table should not be folded to fit an 80-column terminal that is not there.
    piped = not sys.stdout.isatty() and "COLUMNS" not in os.environ
    out = Console(emoji=False, width=LIST_WIDTH_WHEN_PIPED) if piped else console
    # What matters least goes first: the discovery methods get what the columns of numbers leave on one line.
    wide = out.options.update(max_width=LIST_WIDTH_WHEN_PIPED)
    natural = Measurement.get(out, wide, _list_table(shown, title, one_line=True, discovery=False)).maximum
    out.print(
        _list_table(
            shown,
            title,
            one_line=natural <= out.width,
            discovery=out.width - natural >= LIST_DISCOVERY_MIN_WIDTH,
        )
    )
    if info.note:
        console.print(f"[yellow]{escape(info.note)}[/yellow]")
    if limit and len(systems) > limit:
        console.print(f"[dim]… {len(systems) - limit} more; use --limit 0 to show all.[/dim]")


@catalog_app.command("build", short_help="Compute the catalog of multi-planet systems.")
def catalog_build(
    limit: Annotated[
        int, typer.Option("--limit", help="Process at most this many systems (0: all).", min=0)
    ] = 0,
    out: Annotated[Path, typer.Option("--out", help="Output folder.", parser=path)] = Path("catalog"),
    orbits: OrbitsOpt = 1e4,
    draws: Annotated[
        int,
        typer.Option(
            "--draws",
            help="Monte Carlo draws per system (with 0 no overall verdict is stable or unstable).",
            min=0,
            max=MAX_STEPS_OR_DRAWS,
        ),
    ] = 10,
    seed: Annotated[
        int,
        typer.Option(
            "--seed",
            help="Random seed: the same seed gives the same draws and, on the same platform and software "
            "versions, the same results.",
            min=0,
            max=MAX_CATALOG_SEED,
        ),
    ] = 0,
    max_seconds: Annotated[
        float,
        typer.Option(
            "--max-seconds",
            help="Wall-clock cap per system; systems that exceed it are recorded as 'timeout'.",
            min=1,
            callback=_finite_number,
        ),
    ] = 120.0,
    jobs: JobsOpt = None,
    refresh: RefreshOpt = False,
    offline: OfflineOpt = False,
) -> None:
    """Compute indicators for the multi-planet systems and write catalog.csv (+ catalog.parquet)."""
    from .catalog.build import CatalogSettings, build_catalog
    from .data.archive import ArchiveError

    _refuse_conflicting_sources(refresh, offline)
    _output_folder(out, OUTPUT_FILES["catalog"])
    settings = CatalogSettings(orbits=orbits, draws=draws, seed=seed, max_seconds=max_seconds, jobs=jobs)
    t0 = time.perf_counter()
    try:
        paths, rows = build_catalog(
            settings, out, limit=limit, refresh=refresh, offline=offline, console=console
        )
    except ArchiveError as exc:
        _print_error(exc)
        raise typer.Exit(1) from exc
    except OSError as exc:
        _print_error(f"Could not write the catalog: {exc}")
        raise typer.Exit(1) from exc
    counts: dict[str, int] = {}
    for r in rows:
        key = str(r["overall"] or r["status"])
        counts[key] = counts.get(key, 0) + 1
    console.print(
        f"{_plural(len(rows), 'system')} in {time.perf_counter() - t0:.0f} s: "
        + ", ".join(f"{k} {v}" for k, v in sorted(counts.items()))
    )
    _saved(paths)
    if counts.get("error"):
        console.print(
            f"[yellow]{_plural(counts['error'], 'system')} ended with an error: "
            "see the reason column of catalog.csv.[/yellow]"
        )
    # The weekly workflow stops before publishing on this exit status.
    if not any(r["status"] == "ok" for r in rows):
        _print_error("No system was computed, so this is not a catalog to use or publish.")
        raise typer.Exit(1)


if __name__ == "__main__":  # pragma: no cover
    app()
