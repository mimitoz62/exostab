"""User-supplied systems in YAML.

A value can be a number, or a mapping with ``value`` and optional ``err`` (symmetric), ``err_plus`` /
``err_minus`` (asymmetric), ``upper_limit: true`` (planet masses and eccentricities only) and ``reference``.
Units are part of the key names. ``examples/two_planet.yaml`` shows every key, with the alternatives in
comments; in short::

    name: My system
    epoch_jd: 2460000.0            # epoch of mean anomalies / mean longitudes; required if other planets
                                   # give transit or periastron times
    star:
      name: My star
      mass_msun: {value: 1.0, err: 0.05}
    planets:
      - name: My star b
        period_days: 100.0           # or semimajor_axis_au (both: they must agree)
        mass_earth: {value: 30, err: 3}   # or mass_jupiter / mass_msun, or radius_earth only
        mass_kind: true              # true | minimum | estimated
        eccentricity: {value: 0.05, err: 0.02}
        omega_deg: 90                # argument of periastron
        mean_longitude_deg: 10       # or transit_time_jd, or mean_anomaly_deg / periastron_time_jd
                                     # (these two need omega_deg)

Missing values follow the same completion rules as archive data (:mod:`exostab.data.completion`).
"""

from __future__ import annotations

import math
import re
import reprlib
import unicodedata
from pathlib import Path
from typing import Any

import yaml

from ..models import (
    AXIS_MAX_AU,
    JD_MAX,
    PERIOD_MAX_DAYS,
    PERIOD_MIN_DAYS,
    STAR_MASS_MAX_MSUN,
    STAR_MASS_MIN_MSUN,
    CompletionFlag,
    DataSource,
    MassKind,
    Phase,
    PhaseKind,
    Planet,
    Provenance,
    Star,
    System,
    Value,
)
from ..sampling import E_MAX
from ..units import (
    MEARTH_IN_MSUN,
    MJUP_IN_MEARTH,
    days_to_years,
    period_from_semimajor_axis,
    semimajor_axis_from_period,
    years_to_days,
)
from .completion import IncompleteSystemError, coplanar_flag, invalid_message, phase_spread_flags
from .massradius import MassRadiusError, mass_from_radius


class SystemFileError(ValueError):
    """The YAML file does not describe a valid system."""


# A value in a message: bounded also for the nested aliases of a tiny file that expands to gigabytes.
_short = reprlib.Repr()
_short.maxlevel = 2

TOP_KEYS = {"name", "epoch_jd", "star", "planets", "notes"}
STAR_KEYS = {"name", "mass_msun"}
VALUE_KEYS = {"value", "err", "err_plus", "err_minus", "upper_limit", "reference"}
PLANET_KEYS = {
    "name",
    "period_days",
    "semimajor_axis_au",
    "mass_earth",
    "mass_jupiter",
    "mass_msun",
    "radius_earth",
    "mass_kind",
    "eccentricity",
    "omega_deg",
    "mean_anomaly_deg",
    "mean_longitude_deg",
    "transit_time_jd",
    "periastron_time_jd",
    "reference",
}
_PHASE_KEYS = {
    "mean_anomaly_deg": PhaseKind.MEAN_ANOMALY,
    "mean_longitude_deg": PhaseKind.MEAN_LONGITUDE,
    "transit_time_jd": PhaseKind.TRANSIT,
    "periastron_time_jd": PhaseKind.PERIASTRON,
}


class _StrictLoader(yaml.SafeLoader):
    """yaml.safe_load with two changes, so that a file means what it looks like.

    A repeated key is refused: YAML's "the last one wins" drops a planet when a dash is missing in the list of
    planets. Numbers follow the rules of YAML 1.2 instead of 1.1, so 3e-6 and 1e1 are numbers. An integer with a
    leading zero, a base prefix or colons is no longer one (010 was 8, 0x10 was 16, 1:30 was 90): it stays text,
    which the loader refuses where a number is expected.
    """

    def construct_mapping(self, node: yaml.MappingNode, deep: bool = False) -> dict[Any, Any]:
        seen = set()
        for key, _ in node.value:
            if isinstance(key, yaml.ScalarNode) and key.tag != "tag:yaml.org,2002:merge":
                if (key.tag, key.value) in seen:
                    raise SystemFileError(
                        f"line {key.start_mark.line + 1}: the key {key.value!r} is repeated, and the last one would "
                        "silently win; in a list of planets, a missing '-' does this"
                    )
                seen.add((key.tag, key.value))
        return super().construct_mapping(node, deep=deep)


