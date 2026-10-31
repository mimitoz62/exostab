"""Write docs/catalog-changes.md and docs/catalog-changes.xml: what changed between the weekly catalogs.

    python scripts/catalog_changes.py archive/            # folder with the files catalog-YYYY-MM-DD.csv

The documentation workflow runs this on the folder archive/ of the branch "catalog-data", after
scripts/system_pages.py: a system's name links to its page if that script has written one. Without weekly files it
writes the placeholder page, as in the committed docs/catalog-changes.md, and a feed with no entries. The feed is an
Atom feed, which MkDocs copies to catalog-changes.xml under the site. It is not committed, so the placeholder does
not link to it.
"""

from __future__ import annotations

import csv
import html
import sys
import xml.etree.ElementTree as ET
from datetime import date
from itertools import pairwise
from pathlib import Path
from typing import NamedTuple

sys.path.insert(0, str(Path(__file__).resolve().parent))
from catalog_page import BRANCH, RULES_VERSION, SYSTEMS, VERDICTS, _cell, _release, _row_id

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "catalog-changes.md"
FEED = ROOT / "docs" / "catalog-changes.xml"
SITE = "https://mimitoz62.github.io/exostab/"
PAGE = f"{SITE}catalog-changes/"
ATOM = "http://www.w3.org/2005/Atom"
# A tag URI (RFC 4151) rather than the page's URL, so that the ids stay the same if the site moves.
FEED_ID = "tag:mimitoz62.github.io,2026:exostab/catalog-changes"
# A feed with no entries still needs a time: a fixed one, so that a later build does not change the feed.
EMPTY_FEED_UPDATED = "2026-10-31T00:00:00Z"
MAX_COMPARISONS = 8
CAVEAT = "A change here is not a discovery and says nothing about the planets."

HEADER = f"""---
title: Changes between the weekly stability catalogs
description: >-
  What changed from one weekly exostab catalog to the next: systems added and removed, and rows whose overall verdict
  differs. {CAVEAT}
---

# Changes between catalogs

exostab's [stability catalog](catalog.md) is recomputed every week. This page compares each catalog with the one
before it: the systems added and removed, and the rows whose overall verdict differs.

!!! warning "A change here is not a discovery"
    A change means that the rows of a system differ between two catalogs. It says nothing about the planets. A verdict
    can change for three reasons, and this page cannot tell which one applies:

    - **The archive's values changed.** The NASA Exoplanet Archive's table now gives other values for the system.
    - **The code changed.** The catalogs were computed with other code or other settings. A development version such
      as 1.0.2.dev0 can name different code from one week to the next.
    - **Chance.** The draws and any missing orbital angles are random. The seed stays the same, so the same values and
      the same code on the same platform repeat a row. A small change in any of these can give other runs, and with 10
      draws, one draw can change a verdict: in three local rebuilds of the catalog of 26 October 2026 with different
      seeds, 50 of the 1,044 verdicts differ ([how firm the verdicts are](findings.md#how-firm-these-numbers-are)).

    With the same seed, values and code, two catalogs that agree show determinism, not robustness. Each verdict
    describes a published parameter set under the catalog's settings. [Stable is not a proof, and marginal does not
    mean unstable](findings.md#what-stable-means-here-and-what-it-does-not). [Unstable is not a prediction for the
    planets](findings.md#published-parameter-sets-that-do-not-survive-integration).

The overall verdict is the catalog's column `overall`: stable, marginal, unstable or inconclusive. A row has no verdict
if it is skipped, over the time limit or an error, and a row with no verdict in both catalogs is not listed. The time
limit is in wall-clock seconds, so a slower machine alone can put a row over it. A system is added or removed when the
archive's table gains or loses it as a system with at least two planets, when the code changes which hosts get a row,
or when a run covers only part of the table. That does not say when its planets were found, and a renamed host counts
as both. Draws are given as regular / chaotic / with a close encounter or escape, as in the catalog's table; draws whose
integration could not be trusted are not counted, so the three can add up to less than the number of draws.
"""

# Written without weekly files, as in the committed docs/catalog-changes.md and in local previews (mkdocs serve).
PLACEHOLDER = """
*This copy of the page has no comparisons: it was generated without the weekly catalogs. The documentation workflow
builds the [published page]({page}) from the files in `archive/` on the branch [`catalog-data`]({branch}).*
"""

