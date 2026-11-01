"""Pure helpers of the web app: the editable parameter table, "what if" adjustments, shareable links and
the cache key. Kept free of Streamlit so they can be unit-tested.
"""

from __future__ import annotations

import base64
import contextlib
import hashlib
import json
import math
from dataclasses import asdict, dataclass, field, replace
from typing import Any

from ..budget import PRESETS
from ..models import (
    MASS_MAX_EARTH,
    PERIOD_MAX_DAYS,
    PERIOD_MIN_DAYS,
    CompletionFlag,
    MassKind,
    PhaseKind,
    Provenance,
    System,
    Value,
)
from ..sampling import E_MAX

BUDGET_MIN, BUDGET_MAX, BUDGET_DEFAULT = 5, 120, 10
MASS_FACTORS = (0.1, 0.2, 0.3, 0.5, 0.7, 1.0, 1.5, 2.0, 3.0, 5.0, 7.0, 10.0)
SEED_MAX = 2**31 - 1  # range of the seed widget
# A link can ask for at most the longest run that a time budget can choose (the last preset in budget.py).
ORBITS_MAX, DRAWS_MAX = PRESETS[-1]
# Smallest mass the parameter table accepts (app.py), also required of the edits in a link, as are PERIOD_MIN_DAYS and
# the upper limits PERIOD_MAX_DAYS and MASS_MAX_EARTH (runs at those values take about a second).
MASS_MIN_EARTH = 1e-6
# Largest what-if period ratio a link may carry. The slider reaches 1.2 times the table's ratio (at least 10),
# and the widest adjacent pair in the archive is about 1.1e4 apart in period (GJ 2030, 2026-09-28 cache).
PERIOD_RATIO_MAX = 1e5


@dataclass
class WhatIf:
    """Adjustments of one planet on top of the table: mass factor, eccentricity, period ratio to the planet
    just inside it."""

    planet: str | None = None
    mass_factor: float = 1.0
    eccentricity: float | None = None
    period_ratio: float | None = None

    def is_active(self) -> bool:
        return self.planet is not None and (
            self.mass_factor != 1.0 or self.eccentricity is not None or self.period_ratio is not None
        )


@dataclass
class AppState:
    """Everything the shareable link must reproduce."""

    system: str = "TRAPPIST-1"
    source: str = "archive"  # "archive" or "snapshot"
    edits: dict[str, dict[str, float | None]] = field(default_factory=dict)  # planet -> column -> value
    whatif: WhatIf = field(default_factory=WhatIf)
    budget_s: float = BUDGET_DEFAULT
    seed: int = 0
    prior: str = "none"
    orbits: float | None = None  # exact run length of a finished run (makes a shared link reproducible)
    draws: int | None = None
    spock: bool = False  # optional SPOCK indicator (only offered when a SPOCK environment is configured)
    run: bool = False
    # What decode_state could not use from a link and left at the default, for a notice on the page.
    dropped: list[str] = field(default_factory=list, compare=False)


EDITABLE = ("period_days", "mass_earth", "eccentricity", "omega_deg")
# The parameter names of the completion flags about a column's value (archive rows and user files).
_FLAG_PARAMETERS = {
    "period_days": ("pl_orbper", "period"),
    "mass_earth": ("pl_bmasse", "mass"),
    "eccentricity": ("pl_orbeccen", "eccentricity"),
    "omega_deg": ("pl_orblper", "omega"),
}


def planet_rows(system: System) -> list[dict[str, Any]]:
    """Rows for the editable table (one per planet)."""
    rows = []
    for p in system.planets:
        rows.append(
            {
                "planet": p.name,
                "period_days": p.period_days.value,
                "mass_earth": p.mass_earth.value,
                # only shown: an upper limit is no true mass, whatever the archive says the limit is on
                "mass_kind": "upper limit"
                if p.mass_earth.provenance is Provenance.UPPER_LIMIT
                else p.mass_kind.value,
                "eccentricity": p.eccentricity.value,
                "omega_deg": p.omega_deg.value if p.omega_deg.is_known else None,
                "phase": p.phase.kind.value.replace("_", " "),
            }
        )
    return rows


