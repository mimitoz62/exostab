"""exostab web app (Streamlit).

    python -m exostab.web            # or, in a clone of the repository: streamlit run streamlit_app.py

Both need the [web] extra (Streamlit and Plotly); docs/quickstart.md gives the install command.

Search a system, edit its parameters, choose a time budget and run the same analysis as ``exostab check``.
The run length chosen for a budget and the results are cached by a hash of every input, so a repeated view
(or a shared link opened on the same server) is instant. Integrations run in a single process: hosted apps
have one or two CPUs, and a process pool inside a Streamlit server is fragile. A shared link's run length is
used only if its estimated cost on this server is within the largest time budget.
"""

from __future__ import annotations

import io
import json
import math
import re
from dataclasses import asdict
from typing import Any

import pandas as pd  # type: ignore[import-untyped]
import streamlit as st
from pydantic import ValidationError

from .. import __version__
from ..analysis import CheckResult, CheckSettings, check_system, settings_for_budget
from ..budget import estimate_seconds
from ..data import IncompleteSystemError, TableInfo, find_host, load_rows, system_from_rows
from ..data.archive import ArchiveError, group_by_host
from ..data.completion import invalid_message
from ..data.names import SystemNotFoundError, other_names
from ..indicators import Verdict
from ..indicators.spock import SpockUnavailableError, spock_python
from ..models import MASS_MAX_EARTH, PERIOD_MAX_DAYS, PERIOD_MIN_DAYS, System, UnusableParametersError
from ..plots import megno_figure, orbits_figure
from ..report import ACKNOWLEDGMENT, group_flags, system_flags
from ..sampling import E_MAX
from . import figures
from .state import (
    BUDGET_MAX,
    BUDGET_MIN,
    EDITABLE,
    MASS_FACTORS,
    MASS_MIN_EARTH,
    PERIOD_RATIO_MAX,
    SEED_MAX,
    AppState,
    WhatIf,
    apply_changes,
    decode_state,
    edited_rows,
    encode_state,
    input_hash,
    share_url,
    table_edits,
)

REPO = "https://github.com/mimitoz62/exostab"
DOCS = "https://mimitoz62.github.io/exostab/"  # the documentation site (docs.yml)
BADGE = {
    Verdict.STABLE: "green",
    Verdict.MARGINAL: "orange",
    Verdict.UNSTABLE: "red",
    Verdict.INCONCLUSIVE: "gray",
}
ICON = {
    Verdict.STABLE: ":material/check_circle:",
    Verdict.MARGINAL: ":material/warning:",
    Verdict.UNSTABLE: ":material/cancel:",
    Verdict.INCONCLUSIVE: ":material/help:",
}


ArchiveTable = tuple[dict[str, list[dict[str, Any]]], str, str | None, str | None]
RETRY_ARCHIVE_S = 300  # how long the app stays on the snapshot after a failed query before it tries again


class _ArchiveFallbackError(Exception):
    """The archive failed and the snapshot came instead. Raised because st.cache_data caches no exception."""


@st.cache_data(show_spinner=False, ttl=RETRY_ARCHIVE_S)
def _load_table(source: str) -> ArchiveTable:
    """Rows grouped by host, the data kind, retrieval time and any note. Kept only for a few minutes, because this
    can be the snapshot during an outage; :func:`_good_table` keeps the good result for a day."""
    try:
        rows, info = load_rows(offline=source == "snapshot")
    except ArchiveError:
        rows, info = load_rows(offline=True)
    return group_by_host(rows), info.kind, info.retrieved_utc, info.note


@st.cache_data(show_spinner=False, ttl=24 * 3600)
def _good_table(source: str) -> ArchiveTable:
    table = _load_table(source)
    if source == "archive" and table[1] == "snapshot":
        raise _ArchiveFallbackError
    return table


def _archive(source: str) -> ArchiveTable:
    """The table of a data source: the good one, or for now the snapshot, until the archive answers again."""
    try:
        return _good_table(source)
    except _ArchiveFallbackError:
        return _load_table(source)


def _info(kind: str, retrieved: str | None, note: str | None) -> TableInfo:
    return TableInfo(kind=kind, retrieved_utc=retrieved, path=None, note=note)  # type: ignore[arg-type]


