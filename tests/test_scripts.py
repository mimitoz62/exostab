"""Scripts: catalog page, changes and findings, release notes, Zenodo upload, IndexNow, snapshot builder, SPOCK environment."""

from __future__ import annotations

import contextlib
import csv
import html
import importlib.util
import io
import json
import math
import os
import re
import shutil
import subprocess
import urllib.error
import xml.etree.ElementTree as ET
from datetime import datetime
from email.message import Message
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]


def load(name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def small_catalog(tmp_path_factory: pytest.TempPathFactory) -> Path:
    from exostab.catalog.build import CatalogSettings, build_catalog

    out = tmp_path_factory.mktemp("catalog")
    build_catalog(CatalogSettings(orbits=100, draws=1, jobs=2), out, limit=4, offline=True)
    return out


def test_catalog_page(small_catalog: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    page = load("catalog_page")
    monkeypatch.setattr(page, "OUT", tmp_path / "catalog.md")
    text = page.render(small_catalog)
    assert 'id="catalog-table"' in text and text.count("<tr") == 1 + 4
    assert "data/catalog.csv" in text and "Overall verdicts" in text
    assert "verdict-" in text
    # beta < 1 alone is not AMD-stable: beta_S and the domain of the critical AMD also count
    assert "below 1 is AMD-stable" not in text and "β_S < 1" in text
    assert "computed with earlier rules" not in text
    # each row can be linked to, and no two rows of the catalog can share a link
    ids = re.findall(r'<tr id="([^"]+)"', text)
    assert len(ids) == 4 == len(set(ids)) and all(re.fullmatch(r"[0-9a-z]+(-[0-9a-z]+)*", i) for i in ids)
    assert [page._row_id(n) for n in ("TRAPPIST-1", "55 Cnc", "2MASS J19383260+4603591")] == [
        "trappist-1",
        "55-cnc",
        "2mass-j19383260-4603591",
    ]
    # the table's filter also knows a system's other names, from its planets and from spelled-out catalogue names
    rows = list(csv.DictReader((small_catalog / "catalog.csv").open(encoding="utf-8")))
    rows[0].update(system="KOI-351", archive_rows="KOI-351 b;Kepler-90 i")
    folder = tmp_path / "named"
    folder.mkdir()
    (folder / "catalog_meta.json").write_text(
        (small_catalog / "catalog_meta.json").read_text(encoding="utf-8")
    )
    with (folder / "catalog.csv").open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    assert '<tr id="koi-351" data-names="Kepler-90">' in page.render(folder)
    # the description for dataset search engines is valid JSON and names real files
    dataset = json.loads(re.search(r'<script type="application/ld\+json">(.+)</script>', text).group(1))
    assert dataset["@type"] == "Dataset" and len(dataset["description"]) >= 50
    assert {d["contentUrl"].rsplit("/", 1)[1] for d in dataset["distribution"]} == {
        "catalog.csv",
        "catalog.parquet",
    }
    assert (
        dataset["dateModified"]
        == json.loads((small_catalog / "catalog_meta.json").read_text())["created_utc"][:10]
    )
    # the sidebar is hidden on this page, so these sentences are the way to the pages about the results
    assert "[What the catalog shows](findings.md)" in text and "(catalog-changes.md)" in text
    # the filter says what the names are, and catalog.js shows this element when no row matches
    assert "GJ 876 (Gliese 876)" in text and 'id="catalog-filter-none"' in text
    # a catalog from before the 1.0.0 rules (the weekly runs of 0.1.0.dev0) says that its rules differ
    old = tmp_path / "old"
    shutil.copytree(small_catalog, old)
    meta = json.loads((old / "catalog_meta.json").read_text())
    (old / "catalog_meta.json").write_text(json.dumps({**meta, "exostab_version": "0.1.0.dev0"}))
    old_text = page.render(old)
    assert "computed with earlier rules" in old_text and "exostab 0.1.0.dev0, a development" in old_text
    assert [page._release(v) for v in ("0.1.0.dev0", "1.0.0.dev0", "1.0.0", "1.2.3+local", "x")] == [
        (0, 1, 0),
        (1, 0, 0),
        (1, 0, 0),
        (1, 2, 3),
        (0,),
    ]
    placeholder = page.render(None)
    assert "has no catalog table" in placeholder and "data/catalog.csv" not in placeholder
    assert "No catalog has been published" not in placeholder  # the weekly runs have published catalogs
    assert "[What the catalog shows](findings.md)" in placeholder and "(catalog-changes.md)" in placeholder
    monkeypatch.setattr("sys.argv", ["catalog_page.py", str(small_catalog)])
    page.main()
    written = (tmp_path / "catalog.md").read_text()
    assert written.startswith("---\nhide:") and "\n# Stability catalog\n" in written


def test_system_pages(small_catalog: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from urllib.parse import parse_qs, unquote, urlsplit

    from exostab.web.state import decode_state

    pages = load("system_pages")
    table = load("catalog_page")
    monkeypatch.setattr(pages, "OUT", tmp_path / "systems")
    monkeypatch.setattr(table, "SYSTEMS", tmp_path / "systems")
    # no pages yet: the table has no dead links, and row anchors stay
    assert "../systems/" not in table.render(small_catalog)
    assert pages.write_all(small_catalog) == 4
    text = table.render(small_catalog)
    links = re.findall(r'<a href="\.\./systems/([^/"]+)/">', text)
    assert sorted(links) == sorted(p.stem for p in (tmp_path / "systems").glob("*.md")) and len(links) == 4
    assert len(re.findall(r'<tr id="', text)) == 4

    meta = {"created_utc": "2026-10-26T11:24:44+00:00"}
    row = {
        "system": "KOI-351",
        "n_planets": "2",
        "status": "ok",
        "reason": "",
        "overall": "unstable",
        "hill": "unstable",
        "amd": "marginal",
        "nbody": "unstable",
        "hill_min_separation": "2.41",
        "amd_beta_max": "inf",
        "megno_nominal": "12.5",
        "nbody_regular": "0",
        "nbody_chaotic": "0",
        "nbody_unstable": "10",
        "nbody_inconclusive": "0",
        "energy_error_nominal": "1e-6",
        "t_end_yr": "1234.5",
        "orbits": "10000.0",
        "draws": "10",
        "seed": "0",
        "completion_rules": "coplanar_assumed;a_future_rule",
        "archive_rows": "KOI-351 b;Kepler-90 i",
        "data_retrieved_utc": "2026-10-26T10:17:22+00:00",
        "exostab_version": "1.0.0",
    }
    unstable = pages.page(row, meta, {"KOI-351"})
    assert 'title: "KOI-351 (Kepler-90): orbital stability verdicts from exostab"' in unstable
    assert "exclude: true" in unstable and 'exostab check "KOI-351" --draws 10' in unstable
    assert "not a prediction for the planets" in unstable and "#published-parameter-sets" in unstable
    assert "β = ∞" in unstable and "1,234 years" in unstable and "10 with a close encounter" in unstable
    assert "`a_future_rule`" in unstable and "overview/KOI-351" in unstable

    empty = dict.fromkeys(row, "")
    skipped = {
        **row,
        **{
            k: empty[k]
            for k in ("overall", "hill", "amd", "nbody", "archive_rows", "completion_rules", "t_end_yr")
        },
        "status": "skipped",
        "reason": "KOI-351 is a circumbinary_system",
    }
    no_verdict = pages.page(skipped, meta, {"KOI-351"})
    assert "circumbinary\\_system" in no_verdict and "verdict-" not in no_verdict
    assert (
        "exostab check" not in no_verdict
        and "mybinder" not in no_verdict
        and "overview/KOI-351" in no_verdict
    )
    assert "2 planet rows" in no_verdict and "could do with them" in no_verdict
    one_row = pages.page({**skipped, "n_planets": "1"}, meta, {"KOI-351"})
    assert "1 planet row in" in one_row and "could do with it," in one_row
    # text with & and < reaches the reader without a stray backslash
    markdown = pytest.importorskip("markdown")
    reason = pages.page({**skipped, "reason": "Chen & Kipping <2"}, meta, {"KOI-351"})
    assert "Chen &amp; Kipping &lt;2" in markdown.markdown(reason)
    inconclusive = pages.page({**row, "overall": "inconclusive"}, meta, {"KOI-351"})
    assert (
        "makes no statement" in inconclusive.split("---")[1] and "the nominal run or a draw" in inconclusive
    )
    assert "with 10 draws" in unstable and "`inf`" not in unstable
    timeout = pages.page({**skipped, "status": "timeout"}, meta, {"KOI-351"})
    assert "exostab check" in timeout and "verdict-" not in timeout

    # the Binder link survives the two rounds of decoding and selects the system in the app
    for name in ("GJ 876", "2MASS J19383260+4603591", "Barnard's star"):
        urlpath = parse_qs(urlsplit(pages.binder_url(name)).query)["urlpath"][0]
        path = urlsplit(urlpath)
        assert path.path == "exostab/"
        assert decode_state({k: v[0] for k, v in parse_qs(path.query).items()}).system == name
        assert unquote(pages.binder_url(name)).count("exostab/?system=") == 1


def test_catalog_data_dictionary(small_catalog: Path) -> None:
    from exostab.catalog.build import COLUMNS, CatalogSettings

    page = load("catalog_page")
    assert list(page.CSV_COLUMNS) == COLUMNS
    meta = json.loads((small_catalog / "catalog_meta.json").read_text())
    keys = {f"settings.{k}" for k in vars(CatalogSettings())} | (set(meta) - {"settings"})
    assert set(page.META_KEYS) == keys
    text = page.render(small_catalog)
    assert all(f"| `{name}` |" in text for name in [*COLUMNS, *keys])
    # how to cite: the version's date, the archive's DOI and the licence, also for dataset search engines
    assert f"version of\n> {meta['created_utc'][:10]}" in text and "doi:[10.26133/NEA13]" in text
    assert "A DOI for the catalog will follow" in text and "(citing.md)" in text
    assert "CC BY 4.0" in text and '"license": "https://creativecommons.org/licenses/by/4.0/"' in text


def test_cell_formatting() -> None:
    page = load("catalog_page")
    row = {
        "status": "ok",
        "nbody_regular": "3",
        "nbody_chaotic": "1",
        "nbody_unstable": "0",
        "overall": "stable",
        "amd_beta_max": "inf",
        "hill_min_separation": "",
        "megno_nominal": "2.0",
        "t_end_yr": "1234.5",
    }
    assert page._cell("draws_summary", row) == ("3/1/0", "3")
    assert page._cell("amd_beta_max", row) == ("∞", "1e308")
    assert page._cell("hill_min_separation", row)[0] == "—"
    assert page._cell("t_end_yr", row)[0] == "1,234"
    assert page._cell("overall", {**row, "status": "timeout", "overall": ""})[0] == "timeout"


def test_catalog_findings(
    small_catalog: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("EXOSTAB_OFFLINE", "1")  # the bundled snapshot, from which small_catalog was built
    findings = load("catalog_findings")
    catalog = str(small_catalog / "catalog.csv")
    findings.main(
        [
            catalog,
            "--out",
            str(tmp_path),
            "--earlier",
            catalog,
            "--rebuilds",
            catalog,
            catalog,
            "--eccentricity-what-if",
            "--jobs",
            "1",
        ]
    )
    out = capsys.readouterr().out
    # the recomputed Hill and AMD results equal the catalog's, built by the same code from the same table
    assert "This table reproduces 4 of 4 checked systems" in out and "Not reproduced" not in out
    assert "0 verdicts differ" in out and "Verdict differs among the rebuilds: 0 of 4 (0.0%)" in out
    assert "Published catalog against the rebuild with seed 0: 0 of 4 (0.0%) differ" in out
    assert "every e assumed, every e 0.05" in out and "every e removed (so assumed 0)" in out
    for figure in (findings.PLANET_COUNT_FIGURE, findings.INPUTS_FIGURE):
        assert (tmp_path / figure).stat().st_size > 0


def test_catalog_findings_inputs() -> None:
    findings = load("catalog_findings")
    published = {
        "n_planets": 2,
        "n_e_assumed": 0,
        "n_e_published": 2,
        "n_estimated_mass": 0,
        "n_minimum_mass": 0,
        "n_random_phase": 0,
        "n_mass_limits": 0,
        "any_upper_limit": False,
        "all_omega_published": True,
        "n_stars": 1,
        "methods": frozenset({"Transit"}),
        "beta_max": 0.0,
        "outer_orbits": 1e3,
        "pairs": [],
        "planets": [],
    }

    def rests_on(**changed: Any) -> str:
        return str(findings.rests_on(findings.Inputs(**{**published, **changed})))

    assert rests_on() == "published"
    assert rests_on(n_e_assumed=2, n_estimated_mass=2) == "assumed_estimated"
    assert rests_on(n_e_assumed=2, n_estimated_mass=1) == "assumed"
    for changed in ("n_e_assumed", "n_estimated_mass", "n_minimum_mass", "n_random_phase"):
        assert rests_on(**{changed: 1}) == "partly"
    assert rests_on(any_upper_limit=True) == "partly"


def test_catalog_findings_what_if_rows() -> None:
    findings = load("catalog_findings")
    rows = [
        {"pl_name": "X b", "pl_bmasse": 500.0, "pl_bmasselim": 1, "pl_bmassprov": "Mass", "pl_orbeccen": 0.0}
    ]
    row = {
        "pl_name": "X b",
        "pl_refname": "<a href=https://example.invalid target=ref>Someone et al. 2018</a>",
        "pl_msinie": "1.8",
        "pl_msinieerr1": "0.5",
        "pl_msinieerr2": "-0.6",
        "pl_orbeccen": "0.04",
        "pl_orbeccenlim": "1",
    }
    masses = findings.with_minimum_masses(rows, [row], "Someone")[0]
    assert (masses["pl_bmasse"], masses["pl_bmasselim"], masses["pl_bmassprov"]) == (1.8, 0, "Msini")
    limits = findings.with_eccentricity_limits(rows, [row], "Someone")[0]
    assert (limits["pl_orbeccen"], limits["pl_orbeccenlim"]) == (0.04, 1)
    assert rows[0]["pl_bmasse"] == 500.0  # the table itself is not changed
    with pytest.raises(SystemExit, match="no row for X b from Nobody"):
        findings.with_minimum_masses(rows, [row], "Nobody")


def test_catalog_findings_what_if_values() -> None:
    findings = load("catalog_findings")
    rows = [
        {"pl_bmasse": 10.0, "pl_bmasseerr1": 1.0, "pl_bmasseerr2": None, "pl_bmassprov": "Msini"},
        {"pl_bmasse": 20.0, "pl_bmasseerr1": 2.0, "pl_bmasseerr2": -2.0, "pl_bmassprov": "Mass"},
    ]
    larger = findings.with_larger_minimum_masses(rows, 2.0)
    assert (larger[0]["pl_bmasse"], larger[0]["pl_bmasseerr1"], larger[0]["pl_bmasseerr2"]) == (
        20.0,
        2.0,
        None,
    )
    assert larger[1] == rows[1] and rows[0]["pl_bmasse"] == 10.0
    measured = {"pl_orbeccen": 0.2, "pl_orbeccenerr1": 0.1, "pl_orbeccenerr2": -0.1, "pl_orbeccenlim": 1}
    fixed = findings.with_eccentricity([measured], 0.05)[0]
    assert (fixed["pl_orbeccen"], fixed["pl_orbeccenerr1"], fixed["pl_orbeccenlim"]) == (0.05, None, 0)
    assert findings.with_eccentricity([measured], None)[0]["pl_orbeccen"] is None
    assert measured["pl_orbeccen"] == 0.2


def test_catalog_findings_radial_gap() -> None:
    from exostab.sampling import Body, Realization

    findings = load("catalog_findings")

    def gap(pomega: float) -> tuple[float, float]:
        # a ~ P^(2/3): a = 1 and 1.3, apastron 1.2 of the inner orbit and periastron 1.04 of the outer one
        bodies = (
            Body(name="b", m=0.0, P=1.0, e=0.2, pomega=0.0, M=0.0),
            Body(name="c", m=0.0, P=1.3**1.5, e=0.2, pomega=pomega, M=0.0),
        )
        return tuple(findings.radial_gap(Realization("n", 1.0, bodies), 0))

    # the radial ranges overlap either way, but aligned ellipses never meet
    assert gap(0.0) == pytest.approx((-0.36, -0.24), abs=1e-3)
    # with opposite periastra the inner apastron lies outside the outer periastron, on the same side of the star
    assert gap(math.pi) == pytest.approx((-0.76, 0.16), abs=1e-3)


def test_social_preview_svg_path(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EXOSTAB_OFFLINE", "1")  # the script sets it on import; restored after the test
    preview = load("make_social_preview")
    from matplotlib.path import Path as MPath

    square = preview.svg_path("M0 0H1V1Z")
    assert square.vertices.tolist() == [[0, 0], [1, 0], [1, 1], [0, 0]]
    assert square.codes.tolist() == [MPath.MOVETO, MPath.LINETO, MPath.LINETO, MPath.CLOSEPOLY]
    # relative commands, implicit linetos after a moveto, a curve, and an offset
    shape = preview.svg_path("m1 1 1 0v1q0 1-1 1z", dx=10)
    assert shape.vertices.tolist() == [[11, 1], [12, 1], [12, 2], [12, 3], [11, 3], [11, 1]]
    assert shape.codes.tolist() == [
        MPath.MOVETO,
        MPath.LINETO,
        MPath.LINETO,
        MPath.CURVE3,
        MPath.CURVE3,
        MPath.CLOSEPOLY,
    ]


def test_release_notes(small_catalog: Path) -> None:
    notes = load("catalog_release_notes").notes(small_catalog)
    assert "4 multi-planet systems" in notes and "NASA Exoplanet Archive" in notes


def weekly_catalog(folder: Path, day: str, rows: dict[str, str], version: str = "1.0.0") -> None:
    """A file of archive/ on the branch: each system with its overall verdict or, without a verdict, its status."""
    draws = {"stable": (10, 0, 0), "marginal": (7, 3, 0), "unstable": (0, 0, 10), "inconclusive": (9, 0, 0)}
    columns = ["nbody_regular", "nbody_chaotic", "nbody_unstable"]
    fields = ["system", "status", "overall", *columns, "orbits", "draws", "seed"]
    fields += ["data_retrieved_utc", "exostab_version"]
    folder.mkdir(exist_ok=True)
    with (folder / f"catalog-{day}.csv").open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for system, state in rows.items():
            verdict = state in draws
            row = {
                "system": system,
                "status": "ok" if verdict else state,
                "overall": state if verdict else "",
                "orbits": "10000.0",
                "draws": "10",
                "seed": "0",
                "data_retrieved_utc": f"{day}T10:00:00+00:00",
                "exostab_version": version,
            }
            writer.writerow({**row, **(dict(zip(columns, draws[state])) if verdict else {})})


def atom_entries(text: str) -> list[ET.Element]:
    """The entries of a feed, after a check of what RFC 4287 requires of a feed and of its entries."""
    atom = "{http://www.w3.org/2005/Atom}"
    root = ET.fromstring(text)
    assert root.tag == f"{atom}feed" and root.findtext(f"{atom}author/{atom}name")
    assert root.find(f"{atom}link[@rel='self']") is not None
    entries = root.findall(f"{atom}entry")
    for element in (root, *entries):
        assert element.findtext(f"{atom}title")
        assert re.match(r"[a-z]+:", element.findtext(f"{atom}id", ""))  # an IRI, not a relative reference
        datetime.strptime(element.findtext(f"{atom}updated", ""), "%Y-%m-%dT%H:%M:%S%z")
    # with no atom:content, an entry needs a link to the alternate version
    assert all(e.find(f"{atom}link[@rel='alternate']") is not None for e in entries)
    assert all(e.findtext(f"{atom}summary") for e in entries)
    ids = [root.findtext(f"{atom}id"), *(e.findtext(f"{atom}id") for e in entries)]
    assert len(ids) == len(set(ids))
    return entries


def test_catalog_changes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    atom = "{http://www.w3.org/2005/Atom}"
    changes = load("catalog_changes")
    systems = tmp_path / "systems"
    systems.mkdir()
    monkeypatch.setattr(changes, "SYSTEMS", systems)
    tricky = 'A*B_c <x> & "q" [y]|z `1`'
    for name in ("hd-1", "hd-5", changes._row_id(tricky)):
        (systems / f"{name}.md").write_text("a page")
    archive = tmp_path / "archive"
    # Earlier rules: HD 1 would be a change, and HD 9 a removed system, if this catalog were compared.
    weekly_catalog(archive, "2026-10-05", {"HD 1": "unstable", "HD 9": "stable"}, version="0.1.0.dev0")
    older = {
        tricky: "stable",
        "HD 1": "stable",
        "HD 2": "marginal",
        "HD 3": "marginal",
        "HD 4": "unstable",
        "HD 6": "skipped",
        "HD 7": "stable",
        "HD 8": "skipped",
    }
    newer = {
        tricky: "inconclusive",
        "HD 1": "marginal",
        "HD 2": "unstable",
        "HD 3": "marginal",
        "HD 5": "stable",
        "HD 6": "marginal",
        "HD 7": "timeout",
        "HD 8": "timeout",
    }
    weekly_catalog(archive, "2026-10-12", older)
    weekly_catalog(archive, "2026-10-19", newer, version="1.0.2.dev0")
    (archive / "catalog.csv").write_text("not a dated file, so not read")
    catalogs = changes.read_archive(archive)
    assert [str(c.day) for c in catalogs] == ["2026-10-05", "2026-10-12", "2026-10-19"]
    [found] = changes.comparisons(catalogs)
    assert (found.added, found.removed) == (["HD 5"], ["HD 4"])
    assert found.changed == [tricky, "HD 1", "HD 2"]
    # HD 3 is the same in both, and HD 8 has no verdict in both, whatever its status
    assert (found.gained, found.lost) == (["HD 6"], ["HD 7"])

    page = changes.render(catalogs)
    assert "## 12 October 2026 to 19 October 2026 {#from-2026-10-12-to-2026-10-19}" in page
    assert "12 October 2026: exostab 1.0.0, 8 systems, 10,000 orbits, 10 draws, seed 0." in page
    assert "19 October 2026: exostab 1.0.2.dev0, 8 systems" in page
    for label, n in (
        ("Systems added", 1),
        ("Systems removed", 1),
        ("Overall verdicts changed", 3),
        ("Rows from no verdict to a verdict", 1),
        ("Rows from a verdict to no verdict", 1),
    ):
        assert f"<li>{label}: {n}\n<ul>" in page
    stable, marginal, unstable = (
        f'<span class="verdict-{v}">{v}</span>' for v in ("stable", "marginal", "unstable")
    )
    # old to new, as the rows say it, and a link only where a page exists
    assert (
        f'<li><a href="../systems/hd-1/">HD 1</a>: {stable} to {marginal} (draws 10/0/0 to 7/3/0)</li>'
        in page
    )
    assert f"<li>HD 2: {marginal} to {unstable} (draws 7/3/0 to 0/0/10)</li>" in page
    assert "newly" not in page.lower()
    assert f'<li><a href="../systems/hd-5/">HD 5</a>: {stable} (draws 10/0/0)</li>' in page
    assert f"<li>HD 4: {unstable} (draws 0/0/10)</li>" in page
    assert f"<li>HD 6: skipped to {marginal} (draws — to 7/3/0)</li>" in page
    assert f"<li>HD 7: {stable} to timeout (draws 10/0/0 to —)</li>" in page
    assert "HD 3" not in page and "HD 8" not in page
    # the catalog under earlier rules is named as left out, and compared with nothing
    assert "left out" in page and "5 October 2026 (exostab 0.1.0.dev0)" in page
    assert "from-2026-10-05" not in page and "HD 9" not in page
    # why a verdict can change, and what a change does not mean
    assert "The archive's values changed" in page and "The code changed" in page and "**Chance.**" in page
    assert "one draw can change" in page and "(findings.md#how-firm-these-numbers-are)" in page
    assert "says nothing about the planets" in page and "(catalog-changes.xml)" in page
    assert "With the same seed, values and code" in page and "wall-clock seconds" in page
    # a system added need not be new to the archive, a row need not name REBOUND, draws need not add up to 10
    assert "when the code changes which hosts get a row" in page
    assert "with a verdict, that of REBOUND" in page and "can add up to less than" in page

    # the name reaches the reader as it is: not as HTML, not as Markdown, and with a link of its own
    assert html.escape(tricky) in page and "<x>" not in page
    markdown = pytest.importorskip("markdown")
    rendered = markdown.markdown(page, extensions=["admonition", "attr_list"])
    assert 'id="from-2026-10-12-to-2026-10-19"' in rendered
    assert f'<a href="../systems/{changes._row_id(tricky)}/">{html.escape(tricky)}</a>' in rendered

    text = changes.feed(catalogs)
    [entry] = atom_entries(text)
    root = ET.fromstring(text)
    assert entry.findtext(f"{atom}updated") == "2026-10-19T10:00:00+00:00" == root.findtext(f"{atom}updated")
    # the URL readers subscribe to, and the ids, which must never change once they are published
    self_link = root.find(f"{atom}link[@rel='self']")
    assert (
        self_link is not None
        and self_link.get("href") == "https://mimitoz62.github.io/exostab/catalog-changes.xml"
    )
    assert root.findtext(f"{atom}id") == "tag:mimitoz62.github.io,2026:exostab/catalog-changes"
    assert (
        entry.findtext(f"{atom}id")
        == "tag:mimitoz62.github.io,2026:exostab/catalog-changes/from-2026-10-12-to-2026-10-19"
    )
    link = entry.find(f"{atom}link")
    assert link is not None and link.get("href") == f"{changes.PAGE}#from-2026-10-12-to-2026-10-19"
    assert entry.findtext(f"{atom}summary", "").startswith(
        "Systems added: 1. Systems removed: 1. Overall verdicts changed: 3. "
        "Rows from no verdict to a verdict: 1. Rows from a verdict to no verdict: 1. "
    )
    assert "not a discovery" in entry.findtext(f"{atom}summary", "")
    # a later build of the site changes nothing in the feed, so readers see no new entries
    assert changes.feed(changes.read_archive(archive)) == text
    # the entry's time comes from the file, so a second run on the same day changes it; if the time of the
    # download is not known, it is the file's date
    path = archive / "catalog-2026-10-19.csv"
    path.write_text(
        path.read_text(encoding="utf-8").replace("2026-10-19T10:00:00+00:00", ""), encoding="utf-8"
    )
    [entry] = atom_entries(changes.feed(changes.read_archive(archive)))
    assert entry.findtext(f"{atom}updated") == "2026-10-19T00:00:00Z"


def test_catalog_changes_keeps_the_newest_comparisons(tmp_path: Path) -> None:
    changes = load("catalog_changes")
    for day in range(1, 12):
        weekly_catalog(tmp_path, f"2026-11-{day:02d}", {"HD 1": "stable"})
    catalogs = changes.read_archive(tmp_path)
    found = changes.comparisons(catalogs)
    assert len(found) == changes.MAX_COMPARISONS == 8
    assert found[0].anchor == "from-2026-11-10-to-2026-11-11"
    assert found[-1].anchor == "from-2026-11-03-to-2026-11-04"
    assert changes.render(catalogs).count("\n## ") == 8 and len(atom_entries(changes.feed(catalogs))) == 8


def test_catalog_changes_with_nothing_to_compare(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    changes = load("catalog_changes")
    monkeypatch.setattr(changes, "OUT", tmp_path / "catalog-changes.md")
    monkeypatch.setattr(changes, "FEED", tmp_path / "catalog-changes.xml")
    # no archive at all: the page of the committed placeholder, whose build must not need the feed's file
    empty = tmp_path / "empty"
    empty.mkdir()
    (empty / "catalog-2026-10-19.csv").write_text("system,status,overall\n")  # no rows, so no catalog
    for folder in (None, tmp_path / "missing", empty):
        assert changes.read_archive(folder) == []
    placeholder = changes.render([])
    assert "has no comparisons" in placeholder and "catalog-changes.xml" not in placeholder
    assert placeholder.startswith("---\ntitle:") and "(findings.md#how-firm-these-numbers-are)" in placeholder
    assert atom_entries(changes.feed([])) == []
    monkeypatch.setattr("sys.argv", ["catalog_changes.py"])
    changes.main()
    assert (tmp_path / "catalog-changes.md").read_text(encoding="utf-8") == placeholder
    assert atom_entries((tmp_path / "catalog-changes.xml").read_text(encoding="utf-8")) == []
    # one catalog under the current rules, beside one under earlier rules: nothing to compare yet
    archive = tmp_path / "archive"
    weekly_catalog(archive, "2026-10-12", {"HD 1": "stable"}, version="0.1.0.dev0")
    weekly_catalog(archive, "2026-10-19", {"HD 1": "marginal"})
    catalogs = changes.read_archive(archive)
    assert changes.comparisons(catalogs) == [] and atom_entries(changes.feed(catalogs)) == []
    page = changes.render(catalogs)
    assert "no comparison yet" in page and "left out" in page and "has no comparisons" not in page
    monkeypatch.setattr("sys.argv", ["catalog_changes.py", str(archive)])
    changes.main()
    assert (tmp_path / "catalog-changes.md").read_text(encoding="utf-8") == page


@pytest.mark.skipif(not (ROOT / "mkdocs.yml").is_file(), reason="the site's files are not in the sdist")
def test_catalog_changes_are_part_of_the_site() -> None:
    assert "catalog-changes.md" in (ROOT / "mkdocs.yml").read_text(encoding="utf-8")
    head = (ROOT / "overrides" / "main.html").read_text(encoding="utf-8")
    assert re.search(r'<link rel="alternate" type="application/atom\+xml"[^>]*catalog-changes\.xml"', head)
    # the names on the page link to the system pages, so those are written first
    workflow = (ROOT / ".github" / "workflows" / "docs.yml").read_text(encoding="utf-8")
    assert workflow.index("scripts/system_pages.py") < workflow.index("scripts/catalog_changes.py archive")


class FakeResponse:
    def __init__(self, status: int, body: Any = None):
        self.status_code = status
        self._body = body or {}
        self.text = json.dumps(self._body)

    def json(self) -> Any:
        return self._body


class FakeSession:
    """Answers like Zenodo's legacy deposit API and records every call."""

    def __init__(self, fail_first: int = 0):
        self.headers: dict[str, str] = {}
        self.calls: list[tuple[str, str]] = []
        self.fail_first = fail_first

    def request(self, method: str, url: str, **kw: Any) -> FakeResponse:
        self.calls.append((method, url))
        if self.fail_first:
            self.fail_first -= 1
            return FakeResponse(503)
        z = "https://sandbox.zenodo.org"
        if method == "GET" and url == f"{z}/api/records/100":
            return FakeResponse(200, {"id": 105})
        if method == "POST" and url.endswith("/api/deposit/depositions/105/actions/newversion"):
            return FakeResponse(201, {"links": {"latest_draft": f"{z}/api/deposit/depositions/106"}})
        if method == "GET" and url.endswith("/depositions/106"):
            return FakeResponse(
                200,
                {
                    "id": 106,
                    "files": [{"id": "f1"}],
                    "metadata": {"title": "t", "version": "old"},
                    "links": {"bucket": f"{z}/api/files/b1"},
                },
            )
        if method == "DELETE":
            return FakeResponse(204)
        if method == "PUT" and "/api/files/b1/" in url:
            return FakeResponse(201)
        if method == "PUT" and url.endswith("/depositions/106"):
            assert json.loads(kw["data"])["metadata"]["version"] == "2026-09-28"
            return FakeResponse(200)
        if method == "POST" and url.endswith("/depositions/106/actions/publish"):
            return FakeResponse(202, {"doi_url": "https://doi.org/10.5072/zenodo.106"})
        return FakeResponse(404)


def test_zenodo_new_version_sequence(tmp_path: Path) -> None:
    z = load("zenodo_catalog")
    for f in ("catalog.csv", "catalog.parquet"):
        (tmp_path / f).write_text("x")
    (tmp_path / "catalog_meta.json").write_text(json.dumps({"created_utc": "2026-09-28T04:00:00+00:00"}))
    session = FakeSession(fail_first=1)
    client = z.Zenodo("https://sandbox.zenodo.org/", "TOKEN", session=session, pause=0)  # type: ignore[arg-type]
    published = z.publish_catalog(client, "100", tmp_path)
    assert published["doi_url"].endswith("106")
    assert session.headers["Authorization"] == "Bearer TOKEN"
    methods = [m for m, _ in session.calls]
    assert methods == ["GET", "GET", "POST", "GET", "DELETE", "PUT", "PUT", "PUT", "PUT", "POST"]


def test_zenodo_errors(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    z = load("zenodo_catalog")
    client = z.Zenodo("https://sandbox.zenodo.org", "T", session=FakeSession(), pause=0)  # type: ignore[arg-type]
    with pytest.raises(z.ZenodoError, match="HTTP 404"):
        client.latest_record_id("999")
    (tmp_path / "catalog_meta.json").write_text(json.dumps({"created_utc": "2026-09-28"}))
    with pytest.raises(z.ZenodoError, match="missing catalog files"):
        z.publish_catalog(client, "100", tmp_path)
    monkeypatch.delenv("ZENODO_TOKEN", raising=False)
    with pytest.raises(SystemExit):
        z.main()


class FakeIndexNow:
    """Stands in for urllib.request.urlopen: answers every request with one status and records it."""

    def __init__(self, status: int = 200, redirected_to: str = ""):
        self.status = status
        self.redirected_to = redirected_to
        self.requests: list[Any] = []

    def geturl(self) -> str:
        return self.redirected_to or self.requests[-1].full_url

    def __call__(self, request: Any, timeout: float) -> Any:
        self.requests.append(request)
        if self.status >= 400:
            raise urllib.error.HTTPError(
                request.full_url, self.status, "", Message(), io.BytesIO(b"key not in the file")
            )
        return contextlib.nullcontext(self)


def run_indexnow(
    fake: FakeIndexNow, urls: list[str], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """scripts/indexnow.py on a sitemap written the way mkdocs writes it, with no request reaching the network."""
    rows = "".join(f"    <url>\n         <loc>{url}</loc>\n    </url>\n" for url in urls)
    sitemap = tmp_path / "sitemap.xml"
    sitemap.write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        f'<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n{rows}</urlset>\n',
        encoding="utf-8",
    )
    monkeypatch.setattr("urllib.request.urlopen", fake)
    monkeypatch.setattr("sys.argv", ["indexnow.py", str(sitemap)])
    load("indexnow").main()


def test_indexnow_sends_the_sitemap_in_batches(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    site = "https://mimitoz62.github.io/exostab/"
    urls = [site, *(f"{site}systems/s{i}/" for i in range(10_000))]
    fake = FakeIndexNow()
    run_indexnow(fake, urls, tmp_path, monkeypatch)
    bodies = [json.loads(request.data) for request in fake.requests]
    assert [len(body["urlList"]) for body in bodies] == [10_000, 1]  # the protocol's limit for one POST
    assert [url for body in bodies for url in body["urlList"]] == urls
    for request, body in zip(fake.requests, bodies):
        assert request.full_url == "https://api.indexnow.org/indexnow" and request.get_method() == "POST"
        assert request.get_header("Content-type") == "application/json; charset=utf-8"
        assert set(body) == {"host", "key", "keyLocation", "urlList"}
        assert body["host"] == "mimitoz62.github.io" and re.fullmatch(r"[0-9a-f]{32}", body["key"])
        assert body["keyLocation"] == f"{site}{body['key']}.txt"  # the directory that every URL lies under
    assert "received 10,000 URLs (HTTP 200)" in capsys.readouterr().out


def test_indexnow_errors(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    site = "https://mimitoz62.github.io/exostab/"
    # 202 means received, with the key still to be validated
    run_indexnow(FakeIndexNow(202), [site], tmp_path, monkeypatch)
    assert "(HTTP 202)" in capsys.readouterr().out
    for status in (400, 403, 422, 429, 500):
        refused = FakeIndexNow(status)
        with pytest.raises(SystemExit, match=f"HTTP {status}: key not in the file"):
            run_indexnow(refused, [site], tmp_path, monkeypatch)
        assert len(refused.requests) == 1  # not retried
    # urllib follows a redirect with a GET that has no body, and a 204 is not one of the protocol's answers
    for fake, shown in (
        (FakeIndexNow(redirected_to="https://example.org/"), "from https://example.org/: not a receipt"),
        (FakeIndexNow(204), "HTTP 204 from https://api.indexnow.org/indexnow: not a receipt"),
    ):
        with pytest.raises(SystemExit, match=shown):
            run_indexnow(fake, [site], tmp_path, monkeypatch)
    assert "received" not in capsys.readouterr().out
    # a URL that the key does not cover, or no URL at all: nothing is sent
    unused = FakeIndexNow()
    for urls, message in (
        ([site, "https://mimitoz62.github.io/exostab-other/"], "exostab-other"),
        ([site, "https://example.org/exostab/"], "example.org"),
        ([], "No URLs"),
    ):
        with pytest.raises(SystemExit, match=message):
            run_indexnow(unused, urls, tmp_path, monkeypatch)
    assert unused.requests == []


@pytest.mark.skipif(not (ROOT / "mkdocs.yml").is_file(), reason="the site's sources are not in the sdist")
def test_indexnow_key_file_is_served_where_the_script_says() -> None:
    indexnow = load("indexnow")
    # mkdocs copies docs/ to the site's root, here /exostab/
    assert f"site_url: {indexnow.SITE}\n" in (ROOT / "mkdocs.yml").read_text(encoding="utf-8")
    # the protocol's FAQ asks that the file's text match the key exactly, so it has no final newline
    assert (ROOT / "docs" / f"{indexnow.KEY}.txt").read_bytes() == indexnow.KEY.encode("ascii")


def test_make_snapshot(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from exostab.data import load_rows

    snap = load("make_snapshot")
    rows, _ = load_rows(offline=True)
    monkeypatch.setattr(snap, "fetch_rows", lambda where: rows)
    monkeypatch.setattr(snap, "OUT", tmp_path)
    snap.main()
    meta = json.loads((tmp_path / "snapshot.json").read_text())
    assert meta["n_systems"] == len(snap.SYSTEMS) and meta["n_rows"] == len(rows)
    monkeypatch.setattr(snap, "SYSTEMS", ["Not-A-System"])
    with pytest.raises(SystemExit, match="not in the archive"):
        snap.main()


FAKE_UV = """#!/usr/bin/env bash
# Records its arguments; like uv 0.12, "uv venv" refuses an existing folder without --clear or UV_VENV_CLEAR=1.
echo "$*" >> "$UV_LOG"
if [[ "$1" == venv ]]; then
  target="${@: -1}"
  if [[ -e "$target" && "$*" != *--clear* && "${UV_VENV_CLEAR:-}" != 1 ]]; then
    echo "error: A virtual environment already exists at: $target" >&2
    exit 2
  fi
  rm -rf "$target" && mkdir -p "$target/bin" && touch "$target/pyvenv.cfg"
fi
"""


def run_spock_env(tmp_path: Path, target: Path) -> subprocess.CompletedProcess[str]:
    """scripts/make_spock_env.sh with a fake uv first on PATH (nothing is downloaded or built)."""
    bindir = tmp_path / "bin"
    bindir.mkdir(exist_ok=True)
    (bindir / "uv").write_text(FAKE_UV)
    (bindir / "uv").chmod(0o755)
    env = {
        **os.environ,
        "PATH": f"{bindir}{os.pathsep}{os.environ['PATH']}",
        "UV_LOG": str(tmp_path / "uv.log"),
    }
    script = ROOT / "scripts" / "make_spock_env.sh"
    return subprocess.run(
        ["bash", str(script), str(target)], env=env, capture_output=True, text=True, check=False
    )


@pytest.mark.skipif(shutil.which("bash") is None, reason="needs bash")
def test_spock_env_script_can_be_run_again(tmp_path: Path) -> None:
    target = tmp_path / "spock-env"
    for _ in range(2):  # a second run (after a failed source build, or to update) rebuilds the environment
        r = run_spock_env(tmp_path, target)
        assert r.returncode == 0, r.stderr
    calls = [line.split()[:2] for line in (tmp_path / "uv.log").read_text().splitlines()]
    assert calls == [["venv", "--python"], ["pip", "install"]] * 2
    assert f"EXOSTAB_SPOCK_PYTHON={target}/bin/python" in r.stdout


@pytest.mark.skipif(shutil.which("bash") is None, reason="needs bash")
def test_spock_env_script_leaves_other_folders_alone(tmp_path: Path) -> None:
    target = tmp_path / "notes"
    target.mkdir()
    (target / "keep.txt").write_text("not a virtual environment")
    r = run_spock_env(tmp_path, target)
    assert r.returncode == 1 and "is not a virtual environment" in r.stderr
    assert (target / "keep.txt").exists() and not (tmp_path / "uv.log").exists()