INTRO = """The [Atom feed](catalog-changes.xml) has one entry per comparison. This page keeps up to {most} comparisons,
newest first. Every weekly CSV stays in [`archive/` on the branch `catalog-data`]({branch}/archive), and each row
records the version of exostab and, with a verdict, that of REBOUND.
"""

NOTHING_YET = "There is no comparison yet: it takes two catalogs computed with the current verdict rules.\n"


class Catalog(NamedTuple):
    day: date
    version: str
    settings: str
    updated: str  # the time of its entry in the feed
    rows: dict[str, dict[str, str]]  # by system


class Comparison(NamedTuple):
    old: Catalog
    new: Catalog
    added: list[str]
    removed: list[str]
    changed: list[str]  # a verdict in both catalogs, and not the same one
    gained: list[str]  # no verdict, then a verdict
    lost: list[str]  # a verdict, then no verdict

    @property
    def anchor(self) -> str:
        """The id of the comparison's heading, and the end of its entry's id in the feed."""
        return f"from-{self.old.day}-to-{self.new.day}"

    @property
    def groups(self) -> list[tuple[str, list[str]]]:
        return [
            ("Systems added", self.added),
            ("Systems removed", self.removed),
            ("Overall verdicts changed", self.changed),
            ("Rows from no verdict to a verdict", self.gained),
            ("Rows from a verdict to no verdict", self.lost),
        ]


def read_archive(folder: Path | None) -> list[Catalog]:
    """The weekly catalogs of a folder, oldest first. A file without rows is no catalog to compare."""
    catalogs = []
    for path in sorted(folder.glob("catalog-????-??-??.csv")) if folder else []:
        with path.open(encoding="utf-8", newline="") as f:
            rows = list(csv.DictReader(f))
        if rows:
            first = rows[0]
            day = path.stem.removeprefix("catalog-")
            catalogs.append(
                Catalog(
                    day=date.fromisoformat(day),
                    version=first["exostab_version"],
                    settings=f"{float(first['orbits']):,.0f} orbits, {first['draws']} draws, seed {first['seed']}",
                    # When the archive's table was downloaded, if that is known. A later build of the site
                    # does not change it, and a second run on the same day, which overwrites the file, does.
                    updated=first["data_retrieved_utc"] or f"{day}T00:00:00Z",
                    rows={r["system"]: r for r in rows},
                )
            )
    return catalogs


def compare(old: Catalog, new: Catalog) -> Comparison:
    both = sorted(old.rows.keys() & new.rows.keys(), key=str.lower)
    # `overall` is empty in a row without a verdict, so two such rows do not differ here.
    differ = [s for s in both if old.rows[s]["overall"] != new.rows[s]["overall"]]
    return Comparison(
        old=old,
        new=new,
        added=sorted(new.rows.keys() - old.rows.keys(), key=str.lower),
        removed=sorted(old.rows.keys() - new.rows.keys(), key=str.lower),
        changed=[s for s in differ if old.rows[s]["overall"] and new.rows[s]["overall"]],
        gained=[s for s in differ if not old.rows[s]["overall"]],
        lost=[s for s in differ if not new.rows[s]["overall"]],
    )


def comparisons(catalogs: list[Catalog]) -> list[Comparison]:
    """Consecutive catalogs under the current verdict rules (catalog_page.RULES_VERSION), newest first."""
    current = [c for c in catalogs if _release(c.version) >= RULES_VERSION]
    return [compare(old, new) for old, new in reversed(list(pairwise(current))[-MAX_COMPARISONS:])]


def _day(day: date) -> str:
    return f"{day.day} {day:%B %Y}"


def _name(system: str) -> str:
    row_id = _row_id(system)
    shown = html.escape(system)
    # Plain HTML, as in the catalog's table: this page is served at catalog-changes/, the pages at systems/<id>/.
    return f'<a href="../systems/{row_id}/">{shown}</a>' if (SYSTEMS / f"{row_id}.md").exists() else shown


def _state(row: dict[str, str]) -> str:
    """The overall verdict of a row or, without a verdict, its status, as in the catalog's table."""
    text = _cell("overall", row)[0]
    return f'<span class="verdict-{text}">{text}</span>' if text in VERDICTS else html.escape(text)


