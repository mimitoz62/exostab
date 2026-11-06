"""One-parameter sweeps: how do the indicators change when one planet's parameter is varied?

All other parameters stay at the nominal values (randomized angles are drawn once from the seed and then
held fixed, so the sweep isolates the swept parameter). When the argument of periastron or the period is
changed, the mean anomaly at the epoch is kept.
"""

from __future__ import annotations

import csv
import json
import math
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np

from .indicators import amd, hill
from .indicators.megno import classify_run, megno_seed, run_many
from .integrate import RunConfig
from .models import MASS_MAX_EARTH, PERIOD_MAX_DAYS, PERIOD_MIN_DAYS, System, UnusableParametersError
from .report import software_record
from .sampling import E_MAX, Realization, realizations
from .units import days_to_years, mearth_to_msun

PARAM_LABELS = {
    "e": "eccentricity",
    "mass": "mass (Earth masses)",
    "period": "orbital period (days)",
    "omega": "argument of periastron (deg)",
}


def _run_config(orbits: float) -> RunConfig:
    """Integration settings of every run of a sweep (WHFast with the default time step)."""
    return RunConfig(n_orbits=orbits)


def check_value(param: str, value: float) -> None:
    """Raise ValueError unless ``value`` is a valid value of the swept parameter ``param``."""
    if param not in PARAM_LABELS:
        raise ValueError(f"unknown sweep parameter {param!r}")
    if not math.isfinite(value):
        raise ValueError(f"{PARAM_LABELS[param]} must be a finite number, got {value}")
    if param == "e" and not 0 <= value <= E_MAX:
        raise ValueError(
            f"eccentricity must be in [0, {E_MAX:g}], got {value} ({E_MAX:g} is the largest exostab integrates)"
        )
    if param in ("mass", "period") and value <= 0:
        raise ValueError(f"{param} must be positive, got {value}")
    if param == "mass" and value > MASS_MAX_EARTH:
        raise ValueError(f"mass must be at most {MASS_MAX_EARTH:g} Earth masses, got {value}")
    if param == "period" and not PERIOD_MIN_DAYS <= value <= PERIOD_MAX_DAYS:
        raise ValueError(f"period must be in [{PERIOD_MIN_DAYS:g}, {PERIOD_MAX_DAYS:g}] days, got {value}")


def check_range(param: str, value_range: tuple[float, float]) -> None:
    """Raise ValueError unless every value between the two ends is valid (each valid set is an interval)."""
    for end in value_range:
        check_value(param, end)
    if not math.isfinite(value_range[1] - value_range[0]):
        raise ValueError(
            f"the two ends of the range are too far apart: {value_range[0]} and {value_range[1]}"
        )


def _modified(nominal: Realization, index: int, param: str, value: float) -> Realization:
    check_value(param, value)
    if param == "e":
        r = nominal.with_body(index, e=value)
    elif param == "mass":
        r = nominal.with_body(index, m=mearth_to_msun(value))
    elif param == "period":
        r = nominal.with_body(index, P=days_to_years(value))
    else:
        r = nominal.with_body(index, pomega=math.radians(value) % (2 * math.pi))
    return replace(r, bodies=tuple(sorted(r.bodies, key=lambda b: b.P)), label=f"{param} = {value:.6g}")


def run_sweep(
    system: System,
    planet: str,
    param: str,
    value_range: tuple[float, float],
    steps: int,
    *,
    orbits: float = 1e4,
    seed: int = 0,
    jobs: int | None = None,
) -> list[dict[str, Any]]:
    """Indicators for ``steps`` values of ``param`` between the two ends of ``value_range``."""
    check_range(param, value_range)
    target = system.planet(planet).name
    nominal = realizations(system, 0, seed)[0]
    if param == "mass" and mearth_to_msun(max(value_range)) >= nominal.m_star:
        raise UnusableParametersError(
            f"{target}: a mass of {max(value_range):g} Earth masses is not below the stellar mass"
        )
    index = [b.name for b in nominal.bodies].index(target)
    values = np.linspace(value_range[0], value_range[1], steps)
    reals = [_modified(nominal, index, param, float(v)) for v in values]
    # The analytic indicators come first: if they cannot evaluate a value, no integration has been wasted.
    tables = [hill.pair_table(r) for r in reals]
    analyses = [amd.analyse(r) for r in reals]
    config = _run_config(orbits)
    runs = run_many([(r, replace(config, megno_seed=megno_seed(seed, 0))) for r in reals], jobs)
    rows = []
    for v, r, res, pairs, a in zip(values, reals, runs, tables, analyses, strict=True):
        closest = min(pairs, key=lambda p: p["separation_hill"])
        rows.append(
            {
                "value": float(v),
                "nbody_class": classify_run(res),
                "megno": res.megno,
                "energy_error": res.energy_error,
                "status": res.status,
                "t_end_yr": res.t_end,
                "hill_verdict": hill.classify(r).value,
                "hill_min_separation": closest["separation_hill"],
                "hill_margin_min": min(p["gladman_margin"] for p in pairs),
                "hill_gladman_limit": closest["gladman_critical_hill"],
                "amd_verdict": amd.classify(r).value,
                "amd_beta_max": max(p["beta"] for p in a["pairs"]),
            }
        )
    return rows


def write_sweep(
    rows: list[dict[str, Any]],
    system: System,
    planet: str,
    param: str,
    out_dir: Path,
    *,
    value_range: tuple[float, float],
    steps: int,
    orbits: float,
    seed: int,
    command: str | None = None,
) -> list[Path]:
    """sweep.csv (one row per value), sweep.json (everything needed to repeat the sweep) and sweep.png."""
    from .plots import (
        sweep_figure,  # here, so that a broken MPLBACKEND or matplotlib matters only for figures
    )

    csv_path = out_dir / "sweep.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    config = _run_config(orbits)
    meta = {
        "created_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "command": command,
        "system": system.name,
        "planet": system.planet(planet).name,
        "parameter": param,
        "unit": PARAM_LABELS[param],
        "settings": {
            "value_range": list(value_range),
            "steps": steps,
            "orbits": orbits,  # N-body run length, in orbits of the innermost planet
            "seed": seed,  # fixes the randomized angles held throughout the sweep and the MEGNO seed
            "integrator": config.integrator,
            "dt_fraction": config.dt_fraction,
        },
        "flags": [f.model_dump() for f in system.flags],
        "software": software_record().model_dump(),
        "source": system.source.model_dump(),
    }
    meta_path = out_dir / "sweep.json"
    meta_path.write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
    png = sweep_figure(
        rows,
        f"{PARAM_LABELS[param]} of {system.planet(planet).name}",
        f"{system.name}: sweep of {PARAM_LABELS[param]} for {system.planet(planet).name}",
        out_dir / "sweep.png",
    )
    return [csv_path, png, meta_path]
