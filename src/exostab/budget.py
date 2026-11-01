"""Choose the N-body run length and number of draws from a wall-clock budget.

``exostab check NAME --budget fast`` (about 10 s) or ``--budget thorough`` (about 2 min), or a number of
seconds, replaces a fixed ``--orbits`` / ``--draws``. The speed of this system on this machine is measured
with short WHFast and IAS15 runs, and the most thorough preset whose estimated wall time fits the budget is
chosen from ``PRESETS``. The chosen values are stored in ``report.json`` (``settings.orbits``,
``settings.draws``, ``settings.budget_s``), so a run can always be repeated exactly with
``--orbits``/``--draws``/``--seed``; the choice itself depends on the machine's speed.

The estimate is an upper bound when runs stop early at a close encounter. If even the cheapest preset
exceeds the budget it is used anyway and a warning is returned: exostab never integrates less than
``PRESETS[0]`` (2,000 orbits of the innermost planet, 8 draws).
"""

from __future__ import annotations

import math
import os
import time
from dataclasses import dataclass

from .integrate import RunConfig, run
from .sampling import Realization

BUDGETS = {"fast": 10.0, "thorough": 120.0}

# (orbits of the innermost planet, Monte Carlo draws), cheapest first.
PRESETS: tuple[tuple[float, int], ...] = (
    (2e3, 8),
    (5e3, 10),
    (1e4, 20),
    (2e4, 30),
    (5e4, 50),
    (1e5, 100),
)
OVERHEAD_S = 1.5  # worker start-up, analytic indicators and figures (measured about 1-2 s)
# Runs are slower when every core is busy than in the single-process speed measurement (shared caches,
# efficiency cores, clock limits). Measured 1.3 on an Apple M4 Pro with 13 workers.
CONTENTION = 1.3


@dataclass(frozen=True)
class Plan:
    orbits: float
    draws: int
    budget_s: float
    estimated_s: float
    whfast_s_per_orbit: float
    ias15_s_per_orbit: float
    warning: str | None = None


def parse_budget(value: str | float) -> float:
    """Seconds for "fast", "thorough" or a positive number of seconds."""
    if isinstance(value, (int, float)):
        seconds = float(value)
    elif value.strip().lower() in BUDGETS:
        seconds = BUDGETS[value.strip().lower()]
    else:
        try:
            seconds = float(value)
        except ValueError as exc:
            raise ValueError(
                f"budget must be 'fast', 'thorough' or a number of seconds, got {value!r}"
            ) from exc
    if not seconds > 0 or not math.isfinite(seconds):
        raise ValueError(f"budget must be a positive, finite number of seconds, got {value!r}")
    return seconds


def _seconds_per_orbit(real: Realization, integrator: str, min_orbits: float, min_wall: float) -> float:
    """Wall time per orbit of the innermost planet, from a short run with MEGNO."""
    orbits = min_orbits
    while True:
        res = run(real, RunConfig(n_orbits=orbits, integrator=integrator))  # type: ignore[arg-type]
        done = max(res.n_orbits_innermost, 1.0)
        stopped = res.status not in ("completed", "star_approach")  # a star approach does not stop a run
        if res.walltime >= min_wall or stopped or orbits >= 64 * min_orbits:
            return res.walltime / done
        orbits *= 4


def estimate_seconds(
    orbits: float, draws: int, s_wh: float, s_ias: float, workers: int, ias15_check: bool = True
) -> float:
    """Estimated wall time of a check with ``draws`` draws of ``orbits`` orbits on ``workers`` processes."""
    jobs = [orbits * s_wh] * (draws + 1) + ([orbits * s_ias] if ias15_check else [])
    slowdown = CONTENTION if workers > 1 else 1.0
    return OVERHEAD_S + slowdown * max(sum(jobs) / max(workers, 1), max(jobs))


def plan(nominal: Realization, budget_s: float, *, jobs: int | None = None, ias15_check: bool = True) -> Plan:
    """The most thorough preset whose estimated wall time fits ``budget_s``."""
    workers = jobs or max(1, (os.cpu_count() or 2) - 1)
    t0 = time.perf_counter()
    s_wh = _seconds_per_orbit(nominal, "whfast", min_orbits=100, min_wall=0.05)
    s_ias = _seconds_per_orbit(nominal, "ias15", min_orbits=10, min_wall=0.05) if ias15_check else 0.0
    remaining = budget_s - (time.perf_counter() - t0)
    chosen, estimate = PRESETS[0], estimate_seconds(*PRESETS[0], s_wh, s_ias, workers, ias15_check)
    for orbits, draws in PRESETS:
        est = estimate_seconds(orbits, draws, s_wh, s_ias, workers, ias15_check)
        if est <= remaining:
            chosen, estimate = (orbits, draws), est
    warning = None
    if estimate > remaining:
        warning = (
            f"Even the smallest run ({PRESETS[0][0]:,.0f} orbits, {PRESETS[0][1]} draws) needs about "
            f"{estimate:.0f} s, more than the {budget_s:g} s budget; it is used anyway."
        )
    return Plan(
        orbits=chosen[0],
        draws=chosen[1],
        budget_s=budget_s,
        estimated_s=estimate,
        whfast_s_per_orbit=s_wh,
        ias15_s_per_orbit=s_ias,
        warning=warning,
    )