_YAML_INT, _YAML_FLOAT = "tag:yaml.org,2002:int", "tag:yaml.org,2002:float"
_StrictLoader.yaml_implicit_resolvers = {
    first: [(tag, regexp) for tag, regexp in resolvers if tag not in (_YAML_INT, _YAML_FLOAT)]
    for first, resolvers in yaml.SafeLoader.yaml_implicit_resolvers.items()
}
_StrictLoader.add_implicit_resolver(_YAML_INT, re.compile(r"^[-+]?(?:0|[1-9][0-9_]*)$"), list("-+0123456789"))
_StrictLoader.add_implicit_resolver(
    _YAML_FLOAT,
    re.compile(
        r"""^(?:[-+]?(?:[0-9][0-9_]*(?:\.[0-9_]*)?|\.[0-9][0-9_]*)[eE][-+]?[0-9]+
            |[-+]?[0-9][0-9_]*\.[0-9_]*
            |[-+]?\.[0-9][0-9_]*
            |[-+]?\.(?:inf|Inf|INF)
            |\.(?:nan|NaN|NAN))$""",
        re.VERBOSE,
    ),
    list("-+0123456789."),
)


def _finite(x: float, where: str) -> float:
    """``x`` if it is a finite number. YAML reads ``.nan`` and ``.inf`` as floats, and a NaN angle or time used
    to stop every integration at once, which was reported as a close encounter."""
    if not math.isfinite(x):
        raise SystemFileError(f"{where}: expected a finite number, got {x!r}")
    return x


def _number(raw: Any, where: str, scale: float = 1.0) -> float:
    """A finite float from a YAML number. Booleans and text are not numbers, although float() takes them."""
    if isinstance(raw, bool) or not isinstance(raw, (int, float)):
        raise SystemFileError(f"{where}: expected a number, got {_short.repr(raw)}")
    try:
        return _finite(float(raw) * scale, where)
    except OverflowError as exc:  # an integer of hundreds of digits
        raise SystemFileError(f"{where}: expected a finite number, got {_short.repr(raw)}") from exc


def _within(v: Value, where: str, low: float, high: float, unit: str, scale: float = 1.0) -> None:
    """Refuse a value, or an upper error that reaches, outside what exostab accepts at all."""
    top = v.require() + (v.err_plus or 0.0)
    if not (low <= v.require() and top <= high):
        reached = f"{v.require() / scale:g}" + (f" (with its error, {top / scale:g})" if v.err_plus else "")
        raise SystemFileError(
            f"{where}: {reached} {unit} is outside the range exostab accepts, {low / scale:g} to {high / scale:g} {unit}"
        )


def _written(raw: Any) -> Any:
    """The number as the file writes it, for messages."""
    return raw["value"] if isinstance(raw, dict) and "value" in raw else raw


def _reference(raw: Any, where: str) -> str | None:
    """A citation: text, or a number taken as text (``reference: 2017``)."""
    if raw is None or isinstance(raw, str):
        return raw
    if isinstance(raw, (int, float)) and not isinstance(raw, bool):
        return str(raw)
    raise SystemFileError(f"{where}: reference must be text, got {_short.repr(raw)}")


def _text(raw: Any, where: str, *, multiline: bool = False) -> str | None:
    """A name or a note: YAML reads an unquoted No, Yes, On or Off as a boolean, and lists and mappings would
    reach the report as Python text. Control characters would reach the terminal, and a lone surrogate cannot
    be written out at all."""
    if raw is None:
        return None
    if not isinstance(raw, str):
        hint = "; put it in quotes" if isinstance(raw, (bool, int, float)) else ""
        raise SystemFileError(f"{where} must be text, got {_short.repr(raw)}{hint}")
    allowed = "\n\t" if multiline else ""
    bad = [c for c in raw if unicodedata.category(c) in ("Cc", "Cs") and c not in allowed]
    if bad:
        raise SystemFileError(f"{where} contains the control character {bad[0]!a}")
    return raw


