"""Compute the numbers of docs/findings.md and draw its figures.

    python scripts/catalog_findings.py catalog.csv --out docs/assets/findings

The verdicts and draw counts come from the catalog CSV. The CSV names the completion rules of each system but
not the planets they apply to, so what each verdict rests on is recomputed with exostab's own code from the
archive table: the cached copy, or a download if there is none (--refresh downloads it again). The first lines
printed say how many catalog rows that table reproduces, because a later table can differ from the one the
catalog used.

The catalog does not store encounter times, so the runs of the overall unstable systems are repeated here with
the catalog's code and settings. The what-if runs do the same with named values replaced: masses and
eccentricities of one publication in the archive's Planetary Systems table (`ps`), or larger minimum masses.
What-if runs are not catalog results.

Three options add numbers that are printed only if they are given: --earlier compares other weekly catalogs of
the branch catalog-data, --rebuilds compares catalogs rebuilt with `exostab catalog build`, and
--eccentricity-what-if repeats every system with other eccentricities, which takes longer than a catalog
build.
"""

from __future__ import annotations

import argparse
import copy
import csv
import io
import math
import os
import platform
import statistics
import time
import urllib.parse
import urllib.request
from collections import Counter
from collections.abc import Iterable, Sequence
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import Any, NamedTuple, cast

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import rebound

from exostab import __version__
from exostab.analysis import CheckResult, CheckSettings, check_system, upper_limit_inputs
from exostab.data import IncompleteSystemError, load_rows, system_from_rows
from exostab.data.archive import TAP_SERVICE, Row, group_by_host
from exostab.data.completion import parse_reflink
from exostab.data.store import TableInfo
from exostab.indicators import amd as amd_indicator
from exostab.indicators import hill as hill_indicator
from exostab.models import MassKind, PhaseKind, Provenance
from exostab.plots import _RC, INK, MUTED, PLANET_COLORS, STATUS
from exostab.sampling import Realization, realizations

CatalogRow = dict[str, str]

VERDICTS = ["stable", "marginal", "unstable", "inconclusive"]
# The colours of the run classes in exostab's own plots, with the same meaning.
VERDICT_COLORS = dict(zip(VERDICTS, (STATUS[k][0] for k in STATUS), strict=True))
NEUTRAL = "#b5b4ad"
INDICATORS = {
    "hill": ("Hill", "o", PLANET_COLORS[0]),
    "amd": ("AMD", "s", PLANET_COLORS[1]),
    "nbody": ("N-body", "^", PLANET_COLORS[2]),
}
# What a stable verdict rests on, from the least to the most published inputs.
RESTS_ON = {
    "assumed_estimated": "Every e assumed 0, every mass estimated from the radius",
    "assumed": "Every e assumed 0, some masses not estimated from the radius",
    "partly": "Some e not assumed, other inputs assumed, minimum masses or limits",
    "published": "Published values for every e, true mass and phase",
}
DRAWS = "draws regular/chaotic/encounter/inconclusive"
# The hosts of the what-if runs, and the publication in the `ps` table that gives their values.
MINIMUM_MASSES = ("HD 215152", "Delisle")
ECCENTRICITY_LIMITS = ("Kepler-36", "Carter")
# The inclinations of the what-if runs of the unstable systems: every m sin i is divided by sin i.
INCLINATIONS_DEG = (60, 30)
# The seeds of the what-if run at the eccentricity limits, whose omega is drawn at random.
SEEDS = (0, 1, 2)
TRANSIT, RADIAL_VELOCITY = "Transit", "Radial Velocity"
PLANET_COUNT_FIGURE = "verdicts-by-planet-count.png"
INPUTS_FIGURE = "what-stable-rests-on.png"


class Inputs(NamedTuple):
    """What the verdicts of one system rest on, recomputed from the archive table."""

    n_planets: int
    n_e_assumed: int
    n_e_published: int
    n_estimated_mass: int
    n_minimum_mass: int
    n_random_phase: int
    n_mass_limits: int
    any_upper_limit: bool
    all_omega_published: bool
    n_stars: int
    methods: frozenset[str]
    beta_max: float
    outer_orbits: float
    pairs: list[dict[str, Any]]
    planets: list[str]

    @property
    def every_e_assumed(self) -> bool:
        return self.n_e_assumed == self.n_planets

    @property
    def every_mass_estimated(self) -> bool:
        return self.n_estimated_mass == self.n_planets

    @property
    def published(self) -> bool:
        """Every e, true mass and phase from publications, and no value that is only an upper limit."""
        kept = self.n_e_assumed + self.n_estimated_mass + self.n_minimum_mass + self.n_random_phase
        return kept == 0 and not self.any_upper_limit


def rests_on(inputs: Inputs) -> str:
    """The key in RESTS_ON for this system."""
    if inputs.every_e_assumed:
        return "assumed_estimated" if inputs.every_mass_estimated else "assumed"
    return "published" if inputs.published else "partly"


def share(count: int, total: int) -> str:
    return f"{count:,} of {total:,} ({100 * count / total:.1f}%)" if total else f"{count} of 0"


def stable_count(rows: Iterable[CatalogRow], key: str = "overall") -> int:
    return sum(r[key] == "stable" for r in rows)


def read_catalog(path: Path) -> list[CatalogRow]:
    with path.open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def label(row: CatalogRow) -> str:
    """The verdict, or the status (skipped, timeout) of a row without one."""
    return row["overall"] or row["status"]


def verdict_counts(rows: Iterable[CatalogRow]) -> str:
    counts = Counter(r["overall"] for r in rows)
    return ", ".join(f"{v} {counts[v]}" for v in VERDICTS)


def draws_of(row: CatalogRow) -> str:
    return "/".join(row[f"nbody_{k}"] for k in ("regular", "chaotic", "unstable", "inconclusive"))


