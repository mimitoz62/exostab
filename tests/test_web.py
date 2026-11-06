"""Web app: pure helpers and a headless run of the Streamlit app (offline snapshot)."""

from __future__ import annotations

import base64
import json
import sys
from collections.abc import Iterator
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

pytest.importorskip("streamlit")
pytest.importorskip("plotly")

from streamlit.testing.v1 import AppTest

from conftest import two_planet_system
from exostab.analysis import CheckSettings, check_system
from exostab.data import archive, load_system, store
from exostab.models import PhaseKind, Provenance, UnusableParametersError
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


def _raw(text: str) -> str:
    """A query parameter holding ``text`` the way a link encodes its JSON, for values json.dumps would not write."""
    return base64.urlsafe_b64encode(text.encode()).decode().rstrip("=")


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
        # a period or a mass the table would not take either; a period of 1e30 d never returned on the server
        {"edits": _b64({"Test b": {"period_days": 1e30}})},
        {"edits": _b64({"Test b": {"period_days": 1.7e308}})},
        {"edits": _b64({"Test b": {"mass_earth": 1e8}})},
        {"edits": _raw('{"Test b":{"period_days":1%s}}' % ("0" * 400))},  # an integer too large for a float
        {"whatif": _raw('{"planet":"Test b","mass_factor":1%s}' % ("0" * 400))},
        {"whatif": _raw('{"planet":"Test c","period_ratio":1%s}' % ("0" * 400))},
        {"edits": _raw("[" * 20000)},  # RecursionError
        {"whatif": _raw("[" * 20000)},
    ],
)
def test_decode_falls_back_to_defaults(params: dict[str, str]) -> None:
    assert decode_state({"system": "X", **params}) == AppState(system="X")


def test_edits_at_the_largest_values_the_table_takes_stay_valid() -> None:
    s = decode_state({"edits": _b64({"Test b": {"period_days": 1e12, "mass_earth": 1e7}})})
    assert s.edits == {"Test b": {"period_days": 1e12, "mass_earth": 1e7}}


@pytest.mark.parametrize(
    ("params", "said"),
    [
        ({"seed": "-1"}, "the seed"),
        ({"budget": "nan"}, "the time budget"),
        ({"edits": "!!!"}, "the table edits and what-if changes"),
        ({"whatif": _b64({"planet": "Test b", "mass_factor": 4.0})}, "the table edits and what-if changes"),
        ({"orbits": "1e7", "draws": "500"}, "the run length"),
        ({"orbits": "1000"}, "the run length"),
        ({"source": "hack"}, "the data source"),
        ({"prior": "weird"}, "the treatment of minimum masses"),
    ],
)
def test_decode_says_what_it_dropped(params: dict[str, str], said: str) -> None:
    assert said in decode_state(params).dropped


def test_decode_of_a_good_link_drops_nothing() -> None:
    st = AppState(
        system="X",
        source="snapshot",
        edits={"X b": {"eccentricity": 0.1}},
        budget_s=30,
        orbits=5000.0,
        draws=10,
    )
    assert decode_state(encode_state(st)).dropped == []
    assert decode_state({}).dropped == []


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


@pytest.mark.parametrize(
    ("raised", "shown", "hidden"),
    [
        (OverflowError(34, "Result too large"), "outside what exostab can compute", "Result too large"),
        (
            ValueError("Particle and primary positions are the same."),
            "outside what exostab can compute",
            "Particle",
        ),
        (ValueError("root not bracketed: f(1.0)=-6.28e-08"), "outside what exostab can compute", "bracketed"),
        (ZeroDivisionError("float division by zero"), "outside what exostab can compute", "division"),
        (UnusableParametersError("X b / X c: too small"), "too small", "Traceback"),
    ],
)
def test_app_reports_parameters_the_analysis_cannot_use(
    monkeypatch: pytest.MonkeyPatch, raised: Exception, shown: str, hidden: str
) -> None:
    # An error message in plain words, not a traceback, and not the internal text of the numerics.
    import streamlit as st

    import exostab.web.app as web_app

    def fails(*args: object, **kwargs: object) -> None:
        raise raised

    st.cache_data.clear()
    monkeypatch.setattr(web_app, "check_system", fails)
    at = AppTest.from_file(APP, default_timeout=120)
    at.query_params.update(RUN_NOW)
    at.run()
    st.cache_data.clear()
    assert not at.exception, at.exception
    errors = " ".join(e.value for e in at.error)
    assert "cannot be checked" in errors and shown in errors and hidden not in errors
    assert _link(at).get("run") != "1"  # the automatic run is switched off


