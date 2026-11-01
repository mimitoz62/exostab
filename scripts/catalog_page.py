"""Write docs/catalog.md, a sortable table of the stability catalog.

    python scripts/catalog_page.py catalog/            # folder with catalog.csv and catalog_meta.json

The documentation workflow runs this after fetching the latest catalog from the branch "catalog-data".
Without a catalog folder it writes a placeholder page. A system's name links to its page if scripts/system_pages.py has
written one, so that script runs first. Sorting and filtering are done by
docs/javascripts/catalog.js in the browser; the table itself is plain HTML, so it can also be read without
JavaScript.
"""

from __future__ import annotations

import csv
import html
import json
import re
import sys
from collections import Counter
from pathlib import Path

from exostab.data.names import other_names

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "catalog.md"
SYSTEMS = ROOT / "docs" / "systems"  # one page per system, written by scripts/system_pages.py
BRANCH = "https://github.com/mimitoz62/exostab/tree/catalog-data"
SITE = "https://mimitoz62.github.io/exostab/"
PAGE = f"{SITE}catalog/"

# The front matter hides the navigation and table-of-contents sidebars (Material for MkDocs): the table has 12
# columns and needs the full page width; between the sidebars it would scroll sideways.
HEADER = """---
hide:
  - navigation
  - toc
title: Stability catalog of known multi-planet exoplanet systems
description: >-
  Hill spacing, AMD and N-body verdicts for the multi-planet systems in the NASA Exoplanet Archive, recomputed every
  week.
---

# Stability catalog

exostab's three indicators for the multi-planet systems in the NASA Exoplanet Archive's Planetary Systems
Composite Parameters table, recomputed every week by the
[catalog workflow](https://github.com/mimitoz62/exostab/blob/main/.github/workflows/catalog.yml).
[What the catalog shows](findings.md) describes the results of the catalog of 26 October 2026 and how firm they are.
[Changes between catalogs](catalog-changes.md) lists what changed from one catalog to the next.
Each system has its own page, for example
[TRAPPIST-1](https://mimitoz62.github.io/exostab/systems/trappist-1/).

!!! warning "Read the verdicts with their caveats"
    Each system exostab can model is checked with the same settings. Missing orbital phases are drawn at random,
    minimum masses are used as masses, and orbits are coplanar. A resonant system can therefore look marginal or
    unstable here, although the full solution of one paper shows it is stable (GJ 876 is the standard example).
    Masses and eccentricities that are only upper limits are used at the limit, with draws below it; a system
    whose instability rests on them is shown as marginal. Systems exostab cannot model (for example circumbinary
    planets, a planet with neither mass nor radius, or a host whose other planets orbit a companion star) are
    listed as skipped with the reason. A run in which a planet passes within half its Hill radius of the star
    gets no verdict. The catalog uses 10 draws and `exostab check` 20 by default, so a verdict can differ
    (TOI-270 on 26 October 2026: stable here, marginal with the defaults). Add `--draws 10` to match the
    catalog's settings. With 10 draws, one draw can change a verdict: in three local rebuilds of the catalog of
    26 October 2026 with different seeds, 50 of the 1,044 verdicts differ, 10 of them between marginal and
    unstable ([details](findings.md#how-firm-these-numbers-are)). Run `exostab check "<name>"` to see every
    assumption, or `--from-file` with a published solution.
"""

# Written without a catalog folder, as in the committed docs/catalog.md and in local previews (mkdocs serve).
PLACEHOLDER = """
*This copy of the page has no catalog table: it was generated without a catalog. The documentation workflow builds
the [published page]({page}) from the newest catalog on the branch [`catalog-data`]({branch}).*
"""

# Systems that are widely known, listed for that reason and never because of their verdicts.
WELL_KNOWN = (
    "TRAPPIST-1",
    "KOI-351",
    "GJ 876",
    "55 Cnc",
    "ups And",
    "Kepler-11",
    "TOI-178",
    "HR 8799",
    "HD 10180",
    "PSR B1257+12",
    "Proxima Cen",
    "tau Cet",
    "Kepler-186",
    "TOI-700",
)