def verdicts_of(row: CatalogRow) -> str:
    return (
        f"overall {label(row)}, Hill {row['hill']}, AMD {row['amd']}, N-body {row['nbody']}, "
        f"{DRAWS} {draws_of(row)}"
    )


def recompute(row: CatalogRow, host_rows: list[Row], info: TableInfo) -> tuple[Inputs | None, bool]:
    """(what the verdicts rest on, whether this table reproduces the catalog row)."""
    try:
        system = system_from_rows(host_rows, info)
    except (IncompleteSystemError, ValueError) as exc:
        return None, row["status"] == "skipped" and row["reason"] == str(exc)
    if row["status"] != "ok":
        return None, False
    reals = realizations(system, int(row["draws"]), int(row["seed"]))
    nominal, draws = reals[0], reals[1:]
    hill = hill_indicator.evaluate(nominal, draws)
    assumed = [p.name for p in system.planets if p.eccentricity.provenance is Provenance.ASSUMED]
    amd = amd_indicator.evaluate(nominal, draws, assumed_eccentricities=assumed)
    separation = min(p["separation_hill"] for p in hill.details["pairs"])
    beta = max(p["beta"] for p in amd.details["pairs"])
    periods = [b.P for b in nominal.bodies]
    planets = system.planets
    inputs = Inputs(
        n_planets=len(planets),
        n_e_assumed=len(assumed),
        n_e_published=sum(p.eccentricity.provenance is Provenance.MEASURED for p in planets),
        n_estimated_mass=sum(p.mass_kind is MassKind.ESTIMATED for p in planets),
        n_minimum_mass=sum(p.mass_kind is MassKind.MINIMUM for p in planets),
        n_random_phase=sum(p.phase.kind is PhaseKind.RANDOM for p in planets),
        n_mass_limits=sum(p.mass_earth.provenance is Provenance.UPPER_LIMIT for p in planets),
        any_upper_limit=bool(upper_limit_inputs(system)),
        all_omega_published=all(p.omega_deg.provenance is not Provenance.RANDOMIZED for p in planets),
        n_stars=system.star.n_stars,
        methods=frozenset(str(r.get("discoverymethod")) for r in host_rows),
        beta_max=beta,
        outer_orbits=float(row["orbits"]) * periods[0] / periods[-1],
        pairs=[
            {**pair, "period_ratio": periods[k + 1] / periods[k]}
            for k, pair in enumerate(hill.details["pairs"])
        ],
        planets=[
            f"{p.name}: P {p.period_days.value:.5g} d ({p.period_days.reference}), "
            f"{p.mass_earth.value:.5g} M_E, {p.mass_kind.value} ({p.mass_earth.reference}), "
            f"e {p.eccentricity.value:.3g} ({p.eccentricity.reference})"
            for p in planets
        ],
    )
    same = (
        hill.verdict.value == row["hill"]
        and amd.verdict.value == row["amd"]
        and math.isclose(separation, float(row["hill_min_separation"]), rel_tol=1e-9)
        and math.isclose(beta, float(row["amd_beta_max"]), rel_tol=1e-9)
        and ";".join(sorted({f.rule for f in system.flags})) == row["completion_rules"]
        and len(system.flags) == int(row["n_flags"])
    )
    return inputs, same


def planet_groups(checked: list[CatalogRow]) -> list[tuple[str, list[CatalogRow]]]:
    """Rows per planet count: 2, 3, 4, 5 and the rest together."""
    largest = max((int(r["n_planets"]) for r in checked), default=6)
    rest = f"6 to {largest} planets" if largest > 6 else "6 planets"
    bounds = [(n, n, f"{n} planets") for n in (2, 3, 4, 5)] + [(6, largest, rest)]
    groups = [(name, [r for r in checked if lo <= int(r["n_planets"]) <= hi]) for lo, hi, name in bounds]
    return [(name, rows) for name, rows in groups if rows]


def size_groups(checked: list[CatalogRow]) -> dict[str, list[CatalogRow]]:
    """Rows of systems with 2, 3 and at least 4 planets."""
    return {
        "2": [r for r in checked if int(r["n_planets"]) == 2],
        "3": [r for r in checked if int(r["n_planets"]) == 3],
        "4+": [r for r in checked if int(r["n_planets"]) >= 4],
    }


def stable_share(rows: list[CatalogRow], key: str = "overall") -> float:
    return 100 * stable_count(rows, key) / len(rows) if rows else float("nan")


def print_catalog(
    catalog: list[CatalogRow], hosts: dict[str, list[Row]], same: dict[str, bool], info: TableInfo
) -> None:
    checked = [r for r in catalog if r["status"] == "ok"]
    skipped = [r for r in catalog if r["status"] == "skipped"]
    versions = ", ".join(sorted({r["rebound_version"] for r in checked}))
    head = catalog[0]
    print(
        f"Catalog: exostab {head['exostab_version']}, REBOUND {versions}, archive data of "
        f"{head['data_retrieved_utc'][:10]}; {float(head['orbits']):,.0f} orbits of the innermost planet, "
        f"{head['draws']} draws, seed {head['seed']}."
    )
    print(
        f"This run: exostab {__version__}, REBOUND {rebound.__version__}, NumPy {np.__version__}, "
        f"Python {platform.python_version()}, {platform.platform()}."
    )
    print(f"Archive table: {info.kind}, downloaded {(info.retrieved_utc or '?')[:10]}. {info.note or ''}")
    n_checked = sum(same.get(r["system"], False) for r in checked)
    n_skipped = sum(same.get(r["system"], False) for r in skipped)
    print(
        f"This table reproduces {n_checked:,} of {len(checked):,} checked systems (Hill and AMD verdicts and "
        f"numbers, completion rules) and {n_skipped:,} of {len(skipped):,} skipped systems (the same reason)."
    )
    names = {r["system"] for r in catalog}
    print(
        f"Hosts not in this table: {len(names - set(hosts))}; not in the catalog: {len(set(hosts) - names)}."
    )
    different = [r["system"] for r in catalog if not same.get(r["system"], False)]
    if different:
        print(f"  Not reproduced: {', '.join(different)}")
        print("  The numbers about inputs below describe this table and can differ from the page.")

    print("\n== Verdicts")
    print(f"Systems {len(catalog):,}, checked {len(checked):,}, skipped {len(skipped):,}.")
    counts = Counter(r["overall"] for r in checked)
    for v in VERDICTS:
        print(f"  {v}: {share(counts[v], len(checked))}")


