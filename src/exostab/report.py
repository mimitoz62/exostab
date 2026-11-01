"""The report: a versioned JSON record of a check and the terminal report card.

``SCHEMA_VERSION`` follows semantic versioning: the minor number grows when fields are added, the major
number when fields are renamed or removed. The JSON Schema of the current version is shipped as
``exostab/schemas/report.schema.json`` (regenerate with ``python -m exostab.report``).

JSON has no infinities or NaN: in ``report.json`` an infinite number is written as the string ``"inf"`` (or
``"-inf"``), for example the AMD ratio β of a pair whose resonances overlap even on circular orbits, and NaN
as ``null``.
"""

from __future__ import annotations

import json
import math
import platform
import sys
from datetime import datetime, timezone
from importlib import metadata
from pathlib import Path
from typing import Any, Protocol

from pydantic import BaseModel, ConfigDict
from rich.console import Console, Group
from rich.padding import Padding
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from . import __version__
from .indicators import IndicatorResult, Verdict
from .indicators.megno import ENERGY_ERROR_MAX, MEGNO_CHAOTIC
from .integrate import RunResult
from .models import MassKind, Provenance, System, Value
from .sampling import E_MAX, SIN_I_MIN, Realization
from .units import MEARTH_IN_MSUN, format_count, format_years, years_to_days

# 1.1: settings.budget_s; 1.2: settings.spock and the optional "spock" indicator; 1.3: infinite numbers written
# as "inf" / "-inf" instead of null, new completion flags, new keys in the indicator details, and overall
# summaries built from the draw counts
SCHEMA_VERSION = "1.3"

ACKNOWLEDGMENT = (
    "This research has made use of the NASA Exoplanet Archive, which is operated by the California "
    "Institute of Technology, under contract with the National Aeronautics and Space Administration under "
    "the Exoplanet Exploration Program."
)


class Overall(BaseModel):
    model_config = ConfigDict(extra="forbid")

    verdict: Verdict
    summary: str
    reasons: list[str]


class SettingsRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    seed: int
    orbits: float
    draws: int
    inclination_prior: str
    sin_i_min: float
    eccentricity_cap: float
    integrator: str
    check_integrator: str | None
    dt_fraction: float
    dt_yr: float | None
    t_end_yr: float
    megno_threshold: float
    energy_error_max: float
    escape_factor: float
    encounter_rule: str
    budget_s: float | None = None  # wall-clock budget that chose orbits and draws (--budget), if any
    spock: bool = False  # whether the optional SPOCK indicator was requested


class SoftwareRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    exostab: str
    rebound: str
    numpy: str
    astropy: str
    pydantic: str
    python: str
    platform: str


class BodyRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    mass_msun: float
    mass_earth: float
    period_yr: float
    period_days: float
    semi_major_axis_au: float
    eccentricity: float
    pomega_rad: float
    mean_anomaly_rad: float


class NominalRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    star_mass_msun: float
    epoch_jd: float | None
    bodies: list[BodyRecord]


class DataRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source: str
    table: str | None
    service: str | None
    retrieved_utc: str | None
    path: str | None
    note: str | None
    archive_rows: list[str]
    acknowledgment: str | None