@pytest.mark.parametrize(
    "edits",
    [
        {"Kepler-36 c": {"period_days": 1e30}},  # never returned, inside the IAS15 timing run
        {"Kepler-36 c": {"period_days": 1e300}},
        {"Kepler-36 b": {"mass_earth": 1e15}},
    ],
)
def test_app_leaves_out_edits_the_table_would_not_take(edits: dict[str, dict[str, float]]) -> None:
    at = AppTest.from_file(APP, default_timeout=120)
    at.query_params.update({"system": "Kepler-36", "source": "snapshot", "edits": _b64(edits)})
    at.run()
    assert not at.exception, at.exception
    assert at.session_state["state"].edits == {}
    assert any("Part of this link could not be used" in w.value for w in at.warning)


def test_app_runs_at_the_largest_values_the_table_takes() -> None:
    at = AppTest.from_file(APP, default_timeout=120)
    at.query_params.update(
        {**RUN_NOW, "draws": "0", "edits": _b64({"Kepler-36 c": {"period_days": 1e12, "mass_earth": 1e7}})}
    )
    at.run()
    assert not at.exception, at.exception


@pytest.mark.parametrize(
    "params",
    [
        {"edits": _raw('{"Kepler-36 b":{"period_days":1%s}}' % ("0" * 400))},
        {"whatif": _raw('{"planet":"Kepler-36 b","mass_factor":1%s}' % ("0" * 400))},
        {"edits": _raw("[" * 20000)},
        {  # OverflowError in the bounds of the period-ratio slider
            "edits": _b64({"Kepler-36 b": {"period_days": 1.0}, "Kepler-36 c": {"period_days": 1.7e308}}),
            "whatif": _b64({"planet": "Kepler-36 c", "mass_factor": 2.0}),
        },
    ],
)
def test_app_shows_no_traceback_for_more_crafted_links(params: dict[str, str]) -> None:
    # The whole page was a traceback with server paths, and no sidebar.
    at = AppTest.from_file(APP, default_timeout=60)
    at.query_params.update({"system": "Kepler-36", "source": "snapshot", **params})
    at.run()
    assert not at.exception, at.exception
    assert any("Part of this link could not be used" in w.value for w in at.warning)


def test_app_says_when_part_of_a_link_was_lost() -> None:
    # The same link with its last characters cut: MARGINAL instead of UNSTABLE, without a word (D28 keeps the fallback).
    good = _b64({"Kepler-36 b": {"mass_earth": 300.0}})
    at = AppTest.from_file(APP, default_timeout=120)
    at.query_params.update({**RUN_NOW, "edits": good})
    at.run()
    assert not any("could not be used" in w.value for w in at.warning)
    at = AppTest.from_file(APP, default_timeout=120)
    at.query_params.update({**RUN_NOW, "edits": good[:-7]})
    at.run()
    assert not at.exception, at.exception
    assert any(
        "Part of this link could not be used" in w.value and "table edits" in w.value for w in at.warning
    )
    assert any("Overall:" in m.value for m in at.markdown)


def test_a_name_from_a_link_is_not_markdown() -> None:
    # A clickable link and bold text inside the app's own error box, from the URL alone (D28: a link is untrusted).
    name = "[click here](http://127.0.0.1:8597/x) **Warning** :red[red text] `code` $x$ www.example.org"
    at = AppTest.from_file(APP, default_timeout=60)
    at.query_params.update({"system": name, "source": "snapshot"})
    at.run()
    assert not at.exception, at.exception
    text = at.error[0].value
    assert r"\[click here\]" in text and r"\*\*Warning\*\*" in text and r"\:red\[red text\]" in text
    assert r"\`code\`" in text and r"\$x\$" in text and r"www\.example\.org" in text
    assert "http://" not in text


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


def _select_slider(at: AppTest) -> Any:
    return next(s for s in at.select_slider if s.label.startswith("Mass"))


def _planet_box(at: AppTest) -> Any:
    return next(s for s in at.selectbox if s.label == "Planet")