def _system(source: str, name: str) -> System:
    hosts, kind, retrieved, note = _archive(source)
    info = _info(kind, retrieved, note)
    return system_from_rows(hosts[find_host(name, hosts, info)], info)


def _host(state: AppState) -> str | None:
    """The host that ``state.system`` means, which can be another name of it, or None if there is none."""
    hosts, kind, retrieved, note = _archive(state.source)
    try:
        return find_host(state.system, hosts, _info(kind, retrieved, note))
    except SystemNotFoundError:
        return None


_MARKDOWN = re.compile(
    r"([\\`*_\[\]~:$<>&.])"
)  # what can start a link, emphasis, math, a directive or an entity


def _literal(text: str) -> str:
    """``text`` as it is, in an element that renders Markdown: a link can carry a system name, which must not become
    a link or bold text in the app's own error box (DECISIONS.md, D28)."""
    return _MARKDOWN.sub(r"\\\1", text)


def _moved(key: str) -> Any:
    """The value of the widget ``key`` if the user changed it since :func:`_show` last set it, otherwise None."""
    value = st.session_state.get(key)
    return value if value is not None and value != st.session_state.get(f"{key}:shown", value) else None


def _show(key: str, value: Any) -> None:
    """Have the widget ``key`` show ``value``. AppState decides what a control shows, so the widgets are told through
    their keys, in the same way on every run. A widget whose ``value`` argument follows the state gets a new identity
    when it is moved, and Streamlit then drops the next value the browser sends for the old one."""
    st.session_state[key] = st.session_state[f"{key}:shown"] = value


@st.cache_data(show_spinner=False, max_entries=256)
def _plan(system_json: str, settings_json: str) -> tuple[float, int, float, float, str | None]:
    """Orbits and draws chosen for the time budget on this server, the measured seconds per orbit of WHFast and
    IAS15, and a warning if not even the smallest run fits. Cached by its inputs, because the choice depends on the
    measured speed."""
    system = System.model_validate_json(system_json)
    s = json.loads(settings_json)
    base = CheckSettings(seed=s["seed"], inclination_prior=s["prior"], jobs=1)
    _, p = settings_for_budget(system, float(s["budget_s"]), base)
    return p.orbits, p.draws, p.whfast_s_per_orbit, p.ias15_s_per_orbit, p.warning


def _run_settings(state: AppState, system_json: str) -> tuple[dict[str, Any], str | None]:
    """Settings of the run and a note for the user.

    The run length is the one chosen for the time budget on this server, unless the state already carries
    one (a shared link, or the previous run while parameters are edited) whose estimated cost here is within
    BUDGET_MAX; budget_s is recorded only when the budget chose the run length. The cache key of the run is
    computed from these resolved settings, so the view after a budget run finds its result.
    """
    budget = {"seed": state.seed, "prior": state.prior, "budget_s": state.budget_s}
    orbits, draws, s_wh, s_ias, warning = _plan(system_json, json.dumps(budget, sort_keys=True))
    budget_s: float | None = state.budget_s
    note = warning
    if (
        state.orbits is not None
        and state.draws is not None
        and (state.orbits, state.draws) != (orbits, draws)
    ):
        cost = estimate_seconds(state.orbits, state.draws, s_wh, s_ias, workers=1)
        if cost <= BUDGET_MAX:
            orbits, draws, budget_s, note = state.orbits, state.draws, None, None
            if cost > state.budget_s:
                note = (
                    f"This run length ({orbits:,.0f} orbits, {draws} draws) comes from the previous run or the link. It "
                    f"takes about {cost:,.0f} s on this server, more than the {state.budget_s:g} s budget. Press Run "
                    "to choose a run length for the budget."
                )
        else:
            note = (
                f"The requested run ({state.orbits:,.0f} orbits, {state.draws} draws) would take about "
                f"{cost:,.0f} s on this server, more than the {BUDGET_MAX} s limit, so the run length was "
                f"chosen for the {state.budget_s:g} s budget instead." + (f" {warning}" if warning else "")
            )
    settings = {
        "seed": state.seed,
        "prior": state.prior,
        "budget_s": budget_s,
        "orbits": orbits,
        "draws": draws,
        "spock": state.spock,
    }
    return settings, note