def print_planets(checked: list[CatalogRow], details: dict[str, Inputs]) -> None:
    print("\n== More planets, fewer stable verdicts")
    for name, rows in planet_groups(checked):
        print(f"  {name}: n {len(rows)}, {verdict_counts(rows)}, stable share {stable_share(rows):.1f}%")
    groups = size_groups(checked)
    print("Share called stable by each indicator, for 2, 3 and 4+ planets:")
    for key, (name, _, _) in INDICATORS.items():
        print(f"  {name}: " + ", ".join(f"{stable_share(rows, key):.1f}%" for rows in groups.values()))
    print("Every pair passes the two-planet criterion (nominal values, no draws):")
    for g, rows in groups.items():
        kept = [
            r
            for r in rows
            if r["system"] in details
            and all(p["gladman_margin"] > 0 and not p["orbits_cross"] for p in details[r["system"]].pairs)
        ]
        print(f"  {g} planets: {share(len(kept), len(rows))}")
    hill_stable = {r["system"] for r in groups["3"] if r["hill"] == "stable"}
    overall_stable = {r["system"] for r in groups["3"] if r["overall"] == "stable"}
    print(
        f"3-planet systems: Hill stable {len(hill_stable)}, overall stable {len(overall_stable)}, "
        f"both {len(hill_stable & overall_stable)}."
    )
    for r in checked:
        d = details.get(r["system"])
        if d and d.n_planets >= 5 and r["overall"] == "stable":
            print(
                f"Stable with 5 or more planets: {r['system']}, every e assumed: {d.every_e_assumed}, "
                f"every mass estimated: {d.every_mass_estimated}."
            )


def eccentricity_groups(
    known: list[CatalogRow], details: dict[str, Inputs]
) -> tuple[list[CatalogRow], list[CatalogRow]]:
    """(rows with every eccentricity assumed, rows with at least one published value or limit)."""
    assumed = [r for r in known if details[r["system"]].every_e_assumed]
    others = [r for r in known if not details[r["system"]].every_e_assumed]
    return assumed, others


def print_inputs(known: list[CatalogRow], details: dict[str, Inputs]) -> None:
    print("\n== What the stable verdicts rest on")
    stable = [r for r in known if r["overall"] == "stable"]
    print(f"Stable: {len(stable):,} of {len(known):,} checked.")
    ladder = Counter(rests_on(details[r["system"]]) for r in stable)
    for key, text in RESTS_ON.items():
        print(f"  {text}: {share(ladder[key], len(stable))}")
    print(f"Every e assumed 0: {share(ladder['assumed_estimated'] + ladder['assumed'], len(stable))}.")
    only_limits = [
        r
        for r in stable
        if rests_on(details[r["system"]]) == "partly" and not details[r["system"]].n_e_published
    ]
    print(f"  of the {ladder['partly']} with some e not assumed, upper limits only: {len(only_limits)}")
    published = [r for r in known if details[r["system"]].published]
    print(f"Published inputs: {share(len(published), len(known))}; {verdict_counts(published)}.")
    strict = [r for r in published if (d := details[r["system"]]).all_omega_published and d.n_stars == 1]
    print(f"  also every omega published and a single star: {len(strict)}, stable {stable_count(strict)}.")
    print(f"  stable: {', '.join(sorted(r['system'] for r in published if r['overall'] == 'stable'))}")
    assumed, others = eccentricity_groups(known, details)
    for name, group in (("every e assumed", assumed), ("some e not assumed", others)):
        transit = sum(details[r["system"]].methods == {TRANSIT} for r in group)
        velocity = sum(details[r["system"]].methods == {RADIAL_VELOCITY} for r in group)
        estimated = sum(details[r["system"]].every_mass_estimated for r in group)
        print(
            f"{name}: {len(group)}; {verdict_counts(group)}; stable {share(stable_count(group), len(group))}"
        )
        print(
            f"  every planet found by transit {share(transit, len(group))}, by radial velocity "
            f"{share(velocity, len(group))}; every mass estimated {share(estimated, len(group))}"
        )
    with_value = [r for r in others if details[r["system"]].n_e_published]
    print(
        f"Some e not assumed, not only upper limits: {len(with_value)}; "
        f"stable {share(stable_count(with_value), len(with_value))} "
        f"(left out, with nothing but upper limits: {len(others) - len(with_value)})"
    )
    zero = sum(details[r["system"]].beta_max == 0 for r in assumed)
    print(
        f"Every e assumed: beta = 0 in {zero} of {len(assumed)}; AMD stable in {stable_count(assumed, 'amd')}."
    )
    print("Stable share by planet count, every e assumed and some e not assumed:")
    for g, rows in size_groups(known).items():
        a = [r for r in rows if details[r["system"]].every_e_assumed]
        b = [r for r in rows if not details[r["system"]].every_e_assumed]
        print(f"  {g} planets: {share(stable_count(a), len(a))}; {share(stable_count(b), len(b))}")
    print("Stable share within one kind of system, every e assumed and some e not assumed:")
    for name, kind in (
        ("every planet found by transit", lambda d: d.methods == {TRANSIT}),
        (
            "every planet found by transit, no mass estimated",
            lambda d: d.methods == {TRANSIT} and d.n_estimated_mass == 0,
        ),
        ("every planet found by radial velocity", lambda d: d.methods == {RADIAL_VELOCITY}),
    ):
        a = [r for r in assumed if kind(details[r["system"]])]
        b = [r for r in others if kind(details[r["system"]])]
        print(f"  {name}: {share(stable_count(a), len(a))}; {share(stable_count(b), len(b))}")


