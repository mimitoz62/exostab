"""Web app: pure helpers and a headless run of the Streamlit app (offline snapshot)."""

from __future__ import annotations

import json
import sys
from dataclasses import replace
from pathlib import Path

import pytest

pytest.importorskip("streamlit")
pytest.importorskip("plotly")

from streamlit.testing.v1 import AppTest

from conftest import two_planet_system
from exostab.analysis import CheckSettings, check_system
from exostab.data import load_system
from exostab.models import Provenance
from exostab.web import figures
from exostab.web.state import (
    AppState,
    WhatIf,
    _b64,
    apply_changes,
    decode_state,
    encode_state,
    input_hash,
    planet_rows,
    share_url,
    table_edits,
)

APP = str(Path(__file__).resolve().parents[1] / "streamlit_app.py")


def test_table_roundtrip_and_edits() -> None:
    s = two_planet_system(e=(0.1, 0.2))
    rows = planet_rows(s)
    assert [r["planet"] for r in rows] == ["Test b", "Test c"]
    assert table_edits(s, rows) == {}
    rows[1]["eccentricity"] = 0.3
    rows[0]["omega_deg"] = None
    edits = table_edits(s, rows)
    assert edits == {"Test c": {"eccentricity": 0.3}, "Test b": {"omega_deg": None}}
    changed = apply_changes(s, edits, WhatIf())
    assert changed.planet("c").eccentricity.value == 0.3
    assert changed.planet("b").omega_deg.provenance is Provenance.RANDOMIZED
    assert {f.rule for f in changed.flags} == {"edited_in_web_app"}


def test_what_if_adjustments() -> None:
    s = two_planet_system(period_ratio=2.0)
    w = WhatIf(planet="Test c", mass_factor=3.0, eccentricity=0.25, period_ratio=1.5)
    changed = apply_changes(s, {}, w)
    c = changed.planet("c")
    assert c.mass_earth.value == pytest.approx(30.0)
    assert c.eccentricity.value == 0.25
    assert c.period_days.value == pytest.approx(150.0)
    assert any(f.rule == "what_if_in_web_app" for f in changed.flags)
    # a period ratio below the next planet reorders the planets, which must stay sorted
    s3 = two_planet_system(period_ratio=3.0)
    moved = apply_changes(s3, {"Test b": {"period_days": 400.0}}, WhatIf())
    assert [p.name for p in moved.planets] == ["Test c", "Test b"]
    with pytest.raises(ValueError, match="outside another"):
        apply_changes(s, {}, WhatIf(planet="Test b", period_ratio=1.5))
    with pytest.raises(ValueError, match="eccentricity"):
        apply_changes(s, {"Test b": {"eccentricity": 1.5}}, WhatIf())
    with pytest.raises(ValueError, match="unknown planet"):
        apply_changes(s, {"X": {"eccentricity": 0.1}}, WhatIf())
    with pytest.raises(ValueError, match="cannot be edited"):
        apply_changes(s, {"Test b": {"mass_kind": 1.0}}, WhatIf())
    with pytest.raises(ValueError, match="missing"):
        apply_changes(s, {"Test b": {"eccentricity": None}}, WhatIf())
    assert not WhatIf(planet="Test b").is_active()


def test_share_link_roundtrip() -> None:
    st = AppState(
        system="HD 127195",
        source="snapshot",
        edits={"HD 127195 b": {"eccentricity": 0.1}},
        whatif=WhatIf(planet="HD 127195 c", mass_factor=2.0),
        budget_s=30,
        seed=7,
        prior="isotropic",
        orbits=5000.0,
        draws=10,
    )
    back = decode_state(encode_state(st))
    assert back == st
    url = share_url("https://example.org/app/", st)
    assert url.startswith("https://example.org/app/?") and "run=1" in url