def test_a_second_move_of_a_control_is_kept() -> None:
    # A widget whose value came from the state got a new identity after its first move, so the next value sent was
    # lost: 30, 30, 90, 90 in the state, with the thumb snapping back.
    at = _what_if_app("Kepler-36")
    state = at.session_state["state"]

    def slider(label: str) -> Any:
        return next(s for s in at.slider if s.label.startswith(label))

    for v in (30, 60, 90, 120):
        slider("Time budget").set_value(v).run()
        assert state.budget_s == v and slider("Time budget").value == v
    for e in (0.1, 0.2, 0.3, 0.4):
        slider("Eccentricity").set_value(e).run()
        assert at.session_state["state"].whatif.eccentricity == e and slider("Eccentricity").value == e
    for factor in (2.0, 3.0, 5.0, 7.0):
        _select_slider(at).set_value(factor).run()
        assert at.session_state["state"].whatif.mass_factor == factor and _select_slider(at).value == factor
    for seed in (1, 2, 3, 4):
        at.sidebar.number_input[0].set_value(seed).run()
        assert state.seed == seed and at.sidebar.number_input[0].value == seed
    prior = next(r for r in at.sidebar.radio if r.label.startswith("Minimum"))
    for choice in ("isotropic", "none", "isotropic"):
        prior.set_value(choice).run()
        prior = next(r for r in at.sidebar.radio if r.label.startswith("Minimum"))
        assert state.prior == choice and prior.value == choice
    _planet_box(at).select("Kepler-36 c").run()
    for ratio in (2.0, 3.0, 4.0, 9.5, 11.0):  # the upper end of this slider grows with the value
        slider("Period ratio").set_value(ratio).run()
        assert (
            at.session_state["state"].whatif.period_ratio == ratio and slider("Period ratio").value == ratio
        )
    assert not at.exception, at.exception
    # a move resets the run length of an earlier run, as before
    at = _what_if_app("Kepler-36", orbits="300", draws="2")
    assert at.session_state["state"].orbits == 300
    next(s for s in at.slider if s.label.startswith("Time budget")).set_value(30).run()
    assert at.session_state["state"].orbits is None


def test_a_what_if_is_not_carried_to_another_system() -> None:
    # Mass x 10 on TRAPPIST-1 went on to Kepler-36 b, where Run gave MARGINAL with close encounters in 9 of 10 draws;
    # Kepler-36 opened fresh is STABLE.
    at = _what_if_app("TRAPPIST-1")
    _select_slider(at).set_value(10.0).run()
    assert at.session_state["state"].whatif.mass_factor == 10.0
    at.sidebar.selectbox[0].select("Kepler-36").run()
    state = at.session_state["state"]
    assert state.system == "Kepler-36" and not state.whatif.is_active() and _select_slider(at).value == 1.0
    assert "whatif" not in _link(at)
    # the same for an eccentricity
    at = _what_if_app("Kepler-36")
    next(s for s in at.slider if s.label.startswith("Eccentricity")).set_value(0.5).run()
    at.sidebar.selectbox[0].select("TOI-178").run()
    assert not at.session_state["state"].whatif.is_active()
    assert _slider(at, "Eccentricity") < 0.5


def test_a_what_if_is_not_carried_to_another_planet() -> None:
    at = _what_if_app("Kepler-36")
    _select_slider(at).set_value(2.0).run()
    assert at.session_state["state"].whatif == WhatIf(planet="Kepler-36 b", mass_factor=2.0)
    _planet_box(at).select("Kepler-36 c").run()
    state = at.session_state["state"]
    assert (
        state.whatif.planet == "Kepler-36 c"
        and not state.whatif.is_active()
        and _select_slider(at).value == 1.0
    )
    _planet_box(at).select("Kepler-36 b").run()
    state = at.session_state["state"]
    assert (
        state.whatif.planet == "Kepler-36 b"
        and not state.whatif.is_active()
        and _select_slider(at).value == 1.0
    )
    assert not at.exception, at.exception


def test_what_if_from_a_link_is_shown_and_kept() -> None:
    at = _what_if_app(
        "Kepler-36", whatif=_b64({"planet": "Kepler-36 c", "mass_factor": 2.0, "eccentricity": 0.2})
    )
    assert _planet_box(at).value == "Kepler-36 c" and _select_slider(at).value == 2.0
    assert _slider(at, "Eccentricity") == 0.2
    at.run()
    assert at.session_state["state"].whatif == WhatIf(planet="Kepler-36 c", mass_factor=2.0, eccentricity=0.2)


