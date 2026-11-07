"""Direct N-body integrations with REBOUND.

Set-up (justified choices; see also DECISIONS.md):

* Units are set explicitly to (yr, AU, Msun) before any particle is added.
* Planets are added by orbital period in Jacobi coordinates (REBOUND's default when no primary is
  given), all in one plane (inclination 0): exostab models systems as coplanar because published
  sky-plane inclinations do not determine the mutual inclinations.
* WHFast (Rein & Tamayo 2015), a symplectic Wisdom-Holman integrator, is used for all runs. Its
  timestep is ``dt_fraction`` (default 1/30) of the shortest *pericentre passage timescale*
  T_p = 2 pi / f_dot_p = P (1 - e)^(3/2) / (1 + e)^(1/2) over all planets, where f_dot_p is the rate
  of change of the true anomaly at pericentre. Wisdom (2015) found 1/20 of T_p typically adequate to
  resolve the pericentre passage (as restated by Hadden & Lithwick 2018, who used 1/30). For circular
  orbits our step is P_min / 30, finer than the P_min / 20 required by the project brief and the same
  as the HD 127195 Research Note; for eccentric orbits it shrinks accordingly.
* IAS15 (Rein & Spiegel 2015), an adaptive high-order integrator, repeats the nominal run as an
  independent check; it does not rely on a fixed timestep and handles close approaches accurately.
* MEGNO (Cincotta & Simo 2000) is computed from REBOUND's variational equations (Rein & Tamayo 2016).
* A run stops early with a *close encounter* when two planets come closer than the mean of their Hill
  radii, (R_H,j + R_H,k) / 2 with R_H,k = a_k (m_k / 3 M_*)^(1/3). This uses REBOUND's collision detection
  ("line" mode, which also catches passages between two steps) with each planet given a radius of half its
  Hill radius. For two similar planets this equals the HD 127195 Research Note's rule (the smaller Hill
  radius); unlike a single global distance, it also works when the system contains a much smaller planet
  (DECISIONS.md, D20). The run stops with an *escape* when a
  body moves farther than ``escape_factor`` (default 100) times the largest semi-major axis from the
  centre of mass.
* REBOUND's collision search also pairs each planet with the star (radius 0), so it reports a planet that
  comes closer to the star than half its own Hill radius: a pericentre a (1 - e) < 0.5 a (m / 3 M_*)^(1/3),
  i.e. e above about 0.965 for one Jupiter mass and 0.925 for ten around a Sun-like star, from the start or
  after the eccentricity has grown. That is not a close encounter between planets, so it does not stop the
  run; a run that reaches its end is labelled ``star_approach`` instead of ``completed``. exostab models
  neither tides, nor general relativity, nor the size of the star, which can all matter that close, so such
  a run gets no verdict (:mod:`exostab.indicators.megno`). The distance is not a physical limit (stellar and
  planetary radii are not part of the model); it is where the collision search fires (DECISIONS.md, D20).
* The relative energy error |E(t) - E(0)| / |E(0)| is measured at ``ENERGY_CHECKS`` equally spaced times in
  every run (the nominal run, every Monte Carlo draw, the IAS15 check, catalog and sweep runs alike) and when a
  run stops early; the maximum is reported. The time series kept for the plots (``n_samples``) is a subset of
  these checks, so it cannot change the result. WHFast's error oscillates and peaks at pericentre passages, so
  the error at the end of a run alone can be orders of magnitude below this maximum. A run whose maximum
  exceeds the threshold in :mod:`exostab.indicators.megno` is classified as inconclusive instead of receiving
  a verdict.
* A run can be given a wall-clock limit (``RunConfig.max_seconds``). The time is read at each of the
  ``ENERGY_CHECKS`` checkpoints, so the check is cheap; a run that has not reached its end when the limit has
  passed stops at that checkpoint with the status ``time_limit``, and gets no verdict
  (:mod:`exostab.indicators.megno`): a run cut short says nothing about the time it did not reach. A run that ends
  before the limit is the same as without one.
"""

from __future__ import annotations

import ctypes
import math
import signal
import threading
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Literal

import rebound

from .sampling import Realization
from .units import SIM_UNITS

Integrator = Literal["whfast", "ias15"]
# completed: reached the requested length; star_approach: reached it, but a planet passed closer to the star
# than half its Hill radius; encounter / escape: stopped early; time_limit: stopped early by the wall-clock limit
# (RunConfig.max_seconds); error: the integration failed.
Status = Literal["completed", "star_approach", "encounter", "escape", "time_limit", "error"]

# Number of equally spaced times at which every run checks its relative energy error (DECISIONS.md, D8).
ENERGY_CHECKS = 1200