def test_decode_rejects_garbage() -> None:
    s = decode_state(
        {
            "system": "X",
            "budget": "abc",
            "seed": "x",
            "edits": "!!!",
            "orbits": "1e12",
            "draws": "5",
            "source": "hack",
            "prior": "weird",
        }
    )
    assert (s.system, s.budget_s, s.seed, s.edits, s.orbits, s.source, s.prior) == (
        "X",
        10,
        0,
        {},
        None,
        "archive",
        "none",
    )
    assert decode_state({"budget": "1000"}).budget_s == 120
    assert decode_state({"orbits": "x", "draws": "1"}).orbits is None


@pytest.mark.parametrize(
    "params",
    [
        {"seed": "-1"},  # numpy and the seed widget take only 0 ... 2**31 - 1
        {"seed": "99999999999"},
        {"budget": "nan"},  # nan passes min/max clamping
        {"budget": "inf"},
        {"edits": _b64({"Test b": {"eccentricity": float("nan")}})},
        {"whatif": _b64({"planet": "Test b", "mass_factor": 4.0})},  # not a choice of the slider
        {"whatif": _b64({"planet": "Test b", "eccentricity": 1.5})},
        {"whatif": _b64({"planet": "Test c", "period_ratio": 0.5})},
        # beyond what the widgets produce: e above E_MAX = 0.95 (the slider and the e column stop there, and
        # the analysis refuses it), a period ratio of 1e300, table values below the columns' minimums
        {"whatif": _b64({"planet": "Test b", "eccentricity": 0.97})},
        {"whatif": _b64({"planet": "Test c", "period_ratio": 1e300})},
        {"edits": _b64({"Test b": {"eccentricity": 0.97}})},
        {"edits": _b64({"Test b": {"period_days": 1e-4}})},
        {"edits": _b64({"Test b": {"mass_earth": 1e-7}})},
        {"orbits": "1e7", "draws": "500"},  # days of CPU time on a public server
        {"orbits": "1e5", "draws": "101"},
        {"orbits": "1.5e5", "draws": "10"},
        {"orbits": "nan", "draws": "10"},
    ],
)
def test_decode_falls_back_to_defaults(params: dict[str, str]) -> None:
    assert decode_state({"system": "X", **params}) == AppState(system="X")


def test_decode_accepts_the_longest_preset() -> None:
    from exostab.budget import PRESETS

    orbits, draws = PRESETS[-1]
    s = decode_state({"orbits": f"{orbits:g}", "draws": str(draws), "seed": str(2**31 - 1), "budget": "inf"})
    assert (s.orbits, s.draws, s.seed, s.budget_s) == (orbits, draws, 2**31 - 1, 10)


@pytest.mark.parametrize("params", [{"seed": "-1"}, {"seed": "99999999999"}, {"budget": "nan"}])
def test_app_survives_crafted_links(params: dict[str, str]) -> None:
    at = AppTest.from_file(APP, default_timeout=60)
    at.query_params.update({"system": "Kepler-36", "source": "snapshot", **params})
    at.run()
    assert not at.exception, at.exception


RUN_NOW = {"system": "Kepler-36", "source": "snapshot", "orbits": "100", "draws": "1", "run": "1"}


@pytest.mark.parametrize(
    "params",
    [
        {"whatif": _b64({"planet": "Kepler-36 b", "eccentricity": 0.97})},
        {"edits": _b64({"Kepler-36 b": {"eccentricity": 0.97}})},
        {"whatif": _b64({"planet": "Kepler-36 c", "period_ratio": 1e300})},
    ],
)
def test_app_runs_crafted_links_without_a_traceback(params: dict[str, str]) -> None:
    # These links ran on cc063eb (the sliders clamped them, the analysis capped e) and showed a traceback
    # after be59b02 and 27441ad: "eccentricity 0.97 is above 0.95", OverflowError in REBOUND.
    at = AppTest.from_file(APP, default_timeout=120)
    at.query_params.update({**RUN_NOW, **params})
    at.run()
    assert not at.exception, at.exception
    assert not at.error, [e.value for e in at.error]
    assert any("Overall:" in m.value for m in at.markdown)  # the link's invalid part was dropped