def _edit_table(at: AppTest, edited_rows: dict[str, dict[str, float | None]]) -> Any:
    """Send what the browser sends for st.data_editor after a cell edit."""
    states = at._tree.get_widget_states()
    widget = states.widgets.add()
    widget.id = at.dataframe[0].proto.id
    widget.string_value = json.dumps({"edited_rows": edited_rows, "added_rows": [], "deleted_rows": []})
    return at._run(states)


def test_the_edit_after_filling_an_empty_column_is_kept() -> None:
    # 610 of the 1,034 modelled hosts have an all-empty omega column. Typing into it changed the column's type, and so
    # the widget's identity: the next edit was lost, and the mass of c snapped back.
    at = _what_if_app("Kepler-36")
    ident = at.dataframe[0].proto.id
    _edit_table(at, {"0": {"omega_deg": 90}})
    assert at.session_state["state"].edits == {"Kepler-36 b": {"omega_deg": 90.0}}
    assert at.dataframe[0].proto.id == ident
    _edit_table(at, {"0": {"omega_deg": 90}, "1": {"mass_earth": 9.0}})
    assert not at.exception, at.exception
    assert at.session_state["state"].edits == {
        "Kepler-36 b": {"omega_deg": 90.0},
        "Kepler-36 c": {"mass_earth": 9.0},
    }


def test_flags_of_a_replaced_value_are_dropped() -> None:
    # After an edit the page still said "Only an upper limit (25) is published; the nominal run uses the limit".
    s = load_system("Kepler-11")
    g = s.planet("g")
    assert (
        g.mass_earth.provenance is Provenance.UPPER_LIMIT
        and g.eccentricity.provenance is Provenance.UPPER_LIMIT
    )
    changed = apply_changes(
        s, {"Kepler-11 g": {"mass_earth": 3.0, "eccentricity": 0.1, "omega_deg": 45.0}}, WhatIf()
    )
    rules = {f.rule for f in changed.flags if f.planet == "Kepler-11 g"}
    assert rules == {"edited_in_web_app"} | {"phase_from_transit"}
    # other planets keep theirs, and the values of g are the typed ones, with no link to the paper
    assert {f.rule for f in s.flags if f.planet == "Kepler-11 b"} == {
        f.rule for f in changed.flags if f.planet == "Kepler-11 b"
    }
    mass = changed.planet("g").mass_earth
    assert mass.value == 3.0 and mass.reference == "edited in the web app" and mass.reference_url is None
    messages = " ".join(f.message for f in changed.flags if f.rule == "edited_in_web_app")
    assert "published upper limit: 25" in messages and "(published: 25)" not in messages
    # the what-if sliders replace values as well
    moved = apply_changes(s, {}, WhatIf(planet="Kepler-11 g", mass_factor=0.5, eccentricity=0.05))
    rules = {f.rule for f in moved.flags if f.planet == "Kepler-11 g"}
    assert not rules & {"mass_upper_limit", "eccentricity_upper_limit"} and "what_if_in_web_app" in rules


def test_a_minimum_mass_keeps_its_flag_when_edited() -> None:
    # The inclination prior still scales it, so the flag still holds.
    s = load_system("HD 127195")
    changed = apply_changes(s, {"HD 127195 b": {"mass_earth": 100.0}}, WhatIf())
    assert "minimum_mass" in {f.rule for f in changed.flags if f.planet == "HD 127195 b"}
    assert "omega_randomized" not in {
        f.rule
        for f in apply_changes(s, {"HD 127195 b": {"omega_deg": 10.0}}, WhatIf()).flags
        if f.planet == "HD 127195 b"
    }


def test_clearing_omega_says_that_a_phase_from_periastron_is_lost() -> None:
    # ups And c with omega cleared: its longitude went from about 240 deg in every run to anything, while the report
    # still said "set from the published time of periastron".
    s = load_system("ups And")
    c = s.planet("c")
    assert c.phase.kind is PhaseKind.PERIASTRON
    changed = apply_changes(s, {"ups And c": {"omega_deg": None}}, WhatIf())
    assert (
        changed.planet("c").phase.kind is PhaseKind.PERIASTRON
    )  # the random stream of the run stays as it was
    rules = {f.rule for f in changed.flags if f.planet == "ups And c"}
    assert "phase_random_without_omega" in rules and "phase_from_periastron" not in rules
    res = check_system(changed, CheckSettings(orbits=100, draws=0, jobs=1, ias15_check=False))
    note = next(n for n in res.report.indicators["nbody"].notes if "drawn at random" in n)
    assert "ups And c" in note


