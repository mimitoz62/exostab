"""Scripts: catalog page and findings, release notes, Zenodo upload, snapshot builder, SPOCK environment."""

from __future__ import annotations

import csv
import importlib.util
import json
import math
import os
import re
import shutil
import subprocess
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
    # the sidebar is hidden on this page, so this sentence is the way to the page about the results
    assert "[What the catalog shows](findings.md)" in text
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
    assert "[What the catalog shows](findings.md)" in placeholder
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