def test_app_reports_parameters_the_analysis_cannot_use() -> None:
    # A period the table accepts but REBOUND cannot use (1e300 d overflows): an error message, not a traceback.
    at = AppTest.from_file(APP, default_timeout=120)
    at.query_params.update({**RUN_NOW, "edits": _b64({"Kepler-36 c": {"period_days": 1e300}})})
    at.run()
    assert not at.exception, at.exception
    assert any("cannot be checked" in e.value for e in at.error)
    assert _link(at).get("run") != "1"  # the automatic run is switched off


def test_input_hash_changes_with_any_input() -> None:
    s = two_planet_system()
    h = input_hash(s, {"seed": 0})
    assert h == input_hash(two_planet_system(), {"seed": 0})
    assert h != input_hash(s, {"seed": 1})
    assert h != input_hash(two_planet_system(e=(0.0, 0.01)), {"seed": 0})


def test_plotly_figures() -> None:
    res = check_system(load_system("Kepler-36"), CheckSettings(orbits=200, draws=3, jobs=1, n_samples=20))
    assert len(figures.orbits(res.realizations[0], res.runs[0], "K").data) == 1 + 2 * 2
    assert len(figures.megno_time(res.runs[0], res.ias15, "K").data) == 4
    assert figures.megno_draws(res.runs).data


def test_app_runs_headless() -> None:
    at = AppTest.from_file(APP, default_timeout=120)
    at.query_params.update(
        {"system": "Kepler-36", "source": "snapshot", "orbits": "300", "draws": "2", "run": "1"}
    )
    at.run()
    assert not at.exception, at.exception
    text = " ".join(m.value for m in at.markdown)
    assert "Overall:" in text
    assert len(at.get("download_button")) == 3
    assert any("orbits=300" in c.value for c in at.code)
    # the documentation link points to the documentation site, as do the other docs links
    assert any("[documentation](https://mimitoz62.github.io/exostab/)" in c.value for c in at.caption)
    # an unknown system gives a clear error instead of a crash
    at2 = AppTest.from_file(APP, default_timeout=60)
    at2.query_params.update({"system": "Nonexistent-99", "source": "snapshot"})
    at2.run()
    assert not at2.exception and at2.error
    # the command line's pointer to `exostab list` means nothing in a browser
    assert "No multi-planet system" in at2.error[0].value and "search box" in at2.error[0].value
    assert "exostab list" not in at2.error[0].value


def test_app_says_when_a_run_is_shorter_than_the_catalogs() -> None:
    at = AppTest.from_file(APP, default_timeout=120)
    at.query_params.update(
        {"system": "Kepler-36", "source": "snapshot", "orbits": "300", "draws": "2", "run": "1"}
    )
    at.run()
    assert not at.exception, at.exception
    assert any("covers 300 orbits" in w.value for w in at.warning)


def test_search_box_shows_other_names() -> None:
    at = AppTest.from_file(APP, default_timeout=60)
    at.query_params.update({"source": "snapshot"})
    at.run()
    assert not at.exception, at.exception
    options = at.sidebar.selectbox[0].options
    assert "GJ 876 (Gliese 876)" in options and "TRAPPIST-1" in options


def test_app_says_when_only_the_snapshot_was_searched(monkeypatch: pytest.MonkeyPatch) -> None:
    # The web app called resolve_host directly: with the snapshot chosen, or during an archive outage without
    # a cache, a real archive system was reported as missing from "the archive table" (F009).
    import streamlit as st

    from exostab.data import archive, store

    at = AppTest.from_file(APP, default_timeout=60)
    at.query_params.update({"system": "HD 215152", "source": "snapshot"})
    at.run()
    assert not at.exception and at.error
    message = at.error[0].value
    assert (
        "in the offline snapshot, not the full archive table" in message
        and "in the archive table" not in message
    )

    def outage(where: str) -> None:
        raise archive.ArchiveError("simulated outage")

    monkeypatch.delenv("EXOSTAB_OFFLINE")
    monkeypatch.setattr(store, "fetch_rows", outage)
    st.cache_data.clear()  # _archive keeps the rows of earlier runs for a day
    try:
        at = AppTest.from_file(APP, default_timeout=60)
        at.query_params.update({"system": "HD 215152"})
        at.run()
    finally:
        st.cache_data.clear()
    assert not at.exception and at.error
    message = at.error[0].value
    assert "offline snapshot" in message and "simulated outage" in message
    assert "not the full archive table" in message