def test_edited_values_are_not_called_published_in_the_report() -> None:
    # Kepler-36 b edited to 300 M_earth: "... for 2 of 2 draws within the published uncertainties"
    s = load_system("Kepler-36")
    changed = apply_changes(s, {"Kepler-36 b": {"mass_earth": 300.0}}, WhatIf())
    res = check_system(changed, CheckSettings(orbits=300, draws=2, jobs=1, ias15_check=False))
    summary = res.report.overall.summary
    assert "values changed in the web app" in summary and "published uncertainties" not in summary
    plain = check_system(s, CheckSettings(orbits=300, draws=2, jobs=1, ias15_check=False))
    assert "changed in the web app" not in plain.report.overall.summary


def test_the_table_marks_upper_limits_and_the_assumptions_come_before_run() -> None:
    # Masses of 565 to 975 M_earth with Mass kind "true" and e = 0, and no word about them before Run.
    rows = {r["planet"]: r for r in planet_rows(load_system("Kepler-11"))}
    assert rows["Kepler-11 g"]["mass_kind"] == "upper limit" and rows["Kepler-11 b"]["mass_kind"] == "true"
    at = _what_if_app("Kepler-11")
    table = at.dataframe[0].value
    assert list(table[table["planet"] == "Kepler-11 g"]["mass_kind"]) == ["upper limit"]
    assert any("upper limit" in w.value for w in at.warning)
    assert any(e.label.startswith("Data completion") and not e.proto.expanded for e in at.expander)
    # after a run the flags are in the results, once
    next(b for b in at.button if b.label == "Run")
    at = _what_if_app("Kepler-11", orbits="100", draws="1", run="1")
    assert sum(e.label.startswith("Data completion") for e in at.expander) == 1


def test_a_link_with_spock_says_when_spock_is_not_available(monkeypatch: pytest.MonkeyPatch) -> None:
    # No message; the share link kept spock=1, and the input hash differed from the same run without it.
    monkeypatch.delenv("EXOSTAB_SPOCK_PYTHON", raising=False)
    at = _what_if_app("TOI-270", orbits="100", draws="1", run="1", spock="1")
    assert any("asked for SPOCK" in w.value and "not available" in w.value for w in at.sidebar.warning)
    assert "spock" not in _link(at) and not at.session_state["state"].spock
    without = _what_if_app("TOI-270", orbits="100", draws="1", run="1")
    assert _caption(at).split("Input hash")[1] == _caption(without).split("Input hash")[1]


def test_browser_messages_do_not_mention_options() -> None:
    # "increase --orbits", "supply measured phases with --from-file", "unless --inclination-prior is set", "(--draws 0)"
    for params in (
        {"system": "Kepler-36", "orbits": "100", "draws": "1", "run": "1"},
        {"system": "GJ 876", "orbits": "100", "draws": "0", "run": "1"},
        {"system": "HD 127195", "orbits": "100", "draws": "1", "run": "1"},
    ):
        at = AppTest.from_file(APP, default_timeout=120)
        at.query_params.update({"source": "snapshot", **params})
        at.run()
        for element in (*at.markdown, *at.caption, *at.warning, *at.error):
            assert "--" not in element.value, element.value


def test_web_page_on_the_input_hash() -> None:
    # Identical runs can have different hashes: the budget's run length, and the same one from a link.
    page = Path(APP).parent / "docs" / "web.md"
    if not page.is_file():
        pytest.skip("this page is not in the sdist")
    text = " ".join(page.read_text(encoding="utf-8").split())
    assert "The same input hash means the same inputs" in text
    assert "tell whether two runs used the same inputs" not in text


def _table_rows() -> list[dict[str, Any]]:
    """An "archive" table: the snapshot, and one system that only the archive has."""
    rows, _ = store.load_snapshot()
    kepler = [r for r in rows if r["hostname"] == "Kepler-36"]
    extra = [
        {**r, "hostname": "Extra-1", "pl_name": str(r["pl_name"]).replace("Kepler-36", "Extra-1")}
        for r in kepler
    ]
    alias = [
        {**r, "hostname": "Alias-1", "pl_name": str(r["pl_name"]).replace("Kepler-36", "Other name")}
        for r in kepler
    ]
    return [*rows, *extra, *alias]


