"""Report JSON and schema, terminal card, plots, and the command-line interface."""

from __future__ import annotations

import csv
import json
import math
import os
import re
import signal
import subprocess
import sys
import time
import warnings
from concurrent.futures.process import BrokenProcessPool
from pathlib import Path

import pytest
from rich.console import Console
from typer.testing import CliRunner

from conftest import EXAMPLES, two_planet_system
from exostab import __version__
from exostab.analysis import CheckSettings, check_system
from exostab.cli import app, slug
from exostab.plots import check_figures
from exostab.report import SCHEMA_VERSION, Report, json_schema, render, write_json

runner = CliRunner()
FAST = ["--orbits", "300", "--draws", "2", "--jobs", "1"]
READING_GUIDE = Path(__file__).resolve().parents[1] / "docs" / "reading-a-report.md"


@pytest.fixture(scope="module")
def small_result():  # type: ignore[no-untyped-def]
    return check_system(two_planet_system(err=True), CheckSettings(orbits=300, draws=2, jobs=1, n_samples=10))


def test_report_json_roundtrip_and_provenance(small_result, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    path = write_json(small_result.report, tmp_path / "report.json")
    data = json.loads(path.read_text())
    assert data["schema_version"] == SCHEMA_VERSION
    for key in (
        "seed",
        "orbits",
        "draws",
        "integrator",
        "dt_yr",
        "t_end_yr",
        "energy_error_max",
        "megno_threshold",
    ):
        assert key in data["settings"]
    for key in ("exostab", "rebound", "numpy", "python"):
        assert data["software"][key]
    assert data["software"]["exostab"] == __version__
    assert [p["name"] for p in data["system"]["planets"]] == ["Test b", "Test c"]
    assert data["nominal"]["bodies"][1]["period_days"] == pytest.approx(250.0)
    back = Report.model_validate(data)
    assert back.overall.verdict == small_result.report.overall.verdict


def test_non_finite_numbers_in_json(small_result) -> None:  # type: ignore[no-untyped-def]
    # an infinite AMD β (resonances overlap even on circular orbits) is the most unstable case: it must not
    # be written as null, which reads as "no value"
    rep = small_result.report.model_copy(deep=True)
    details = rep.indicators["amd"].details
    details["pairs"][0]["beta"] = math.inf
    details["test_values"] = [-math.inf, math.nan, 1.5]
    text = rep.to_json()  # valid JSON: allow_nan=False would raise otherwise
    data = json.loads(text)
    assert data["indicators"]["amd"]["details"]["pairs"][0]["beta"] == "inf"
    assert data["indicators"]["amd"]["details"]["test_values"] == ["-inf", None, 1.5]
    assert float(data["indicators"]["amd"]["details"]["pairs"][0]["beta"]) == math.inf
    Report.model_validate(data)


def test_infinite_amd_beta_in_report_json() -> None:
    # Two 10 Earth-mass planets with a period ratio of 1.1: inside the domain of Petit et al. (2017), and their
    # resonances overlap even on circular orbits, so β is infinite. (GJ 876 no longer serves: its pairs lie
    # outside that domain, β uses the collision criterion and is finite; no snapshot system has an infinite β.)
    res = check_system(
        two_planet_system(period_ratio=1.1), CheckSettings(orbits=50, draws=0, jobs=1, ias15_check=False)
    )
    pairs = json.loads(res.report.to_json())["indicators"]["amd"]["details"]["pairs"]
    betas = [p["beta"] for p in pairs]
    assert "inf" in betas and None not in betas
    assert all(p["circular_overlap"] and p["outside_domain"] is None for p in pairs if p["beta"] == "inf")


def test_shipped_schema_is_up_to_date() -> None:
    shipped = Path(__file__).resolve().parents[1] / "src" / "exostab" / "schemas" / "report.schema.json"
    assert json.loads(shipped.read_text()) == json_schema(), "regenerate with `python -m exostab.report`"


def test_render_card(small_result) -> None:  # type: ignore[no-untyped-def]
    console = Console(record=True, width=100)
    render(small_result.report, console, outputs=[Path("x/report.json")])
    text = console.export_text()
    for s in ("Hill spacing", "AMD", "N-body + MEGNO", "Overall:", "Saved: x/report.json"):
        assert s in text


def test_flags_are_grouped_in_the_card() -> None:
    from exostab.data import load_system
    from exostab.report import group_flags

    res = check_system(
        load_system("TRAPPIST-1"), CheckSettings(orbits=50, draws=0, jobs=1, ias15_check=False)
    )
    groups = group_flags(res.report)
    transit = [who for who, msg in groups if "transit mid-time" in msg]
    assert transit == ["b, c, d, e, f, g, h"]
    console = Console(record=True, width=120)
    render(res.report, console)
    assert "Data completion" in console.export_text()


@pytest.mark.skipif(not READING_GUIDE.is_file(), reason="this page is not in the sdist")
def test_reading_guide_quotes_a_real_card() -> None:
    # docs/reading-a-report.md walks through the card of `exostab check "TRAPPIST-1" --offline`. Its title
    # must name this version or a released one, and the excerpts that take it apart must repeat its lines. A
    # short run without draws prints every line that does not depend on the integration, so those can be
    # compared without the long run. If this fails, print the card again with the command on that page and
    # re-read the text around it.
    from exostab.data import load_system

    def plain(text: str) -> str:
        return " ".join(re.sub("[│╭╮╰╯─]", " ", text).split())

    page = READING_GUIDE.read_text(encoding="utf-8")
    changelog = (READING_GUIDE.parents[1] / "CHANGELOG.md").read_text(encoding="utf-8")
    released = re.findall(r"^## \[(.+)\] - \d{4}-\d{2}-\d{2}$", changelog, re.MULTILINE)
    quoted = set(re.findall(r"exostab (\S+) — stability report card", page))
    assert quoted and quoted <= {__version__, *released}

    # The first text fence is the card. The table of Kepler-292 is another system.
    fences = re.findall(r"^```text\n(.*?)^```$", page.split("## Common cases")[0], re.MULTILINE | re.DOTALL)
    excerpts = [line for fence in fences[1:] if "Kepler-292" not in fence for line in fence.splitlines()]
    assert [line for line in excerpts if line not in fences[0].splitlines()] == []

    res = check_system(
        load_system("TRAPPIST-1", offline=True), CheckSettings(orbits=50, draws=0, jobs=1, ias15_check=False)
    )
    console = Console(record=True, width=100)
    render(res.report, console)
    card = console.export_text().splitlines()
    n_body = next(i for i, line in enumerate(card) if "N-body + MEGNO" in line)
    completion = next(i for i, line in enumerate(card) if "Data completion" in line)
    fixed = [line for line in card[1:n_body] + card[completion:] if not re.search("MARGINAL|STABLE", line)]
    assert [line for line in map(plain, fixed) if line not in plain(fences[0])] == []


def test_figures(small_result, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    paths = check_figures(small_result, tmp_path)
    assert [p.name for p in paths] == ["orbits.png", "megno.png"]
    assert all(p.stat().st_size > 10_000 for p in paths)


def write_system(tmp_path: Path, system: str = "T", b: str = "T b", c: str = "T c") -> Path:
    path = tmp_path / "system.yaml"
    path.write_text(
        f"name: {json.dumps(system)}\nstar: {{mass_msun: 1.0}}\nplanets:\n"
        f"  - {{name: {json.dumps(b)}, period_days: 10, mass_earth: 5}}\n"
        f"  - {{name: {json.dumps(c)}, period_days: 30, mass_earth: 8}}\n",
        encoding="utf-8",
    )
    return path


@pytest.mark.parametrize(
    ("system", "b"),
    [("a$b", "x$y"), ("$a_b$", "$x^$"), ("a$", "$$"), ("T", "_b"), ("_T", "__"), ("Τ€x", "日本語 b")],
)
def test_figures_take_any_name(tmp_path: Path, system: str, b: str) -> None:
    # "$" is mathtext to matplotlib: ParseSyntaxException after the whole integration, and no card. A label with a
    # leading underscore left the legend out, and letters the font lacks gave one warning each.
    import matplotlib.pyplot as plt

    from exostab.data import load_system_file
    from exostab.plots import orbits_figure, sweep_figure

    s = load_system_file(write_system(tmp_path, system, b))
    res = check_system(s, CheckSettings(orbits=100, draws=0, jobs=1, n_samples=5, ias15_check=False))
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        assert all(p.stat().st_size > 10_000 for p in check_figures(res, tmp_path))
        rows = [
            {
                "value": 0.1,
                "nbody_class": "regular",
                "megno": 2.0,
                "hill_margin_min": 0.1,
                "amd_beta_max": 0.5,
            }
        ]
        assert sweep_figure(rows, f"e of {b}", f"{system}: sweep", tmp_path / "s.png").exists()
    figures: list[object] = []
    keep = plt.close
    plt.close = figures.append  # type: ignore[assignment]
    try:
        orbits_figure(res.realizations[0], res.runs[0], system, tmp_path / "o.png")
    finally:
        plt.close = keep  # type: ignore[assignment]
    legend = figures[0].axes[0].get_legend()  # type: ignore[attr-defined]
    shown = [t.get_text().strip().replace(r"\$", "$") for t in legend.get_texts()]
    keep(figures[0])  # type: ignore[arg-type]
    assert shown == [b, "T c"]


def test_sweep_figure_shows_infinite_and_zero_beta(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import matplotlib.pyplot as plt
    import numpy as np

    from exostab.plots import sweep_figure

    # β = ∞ (resonance overlap on circular orbits, the most AMD-unstable case) and β = 0 (circular, coplanar
    # orbits) cannot be drawn on a log axis; they must still appear, at the edges, not leave a gap
    betas = (math.inf, math.inf, 2.0, 0.5, 0.0)
    rows = [
        {
            "value": 10.0 * (k + 1),
            "nbody_class": "regular",
            "megno": 2.0,
            "hill_margin_min": 0.1,
            "amd_beta_max": b,
        }
        for k, b in enumerate(betas)
    ]
    figures: list[object] = []
    monkeypatch.setattr(plt, "close", figures.append)
    sweep_figure(rows, "x", "title", tmp_path / "sweep.png")
    monkeypatch.undo()
    ax = figures[0].axes[2]  # type: ignore[attr-defined]
    lo, hi = ax.get_ylim()
    drawn: dict[float, float] = {}
    for line in ax.lines[:-1]:  # the last line is the β = 1 reference
        drawn.update(
            (float(x), float(y)) for x, y in zip(line.get_xdata(), line.get_ydata()) if np.isfinite(y)
        )
    for coll in ax.collections:
        drawn.update((float(x), float(y)) for x, y in coll.get_offsets())
    plt.close(figures[0])  # type: ignore[arg-type]
    assert sorted(drawn) == [10.0, 20.0, 30.0, 40.0, 50.0]
    assert all(lo <= y <= hi for y in drawn.values())
    assert drawn[10.0] == drawn[20.0] == pytest.approx(hi) and drawn[50.0] == pytest.approx(lo)
    assert drawn[30.0] == 2.0 and drawn[40.0] == 0.5
    assert any("β = ∞" in t.get_text() for t in ax.get_legend().get_texts())


# ------------------------------------------------------------------------------------------ CLI


def plain(output: str) -> str:
    """CLI output without ANSI styling (Typer forces colour when GITHUB_ACTIONS, FORCE_COLOR or PY_COLORS is set)."""
    return re.sub(r"\x1b\[[0-9;]*m", "", output)


def test_version_and_help() -> None:
    r = runner.invoke(app, ["--version"])
    assert r.exit_code == 0 and __version__ in r.output
    r = runner.invoke(app, ["--help"])
    assert r.exit_code == 0 and "check" in r.output and "catalog" in r.output
    # pip users have no streamlit_app.py: the help points to the packaged launcher, and to the install commands
    # for its extra (from GitHub: there is no exostab on PyPI)
    help_text = " ".join(plain(r.output).split())
    assert (
        "python -m exostab.web (needs the [web] extra: https://mimitoz62.github.io/exostab/quickstart/)"
        in help_text
    )


def test_spock_message_points_to_the_environment_script(monkeypatch: pytest.MonkeyPatch) -> None:
    # scripts/make_spock_env.sh is not installed with the package, so the message gives its URL
    monkeypatch.delenv("EXOSTAB_SPOCK_PYTHON", raising=False)
    r = runner.invoke(app, ["check", "Kepler-36", "--spock"])
    assert r.exit_code == 2
    assert "https://raw.githubusercontent.com/mimitoz62/exostab/main/scripts/make_spock_env.sh" in "".join(
        plain(r.output).split()
    )


def test_check_help_shows_the_run_length_defaults() -> None:
    # the defaults are written into the help text by hand (the options default to None so that --budget can
    # be detected); Rich must not swallow them as markup tags
    r = runner.invoke(app, ["check", "--help"], env={"COLUMNS": "200"})
    assert r.exit_code == 0
    text = " ".join(r.output.split())
    assert "innermost planet [default: 10000]." in text
    assert "published uncertainties [default: 20]." in text
    cli_md = (Path(__file__).resolve().parents[1] / "docs" / "cli.md").read_text()
    assert "innermost planet [default: 10000]." in cli_md and "uncertainties [default: 20]." in cli_md


def test_check_from_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    out = tmp_path / "out"
    args = ["check", "--from-file", str(EXAMPLES / "two_planet.yaml"), *FAST, "--out", str(out)]
    monkeypatch.setattr("sys.argv", ["exostab", *args])
    r = runner.invoke(app, args)
    assert r.exit_code == 0, r.output
    assert {p.name for p in out.iterdir()} == {"report.json", "orbits.png", "megno.png"}
    data = json.loads((out / "report.json").read_text())
    assert data["data"]["source"] == "file" and data["settings"]["seed"] == 0
    assert "--from-file" in data["command"]


def test_check_by_name_offline(tmp_path: Path) -> None:
    out = tmp_path / "hd"
    r = runner.invoke(
        app, ["check", "HD 127195", *FAST, "--seed", "7", "--no-plots", "--no-ias15", "--out", str(out)]
    )
    assert r.exit_code == 0, r.output
    data = json.loads((out / "report.json").read_text())
    assert data["data"]["archive_rows"] == ["HD 127195 b", "HD 127195 c"]
    assert data["data"]["table"] == "pscomppars" and data["data"]["acknowledgment"]
    assert data["settings"]["seed"] == 7 and data["settings"]["check_integrator"] is None
    assert not (out / "orbits.png").exists()


def test_check_inclination_prior(tmp_path: Path) -> None:
    r = runner.invoke(
        app,
        [
            "check",
            "HD 127195",
            *FAST,
            "--no-plots",
            "--inclination-prior",
            "isotropic",
            "--out",
            str(tmp_path),
        ],
    )
    assert r.exit_code == 0, r.output
    assert json.loads((tmp_path / "report.json").read_text())["settings"]["inclination_prior"] == "isotropic"


def test_default_output_folder(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    r = runner.invoke(app, ["check", "Kepler-36", *FAST, "--no-plots"])
    assert r.exit_code == 0, r.output
    assert (tmp_path / "exostab-results" / "kepler-36" / "report.json").exists()
    assert slug("HD 127195") == "hd-127195" and slug("!!") == "system"


@pytest.mark.parametrize(
    ("args", "message"),
    [
        (["check"], "either a system name or --from-file"),
        (["check", "TRAPIST-1"], "Did you mean"),
        (["check", "Kepler-47"], "circumbinary"),
        (["check", "[/red]"], "'[/red]'"),  # text, not markup: it used to crash with a traceback
    ],
)
def test_check_errors(args: list[str], message: str) -> None:
    r = runner.invoke(app, args)
    assert r.exit_code != 0
    assert message in r.output


@pytest.mark.parametrize(
    "command",
    [
        ["check", "--from-file", str(EXAMPLES / "two_planet.yaml"), *FAST, "--no-plots"],
        ["sweep", "--from-file", str(EXAMPLES / "two_planet.yaml"), "--steps", "2", "--orbits", "100"],
        ["catalog", "build", "--limit", "1", "--orbits", "100", "--draws", "0"],
    ],
)
def test_negative_seed_is_rejected(command: list[str], tmp_path: Path) -> None:
    # numpy's SeedSequence rejects negative seeds: refuse them up front instead of crashing (check, sweep) or
    # recording every catalog system as an error
    r = runner.invoke(app, [*command, "--seed", "-1", "--out", str(tmp_path)])
    assert r.exit_code == 2, r.output
    assert "--seed" in plain(r.output) and not list(tmp_path.iterdir())


def test_list_command() -> None:
    r = runner.invoke(app, ["list", "--min-planets", "4", "--max-period-days", "200"])
    assert r.exit_code == 0, r.output
    assert "TRAPPIST-1" in r.output and "HD 127195" not in r.output
    r = runner.invoke(app, ["list", "--limit", "2"])
    assert r.exit_code == 0 and "more; use --limit 0" in r.output


def test_sweep_command(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    args = [
        "sweep",
        "--from-file",
        str(EXAMPLES / "hd127195_note.yaml"),
        "--planet",
        "b",
        "--param",
        "e",
        "--range",
        "0",
        "0.6",
        "--steps",
        "4",
        "--orbits",
        "200",
        "--seed",
        "3",
        "--jobs",
        "1",
        "--out",
        str(tmp_path),
    ]
    monkeypatch.setattr("sys.argv", ["exostab", *args])
    r = runner.invoke(app, args)
    assert r.exit_code == 0, r.output
    rows = list(csv.DictReader((tmp_path / "sweep.csv").open()))
    assert [float(x["value"]) for x in rows] == pytest.approx([0.0, 0.2, 0.4, 0.6])
    assert rows[-1]["hill_verdict"] == "unstable" and rows[0]["amd_verdict"] == "stable"
    assert (tmp_path / "sweep.png").exists() and (tmp_path / "sweep.json").exists()
    # sweep.json records what is needed to repeat the sweep: the seed changes the N-body classifications
    meta = json.loads((tmp_path / "sweep.json").read_text())
    assert meta["settings"] == {
        "value_range": [0.0, 0.6],
        "steps": 4,
        "orbits": 200.0,
        "seed": 3,
        "integrator": "whfast",
        "dt_fraction": pytest.approx(1 / 30),
    }
    assert meta["command"].startswith("exostab sweep --from-file") and "--seed 3" in meta["command"]
    assert meta["created_utc"] and meta["parameter"] == "e"
    r = runner.invoke(app, ["sweep", "HD 127195", "--planet", "z", "--steps", "2"])
    assert r.exit_code == 1 and "no planet" in r.output


@pytest.mark.parametrize(
    ("param", "rng"), [("mass", ("100", "300")), ("period", ("500", "520")), ("omega", ("0", "90"))]
)
def test_sweep_other_parameters(tmp_path: Path, param: str, rng: tuple[str, str]) -> None:
    r = runner.invoke(
        app,
        [
            "sweep",
            "HD 127195",
            "--planet",
            "c",
            "--param",
            param,
            "--range",
            *rng,
            "--steps",
            "2",
            "--orbits",
            "100",
            "--jobs",
            "1",
            "--out",
            str(tmp_path),
        ],
    )
    assert r.exit_code == 0, r.output


@pytest.mark.parametrize(
    ("args", "message"),
    [
        (["--param", "mass"], "--range is required"),  # the e default (0 0.5) is not a valid mass or period
        (["--param", "period"], "--range is required"),
        (["--param", "omega"], "--range is required"),
        (["--param", "e", "--range", "0", "1"], "eccentricity must be in [0, 0.95]"),
        (["--param", "e", "--range", "0.9", "0.99"], "eccentricity must be in [0, 0.95]"),  # above E_MAX
        (["--param", "mass", "--range", "0", "10"], "mass must be positive"),
        (["--param", "omega", "--range", "0", "nan"], "must be a finite number"),
    ],
)
def test_sweep_rejects_invalid_ranges(args: list[str], message: str, tmp_path: Path) -> None:
    r = runner.invoke(
        app,
        [
            "sweep",
            "HD 127195",
            "--planet",
            "c",
            *args,
            "--steps",
            "2",
            "--orbits",
            "100",
            "--out",
            str(tmp_path),
        ],
    )
    assert r.exit_code == 2, r.output
    assert message in " ".join(r.output.split()) and not list(tmp_path.iterdir())


def test_sweep_rejects_invalid_values() -> None:
    from exostab.sampling import E_MAX, realizations
    from exostab.sweep import _modified, check_value, run_sweep

    nom = realizations(two_planet_system(), 0, seed=0)[0]
    for param, value, match in (
        ("e", 1.2, "eccentricity"),
        ("mass", -1.0, "mass"),
        ("period", 0.0, "period"),
        ("omega", math.inf, "finite"),
        ("bogus", 1.0, "unknown"),
    ):
        with pytest.raises(ValueError, match=match):
            _modified(nom, 0, param, value)
    # the ends of the range are checked before anything is integrated
    with pytest.raises(ValueError, match="eccentricity"):
        run_sweep(two_planet_system(), "b", "e", (0.0, 1.0), 3, orbits=1e9)
    # the sweep uses the same eccentricity cap as check: E_MAX itself is allowed, anything above it is not
    check_value("e", E_MAX)
    with pytest.raises(ValueError, match=r"\[0, 0\.95\]"):
        check_value("e", 0.96)


def test_catalog_build(tmp_path: Path) -> None:
    r = runner.invoke(
        app,
        [
            "catalog",
            "build",
            "--limit",
            "3",
            "--orbits",
            "100",
            "--draws",
            "1",
            "--jobs",
            "2",
            "--out",
            str(tmp_path),
        ],
    )
    assert r.exit_code == 0, r.output
    rows = list(csv.DictReader((tmp_path / "catalog.csv").open()))
    assert len(rows) == 3
    assert {row["status"] for row in rows} <= {"ok", "skipped"}
    ok = [row for row in rows if row["status"] == "ok"]
    assert ok and all(row["overall"] in ("stable", "marginal", "unstable", "inconclusive") for row in ok)
    assert (tmp_path / "catalog.parquet").exists()
    meta = json.loads((tmp_path / "catalog_meta.json").read_text())
    assert meta["n_systems"] == 3 and meta["settings"]["draws"] == 1


def _no_integration(monkeypatch: pytest.MonkeyPatch) -> None:
    """Fail a test, instead of letting it wait for an endless run, if anything is integrated."""

    def integrate(*args: object, **kwargs: object) -> None:
        raise AssertionError("the run should have been refused before any integration")

    monkeypatch.setattr("exostab.indicators.megno.run_many", integrate)
    monkeypatch.setattr("exostab.sweep.run_many", integrate)


@pytest.mark.parametrize(
    "args",
    [
        ["check", "Kepler-36", "--orbits", "nan"],
        ["check", "Kepler-36", "--orbits", "inf"],
        ["sweep", "Kepler-36", "--orbits", "inf"],
        ["sweep", "Kepler-36", "--orbits", "nan"],
        ["list", "--max-period-days", "nan"],
        ["list", "--max-period-days", "inf"],
        ["catalog", "build", "--limit", "1", "--max-seconds", "1", "--orbits", "nan"],
        ["catalog", "build", "--limit", "1", "--orbits", "100", "--draws", "0", "--max-seconds", "nan"],
        ["catalog", "build", "--limit", "1", "--orbits", "100", "--draws", "0", "--max-seconds", "inf"],
    ],
)
def test_non_finite_options_are_refused(
    args: list[str], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Their minimums let NaN through: runs that never ended, a filter that stopped filtering, a cap that was no cap.
    _no_integration(monkeypatch)
    r = runner.invoke(app, [*args, *([] if args[0] == "list" else ["--out", str(tmp_path / "o")])])
    assert r.exit_code == 2, r.output
    assert "must be a finite number" in " ".join(plain(r.output).split())


@pytest.mark.parametrize(
    "args",
    [
        ["check", "Kepler-36", "--orbits", "100", "--draws", str(10**20)],
        ["catalog", "build", "--limit", "1", "--orbits", "100", "--draws", str(10**20)],
        ["sweep", "Kepler-36", "--orbits", "100", "--steps", str(10**13)],
    ],
)
def test_impossible_run_sizes_are_refused(args: list[str], tmp_path: Path) -> None:
    # MemoryError and OverflowError, as tracebacks
    r = runner.invoke(app, [*args, "--out", str(tmp_path / "o")])
    assert r.exit_code == 2, r.output


@pytest.mark.parametrize(
    ("param", "rng"),
    [
        ("mass", ("1e200", "1e201")),
        ("omega", ("-1e308", "1e308")),
        ("period", ("1", "1e13")),
        ("period", ("1e-4", "1")),
    ],
)
def test_sweep_refuses_absurd_ranges(param: str, rng: tuple[str, str], tmp_path: Path) -> None:
    r = runner.invoke(
        app,
        [
            "sweep",
            "Kepler-36",
            "--param",
            param,
            "--range",
            *rng,
            "--steps",
            "3",
            "--out",
            str(tmp_path / "o"),
        ],
    )
    assert r.exit_code == 2, r.output
    assert r.output.count("Traceback") == 0 and "--range:" in r.output
    assert not (tmp_path / "o").exists()


def test_sweep_refuses_a_mass_above_the_star(tmp_path: Path) -> None:
    r = runner.invoke(
        app,
        [
            "sweep",
            "Kepler-36",
            "--param",
            "mass",
            "--range",
            "1",
            "1e7",
            "--steps",
            "2",
            "--out",
            str(tmp_path),
        ],
    )
    assert r.exit_code == 1 and "not below the stellar mass" in " ".join(r.output.split())


def _blocked_outputs(tmp_path: Path) -> list[list[str]]:
    a_file = tmp_path / "a-file"
    a_file.write_text("x")
    full = tmp_path / "with-a-directory"
    (full / "report.json").mkdir(parents=True)
    figures = tmp_path / "figures"
    (figures / "orbits.png").mkdir(parents=True)
    sweep_dir = tmp_path / "sweep-dir"
    (sweep_dir / "sweep.csv").mkdir(parents=True)
    catalog_dir = tmp_path / "catalog-dir"
    (catalog_dir / "catalog.csv").mkdir(parents=True)
    check = ["check", "Kepler-36", "--orbits", "100", "--draws", "0", "--jobs", "1"]
    sweep = ["sweep", "Kepler-36", "--orbits", "100", "--steps", "2", "--jobs", "1"]
    catalog = ["catalog", "build", "--limit", "1", "--orbits", "100", "--draws", "0", "--jobs", "1"]
    return [
        [*check, "--no-plots", "--out", str(a_file)],
        [*check, "--no-plots", "--out", str(a_file / "below")],
        [*check, "--no-plots", "--out", str(full)],
        [*check, "--out", str(figures)],
        [*sweep, "--out", str(a_file)],
        [*sweep, "--out", str(sweep_dir)],
        [*catalog, "--out", str(a_file)],
        [*catalog, "--out", str(catalog_dir)],
    ]


def test_an_output_folder_that_cannot_be_written_is_refused_first(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Tracebacks after the whole run: TRAPPIST-1 at 20,000 orbits ran for 14 s before failing, and nothing was saved.
    _no_integration(monkeypatch)
    for args in _blocked_outputs(tmp_path):
        r = runner.invoke(app, args)
        assert r.exit_code == 2, (args, r.output, r.exception)
        assert "Cannot write" in r.output and "--out" in r.output


def test_a_read_only_output_folder_is_refused_first(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    if os.geteuid() == 0:
        pytest.skip("root can write everywhere")
    _no_integration(monkeypatch)
    tmp_path.chmod(0o500)
    try:
        r = runner.invoke(app, ["check", "Kepler-36", "--no-plots", "--out", str(tmp_path / "o")])
    finally:
        tmp_path.chmod(0o700)
    assert r.exit_code == 2 and "Cannot write" in r.output


def test_a_write_that_fails_at_the_end_names_the_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def full_disk(report: object, path: Path) -> Path:
        raise OSError(28, "No space left on device", str(path))

    monkeypatch.setattr("exostab.report.write_json", full_disk)
    r = runner.invoke(app, ["check", "Kepler-36", *FAST, "--no-plots", "--out", str(tmp_path)])
    assert r.exit_code == 1 and r.exception is not None and isinstance(r.exception, SystemExit)
    text = " ".join(plain(r.output).split())
    assert "Could not write the results" in text and "No space left" in text


def test_an_empty_output_folder_is_refused(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # An unset shell variable in --out "$DIR" wrote into the current folder.
    monkeypatch.chdir(tmp_path)
    for args in (
        ["check", "Kepler-36", *FAST, "--no-plots"],
        ["sweep", "Kepler-36", "--orbits", "100", "--steps", "2", "--jobs", "1"],
        ["catalog", "build", "--limit", "1", "--orbits", "100", "--draws", "0"],
    ):
        r = runner.invoke(app, [*args, "--out", ""], env={"COLUMNS": "200"})
        assert r.exit_code == 2, r.output
        assert "the output folder is empty" in " ".join(plain(r.output).split())
    assert list(tmp_path.iterdir()) == []


def test_slug_is_safe_for_long_and_non_latin_names() -> None:
    # A 300-character name failed with "File name too long" after the run.
    long = slug("x" * 300)
    assert len(long.encode()) <= 110 and long.startswith("x" * 90)
    assert slug("x" * 300) != slug("x" * 299 + "y")
    assert len(slug("日本語" * 100).encode()) <= 110
    # Non-ASCII names became the same folder, and the second report replaced the first.
    assert slug("日本語") != slug("ταυ κήτου") != "system"
    assert slug("Κέπλερ-11_b") == "κέπλερ-11-b"
    assert slug("HD 127195") == "hd-127195" and slug("!!") == "system"


def test_a_long_name_runs_to_the_end(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    file = write_system(tmp_path, "x" * 300)
    r = runner.invoke(app, ["check", "--from-file", str(file), *FAST, "--no-plots", "--no-ias15"])
    assert r.exit_code == 0, r.output
    assert list((tmp_path / "exostab-results").glob("*/report.json"))


def test_old_figures_are_mentioned(tmp_path: Path) -> None:
    # check --no-plots left the earlier figures next to the new report.json without a word.
    args = ["check", "Kepler-36", *FAST, "--out", str(tmp_path)]
    r = runner.invoke(app, [*args, "--no-plots"])
    assert r.exit_code == 0 and "earlier run" not in r.output
    (tmp_path / "orbits.png").write_text("old")
    r = runner.invoke(app, [*args, "--no-plots"])
    assert r.exit_code == 0 and "orbits.png here are from an earlier run" in " ".join(r.output.split())


@pytest.mark.parametrize(
    "args",
    [
        ["check", "Kepler-36", "--orbits", "100", "--draws", "0", "--no-plots"],
        ["sweep", "Kepler-36", "--orbits", "100", "--steps", "2"],
        ["list"],
        ["catalog", "build", "--limit", "1", "--orbits", "100", "--draws", "0"],
    ],
)
def test_offline_and_refresh_exclude_each_other(args: list[str], tmp_path: Path) -> None:
    # --refresh, which promises to fail loudly if it cannot get fresh data, was ignored without a word.
    out = [] if args[0] == "list" else ["--out", str(tmp_path / "o")]
    r = runner.invoke(app, [*args, "--offline", "--refresh", *out])
    assert r.exit_code == 2, r.output
    assert "give one" in " ".join(r.output.split())


def test_offline_variable_with_refresh_is_mentioned() -> None:
    r = runner.invoke(app, ["list", "--refresh", "--limit", "1"])  # conftest sets EXOSTAB_OFFLINE=1
    assert r.exit_code == 0 and "--refresh is ignored" in " ".join(r.output.split())


def test_catalog_build_fails_when_nothing_was_computed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # The weekly workflow stops before publishing on this exit status, and it was 0 for all of these.
    from exostab.catalog import build

    base = {**dict.fromkeys(build.COLUMNS), "n_planets": 2, "overall": None}

    def fake(status: str, n: int) -> object:
        return lambda *a, **k: (
            [tmp_path / "x"],
            [{**base, "system": f"S{i}", "status": status} for i in range(n)],
        )

    for status, n in (("timeout", 3), ("error", 2), ("skipped", 1), ("ok", 0)):
        monkeypatch.setattr(build, "build_catalog", fake(status, n))
        r = runner.invoke(app, ["catalog", "build", "--out", str(tmp_path / "o")])
        assert r.exit_code == 1, (status, r.output)
        assert "No system was computed" in r.output
    # one bad system among others does not stop the weekly catalog; it is counted
    rows = [
        {**base, "system": "A", "status": "ok", "overall": "stable"},
        {**base, "system": "B", "status": "error"},
    ]
    monkeypatch.setattr(build, "build_catalog", lambda *a, **k: ([tmp_path / "x"], rows))
    r = runner.invoke(app, ["catalog", "build", "--out", str(tmp_path / "o")])
    assert r.exit_code == 0 and "1 system ended with an error" in " ".join(r.output.split())


def test_catalog_build_reports_an_outage(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from exostab.data import archive, store

    # --refresh: 40 kB of traceback, where `list --refresh` prints one line
    def outage(where: str) -> None:
        raise archive.ArchiveError("could not query the NASA Exoplanet Archive: simulated")

    monkeypatch.delenv("EXOSTAB_OFFLINE")
    monkeypatch.setattr(store, "fetch_rows", outage)
    args = ["catalog", "build", "--limit", "1", "--orbits", "100", "--draws", "0", "--out", str(tmp_path)]
    r = runner.invoke(app, [*args, "--refresh"])
    assert r.exit_code == 1 and isinstance(r.exception, SystemExit)
    assert "could not query" in " ".join(r.output.split()) and "Traceback" not in r.output
    # without it: a silent catalog of the snapshot, whose metadata did not say why
    r = runner.invoke(app, args)
    assert r.exit_code == 0, r.output
    assert "simulated" in " ".join(r.output.split())
    meta = json.loads((tmp_path / "catalog_meta.json").read_text())
    assert meta["data_source"] == "snapshot" and "simulated" in meta["data_note"]


def test_catalog_seed_is_limited_to_what_parquet_stores(tmp_path: Path) -> None:
    # OverflowError from pyarrow after every system had run, with no meta file. The same seed works in check.
    small = ["--limit", "1", "--orbits", "100", "--draws", "0", "--jobs", "1"]
    r = runner.invoke(app, ["catalog", "build", *small, "--seed", str(2**63), "--out", str(tmp_path / "c")])
    assert r.exit_code == 2 and not (tmp_path / "c").exists()
    r = runner.invoke(
        app, ["check", "Kepler-36", *FAST, "--seed", str(2**63), "--no-plots", "--out", str(tmp_path)]
    )
    assert r.exit_code == 0, r.output


@pytest.mark.parametrize("folder", ["results[test]", "res[/dim]x", "x:fire:y", "cat[/x]"])
@pytest.mark.parametrize(
    "command",
    [
        ["sweep", "Kepler-36", "--orbits", "100", "--steps", "2", "--jobs", "1"],
        ["catalog", "build", "--limit", "1", "--orbits", "100", "--draws", "0", "--jobs", "1"],
    ],
)
def test_paths_are_text_not_markup(command: list[str], folder: str, tmp_path: Path) -> None:
    # results[test] printed "Saved: results/sweep.csv" while the files were in results[test]/, x:fire:y an emoji, and
    # [/dim] a MarkupError after the work was done.
    r = runner.invoke(app, [*command, "--out", str(tmp_path / folder)])
    assert r.exit_code == 0, r.output
    assert f"{folder}/" in "".join(plain(r.output).split())


@pytest.mark.parametrize(
    ("system", "b"),
    [
        ("foo[/red]", "T b"),
        ("T", "Plain [/x]"),
        ("K-1 [b]", "K-1 [b] b"),
        ("HD 1 [best fit]", "HD 1 c"),
        ("x:fire:y", "x:fire:y b"),
    ],
)
def test_names_are_text_not_markup(system: str, b: str, tmp_path: Path) -> None:
    # A MarkupError before the run or after it, which left report.json and no card; "K-1 [b]" printed as "K-1".
    file = write_system(tmp_path, system, b)
    out = ["--out", str(tmp_path / "o")]
    r = runner.invoke(app, ["check", "--from-file", str(file), *FAST, "--no-plots", *out])
    assert r.exit_code == 0, r.output
    text = plain(r.output)
    assert system in text and b in text
    r = runner.invoke(
        app,
        [
            "sweep",
            "--from-file",
            str(file),
            "--planet",
            b,
            "--steps",
            "2",
            "--orbits",
            "100",
            "--jobs",
            "1",
            *out,
        ],
    )
    assert r.exit_code == 0, r.output
    assert b in plain(r.output)


def test_a_note_is_text_not_markup(monkeypatch: pytest.MonkeyPatch) -> None:
    from exostab.data import archive, store

    def outage(where: str) -> None:
        raise archive.ArchiveError("HTTP 503 [/TAP/sync] service down")

    monkeypatch.delenv("EXOSTAB_OFFLINE")
    monkeypatch.setattr(store, "fetch_rows", outage)
    r = runner.invoke(app, ["list", "--limit", "1"])
    assert r.exit_code == 0, r.output
    assert "[/TAP/sync]" in r.output


def _exostab(*args: str, **env: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "exostab", *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=120,
        check=False,
        env={**os.environ, **env},
    )


@pytest.mark.parametrize(
    "args",
    [
        ("--help",),
        ("check", "--help"),
        ("list", "--offline", "--limit", "1"),
        ("sweep", "Kepler-36", "--offline", "--orbits", "100", "--steps", "2", "--jobs", "1"),
        ("check", "Kepler-36", "--offline", "--orbits", "100", "--draws", "0", "--no-plots", "--no-ias15"),
    ],
)
@pytest.mark.parametrize("encoding", ["ascii", "latin-1"])
def test_output_that_cannot_be_encoded_is_replaced(
    args: tuple[str, ...], encoding: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # UnicodeEncodeError for "⊕" and "☉", also after the integration: a Windows user redirecting output, for example.
    monkeypatch.chdir(tmp_path)
    r = _exostab(*args, PYTHONIOENCODING=encoding)
    assert r.returncode == 0, r.stderr
    assert "Traceback" not in r.stderr


def test_python_m_exostab() -> None:
    r = _exostab("--version")
    assert r.returncode == 0 and __version__ in r.stdout
    assert "Usage: exostab" in " ".join(_exostab("--help").stdout.split())


def test_a_broken_mplbackend_does_not_matter(tmp_path: Path) -> None:
    # exostab always uses Agg, but matplotlib checks the variable when it is imported: a traceback even with --no-plots.
    for args in (
        (
            "check",
            "Kepler-36",
            "--offline",
            "--orbits",
            "100",
            "--draws",
            "0",
            "--no-plots",
            "--out",
            str(tmp_path),
        ),
        (
            "sweep",
            "Kepler-36",
            "--offline",
            "--orbits",
            "100",
            "--steps",
            "2",
            "--jobs",
            "1",
            "--out",
            str(tmp_path),
        ),
    ):
        r = _exostab(*args, MPLBACKEND="nonsense")
        assert r.returncode == 0, r.stderr


def test_a_worker_that_dies_is_one_line(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # What an out-of-memory kill looks like: a BrokenProcessPool traceback.
    def killed(*args: object, **kwargs: object) -> None:
        raise BrokenProcessPool("A process in the process pool was terminated abruptly")

    monkeypatch.setattr("exostab.analysis.check_system", killed)
    monkeypatch.setattr("exostab.sweep.run_sweep", killed)
    for args in (
        ["check", "Kepler-36", *FAST, "--no-plots", "--out", str(tmp_path)],
        ["sweep", "Kepler-36", "--orbits", "100", "--steps", "2", "--out", str(tmp_path)],
    ):
        r = runner.invoke(app, args)
        assert r.exit_code == 1 and isinstance(r.exception, SystemExit), r.output
        assert "worker process died" in " ".join(r.output.split())


def test_parameters_the_analysis_cannot_use_are_one_line(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    file = tmp_path / "t.yaml"
    file.write_text(
        "star: {mass_msun: 1.0}\nplanets:\n  - {name: T b, period_days: 10, mass_earth: 1.0e-14}\n"
        "  - {name: T c, period_days: 30, mass_earth: 5}\n"
    )
    r = runner.invoke(
        app, ["check", "--from-file", str(file), *FAST, "--no-plots", "--out", str(tmp_path / "o")]
    )
    assert r.exit_code == 1 and isinstance(r.exception, SystemExit), r.output
    assert "the Hill limit cannot be evaluated" in " ".join(r.output.split())
    # a sweep finds out before it integrates anything, not after every run
    _no_integration(monkeypatch)
    file.write_text(file.read_text().replace("1.0e-14", "1.0"))
    r = runner.invoke(
        app,
        [
            "sweep",
            "--from-file",
            str(file),
            "--param",
            "mass",
            "--range",
            "1e-20",
            "10",
            "--steps",
            "2",
            "--orbits",
            "100",
            "--out",
            str(tmp_path / "s"),
        ],
    )
    assert r.exit_code == 1 and isinstance(r.exception, SystemExit), r.output
    assert "the Hill limit cannot be evaluated" in " ".join(r.output.split())


def test_a_draw_that_is_not_finite_is_one_line(tmp_path: Path) -> None:
    file = tmp_path / "t.yaml"
    file.write_text(
        "star: {mass_msun: 1.0}\nplanets:\n"
        "  - {name: T b, period_days: 10, mass_earth: 5, omega_deg: {value: 90, err: 1.0e+308}}\n"
        "  - {name: T c, period_days: 60, mass_earth: 8}\n"
    )
    r = runner.invoke(
        app,
        [
            "check",
            "--from-file",
            str(file),
            "--orbits",
            "100",
            "--draws",
            "60",
            "--no-plots",
            "--out",
            str(tmp_path),
        ],
    )
    assert r.exit_code == 1 and isinstance(r.exception, SystemExit), r.output
    assert "an error bar is so large" in " ".join(r.output.split())


@pytest.mark.skipif(not hasattr(signal, "SIGHUP"), reason="POSIX signals")
@pytest.mark.parametrize("sig", ["SIGTERM", "SIGHUP"])
def test_a_signal_stops_the_workers_too(sig: str, tmp_path: Path) -> None:
    # The main process exited at once and left 3 workers at full CPU, with parent 1, until their runs ended.
    args = [
        "check",
        "TRAPPIST-1",
        "--offline",
        "--orbits",
        "2000000",
        "--draws",
        "4",
        "--no-plots",
        "--jobs",
        "3",
    ]
    p = subprocess.Popen(
        [sys.executable, "-m", "exostab", *args, "--out", str(tmp_path)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,  # its own process group, which this test can check and clean up
    )
    try:
        deadline = time.monotonic() + 60
        while time.monotonic() < deadline and not _children(p.pid):
            time.sleep(0.2)
        assert _children(p.pid), "no worker started"
        time.sleep(1)
        os.kill(p.pid, getattr(signal, sig))
        assert p.wait(timeout=20) == 128 + getattr(signal, sig)
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline and _group_alive(p.pid):
            time.sleep(0.2)
        assert not _group_alive(p.pid), "workers are still running"
    finally:
        if _group_alive(p.pid):
            os.killpg(p.pid, signal.SIGKILL)
        p.wait(timeout=20)


def _children(pid: int) -> list[str]:
    out = subprocess.run(["pgrep", "-P", str(pid)], capture_output=True, text=True, check=False)
    return out.stdout.split()


def _group_alive(pgid: int) -> bool:
    """Whether a process of this group, except a zombie, is left."""
    out = subprocess.run(["ps", "-A", "-o", "pgid=,stat="], capture_output=True, text=True, check=False)
    return any(
        line.split()[0] == str(pgid) and not line.split()[1].startswith("Z")
        for line in out.stdout.splitlines()
    )


def test_sweep_varies_the_planet_named_in_the_first_argument(tmp_path: Path) -> None:
    # "exostab sweep 'TRAPPIST-1 c'" swept planet b; only the title and sweep.json showed it.
    base = ["--orbits", "100", "--steps", "2", "--range", "0", "0.01", "--jobs", "1", "--out", str(tmp_path)]

    def swept(*args: str) -> str:
        r = runner.invoke(app, ["sweep", *args, *base])
        assert r.exit_code == 0, r.output
        return str(json.loads((tmp_path / "sweep.json").read_text())["planet"])

    assert swept("TRAPPIST-1 c") == "TRAPPIST-1 c"
    assert swept("trappist-1 C") == "TRAPPIST-1 c"
    assert swept("TRAPPIST-1") == "TRAPPIST-1 b"
    assert swept("TRAPPIST-1 c", "--planet", "d") == "TRAPPIST-1 d"  # the option says it outright


def test_sweep_title_names_the_planet_varied(tmp_path: Path) -> None:
    file = write_system(tmp_path, "Z", "Z b", "Z c")
    r = runner.invoke(
        app,
        [
            "sweep",
            "--from-file",
            str(file),
            "--planet",
            "z B",
            "--range",
            "0",
            "0.1",
            "--steps",
            "2",
            "--orbits",
            "100",
            "--jobs",
            "1",
            "--out",
            str(tmp_path / "o"),
        ],
        env={"COLUMNS": "120"},
    )
    assert r.exit_code == 0, r.output
    assert "for planet Z b" in r.output


def test_sweep_refuses_a_letter_that_fits_two_planets(tmp_path: Path) -> None:
    file = write_system(tmp_path, "Y", "HD 1 A b", "HD 1 B b")
    r = runner.invoke(
        app,
        ["sweep", "--from-file", str(file), "--steps", "2", "--orbits", "100", "--out", str(tmp_path / "o")],
    )
    assert r.exit_code == 1 and "fits several planets" in " ".join(r.output.split())


def test_sweep_table_tells_close_values_apart(tmp_path: Path) -> None:
    # All three rows read 16.22, while sweep.csv had 16.2187, 16.2188 and 16.2189.
    r = runner.invoke(
        app,
        [
            "sweep",
            "Kepler-36",
            "--param",
            "period",
            "--planet",
            "c",
            "--range",
            "16.2187",
            "16.2189",
            "--steps",
            "3",
            "--orbits",
            "100",
            "--jobs",
            "1",
            "--out",
            str(tmp_path),
        ],
        env={"COLUMNS": "120"},
    )
    assert r.exit_code == 0, r.output
    assert all(v in r.output for v in ("16.2187", "16.2188", "16.2189"))
    r = runner.invoke(
        app, ["sweep", "Kepler-36", "--steps", "3", "--orbits", "100", "--jobs", "1", "--out", str(tmp_path)]
    )
    assert "0.25" in r.output  # a wide range keeps its short values


def test_sweep_output_lists_the_assumptions(tmp_path: Path) -> None:
    # Only the table and the Saved line, although sweep.json holds every flag.
    r = runner.invoke(
        app, ["sweep", "HD 127195", "--steps", "2", "--orbits", "100", "--jobs", "1", "--out", str(tmp_path)]
    )
    assert r.exit_code == 0, r.output
    text = " ".join(r.output.split())
    assert "Data completion" in text and "minimum mass m sin i" in text


def test_saved_paths_stay_on_one_line(tmp_path: Path) -> None:
    # A path after Saved: was split at 80 columns when piped, so it could not be copied.
    folder = tmp_path / ("long-folder-name-" * 8)
    r = runner.invoke(
        app, ["sweep", "Kepler-36", "--steps", "2", "--orbits", "100", "--jobs", "1", "--out", str(folder)]
    )
    assert r.exit_code == 0, r.output
    assert f"{folder}/sweep.csv" in plain(r.output)


def _card(res: object, width: int = 100) -> str:
    console = Console(record=True, width=width)
    render(res.report, console)  # type: ignore[attr-defined]
    return " ".join(re.sub("[│╭╮╰╯─]", " ", console.export_text()).split())


def test_the_card_says_what_the_inclination_prior_did() -> None:
    # Only report.json recorded it.
    from exostab.data import load_system

    hd = load_system("HD 127195")
    used = check_system(
        hd, CheckSettings(orbits=100, draws=2, jobs=1, ias15_check=False, inclination_prior="isotropic")
    )
    assert "drawn with the isotropic prior" in _card(used)
    no_draws = check_system(
        hd, CheckSettings(orbits=100, draws=0, jobs=1, ias15_check=False, inclination_prior="isotropic")
    )
    assert "isotropic inclination prior has no effect: it applies only to draws" in _card(no_draws)
    no_minimum = check_system(
        two_planet_system(),
        CheckSettings(orbits=100, draws=1, jobs=1, ias15_check=False, inclination_prior="isotropic"),
    )
    assert "no mass here is a minimum mass" in _card(no_minimum)
    default = _card(check_system(hd, CheckSettings(orbits=100, draws=1, jobs=1)))
    assert "isotropic" not in default and "no effect" not in default


def test_the_assumptions_keep_their_text_next_to_long_names(tmp_path: Path) -> None:
    # Three lines of truncated planet names, and no text, under Data completion at 80 columns.
    from exostab.data import load_system_file

    path = tmp_path / "s.yaml"
    planets = "".join(
        f"  - {{name: A long planet name {k}, period_days: {10 * 2**k}, mass_earth: 5}}\n" for k in range(8)
    )
    path.write_text(f"name: Other\nstar: {{mass_msun: 1.0}}\nplanets:\n{planets}")
    res = check_system(load_system_file(path), CheckSettings(orbits=100, draws=0, jobs=1, ias15_check=False))
    text = _card(res, width=80)
    assert "Eccentricity not given; assumed 0." in text and "A long planet name 7" in text
    assert "…" not in text


def test_help_does_not_cut_the_default_folder_or_the_script_url() -> None:
    # At 80 columns: "exostab-results/<system..." and "(https://github.com/mim..."
    r = runner.invoke(app, ["check", "--help"], env={"COLUMNS": "80"})
    assert r.exit_code == 0
    text = plain(r.output)
    assert "…" not in text
    joined = "".join(re.sub("[│╭╮╰╯─]", " ", text).split())
    assert "raw.githubusercontent.com/mimitoz62/exostab/main/scripts/make_spock_env.sh" in joined
    assert "exostab-results" in joined


def test_the_card_folds_planet_names_at_60_columns() -> None:
    from exostab.data import load_system

    res = check_system(
        load_system("TRAPPIST-1"), CheckSettings(orbits=50, draws=0, jobs=1, ias15_check=False)
    )
    console = Console(record=True, width=60)
    render(res.report, console)
    assert "…" not in console.export_text()


def test_list_is_not_cut_when_piped_or_narrow(monkeypatch: pytest.MonkeyPatch) -> None:
    # Piped or at 80 columns the M* of TRAPPIST-1 read 0.08..., at 60 only an ellipsis, and grep got cut numbers.
    monkeypatch.delenv("COLUMNS", raising=False)
    piped = runner.invoke(app, ["list"]).output
    assert "…" not in piped.replace("… ", "") and "0.0898" in piped and "Discovery" in piped
    for columns in ("80", "60", "40", "120"):
        r = runner.invoke(app, ["list"], env={"COLUMNS": columns})
        assert r.exit_code == 0
        assert "…" not in r.output.replace("… ", "")
        assert "0.0898" in r.output or columns == "40"  # at 40 it goes on over the next lines
    # what matters least goes first
    assert "Discovery" in runner.invoke(app, ["list"], env={"COLUMNS": "120"}).output
    assert "Discovery" not in runner.invoke(app, ["list"], env={"COLUMNS": "60"}).output


def test_one_of_a_thing_is_singular(tmp_path: Path) -> None:
    # "1 systems in 1 s", "any of the 1 draws"
    r = runner.invoke(
        app, ["catalog", "build", "--limit", "1", "--orbits", "100", "--draws", "0", "--out", str(tmp_path)]
    )
    assert r.exit_code == 0 and "1 system in" in r.output
    res = check_system(two_planet_system(), CheckSettings(orbits=300, draws=1, jobs=1))
    text = _card(res)
    assert "1 Monte Carlo draw;" in text and "1 draws" not in text


def test_catalog_timeout_and_skip(tmp_path: Path) -> None:
    from exostab.catalog.build import CatalogSettings, build_catalog

    t0 = time.monotonic()
    _, rows = build_catalog(CatalogSettings(orbits=1e6, draws=0, max_seconds=1, jobs=1), tmp_path, limit=1)
    assert rows[0]["status"] == "timeout" and rows[0]["overall"] is None
    # the cap is enforced: the 1e6-orbit integration (minutes) is stopped, even under coverage
    assert time.monotonic() - t0 < 30
    from exostab.catalog.build import check_one
    from exostab.data import load_rows
    from exostab.data.archive import group_by_host

    rows_, info = load_rows()
    skipped = check_one(group_by_host(rows_)["Kepler-47"], info, CatalogSettings())
    assert skipped["status"] == "skipped" and "circumbinary" in skipped["reason"]