def _value(
    raw: Any, *, scale: float = 1.0, reference: str | None = None, where: str = "", allow_limit: bool = False
) -> Value:
    if isinstance(raw, bool) or raw is None:
        raise SystemFileError(f"{where}: expected a number or a mapping, got {raw!r}")
    if isinstance(raw, (int, float)):
        return Value(value=_number(raw, where, scale), reference=reference)
    if not isinstance(raw, dict):
        raise SystemFileError(f"{where}: expected a number or a mapping, got {_short.repr(raw)}")
    unknown = set(raw) - VALUE_KEYS
    if unknown:
        raise SystemFileError(f"{where}: unknown keys {sorted(unknown, key=str)}")
    if "value" not in raw:
        raise SystemFileError(f"{where}: missing 'value'")
    limit = raw.get("upper_limit", False)
    if not isinstance(limit, bool):
        raise SystemFileError(f"{where}: upper_limit must be true or false, got {_short.repr(limit)}")
    if limit and not allow_limit:
        # Draws are uniform between 0 and an upper limit: meaningful for a planet mass or an eccentricity, not
        # for a stellar mass, a period, an angle or an absolute time.
        raise SystemFileError(f"{where}: upper_limit is only supported for planet masses and eccentricities")
    value = _number(raw["value"], where, scale)
    errors = [k for k in ("err", "err_plus", "err_minus") if k in raw]
    if "err" in raw and len(errors) > 1:
        raise SystemFileError(f"{where}: give either err or err_plus and err_minus, not both")
    if len(errors) == 1 and errors[0] != "err":
        # Value.has_errors needs both sides: a single one would be stored and silently ignored in every draw.
        other = "err_minus" if errors[0] == "err_plus" else "err_plus"
        raise SystemFileError(f"{where}: {errors[0]} needs {other} too; for equal errors, use err")
    if limit and errors:
        raise SystemFileError(f"{where}: an upper limit takes no error bar; give only one of them")
    if limit and not value > 0:
        raise SystemFileError(f"{where}: an upper limit must be positive, got {_written(raw)}")
    err_p, err_m = (raw[k] if k in raw else raw.get("err") for k in ("err_plus", "err_minus"))
    return Value(
        value=value,
        err_plus=abs(_number(err_p, f"{where} error", scale)) if errors else None,
        err_minus=abs(_number(err_m, f"{where} error", scale)) if errors else None,
        provenance=Provenance.UPPER_LIMIT if limit else Provenance.MEASURED,
        reference=_reference(raw.get("reference", reference), where),
    )


def _flag(planet: str | None, parameter: str, rule: str, message: str) -> CompletionFlag:
    return CompletionFlag(planet=planet, parameter=parameter, rule=rule, message=message)


AXIS_TOLERANCE = 0.10  # relative; Kepler's a scales as M*^(1/3), so a 30% different stellar mass gives 9%
# A mass plus its upper error may not exceed this. It only stops an error bar that overflows the draws: a planet must
# be below its star anyway, and the largest star accepted is about 3.3e8 Earth masses.
MASS_ERROR_MAX_EARTH = 1e9


def _check_axis(name: str, a: Value, period_days: float, m_total_msun: float) -> None:
    """Refuse a semi-major axis that contradicts the period (the period is what the integrations use).

    Allowed: 10% (stellar masses from different sources) or three times the axis's relative error, whichever
    is larger.
    """
    a_kepler = semimajor_axis_from_period(days_to_years(period_days), m_total_msun)
    rel_err = 0.5 * ((a.err_plus or 0.0) + (a.err_minus or 0.0)) / a.require()
    if abs(a.require() / a_kepler - 1) > max(AXIS_TOLERANCE, 3 * rel_err):
        raise SystemFileError(
            f"{name}: semimajor_axis_au = {a.value:g} AU disagrees with period_days = {period_days:g} d, "
            f"which gives {a_kepler:.4g} AU for the stellar and planet mass; give only one of them or check "
            "the stellar mass"
        )