def edited_rows(system: System, edits: dict[str, dict[str, float | None]]) -> list[dict[str, Any]]:
    """Rows of the table with the edits applied (a cleared cell is None)."""
    rows = planet_rows(system)
    for r in rows:
        r.update(edits.get(r["planet"], {}))
    return rows


def table_edits(system: System, rows: list[dict[str, Any]]) -> dict[str, dict[str, float | None]]:
    """Cells of the table that differ from the system's published values."""
    base = {r["planet"]: r for r in planet_rows(system)}
    edits: dict[str, dict[str, float | None]] = {}
    for r in rows:
        orig = base.get(r["planet"])
        if orig is None:
            continue
        for col in EDITABLE:
            new, old = r.get(col), orig[col]
            new = None if new is None or (isinstance(new, float) and math.isnan(new)) else float(new)
            if new != old and not (
                new is not None and old is not None and math.isclose(new, old, rel_tol=1e-12)
            ):
                edits.setdefault(r["planet"], {})[col] = new
    return edits


def _edited(v: Value, new: float | None, *, randomize_if_none: bool = False) -> Value:
    if new is None:
        if randomize_if_none:
            return Value(provenance=Provenance.RANDOMIZED, reference="set to random in the web app")
        raise ValueError("a value is missing")
    return v.model_copy(
        update={
            "value": new,
            "provenance": Provenance.MEASURED,
            "reference": "edited in the web app",
            "reference_url": None,  # the link of the publication is not the source of a typed value
        }
    )


def apply_changes(system: System, edits: dict[str, dict[str, float | None]], whatif: WhatIf) -> System:
    """The system with table edits and "what if" adjustments applied, each recorded as a completion flag."""
    planets = {p.name: p for p in system.planets}
    flags: list[CompletionFlag] = []
    replaced: set[tuple[str, str]] = set()  # (planet, parameter) of the flags that no longer hold
    for name, cols in edits.items():
        p = planets.get(name)
        if p is None:
            raise ValueError(f"unknown planet {name!r}")
        update: dict[str, Any] = {}
        for col, new in cols.items():
            if col not in EDITABLE:
                raise ValueError(f"column {col!r} cannot be edited")
            update[col] = _edited(getattr(p, col), new, randomize_if_none=col == "omega_deg")
            replaced.update((name, parameter) for parameter in _FLAG_PARAMETERS[col])
            shown = "random" if new is None else f"{new:g}"
            flags.append(
                CompletionFlag(
                    planet=name,
                    parameter=col,
                    rule="edited_in_web_app",
                    message=f"{col.replace('_', ' ')} set to {shown} in the web app ({_was(getattr(p, col))}).",
                )
            )
            if (
                col == "omega_deg"
                and new is None
                and p.phase.kind in (PhaseKind.PERIASTRON, PhaseKind.MEAN_ANOMALY)
            ):
                # The phase places the planet relative to its periastron, whose direction is now random in every
                # run. The phase kind stays, because changing it would change the random numbers of the run.
                replaced.add((name, "pl_orbtper"))
                flags.append(
                    CompletionFlag(
                        planet=name,
                        parameter="phase",
                        rule="phase_random_without_omega",
                        message="The argument of periastron was cleared, so the planet's longitude is random in every "
                        f"run, although its phase still comes from its {p.phase.kind.value.replace('_', ' ')}.",
                    )
                )
        planets[name] = p.model_copy(update=update)
    if whatif.is_active():
        assert whatif.planet is not None
        p = planets.get(whatif.planet)
        if p is None:
            raise ValueError(f"unknown planet {whatif.planet!r}")
        update = {}
        notes = []
        if whatif.mass_factor != 1.0:
            m = p.mass_earth.require() * whatif.mass_factor
            update["mass_earth"] = _edited(p.mass_earth, m)
            replaced.update((p.name, parameter) for parameter in _FLAG_PARAMETERS["mass_earth"])
            if p.mass_kind is MassKind.ESTIMATED:
                update["mass_kind"] = MassKind.TRUE
            notes.append(f"mass × {whatif.mass_factor:g} = {m:.4g} Earth masses")
        if whatif.eccentricity is not None:
            update["eccentricity"] = _edited(p.eccentricity, whatif.eccentricity)
            replaced.update((p.name, parameter) for parameter in _FLAG_PARAMETERS["eccentricity"])
            notes.append(f"e = {whatif.eccentricity:g}")
        if whatif.period_ratio is not None:
            ordered = sorted(planets.values(), key=lambda q: q.period_days.require())
            k = [q.name for q in ordered].index(p.name)
            if k == 0:
                raise ValueError("the period ratio applies to a planet outside another one")
            inner = ordered[k - 1].period_days.require()
            update["period_days"] = _edited(p.period_days, inner * whatif.period_ratio)
            replaced.update((p.name, parameter) for parameter in _FLAG_PARAMETERS["period_days"])
            notes.append(f"period ratio to {ordered[k - 1].name} = {whatif.period_ratio:g}")
        planets[p.name] = p.model_copy(update=update)
        flags.append(
            CompletionFlag(
                planet=p.name,
                parameter="what-if",
                rule="what_if_in_web_app",
                message="What-if adjustment in the web app: " + "; ".join(notes) + ".",
            )
        )
    # Re-validate: model_copy() skips the checks (positive values, 0 <= e < 1, ordered and unique planets).
    ordered_planets = sorted(planets.values(), key=lambda q: q.period_days.require())
    data = system.model_dump()
    data["planets"] = [q.model_dump() for q in ordered_planets]

    def still_holds(f: CompletionFlag) -> bool:
        # A minimum mass stays one with another value: the inclination prior still scales it.
        minimum = f.planet in planets and planets[f.planet].mass_kind is MassKind.MINIMUM
        return (f.planet, f.parameter) not in replaced or (
            f.rule in ("minimum_mass", "mass_lower_limit") and minimum
        )

    data["flags"] = [f.model_dump() for f in (*filter(still_holds, system.flags), *flags)]
    return System.model_validate(data)