@st.cache_data(show_spinner=False, max_entries=64)
def _run(system_json: str, settings_json: str, key: str) -> CheckResult:
    """The analysis, cached by the input hash ``key`` (the JSON arguments are the inputs themselves)."""
    system = System.model_validate_json(system_json)
    s = json.loads(settings_json)
    spock = spock_python() if s.get("spock") else None
    settings = CheckSettings(
        orbits=s["orbits"],
        draws=s["draws"],
        seed=s["seed"],
        inclination_prior=s["prior"],
        jobs=1,
        n_samples=300,
        budget_s=s["budget_s"],
        spock_python=spock,
    )
    result = check_system(system, settings, command=f"exostab web app {__version__} (input {key[:12]})")
    result.extra["input_hash"] = key
    return result


def _state_from_url() -> AppState:
    if "state" not in st.session_state:
        st.session_state.state = decode_state({k: st.query_params[k] for k in st.query_params})
    state: AppState = st.session_state.state
    return state


def _verdict_badge(v: Verdict, label: str) -> None:
    st.badge(f"{label}: {v.value}", icon=ICON[v], color=BADGE[v])  # type: ignore[arg-type]


def _labels(hosts: dict[str, list[dict[str, Any]]]) -> dict[str, str]:
    """What the search box shows: a host with its other names, so that typing "Kepler-90" finds KOI-351."""
    labels = {}
    for host, rows in hosts.items():
        also = other_names(host, (str(r["pl_name"]) for r in rows), hosts)
        labels[host] = f"{host} ({', '.join(also)})" if also else host
    return labels


def _source_changed(state: AppState) -> None:
    """Callback of the data radio. It runs before the page, so that the names and the data label follow the new
    source, and the search box shows the system if the new table has it."""
    state.source, state.run = st.session_state["source_radio"], False
    st.session_state["system_select"] = _host(state)


def _sidebar(state: AppState, names: list[str], labels: dict[str, str]) -> None:
    with st.sidebar:
        st.header("System")
        host = _host(state)
        st.session_state.setdefault("system_select", host)
        if st.session_state["system_select"] not in names:  # the table was refreshed, or it is empty so far
            st.session_state["system_select"] = None
        choice = st.selectbox(
            "Search the archive (type to filter)",
            names,
            index=None,
            format_func=labels.__getitem__,
            placeholder="e.g. TRAPPIST-1",
            key="system_select",
        )
        if choice and choice != host:
            state.system, state.edits, state.whatif, state.run = choice, {}, WhatIf(), False
            state.orbits = state.draws = None
            state.dropped = []
        st.session_state.setdefault("source_radio", state.source)
        st.radio(
            "Data",
            ["archive", "snapshot"],
            format_func=lambda s: (
                "NASA Exoplanet Archive (cached copy)" if s == "archive" else "Offline snapshot (22 systems)"
            ),
            key="source_radio",
            on_change=_source_changed,
            args=(state,),
        )
        st.divider()
        st.header("Run")
        budget, seed, prior = _moved("budget_slider"), _moved("seed_input"), _moved("prior_radio")
        if budget is not None or seed is not None or prior is not None:
            state.orbits = state.draws = None
        state.budget_s = state.budget_s if budget is None else float(budget)
        state.seed = state.seed if seed is None else int(seed)
        state.prior = state.prior if prior is None else prior
        _show("budget_slider", int(state.budget_s))
        st.slider(
            "Time budget (s)",
            BUDGET_MIN,
            BUDGET_MAX,
            step=5,
            help="About 10 s is a quick look; about 120 s runs longer integrations and more draws.",
            key="budget_slider",
        )
        _show("seed_input", int(state.seed))
        st.number_input(
            "Seed",
            min_value=0,
            max_value=SEED_MAX,
            step=1,
            help="The same seed gives the same draws.",
            key="seed_input",
        )
        _show("prior_radio", state.prior)
        st.radio(
            "Minimum masses (m sin i)",
            ["none", "isotropic"],
            format_func=lambda p: (
                "use m sin i as the mass" if p == "none" else "draw inclinations (isotropic)"
            ),
            key="prior_radio",
        )
        if spock_python():
            spock = _moved("spock_box")
            state.spock = state.spock if spock is None else spock
            _show("spock_box", state.spock)
            st.checkbox(
                "Add SPOCK (machine-learned, 3+ planets)",
                help="Uses the SPOCK environment set in EXOSTAB_SPOCK_PYTHON.",
                key="spock_box",
            )
        elif state.spock:
            st.warning(
                "This link asked for SPOCK, which is not available on this server. The run is without it."
            )
            state.spock = False
        st.divider()
        st.caption(f"exostab {__version__} · [documentation]({DOCS}) · [source]({REPO})")
        st.link_button(
            "Report a problem or request a system", f"{REPO}/issues/new/choose", icon=":material/feedback:"
        )