def _planet(raw: dict[str, Any], m_star: float, flags: list[CompletionFlag], idx: int) -> Planet:
    name = _text(raw.get("name"), f"planet {idx + 1}: name") or f"planet {idx + 1}"
    unknown = set(raw) - PLANET_KEYS
    if unknown:
        raise SystemFileError(f"{name}: unknown keys {sorted(unknown, key=str)}")
    ref = _reference(raw.get("reference"), name)

    # mass
    mass_keys = [k for k in ("mass_earth", "mass_jupiter", "mass_msun") if k in raw]
    if len(mass_keys) > 1:
        raise SystemFileError(f"{name}: give only one of {mass_keys}")
    radius = (
        _value(raw["radius_earth"], reference=ref, where=f"{name}.radius_earth")
        if "radius_earth" in raw
        else None
    )
    if radius is not None and not radius.require() > 0:
        raise SystemFileError(f"{name}.radius_earth must be positive, got {_written(raw['radius_earth'])}")
    kind_raw = raw.get("mass_kind", "true")
    try:
        kind = MassKind(str(kind_raw).lower())
    except ValueError as exc:
        raise SystemFileError(f"{name}: mass_kind must be true, minimum or estimated") from exc
    if mass_keys:
        scale = {"mass_earth": 1.0, "mass_jupiter": MJUP_IN_MEARTH, "mass_msun": 1 / MEARTH_IN_MSUN}[
            mass_keys[0]
        ]
        where = f"{name}.{mass_keys[0]}"
        mass = _value(raw[mass_keys[0]], scale=scale, reference=ref, where=where, allow_limit=True)
        if not mass.require() > 0:
            raise SystemFileError(f"{where}: mass must be positive, got {_written(raw[mass_keys[0]])}")
        if not mass.require() * MEARTH_IN_MSUN < m_star:
            raise SystemFileError(f"{where}: {_written(raw[mass_keys[0]])} is not below the stellar mass")
        _within(mass, where, 0.0, MASS_ERROR_MAX_EARTH, "Earth masses")
        if kind is MassKind.MINIMUM:
            flags.append(
                _flag(
                    name,
                    "mass",
                    "minimum_mass",
                    "Only the minimum mass m sin i is known; it is used as the mass (sin i = 1) unless an "
                    "inclination prior is chosen.",
                )
            )
        elif kind is MassKind.ESTIMATED:
            if mass.provenance is Provenance.UPPER_LIMIT:
                # The draws would hold the limit fixed, and an instability would no longer count as resting on a
                # limit (DECISIONS.md, D27).
                raise SystemFileError(
                    f"{where}: upper_limit and mass_kind estimated exclude each other; give only one of them"
                )
            mass = mass.model_copy(update={"provenance": Provenance.ESTIMATED})
            flags.append(
                _flag(
                    name,
                    "mass",
                    "mass_estimated_in_file",
                    "The file marks this mass as estimated (for example from a mass-radius relation), not "
                    "measured.",
                )
            )
    elif radius is not None:
        if "mass_kind" in raw and kind is not MassKind.ESTIMATED:
            raise SystemFileError(
                f"{name}: mass_kind {kind.value!r} needs a mass; with radius_earth only, the mass is "
                "estimated from the radius (leave out mass_kind or set it to estimated)"
            )
        try:
            m = mass_from_radius(radius.require())
        except MassRadiusError as exc:
            raise IncompleteSystemError(f"{name}: no mass given and {exc}") from exc
        mass, kind = (
            Value(value=m, provenance=Provenance.ESTIMATED, reference="Chen & Kipping 2017"),
            MassKind.ESTIMATED,
        )
        flags.append(
            _flag(
                name,
                "mass",
                "mass_from_radius_chen_kipping",
                f"Mass not given; estimated as {m:.3g} Earth masses from R = {radius.value:g} Earth radii "
                "with the Chen & Kipping (2017) mass-radius relation."
                + (
                    " The radius error is not propagated: the mass is held fixed in the draws."
                    if radius.has_errors
                    else ""
                ),
            )
        )
    else:
        raise IncompleteSystemError(
            f"{name}: give a mass (mass_earth, mass_jupiter or mass_msun) or radius_earth"
        )
    if mass.provenance is Provenance.UPPER_LIMIT:
        flags.append(
            _flag(
                name,
                "mass",
                "mass_upper_limit",
                "Only an upper limit is given; the nominal run uses the limit, draws are uniform below it.",
            )
        )

    # period
    a = None
    m_total = m_star + mass.require() * MEARTH_IN_MSUN  # Msun
    if "semimajor_axis_au" in raw:
        a = _value(raw["semimajor_axis_au"], reference=ref, where=f"{name}.semimajor_axis_au")
        if not a.require() > 0:
            raise SystemFileError(f"{name}: semimajor_axis_au must be positive, got {a.value:g}")
        _within(a, f"{name}.semimajor_axis_au", 0.0, AXIS_MAX_AU, "AU")
    if "period_days" in raw:
        period = _value(raw["period_days"], reference=ref, where=f"{name}.period_days")
        _within(period, f"{name}.period_days", PERIOD_MIN_DAYS, PERIOD_MAX_DAYS, "d")
        if a is not None:
            _check_axis(name, a, period.require(), m_total)
    elif a is not None:
        P = years_to_days(period_from_semimajor_axis(a.require(), m_total))
        if not PERIOD_MIN_DAYS <= P <= PERIOD_MAX_DAYS:
            raise SystemFileError(
                f"{name}.semimajor_axis_au: {a.value:g} AU gives a period of {P:g} d, outside the range exostab "
                f"accepts, {PERIOD_MIN_DAYS:g} to {PERIOD_MAX_DAYS:g} d"
            )
        rel = 0.5 * ((a.err_plus or 0) + (a.err_minus or 0)) / a.require()
        err = 1.5 * rel * P if a.has_errors else None
        period = Value(value=P, err_plus=err, err_minus=err, provenance=Provenance.DERIVED, reference=ref)
        flags.append(
            _flag(
                name,
                "period",
                "period_from_semimajor_axis",
                f"Period derived from a = {a.value:g} AU with Kepler's third law ({P:.4g} d).",
            )
        )
    else:
        raise IncompleteSystemError(f"{name}: give period_days or semimajor_axis_au")

    # eccentricity and argument of periastron
    if "eccentricity" in raw:
        ecc = _value(raw["eccentricity"], reference=ref, where=f"{name}.eccentricity", allow_limit=True)
        if ecc.require() > E_MAX:
            raise SystemFileError(
                f"{name}: eccentricity {ecc.value} is above {E_MAX:g}, the largest eccentricity exostab integrates"
            )
        if ecc.provenance is Provenance.UPPER_LIMIT:
            flags.append(
                _flag(
                    name,
                    "eccentricity",
                    "eccentricity_upper_limit",
                    "Only an upper limit is given; the nominal run uses the limit, draws are uniform below it.",
                )
            )
    else:
        ecc = Value(value=0.0, provenance=Provenance.ASSUMED)
        flags.append(
            _flag(name, "eccentricity", "eccentricity_assumed_zero", "Eccentricity not given; assumed 0.")
        )
    if "omega_deg" in raw:
        omega = _value(raw["omega_deg"], reference=ref, where=f"{name}.omega_deg")
    else:
        omega = Value(provenance=Provenance.RANDOMIZED)
        flags.append(
            _flag(
                name,
                "omega",
                "omega_randomized",
                "Argument of periastron not given; drawn uniformly in [0, 360) deg for every run.",
            )
        )

    # phase
    given = [k for k in _PHASE_KEYS if k in raw]
    if len(given) > 1:
        raise SystemFileError(f"{name}: give at most one of {given}")
    if given and given[0] in ("mean_anomaly_deg", "periastron_time_jd") and "omega_deg" not in raw:
        # These place the planet relative to its periastron; without its direction (omega_deg, drawn at
        # random) the planet's longitude would be random in every run while the report said the phase was set.
        raise SystemFileError(
            f"{name}: {given[0]} needs omega_deg (the direction of the periastron); give omega_deg, or the "
            "mean longitude (mean_longitude_deg) instead"
        )
    if given:
        phase = Phase(
            kind=_PHASE_KEYS[given[0]], value=_value(raw[given[0]], reference=ref, where=f"{name}.{given[0]}")
        )
        if given[0].endswith("_jd"):
            assert phase.value is not None
            _within(phase.value, f"{name}.{given[0]}", -JD_MAX, JD_MAX, "JD")
    else:
        phase = Phase(kind=PhaseKind.RANDOM)
        flags.append(
            _flag(
                name, "phase", "phase_randomized", "Orbital phase not given; drawn uniformly for every run."
            )
        )
    try:
        return Planet(
            name=name,
            period_days=period,
            mass_earth=mass,
            mass_kind=kind,
            eccentricity=ecc,
            omega_deg=omega,
            phase=phase,
            radius_earth=radius,
            semimajor_axis_au=a,
        )
    except ValueError as exc:
        raise SystemFileError(invalid_message(exc)) from exc


