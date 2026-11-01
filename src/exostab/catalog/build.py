"""Batch catalog: stability indicators for every multi-planet system in the archive table.

Each system runs in its own process with a hard wall-clock cap (``max_seconds``). A system that exceeds
the cap is recorded with ``status = timeout`` and no verdict, rather than being given a shorter run
silently. Systems the completion rules cannot model (for example circumbinary planets, a planet with
neither a mass nor a radius, or a host with a single planet row because its other planets orbit a companion
star) are recorded with ``status = skipped`` and the reason.

Each row is computed by :func:`exostab.analysis.check_system`, the function behind ``exostab check``, so for
the same system, run length, draws and seed the verdicts are those of ``exostab check``. The catalog keeps no
time series for plots, which does not change any result (see :mod:`exostab.integrate`).
"""

from __future__ import annotations

import csv
import json
import multiprocessing as mp
import os
import queue
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from rich.console import Console

from .. import __version__
from ..data import IncompleteSystemError, load_rows, system_from_rows
from ..data.archive import Row, group_by_host
from ..data.store import TableInfo

COLUMNS = [
    "system",
    "n_planets",
    "status",
    "reason",
    "overall",
    "hill",
    "amd",
    "nbody",
    "hill_min_separation",
    "amd_beta_max",
    "megno_nominal",
    "hill_summary",
    "amd_summary",
    "overall_summary",
    "nbody_regular",
    "nbody_chaotic",
    "nbody_unstable",
    "nbody_inconclusive",
    "energy_error_nominal",
    "t_end_yr",
    "orbits",
    "draws",
    "seed",
    "completion_rules",
    "n_flags",
    "archive_rows",
    "data_source",
    "data_retrieved_utc",
    "exostab_version",
    "rebound_version",
    "runtime_s",
]


@dataclass(frozen=True)
class CatalogSettings:
    orbits: float = 1e4
    draws: int = 10
    seed: int = 0
    max_seconds: float = 120.0
    jobs: int | None = None


def _empty(
    host: str, n: int, status: str, reason: str, settings: CatalogSettings, info: TableInfo
) -> dict[str, Any]:
    row: dict[str, Any] = dict.fromkeys(COLUMNS)
    row.update(
        system=host,
        n_planets=n,
        status=status,
        reason=reason,
        orbits=settings.orbits,
        draws=settings.draws,
        seed=settings.seed,
        data_source=info.kind,
        data_retrieved_utc=info.retrieved_utc,
        exostab_version=__version__,
    )
    return row


def check_one(rows: list[Row], info: TableInfo, settings: CatalogSettings) -> dict[str, Any]:
    """Catalog row for one host (runs in a worker process)."""
    from ..analysis import CheckSettings, check_system

    host = str(rows[0]["hostname"])
    try:
        system = system_from_rows(rows, info)
    except (IncompleteSystemError, ValueError) as exc:
        return _empty(host, len(rows), "skipped", str(exc), settings, info)
    result = check_system(
        system,
        CheckSettings(orbits=settings.orbits, draws=settings.draws, seed=settings.seed, jobs=1, n_samples=0),
    )
    rep = result.report
    ind = rep.indicators
    counts = ind["nbody"].details["classification_counts"]
    row = _empty(host, len(system.planets), "ok", "", settings, info)
    row.update(
        overall=rep.overall.verdict.value,
        hill=ind["hill"].verdict.value,
        amd=ind["amd"].verdict.value,
        nbody=ind["nbody"].verdict.value,
        hill_min_separation=min(p["separation_hill"] for p in ind["hill"].details["pairs"]),
        amd_beta_max=max(p["beta"] for p in ind["amd"].details["pairs"]),
        megno_nominal=result.runs[0].megno,
        hill_summary=ind["hill"].summary,
        amd_summary=ind["amd"].summary,
        overall_summary=rep.overall.summary,
        nbody_regular=counts["regular"],
        nbody_chaotic=counts["chaotic"],
        nbody_unstable=counts["unstable"],
        nbody_inconclusive=counts["inconclusive"],
        energy_error_nominal=result.runs[0].energy_error,
        t_end_yr=rep.settings.t_end_yr,
        completion_rules=";".join(sorted({f.rule for f in system.flags})),
        n_flags=len(system.flags),
        archive_rows=";".join(rep.data.archive_rows),
        rebound_version=rep.software.rebound,
        runtime_s=round(rep.runtime_s, 2),
    )
    return row


