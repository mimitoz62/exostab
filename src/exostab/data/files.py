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
from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from ..models import (
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
from .completion import IncompleteSystemError, coplanar_flag
from .massradius import MassRadiusError, mass_from_radius


class SystemFileError(ValueError):
    """The YAML file does not describe a valid system."""


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


def _finite(x: float, where: str) -> float:
    """``x`` if it is a finite number. YAML reads ``.nan`` and ``.inf`` as floats, and a NaN angle or time used
    to stop every integration at once, which was reported as a close encounter."""
    if not math.isfinite(x):
        raise SystemFileError(f"{where}: expected a finite number, got {x!r}")
    return x


def _value(
    raw: Any, *, scale: float = 1.0, reference: str | None = None, where: str = "", allow_limit: bool = False
) -> Value:
    if isinstance(raw, bool) or raw is None:
        raise SystemFileError(f"{where}: expected a number or a mapping, got {raw!r}")
    if isinstance(raw, (int, float)):
        return Value(value=_finite(float(raw) * scale, where), reference=reference)
    if not isinstance(raw, dict):
        raise SystemFileError(f"{where}: expected a number or a mapping, got {raw!r}")
    unknown = set(raw) - VALUE_KEYS
    if unknown:
        raise SystemFileError(f"{where}: unknown keys {sorted(unknown)}")
    if "value" not in raw:
        raise SystemFileError(f"{where}: missing 'value'")
    limit = raw.get("upper_limit", False)
    if not isinstance(limit, bool):
        raise SystemFileError(f"{where}: upper_limit must be true or false, got {limit!r}")
    if limit and not allow_limit:
        # Draws are uniform between 0 and an upper limit: meaningful for a planet mass or an eccentricity, not
        # for a stellar mass, a period, an angle or an absolute time.
        raise SystemFileError(f"{where}: upper_limit is only supported for planet masses and eccentricities")
    err_p = raw.get("err_plus", raw.get("err"))
    err_m = raw.get("err_minus", raw.get("err"))
    try:
        return Value(
            value=_finite(float(raw["value"]) * scale, where),
            err_plus=None if err_p is None else _finite(abs(float(err_p)) * scale, f"{where} error"),
            err_minus=None if err_m is None else _finite(abs(float(err_m)) * scale, f"{where} error"),
            provenance=Provenance.UPPER_LIMIT if limit else Provenance.MEASURED,
            reference=raw.get("reference", reference),
        )
    except SystemFileError:
        raise
    except (TypeError, ValueError) as exc:
        raise SystemFileError(f"{where}: {exc}") from exc


def _invalid(exc: ValueError) -> str:
    """The messages of a model validation error, without pydantic's boilerplate."""
    if isinstance(exc, ValidationError):
        return "; ".join(str(e["msg"]).removeprefix("Value error, ") for e in exc.errors())
    return str(exc)


def _flag(planet: str | None, parameter: str, rule: str, message: str) -> CompletionFlag:
    return CompletionFlag(planet=planet, parameter=parameter, rule=rule, message=message)


AXIS_TOLERANCE = 0.10  # relative; Kepler's a scales as M*^(1/3), so a 30% different stellar mass gives 9%
AXIS_SIGMA = 3.0  # with uncertainties on the axis, the period and the stellar mass, refuse above 3 sigma


def _relative_error(v: Value) -> float:
    """Mean of the two error bars over the value; 0 when the value has no uncertainty."""
    if not v.has_errors:
        return 0.0
    return 0.5 * ((v.err_plus or 0.0) + (v.err_minus or 0.0)) / abs(v.require())


def _check_axis(name: str, a: Value, period: Value, star_mass: Value, planet_mass: Value) -> None:
    """Refuse a semi-major axis that contradicts the period (the period is what the integrations use).

    The Kepler axis a_K = (G M P^2 / 4 pi^2)^(1/3), with M the stellar plus planet mass, has the first-order relative
    error sigma_K = sqrt((sigma_M / 3M)^2 + (2 sigma_P / 3P)^2). It is combined in quadrature with the axis's own
    relative error, sigma = sqrt((sigma_a / a)^2 + sigma_K^2). When the axis, the period and the stellar mass all have
    uncertainties, the two may differ by up to 3 sigma. Otherwise the fixed 10% tolerance (stellar masses from
    different sources) still applies as a floor: max(10%, 3 sigma). ``planet_mass`` is in Earth masses.
    """
    m_star = star_mass.require()
    m_total = m_star + planet_mass.require() * MEARTH_IN_MSUN  # Msun
    a_kepler = semimajor_axis_from_period(days_to_years(period.require()), m_total)
    sigma_m = math.hypot(
        _relative_error(star_mass) * m_star,
        _relative_error(planet_mass) * planet_mass.require() * MEARTH_IN_MSUN,
    )
    rel_kepler = math.hypot(sigma_m / (3 * m_total), 2 * _relative_error(period) / 3)
    sigma = math.hypot(_relative_error(a), rel_kepler)
    all_uncertain = all(_relative_error(v) > 0 for v in (a, period, star_mass))
    allowed = AXIS_SIGMA * sigma if all_uncertain else max(AXIS_TOLERANCE, AXIS_SIGMA * sigma)
    off = abs(a.require() / a_kepler - 1)
    if off > allowed:
        raise SystemFileError(
            f"{name}: semimajor_axis_au = {a.value:g} AU disagrees with period_days = {period.value:g} d, "
            f"which gives {a_kepler:.4g} AU for the stellar and planet mass ({off:.1%} apart, {allowed:.1%} "
            "allowed); give only one of them or check the stellar mass"
        )


def _planet(raw: dict[str, Any], star_mass: Value, flags: list[CompletionFlag], idx: int) -> Planet:
    m_star = star_mass.require()
    name = str(raw.get("name") or f"planet {idx + 1}")
    unknown = set(raw) - PLANET_KEYS
    if unknown:
        raise SystemFileError(f"{name}: unknown keys {sorted(unknown)}")
    ref = raw.get("reference")

    # mass
    mass_keys = [k for k in ("mass_earth", "mass_jupiter", "mass_msun") if k in raw]
    if len(mass_keys) > 1:
        raise SystemFileError(f"{name}: give only one of {mass_keys}")
    radius = (
        _value(raw["radius_earth"], reference=ref, where=f"{name}.radius_earth")
        if "radius_earth" in raw
        else None
    )
    kind_raw = raw.get("mass_kind", "true")
    try:
        kind = MassKind(str(kind_raw).lower())
    except ValueError as exc:
        raise SystemFileError(f"{name}: mass_kind must be true, minimum or estimated") from exc
    if mass_keys:
        scale = {"mass_earth": 1.0, "mass_jupiter": MJUP_IN_MEARTH, "mass_msun": 1 / MEARTH_IN_MSUN}[
            mass_keys[0]
        ]
        mass = _value(
            raw[mass_keys[0]], scale=scale, reference=ref, where=f"{name}.{mass_keys[0]}", allow_limit=True
        )
        if kind is MassKind.MINIMUM:
            flags.append(
                _flag(
                    name,
                    "mass",
                    "minimum_mass",
                    "Only the minimum mass m sin i is known; it is used as the mass (sin i = 1) unless "
                    "--inclination-prior is set.",
                )
            )
        elif kind is MassKind.ESTIMATED:
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
                "with the Chen & Kipping (2017) mass-radius relation.",
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
    if "period_days" in raw:
        period = _value(raw["period_days"], reference=ref, where=f"{name}.period_days")
        if a is not None and period.require() > 0:
            _check_axis(name, a, period, star_mass, mass)
    elif a is not None:
        P = years_to_days(period_from_semimajor_axis(a.require(), m_total))
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
                f"{name}: eccentricity {ecc.value:g} is above {E_MAX:g}, the largest eccentricity exostab "
                "integrates"
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
        raise SystemFileError(_invalid(exc)) from exc


def load_system_file(path: str | Path) -> System:
    """Read a system from a YAML file."""
    p = Path(path)
    try:
        raw = yaml.safe_load(p.read_text(encoding="utf-8"))
    except OSError as exc:
        raise SystemFileError(f"cannot read {p}: {exc}") from exc
    except yaml.YAMLError as exc:
        raise SystemFileError(f"{p} is not valid YAML: {exc}") from exc
    if not isinstance(raw, dict):
        raise SystemFileError(f"{p}: the top level must be a mapping")
    unknown = set(raw) - TOP_KEYS
    if unknown:
        raise SystemFileError(f"{p}: unknown top-level keys {sorted(unknown)}")
    star_raw = raw.get("star")
    if not isinstance(star_raw, dict) or "mass_msun" not in star_raw:
        raise SystemFileError(f"{p}: 'star' must be a mapping with 'mass_msun'")
    unknown = set(star_raw) - STAR_KEYS
    if unknown:  # e.g. a misspelt error key, which would leave the stellar mass fixed in every draw
        raise SystemFileError(f"{p}: star: unknown keys {sorted(unknown)}")
    star_mass = _value(star_raw["mass_msun"], where="star.mass_msun")
    name = str(raw.get("name") or p.stem)
    try:
        star = Star(name=str(star_raw.get("name") or name), mass_msun=star_mass)
    except ValueError as exc:
        raise SystemFileError(f"{p}: star: {_invalid(exc)}") from exc
    planets_raw = raw.get("planets")
    if not isinstance(planets_raw, list) or len(planets_raw) < 2:
        raise SystemFileError(f"{p}: 'planets' must be a list of at least two planets")
    flags: list[CompletionFlag] = []
    planets = []
    for i, pr in enumerate(planets_raw):
        if not isinstance(pr, dict):
            raise SystemFileError(f"{p}: planet {i + 1} must be a mapping")
        planets.append(_planet(pr, star_mass, flags, i))
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
        if isinstance(epoch, bool):  # YAML reads "yes"/"no" as booleans, which float() would accept
            raise TypeError
        epoch_jd = None if epoch is None else float(epoch)
        if epoch_jd is not None and not math.isfinite(epoch_jd):
            raise ValueError
    except (TypeError, ValueError) as exc:
        raise SystemFileError(
            f"{p}: epoch_jd must be a Julian date (a finite number), got {epoch!r}"
        ) from exc
    try:
        return System(
            name=name,
            star=star,
            planets=tuple(planets),
            epoch_jd=epoch_jd,
            source=DataSource(kind="file", path=str(p), note=str(raw["notes"]) if raw.get("notes") else None),
            flags=tuple(flags),
        )
    except ValueError as exc:
        raise SystemFileError(f"{p}: {_invalid(exc)}") from exc