_WAS = {
    Provenance.MEASURED: "published",
    Provenance.DERIVED: "derived",
    Provenance.ASSUMED: "assumed",
    Provenance.ESTIMATED: "estimated",
    Provenance.UPPER_LIMIT: "published upper limit",
}


def _was(v: Value) -> str:
    """The value a table edit replaced, for what it was: "published upper limit: 565.417"."""
    if v.provenance is Provenance.RANDOMIZED or v.value is None:
        return "was random"
    return f"{_WAS[v.provenance]}: {v.value:g}"


# ------------------------------------------------------------------------------------------ shareable links


def _b64(obj: Any) -> str:
    raw = json.dumps(obj, separators=(",", ":"), sort_keys=True).encode()
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def _unb64(text: str) -> Any:
    pad = "=" * (-len(text) % 4)
    return json.loads(base64.urlsafe_b64decode(text + pad).decode())


def encode_state(state: AppState) -> dict[str, str]:
    """Query parameters for a shareable link."""
    q = {"system": state.system, "budget": f"{state.budget_s:g}", "seed": str(state.seed)}
    if state.source != "archive":
        q["source"] = state.source
    if state.prior != "none":
        q["prior"] = state.prior
    if state.edits:
        q["edits"] = _b64(state.edits)
    if state.whatif.is_active():
        q["whatif"] = _b64(asdict(state.whatif))
    if state.orbits is not None and state.draws is not None:
        q["orbits"] = f"{state.orbits:g}"
        q["draws"] = str(state.draws)
    if state.spock:
        q["spock"] = "1"
    if state.run:
        q["run"] = "1"
    return q


def _number(v: Any) -> float:
    """A finite number from a decoded link (ValueError otherwise, also for an integer too large for a float)."""
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        raise ValueError("not a number")
    try:
        x = float(v)
    except OverflowError as exc:
        raise ValueError("not a finite number") from exc
    if not math.isfinite(x):
        raise ValueError("not a finite number")
    return x


# What the table's columns accept (app.py): bounds of each editable value in a link.
_EDIT_RANGES = {
    "period_days": (PERIOD_MIN_DAYS, PERIOD_MAX_DAYS),
    "mass_earth": (MASS_MIN_EARTH, MASS_MAX_EARTH),
    "eccentricity": (0.0, E_MAX),
    "omega_deg": (-math.inf, math.inf),
}


