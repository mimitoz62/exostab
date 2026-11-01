"""Client for the NASA Exoplanet Archive Planetary Systems Composite Parameters table (``pscomppars``).

The table is queried through the archive's Table Access Protocol (TAP) service with astroquery. Column
names were checked against ``TAP_SCHEMA.columns`` on 2026-09-28 (DECISIONS.md, D6). Rows are kept as
plain dictionaries (``None`` for missing values) so that the live archive, the on-disk cache and the
offline snapshot all look the same to the rest of the package.
"""

from __future__ import annotations

import csv
import io
import math
import time
import warnings
from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import Any

TABLE = "pscomppars"
ARCHIVE_URL = "https://exoplanetarchive.ipac.caltech.edu"  # base for the relative links in *_reflink cells
TAP_SERVICE = "https://exoplanetarchive.ipac.caltech.edu/TAP"
MULTI_PLANET_WHERE = "sy_pnum >= 2"
# Seconds for each attempt to connect, and without receiving any data once connected. astroquery and pyvo set no
# timeout, so a server that accepted the query and then stalled kept exostab waiting without end.
CONNECT_TIMEOUT_S, READ_TIMEOUT_S = 30.0, 120.0

Row = dict[str, Any]

# (column, type). Units follow TAP_SCHEMA: periods and times in days, angles in degrees, planet masses
# in Earth masses, radii in Earth radii, stellar mass in solar masses, semi-major axis in AU.
_ERR = ("err1", "err2")
COLUMNS: list[tuple[str, str]] = [
    ("pl_name", "str"),
    ("hostname", "str"),
    ("pl_letter", "str"),
    ("sy_pnum", "int"),
    ("sy_snum", "int"),
    ("cb_flag", "int"),
    ("tran_flag", "int"),
    ("rv_flag", "int"),
    ("ttv_flag", "int"),
    ("pl_controv_flag", "int"),
    ("discoverymethod", "str"),
    ("disc_year", "int"),
]
for _base in (
    "pl_orbper",
    "pl_orbsmax",
    "pl_orbeccen",
    "pl_orblper",
    "pl_orbtper",
    "pl_tranmid",
    "pl_bmasse",
    "pl_rade",
    "pl_orbincl",
    "st_mass",
):
    COLUMNS += [
        (_base, "float"),
        (_base + "err1", "float"),
        (_base + "err2", "float"),
        (_base + "lim", "int"),
        (_base + "_reflink", "str"),
    ]
COLUMNS += [("pl_bmassprov", "str")]
COLUMN_NAMES = [c for c, _ in COLUMNS]
_TYPES = dict(COLUMNS)


class ArchiveError(RuntimeError):
    """The archive could not be queried."""


def _clean(value: Any, kind: str) -> Any:
    """Convert one table cell to a plain Python value (None if missing)."""
    if value is None:
        return None
    if hasattr(value, "mask") and bool(getattr(value, "mask", False)):
        return None
    if hasattr(value, "unit") and hasattr(value, "value"):  # astropy Quantity
        value = value.value
    if kind == "str":
        s = str(value).strip()
        return s or None
    try:
        x = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(x):  # an infinite phase or time would become a NaN angle, and stop every run at once
        return None
    return int(x) if kind == "int" else x


def rows_from_table(table: Any) -> list[Row]:
    """Rows from an astropy table returned by astroquery (or any table with named columns)."""
    names = set(table.colnames)
    missing = [c for c in COLUMN_NAMES if c not in names]
    if missing:
        raise ArchiveError(f"archive response lacks columns {missing}")
    return [{c: _clean(r[c], _TYPES[c]) for c in COLUMN_NAMES} for r in table]


def _timeouts_on(session: Any) -> None:
    """Give every request of a ``requests`` session a timeout, for those that set none (pyvo's)."""
    from requests.adapters import HTTPAdapter

    class TimeoutAdapter(HTTPAdapter):
        def send(self, request: Any, **kwargs: Any) -> Any:  # type: ignore[override]
            if kwargs.get("timeout") is None:
                kwargs["timeout"] = (CONNECT_TIMEOUT_S, READ_TIMEOUT_S)
            return super().send(request, **kwargs)

    for prefix in ("https://", "http://"):
        session.mount(prefix, TimeoutAdapter())


def fetch_rows(where: str = MULTI_PLANET_WHERE, *, attempts: int = 3, pause: float = 2.0) -> list[Row]:
    """Query ``pscomppars`` for all planets matching ``where`` (retrying transient network errors).

    A result the service reports as cut (QUERY_STATUS=OVERFLOW, which pyvo only warns about) is an error: it would
    otherwise replace a good cache and silently drop planets.
    """
    from astroquery.ipac.nexsci.nasa_exoplanet_archive import NasaExoplanetArchive
    from pyvo.dal.exceptions import DALOverflowWarning  # type: ignore[import-untyped]

    _timeouts_on(NasaExoplanetArchive._session)
    last: Exception | None = None
    for i in range(attempts):
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("error", DALOverflowWarning)
                table = NasaExoplanetArchive.query_criteria(
                    table=TABLE, select=",".join(COLUMN_NAMES), where=where, cache=False
                )
            return rows_from_table(table)
        except Exception as exc:  # network errors surface as many different exception types
            last = exc
            if i + 1 < attempts:
                time.sleep(pause * (i + 1))
    raise ArchiveError(f"could not query the NASA Exoplanet Archive: {type(last).__name__}: {last}") from last


def write_csv(rows: Iterable[Row], path: Path) -> None:
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=COLUMN_NAMES)
        w.writeheader()
        for r in rows:
            w.writerow({c: ("" if r.get(c) is None else r[c]) for c in COLUMN_NAMES})


def read_csv(source: Path | str) -> list[Row]:
    """Read rows written by :func:`write_csv` (or a TAP ``format=csv`` response with these columns)."""
    text = source.read_text(encoding="utf-8") if isinstance(source, Path) else source
    reader = csv.DictReader(io.StringIO(text))
    fields = set(reader.fieldnames or [])
    missing = [c for c in COLUMN_NAMES if c not in fields]
    if missing:
        raise ArchiveError(f"table file lacks columns {missing}")
    rows = []
    for r in reader:
        if any(
            r[c] is None for c in COLUMN_NAMES
        ):  # csv gives None, not "", for a field the line does not reach
            raise ArchiveError(f"table file has a cut row, at line {reader.line_num}")
        rows.append({c: _clean(r[c] if r[c] != "" else None, _TYPES[c]) for c in COLUMN_NAMES})
    return rows


def group_by_host(rows: Sequence[Row]) -> dict[str, list[Row]]:
    hosts: dict[str, list[Row]] = {}
    for r in rows:
        hosts.setdefault(str(r["hostname"]), []).append(r)
    return hosts