def check(row: CatalogRow, host_rows: list[Row], info: TableInfo, seed: int | None = None) -> CheckResult:
    """The check behind a catalog row (exostab.catalog.build.check_one), with the row's seed unless given."""
    settings = CheckSettings(
        orbits=float(row["orbits"]),
        draws=int(row["draws"]),
        seed=int(row["seed"]) if seed is None else seed,
        jobs=1,
        n_samples=0,
    )
    return check_system(system_from_rows(host_rows, info), settings)


def rerun_text(result: CheckResult) -> str:
    report = result.report
    ind = report.indicators
    nominal = ind["nbody"].details["nominal"]
    counts = ind["nbody"].details["classification_counts"]
    draws = "/".join(str(counts[k]) for k in ("regular", "chaotic", "unstable", "inconclusive"))
    return (
        f"overall {report.overall.verdict.value}, Hill {ind['hill'].verdict.value}, AMD {ind['amd'].verdict.value}, "
        f"N-body {ind['nbody'].verdict.value}, nominal {nominal['status']} after {nominal['t_end_yr']:.3g} yr "
        f"({nominal['classification']}), {DRAWS} {draws}"
    )


def radial_gap(real: Realization, k: int) -> tuple[float, float]:
    """Smallest and largest r_k - r_(k+1) in AU, at equal longitudes in the plane of the orbits.

    The ellipses of planets k and k + 1 meet only if this changes sign. The Hill indicator's `orbits_cross` is
    weaker: it compares the apastron of the inner orbit with the periastron of the outer one, whatever the
    directions of the two.
    """
    a = real.semi_major_axes()
    longitude = np.linspace(0, 2 * np.pi, 7200, endpoint=False)

    def radius(j: int) -> Any:
        body = real.bodies[j]
        return a[j] * (1 - body.e**2) / (1 + body.e * np.cos(longitude - body.pomega))

    gap = radius(k) - radius(k + 1)
    return float(gap.min()), float(gap.max())


def print_unstable(
    checked: list[CatalogRow], details: dict[str, Inputs], hosts: dict[str, list[Row]], info: TableInfo
) -> None:
    print("\n== Published parameter sets that do not survive integration")
    rows = [r for r in checked if r["overall"] == "unstable" and r["system"] in details]
    print(f"Overall unstable: {len(rows)}.")
    rows = sorted(rows, key=lambda r: float(r["hill_min_separation"]))
    overlap = meet = 0
    for r in rows:
        d = details[r["system"]]
        result = check(r, hosts[r["system"]], info)
        nbody = result.report.indicators["nbody"].details
        nominal, ias15 = nbody["nominal"], nbody["ias15"]
        print(
            f"{r['system']}: {r['n_planets']} planets, {DRAWS} {draws_of(r)}, smallest spacing "
            f"{float(r['hill_min_separation']):.2f} mutual Hill radii, rules {r['completion_rules']}"
        )
        print(f"  local rerun: {rerun_text(result)}")
        print(
            f"  nominal run: WHFast {nominal['status']} after {nominal['t_end_yr']:.3g} yr, IAS15 "
            f"{ias15['status']} after {ias15['t_end_yr']:.3g} yr"
        )
        gaps = [radial_gap(result.realizations[0], k) for k in range(len(d.pairs))]
        omega = "the published omega" if d.all_omega_published else "omega drawn at random"
        for p, (low, high) in zip(d.pairs, gaps, strict=True):
            print(
                f"  {p['pair']}: period ratio {p['period_ratio']:.3f}, radial ranges overlap: "
                f"{p['orbits_cross']}, ellipses meet with {omega}: {low <= 0 <= high} "
                f"(r1 - r2 from {low:+.3f} to {high:+.3f} AU)"
            )
        overlap += any(p["orbits_cross"] for p in d.pairs)
        meet += any(low <= 0 <= high for low, high in gaps)
        for line in d.planets:
            print(f"  {line}")
    print(f"Nominal radial ranges overlap in {overlap} of {len(rows)}; nominal ellipses meet in {meet}.")
    for degrees in INCLINATIONS_DEG:
        factor = 1 / math.sin(math.radians(degrees))
        print(f"What-if with every m sin i divided by sin {degrees} deg, not a catalog result:")
        for r in rows:
            result = check(r, with_larger_minimum_masses(hosts[r["system"]], factor), info)
            spacing = min(p["separation_hill"] for p in result.report.indicators["hill"].details["pairs"])
            print(f"  {r['system']}: smallest spacing {spacing:.2f}; {rerun_text(result)}")


def query_ps(hosts: Sequence[str]) -> list[dict[str, str]]:
    """Rows of the archive's Planetary Systems table for these hosts, one per planet and publication."""
    names = ",".join(f"'{h}'" for h in hosts)
    query = (
        "select pl_name,pl_refname,pl_msinie,pl_msinieerr1,pl_msinieerr2,pl_orbeccen,pl_orbeccenlim "
        f"from ps where hostname in ({names})"
    )
    url = f"{TAP_SERVICE}/sync?" + urllib.parse.urlencode({"query": query, "format": "csv"})
    for attempt in range(3):  # transient network errors, as in exostab.data.archive.fetch_rows
        try:
            with urllib.request.urlopen(url, timeout=120) as response:
                return list(csv.DictReader(io.StringIO(response.read().decode("utf-8"))))
        except OSError:
            if attempt == 2:
                raise
            time.sleep(5 * (attempt + 1))
    return []


def ps_row(ps: list[dict[str, str]], planet: str, author: str) -> dict[str, str]:
    """The row of one planet from one publication."""
    for r in ps:
        if r["pl_name"] == planet and author in r["pl_refname"]:
            return r
    raise SystemExit(f"The ps table has no row for {planet} from {author}.")