# Next to the filter: a common name such as Gliese 876 finds nothing, and Kepler-90 finds another system.
FILTER = """Names are the archive's, for example KOI-351 (Kepler-90), GJ 876 (Gliese 876), ups And (Upsilon Andromedae)
and 55 Cnc (55 Cancri). The filter looks for part of a name, also of these other names, and ignores case, spaces and
punctuation, so `Kepler-90` finds KOI-351 and Kepler-903, and `gliese 876` finds GJ 876. Each row has its own link, for example [TRAPPIST-1](#trappist-1).

<input id="catalog-filter" type="search" placeholder="Filter systems…" aria-label="Filter systems">

<p id="catalog-filter-none" role="status" hidden>No system in the table has this name. It lists the archive's systems
with at least two planets, under the archive's names.</p>
"""

DOWNLOAD = """**Download:** [`catalog.csv`](data/catalog.csv), [`catalog.parquet`](data/catalog.parquet) and
[`catalog_meta.json`](data/catalog_meta.json) (settings and archive download date). Every weekly version is
kept on the [`catalog-data` branch]({branch}). Every column is defined at the end of this page.
"""

COLUMNS = [
    ("system", "System"),
    ("n_planets", "Planets"),
    ("overall", "Overall"),
    ("hill", "Hill"),
    ("amd", "AMD"),
    ("nbody", "N-body"),
    ("hill_min_separation", "Min. spacing (R_H)"),
    ("amd_beta_max", "Max. AMD β"),
    ("megno_nominal", "Nominal ⟨Y⟩"),
    ("draws_summary", "Draws reg/chaos/unst"),
    ("t_end_yr", "Horizon (yr)"),
    ("n_flags", "Flags"),
]
VERDICTS = {"stable", "marginal", "unstable", "inconclusive"}

# The verdict rules and the AMD beta column changed in 1.0.0 (CHANGELOG.md). A catalog computed with an earlier
# version (the weekly runs before the 1.0.0 code reached main used 0.1.0.dev0) gets a notice, so that its rows are
# not read against the caveats and column definitions of this page. Raise this when the rules change again.
RULES_VERSION = (1, 0, 0)

OLD_RULES = """
!!! note "This catalog was computed with earlier rules"
    It was computed with exostab {version}, a development version from before 1.0.0, whose verdict rules differ
    from those described on this page and in [Methods](methods.md). For example, a system whose instability rests
    on upper limits can be listed as unstable, and the column Max. AMD β holds the coplanar value β_p rather than
    the β defined below (β = 2β_p). The next weekly run recomputes the catalog with the current version.
"""