def test_app_rejects_circumbinary_and_reports_json() -> None:
    at = AppTest.from_file(APP, default_timeout=60)
    at.query_params.update({"system": "Kepler-47", "source": "snapshot"})
    at.run()
    assert at.error and "circumbinary" in at.error[0].value
    # report.json produced by the app is a valid report
    at = AppTest.from_file(APP, default_timeout=120)
    at.query_params.update(
        {"system": "Kepler-36", "source": "snapshot", "orbits": "200", "draws": "1", "run": "1"}
    )
    at.run()
    data = at.get("download_button")[0].proto.url  # served from the media file manager
    assert data
    rep = json.loads(
        check_system(load_system("Kepler-36"), CheckSettings(orbits=200, draws=1, jobs=1)).report.to_json()
    )
    assert rep["settings"]["orbits"] == 200


def _what_if_app(system: str, **params: str) -> AppTest:
    at = AppTest.from_file(APP, default_timeout=60)
    at.query_params.update({"system": system, "source": "snapshot", **params})
    at.run()
    assert not at.exception, at.exception
    return at


def _slider(at: AppTest, label: str) -> float:
    return float(next(s.value for s in at.slider if s.label.startswith(label)))


def _link(at: AppTest) -> dict[str, str]:
    """The query parameters the app wrote, one string per key, as st.query_params reads them.

    After a run, AppTest.query_params holds a list for every key up to Streamlit 1.64, and a string for a key
    that occurs once from 1.65 on; st.query_params returns the last value of a repeated key.
    """
    return {k: v if isinstance(v, str) else v[-1] for k, v in at.query_params.items()}


def test_what_if_is_not_set_by_selecting_a_planet() -> None:
    # GJ 876 c lies 15.5 times further out than d, beyond the slider's old range (1.01-10): selecting it
    # used to move c to 10 times d's period without the user touching a slider
    at = _what_if_app("GJ 876")
    next(s for s in at.selectbox if s.label == "Planet").select("GJ 876 c").run()
    assert not at.exception, at.exception
    state = at.session_state["state"]
    assert state.whatif.planet == "GJ 876 c" and not state.whatif.is_active()
    gj876 = load_system("GJ 876")
    p_c, p_d = gj876.planet("c").period_days.value, gj876.planet("d").period_days.value
    assert _slider(at, "Period ratio to GJ 876 d") == pytest.approx(p_c / p_d)
    # moving the slider does set a what-if, which stays set on later reruns and comes back from the link
    next(s for s in at.slider if s.label.startswith("Period ratio")).set_value(12.0).run()
    assert at.session_state["state"].whatif.period_ratio == 12.0
    at.run()
    assert at.session_state["state"].whatif.period_ratio == 12.0 and _slider(at, "Period ratio") == 12.0
    link = _link(at)
    at2 = _what_if_app("GJ 876", whatif=link["whatif"])
    assert at2.session_state["state"].whatif == WhatIf(planet="GJ 876 c", period_ratio=12.0)


def test_what_if_keeps_a_table_eccentricity_above_the_old_slider_range() -> None:
    # the table accepts e up to 0.95; the eccentricity slider (innermost planet, selected by default) used to
    # stop at 0.9 and overrode 0.93 with 0.9
    at = _what_if_app("Kepler-36", edits=_b64({"Kepler-36 b": {"eccentricity": 0.93}}))
    assert not at.session_state["state"].whatif.is_active()
    assert _slider(at, "Eccentricity") == 0.93


def test_what_if_neighbour_follows_the_edited_order() -> None:
    # with c moved outside b (70 d > 61.1 d), b's inner neighbour is d, as in apply_changes
    at = _what_if_app("GJ 876", edits=_b64({"GJ 876 c": {"period_days": 70.0}}))
    next(s for s in at.selectbox if s.label == "Planet").select("GJ 876 b").run()
    assert not at.exception and not at.error, (at.exception, at.error)
    assert not at.session_state["state"].whatif.is_active()
    assert any(s.label == "Period ratio to GJ 876 d" for s in at.slider)