def _parameters(state: AppState, system: System) -> System:
    st.subheader("Parameters")
    st.caption(
        "Edit any value; leave ω empty to draw it at random. Published uncertainties are kept for the "
        "Monte Carlo draws. Every change is listed in the report."
    )
    # The table is another widget if its data change: a new column type (typing into a column that is empty for every
    # planet) or, in older Streamlit versions, any new value. So the widget gets float columns and the same data for
    # as long as it is on the page, and holds the edits itself.
    table_key = f"table_{state.system}_{state.source}"
    if table_key not in st.session_state:
        st.session_state[f"{table_key}:data"] = pd.DataFrame(edited_rows(system, state.edits)).astype(
            dict.fromkeys(EDITABLE, "float64")
        )
    edited = st.data_editor(
        st.session_state[f"{table_key}:data"],
        key=table_key,
        hide_index=True,
        disabled=["planet", "mass_kind", "phase"],
        column_config={
            "planet": st.column_config.TextColumn("Planet"),
            "period_days": st.column_config.NumberColumn(
                "P (days)", min_value=PERIOD_MIN_DAYS, max_value=PERIOD_MAX_DAYS, format="%.6g"
            ),
            "mass_earth": st.column_config.NumberColumn(
                "Mass (M⊕)", min_value=MASS_MIN_EARTH, max_value=MASS_MAX_EARTH, format="%.4g"
            ),
            "mass_kind": st.column_config.TextColumn("Mass kind"),
            "eccentricity": st.column_config.NumberColumn("e", min_value=0.0, max_value=E_MAX, format="%.4g"),
            "omega_deg": st.column_config.NumberColumn("ω (deg)", format="%.4g"),
            "phase": st.column_config.TextColumn("Phase from"),
        },
    )
    state.edits = table_edits(system, edited.to_dict("records"))
    rows = {r["planet"]: r for r in edited_rows(system, state.edits)}  # the table as it is now
    with st.expander("What if? Adjust one planet", expanded=state.whatif.is_active()):
        names = [p.name for p in system.planets]
        cur = state.whatif
        # Keys with the system, the source and the planet: another system or planet gets new widgets at their
        # defaults, and a value moved on one is not applied to the next.
        scope = f"{state.system}|{state.source}"
        st.session_state.setdefault(f"whatif_planet|{scope}", cur.planet if cur.planet in names else names[0])
        planet = st.selectbox("Planet", names, key=f"whatif_planet|{scope}")
        scope = f"{scope}|{planet}"
        row, mine = rows[planet], cur.planet == planet
        c1, c2, c3 = st.columns(3)
        factor = _moved(f"whatif_factor|{scope}")
        if factor is None:
            factor = cur.mass_factor if mine and cur.mass_factor in MASS_FACTORS else 1.0
        _show(f"whatif_factor|{scope}", factor)
        c1.select_slider("Mass × factor", options=MASS_FACTORS, key=f"whatif_factor|{scope}")
        # A slider sets a what-if value only when it is moved (or the value came with the link): a table value
        # outside the slider's range is shown at the end of the range, and is not changed by being shown.
        e_table = float(row["eccentricity"] or 0.0)
        e_set = cur.eccentricity if mine else None
        ecc = _moved(f"whatif_e|{scope}")
        if ecc is not None:
            e_set = None if abs(ecc - e_table) < 5e-3 else ecc
        _show(f"whatif_e|{scope}", min(e_table if e_set is None else e_set, E_MAX))
        c2.slider("Eccentricity", 0.0, E_MAX, step=0.01, key=f"whatif_e|{scope}")
        # The inner neighbour comes from the edited periods, as in apply_changes.
        ratio = cur.period_ratio if mine else None
        if not all(r["period_days"] is not None and r["period_days"] > 0 for r in rows.values()):
            c3.caption("A period ratio needs a positive period for every planet.")
        else:
            order = sorted(rows.values(), key=lambda r: float(r["period_days"]))
            k = [r["planet"] for r in order].index(planet)
            if k == 0:
                c3.caption("The innermost planet has no inner neighbour.")
                ratio = None
            else:
                r_table = row["period_days"] / order[k - 1]["period_days"]
                ratio_key = f"whatif_ratio|{scope}|{order[k - 1]['planet']}"
                moved = _moved(ratio_key)
                if moved is not None:
                    ratio = None if abs(moved - r_table) < 5e-3 else moved
                r_shown = r_table if ratio is None else ratio
                hi = float(max(10, math.ceil(1.2 * min(max(r_table, r_shown), PERIOD_RATIO_MAX))))
                _show(ratio_key, min(max(r_shown, 1.01), hi))
                c3.slider(f"Period ratio to {order[k - 1]['planet']}", 1.01, hi, step=0.01, key=ratio_key)
        state.whatif = WhatIf(
            planet=planet, mass_factor=float(factor), eccentricity=e_set, period_ratio=ratio
        )
    return apply_changes(system, state.edits, state.whatif)