def with_minimum_masses(host_rows: list[Row], ps: list[dict[str, str]], author: str) -> list[Row]:
    """A copy of the rows with each planet's mass replaced by its m sin i from one publication."""
    rows = copy.deepcopy(host_rows)
    for r in rows:
        p = ps_row(ps, r["pl_name"], author)
        r.update(
            pl_bmasse=float(p["pl_msinie"]),
            pl_bmasseerr1=float(p["pl_msinieerr1"]),
            pl_bmasseerr2=float(p["pl_msinieerr2"]),
            pl_bmasselim=0,
            pl_bmassprov="Msini",
            pl_bmasse_reflink=p["pl_refname"],
        )
    return rows


def with_eccentricity_limits(host_rows: list[Row], ps: list[dict[str, str]], author: str) -> list[Row]:
    """A copy of the rows with each planet's eccentricity replaced by its upper limit from one publication."""
    rows = copy.deepcopy(host_rows)
    for r in rows:
        p = ps_row(ps, r["pl_name"], author)
        r.update(
            pl_orbeccen=float(p["pl_orbeccen"]),
            pl_orbeccenerr1=None,
            pl_orbeccenerr2=None,
            pl_orbeccenlim=int(p["pl_orbeccenlim"]),
            pl_orbeccen_reflink=p["pl_refname"],
        )
    return rows


def with_larger_minimum_masses(host_rows: list[Row], factor: float) -> list[Row]:
    """A copy of the rows with each m sin i and its uncertainties multiplied by the factor."""
    rows = copy.deepcopy(host_rows)
    for r in rows:
        if r.get("pl_bmassprov") == "Msini":
            for key in ("pl_bmasse", "pl_bmasseerr1", "pl_bmasseerr2"):
                if r.get(key) is not None:
                    r[key] *= factor
    return rows


def with_eccentricity(host_rows: list[Row], e: float | None) -> list[Row]:
    """A copy of the rows with every eccentricity replaced by a value without uncertainty, or by none at all."""
    rows = copy.deepcopy(host_rows)
    for r in rows:
        r.update(
            pl_orbeccen=e,
            pl_orbeccenerr1=None,
            pl_orbeccenerr2=None,
            pl_orbeccenlim=None if e is None else 0,
        )
    return rows


def references(cells: Iterable[str | None]) -> str:
    return ", ".join(sorted({(parse_reflink(c)[0] or "no reference").strip() for c in cells}))


def print_limits(
    by_name: dict[str, CatalogRow],
    known: list[CatalogRow],
    details: dict[str, Inputs],
    rows: list[Row],
    info: TableInfo,
    ps: list[dict[str, str]] | None,
) -> None:
    print("\n== Where stability runs point to the table")
    limited = [r for r in known if details[r["system"]].n_mass_limits]
    print(
        f"Checked systems with a mass upper limit: {len(limited)} of {len(known):,}; {verdict_counts(limited)}."
    )
    kiefer = [
        r for r in rows if r.get("pl_bmasselim") == 1 and "Kiefer" in (r.get("pl_bmasse_reflink") or "")
    ]
    print(
        f"Upper limits from Kiefer et al. 2021: {len(kiefer)} planets, {len({r['hostname'] for r in kiefer})} hosts."
    )
    host, author = MINIMUM_MASSES
    table = [r for r in rows if r["hostname"] == host]
    if host not in details:
        return
    periods = sorted(float(r["pl_orbper"]) for r in table)
    masses = sorted(float(r["pl_bmasse"]) for r in table)
    print(
        f"{host}: periods {periods[0]:.3g} to {periods[-1]:.3g} d; composite masses {masses[0]:.0f} to "
        f"{masses[-1]:.0f} M_E, upper limits in {sum(r.get('pl_bmasselim') == 1 for r in table)} of {len(table)} "
        f"rows, from {references(r.get('pl_bmasse_reflink') for r in table)}."
    )
    row = by_name[host]
    print(
        f"  catalog: {verdicts_of(row)}; smallest spacing {float(row['hill_min_separation']):.2f} mutual Hill radii"
    )
    if ps is not None:
        swapped = with_minimum_masses(table, ps, author)
        low = sorted(float(r["pl_bmasse"]) for r in swapped)
        print(
            f"  ps table: m sin i {low[0]:.2f} to {low[-1]:.2f} M_E, from "
            f"{references(r['pl_bmasse_reflink'] for r in swapped)}"
        )
        print(f"  what-if with these m sin i, not a catalog result: {rerun_text(check(row, swapped, info))}")