# Every column of catalog.csv (and catalog.parquet): name, unit, meaning and what an empty value means. The pages of
# scripts/system_pages.py take their explanations of the numbers from here.
CSV_COLUMNS = {
    "system": ("—", "Host name in the archive's table (`hostname`). Never empty."),
    "n_planets": (
        "—",
        "Planets modelled; without a verdict, the number of planet rows of the host. Never empty.",
    ),
    "status": (
        "—",
        "`ok`, `skipped` (exostab cannot model it), `timeout` (over the cap) or `error`. Never empty.",
    ),
    "reason": ("—", "Why there is no verdict. Empty when `status` is `ok`."),
    "overall": ("—", "Overall verdict: stable, marginal, unstable or inconclusive. Empty without a verdict."),
    "hill": ("—", "Verdict of the Hill spacing: stable, marginal or unstable. Empty without a verdict."),
    "amd": (
        "—",
        "Verdict of the angular momentum deficit: stable, marginal or unstable. Empty without a verdict.",
    ),
    "nbody": ("—", "Verdict of the N-body integration, as for `overall`. Empty without a verdict."),
    "hill_min_separation": (
        "mutual Hill radii",
        "Smallest separation of adjacent planets, with the nominal values. Empty without a verdict.",
    ),
    "amd_beta_max": (
        "—",
        "Largest AMD-stability coefficient β of the adjacent pairs, with twice the coplanar AMD for the unknown "
        "inclinations. Below 1 excludes collisions between planets in the secular (orbit-averaged) approximation, which "
        "leaves out mean-motion resonances, if the unknown inclinations carry no more AMD than the eccentricities; the "
        "AMD verdict is stable only if, in addition, "
        "the innermost planet cannot reach the star (β_S < 1) and every pair lies in the domain of the critical AMD. "
        "`inf` (∞ on the pages) means that resonances overlap even for circular orbits. Empty without a verdict.",
    ),
    "megno_nominal": (
        "—",
        "MEGNO ⟨Y⟩ of the nominal run: it settles at 2 for regular motion, and exostab counts 2.2 or more as chaotic. "
        "A run stopped by a close encounter still has a value. Empty without a verdict.",
    ),
    "hill_summary": (
        "—",
        "The report card's sentence on the Hill spacing. Empty without a verdict, and not in catalogs built before "
        "November 2026.",
    ),
    "amd_summary": (
        "—",
        "The report card's sentence on the AMD. Empty without a verdict, and not in catalogs built before November 2026.",
    ),
    "overall_summary": (
        "—",
        "The report card's sentence on the overall verdict. Empty without a verdict, and not in catalogs built before "
        "November 2026.",
    ),
    "nbody_regular": ("draws", "Draws with regular motion. Empty without a verdict."),
    "nbody_chaotic": ("draws", "Draws with chaotic motion. Empty without a verdict."),
    "nbody_unstable": ("draws", "Draws with a close encounter or escape. Empty without a verdict."),
    "nbody_inconclusive": ("draws", "Draws whose integration could not be trusted. Empty without a verdict."),
    "energy_error_nominal": (
        "—",
        "Largest relative energy error over 1,200 checks through the nominal run. Empty without a verdict.",
    ),
    "t_end_yr": ("yr", "Horizon: the length of the N-body runs. Empty without a verdict."),
    "orbits": ("orbits of the innermost planet", "Requested length of the runs. Never empty."),
    "draws": ("—", "Monte Carlo draws requested. Never empty."),
    "seed": ("—", "Random seed. Never empty."),
    "completion_rules": (
        "—",
        "The [completion rules](data-assumptions.md#completion-rules) applied, separated by semicolons. Empty without "
        "a verdict.",
    ),
    "n_flags": (
        "—",
        "Flags set by those rules; a rule that fires for several planets counts each time. Empty without a verdict.",
    ),
    "archive_rows": (
        "—",
        "The archive's planet names (`pl_name`), separated by semicolons. Empty without a verdict.",
    ),
    "data_source": (
        "—",
        "`archive`, `archive-cache` for the archive's table from the local cache, or `snapshot` for the snapshot bundled with the package. Never empty.",
    ),
    "data_retrieved_utc": ("UTC, ISO 8601", "When the table was downloaded. Empty if that is not known."),
    "exostab_version": ("—", "Version of exostab. Never empty."),
    "rebound_version": ("—", "Version of REBOUND. Empty without a verdict."),
    "runtime_s": ("s", "Run time of the system's check. Empty without a verdict."),
}

