"""Report JSON and schema, terminal card, plots, and the command-line interface."""

from __future__ import annotations

import csv
import json
import math
import re
import time
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


def test_figures(small_result, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    paths = check_figures(small_result, tmp_path)
    assert [p.name for p in paths] == ["orbits.png", "megno.png"]
    assert all(p.stat().st_size > 10_000 for p in paths)


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
    assert "https://github.com/mimitoz62/exostab/blob/main/scripts/make_spock_env.sh" in " ".join(
        r.output.split()
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