def print_firmness(
    catalog: list[CatalogRow], earlier: Sequence[Path], rebuilds: Sequence[Path], details: dict[str, Inputs]
) -> None:
    print("\n== How firm these numbers are")
    by_name = {r["system"]: r for r in catalog}
    for path in earlier:
        other = read_catalog(path)
        common = [r for r in other if r["system"] in by_name]
        changed = sum(label(r) != label(by_name[r["system"]]) for r in common)
        columns = Counter(k for r in common for k, v in r.items() if v != by_name[r["system"]][k])
        listed = ", ".join(f"{k} ({n:,} rows)" for k, n in columns.items()) or "none"
        print(
            f"{path.name} (exostab {other[0]['exostab_version']}): {len(common):,} common systems, {changed} "
            f"verdicts differ; columns that differ: {listed}."
        )
    if not rebuilds:
        print("No rebuilds given (--rebuilds): their numbers are not printed.")
        return
    checked = [r for r in catalog if r["status"] == "ok"]
    names = [r["system"] for r in checked]
    runs = [{r["system"]: r for r in read_catalog(p)} for p in rebuilds]
    tables = [{s: label(run[s]) if s in run else "missing" for s in names} for run in runs]
    seeds = [run[names[0]]["seed"] for run in runs]
    versions = ", ".join(sorted({run[names[0]]["rebound_version"] for run in runs}))
    print(f"Rebuilds: seeds {', '.join(seeds)}, REBOUND {versions}.")
    for v in VERDICTS:
        print(f"  {v}: " + ", ".join(str(sum(t[s] == v for s in names)) for t in tables))
    differ = {s for s in names if len({t[s] for t in tables}) > 1}
    print(f"Verdict differs among the rebuilds: {share(len(differ), len(names))}.")
    kinds = Counter(
        " / ".join(v for v in [*VERDICTS, "missing"] if any(t[s] == v for t in tables)) for s in differ
    )
    print("  " + ", ".join(f"{kind} {n}" for kind, n in kinds.most_common()))
    known = [s for s in names if s in details]
    for name, group in (
        ("every e assumed", [s for s in known if details[s].every_e_assumed]),
        ("some e not assumed", [s for s in known if not details[s].every_e_assumed]),
        ("any random phase", [s for s in known if details[s].n_random_phase]),
    ):
        print(f"  {name}: {share(len(differ.intersection(group)), len(group))}")
    print("Stable share per rebuild:")
    for g, rows in size_groups(checked).items():
        shares = [100 * sum(t[r["system"]] == "stable" for r in rows) / max(len(rows), 1) for t in tables]
        print(f"  {g} planets: " + ", ".join(f"{x:.1f}%" for x in shares))
    stable = [s for s in names if by_name[s]["overall"] == "stable"]
    kept = {s for s in stable if all(t[s] == "stable" for t in tables)}
    print(f"Published stable verdicts that are stable in every rebuild: {share(len(kept), len(stable))}.")
    published = [s for s in stable if s in details and details[s].published]
    print(f"  of those with published inputs: {share(len(kept.intersection(published)), len(published))}")
    for s in names:
        if by_name[s]["overall"] == "unstable":
            print(f"  published unstable, {s}: " + ", ".join(t[s] for t in tables))
    for t, seed in zip(tables, seeds, strict=True):
        if seed == by_name[names[0]]["seed"]:
            changed_names = [s for s in names if t[s] != by_name[s]["overall"]]
            print(
                f"Published catalog against the rebuild with seed {seed}: "
                f"{share(len(changed_names), len(names))} differ. {', '.join(changed_names)}"
            )


def print_meaning(
    checked: list[CatalogRow],
    details: dict[str, Inputs],
    by_name: dict[str, CatalogRow],
    rows: list[Row],
    info: TableInfo,
    ps: list[dict[str, str]] | None,
) -> None:
    print("\n== What 'stable' means here")
    years = [float(r["t_end_yr"]) for r in checked]
    low, high = np.percentile(years, [10, 90]) if years else (0.0, 0.0)
    print(
        f"Run length: median {statistics.median(years):,.0f} yr, 10 to 90% range {low:,.0f} to {high:,.0f} yr."
    )
    marginal = [r for r in checked if r["overall"] == "marginal" and r["system"] in details]
    nbody_stable = [r for r in marginal if r["nbody"] == "stable"]
    analytic = [r for r in nbody_stable if r["hill"] != "stable" or r["amd"] != "stable"]
    horizon = [
        r
        for r in marginal
        if r["nbody"] != "stable"
        and r["nbody_regular"] == r["draws"]
        and details[r["system"]].outer_orbits < 100
    ]
    print(
        f"Marginal: {len(marginal)}; N-body stable {len(nbody_stable)}, of which Hill or AMD not stable "
        f"{len(analytic)}; all draws regular but the outermost planet under 100 orbits {len(horizon)}."
    )
    for name in ("TRAPPIST-1", "KOI-351"):
        if name in by_name:
            print(f"{name}: {by_name[name]['n_planets']} planets, {verdicts_of(by_name[name])}")
    stable = [r for r in checked if r["overall"] == "stable"]
    if stable:
        closest = min(stable, key=lambda r: float(r["hill_min_separation"]))
        spacing = float(closest["hill_min_separation"])
        print(f"Smallest spacing among stable systems: {closest['system']}, {spacing:.2f} mutual Hill radii.")
    host, author = ECCENTRICITY_LIMITS
    if host not in details:
        return
    row = by_name[host]
    print(
        f"{host}: {verdicts_of(row)}, run length {float(row['t_end_yr']):,.0f} yr, rules {row['completion_rules']}"
    )
    print(f"  every e assumed: {details[host].every_e_assumed}")
    for line in details[host].planets:
        print(f"  {line}")
    if ps is not None:
        swapped = with_eccentricity_limits([r for r in rows if r["hostname"] == host], ps, author)
        limits = ", ".join(f"{r['pl_orbeccen']:g}" for r in sorted(swapped, key=lambda r: str(r["pl_name"])))
        print(
            f"  ps table: e upper limits {limits}, from {references(r['pl_orbeccen_reflink'] for r in swapped)}"
        )
        for seed in SEEDS:
            result = check(row, swapped, info, seed=seed)
            print(f"  what-if at these limits with seed {seed}, not a catalog result: {rerun_text(result)}")


def verdicts_with_eccentricity(task: tuple[CatalogRow, list[Row], TableInfo, float | None]) -> dict[str, str]:
    row, host_rows, info, e = task
    report = check(row, with_eccentricity(host_rows, e), info).report
    return {
        "system": row["system"],
        "overall": report.overall.verdict.value,
        **{key: report.indicators[key].verdict.value for key in INDICATORS},
    }