@dataclass(frozen=True)
class RunConfig:
    """How to integrate one realization."""

    n_orbits: float = 1e4  # length, in orbits of the innermost planet
    integrator: Integrator = "whfast"
    dt_fraction: float = 1 / 30  # WHFast step as a fraction of the shortest pericentre timescale
    megno: bool = True
    megno_seed: int = 0
    n_samples: int = 0  # time-series samples kept for the plots (0: none; at most ENERGY_CHECKS)
    escape_factor: float = 100.0
    # Wall-clock limit in seconds (None: none). A duration, not a time: the clock starts when the run starts, in the
    # process that integrates it, because the clocks of two processes need not share a reference point.
    max_seconds: float | None = None


@dataclass
class RunResult:
    """Outcome of one integration."""

    label: str
    integrator: str
    dt: float | None  # yr (None for IAS15, which is adaptive)
    t_target: float  # yr
    t_end: float  # yr, time actually reached
    status: Status
    megno: float | None
    lyapunov: float | None  # 1/yr
    energy_error: float  # maximum relative energy error at the ENERGY_CHECKS checkpoints and at a stop
    walltime: float  # s
    encounter_distance: float  # AU
    n_orbits_innermost: float
    n_orbits_outermost: float
    series: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    star_approach: str | None = None  # first planet that came closer to the star than half its Hill radius


def pericentre_timescale(P: float, e: float) -> float:
    """P (1 - e)^(3/2) / (1 + e)^(1/2): 2 pi divided by the angular velocity at pericentre."""
    return float(P * (1 - e) ** 1.5 / math.sqrt(1 + e))


def timestep(real: Realization, dt_fraction: float) -> float:
    """WHFast timestep in years (see module docstring)."""
    return dt_fraction * min(pericentre_timescale(b.P, b.e) for b in real.bodies)


ENCOUNTER_HILL_FRACTION = 0.5  # collision radius of a planet, as a fraction of its Hill radius


def encounter_distance(real: Realization) -> float:
    """Smallest close-encounter distance over adjacent pairs, (R_H,j + R_H,k) / 2, in AU (for reports)."""
    r = hill_radii(real)
    return min(ENCOUNTER_HILL_FRACTION * (r[k] + r[k + 1]) for k in range(len(r) - 1))


def hill_radii(real: Realization) -> list[float]:
    a = real.semi_major_axes()
    return [float(a[k]) * (b.m / (3 * real.m_star)) ** (1 / 3) for k, b in enumerate(real.bodies)]


def _resolve_collision(star_approaches: list[int]) -> Callable[[Any, Any], int]:
    """REBOUND collision callback: two planets halt the run; a planet and the star are only recorded.

    The index of a planet passing the star is appended to ``star_approaches`` (first time only).
    """

    def resolve(sim_p: Any, c: Any) -> int:
        if c.p1 == 0 or c.p2 == 0:
            if not star_approaches:
                star_approaches.append(int(max(c.p1, c.p2)))
            return 0  # keep both particles and go on
        return int(rebound.clibrebound.reb_collision_resolve_halt(sim_p, c))

    return resolve


def build_simulation(
    real: Realization, config: RunConfig, star_approaches: list[int] | None = None
) -> rebound.Simulation:
    """A REBOUND simulation of ``real`` in (yr, AU, Msun), centred on the centre of mass.

    Close encounters between planets halt the integration (``rebound.Collision``); a planet passing within
    half its Hill radius of the star does not, and its particle index is appended to ``star_approaches``.
    """
    sim = rebound.Simulation()
    sim.units = SIM_UNITS
    sim.add(m=real.m_star)
    for b in real.bodies:
        # inc = 0: coplanar. Omega = 0, so pomega = omega; M is the mean anomaly at the epoch.
        sim.add(m=b.m, P=b.P, e=b.e, inc=0.0, Omega=0.0, omega=b.pomega, M=b.M)
    sim.move_to_com()
    sim.integrator = config.integrator
    if config.integrator == "whfast":
        sim.dt = timestep(real, config.dt_fraction)
    for k, rh in enumerate(hill_radii(real)):
        sim.particles[k + 1].r = ENCOUNTER_HILL_FRACTION * rh
    sim.collision = "line"
    sim.collision_resolve = _resolve_collision([] if star_approaches is None else star_approaches)
    sim.exit_max_distance = config.escape_factor * max(p.a for p in sim.particles[1:])
    return sim


def _c_sigint_api() -> tuple[Any, Any] | None:
    """PyOS_getsig and PyOS_setsig of Python's C API, or None where ctypes cannot reach them."""
    try:
        getsig, setsig = ctypes.pythonapi.PyOS_getsig, ctypes.pythonapi.PyOS_setsig
    except (AttributeError, OSError):  # pragma: no cover - an interpreter that does not export them
        return None
    getsig.restype, getsig.argtypes = ctypes.c_void_p, [ctypes.c_int]
    setsig.restype, setsig.argtypes = ctypes.c_void_p, [ctypes.c_int, ctypes.c_void_p]
    return getsig, setsig


_C_SIGINT_API = _c_sigint_api()
_sigint_lock = threading.Lock()
_sigint_runs = 0  # runs integrating in this process, in any thread
_sigint_saved: Any = None