META_KEYS = {
    "created_utc": ("UTC, ISO 8601", "When the catalog was written."),
    "exostab_version": ("—", "Version of exostab."),
    "settings.orbits": ("orbits of the innermost planet", "Requested length of the runs."),
    "settings.draws": ("—", "Monte Carlo draws per system."),
    "settings.seed": ("—", "Random seed."),
    "settings.max_seconds": ("s", "Wall-clock cap per system; a system over it has `status` `timeout`."),
    "settings.jobs": ("—", "Worker processes; `null` means one fewer than the CPUs of the machine."),
    "data_source": ("—", "`archive`, `archive-cache` or `snapshot`, as in the CSV."),
    "data_retrieved_utc": ("UTC, ISO 8601", "When the table was downloaded; `null` if that is not known."),
    "data_note": (
        "text",
        "Why the data are not the archive table, if so; or `null`. Example: the archive could not be reached.",
    ),
    "n_systems": ("—", "Rows in the catalog."),
    "columns": ("—", "The names of the CSV columns, in order."),
}


def _dictionary() -> str:
    """The two tables that define every column of catalog.csv and every key of catalog_meta.json."""

    def table(head: str, entries: dict[str, tuple[str, str]]) -> str:
        rows = "\n".join(f"| `{name}` | {unit} | {text} |" for name, (unit, text) in entries.items())
        return f"| {head} | Unit | Meaning |\n|---|---|---|\n{rows}\n"

    return (
        "\n### `catalog.csv` and `catalog.parquet`\n\nThe two files have the same columns. In the Parquet file an "
        "empty value is null.\n\n"
        + table("Column", CSV_COLUMNS)
        + "\n### `catalog_meta.json`\n\n"
        + table("Key", META_KEYS)
    )


def _citation(meta: dict[str, object]) -> str:
    return f"""
## How to cite the catalog

> Öz, M., *exostab stability catalog of known multi-planet exoplanet systems*, version of
> {str(meta["created_utc"])[:10]}, <{PAGE}>. Based on the NASA Exoplanet Archive's Planetary Systems Composite
> Parameters table, doi:[10.26133/NEA13](https://doi.org/10.26133/NEA13), accessed
> {str(meta.get("data_retrieved_utc") or "?")[:10]}.

The file of this version stays at
<{BRANCH.replace("/tree/", "/blob/")}/archive/catalog-{str(meta["created_utc"])[:10]}.csv>.

A DOI for the catalog will follow. [Citing exostab](citing.md) lists what to cite for the software, the methods and
the data. The catalog data are licensed under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/); the software is under the MIT license.
"""


def _row_id(system: str) -> str:
    """The id of a system's row, for a link such as catalog/#trappist-1."""
    return re.sub(r"[^0-9a-z]+", "-", system.lower()).strip("-")


def _well_known(rows: list[dict[str, str]]) -> str:
    """A line of links to the pages of WELL_KNOWN, without a system that has no page; empty if none has one."""
    hosts = {r["system"]: r for r in rows}
    links = []
    for system in WELL_KNOWN:
        if system in hosts and (SYSTEMS / f"{_row_id(system)}.md").exists():
            names = other_names(system, filter(None, hosts[system]["archive_rows"].split(";")), hosts)
            shown = f"{system} ({', '.join(names)})" if names else system
            links.append(f"[{shown}](systems/{_row_id(system)}.md)")
    return f"**Some well-known systems:** {', '.join(links)}.\n" if links else ""