class Report(BaseModel):
    """Everything needed to trace and reproduce one ``exostab check``."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str
    created_utc: str
    command: str | None
    system: System
    data: DataRecord
    settings: SettingsRecord
    software: SoftwareRecord
    nominal: NominalRecord
    indicators: dict[str, IndicatorResult]
    overall: Overall
    runtime_s: float

    def to_json(self) -> str:
        # pydantic's JSON mode turns infinities into None; the Python dump still has them
        data = _json_numbers(self.model_dump(mode="json"), self.model_dump(mode="python"))
        return json.dumps(data, indent=2, allow_nan=False)


class _Settings(Protocol):
    @property
    def orbits(self) -> float: ...
    @property
    def draws(self) -> int: ...
    @property
    def seed(self) -> int: ...
    @property
    def inclination_prior(self) -> str: ...
    @property
    def ias15_check(self) -> bool: ...
    @property
    def dt_fraction(self) -> float: ...
    @property
    def budget_s(self) -> float | None: ...
    @property
    def spock_python(self) -> str | None: ...


def _json_numbers(data: Any, raw: Any) -> Any:
    """``data`` (a JSON-mode dump) with the infinities of ``raw`` (the Python-mode dump of the same object)
    written as "inf" / "-inf" and NaN as None, since JSON has neither.

    Infinity is kept distinct from null: an infinite AMD β is the most unstable case, not a missing value.
    """
    for x in (raw, data):
        if isinstance(x, float) and not math.isfinite(x):
            return None if math.isnan(x) else ("inf" if x > 0 else "-inf")
    if isinstance(data, dict):
        return {k: _json_numbers(v, raw.get(k) if isinstance(raw, dict) else None) for k, v in data.items()}
    if isinstance(data, list):
        same = isinstance(raw, (list, tuple)) and len(raw) == len(data)
        return [_json_numbers(v, raw[i] if same else None) for i, v in enumerate(data)]
    return data


def _version(pkg: str) -> str:
    try:
        return metadata.version(pkg)
    except metadata.PackageNotFoundError:  # pragma: no cover
        return "unknown"


def software_record() -> SoftwareRecord:
    import rebound

    return SoftwareRecord(
        exostab=__version__,
        rebound=str(rebound.__version__),
        numpy=_version("numpy"),
        astropy=_version("astropy"),
        pydantic=_version("pydantic"),
        python=sys.version.split()[0],
        platform=platform.platform(),
    )


def build_report(
    *,
    system: System,
    settings: _Settings,
    epoch_jd: float | None,
    nominal: Realization,
    nominal_run: RunResult,
    indicators: dict[str, IndicatorResult],
    overall: Overall,
    runtime_s: float,
    command: str | None,
) -> Report:
    a = nominal.semi_major_axes()
    bodies = [
        BodyRecord(
            name=b.name,
            mass_msun=b.m,
            mass_earth=b.m / MEARTH_IN_MSUN,
            period_yr=b.P,
            period_days=years_to_days(b.P),
            semi_major_axis_au=float(a[k]),
            eccentricity=b.e,
            pomega_rad=b.pomega,
            mean_anomaly_rad=b.M,
        )
        for k, b in enumerate(nominal.bodies)
    ]
    src = system.source
    is_archive = src.kind in ("archive", "archive-cache", "snapshot")
    return Report(
        schema_version=SCHEMA_VERSION,
        created_utc=datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        command=command,
        system=system,
        data=DataRecord(
            source=src.kind,
            table=src.table,
            service=src.service,
            retrieved_utc=src.retrieved_utc,
            path=src.path,
            note=src.note,
            archive_rows=[p.archive_name for p in system.planets if p.archive_name],
            acknowledgment=ACKNOWLEDGMENT if is_archive else None,
        ),
        settings=SettingsRecord(
            seed=settings.seed,
            orbits=settings.orbits,
            draws=settings.draws,
            inclination_prior=settings.inclination_prior,
            sin_i_min=SIN_I_MIN,
            eccentricity_cap=E_MAX,
            integrator="whfast",
            check_integrator="ias15" if settings.ias15_check else None,
            dt_fraction=settings.dt_fraction,
            dt_yr=nominal_run.dt,
            t_end_yr=nominal_run.t_target,
            megno_threshold=MEGNO_CHAOTIC,
            energy_error_max=ENERGY_ERROR_MAX,
            escape_factor=100.0,
            encounter_rule="two planets closer than the mean of their Hill radii (REBOUND collision detection, "
            "line mode); a planet within half its Hill radius of the star does not stop the run and makes it "
            "inconclusive",
            budget_s=settings.budget_s,
            spock=settings.spock_python is not None,
        ),
        software=software_record(),
        nominal=NominalRecord(star_mass_msun=nominal.m_star, epoch_jd=epoch_jd, bodies=bodies),
        indicators=indicators,
        overall=overall,
        runtime_s=runtime_s,
    )


# ----------------------------------------------------------------------------------- terminal report card

_STYLE = {
    Verdict.STABLE: "bold green",
    Verdict.MARGINAL: "bold yellow",
    Verdict.UNSTABLE: "bold red",
    Verdict.INCONCLUSIVE: "bold magenta",
}
_MARK = {
    Provenance.MEASURED: "",
    Provenance.DERIVED: "ᵈ",
    Provenance.ASSUMED: "ᵃ",
    Provenance.ESTIMATED: "ᵉ",
    Provenance.RANDOMIZED: "ʳ",
    Provenance.UPPER_LIMIT: "<",
}


def _verdict_text(v: Verdict) -> Text:
    return Text(v.value.upper(), style=_STYLE[v])


def _fmt(v: Value | None, fmt: str = "{:.4g}", scale: float = 1.0) -> str:
    if v is None or v.value is None:
        return "random" if v is not None and v.provenance is Provenance.RANDOMIZED else "—"
    s = fmt.format(v.value * scale)
    if v.provenance is Provenance.UPPER_LIMIT:
        return "<" + s
    if v.has_errors and v.err_plus is not None and v.err_minus is not None:
        if math.isclose(v.err_plus, v.err_minus, rel_tol=0.05):
            s += " ± " + fmt.format(v.err_plus * scale)
        else:
            s += f" +{fmt.format(v.err_plus * scale)}/−{fmt.format(v.err_minus * scale)}"
    return s + _MARK[v.provenance]


def _planet_table(report: Report) -> Table:
    t = Table(title=None, box=None, pad_edge=False, header_style="bold")
    for col in ("Planet", "P (d)", "Mass (M⊕)", "e", "ω (deg)", "Phase"):
        t.add_column(col, overflow="fold")
    for p in report.system.planets:
        mass = _fmt(p.mass_earth, "{:.3g}")
        if p.mass_kind.value == "minimum":
            mass += " (m sin i)"
        t.add_row(
            Text(p.name),  # a name is text, not markup
            _fmt(p.period_days, "{:.6g}"),
            mass,
            _fmt(p.eccentricity, "{:.3g}"),
            _fmt(p.omega_deg, "{:.3g}"),
            p.phase.kind.value.replace("_", " "),
        )
    return t


def _indicator_block(report: Report) -> Group:
    """One heading line per indicator (name, verdict, draw counts) followed by its explanation."""
    parts: list[Any] = []
    width = max(len(ind.title) for ind in report.indicators.values())
    for ind in report.indicators.values():
        head = Text(f"{ind.title:<{width}}  ", style="bold")
        head.append_text(_verdict_text(ind.verdict))
        d = ind.draws
        if d:
            head.append(
                f"   draws: {d.stable} stable, {d.marginal} marginal, {d.unstable} unstable"
                + (f", {d.inconclusive} inconclusive" if d.inconclusive else ""),
                style="dim",
            )
        body = Text(ind.summary)
        for note in ind.notes:
            body.append("\n• " + note, style="dim")
        parts += [head, Padding(body, (0, 0, 0, 2))]
    return Group(*parts)


def system_flags(system: System) -> list[tuple[str, str]]:
    """Completion flags with identical messages merged: ("b, c, d", message)."""
    host = system.star.name
    order = {p.name: k for k, p in enumerate(system.planets)}
    groups: dict[str, list[str]] = {}
    for f in system.flags:
        groups.setdefault(f.message, []).append(f.planet or "system")
    out = []
    for message, names in groups.items():
        unique = sorted(dict.fromkeys(names), key=lambda n: order.get(n, len(order)))
        short = [n[len(host) + 1 :] if n.startswith(host + " ") else n for n in unique]
        out.append((", ".join(short), message))
    return out


def group_flags(report: Report) -> list[tuple[str, str]]:
    """The completion flags of a report, see :func:`system_flags`."""
    return system_flags(report.system)


def flags_table(system: System) -> Table:
    """The completion flags, one row per message. Names can be long, so both columns wrap, or the messages could
    be left with no room at all."""
    flags = Table(box=None, pad_edge=False, show_header=False)
    flags.add_column(style="dim", overflow="fold")
    flags.add_column(style="dim", overflow="fold")
    for who, message in system_flags(system):
        flags.add_row(Text(who), Text(message))
    return flags


def _prior_note(report: Report) -> str:
    """What the inclination prior did: report.json is not the only place that should say."""
    s = report.settings
    if s.inclination_prior == "none":
        return ""
    if s.draws == 0:
        return f" The {s.inclination_prior} inclination prior has no effect: it applies only to draws."
    if not any(p.mass_kind is MassKind.MINIMUM for p in report.system.planets):
        return f" The {s.inclination_prior} inclination prior has no effect: no mass here is a minimum mass."
    return f" Inclinations drawn with the {s.inclination_prior} prior (sin i ≥ {s.sin_i_min:g})."


def render(report: Report, console: Console, *, outputs: list[Path] | None = None) -> None:
    """Print the report card."""
    s = report.settings
    star = report.system.star
    header = Text()
    header.append(f"{report.system.name}", style="bold")
    header.append(f"   M* = {_fmt(star.mass_msun, '{:.3g}')} M☉   {len(report.system.planets)} planets   ")
    src = report.data
    header.append(
        f"data: {src.source}" + (f" ({src.retrieved_utc[:10]})" if src.retrieved_utc else ""), style="dim"
    )
    overall = Text("Overall: ", style="bold")
    overall.append_text(_verdict_text(report.overall.verdict))
    overall.append("  " + report.overall.summary)
    horizon = (
        f"N-body: {format_count(s.orbits)} orbits of the innermost planet = {format_years(s.t_end_yr)}, WHFast dt = "
        f"{(s.dt_yr or 0) * 365.25:.3g} d"
        + (", checked with IAS15" if s.check_integrator else "")
        + f"; {s.draws} Monte Carlo {'draw' if s.draws == 1 else 'draws'}; seed {s.seed}; MEGNO chaotic at <Y> ≥ "
        f"{s.megno_threshold:g}; energy-error limit {s.energy_error_max:.0e}."
        + (f" Run length and draws chosen for a {s.budget_s:g} s budget." if s.budget_s else "")
        + _prior_note(report)
    )
    parts: list[Any] = [
        header,
        Text(""),
        _planet_table(report),
        Text("ᵃ assumed  ᵈ derived  ᵉ estimated  ʳ randomized per run  < upper limit", style="dim"),
        Text(""),
        _indicator_block(report),
        Text(""),
        overall,
        Text(horizon, style="dim"),
    ]
    if report.system.flags:
        parts += [
            Text(""),
            Text("Data completion (applied automatically):", style="bold dim"),
            flags_table(report.system),
        ]
    if src.note:
        parts += [Text(f"Note: {src.note}", style="yellow")]
    if outputs:
        parts += [Text(""), Text("Saved: " + ", ".join(str(p) for p in outputs), style="dim")]
    console.print(
        Panel(Group(*parts), title=f"exostab {report.software.exostab} — stability report card", expand=True)
    )


def write_json(report: Report, path: Path) -> Path:
    path.write_text(report.to_json() + "\n", encoding="utf-8")
    return path


def json_schema() -> dict[str, Any]:
    schema = Report.model_json_schema()
    # Published on the documentation site by .github/workflows/docs.yml, so the identifier resolves (D33).
    schema["$id"] = f"https://mimitoz62.github.io/exostab/schemas/report-{SCHEMA_VERSION}.json"
    schema["title"] = f"exostab report (schema {SCHEMA_VERSION})"
    return schema


if __name__ == "__main__":  # pragma: no cover
    out = Path(__file__).parent / "schemas" / "report.schema.json"
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(json_schema(), indent=2) + "\n", encoding="utf-8")
    print(f"wrote {out}")