def _line(c: Comparison, system: str) -> str:
    """What the rows of the system say, in the catalog or catalogs that have it."""
    rows = [catalog.rows[system] for catalog in (c.old, c.new) if system in catalog.rows]
    states = " to ".join(_state(r) for r in rows)
    draws = " to ".join(html.escape(_cell("draws_summary", r)[0]) for r in rows)
    return f"{_name(system)}: {states} (draws {draws})"


def _about(catalog: Catalog) -> str:
    return (
        f"{_day(catalog.day)}: exostab {html.escape(catalog.version)}, {len(catalog.rows):,} systems, "
        f"{html.escape(catalog.settings)}."
    )


def _section(c: Comparison) -> str:
    """One comparison. All that comes from a CSV is in plain HTML, so its only escaping is that of HTML."""
    items = []
    for label, systems in c.groups:
        lines = "".join(f"<li>{_line(c, s)}</li>\n" for s in systems)
        nested = f"\n<ul>\n{lines}</ul>\n" if lines else ""
        items.append(f"<li>{label}: {len(systems):,}{nested}</li>\n")
    return (
        f"## {_day(c.old.day)} to {_day(c.new.day)} {{#{c.anchor}}}\n\n"
        f"<p>{_about(c.old)}<br>\n{_about(c.new)}</p>\n\n"
        f"<ul>\n{''.join(items)}</ul>\n"
    )


def render(catalogs: list[Catalog]) -> str:
    if not catalogs:
        return HEADER + PLACEHOLDER.format(branch=BRANCH, page=PAGE)
    parts = [HEADER, INTRO.format(branch=BRANCH, most=MAX_COMPARISONS)]
    earlier = [c for c in catalogs if _release(c.version) < RULES_VERSION]
    if earlier:
        listed = ", ".join(f"{_day(c.day)} (exostab {html.escape(c.version)})" for c in earlier)
        parts.append(
            "<p>Catalogs computed with earlier verdict rules are left out, because their verdicts can differ for that "
            f"reason alone: {listed}.</p>\n"
        )
    parts += [_section(c) for c in comparisons(catalogs)] or [NOTHING_YET]
    return "\n".join(parts)


def _element(parent: ET.Element, tag: str, text: str | None = None, **attributes: str) -> ET.Element:
    element = ET.SubElement(parent, f"{{{ATOM}}}{tag}", attributes)
    element.text = text
    return element


def feed(catalogs: list[Catalog]) -> str:
    """The Atom feed (RFC 4287), with one entry for each comparison on the page."""
    found = comparisons(catalogs)
    ET.register_namespace("", ATOM)
    root = ET.Element(f"{{{ATOM}}}feed")
    _element(root, "title", "exostab: changes between the weekly stability catalogs")
    _element(root, "subtitle", f"Systems added and removed, and rows whose overall verdict differs. {CAVEAT}")
    _element(root, "id", FEED_ID)
    _element(root, "updated", found[0].new.updated if found else EMPTY_FEED_UPDATED)
    _element(root, "link", rel="self", type="application/atom+xml", href=f"{SITE}catalog-changes.xml")
    _element(root, "link", rel="alternate", type="text/html", href=PAGE)
    _element(_element(root, "author"), "name", "Mehmet Öz")
    for c in found:
        entry = _element(root, "entry")
        _element(entry, "title", f"exostab catalog, {_day(c.old.day)} to {_day(c.new.day)}")
        _element(entry, "id", f"{FEED_ID}/{c.anchor}")
        _element(entry, "updated", c.new.updated)
        _element(entry, "link", rel="alternate", type="text/html", href=f"{PAGE}#{c.anchor}")
        counts = " ".join(f"{label}: {len(systems):,}." for label, systems in c.groups)
        _element(entry, "summary", f"{counts} {CAVEAT}")
    ET.indent(root)
    return ET.tostring(root, encoding="utf-8", xml_declaration=True).decode("utf-8") + "\n"


def main() -> None:
    catalogs = read_archive(Path(sys.argv[1]) if len(sys.argv) > 1 else None)
    OUT.write_text(render(catalogs), encoding="utf-8")
    FEED.write_text(feed(catalogs), encoding="utf-8")
    print(f"wrote {OUT} and {FEED}")


if __name__ == "__main__":
    main()