def print_eccentricity_what_if(
    known: list[CatalogRow],
    details: dict[str, Inputs],
    hosts: dict[str, list[Row]],
    info: TableInfo,
    jobs: int,
) -> None:
    print("\n== What-if with other eccentricities, not a catalog result (nothing else changed)")
    assumed, others = eccentricity_groups(known, details)
    gap = stable_share(assumed) - stable_share(others)
    for name, group, e in (
        ("some e not assumed, every e removed (so assumed 0)", others, None),
        ("every e assumed, every e 0.05", assumed, 0.05),
        ("every e assumed, every e 0.1", assumed, 0.1),
    ):
        tasks = [(r, hosts[r["system"]], info, e) for r in group]
        if jobs == 1:
            runs = [verdicts_with_eccentricity(task) for task in tasks]
        else:
            with ProcessPoolExecutor(max_workers=jobs) as pool:
                runs = list(pool.map(verdicts_with_eccentricity, tasks))
        pairs = list(zip(group, runs, strict=True))
        changes = Counter(f"{r['overall']} to {run['overall']}" for r, run in pairs)
        kept = sum(r["overall"] == run["overall"] == "stable" for r, run in pairs)
        many = sum(int(r["n_planets"]) >= 3 and run["overall"] == "stable" for r, run in pairs)
        print(f"{name}: {verdict_counts(runs)}; stable {share(stable_count(runs), len(runs))}")
        print(
            f"  catalog: {verdict_counts(group)}; stable in both {kept}; stable with 3 or more planets {many}"
        )
        print("  changes: " + ", ".join(f"{k} {n}" for k, n in changes.most_common()))
        for key, (title, _, _) in INDICATORS.items():
            print(f"  {title} stable: {stable_count(runs, key)}, in the catalog {stable_count(group, key)}")
        if e is None and gap:
            closed = 100 * (stable_share(runs) - stable_share(group)) / gap
            print(f"  this closes {closed:.0f}% of the gap between the stable shares of the two groups")


def figure_planets(checked: list[CatalogRow], out: Path) -> Path:
    groups = planet_groups(checked)
    sizes = size_groups(checked)
    with plt.rc_context(cast(Any, _RC)):
        fig, (ax, side) = plt.subplots(
            1, 2, figsize=(7.4, 3.1), width_ratios=[1.75, 1.0], layout="constrained"
        )
        ax.set_title("Overall verdict, share of checked systems", fontsize=9, loc="left", color=INK)
        for y, (_, rows) in enumerate(groups):
            counts = Counter(r["overall"] for r in rows)
            left = 0.0
            for v in VERDICTS:
                width = 100 * counts[v] / len(rows)
                ax.barh(
                    y, width, left=left, height=0.58, color=VERDICT_COLORS[v], ec="white", lw=1.0, zorder=3
                )
                left += width
            stable = 100 * counts["stable"] / len(rows)
            # the share inside the green bar if it fits, otherwise the count on the next segment
            if stable >= 9:
                ax.text(
                    stable / 2,
                    y,
                    f"{stable:.1f}%",
                    ha="center",
                    va="center",
                    fontsize=8,
                    color="white",
                    fontweight="bold",
                    zorder=4,
                )
            else:
                text = f"{counts['stable']} of {len(rows)} stable"
                ax.text(stable + 1.5, y, text, va="center", fontsize=8, color=INK, zorder=4)
            rare = ", ".join(f"{counts[v]} {v}" for v in VERDICTS[2:] if counts[v])
            ax.text(101.5, y - (0.13 if rare else 0), f"n = {len(rows)}", va="center", fontsize=8, color=INK)
            if rare:
                ax.text(101.5, y + 0.16, rare, va="center", fontsize=6.8, color=MUTED)
        ax.set_yticks(range(len(groups)), [name for name, _ in groups], color=INK)
        ax.set_ylim(len(groups) - 0.5, -0.5)
        ax.set_xlim(0, 100)
        ax.set_xticks([0, 25, 50, 75, 100], ["0", "25", "50", "75", "100%"])
        ax.grid(axis="y", visible=False)
        ax.tick_params(length=0)
        ax.spines["left"].set_visible(False)
        swatches = [plt.Rectangle((0, 0), 1, 1, color=VERDICT_COLORS[v]) for v in VERDICTS]
        fig.legend(
            swatches,
            VERDICTS,
            loc="outside lower left",
            ncol=4,
            fontsize=8,
            handlelength=1.0,
            handleheight=1.0,
            columnspacing=1.2,
        )

        side.set_title("Share called stable, by indicator", fontsize=9, loc="left", color=INK)
        xs = np.arange(len(sizes))
        for key, (name, marker, color) in INDICATORS.items():
            ys = [stable_share(rows, key) for rows in sizes.values()]
            side.plot(
                xs, ys, marker=marker, color=color, lw=1.5, ms=5.5, mec="white", mew=0.7, label=name, zorder=3
            )
            side.text(xs[0] - 0.12, ys[0], f"{ys[0]:.1f}", ha="right", va="center", fontsize=7.4, color=INK)
            side.text(xs[-1] + 0.12, ys[-1], f"{ys[-1]:.1f}", va="center", fontsize=7.4, color=INK)
        side.set_xticks(xs, list(sizes))
        side.set_xlim(-0.72, xs[-1] + 0.72)
        side.set_ylim(0, 100)
        side.set_yticks([0, 25, 50, 75, 100], ["0", "25", "50", "75", "100%"])
        side.set_xlabel("planets in the system")
        side.grid(axis="x", visible=False)
        side.tick_params(length=0)
        side.legend(loc="lower left", fontsize=8, handlelength=1.6, borderaxespad=0.2)
        path = out / PLANET_COUNT_FIGURE
        fig.savefig(path)
        plt.close(fig)
    return path