@pytest.fixture
def archive_up(monkeypatch: pytest.MonkeyPatch) -> Iterator[list[str]]:
    """The app with a working "archive" (a record of its queries is yielded)."""
    import streamlit as st

    calls: list[str] = []

    def fetch(where: str) -> list[dict[str, Any]]:
        calls.append(where)
        return _table_rows()

    monkeypatch.delenv("EXOSTAB_OFFLINE")
    monkeypatch.setattr(store, "fetch_rows", fetch)
    st.cache_data.clear()
    yield calls
    st.cache_data.clear()


def _data_label(at: AppTest) -> str:
    return next(c.value for c in at.caption if c.value.startswith("Data:"))


def test_switching_the_source_updates_the_page(archive_up: list[str]) -> None:
    # The caption still said archive-cache and the box still had every name, while the table came from the snapshot.
    at = AppTest.from_file(APP, default_timeout=60)
    at.query_params.update({"system": "Kepler-36"})
    at.run()
    assert "archive" in _data_label(at) and len(at.sidebar.selectbox[0].options) == 24
    at.sidebar.radio[0].set_value("snapshot").run()
    assert not at.exception, at.exception
    assert "snapshot" in _data_label(at) and len(at.sidebar.selectbox[0].options) == 22
    assert at.sidebar.selectbox[0].value == "Kepler-36"
    # a pick from the list is not dropped
    at.sidebar.selectbox[0].select("TRAPPIST-1").run()
    assert at.session_state["state"].system == "TRAPPIST-1" and "7 planets" in _data_label(at)
    at.sidebar.radio[0].set_value("archive").run()
    assert "archive" in _data_label(at) and len(at.sidebar.selectbox[0].options) == 24
    assert at.sidebar.selectbox[0].value == "TRAPPIST-1"


def test_a_system_only_the_archive_has_comes_back_in_the_box(archive_up: list[str]) -> None:
    # To the snapshot and back left a blank box.
    at = AppTest.from_file(APP, default_timeout=60)
    at.query_params.update({"system": "Extra-1"})
    at.run()
    assert at.sidebar.selectbox[0].value == "Extra-1" and not at.error
    at.sidebar.radio[0].set_value("snapshot").run()
    assert at.sidebar.selectbox[0].value is None and at.error and "offline snapshot" in at.error[0].value
    at.sidebar.radio[0].set_value("archive").run()
    assert not at.exception, at.exception
    assert at.sidebar.selectbox[0].value == "Extra-1" and not at.error


def test_the_link_follows_the_page_after_an_error(archive_up: list[str]) -> None:
    # Error shown, but the link stayed at the old state: reopening it went back and ran the old system.
    at = AppTest.from_file(APP, default_timeout=120)
    at.query_params.update({"system": "Extra-1", "orbits": "100", "draws": "1", "run": "1"})
    at.run()
    assert _link(at)["run"] == "1"
    at.sidebar.radio[0].set_value("snapshot").run()
    assert at.error
    link = _link(at)
    assert link["source"] == "snapshot" and link["system"] == "Extra-1" and "run" not in link
    at = AppTest.from_file(APP, default_timeout=120)
    at.query_params.update(
        {"system": "Kepler-36", "source": "snapshot", "orbits": "100", "draws": "1", "run": "1"}
    )
    at.run()
    at.sidebar.selectbox[0].select("Kepler-47").run()
    assert at.error and "circumbinary" in at.error[0].value
    link = _link(at)
    assert link["system"] == "Kepler-47" and "run" not in link


def test_the_search_box_shows_the_host_of_another_name(archive_up: list[str]) -> None:
    # ?system=Kepler-36 b resolved and ran, with a blank search box; and a host under another name must not count as
    # a new pick, which would end the run.
    for name, host in (("Kepler-36 b", "Kepler-36"), ("Other name", "Alias-1")):
        at = AppTest.from_file(APP, default_timeout=120)
        at.query_params.update({"system": name, "orbits": "100", "draws": "1", "run": "1"})
        at.run()
        assert not at.exception, at.exception
        assert at.sidebar.selectbox[0].value == host, name
        assert at.session_state["state"].run and any("Overall:" in m.value for m in at.markdown)
        at.run()
        assert at.session_state["state"].run and at.session_state["state"].system == name