# Seconds a worker may take to exit after SIGTERM before it is killed. A Python-level SIGTERM handler (for
# example coverage's ``sigterm = true``) runs only when REBOUND returns from C (sim.integrate to the next
# energy checkpoint, which can take long for a slow system), so terminate() alone does not enforce the cap.
KILL_AFTER_S = 5.0


def _stop(p: Any, grace_s: float = KILL_AFTER_S) -> None:
    """Stop worker process ``p``: SIGTERM, then SIGKILL if it is still alive after ``grace_s`` seconds."""
    p.terminate()
    p.join(timeout=grace_s)
    if p.is_alive():
        p.kill()
        p.join()


def _worker(rows: list[Row], info: TableInfo, settings: CatalogSettings, out: Any) -> None:
    host = str(rows[0]["hostname"])
    try:
        out.put((host, check_one(rows, info, settings)))
    except Exception as exc:  # pragma: no cover - reported as an error row
        out.put((host, _empty(host, len(rows), "error", f"{type(exc).__name__}: {exc}", settings, info)))


def build_catalog(
    settings: CatalogSettings,
    out_dir: Path,
    *,
    limit: int = 0,
    refresh: bool = False,
    offline: bool = False,
    console: Console | None = None,
) -> tuple[list[Path], list[dict[str, Any]]]:
    rows, info = load_rows(refresh=refresh, offline=offline)
    # Every host of the table (sy_pnum >= 2) gets a row: a host with a single planet row, whose other planets
    # orbit a companion star, is recorded as skipped with the reason, like any other system exostab cannot model.
    hosts = sorted(group_by_host(rows).items(), key=lambda x: x[0].lower())
    if limit:
        hosts = hosts[:limit]
    n_workers = settings.jobs or max(1, (os.cpu_count() or 2) - 1)
    ctx = mp.get_context("spawn")
    results: dict[str, dict[str, Any]] = {}
    q = ctx.Queue()
    pending = list(hosts)
    active: dict[str, tuple[Any, float, int]] = {}
    while pending or active:
        while pending and len(active) < n_workers:
            host, rs = pending.pop(0)
            p = ctx.Process(target=_worker, args=(rs, info, settings, q), daemon=True)
            p.start()
            active[host] = (p, time.monotonic(), len(rs))
        try:
            while True:
                host, row = q.get(timeout=0.2)
                results[host] = row
                if console is not None:
                    console.print(
                        f"[dim]{len(results)}/{len(hosts)}[/dim] {host}: {row['overall'] or row['status']}"
                    )
        except queue.Empty:
            pass
        for host, (p, start, n) in list(active.items()):
            if host in results:
                p.join(timeout=5)
                del active[host]
            elif time.monotonic() - start > settings.max_seconds:
                _stop(p)
                results[host] = _empty(
                    host, n, "timeout", f"exceeded {settings.max_seconds:g} s", settings, info
                )
                del active[host]
                if console is not None:
                    console.print(f"[dim]{len(results)}/{len(hosts)}[/dim] {host}: timeout")
            elif not p.is_alive() and p.exitcode not in (0, None):
                results[host] = _empty(
                    host, n, "error", f"worker exited with code {p.exitcode}", settings, info
                )
                del active[host]
    out_rows = [results[h] for h, _ in hosts]
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = [_write_csv(out_rows, out_dir / "catalog.csv")]
    parquet = _write_parquet(out_rows, out_dir / "catalog.parquet")
    if parquet is not None:
        paths.append(parquet)
    meta = {
        "created_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "exostab_version": __version__,
        "settings": asdict(settings),
        "data_source": info.kind,
        "data_retrieved_utc": info.retrieved_utc,
        "n_systems": len(out_rows),
        "columns": COLUMNS,
    }
    meta_path = out_dir / "catalog_meta.json"
    meta_path.write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
    paths.append(meta_path)
    return paths, out_rows


def _write_csv(rows: list[dict[str, Any]], path: Path) -> Path:
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=COLUMNS)
        w.writeheader()
        w.writerows(rows)
    return path


def _write_parquet(rows: list[dict[str, Any]], path: Path) -> Path | None:
    try:
        import pyarrow as pa
        import pyarrow.parquet as pq
    except ImportError:
        return None
    table = pa.Table.from_pylist(rows)
    pq.write_table(table, path)
    return path