def figure_inputs(known: list[CatalogRow], details: dict[str, Inputs], out: Path) -> Path:
    stable = [r for r in known if r["overall"] == "stable"]
    ladder = Counter(rests_on(details[r["system"]]) for r in stable)
    longest = max(ladder.values(), default=1)
    with plt.rc_context(cast(Any, _RC)):
        fig, (ax, side) = plt.subplots(
            1, 2, figsize=(7.4, 3.0), width_ratios=[1.08, 1.0], layout="constrained"
        )
        ax.set_title(f"What the {len(stable)} stable verdicts rest on", fontsize=9, loc="left", color=INK)
        for y, (key, text) in enumerate(RESTS_ON.items()):
            color = PLANET_COLORS[0] if key == "published" else NEUTRAL
            ax.barh(y, ladder[key], height=0.3, color=color, zorder=3)
            ax.text(0, y - 0.29, text, fontsize=7.4, color=INK, va="center")
            value = f"{ladder[key]} ({100 * ladder[key] / max(len(stable), 1):.1f}%)"
            ax.text(ladder[key] + 0.02 * longest, y, value, fontsize=8, color=INK, va="center")
        ax.set_ylim(3.45, -0.62)
        ax.set_xlim(0, longest * 1.32)
        ax.set_yticks([])
        ax.set_xticks([])
        ax.grid(visible=False)
        ax.spines["bottom"].set_visible(False)

        side.set_title("Share of checked systems called stable", fontsize=9, loc="left", color=INK)
        groups = size_groups(known)
        for y, rows in enumerate(groups.values()):
            assumed = [r for r in rows if details[r["system"]].every_e_assumed]
            others = [r for r in rows if not details[r["system"]].every_e_assumed]
            a, m = stable_count(assumed), stable_count(others)
            pa, pm = stable_share(assumed), stable_share(others)
            side.plot([pm, pa], [y, y], color=NEUTRAL, lw=1.5, zorder=2)
            side.plot(pa, y, "o", color=PLANET_COLORS[0], ms=7, mec="white", mew=0.8, zorder=3)
            side.plot(pm, y, "s", color=PLANET_COLORS[1], ms=6.5, mec="white", mew=0.8, zorder=3)
            above = f"{pa:.1f}% ({a} of {len(assumed)})"
            below = f"{pm:.1f}% ({m} of {len(others)})"
            ha_above, ha_below = "right" if pa > 60 else "center", "left" if pm < 15 else "center"
            side.text(pa, y - 0.2, above, fontsize=7.4, color=INK, va="bottom", ha=ha_above)
            side.text(pm, y + 0.2, below, fontsize=7.4, color=INK, va="top", ha=ha_below)
        side.set_yticks(range(len(groups)), [f"{g} planets" for g in groups], color=INK)
        side.set_ylim(len(groups) - 0.45, -0.55)
        side.set_xlim(-2, 104)
        side.set_xticks([0, 25, 50, 75, 100], ["0", "25", "50", "75", "100%"])
        side.grid(axis="y", visible=False)
        side.tick_params(length=0)
        side.spines["left"].set_visible(False)
        marks = [
            plt.Line2D([], [], ls="none", marker="o", color=PLANET_COLORS[0], ms=6.5, mec="white"),
            plt.Line2D([], [], ls="none", marker="s", color=PLANET_COLORS[1], ms=6, mec="white"),
        ]
        side.legend(
            marks,
            ["every e assumed 0", "at least one e not assumed"],
            loc="upper center",
            bbox_to_anchor=(0.5, -0.11),
            ncol=2,
            fontsize=8,
            columnspacing=1.0,
            handletextpad=0.2,
        )
        path = out / INPUTS_FIGURE
        fig.savefig(path)
        plt.close(fig)
    return path


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Compute the numbers of docs/findings.md and draw its figures."
    )
    parser.add_argument("catalog", type=Path, help="catalog.csv of the catalog the page describes")
    parser.add_argument("--out", type=Path, required=True, help="folder for the figures")
    parser.add_argument("--refresh", action="store_true", help="download the archive table again")
    parser.add_argument(
        "--earlier", type=Path, nargs="*", default=[], help="other weekly catalogs to compare"
    )
    parser.add_argument(
        "--rebuilds", type=Path, nargs="*", default=[], help="catalogs rebuilt with other seeds"
    )
    parser.add_argument(
        "--eccentricity-what-if",
        action="store_true",
        help="repeat every system with other eccentricities (slow; not catalog results)",
    )
    parser.add_argument(
        "--jobs",
        type=int,
        default=max(1, (os.cpu_count() or 2) - 1),
        help="worker processes of --eccentricity-what-if (default: all cores but one)",
    )
    args = parser.parse_args(argv)

    catalog = read_catalog(args.catalog)
    rows, info = load_rows(refresh=args.refresh)
    hosts = group_by_host(rows)
    details: dict[str, Inputs] = {}
    same: dict[str, bool] = {}
    for row in catalog:
        if row["system"] in hosts:
            inputs, same[row["system"]] = recompute(row, hosts[row["system"]], info)
            if inputs is not None:
                details[row["system"]] = inputs
    by_name = {r["system"]: r for r in catalog}
    checked = [r for r in catalog if r["status"] == "ok"]
    known = [r for r in checked if r["system"] in details]

    print_catalog(catalog, hosts, same, info)
    print_planets(checked, details)
    print_inputs(known, details)
    if args.eccentricity_what_if:
        print_eccentricity_what_if(known, details, hosts, info, args.jobs)
    print_unstable(checked, details, hosts, info)
    ps = None
    what_if = [h for h, _ in (MINIMUM_MASSES, ECCENTRICITY_LIMITS) if h in details]
    if what_if:
        try:
            ps = query_ps(what_if)
        except OSError as exc:
            print(f"\nThe what-if runs are left out: the ps table could not be queried ({exc}).")
    print_limits(by_name, known, details, rows, info, ps)
    print_firmness(catalog, args.earlier, args.rebuilds, details)
    print_meaning(checked, details, by_name, rows, info, ps)

    args.out.mkdir(parents=True, exist_ok=True)
    print("\n== Figures")
    print("wrote", figure_planets(checked, args.out))
    print("wrote", figure_inputs(known, details, args.out))


if __name__ == "__main__":
    main()