def _dataset(meta: dict[str, object]) -> str:
    """The catalog as a schema.org Dataset, the form Google Dataset Search reads.

    Of the properties Google recommends, those that do not hold for this dataset are left out: identifier (no DOI
    yet), citation (no article about it), includedInDataCatalog, funder, and temporal and spatial coverage.
    """
    date = str(meta["created_utc"])[:10]
    dataset = {
        "@context": "https://schema.org/",
        "@type": "Dataset",
        "name": "exostab stability catalog of known multi-planet exoplanet systems",
        "description": (
            "Orbital-stability verdicts for the multi-planet systems in the NASA Exoplanet Archive's Planetary "
            "Systems Composite Parameters table: Hill spacing, angular momentum deficit and N-body integration "
            "with MEGNO, with the same settings for each system that exostab can model, recomputed every week. "
            "Systems that exostab cannot model are listed as skipped, with the reason. A verdict describes the "
            "published parameter set under these settings and is not a proof of stability or instability."
        ),
        "url": PAGE,
        "sameAs": BRANCH,
        "version": date,
        "keywords": ["exoplanets", "orbital stability", "planetary systems", "N-body", "MEGNO", "AMD"],
        "creator": {
            "@type": "Person",
            "name": "Mehmet Öz",
            "givenName": "Mehmet",
            "familyName": "Öz",
            "sameAs": "https://orcid.org/0009-0007-1005-7640",  # Google asks for an ORCID iD in this property
        },
        "isBasedOn": "https://doi.org/10.26133/NEA13",
        "isAccessibleForFree": True,
        "license": "https://creativecommons.org/licenses/by/4.0/",
        "dateModified": date,
        "measurementTechnique": (
            "Hill spacing, angular momentum deficit, and N-body integration with REBOUND and the MEGNO chaos "
            "indicator, with Monte Carlo draws within the published uncertainties"
        ),
        "variableMeasured": [
            "Overall stability verdict",
            "Hill spacing verdict",
            "Angular momentum deficit verdict",
            "N-body verdict",
            "Smallest separation of adjacent planets, in mutual Hill radii",
            "Largest AMD-stability coefficient of the adjacent pairs",
            "MEGNO of the nominal run",
            "Numbers of draws with regular motion, chaotic motion, a close encounter or escape, or no trusted result",
        ],
        "distribution": [
            # docs/data/ on the site, as in the links of DOWNLOAD
            {"@type": "DataDownload", "encodingFormat": "text/csv", "contentUrl": f"{SITE}data/catalog.csv"},
            {
                "@type": "DataDownload",
                "encodingFormat": "application/vnd.apache.parquet",
                "contentUrl": f"{SITE}data/catalog.parquet",
            },
        ],
    }
    text = json.dumps(dataset, ensure_ascii=False).replace("</", "<\\/")
    return f'<script type="application/ld+json">{text}</script>\n'


def _release(version: str) -> tuple[int, ...]:
    """(major, minor, patch) of a version string such as "1.0.0.dev0"; (0,) if it does not start with one."""
    m = re.match(r"(\d+)\.(\d+)\.(\d+)", version)
    return tuple(int(x) for x in m.groups()) if m else (0,)


def _num(value: str, fmt: str) -> str:
    if value in ("", "None", "nan"):
        return "—"
    x = float(value)
    if x == float("inf"):
        return "∞"
    return format(x, fmt)


def _cell(key: str, row: dict[str, str]) -> tuple[str, str]:
    """(display text, sort key)."""
    if key == "draws_summary":
        if row["status"] != "ok":
            return "—", "-1"
        return f"{row['nbody_regular']}/{row['nbody_chaotic']}/{row['nbody_unstable']}", row["nbody_regular"]
    v = row.get(key, "")
    if key in ("overall", "hill", "amd", "nbody"):
        text = v if v in VERDICTS else (row["status"] if key == "overall" else "—")
        return text, text
    if key == "hill_min_separation":
        return _num(v, ".2f"), v or "-1"
    if key == "amd_beta_max":
        return _num(v, ".3g"), "1e308" if v == "inf" else (v or "-1")
    if key == "megno_nominal":
        return _num(v, ".3f"), v or "-1"
    if key == "t_end_yr":
        return _num(v, ",.0f"), v or "-1"
    return v, v