def test_an_outage_on_first_use_ends_a_few_minutes_after_the_archive_is_back(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # The fallback was cached like a good table: the app stayed on 22 systems for a day.
    import streamlit as st

    import exostab.web.app as web_app

    calls: list[str] = []

    def outage(where: str) -> None:
        calls.append(where)
        raise archive.ArchiveError("simulated outage")

    monkeypatch.delenv("EXOSTAB_OFFLINE")
    monkeypatch.setattr(store, "fetch_rows", outage)
    st.cache_data.clear()
    try:
        at = AppTest.from_file(APP, default_timeout=60)
        at.query_params.update({"system": "TRAPPIST-1"})
        at.run()
        assert len(at.sidebar.selectbox[0].options) == 22 and len(calls) == 1
        # within those minutes no new query is made: another visit does not wait for three more failed attempts
        at = AppTest.from_file(APP, default_timeout=60)
        at.query_params.update({"system": "TRAPPIST-1"})
        at.run()
        assert len(calls) == 1
        monkeypatch.setattr(store, "fetch_rows", lambda where: _table_rows())
        web_app._load_table.clear()  # what the end of the short time-to-live does
        at = AppTest.from_file(APP, default_timeout=60)
        at.query_params.update({"system": "TRAPPIST-1"})
        at.run()
        assert not at.exception, at.exception
        assert len(at.sidebar.selectbox[0].options) == 24 and "archive" in _data_label(at)
    finally:
        st.cache_data.clear()


def test_app_survives_a_cache_folder_that_cannot_be_written(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, archive_up: list[str]
) -> None:
    # A full-page traceback, and no sidebar, on a read-only home folder.
    blocker = tmp_path / "blocker"
    blocker.write_text("x")
    monkeypatch.setenv("EXOSTAB_CACHE_DIR", str(blocker / "cache"))
    at = AppTest.from_file(APP, default_timeout=60)
    at.query_params.update({"system": "Extra-1"})
    at.run()
    assert not at.exception, at.exception
    assert len(archive_up) == 1 and len(at.sidebar.selectbox[0].options) == 24


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


def test_page_says_when_a_budget_cannot_be_met(fake_budget, monkeypatch: pytest.MonkeyPatch) -> None:  # type: ignore[no-untyped-def]
    # HD 187123 b at e = 0.9, budget 5 s: "computed in 10.4 s", and the plan's warning was not on the page.
    import exostab.web.app as web_app

    plan = web_app.settings_for_budget

    def too_slow(system, budget_s, base):  # type: ignore[no-untyped-def]
        settings, p = plan(system, budget_s, base)
        return settings, replace(
            p, warning="Even the smallest run needs about 12 s, more than the 5 s budget."
        )

    monkeypatch.setattr(web_app, "settings_for_budget", too_slow)
    at = AppTest.from_file(APP, default_timeout=120)
    at.query_params.update({"system": "Kepler-36", "source": "snapshot", "budget": "5"})
    at.run()
    next(b for b in at.button if b.label == "Run").click().run()
    assert not at.exception, at.exception
    assert any("Even the smallest run" in w.value for w in at.warning)


def test_page_says_when_a_kept_run_length_exceeds_the_budget(fake_budget) -> None:  # type: ignore[no-untyped-def]
    # Run at 10 s, then the e slider to 0.7: the automatic rerun took 26 s with no note.
    at = AppTest.from_file(APP, default_timeout=120)
    at.query_params.update(
        {
            "system": "Kepler-36",
            "source": "snapshot",
            "budget": "5",
            "orbits": "300",
            "draws": "2",
            "run": "1",
        }
    )
    at.run()
    assert not at.exception, at.exception
    assert fake_budget[-1] == (300.0, 2, None)  # the run length itself is unchanged
    assert any("more than the 5 s budget" in w.value and "Press Run" in w.value for w in at.warning)
    # within the budget there is nothing to say
    at = AppTest.from_file(APP, default_timeout=120)
    at.query_params.update(
        {
            "system": "Kepler-36",
            "source": "snapshot",
            "budget": "30",
            "orbits": "300",
            "draws": "2",
            "run": "1",
        }
    )
    at.run()
    assert not any("Press Run" in w.value for w in at.warning)


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
