"""Write docs/catalog.md, a sortable table of the stability catalog.

    python scripts/catalog_page.py catalog/            # folder with catalog.csv and catalog_meta.json

The documentation workflow runs this after fetching the latest catalog from the branch "catalog-data".
Without a catalog folder it writes a placeholder page. Sorting and filtering are done by
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

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "catalog.md"
BRANCH = "https://github.com/mimitoz62/exostab/tree/catalog-data"
PAGE = "https://mimitoz62.github.io/exostab/catalog/"

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


!!! warning "Read the verdicts with their caveats"
    Every system is checked with the same settings. Missing orbital phases are drawn at random,
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

# Next to the filter: a common name such as Gliese 876 finds nothing, and Kepler-90 finds another system.
FILTER = """Names are the archive's, for example KOI-351 (Kepler-90), GJ 876 (Gliese 876), ups And (Upsilon Andromedae)
and 55 Cnc (55 Cancri). The filter looks for part of a name and ignores case, spaces and punctuation, so `Kepler-90`
finds Kepler-903 but not KOI-351. Each row has its own link, for example [TRAPPIST-1](#trappist-1).

<input id="catalog-filter" type="search" placeholder="Filter systems…" aria-label="Filter systems">

<p id="catalog-filter-none" role="status" hidden>No system in the table has this name. It lists the archive's systems
with at least two planets, under the archive's names.</p>
"""

DOWNLOAD = """**Download:** [`catalog.csv`](data/catalog.csv), [`catalog.parquet`](data/catalog.parquet) and
[`catalog_meta.json`](data/catalog_meta.json) (settings and archive download date). Every weekly version is
kept on the [`catalog-data` branch]({branch}). Column definitions are at the end of this page.
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


def _row_id(system: str) -> str:
    """The id of a system's row, for a link such as catalog/#trappist-1."""
    return re.sub(r"[^0-9a-z]+", "-", system.lower()).strip("-")


def _dataset(meta: dict[str, object]) -> str:
    """The catalog as a schema.org Dataset, the form Google Dataset Search reads. No license yet: the owner has not
    chosen one for the catalog data."""
    dataset = {
        "@context": "https://schema.org/",
        "@type": "Dataset",
        "name": "exostab stability catalog of known multi-planet exoplanet systems",
        "description": (
            "Orbital-stability verdicts for the multi-planet systems in the NASA Exoplanet Archive's Planetary "
            "Systems Composite Parameters table: Hill spacing, angular momentum deficit and N-body integration "
            "with MEGNO, with the same settings for all systems, recomputed every week. Systems that exostab "
            "cannot model are listed as skipped, with the reason."
        ),
        "url": PAGE,
        "sameAs": BRANCH,
        "keywords": ["exoplanets", "orbital stability", "planetary systems", "N-body", "MEGNO", "AMD"],
        "creator": {
            "@type": "Person",
            "name": "Mehmet Öz",
            "identifier": "https://orcid.org/0009-0007-1005-7640",
        },
        "isBasedOn": "https://doi.org/10.26133/NEA13",
        "isAccessibleForFree": True,
        "dateModified": str(meta["created_utc"])[:10],
        "distribution": [
            {"@type": "DataDownload", "encodingFormat": "text/csv", "contentUrl": f"{PAGE}data/catalog.csv"},
            {
                "@type": "DataDownload",
                "encodingFormat": "application/vnd.apache.parquet",
                "contentUrl": f"{PAGE}data/catalog.parquet",
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
    parts = [HEADER.format(branch=BRANCH), _dataset(meta), DOWNLOAD.format(branch=BRANCH)]
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
    body = []
    for r in rows:
        cells = []
        for key, _ in COLUMNS:
            text, sort = _cell(key, r)
            cls = (
                f' class="verdict-{text}"'
                if key in ("overall", "hill", "amd", "nbody") and text in VERDICTS
                else ""
            )
            title = f' title="{html.escape(r["reason"])}"' if key == "overall" and r["status"] != "ok" else ""
            cells.append(f'<td data-sort="{html.escape(sort)}"{cls}{title}>{html.escape(text)}</td>')
        body.append(f'<tr id="{html.escape(_row_id(r["system"]))}">' + "".join(cells) + "</tr>")
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
| Flags | Number of data-completion rules applied (the CSV lists them) |

The CSV has more columns: archive row names, completion rules, energy errors (`energy_error_nominal` is the
largest relative energy error over 1,200 checks through the nominal run), versions and run times.
"""
    )
    return "\n".join(parts)


def main() -> None:
    folder = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    OUT.write_text(render(folder), encoding="utf-8")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
