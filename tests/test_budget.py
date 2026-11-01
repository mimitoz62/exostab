import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from conftest import two_planet_system
from exostab import budget
from exostab.analysis import CheckSettings, settings_for_budget
from exostab.cli import app
from exostab.sampling import realizations


def test_parse_budget() -> None:
    assert budget.parse_budget("fast") == 10.0
    assert budget.parse_budget(" Thorough ") == 120.0
    assert budget.parse_budget("45") == 45.0
    assert budget.parse_budget(3) == 3.0
    for bad in ("soon", "-5", "0", "inf", "nan"):
        with pytest.raises(ValueError, match="budget"):
            budget.parse_budget(bad)


def test_presets_are_ordered_and_have_a_floor() -> None:
    costs = [o * (d + 1) for o, d in budget.PRESETS]
    assert costs == sorted(costs)
    assert budget.PRESETS[0] == (2e3, 8)


def test_estimate_seconds() -> None:
    # one worker: everything in sequence, no contention factor
    assert budget.estimate_seconds(1000, 4, 1e-3, 1e-2, workers=1) == pytest.approx(
        budget.OVERHEAD_S + 5 * 1.0 + 10.0
    )
    # many workers: bounded below by the longest single job (IAS15)
    many = budget.estimate_seconds(1000, 4, 1e-3, 1e-2, workers=64)
    assert many == pytest.approx(budget.OVERHEAD_S + budget.CONTENTION * 10.0)
    assert budget.estimate_seconds(1000, 4, 1e-3, 0.0, workers=1, ias15_check=False) == pytest.approx(
        budget.OVERHEAD_S + 5.0
    )


def test_plan_picks_the_largest_preset_that_fits(monkeypatch: pytest.MonkeyPatch) -> None:
    nominal = realizations(two_planet_system(), 0, 0)[0]
    speeds = {"whfast": 1e-5, "ias15": 1e-4}
    monkeypatch.setattr(budget, "_seconds_per_orbit", lambda real, integ, **kw: speeds[integ])
    p = budget.plan(nominal, 1000.0, jobs=1)
    assert (p.orbits, p.draws) == budget.PRESETS[-1] and p.warning is None
    p = budget.plan(nominal, 3.0, jobs=1)
    assert p.estimated_s <= 3.0 and (p.orbits, p.draws) != budget.PRESETS[-1]
    p = budget.plan(nominal, 0.01, jobs=1)
    assert (p.orbits, p.draws) == budget.PRESETS[0] and p.warning and "smallest run" in p.warning


def test_speed_measurement_is_positive() -> None:
    nominal = realizations(two_planet_system(), 0, 0)[0]
    s = budget._seconds_per_orbit(nominal, "whfast", min_orbits=20, min_wall=0.001)
    assert 0 < s < 0.01


def test_settings_for_budget_records_the_budget() -> None:
    s, p = settings_for_budget(two_planet_system(), 5.0, CheckSettings(jobs=1))
    assert s.budget_s == 5.0 and (s.orbits, s.draws) == (p.orbits, p.draws)


def test_cli_budget(tmp_path: Path) -> None:
    runner = CliRunner()
    r = runner.invoke(
        app, ["check", "Kepler-36", "--budget", "4", "--jobs", "2", "--no-plots", "--out", str(tmp_path)]
    )
    assert r.exit_code == 0, r.output
    assert "Budget 4 s" in r.output
    data = json.loads((tmp_path / "report.json").read_text())
    assert data["settings"]["budget_s"] == 4.0
    r = runner.invoke(app, ["check", "Kepler-36", "--budget", "4", "--draws", "3"])
    assert r.exit_code == 2 and "either --budget" in r.output
    r = runner.invoke(app, ["check", "Kepler-36", "--budget", "later"])
    assert r.exit_code == 2 and "budget must be" in r.output


@pytest.mark.parametrize("value", ["inf", "nan", "-5", "0"])
def test_budget_message_says_what_is_wanted(value: str) -> None:
    # "budget must be positive, got 'inf'"
    with pytest.raises(ValueError, match=f"positive, finite number of seconds, got '{value}'"):
        budget.parse_budget(value)


def test_a_small_budget_is_not_rounded_to_zero(monkeypatch: pytest.MonkeyPatch) -> None:
    # "needs about 2 s, more than the 0 s budget"
    nominal = realizations(two_planet_system(), 0, 0)[0]
    monkeypatch.setattr(budget, "_seconds_per_orbit", lambda real, integ, **kw: 1e-3)
    p = budget.plan(nominal, 0.4, jobs=1)
    assert p.warning and "more than the 0.4 s budget" in p.warning