def load_system_file(path: str | Path) -> System:
    """Read a system from a YAML file."""
    p = Path(path)
    try:
        raw = yaml.load(p.read_text(encoding="utf-8"), Loader=_StrictLoader)
    except OSError as exc:
        raise SystemFileError(f"cannot read {p}: {exc}") from exc
    except UnicodeDecodeError as exc:
        raise SystemFileError(f"{p} is not a UTF-8 text file: {exc}") from exc
    except SystemFileError as exc:
        raise SystemFileError(f"{p}, {exc}") from exc
    except (
        yaml.YAMLError,
        ValueError,
        TypeError,
        KeyError,
        AttributeError,
        RecursionError,
        OverflowError,
    ) as exc:
        # Besides YAMLError: PyYAML's constructors let these through for a date or tag they cannot read
        # ("2024-02-30", "!!float abc"), for very deep nesting and for an integer of thousands of digits.
        raise SystemFileError(f"{p} is not valid YAML: {exc}") from exc
    if not isinstance(raw, dict):
        raise SystemFileError(f"{p}: the top level must be a mapping")
    unknown = set(raw) - TOP_KEYS
    if unknown:
        raise SystemFileError(f"{p}: unknown top-level keys {sorted(unknown, key=str)}")
    star_raw = raw.get("star")
    if not isinstance(star_raw, dict) or "mass_msun" not in star_raw:
        raise SystemFileError(f"{p}: 'star' must be a mapping with 'mass_msun'")
    unknown = set(star_raw) - STAR_KEYS
    if unknown:  # e.g. a misspelt error key, which would leave the stellar mass fixed in every draw
        raise SystemFileError(f"{p}: star: unknown keys {sorted(unknown, key=str)}")
    star_mass = _value(star_raw["mass_msun"], where="star.mass_msun")
    name = _text(raw.get("name"), f"{p}: name") or p.stem
    notes = _text(raw.get("notes"), f"{p}: notes", multiline=True)
    try:
        star = Star(name=_text(star_raw.get("name"), f"{p}: star: name") or name, mass_msun=star_mass)
    except ValueError as exc:
        raise SystemFileError(f"{p}: star: {invalid_message(exc)}") from exc
    _within(star_mass, "star.mass_msun", STAR_MASS_MIN_MSUN, STAR_MASS_MAX_MSUN, "solar masses")
    planets_raw = raw.get("planets")
    if not isinstance(planets_raw, list) or len(planets_raw) < 2:
        raise SystemFileError(f"{p}: 'planets' must be a list of at least two planets")
    flags: list[CompletionFlag] = []
    planets = []
    for i, pr in enumerate(planets_raw):
        if not isinstance(pr, dict):
            raise SystemFileError(f"{p}: planet {i + 1} must be a mapping")
        planets.append(_planet(pr, star_mass.require(), flags, i))
    folded: dict[str, str] = {}
    for q in planets:
        other = folded.setdefault(q.name.strip().casefold(), q.name)
        if other != q.name:  # sweep --planet ignores case, so it could reach either of them
            raise SystemFileError(
                f"{p}: the planet names {other!r} and {q.name!r} differ only in case or surrounding spaces"
            )
    planets.sort(key=lambda q: q.period_days.require())
    flags.append(coplanar_flag())
    epoch = raw.get("epoch_jd")
    kinds = {q.phase.kind for q in planets}
    if (
        epoch is None
        and kinds & {PhaseKind.MEAN_ANOMALY, PhaseKind.MEAN_LONGITUDE}
        and kinds & {PhaseKind.TRANSIT, PhaseKind.PERIASTRON}
    ):
        # The angles hold at an epoch the file does not state; taking them at one of the reference times would
        # make the relative phases arbitrary.
        raise SystemFileError(
            f"{p}: epoch_jd is required when mean anomalies or mean longitudes are combined with transit or "
            "periastron times: give the epoch at which the angles hold"
        )
    try:
        epoch_jd = None if epoch is None else _number(epoch, "epoch_jd")
    except SystemFileError as exc:
        raise SystemFileError(
            f"{p}: epoch_jd must be a Julian date (a finite number), got {_short.repr(epoch)}"
        ) from exc
    if epoch_jd is not None and abs(epoch_jd) > JD_MAX:
        raise SystemFileError(f"{p}: epoch_jd = {epoch_jd:g} is not a plausible Julian date")
    try:
        system = System(
            name=name,
            star=star,
            planets=tuple(planets),
            epoch_jd=epoch_jd,
            source=DataSource(kind="file", path=str(p), note=notes or None),
            flags=tuple(flags),
        )
    except ValueError as exc:
        raise SystemFileError(f"{p}: {invalid_message(exc)}") from exc
    return system.model_copy(update={"flags": (*system.flags, *phase_spread_flags(system))})