def _data_completion(flags: list[tuple[str, str]], *, expanded: bool) -> None:
    if flags:
        with st.expander(f"Data completion: {len(flags)} rule(s) applied", expanded=expanded):
            for who, msg in flags:
                st.warning(f"**{who}**: {msg}", icon=":material/info:")


def _error_text(exc: Exception) -> str:
    """Why the analysis cannot use the values, in plain words: its own messages are not for the page."""
    if isinstance(exc, UnusableParametersError):
        return str(exc)
    if isinstance(exc, ValidationError):
        return invalid_message(exc)
    return "a value is outside what exostab can compute. Check the values in the table and in the what-if sliders."


def _results(result: CheckResult, state: AppState) -> None:
    rep = result.report
    st.subheader("Result")
    st.markdown(f"### Overall: **{rep.overall.verdict.value.upper()}**")
    _verdict_badge(rep.overall.verdict, "overall")
    st.write(rep.overall.summary)
    cols = st.columns(len(rep.indicators))
    for col, ind in zip(cols, rep.indicators.values(), strict=True):
        with col, st.container(border=True):
            _verdict_badge(ind.verdict, ind.title)
            st.write(ind.summary)
            if ind.draws:
                d = ind.draws
                st.caption(
                    f"Draws: {d.stable} stable, {d.marginal} marginal, {d.unstable} unstable"
                    + (f", {d.inconclusive} inconclusive" if d.inconclusive else "")
                )
            for note in ind.notes:
                st.caption("• " + note)
    s = rep.settings
    if s.orbits < 1e4:
        st.warning(
            f"This run covers {s.orbits:,.0f} orbits of the innermost planet, fewer than the 10,000 of exostab check "
            "and the catalog. A short run has less time to show chaos, so its N-body verdict can look better than a "
            "longer one."
        )
    st.caption(
        f"N-body: {s.orbits:,.0f} orbits of the innermost planet ({s.t_end_yr:,.4g} yr), {s.draws} draws, seed "
        f"{s.seed}"
        + (f", chosen for a {s.budget_s:g} s budget" if s.budget_s else "")
        + f"; computed in {rep.runtime_s:.1f} s. Input hash {str(result.extra.get('input_hash', ''))[:12]}."
    )
    _data_completion(group_flags(rep), expanded=True)
    if rep.data.note:
        st.warning(rep.data.note)
    t1, t2, t3 = st.tabs(["Orbits", "MEGNO over time", "Draws"])
    with t1:
        st.plotly_chart(
            figures.orbits(result.realizations[0], result.runs[0], rep.system.name), width="stretch"
        )
    with t2:
        st.plotly_chart(figures.megno_time(result.runs[0], result.ias15, rep.system.name), width="stretch")
    with t3:
        st.plotly_chart(figures.megno_draws(result.runs), width="stretch")
    st.subheader("Download and share")
    d1, d2, d3 = st.columns(3)
    d1.download_button(
        "report.json",
        rep.to_json(),
        file_name="report.json",
        mime="application/json",
        on_click="ignore",
        icon=":material/download:",
    )
    d2.download_button(
        "orbits.png",
        _png(result, "orbits"),
        file_name="orbits.png",
        mime="image/png",
        on_click="ignore",
        icon=":material/download:",
    )
    d3.download_button(
        "megno.png",
        _png(result, "megno"),
        file_name="megno.png",
        mime="image/png",
        on_click="ignore",
        icon=":material/download:",
    )
    state.orbits, state.draws = s.orbits, s.draws
    base = st.context.url or "http://localhost:8501"
    st.caption(
        "Shareable link (same settings; the archive data and, for a long run, the run length can differ on "
        "the server that opens it; use the copy button):"
    )
    st.code(share_url(base, state), language=None, wrap_lines=True)