@contextmanager
def _sigint_handler_kept() -> Iterator[None]:
    """Put back the C handler for SIGINT that REBOUND replaces when it integrates and leaves in place.

    Ctrl-C still stops a run while it integrates, but afterwards it no longer reached Python: the web app's server, for
    one, could not be stopped from its terminal. PyOS_setsig works from any thread, unlike signal.signal. The handler
    is saved by the first of overlapping runs (two sessions of the web app) and put back by the last one, so that no
    run saves REBOUND's handler as the one to restore.
    """
    global _sigint_runs, _sigint_saved
    if _C_SIGINT_API is None:  # pragma: no cover
        yield
        return
    getsig, setsig = _C_SIGINT_API
    with _sigint_lock:
        if _sigint_runs == 0:
            _sigint_saved = getsig(signal.SIGINT)
        _sigint_runs += 1
    try:
        yield
    finally:
        with _sigint_lock:
            _sigint_runs -= 1
            if _sigint_runs == 0:
                setsig(signal.SIGINT, _sigint_saved)


def run(real: Realization, config: RunConfig) -> RunResult:
    """Integrate one realization and return what happened. Never raises for physical outcomes."""
    t_wall = time.perf_counter()
    deadline = None if config.max_seconds is None else time.monotonic() + config.max_seconds
    star_approaches: list[int] = []
    sim = build_simulation(real, config, star_approaches)
    if config.megno:
        sim.init_megno(seed=config.megno_seed)
    periods = [b.P for b in real.bodies]
    t_target = config.n_orbits * min(periods)
    e0 = sim.energy()
    n_planets = len(real.bodies)
    series: dict[str, Any] = {"t": [], "megno": [], "energy_error": []}
    series.update({f"x{k}": [] for k in range(n_planets)})
    series.update({f"y{k}": [] for k in range(n_planets)})
    max_err = 0.0
    status: Status = "completed"
    error: str | None = None

    def sample(keep: bool) -> None:
        nonlocal max_err
        err = abs((sim.energy() - e0) / e0)
        max_err = max(max_err, err)
        if keep:
            series["t"].append(sim.t)
            series["megno"].append(sim.megno() if config.megno else math.nan)
            series["energy_error"].append(err)
            star = sim.particles[0]
            for k in range(n_planets):
                p = sim.particles[k + 1]
                series[f"x{k}"].append(p.x - star.x)
                series[f"y{k}"].append(p.y - star.y)

    # The energy error is checked at the same ENERGY_CHECKS checkpoints in every run, so that the
    # classification never depends on n_samples; the time series is kept at n_samples of them, as evenly spaced
    # as the grid allows, so no plotted error exceeds the reported maximum.
    checkpoints = [t_target * (i + 1) / ENERGY_CHECKS for i in range(ENERGY_CHECKS)]
    n_keep = min(config.n_samples, ENERGY_CHECKS)
    kept = {round((j + 1) * ENERGY_CHECKS / n_keep) - 1 for j in range(n_keep)}
    try:
        with _sigint_handler_kept():
            if n_keep:
                sample(keep=True)
            for i, tc in enumerate(checkpoints):
                # exact_finish_time=0: never shorten a step to land on the checkpoint, so sampling does not
                # change the trajectory of a fixed-step integrator. A step can therefore overshoot the next
                # checkpoints when they are closer together than one step (short runs); those are skipped, because
                # REBOUND would integrate backwards (with a negative dt) to reach them.
                if tc <= sim.t:
                    continue
                sim.integrate(tc, exact_finish_time=0)
                sample(keep=i in kept)
                if deadline is not None and sim.t < t_target and time.monotonic() >= deadline:
                    status = "time_limit"
                    break
    except (rebound.Collision, rebound.Encounter):
        status = "encounter"
    except rebound.Escape:
        status = "escape"
    except Exception as exc:  # pragma: no cover - defensive: REBOUND errors we do not expect
        status = "error"
        error = f"{type(exc).__name__}: {exc}"
    if status != "completed":
        try:
            max_err = max(max_err, abs((sim.energy() - e0) / e0))
        except Exception:  # pragma: no cover
            max_err = math.inf
    megno = lyap = None
    if config.megno:
        megno, lyap = float(sim.megno()), float(sim.lyapunov())
    star_planet = real.bodies[star_approaches[0] - 1].name if star_approaches else None
    if status == "completed" and star_planet is not None:
        status = "star_approach"
    if not math.isfinite(max_err):
        status, error = "error", error or "non-finite energy"
    return RunResult(
        label=real.label,
        integrator=config.integrator,
        dt=sim.dt if config.integrator == "whfast" else None,
        t_target=t_target,
        t_end=float(sim.t),
        status=status,
        megno=megno,
        lyapunov=lyap,
        energy_error=max_err,
        walltime=time.perf_counter() - t_wall,
        encounter_distance=encounter_distance(real),
        n_orbits_innermost=float(sim.t) / min(periods),
        n_orbits_outermost=float(sim.t) / max(periods),
        series=series if config.n_samples else {},
        error=error,
        star_approach=star_planet,
    )
