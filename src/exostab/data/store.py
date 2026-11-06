"""Where archive rows come from: the live archive, the on-disk cache, or the bundled offline snapshot.

Order of preference for ``load_rows()``:

1. ``offline=True`` (or the environment variable ``EXOSTAB_OFFLINE=1``): the bundled snapshot only.
2. ``refresh=True``: query the archive now and overwrite the cache (fails loudly if the archive cannot
   be reached, because the user explicitly asked for fresh data).
3. Otherwise: the cache if it exists; if not, query the archive and fill the cache; if the archive
   cannot be reached, fall back to the snapshot with a warning that is carried into the report.

The cache lives in the platform's user cache directory (``platformdirs``), or in ``EXOSTAB_CACHE_DIR``
if that is set.
"""

from __future__ import annotations

import contextlib
import csv
import hashlib
import json
import os
import sys
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from importlib import resources
from pathlib import Path

import platformdirs

from .. import __version__
from ..models import SourceKind
from .archive import (
    MULTI_PLANET_WHERE,
    TABLE,
    TAP_SERVICE,
    ArchiveError,
    Row,
    fetch_rows,
    group_by_host,
    read_csv,
    write_csv,
)

CACHE_TABLE = "pscomppars_multi.csv"
CACHE_META = "pscomppars_multi.json"
SNAPSHOT_TABLE = "pscomppars_snapshot.csv"
SNAPSHOT_META = "snapshot.json"
# A table in which more than this fraction of the single-star hosts lack planets (fewer rows than sy_pnum) was cut
# on the way. No host of the real tables lacks any (2026-09-28 and 2026-10-31).
MAX_SHORT_HOSTS = 0.01


@dataclass(frozen=True)
class TableInfo:
    kind: SourceKind  # "archive", "archive-cache" or "snapshot"
    retrieved_utc: str | None
    path: str | None
    note: str | None = None


def cache_dir() -> Path:
    env = os.environ.get("EXOSTAB_CACHE_DIR")
    return Path(env).expanduser() if env else platformdirs.user_cache_path("exostab")


def offline_requested() -> bool:
    return os.environ.get("EXOSTAB_OFFLINE", "").strip().lower() in ("1", "true", "yes")


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def load_snapshot() -> tuple[list[Row], TableInfo]:
    pkg = resources.files("exostab.data.snapshot")
    rows = read_csv(pkg.joinpath(SNAPSHOT_TABLE).read_text(encoding="utf-8"))
    meta = json.loads(pkg.joinpath(SNAPSHOT_META).read_text(encoding="utf-8"))
    return rows, TableInfo(
        kind="snapshot",
        retrieved_utc=meta.get("retrieved_utc"),
        path=f"exostab/data/snapshot/{SNAPSHOT_TABLE}",
        note=f"offline snapshot of {meta.get('n_systems')} systems",
    )


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_cache() -> tuple[list[Row], TableInfo] | None:
    """The cached table, or None if there is none or it is damaged (it is then rebuilt).

    The table must have the row count, and the checksum if one is recorded, stored in the metadata: a table
    cut off by an interrupted write would otherwise load silently, with planets missing.
    """
    d = cache_dir()
    table, meta = d / CACHE_TABLE, d / CACHE_META
    try:
        if not (table.exists() and meta.exists()):
            return None
        info = json.loads(meta.read_text(encoding="utf-8"))
        if not isinstance(info, dict) or ("sha256" in info and info["sha256"] != _sha256(table)):
            return None
        rows = read_csv(table)
    except (OSError, ValueError, OverflowError, csv.Error, ArchiveError):
        return None  # a damaged or unreadable cache is ignored and rebuilt
    retrieved = info.get("retrieved_utc")
    if len(rows) != info.get("n_rows") or not isinstance(retrieved, (str, type(None))):
        return None
    return rows, TableInfo(kind="archive-cache", retrieved_utc=retrieved, path=str(table))


def _refuse_cut_table(rows: list[Row]) -> None:
    """Raise ArchiveError for an answer that must not replace a cache: empty, or with planets missing."""
    if not rows:
        raise ArchiveError("the archive's answer has no rows")
    single = [rs for rs in group_by_host(rows).values() if rs[0].get("sy_snum") == 1]
    short = [rs for rs in single if rs[0].get("sy_pnum") is not None and len(rs) < rs[0]["sy_pnum"]]
    if len(short) > MAX_SHORT_HOSTS * len(single):
        raise ArchiveError(
            f"the archive's answer looks cut: {len(short)} of {len(single)} single-star hosts have fewer rows than "
            "their number of planets"
        )


def refresh_cache() -> tuple[list[Row], TableInfo]:
    """Query the archive and replace the cache.

    Both files are written to temporary names of their own first and then renamed into place, so an interrupted
    write leaves the previous cache intact, and processes filling the same cache do not disturb each other. If
    the cache cannot be written (a read-only home folder, for example), the rows are still returned, with a note.
    """
    print("Downloading the archive table...", file=sys.stderr, flush=True)
    rows = fetch_rows(MULTI_PLANET_WHERE)
    _refuse_cut_table(rows)
    d = cache_dir()
    stamp = _now()
    table, meta_path = d / CACHE_TABLE, d / CACHE_META
    unique = f"{os.getpid()}.{uuid.uuid4().hex[:8]}.tmp"
    tmp_table, tmp_meta = d / f"{CACHE_TABLE}.{unique}", d / f"{CACHE_META}.{unique}"
    try:
        d.mkdir(parents=True, exist_ok=True)
        write_csv(rows, tmp_table)
        meta = {
            "retrieved_utc": stamp,
            "table": TABLE,
            "service": TAP_SERVICE,
            "where": MULTI_PLANET_WHERE,
            "n_rows": len(rows),
            "sha256": _sha256(tmp_table),
            "exostab_version": __version__,
        }
        tmp_meta.write_text(json.dumps(meta, indent=2), encoding="utf-8")
        os.replace(tmp_table, table)
        os.replace(tmp_meta, meta_path)
    except OSError as exc:
        note = f"the table could not be saved in the cache folder {d} ({exc}); it will be downloaded again next time"
        return rows, TableInfo(kind="archive", retrieved_utc=stamp, path=None, note=note)
    finally:
        with contextlib.suppress(OSError):
            tmp_table.unlink(missing_ok=True)
            tmp_meta.unlink(missing_ok=True)
    return rows, TableInfo(kind="archive", retrieved_utc=stamp, path=str(table))


def load_rows(*, refresh: bool = False, offline: bool = False) -> tuple[list[Row], TableInfo]:
    """Archive rows for all multi-planet systems, and where they came from."""
    if offline or offline_requested():
        return load_snapshot()
    if refresh:
        return refresh_cache()
    cached = load_cache()
    if cached is not None:
        return cached
    try:
        return refresh_cache()
    except ArchiveError as exc:
        rows, info = load_snapshot()
        note = f"archive unreachable ({exc}); using the offline snapshot instead"
        return rows, TableInfo(kind=info.kind, retrieved_utc=info.retrieved_utc, path=info.path, note=note)