def render(folder: Path | None) -> str:
    if folder is None or not (folder / "catalog.csv").exists():
        return HEADER.format(branch=BRANCH) + PLACEHOLDER.format(branch=BRANCH, page=PAGE)
    rows = list(csv.DictReader((folder / "catalog.csv").open(encoding="utf-8")))
    meta = json.loads((folder / "catalog_meta.json").read_text(encoding="utf-8"))
    counts = Counter(r["overall"] if r["status"] == "ok" else r["status"] for r in rows)
    s = meta["settings"]
    parts = [HEADER.format(branch=BRANCH), _dataset(meta), _well_known(rows), DOWNLOAD.format(branch=BRANCH)]
    parts.append(
        f"**This version:** {meta['n_systems']} systems, computed {meta['created_utc'][:10]} with exostab "
        f"{meta['exostab_version']} from archive data of {(meta.get('data_retrieved_utc') or '?')[:10]}. "
        f"Settings: {s['orbits']:,.0f} orbits of the innermost planet, {s['draws']} draws, seed {s['seed']}, "
        f"at most {s['max_seconds']:g} s per system.\n"
    )
    summary = ", ".join(f"{k} {v}" for k, v in sorted(counts.items(), key=lambda kv: -kv[1]))
    parts.append(f"**Overall verdicts:** {summary}.\n")
    if _release(str(meta["exostab_version"])) < RULES_VERSION:
        parts.append(OLD_RULES.format(version=html.escape(str(meta["exostab_version"]))))
    parts.append(FILTER)
    head = "".join(
        f'<th scope="col" data-col="{i}">{html.escape(t)}</th>' for i, (_, t) in enumerate(COLUMNS)
    )
    systems = {r["system"] for r in rows}
    body = []
    for r in rows:
        row_id = _row_id(r["system"])
        cells = []
        for key, _ in COLUMNS:
            text, sort = _cell(key, r)
            cls = (
                f' class="verdict-{text}"'
                if key in ("overall", "hill", "amd", "nbody") and text in VERDICTS
                else ""
            )
            title = f' title="{html.escape(r["reason"])}"' if key == "overall" and r["status"] != "ok" else ""
            shown = html.escape(text)
            # Plain HTML, which MkDocs does not rewrite: the page is served at catalog/, the pages at systems/<id>/.
            if key == "system" and (SYSTEMS / f"{row_id}.md").exists():
                shown = f'<a href="../systems/{row_id}/">{shown}</a>'
            cells.append(f'<td data-sort="{html.escape(sort)}"{cls}{title}>{shown}</td>')
        names = other_names(r["system"], filter(None, r["archive_rows"].split(";")), systems)
        also = f' data-names="{html.escape("; ".join(names))}"' if names else ""
        body.append(f'<tr id="{html.escape(row_id)}"{also}>' + "".join(cells) + "</tr>")
    parts.append(
        '<div class="catalog-wrap"><table id="catalog-table">\n<thead><tr>'
        + head
        + "</tr></thead>\n<tbody>\n"
        + "\n".join(body)
        + "\n</tbody></table></div>\n"
    )
    parts.append(
        """
## Columns

| Column | Meaning |
|---|---|
| Overall, Hill, AMD, N-body | Verdicts: stable, marginal, unstable, inconclusive (see [Methods](methods.md)). "skipped" or "timeout" means no verdict; hover for the reason. |
| Min. spacing | Smallest separation of adjacent planets in mutual Hill radii |
| Max. AMD β | Largest AMD-stability coefficient β of the adjacent pairs, with twice the coplanar AMD for the unknown inclinations. Below 1 excludes collisions between planets; the AMD verdict is stable only if, in addition, the innermost planet cannot reach the star (β_S < 1) and every pair lies in the domain of the critical AMD (see [Methods](methods.md)). ∞ means resonances overlap even for circular orbits |
| Nominal ⟨Y⟩ | MEGNO of the nominal run (runs stopped by a close encounter still show a value) |
| Draws reg/chaos/unst | Monte Carlo draws that were regular / chaotic / had a close encounter or escape |
| Horizon | Length of the N-body runs in years |
| Flags | Number of flags set by the data-completion rules (the CSV lists the rules) |
"""
    )
    parts.append(_dictionary())
    parts.append(_citation(meta))
    return "\n".join(parts)


def main() -> None:
    folder = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    OUT.write_text(render(folder), encoding="utf-8")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
