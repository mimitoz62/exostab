"""Turn a :class:`~exostab.models.System` into concrete initial conditions ("realizations").

A realization is one fully specified set of numbers in simulation units (yr, AU, Msun, radians) that
can be integrated. Run 0 is the *nominal* realization: published central values, with randomized
angles drawn from the seed. The remaining runs are Monte Carlo *draws* within the published
uncertainties.

Sampling rules (also listed in ``docs/data-assumptions.md``):

* A value with asymmetric errors is drawn from a split normal distribution (one Gaussian half-width
  above the value and another below it). Values without published errors are held fixed.
* Eccentricities below zero are set to zero, as in the HD 127195 Research Note; drawn eccentricities
  are capped at ``E_MAX``, and a nominal eccentricity above it is refused (the loaders reject such
  systems). Masses, periods and the stellar mass are redrawn until positive.
* Upper limits, allowed only on planet masses and eccentricities: the nominal run uses the limit itself
  (normally the hardest case; a mass limit need not be for AMD, see ``docs/methods.md``); draws are uniform
  between zero and the limit. An upper limit on any other value (stellar mass, period, angle, reference time)
  is refused.
* Orbital phases are propagated from the published reference time to the common epoch ``t0`` with the
  drawn period, so period and timing uncertainties both enter the draws.
* ``inclination_prior="isotropic"`` draws one inclination per run for the whole (coplanar) system with
  cos i uniform, truncated at sin i >= ``SIN_I_MIN``, and divides every minimum mass by sin i.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass, replace
from typing import Literal

import numpy as np
import numpy.typing as npt

from .models import MassKind, PhaseKind, Planet, Provenance, System, UnusableParametersError, Value
from .units import G_SIM, days_to_years, mearth_to_msun

InclinationPrior = Literal["none", "isotropic"]

E_MAX = 0.95  # eccentricities are capped here; above it the integrations are not meaningful
SIN_I_MIN = 0.1  # isotropic prior truncated at i >= 5.7 deg (true mass <= 10 x minimum mass)
TWO_PI = 2 * math.pi


@dataclass(frozen=True)
class Body:
    """One planet in simulation units."""

    name: str
    m: float  # Msun
    P: float  # yr
    e: float
    pomega: float  # longitude of periastron in the orbital plane, rad
    M: float  # mean anomaly at the epoch, rad


@dataclass(frozen=True)
class Realization:
    """A complete set of initial conditions for one run."""

    label: str
    m_star: float  # Msun
    bodies: tuple[Body, ...]
    sin_i: float = 1.0  # sin of the system inclination used to scale minimum masses

    def semi_major_axes(self) -> npt.NDArray[np.float64]:
        """Jacobi semi-major axes in AU, as REBOUND sets them when a planet is added by its period."""
        out = []
        interior = self.m_star
        for b in self.bodies:
            total = interior + b.m
            out.append((G_SIM * total * b.P**2 / (4 * math.pi**2)) ** (1 / 3))
            interior += b.m
        return np.array(out)

    def with_body(self, index: int, **changes: float) -> Realization:
        bodies = list(self.bodies)
        bodies[index] = replace(bodies[index], **changes)  # type: ignore[arg-type]
        return replace(self, bodies=tuple(bodies))


def true_to_mean_anomaly(f: float, e: float) -> float:
    """Mean anomaly (rad) for true anomaly ``f`` (rad) and eccentricity ``e``."""
    E = 2 * math.atan2(math.sqrt(1 - e) * math.sin(f / 2), math.sqrt(1 + e) * math.cos(f / 2))
    return (E - e * math.sin(E)) % TWO_PI


def split_normal(rng: np.random.Generator, value: float, err_plus: float, err_minus: float) -> float:
    """One draw from a split normal distribution with mode ``value``."""
    z = float(rng.standard_normal())
    return value + z * (err_plus if z >= 0 else err_minus)


def _draw(rng: np.random.Generator, v: Value, *, positive: bool = False) -> float:
    """Draw a value within its uncertainties (or return it unchanged if it has none)."""
    x = v.require()
    if v.provenance is Provenance.UPPER_LIMIT:
        return float(rng.uniform(0.0, x))
    if not v.has_errors:
        return x
    assert v.err_plus is not None and v.err_minus is not None
    for _ in range(1000):
        y = split_normal(rng, x, v.err_plus, v.err_minus)
        if not positive or y > 0:
            return y
    return x  # errors so large that no positive draw was found; keep the published value


def _nominal(v: Value) -> float:
    return v.require()


def phase_sigma_rad(planet: Planet, t0: float) -> float:
    """1-sigma uncertainty (rad) of the mean longitude at ``t0`` propagated from a reference time."""
    ph = planet.phase
    if ph.kind not in (PhaseKind.TRANSIT, PhaseKind.PERIASTRON) or ph.value is None:
        return math.inf if ph.kind is PhaseKind.RANDOM else 0.0
    P = planet.period_days.require()
    T = ph.value.require()
    s_T = _sym(ph.value)
    s_P = _sym(planet.period_days)
    n = (t0 - T) / P
    return TWO_PI / P * math.hypot(s_T, n * s_P)


def _sym(v: Value) -> float:
    if not v.has_errors:
        return 0.0
    assert v.err_plus is not None and v.err_minus is not None
    return 0.5 * (v.err_plus + v.err_minus)


def choose_epoch(system: System) -> float | None:
    """Common epoch (JD) for the initial conditions.

    If the system defines ``epoch_jd`` it is used. Otherwise, among the published reference times
    (transit or periastron), pick the one that minimises the summed variance of the propagated mean
    longitudes. Returns None if no planet has a time-based phase. Mean anomalies and longitudes are
    defined at the system epoch, so combining them with reference times without ``epoch_jd`` is an error:
    their phase relative to the timed planets would depend on whichever reference time is picked.
    """
    if system.epoch_jd is not None:
        return system.epoch_jd
    angles = [
        p.name for p in system.planets if p.phase.kind in (PhaseKind.MEAN_ANOMALY, PhaseKind.MEAN_LONGITUDE)
    ]
    if angles and any(p.phase.kind in (PhaseKind.TRANSIT, PhaseKind.PERIASTRON) for p in system.planets):
        raise ValueError(
            f"{system.name}: epoch_jd is required when mean anomalies or longitudes "
            f"({', '.join(angles)}) are combined with transit or periastron times"
        )
    times = [
        p.phase.value.require()
        for p in system.planets
        if p.phase.kind in (PhaseKind.TRANSIT, PhaseKind.PERIASTRON) and p.phase.value is not None
    ]
    if not times:
        return None
    timed = [p for p in system.planets if p.phase.kind in (PhaseKind.TRANSIT, PhaseKind.PERIASTRON)]
    return min(times, key=lambda t0: sum(phase_sigma_rad(p, t0) ** 2 for p in timed))


def _mean_anomaly(
    planet: Planet,
    rng: np.random.Generator,
    t0: float | None,
    *,
    P_days: float,
    e: float,
    omega: float,
    draw: bool,
) -> float:
    ph = planet.phase

    def pick(v: Value) -> float:
        return _draw(rng, v) if draw else _nominal(v)

    if ph.kind is PhaseKind.RANDOM or ph.value is None:
        return float(rng.uniform(0.0, TWO_PI))
    if ph.kind is PhaseKind.MEAN_ANOMALY:
        return math.radians(pick(ph.value)) % TWO_PI
    if ph.kind is PhaseKind.MEAN_LONGITUDE:
        return (math.radians(pick(ph.value)) - omega) % TWO_PI
    if t0 is None:  # pragma: no cover - choose_epoch always returns a time when one exists
        raise ValueError("a time-based phase needs a common epoch")
    T = pick(ph.value)
    # Mid-transit / inferior conjunction happens at true anomaly f = pi/2 - omega (Winn 2010, Eq. 6), with omega
    # used as published, whichever orbit the source calls it (docs/data-assumptions.md). In the coplanar dynamical
    # frame this fixes a common line of sight for all planets. At periastron passage M = 0.
    M_ref = true_to_mean_anomaly(math.pi / 2 - omega, e) if ph.kind is PhaseKind.TRANSIT else 0.0
    return (M_ref + TWO_PI * (t0 - T) / P_days) % TWO_PI


def _sin_i(rng: np.random.Generator, prior: InclinationPrior, draw: bool) -> float:
    if prior == "none" or not draw:
        return 1.0
    cos_max = math.sqrt(1 - SIN_I_MIN**2)
    cos_i = float(rng.uniform(0.0, cos_max))
    return math.sqrt(1 - cos_i**2)


def _refuse_misplaced_limits(system: System) -> None:
    """Upper limits make sense only for planet masses and eccentricities (see the module docstring).

    Drawn uniformly from zero, a limited stellar mass gives stars of almost no mass (and its limit is the
    most stable case, not the worst), a limited period reorders the planets, and a limited angle or
    reference time is meaningless.
    """
    values = [("stellar mass", system.star.mass_msun)]
    for p in system.planets:
        values += [(f"{p.name} period", p.period_days), (f"{p.name} omega", p.omega_deg)]
        if p.phase.value is not None:
            values.append((f"{p.name} phase", p.phase.value))
    limited = [what for what, v in values if v.provenance is Provenance.UPPER_LIMIT]
    if limited:
        raise ValueError(
            f"{system.name}: an upper limit is only supported for planet masses and eccentricities, not for "
            + ", ".join(limited)
        )


def realize(
    system: System,
    rng: np.random.Generator,
    *,
    draw: bool,
    label: str,
    inclination_prior: InclinationPrior = "none",
) -> Realization:
    """Build one realization. ``draw=False`` gives the nominal run."""
    _refuse_misplaced_limits(system)
    t0 = choose_epoch(system)

    def pick(v: Value, *, positive: bool = False) -> float:
        return _draw(rng, v, positive=positive) if draw else _nominal(v)

    m_star = pick(system.star.mass_msun, positive=True)
    sin_i = _sin_i(rng, inclination_prior, draw)
    bodies = []
    for p in system.planets:
        P_days = pick(p.period_days, positive=True)
        m_earth = pick(p.mass_earth, positive=True)
        if p.mass_kind is MassKind.MINIMUM:
            m_earth /= sin_i
        e = pick(p.eccentricity)
        if not draw and e > E_MAX:
            # Capping the nominal run would check a different orbit from the one the report shows.
            raise ValueError(
                f"{p.name}: eccentricity {e:g} is above {E_MAX:g}, the largest exostab integrates"
            )
        e = min(max(e, 0.0), E_MAX)
        if p.omega_deg.is_known:
            omega = math.radians(pick(p.omega_deg)) % TWO_PI
        else:
            omega = float(rng.uniform(0.0, TWO_PI))
        M = _mean_anomaly(p, rng, t0, P_days=P_days, e=e, omega=omega, draw=draw)
        body = Body(name=p.name, m=mearth_to_msun(m_earth), P=days_to_years(P_days), e=e, pomega=omega, M=M)
        if not all(math.isfinite(x) for x in (m_star, body.m, body.P, body.e, body.pomega, body.M)):
            # A NaN angle stops an integration at once, which would be reported as a close encounter.
            raise UnusableParametersError(
                f"{p.name}: an error bar is so large that a {label} is not a finite number; use a smaller one"
            )
        bodies.append(body)
    # Drawn periods can change the order of planets with overlapping period uncertainties; keep the
    # bodies ordered from the inside out so that "adjacent pair" always means adjacent orbits.
    bodies.sort(key=lambda b: b.P)
    return Realization(label=label, m_star=m_star, bodies=tuple(bodies), sin_i=sin_i)


def realizations(
    system: System, n_draws: int, seed: int, inclination_prior: InclinationPrior = "none"
) -> list[Realization]:
    """The nominal realization followed by ``n_draws`` Monte Carlo draws, reproducible from ``seed``.

    Each realization has its own random stream (``numpy.random.SeedSequence.spawn``), so adding draws
    never changes the earlier ones.
    """
    streams = np.random.SeedSequence(seed).spawn(n_draws + 1)
    out = [realize(system, np.random.default_rng(streams[0]), draw=False, label="nominal")]
    for k in range(1, n_draws + 1):
        out.append(
            realize(
                system,
                np.random.default_rng(streams[k]),
                draw=True,
                label=f"draw {k}",
                inclination_prior=inclination_prior,
            )
        )
    return out


def orbits_to_years(realization: Realization, n_orbits: float) -> float:
    """Length in years of ``n_orbits`` orbits of the innermost planet."""
    return n_orbits * min(b.P for b in realization.bodies)


def period_ratios(bodies: Sequence[Body]) -> list[float]:
    return [bodies[k + 1].P / bodies[k].P for k in range(len(bodies) - 1)]