def _png(result: CheckResult, which: str) -> bytes:
    buf = io.BytesIO()
    name = result.report.system.name
    if which == "orbits":
        orbits_figure(result.realizations[0], result.runs[0], name, buf)
    else:
        megno_figure(result.runs, result.ias15, name, buf)
    return buf.getvalue()


def main() -> None:
    st.set_page_config(
        page_title="exostab: is this planetary system stable?", page_icon=":material/public:", layout="wide"
    )
    state = _state_from_url()
    try:
        _page(state)
    finally:
        # On every path, the errors included: a reload must not go back to the state before the last change.
        st.query_params.from_dict(encode_state(state))


def _page(state: AppState) -> None:
    st.title("exostab")
    st.write(
        "Is this planetary system dynamically stable? Three indicators (Hill spacing, angular momentum "
        "deficit, N-body integration with MEGNO) for multi-planet systems in the NASA Exoplanet Archive, "
        "with every assumption shown."
    )
    if state.dropped:
        st.warning(
            f"Part of this link could not be used, so the defaults apply instead: {', '.join(state.dropped)}."
        )
    hosts, kind, retrieved, _ = _archive(state.source)
    names = sorted(hosts, key=str.lower)
    _sidebar(state, names, _labels(hosts))
    try:
        system = _system(state.source, state.system)
    except SystemNotFoundError as exc:
        text = str(exc)
        if exc.cli_hint:
            text = text.replace(exc.cli_hint, "The search box in the sidebar lists the names.")
        st.error(_literal(text))
        return
    except IncompleteSystemError as exc:
        st.error(_literal(f"This system cannot be checked: {exc}"))
        return
    st.caption(f"Data: {kind} ({(retrieved or '')[:10]}), table pscomppars, {len(system.planets)} planets.")
    try:
        modified = _parameters(state, system)
    except ValueError as exc:
        st.error(_literal(f"Invalid parameters: {exc}"))
        return
    assumptions = st.container()
    run_clicked = st.button("Run", type="primary", icon=":material/play_arrow:")
    if not (run_clicked or state.run):
        with assumptions:
            _data_completion(system_flags(modified), expanded=False)
    if run_clicked:
        state.orbits = state.draws = None
    if run_clicked or state.run:
        state.run = True
        system_json = modified.model_dump_json()
        try:
            with st.spinner("Integrating… (cached results appear instantly)"):
                settings, note = _run_settings(state, system_json)
                key = input_hash(modified, settings)
                result = _run(system_json, json.dumps(settings, sort_keys=True), key)
        except SpockUnavailableError as exc:
            # failures are not cached: switch SPOCK and the automatic run off, or every rerun repeats the call
            state.spock = state.run = False
            st.error(
                f"SPOCK could not be run, so it has been switched off: {exc}. Press Run to check without it."
            )
        except (ValueError, ArithmeticError) as exc:
            # parameters the analysis refuses or cannot integrate (for example extreme values typed into the
            # table); not cached either, so the automatic run is switched off
            state.run = False
            st.error(_literal(f"These parameters cannot be checked: {_error_text(exc)}"))
        else:
            if note:
                st.warning(note)
            _results(result, state)
    st.divider()
    st.caption(ACKNOWLEDGMENT)
    st.caption(
        "Parameters: NASA Exoplanet Archive, Planetary Systems Composite Parameters (doi:10.26133/NEA13). "
        "The underlying publications are listed in report.json."
    )


def _debug_state(state: AppState) -> dict[str, Any]:  # pragma: no cover - development aid
    return asdict(state)
