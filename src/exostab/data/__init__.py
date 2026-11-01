"""Getting systems into exostab: the NASA Exoplanet Archive, the disk cache, the offline snapshot and
user files."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from ..models import DataSource, MassKind, System
from .archive import TABLE, TAP_SERVICE, Row, group_by_host
from .completion import (
    IncompleteSystemError,
    complete_planets,
    complete_star,
    coplanar_flag,
    eccentricity_is_assumed,
    mass_kind,
    missing_rows_flag,
    phase_spread_flags,
    star_mass_row,
)
from .files import SystemFileError, load_system_file
from .names import SNAPSHOT_LIST_HINT, AmbiguousNameError, SystemNotFoundError, resolve_host
from .store import TableInfo, load_rows

__all__ = [
    "AmbiguousNameError",
    "IncompleteSystemError",
    "SystemFileError",
    "SystemNotFoundError",
    "SystemSummary",
    "TableInfo",
    "find_host",
    "list_systems",
    "load_rows",
    "load_system",
    "load_system_file",
    "system_from_rows",
]


def system_from_rows(rows: Sequence[Row], info: TableInfo) -> System:
    """Build a :class:`System` from the archive rows of one host, applying the completion rules."""
    host = str(rows[0]["hostname"])
    if len(rows) < 2:
        raise IncompleteSystemError(
            f"The archive lists only one planet around {host} (sy_pnum counts planets around every star of "
            "the system); a stability check needs at least two."
        )
    star, flags = complete_star(rows)
    planets, pflags = complete_planets(rows, star.mass_msun.require())
    source = DataSource(
        kind=info.kind,
        table=TABLE,
        service=TAP_SERVICE,
        retrieved_utc=info.retrieved_utc,
        path=info.path,
        note=info.note,
    )
    missing = missing_rows_flag(rows)
    system = System(
        name=host,
        star=star,
        planets=tuple(planets),
        source=source,
        flags=(*flags, *pflags, coplanar_flag(), *([missing] if missing else [])),
    )
    return system.model_copy(update={"flags": (*system.flags, *phase_spread_flags(system))})


def find_host(name: str, hosts: Mapping[str, Sequence[Row]], info: TableInfo) -> str:
    """:func:`~exostab.data.names.resolve_host`, saying which table was searched when the name is not found.

    When the rows come from the bundled snapshot (offline, or the archive was unreachable), a real archive
    system must not be reported as missing from the archive: the error then says that only the offline
    snapshot was searched, and why. An ambiguous name is passed on unchanged.
    """
    try:
        return resolve_host(name, hosts)
    except SystemNotFoundError as exc:
        if info.kind != "snapshot" or isinstance(exc, AmbiguousNameError):
            raise
        why = "" if info.note is None or info.note.startswith("offline snapshot") else f" ({info.note})"
        where = f"the offline snapshot{why}, not the full archive table"
        raise SystemNotFoundError(
            exc.query, exc.suggestions, where=where, list_hint=SNAPSHOT_LIST_HINT
        ) from exc


def load_system(name: str, *, refresh: bool = False, offline: bool = False) -> System:
    """Look up a multi-planet system in the archive table by host or planet name."""
    rows, info = load_rows(refresh=refresh, offline=offline)
    hosts = group_by_host(rows)
    return system_from_rows(hosts[find_host(name, hosts, info)], info)


@dataclass(frozen=True)
class SystemSummary:
    host: str
    n_planets: int
    min_period_days: float | None
    max_period_days: float | None
    star_mass_msun: float | None
    minimum_masses: int  # planets with only m sin i
    estimated_masses: int  # planets whose mass comes from a mass-radius relation
    missing_eccentricities: int
    discovery_methods: str


def list_systems(
    rows: Sequence[Row], *, min_planets: int = 2, max_period_days: float | None = None
) -> list[SystemSummary]:
    """Multi-planet systems in ``rows`` with at least ``min_planets`` planets and all periods below a limit."""
    out = []
    for host, rs in group_by_host(rows).items():
        if len(rs) < max(2, min_planets):
            continue
        periods = [r["pl_orbper"] for r in rs if r.get("pl_orbper") is not None]
        pmax = max(periods) if periods else None
        if max_period_days is not None and (pmax is None or len(periods) < len(rs) or pmax > max_period_days):
            continue
        star_row = star_mass_row(rs)  # the same choice as in the analysis
        out.append(
            SystemSummary(
                host=host,
                n_planets=len(rs),
                min_period_days=min(periods) if periods else None,
                max_period_days=pmax,
                star_mass_msun=None if star_row is None else star_row["st_mass"],
                minimum_masses=sum(
                    r.get("pl_bmasse") is not None and mass_kind(r) is MassKind.MINIMUM for r in rs
                ),
                estimated_masses=sum(
                    r.get("pl_bmassprov") == "M-R relationship" or r.get("pl_bmasse") is None for r in rs
                ),
                missing_eccentricities=sum(eccentricity_is_assumed(r) for r in rs),
                discovery_methods=", ".join(
                    sorted({str(r.get("discoverymethod")) for r in rs if r.get("discoverymethod")})
                ),
            )
        )
    out.sort(key=lambda s: (-s.n_planets, s.host.lower()))
    return out