def _edit(column: str, v: Any) -> float | None:
    """One table edit from a decoded link: None (a cleared cell) or a number the table accepts."""
    if v is None:
        return None
    x = _number(v)
    lo, hi = _EDIT_RANGES[column]
    if not lo <= x <= hi:
        raise ValueError(f"{column} = {x:g} is outside the table's range")
    return x


def decode_state(params: dict[str, str]) -> AppState:
    """AppState from query parameters; invalid values fall back to the defaults.

    Links come from anywhere, so every value is checked against what the app itself can produce: a finite
    budget (clamped to the slider's range), a seed in the seed widget's range, table edits within the
    columns' ranges (an eccentricity at most ``E_MAX``), a what-if within the sliders' choices (a period ratio
    at most ``PERIOD_RATIO_MAX``), and a run length no longer than the longest preset a budget can choose.
    ``dropped`` names what fell back, so that the page can say so.
    """
    s = AppState()
    s.system = params.get("system", s.system)[:200]
    if params.get("source") in ("archive", "snapshot"):
        s.source = params["source"]
    elif "source" in params:
        s.dropped.append("the data source")
    if params.get("prior") in ("none", "isotropic"):
        s.prior = params["prior"]
    elif "prior" in params:
        s.dropped.append("the treatment of minimum masses")
    budget_read = False
    with contextlib.suppress(ValueError):
        budget = float(params.get("budget", s.budget_s))
        if math.isfinite(budget):
            s.budget_s = min(max(budget, BUDGET_MIN), BUDGET_MAX)
            budget_read = True
    if not budget_read:
        s.dropped.append("the time budget")
    seed_read = False
    with contextlib.suppress(ValueError):
        seed = int(params.get("seed", s.seed))
        if 0 <= seed <= SEED_MAX:
            s.seed = seed
            seed_read = True
    if not seed_read:
        s.dropped.append("the seed")
    try:
        if "edits" in params:
            raw = _unb64(params["edits"])
            s.edits = {
                str(p): {str(c): _edit(c, v) for c, v in cols.items() if c in EDITABLE}
                for p, cols in raw.items()
            }
        if "whatif" in params:
            raw = _unb64(params["whatif"])
            factor = 1.0 if raw.get("mass_factor") is None else _number(raw["mass_factor"])
            e = None if raw.get("eccentricity") is None else _number(raw["eccentricity"])
            ratio = None if raw.get("period_ratio") is None else _number(raw["period_ratio"])
            if (
                factor not in MASS_FACTORS
                or not (e is None or 0 <= e <= E_MAX)
                or not (ratio is None or 1 < ratio <= PERIOD_RATIO_MAX)
            ):
                raise ValueError("what-if adjustment out of range")
            s.whatif = WhatIf(
                planet=None if raw.get("planet") is None else str(raw["planet"]),
                mass_factor=factor,
                eccentricity=e,
                period_ratio=ratio,
            )
    except (ValueError, TypeError, AttributeError, OverflowError, RecursionError):
        s.edits, s.whatif = {}, WhatIf()
        s.dropped.append("the table edits and what-if changes")
    with contextlib.suppress(ValueError, KeyError):
        orbits, draws = float(params["orbits"]), int(params["draws"])
        if 10 <= orbits <= ORBITS_MAX and 0 <= draws <= DRAWS_MAX:
            s.orbits, s.draws = orbits, draws
    if s.orbits is None and ("orbits" in params or "draws" in params):
        s.dropped.append("the run length")
    s.spock = params.get("spock") == "1"
    s.run = params.get("run") == "1"
    return s


def share_url(base: str, state: AppState) -> str:
    from urllib.parse import urlencode

    return base.rstrip("/") + "/?" + urlencode(encode_state(replace(state, run=True)))


def input_hash(system: System, settings: dict[str, Any]) -> str:
    """SHA-256 of every input of a run: the system (values, errors, flags) and the settings."""
    payload = json.dumps({"system": system.model_dump(mode="json"), "settings": settings}, sort_keys=True)
    return hashlib.sha256(payload.encode()).hexdigest()