@pytest.mark.parametrize("planet", ["TRAPPIST-1 c", "TRAPPIST-1 d"])
def test_what_if_with_a_cleared_period(planet: str) -> None:
    # a cleared cell is None: the what-if box must not divide by it, and the run is refused with a message
    at = _what_if_app(
        "TRAPPIST-1",
        edits=_b64({"TRAPPIST-1 c": {"period_days": None}}),
        whatif=_b64({"planet": planet, "mass_factor": 2.0}),
    )
    assert at.error and "a value is missing" in at.error[0].value


def test_packaged_launcher(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    # `python -m exostab.web` works from an installed package: streamlit_app.py at the repository root is not
    # in the wheel
    import streamlit.web.cli as stcli

    import exostab.web.__main__ as launcher

    calls: list[list[str]] = []
    monkeypatch.setattr(sys, "argv", ["python -m exostab.web"])
    monkeypatch.setattr(stcli, "main", lambda: calls.append(list(sys.argv)))
    assert launcher.main(["--server.port", "8502"]) == 0
    assert calls == [["streamlit", "run", str(launcher.SCRIPT), *launcher.SETTINGS, "--server.port", "8502"]]
    assert launcher.SCRIPT.parent == Path(launcher.__file__).parent
    at = AppTest.from_file(str(launcher.SCRIPT), default_timeout=60)
    at.query_params.update({"system": "Kepler-36", "source": "snapshot"})
    at.run()
    assert not at.exception, at.exception
    assert at.title[0].value == "exostab"
    # without the [web] extra it says what to install, pointing to the install commands (exostab is not on PyPI)
    monkeypatch.setitem(sys.modules, "streamlit.web.cli", None)
    capsys.readouterr()
    assert launcher.main([]) == 1
    err = capsys.readouterr().err
    assert "[web] extra" in err and "https://mimitoz62.github.io/exostab/quickstart/" in err
    assert 'pip install "exostab[web]"' not in err


def test_launcher_settings_and_overriding_them(monkeypatch: pytest.MonkeyPatch) -> None:
    # The wheel has no .streamlit/config.toml. Without --server.headless the first run stops at Streamlit's
    # email prompt, without --browser.gatherUsageStats false it sends usage statistics, and without
    # --client.toolbarMode viewer the toolbar has a Deploy button.
    import streamlit.web.cli as stcli

    import exostab.web.__main__ as launcher

    calls: list[list[str]] = []
    monkeypatch.setattr(stcli, "main", lambda: calls.append(list(sys.argv)))
    monkeypatch.setattr(sys, "argv", ["python -m exostab.web"])
    assert launcher.main() == 0
    monkeypatch.setattr(sys, "argv", ["python -m exostab.web", "--server.headless", "false"])
    assert launcher.main() == 0

    def parsed(argv: list[str]) -> dict[str, object]:
        assert argv[:3] == ["streamlit", "run", str(launcher.SCRIPT)]
        return stcli.main_run.make_context("run", argv[2:]).params  # Streamlit's own parser

    params = parsed(calls[0])
    assert params["server_headless"] is True and params["browser_gatherUsageStats"] is False
    assert params["client_toolbarMode"] == "viewer"
    # the user's arguments come later, and the last value of an option wins
    params = parsed(calls[1])
    assert params["server_headless"] is False and params["browser_gatherUsageStats"] is False


def test_app_reports_a_broken_spock_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EXOSTAB_SPOCK_PYTHON", "/nonexistent/python")
    at = _what_if_app("TOI-270", orbits="100", draws="1", run="1", spock="1")
    assert at.error and "SPOCK could not be run" in at.error[0].value
    # SPOCK and the automatic run are switched off, also in the link, so a rerun does not repeat the failure
    state = at.session_state["state"]
    assert not state.spock and not state.run
    assert "spock" not in at.query_params and "run" not in at.query_params
    at.run()
    assert not at.exception and not at.error, (at.exception, at.error)
    assert not next(c for c in at.checkbox if c.label.startswith("Add SPOCK")).value


@pytest.fixture
def fake_budget(monkeypatch: pytest.MonkeyPatch):  # type: ignore[no-untyped-def]
    """The web app with a fixed, cheap budget plan (200 orbits, 1 draw; 1e-3 and 1e-2 s per orbit for WHFast
    and IAS15) and a record of every analysis it runs (orbits, draws, budget_s)."""
    import streamlit as st

    import exostab.web.app as web_app
    from exostab.budget import Plan

    calls: list[tuple[float, int, float | None]] = []
    check = web_app.check_system

    def counting_check(system, settings, **kwargs):  # type: ignore[no-untyped-def]
        calls.append((settings.orbits, settings.draws, settings.budget_s))
        assert settings.orbits <= 1e3, "this test must not integrate long runs"
        return check(system, settings, **kwargs)

    def plan(system, budget_s, base):  # type: ignore[no-untyped-def]
        p = Plan(
            orbits=200.0,
            draws=1,
            budget_s=budget_s,
            estimated_s=1.0,
            whfast_s_per_orbit=1e-3,
            ias15_s_per_orbit=1e-2,
        )
        return replace(base, orbits=p.orbits, draws=p.draws, budget_s=budget_s), p

    st.cache_data.clear()
    monkeypatch.setattr(web_app, "check_system", counting_check)
    monkeypatch.setattr(web_app, "settings_for_budget", plan)
    yield calls
    st.cache_data.clear()


def _caption(at: AppTest) -> str:
    return next(c.value for c in at.caption if c.value.startswith("N-body:"))


def test_budget_run_is_not_recomputed(fake_budget) -> None:  # type: ignore[no-untyped-def]
    at = AppTest.from_file(APP, default_timeout=120)
    at.query_params.update({"system": "Kepler-36", "source": "snapshot", "budget": "15", "seed": "4242"})
    at.run()
    next(b for b in at.button if b.label == "Run").click().run()
    assert not at.exception, at.exception
    assert fake_budget == [(200.0, 1, 15.0)]
    caption = _caption(at)
    assert "chosen for a 15 s budget" in caption
    # a rerun with the same inputs (any widget interaction) finds the cached result: same report and hash
    at.run()
    assert fake_budget == [(200.0, 1, 15.0)] and _caption(at) == caption
    # so does the link the app wrote, opened in a new session on the same server
    link = _link(at)
    assert link["orbits"] == "200" and link["draws"] == "1" and link["run"] == "1"
    at2 = AppTest.from_file(APP, default_timeout=120)
    at2.query_params.update(link)
    at2.run()
    assert not at2.exception, at2.exception
    assert fake_budget == [(200.0, 1, 15.0)] and _caption(at2) == caption


def test_link_run_length_is_limited_by_its_cost(fake_budget) -> None:  # type: ignore[no-untyped-def]
    # 1e5 orbits and 100 draws pass the static checks (the longest preset), but at the measured speed they
    # would take about 1,000 s here: the run length chosen for the link's budget is used instead
    at = AppTest.from_file(APP, default_timeout=120)
    at.query_params.update(
        {
            "system": "Kepler-36",
            "source": "snapshot",
            "budget": "20",
            "orbits": "1e5",
            "draws": "100",
            "run": "1",
        }
    )
    at.run()
    assert not at.exception, at.exception
    assert fake_budget == [(200.0, 1, 20.0)]
    assert any("more than the 120 s limit" in w.value for w in at.warning)
    assert "chosen for a 20 s budget" in _caption(at)
    # an affordable run length from a link is used as given; no budget chose it here, so none is recorded
    at = AppTest.from_file(APP, default_timeout=120)
    at.query_params.update(
        {
            "system": "Kepler-36",
            "source": "snapshot",
            "budget": "20",
            "orbits": "300",
            "draws": "2",
            "run": "1",
        }
    )
    at.run()
    assert not at.exception, at.exception
    assert fake_budget[-1] == (300.0, 2, None)
    assert "budget" not in _caption(at)
