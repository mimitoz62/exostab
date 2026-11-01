"""Archive client, completion rules, cache/snapshot store and name matching."""

from __future__ import annotations

import json
import os
import random
import socket
import threading
import warnings
from pathlib import Path
from typing import Any

import numpy as np
import pytest
from astropy.table import MaskedColumn, Table

from exostab.data import (
    IncompleteSystemError,
    SystemNotFoundError,
    archive,
    completion,
    list_systems,
    load_rows,
    load_system,
    names,
    store,
    system_from_rows,
)
from exostab.data.names import other_names
from exostab.data.store import TableInfo
from exostab.models import MassKind, PhaseKind, Provenance

INFO = TableInfo(kind="archive", retrieved_utc="2026-09-28T00:00:00+00:00", path=None)
REF_A = "<a refstr=A href=https://ui.adsabs.harvard.edu/abs/A/abstract target=ref>Alpha et al. 2020</a>"
REF_B = "<a refstr=B href=https://ui.adsabs.harvard.edu/abs/B/abstract target=ref>Beta et al. 2021</a>"
REF_C = "<a refstr=C href=https://ui.adsabs.harvard.edu/abs/C/abstract target=ref>Gamma et al. 2022</a>"


def row(name: str = "Host b", host: str = "Host", **kw: Any) -> dict[str, Any]:
    r: dict[str, Any] = dict.fromkeys(archive.COLUMN_NAMES)
    r.update(
        pl_name=name,
        hostname=host,
        pl_letter=name.split()[-1],
        sy_pnum=2,
        sy_snum=1,
        cb_flag=0,
        tran_flag=0,
        pl_orbper=10.0,
        pl_orbpererr1=0.01,
        pl_orbpererr2=-0.01,
        pl_orbper_reflink=REF_A,
        pl_orbeccen=0.1,
        pl_orbeccenerr1=0.02,
        pl_orbeccenerr2=-0.03,
        pl_orbeccenlim=0,
        pl_orbeccen_reflink=REF_A,
        pl_orblper=45.0,
        pl_orblper_reflink=REF_A,
        pl_bmasse=5.0,
        pl_bmasseerr1=0.5,
        pl_bmasseerr2=-0.5,
        pl_bmasselim=0,
        pl_bmassprov="Mass",
        pl_bmasse_reflink=REF_A,
        st_mass=1.0,
        st_masserr1=0.05,
        st_masserr2=-0.05,
        st_mass_reflink=REF_A,
    )
    r.update(kw)
    return r


def pair(**kw_c: Any) -> list[dict[str, Any]]:
    return [row("Host b"), row("Host c", **{"pl_orbper": 25.0, **kw_c})]


# ------------------------------------------------------------------------------------------ archive module


def test_parse_reflink() -> None:
    assert completion.parse_reflink(REF_A) == (
        "Alpha et al. 2020",
        "https://ui.adsabs.harvard.edu/abs/A/abstract",
    )
    assert completion.parse_reflink(None) == (None, None)
    assert completion.parse_reflink("Plain text") == ("Plain text", None)


def test_parse_reflink_unescapes_entities_and_resolves_relative_links() -> None:
    # Archive cells carry HTML entities, and archive-calculated values link to a page relative to the
    # archive site; report.json must hold plain text and links that work outside the archive.
    text, url = completion.parse_reflink(
        "<a refstr=X href=https://ui.adsabs.harvard.edu/abs/X/abstract target=ref>"
        "Su&aacute;rez Mascare&ntilde;o et al. 2025</a>"
    )
    assert text == "Suárez Mascareño et al. 2025"
    assert url == "https://ui.adsabs.harvard.edu/abs/X/abstract"
    assert completion.parse_reflink("<a href=x>Fulton &amp; Petigura 2018</a>")[0] == "Fulton & Petigura 2018"
    assert completion.parse_reflink("<a href=x>Kunovac Hod&#x17E;i&#x107; et al. 2021</a>")[0] == (
        "Kunovac Hodžić et al. 2021"
    )
    calc = "<a refstr=CALCULATED_VALUE href=/docs/pscp_calc.html target=_blank>Calculated Value</a>"
    assert completion.parse_reflink(calc) == (
        "Calculated Value",
        "https://exoplanetarchive.ipac.caltech.edu/docs/pscp_calc.html",
    )


def test_csv_roundtrip(tmp_path: Path) -> None:
    rows = pair()
    archive.write_csv(rows, tmp_path / "t.csv")
    back = archive.read_csv(tmp_path / "t.csv")
    assert back == rows


def test_read_csv_rejects_missing_columns(tmp_path: Path) -> None:
    (tmp_path / "bad.csv").write_text("pl_name,hostname\nx,y\n")
    with pytest.raises(archive.ArchiveError, match="lacks columns"):
        archive.read_csv(tmp_path / "bad.csv")


def test_rows_from_astropy_table_handles_masks_and_units() -> None:
    import astropy.units as u

    rows = pair()
    t = Table()
    for c, kind in archive.COLUMNS:
        vals = [r[c] for r in rows]
        if kind == "str":
            t[c] = MaskedColumn([v or "" for v in vals], mask=[v is None for v in vals])
        else:
            t[c] = MaskedColumn([np.nan if v is None else v for v in vals], mask=[v is None for v in vals])
    t["pl_orbper"].unit = u.day
    out = archive.rows_from_table(t)
    assert out[0]["pl_orbper"] == 10.0
    assert out[0]["pl_tranmid"] is None
    assert out[0]["sy_pnum"] == 2
    assert out[1]["pl_name"] == "Host c"
    with pytest.raises(archive.ArchiveError):
        archive.rows_from_table(Table({"pl_name": ["x"]}))


def test_clean_values() -> None:
    import astropy.units as u

    assert archive._clean(3 * u.day, "float") == 3.0
    assert archive._clean("  ", "str") is None
    assert archive._clean("abc", "float") is None
    assert archive._clean(float("nan"), "float") is None
    assert archive._clean(2.0, "int") == 2


@pytest.mark.parametrize("cell", ["inf", "-inf", "1e999", float("inf")])
@pytest.mark.parametrize("kind", ["float", "int"])
def test_a_non_finite_cell_is_missing(cell: Any, kind: str) -> None:
    # An infinite time or angle became a NaN phase, which stopped every run at once and gave overall UNSTABLE, and
    # inf in an integer column gave an OverflowError.
    assert archive._clean(cell, kind) is None


def test_fetch_rows_retries_then_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    from astroquery.ipac.nexsci.nasa_exoplanet_archive import NasaExoplanetArchive

    calls = []

    def boom(**kw: Any) -> None:
        calls.append(kw)
        raise ConnectionError("no network")

    monkeypatch.setattr(NasaExoplanetArchive, "query_criteria", boom)
    with pytest.raises(archive.ArchiveError, match="no network"):
        archive.fetch_rows(attempts=2, pause=0.0)
    assert len(calls) == 2
    assert calls[0]["table"] == "pscomppars"


def test_fetch_rows_refuses_a_result_the_service_reports_as_cut(monkeypatch: pytest.MonkeyPatch) -> None:
    # QUERY_STATUS=OVERFLOW is only a warning in pyvo: the 16 rows that came replaced the good cache.
    from astroquery.ipac.nexsci.nasa_exoplanet_archive import NasaExoplanetArchive
    from pyvo.dal.exceptions import DALOverflowWarning

    def cut(**kw: Any) -> Table:
        warnings.warn("Result set limited", category=DALOverflowWarning, stacklevel=2)
        return Table()

    monkeypatch.setattr(NasaExoplanetArchive, "query_criteria", cut)
    with pytest.raises(archive.ArchiveError, match="Result set limited"):
        archive.fetch_rows(attempts=1)


def test_fetch_rows_gives_up_on_a_stalled_connection(monkeypatch: pytest.MonkeyPatch) -> None:
    # A server that accepts the query and never answers: `exostab list` waited for ever, in silence.
    from astroquery.ipac.nexsci.nasa_exoplanet_archive import NasaExoplanetArchive

    with socket.socket() as server:
        server.bind(("127.0.0.1", 0))
        server.listen()
        monkeypatch.setattr(
            NasaExoplanetArchive, "URL_TAP", f"http://127.0.0.1:{server.getsockname()[1]}/TAP"
        )
        monkeypatch.setattr(archive, "READ_TIMEOUT_S", 0.5)
        errors: list[Exception] = []

        def fetch() -> None:
            try:
                archive.fetch_rows(attempts=1)
            except archive.ArchiveError as exc:
                errors.append(exc)

        thread = threading.Thread(target=fetch, daemon=True)
        thread.start()
        thread.join(timeout=30)
        assert not thread.is_alive(), "still waiting after 30 s"
    assert errors and "could not query" in str(errors[0])


# ------------------------------------------------------------------------------------------ completion rules


def rules(rows: list[dict[str, Any]]) -> set[str]:
    return {f.rule for f in system_from_rows(rows, INFO).flags}


def test_complete_system_basic() -> None:
    s = system_from_rows(pair(), INFO)
    assert [p.name for p in s.planets] == ["Host b", "Host c"]
    b = s.planets[0]
    assert b.period_days.reference == "Alpha et al. 2020"
    assert b.eccentricity.err_minus == 0.03
    assert b.archive_name == "Host b"
    assert s.source.table == "pscomppars"
    assert "coplanar_assumed" in rules(pair())


def test_missing_eccentricity_and_omega() -> None:
    s = system_from_rows(pair(pl_orbeccen=None, pl_orblper=None), INFO)
    c = s.planets[1]
    assert c.eccentricity.value == 0.0 and c.eccentricity.provenance is Provenance.ASSUMED
    assert c.omega_deg.provenance is Provenance.RANDOMIZED
    assert {"eccentricity_assumed_zero", "omega_randomized"} <= {f.rule for f in s.flags}


def test_published_zero_eccentricity_without_errors_is_an_assumption() -> None:
    # e = 0 with no uncertainty is a circular orbit fixed in the source's fit (e.g. the DR25 KOI table),
    # not a measurement: it must be labelled and flagged like exostab's own e = 0 assumption.
    fixed = {
        "pl_orbeccen": 0.0,
        "pl_orbeccenerr1": None,
        "pl_orbeccenerr2": None,
        "pl_orbeccen_reflink": REF_B,
    }
    s = system_from_rows(pair(**fixed), INFO)
    c = s.planets[1]
    assert c.eccentricity.value == 0.0 and c.eccentricity.provenance is Provenance.ASSUMED
    assert c.eccentricity.reference == "Beta et al. 2021"
    flag = next(f for f in s.flags if f.rule == "eccentricity_fixed_zero_by_source")
    assert flag.planet == "Host c" and "Beta et al. 2021" in flag.message
    # zero error bars are no uncertainty either
    s = system_from_rows(pair(**{**fixed, "pl_orbeccenerr1": 0.0, "pl_orbeccenerr2": 0.0}), INFO)
    assert s.planets[1].eccentricity.provenance is Provenance.ASSUMED
    # a zero eccentricity with an error bar is a measurement
    s = system_from_rows(pair(pl_orbeccen=0.0, pl_orbeccenerr1=0.05, pl_orbeccenerr2=0.0), INFO)
    assert s.planets[1].eccentricity.provenance is Provenance.MEASURED
    assert "eccentricity_fixed_zero_by_source" not in {f.rule for f in s.flags}


def test_limits() -> None:
    s = system_from_rows(pair(pl_orbeccenlim=1, pl_bmasselim=1), INFO)
    c = s.planets[1]
    assert c.eccentricity.provenance is Provenance.UPPER_LIMIT
    assert c.mass_earth.provenance is Provenance.UPPER_LIMIT
    r = rules(pair(pl_orbeccenlim=-1, pl_bmasselim=-1, pl_orbperlim=-1))
    assert {"eccentricity_lower_limit", "mass_lower_limit", "period_lower_limit"} <= r


def test_bad_eccentricity_rejected() -> None:
    with pytest.raises(IncompleteSystemError, match="outside"):
        system_from_rows(pair(pl_orbeccen=1.2), INFO)
    # above the 0.95 cap the runs would silently use 0.95 while the report showed the published value
    with pytest.raises(IncompleteSystemError, match=r"above 0\.95"):
        system_from_rows(pair(pl_orbeccen=0.97), INFO)
    with pytest.raises(IncompleteSystemError, match=r"above 0\.95"):
        system_from_rows(pair(pl_orbeccen=0.97, pl_orbeccenlim=1), INFO)
    assert system_from_rows(pair(pl_orbeccen=0.95), INFO).planets[1].eccentricity.value == 0.95


@pytest.mark.parametrize(
    ("prov", "kind", "rule"),
    [
        ("Mass", MassKind.TRUE, None),
        ("Msini", MassKind.MINIMUM, "minimum_mass"),
        ("M-R relationship", MassKind.ESTIMATED, "mass_estimated_by_archive"),
        ("Msin(i)/sin(i)", MassKind.TRUE, "mass_from_msini_and_inclination"),
    ],
)
def test_mass_provenance(prov: str, kind: MassKind, rule: str | None) -> None:
    s = system_from_rows(pair(pl_bmassprov=prov), INFO)
    assert s.planets[1].mass_kind is kind
    if rule:
        assert rule in {f.rule for f in s.flags}


def test_mass_kind_uses_transit_and_limit_flags() -> None:
    # A transiting planet has i close to 90 deg, so its archive "Msini" is its mass (Kepler-9 d:
    # i = 89.38 deg); it must not be called a minimum mass or be scaled by the inclination prior while its
    # siblings are not.
    s = system_from_rows(pair(pl_bmassprov="Msini", tran_flag=1, pl_orbincl=89.38), INFO)
    assert s.planets[1].mass_kind is MassKind.TRUE
    c_flags = {f.rule: f.message for f in s.flags if f.planet == "Host c"}
    assert "minimum_mass" not in c_flags and "89.38" in c_flags["msini_of_transiting_planet"]
    # A lower limit on the mass of a non-transiting planet is an m sin i with unknown inclination
    # (HD 219134 d and f); it is a minimum mass for the inclination prior, like its "Msini" siblings.
    s = system_from_rows(pair(pl_bmasselim=-1), INFO)
    assert s.planets[1].mass_kind is MassKind.MINIMUM
    assert any(f.rule == "mass_lower_limit" and "minimum mass" in f.message for f in s.flags)
    assert system_from_rows(pair(pl_bmasselim=-1, tran_flag=1), INFO).planets[1].mass_kind is MassKind.TRUE
    # `exostab list` counts minimum masses by the same rule
    rows = [row("Host b", pl_bmasselim=-1), row("Host c", pl_orbper=25.0, pl_bmassprov="Msini", tran_flag=1)]
    assert list_systems(rows)[0].minimum_masses == 1


def test_archive_calculated_value_provenance() -> None:
    # The archive cell for a value it computed itself (pscp_calc.html). A radius is filled from the
    # Chen & Kipping mass-radius relation ("estimated"); any other column is computed from measured
    # quantities ("derived"). HD 127195 b and c in the snapshot are this kind of radius.
    calc = "<a refstr=CALCULATED_VALUE href=/docs/pscp_calc.html target=_blank>Calculated Value</a>"
    s = system_from_rows(
        pair(
            pl_bmassprov="Msini",
            pl_rade=14.0,
            pl_rade_reflink=calc,
            pl_orbsmax=1.25,
            pl_orbsmax_reflink=calc,
        ),
        INFO,
    )
    c = s.planets[1]
    assert c.radius_earth is not None and c.semimajor_axis_au is not None
    assert c.radius_earth.value == 14.0
    assert c.radius_earth.provenance is Provenance.ESTIMATED
    assert c.radius_earth.reference == "Calculated Value"
    assert c.radius_earth.reference_url == "https://exoplanetarchive.ipac.caltech.edu/docs/pscp_calc.html"
    assert c.radius_earth.err_plus is None and c.radius_earth.err_minus is None
    assert c.semimajor_axis_au.provenance is Provenance.DERIVED
    assert c.semimajor_axis_au.reference == "Calculated Value"
    # the published mass is untouched: these radii never feed the Chen & Kipping mass
    assert c.mass_kind is MassKind.MINIMUM and c.mass_earth.provenance is Provenance.MEASURED
    published = system_from_rows(
        pair(pl_rade=1.2, pl_radeerr1=0.1, pl_radeerr2=-0.1, pl_rade_reflink=REF_B), INFO
    )
    assert published.planets[1].radius_earth is not None
    assert published.planets[1].radius_earth.provenance is Provenance.MEASURED
    # the rule lives in _value, so it covers columns the planet builder does not special-case
    r = row("Host b")
    r.update(pl_radj=1.1, pl_radj_reflink=calc, pl_orbincl=89.0, pl_orbincl_reflink=calc)
    assert completion._value(r, "pl_radj").provenance is Provenance.ESTIMATED
    assert completion._value(r, "pl_bmasse").provenance is Provenance.MEASURED  # literature reference
    assert completion._value(r, "pl_orbincl").provenance is Provenance.DERIVED
    assert completion._value({"pl_bmassj": 1.0, "pl_bmassj_reflink": calc}, "pl_bmassj").provenance is (
        Provenance.ESTIMATED
    )
    hd = load_system("HD 127195")
    calculated = [p for p in hd.planets if p.radius_earth and p.radius_earth.reference == "Calculated Value"]
    assert [p.name for p in calculated] == ["HD 127195 b", "HD 127195 c"]
    assert all(
        p.radius_earth is not None and p.radius_earth.provenance is Provenance.ESTIMATED for p in calculated
    )


def test_mass_from_radius_and_failures() -> None:
    s = system_from_rows(pair(pl_bmasse=None, pl_rade=2.0), INFO)
    assert s.planets[1].mass_kind is MassKind.ESTIMATED
    assert s.planets[1].mass_earth.value == pytest.approx(4.4, abs=0.3)
    with pytest.raises(IncompleteSystemError, match="giant-planet"):
        system_from_rows(pair(pl_bmasse=None, pl_rade=13.0), INFO)
    with pytest.raises(IncompleteSystemError, match="neither a mass nor a radius"):
        system_from_rows(pair(pl_bmasse=None, pl_rade=None), INFO)


def test_period_from_semimajor_axis() -> None:
    s = system_from_rows(
        pair(pl_orbper=None, pl_orbsmax=0.2, pl_orbsmaxerr1=0.01, pl_orbsmaxerr2=-0.01), INFO
    )
    c = s.planets[1]
    assert c.period_days.provenance is Provenance.DERIVED
    assert c.period_days.value == pytest.approx(0.2**1.5 * 365.25, rel=1e-3)
    assert c.period_days.err_plus == pytest.approx(1.5 * 0.05 * c.period_days.value)
    with pytest.raises(IncompleteSystemError, match="semi-major axis"):
        system_from_rows(pair(pl_orbper=None, pl_orbsmax=None), INFO)


@pytest.mark.parametrize("method", ["Microlensing", "Imaging"])
def test_no_period_from_a_projected_separation(method: str) -> None:
    # For microlensing and directly imaged planets the archive's pl_orbsmax can be the projected separation
    # on the sky, which gives neither the orbit nor the spacing of the planets.
    with pytest.raises(IncompleteSystemError, match="projected separation"):
        system_from_rows(pair(pl_orbper=None, pl_orbsmax=2.77, discoverymethod=method), INFO)
    # with a published period the planet is placed as usual
    s = system_from_rows(pair(pl_orbsmax=2.77, discoverymethod=method), INFO)
    assert s.planets[1].period_days.provenance is Provenance.MEASURED


def test_star_rules() -> None:
    with pytest.raises(IncompleteSystemError, match="circumbinary"):
        system_from_rows(pair(cb_flag=1), INFO)
    with pytest.raises(IncompleteSystemError, match="stellar mass"):
        system_from_rows([row("Host b", st_mass=None), row("Host c", pl_orbper=25.0, st_mass=None)], INFO)
    assert "companion_stars_ignored" in rules([row("Host b", sy_snum=2), row("Host c", pl_orbper=25.0)])
    with pytest.raises(IncompleteSystemError, match="only one planet"):
        system_from_rows([row("Host b")], INFO)


@pytest.mark.parametrize("lim", [1, -1])
def test_stellar_mass_limits_are_not_used(lim: int) -> None:
    # An upper limit used to be drawn uniformly between 0 and the limit (masses near 0, the planet-to-star
    # mass ratios inflated many times) under a flag saying "the limit is used". A limit is not a stellar mass.
    with pytest.raises(IncompleteSystemError, match="only a limit on the stellar mass"):
        system_from_rows([row("Host b", st_masslim=lim), row("Host c", pl_orbper=25.0, st_masslim=lim)], INFO)
    # a measured value in another row is used, and the ignored limit is reported
    s = system_from_rows([row("Host b", st_mass=0.6, st_masslim=lim), row("Host c", pl_orbper=25.0)], INFO)
    assert s.star.mass_msun.value == 1.0 and s.star.mass_msun.provenance is Provenance.MEASURED
    flag = next(f for f in s.flags if f.rule == "star_mass_limit_ignored")
    assert "Host b" in flag.message


def _kepler114_like() -> list[dict[str, Any]]:
    # Kepler-114 in the archive: b's row has M* = 0.77 (Morton et al. 2016), c's and d's rows 0.56 (Xie 2014,
    # also the source of their TTV masses). exostab used whichever row came first.
    morton = {"st_mass": 0.77, "st_masserr1": 0.02, "st_masserr2": -0.022, "st_mass_reflink": REF_A}
    xie = {"st_mass": 0.56, "st_masserr1": 0.06, "st_masserr2": -0.06, "st_mass_reflink": REF_B}
    return [
        row("Host b", pl_orbper=5.2, **morton),
        row("Host c", pl_orbper=8.0, pl_bmasse_reflink=REF_B, **xie),
        row("Host d", pl_orbper=11.8, pl_bmasse_reflink=REF_B, **xie),
    ]


def test_stellar_mass_is_the_median_of_the_rows_whatever_their_order() -> None:
    rows = _kepler114_like()
    for k in range(len(rows)):
        s = system_from_rows(rows[k:] + rows[:k], INFO)
        assert s.star.mass_msun.value == 0.56
        assert s.star.mass_msun.reference == "Beta et al. 2021"
        assert s.star.mass_msun.err_plus == 0.06
        flag = next(f for f in s.flags if f.rule == "star_mass_inconsistent")
        assert flag.planet is None
        assert "0.77" in flag.message and "Alpha et al. 2020" in flag.message
        assert "0.56" in flag.message and "Host c, Host d" in flag.message
    # an even number of rows: the lower of the two middle values (the less stable choice)
    two = [row("Host b", st_mass=1.0), row("Host c", pl_orbper=25.0, st_mass=0.9)]
    assert system_from_rows(two, INFO).star.mass_msun.value == 0.9
    assert system_from_rows(two[::-1], INFO).star.mass_msun.value == 0.9
    assert any("lower of the two middle values" in f.message for f in system_from_rows(two, INFO).flags)
    # ... which is only said when the two middle values differ
    four = [*rows, {**rows[1], "pl_name": "Host e", "pl_letter": "e", "pl_orbper": 15.0}]  # 0.56 x 3, 0.77
    assert not any("lower of the two" in f.message for f in system_from_rows(four, INFO).flags)
    # rows that agree raise no flag; a row without a stellar mass is skipped
    assert "star_mass_inconsistent" not in rules(pair())
    s = system_from_rows([row("Host b", st_mass=None), row("Host c", pl_orbper=25.0, st_mass=0.8)], INFO)
    assert s.star.mass_msun.value == 0.8
    # `exostab list` shows the same stellar mass
    assert list_systems(rows)[0].star_mass_msun == 0.56


def test_stellar_mass_of_the_publication_of_the_measured_masses() -> None:
    """Kepler-968: the only measured mass (TTV, Jontof-Hutter et al. 2021, M* = 0.681) was divided by the median
    0.76 of the two rows whose masses come from the mass-radius relation (Morton et al. 2016)."""
    estimated = {"pl_bmassprov": "M-R relationship", "st_mass": 0.76, "st_mass_reflink": REF_A}
    rows = [
        row("Host b", pl_orbper=5.7, **estimated),
        row("Host c", pl_orbper=8.0, **estimated),
        row("Host d", pl_orbper=12.0, pl_bmasse_reflink=REF_B, st_mass=0.681, st_mass_reflink=REF_B),
    ]
    for k in range(len(rows)):
        s = system_from_rows(rows[k:] + rows[:k], INFO)
        assert s.star.mass_msun.value == 0.681 and s.star.mass_msun.reference == "Beta et al. 2021"
        flag = next(f for f in s.flags if f.rule == "star_mass_inconsistent")
        assert "the publication of the measured masses of Host d" in flag.message
        assert "0.76" in flag.message and "median" not in flag.message
    assert list_systems(rows)[0].star_mass_msun == 0.681
    # a tie (HD 116029: one mass from each publication): the median rule, lower middle value
    tie = [
        row("Host b", pl_bmasse_reflink=REF_B, st_mass=0.83, st_mass_reflink=REF_B),
        row("Host c", pl_orbper=25.0, st_mass=1.33),
    ]
    s = system_from_rows(tie, INFO)
    assert s.star.mass_msun.value == 0.83
    assert any("the median of the rows (the lower of the two middle values" in f.message for f in s.flags)
    assert system_from_rows(tie[::-1], INFO).star.mass_msun.value == 0.83
    # the publication of most masses gives no stellar mass of its own in the table: the median rule
    other = [
        row("Host b", pl_bmasse_reflink=REF_B, st_mass=1.1),
        row("Host c", pl_orbper=25.0, pl_bmasse_reflink=REF_B, st_mass=0.9),
        row("Host d", pl_orbper=60.0, st_mass=1.0),
    ]
    assert system_from_rows(other, INFO).star.mass_msun.value == 1.0
    # AU Mic: two of four masses from one publication, one each from two others: that publication's value
    au_mic = [
        row("Host b", st_mass=0.635),
        row("Host c", pl_orbper=18.9, st_mass=0.635),
        row("Host d", pl_orbper=12.7, pl_bmasse_reflink=REF_B, st_mass=0.51, st_mass_reflink=REF_B),
        row("Host e", pl_orbper=33.4, pl_bmasse_reflink=REF_C, st_mass=0.6, st_mass_reflink=REF_C),
    ]
    assert system_from_rows(au_mic, INFO).star.mass_msun.value == 0.635


def test_the_flag_says_when_only_the_sources_of_one_stellar_mass_differ() -> None:
    # HAT-P-2: "The planet rows give different stellar masses" followed by the same value twice.
    same = [row("Host b"), row("Host c", pl_orbper=25.0, st_mass_reflink=REF_B)]
    flag = next(f for f in system_from_rows(same, INFO).flags if f.rule == "star_mass_inconsistent")
    assert "one stellar mass with different errors or sources" in flag.message
    assert "different stellar masses" not in flag.message
    other = [row("Host b"), row("Host c", pl_orbper=25.0, st_mass=0.5, st_mass_reflink=REF_B)]
    flag = next(f for f in system_from_rows(other, INFO).flags if f.rule == "star_mass_inconsistent")
    assert "different stellar masses" in flag.message


@pytest.mark.parametrize(
    ("kw", "match"),
    [
        ({"pl_bmasse": 0.0}, r"Host c: the archive's mass \(pl_bmasse\) is 0"),
        ({"pl_bmasse": -3.0}, r"Host c: the archive's mass \(pl_bmasse\) is -3"),
        ({"pl_orbper": 0.0}, r"Host c: the archive's orbital period \(pl_orbper\) is 0"),
        ({"pl_orbper": -5.0}, r"Host c: the archive's orbital period \(pl_orbper\) is -5"),
        ({"pl_orbper": None, "pl_orbsmax": 0.0}, r"\(pl_orbsmax\) is 0"),
        ({"pl_orbper": None, "pl_orbsmax": -1.0}, r"\(pl_orbsmax\) is -1"),
        ({"pl_bmasse": None, "pl_rade": -1.0}, r"\(pl_rade\) is -1"),
    ],
)
def test_impossible_cells_are_rejected_with_planet_and_column(kw: dict[str, Any], match: str) -> None:
    # A pydantic traceback, a ZeroDivisionError or "math domain error", and a pydantic dump as a catalog's reason.
    with pytest.raises(IncompleteSystemError, match=match):
        system_from_rows(pair(**kw), INFO)


def test_an_impossible_stellar_mass_is_rejected() -> None:
    rows = [row("Host b", st_mass=0.0), row("Host c", pl_orbper=25.0, st_mass=0.0)]
    with pytest.raises(IncompleteSystemError, match=r"Host: the archive's stellar mass \(st_mass\) is 0"):
        system_from_rows(rows, INFO)


@pytest.mark.parametrize(
    ("value", "said"), [("M-R Relationship", "gives 'M-R Relationship'"), (None, "says nothing")]
)
def test_an_unknown_mass_kind_is_flagged_and_stays_true(value: str | None, said: str) -> None:
    # 1,179 of 2,663 rows depend on the exact spelling of pl_bmassprov, which the archive does not document (D18).
    s = system_from_rows(pair(pl_bmassprov=value), INFO)
    assert (
        s.planets[1].mass_kind is MassKind.TRUE and s.planets[1].mass_earth.provenance is Provenance.MEASURED
    )
    flag = next(f for f in s.flags if f.rule == "mass_kind_unknown")
    assert flag.planet == "Host c" and said in flag.message
    assert "mass_kind_unknown" not in rules(pair())


def test_the_reason_for_a_rejection_does_not_depend_on_the_row_order() -> None:
    # The archive returns rows in no fixed order, and catalog.csv and the system pages show this text.
    rows = [
        row("Host a", pl_bmasse=None),
        row("Host b", pl_orbper=None),
        row("Host c", pl_orbper=25.0),
    ]
    reasons = set()
    for seed in range(12):
        shuffled = random.Random(seed).sample(rows, len(rows))
        with pytest.raises(IncompleteSystemError) as err:
            system_from_rows(shuffled, INFO)
        reasons.add(str(err.value))
    assert len(reasons) == 1


def test_the_flags_of_an_accepted_system_keep_the_row_order() -> None:
    s = system_from_rows(list(reversed(pair(pl_orbeccen=None))), INFO)
    assert [p.name for p in s.planets] == ["Host b", "Host c"]
    assert next(f.planet for f in s.flags if f.rule == "eccentricity_assumed_zero") == "Host c"


def test_messages_do_not_assume_the_command_line() -> None:
    # The same text reaches the web app, and a report downloaded from it.
    s = system_from_rows(pair(pl_bmassprov="Msini"), INFO)
    assert "an inclination prior" in next(f.message for f in s.flags if f.rule == "minimum_mass")
    s = system_from_rows(pair(pl_bmassprov="Msini", tran_flag=1), INFO)
    s2 = system_from_rows(pair(pl_bmasselim=-1), INFO)
    for f in (*s.flags, *s2.flags):
        assert "--" not in f.message
    no_star = [row("Host b", st_mass=None), row("Host c", pl_orbper=25.0, st_mass=None)]
    limit = [row("Host b", st_masslim=1), row("Host c", pl_orbper=25.0, st_masslim=1)]
    imaged = pair(pl_orbper=None, pl_orbsmax=5.0, discoverymethod="Imaging")
    for rows in (no_star, limit, imaged):
        with pytest.raises(IncompleteSystemError) as err:
            system_from_rows(rows, INFO)
        assert "--" not in str(err.value) and "YAML system file" in str(err.value)


def test_a_reference_time_far_from_the_epoch_is_flagged() -> None:
    # HD 11964 c and HD 4203 c, from a time of periastron: the phase is uncertain by many turns at the common epoch,
    # while the card says "periastron". A flag, with the numbers unchanged.
    def far(reference: float) -> list[dict[str, Any]]:
        return [
            row("Host b", tran_flag=1, pl_tranmid=2455000.0, pl_tranmiderr1=1e-3, pl_tranmiderr2=-1e-3),
            row(
                "Host c",
                pl_orbper=25.0,
                pl_orbpererr1=0.01,
                pl_orbpererr2=-0.01,
                tran_flag=1,
                pl_tranmid=reference,
                pl_tranmiderr1=1e-3,
                pl_tranmiderr2=-1e-3,
            ),
        ]

    s = system_from_rows(far(5000.0), INFO)
    flagged = [f for f in s.flags if f.rule == "phase_uncertain_at_epoch"]
    assert len(flagged) == 1 and "full turns" in flagged[0].message
    assert "phase_uncertain_at_epoch" not in {f.rule for f in system_from_rows(far(2455010.0), INFO).flags}


@pytest.mark.parametrize(
    "rule",
    ["mass_kind_unknown", "phase_uncertain_at_epoch", "planet_rows_missing", "phase_random_without_omega"],
)
def test_new_flags_are_documented(rule: str) -> None:
    # docs/data-assumptions.md says that its table lists every flag exostab can set.
    page = Path(__file__).resolve().parents[1] / "docs" / "data-assumptions.md"
    if not page.is_file():
        pytest.skip("this page is not in the sdist")
    assert f"`{rule}`" in page.read_text(encoding="utf-8")


def test_controversial_flag() -> None:
    assert "controversial_planet" in rules(pair(pl_controv_flag=1))


def test_phase_rules() -> None:
    # transiting: always from the transit time, noting a different reference
    s = system_from_rows(pair(tran_flag=1, pl_tranmid=2460000.0, pl_tranmid_reflink=REF_B), INFO)
    assert s.planets[1].phase.kind is PhaseKind.TRANSIT
    assert any("different publications" in f.message for f in s.flags)
    # non-transiting conjunction time: only from the same publication as the period
    s = system_from_rows(pair(pl_tranmid=2460000.0, pl_tranmid_reflink=REF_A), INFO)
    assert s.planets[1].phase.kind is PhaseKind.TRANSIT
    assert "phase_from_conjunction" in {f.rule for f in s.flags}
    s = system_from_rows(pair(pl_tranmid=2460000.0, pl_tranmid_reflink=REF_B), INFO)
    assert s.planets[1].phase.kind is PhaseKind.RANDOM
    assert any("different publication" in f.message for f in s.flags)
    # periastron time from the same publication
    s = system_from_rows(pair(pl_orbtper=2460001.0, pl_orbtper_reflink=REF_A), INFO)
    assert s.planets[1].phase.kind is PhaseKind.PERIASTRON
    # ... but without the argument of periastron the periastron direction, and so the planet's longitude, is
    # random in every run: the phase is random and the report must say so
    s = system_from_rows(pair(pl_orbtper=2460001.0, pl_orbtper_reflink=REF_A, pl_orblper=None), INFO)
    assert s.planets[1].phase.kind is PhaseKind.RANDOM
    c_rules = {f.rule for f in s.flags if f.planet == "Host c"}
    assert "phase_randomized" in c_rules and "phase_from_periastron" not in c_rules
    assert any(f.planet == "Host c" and "argument of periastron" in f.message for f in s.flags)
    # identical periastron times across planets are treated as an epoch, not a periastron time
    rows = [
        row("Host b", pl_orbtper=2450602.093, pl_orbtper_reflink=REF_A),
        row("Host c", pl_orbper=25.0, pl_orbtper=2450602.093, pl_orbtper_reflink=REF_A),
    ]
    s = system_from_rows(rows, INFO)
    assert all(p.phase.kind is PhaseKind.RANDOM for p in s.planets)
    assert any("likely an epoch" in f.message for f in s.flags)
    # nothing published
    s = system_from_rows(pair(), INFO)
    assert any("no transit, conjunction or periastron time" in f.message for f in s.flags)


# ------------------------------------------------------------------------------------------ store and names


def test_snapshot_loads_and_has_validation_systems() -> None:
    rows, info = load_rows()
    assert info.kind == "snapshot"
    hosts = archive.group_by_host(rows)
    for h in ("TRAPPIST-1", "HD 127195", "GJ 876", "Kepler-11"):
        assert h in hosts
    assert 18 <= len(hosts) <= 25


def test_every_snapshot_system_builds_or_is_rejected_with_a_reason() -> None:
    rows, info = load_rows()
    for host, rs in archive.group_by_host(rows).items():
        if host == "Kepler-47":  # circumbinary: rejected on purpose
            with pytest.raises(IncompleteSystemError, match="circumbinary"):
                system_from_rows(rs, info)
        else:
            assert len(system_from_rows(rs, info).planets) >= 2


def test_cache_roundtrip_and_refresh(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("EXOSTAB_OFFLINE")
    monkeypatch.setattr(store, "fetch_rows", lambda where: pair())
    rows, info = load_rows()
    assert info.kind == "archive" and rows == pair()
    meta = json.loads((store.cache_dir() / store.CACHE_META).read_text())
    assert meta["table"] == "pscomppars" and meta["n_rows"] == 2
    rows, info = load_rows()
    assert info.kind == "archive-cache" and rows == pair()
    rows, info = load_rows(refresh=True)
    assert info.kind == "archive"


def test_damaged_cache_is_ignored(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("EXOSTAB_OFFLINE")
    d = store.cache_dir()
    d.mkdir(parents=True)
    (d / store.CACHE_TABLE).write_text("garbage")
    (d / store.CACHE_META).write_text("{}")
    assert store.load_cache() is None


def test_truncated_or_altered_cache_is_ignored(monkeypatch: pytest.MonkeyPatch) -> None:
    # A cut-off table used to load silently (csv fills missing fields with None): systems lost planets.
    monkeypatch.delenv("EXOSTAB_OFFLINE")
    three = [*pair(), row("Host d", pl_orbper=60.0)]
    monkeypatch.setattr(store, "fetch_rows", lambda where: three)
    load_rows()
    table = store.cache_dir() / store.CACHE_TABLE
    full = table.read_bytes()
    assert store.load_cache() is not None
    table.write_bytes(full[: len(full) * 2 // 3])  # last rows lost or cut in the middle
    assert store.load_cache() is None
    table.write_bytes(full.replace(b"25.0", b"26.0"))  # same number of rows, different content
    assert store.load_cache() is None
    # a cache written before the checksum existed is still accepted if its row count matches
    table.write_bytes(full)
    meta_path = store.cache_dir() / store.CACHE_META
    meta = json.loads(meta_path.read_text())
    del meta["sha256"]
    meta_path.write_text(json.dumps(meta))
    assert store.load_cache() is not None


def test_interrupted_refresh_keeps_the_previous_cache(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("EXOSTAB_OFFLINE")
    monkeypatch.setattr(store, "fetch_rows", lambda where: pair())
    load_rows()
    good = (store.cache_dir() / store.CACHE_TABLE).read_bytes()

    def interrupted(rows: Any, path: Path) -> None:
        path.write_text("pl_name,hostname\nHost b,Host\n")  # partly written when the user presses Ctrl-C
        raise KeyboardInterrupt

    monkeypatch.setattr(store, "fetch_rows", lambda where: [*pair(), row("Host d", pl_orbper=60.0)])
    monkeypatch.setattr(store, "write_csv", interrupted)
    with pytest.raises(KeyboardInterrupt):
        load_rows(refresh=True)
    assert (store.cache_dir() / store.CACHE_TABLE).read_bytes() == good
    cached = store.load_cache()
    assert cached is not None and cached[0] == pair()
    assert sorted(p.name for p in store.cache_dir().iterdir()) == sorted(
        [store.CACHE_META, store.CACHE_TABLE]
    )


def test_network_failure_falls_back_to_snapshot(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("EXOSTAB_OFFLINE")

    def fail(where: str) -> None:
        raise archive.ArchiveError("down")

    monkeypatch.setattr(store, "fetch_rows", fail)
    _, info = load_rows()
    assert info.kind == "snapshot" and "unreachable" in (info.note or "")
    with pytest.raises(archive.ArchiveError):
        load_rows(refresh=True)


def test_lookup_in_the_snapshot_says_only_the_snapshot_was_searched(monkeypatch: pytest.MonkeyPatch) -> None:
    # During an outage without a cache, a real archive system outside the snapshot was reported as absent
    # from the archive.
    monkeypatch.delenv("EXOSTAB_OFFLINE")

    def fail(where: str) -> None:
        raise archive.ArchiveError("simulated outage")

    monkeypatch.setattr(store, "fetch_rows", fail)
    with pytest.raises(SystemNotFoundError) as err:
        load_system("Kepler-1542")
    message = str(err.value)
    assert "offline snapshot" in message and "simulated outage" in message
    assert "not the full archive table" in message and "in the archive table" not in message
    with pytest.raises(SystemNotFoundError, match="offline snapshot"):
        load_system("Kepler-1542", offline=True)


def test_empty_answer_keeps_the_cache_or_falls_back(monkeypatch: pytest.MonkeyPatch) -> None:
    # An empty answer replaced a good cache: n_rows went from 2663 to 0, and `catalog build --refresh` exited 0
    # with no systems.
    monkeypatch.delenv("EXOSTAB_OFFLINE")
    monkeypatch.setattr(store, "fetch_rows", lambda where: [])
    _rows, info = load_rows()  # no cache: the snapshot, with the reason
    assert info.kind == "snapshot" and "no rows" in (info.note or "")
    assert not store.cache_dir().exists() or not list(store.cache_dir().iterdir())
    monkeypatch.setattr(store, "fetch_rows", lambda where: pair())
    load_rows()
    good = (store.cache_dir() / store.CACHE_TABLE).read_bytes()
    monkeypatch.setattr(store, "fetch_rows", lambda where: [])
    with pytest.raises(archive.ArchiveError, match="no rows"):
        load_rows(refresh=True)
    assert (store.cache_dir() / store.CACHE_TABLE).read_bytes() == good


def _hosts(n: int, short: int = 0) -> list[dict[str, Any]]:
    """Rows of ``n`` single-star hosts with two planets each, of which ``short`` have lost one row."""
    rows = []
    for k in range(n):
        rows.append(row(f"H{k} b", host=f"H{k}"))
        if k >= short:
            rows.append(row(f"H{k} c", host=f"H{k}", pl_orbper=25.0))
    return rows


def test_a_cut_answer_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    # A result cut after 16 rows: Kepler-11 kept 3 of its 6 planets, with no flag, in every later report.
    monkeypatch.delenv("EXOSTAB_OFFLINE")
    monkeypatch.setattr(store, "fetch_rows", lambda where: _hosts(100, short=2))
    with pytest.raises(archive.ArchiveError, match="looks cut: 2 of 100"):
        load_rows(refresh=True)
    # up to 1% is taken as the archive's own gaps: the table is kept, and those hosts are flagged
    monkeypatch.setattr(store, "fetch_rows", lambda where: _hosts(100, short=1))
    _rows, info = load_rows(refresh=True)
    assert info.kind == "archive" and store.load_cache() is not None
    host_rows = [row("H b", host="H", sy_pnum=3), row("H c", host="H", sy_pnum=3, pl_orbper=25.0)]
    flag = next(f for f in system_from_rows(host_rows, INFO).flags if f.rule == "planet_rows_missing")
    assert "counts 3 planets" in flag.message and "2 rows" in flag.message
    # companion stars can hold the other planets, as sy_pnum counts around every star of the system
    host_rows = [{**r, "sy_snum": 2} for r in host_rows]
    assert "planet_rows_missing" not in {f.rule for f in system_from_rows(host_rows, INFO).flags}


@pytest.mark.parametrize("kind", ["a file in the way", "below a file", "read-only"])
def test_a_cache_folder_that_cannot_be_written_keeps_the_rows(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, kind: str
) -> None:
    # A read-only home on a cluster: the tracebacks came after a successful download, and the rows were thrown away.
    monkeypatch.delenv("EXOSTAB_OFFLINE")
    monkeypatch.setattr(store, "fetch_rows", lambda where: pair())
    blocker = tmp_path / "blocker"
    if kind == "read-only":
        if os.geteuid() == 0:
            pytest.skip("root can write everywhere")
        blocker.mkdir()
        blocker.chmod(0o500)
        monkeypatch.setenv("EXOSTAB_CACHE_DIR", str(blocker / "cache"))
    else:
        blocker.write_text("x")
        monkeypatch.setenv(
            "EXOSTAB_CACHE_DIR", str(blocker if kind == "a file in the way" else blocker / "cache")
        )
    try:
        rows, info = load_rows()
    finally:
        if kind == "read-only":
            blocker.chmod(0o700)
    assert rows == pair() and info.kind == "archive" and info.path is None
    assert "could not be saved in the cache folder" in (info.note or "")


def test_a_cache_folder_that_cannot_be_searched_counts_as_no_cache(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    if os.geteuid() == 0:
        pytest.skip("root can read everywhere")
    monkeypatch.delenv("EXOSTAB_OFFLINE")
    monkeypatch.setattr(store, "fetch_rows", lambda where: pair())
    closed = tmp_path / "closed"
    closed.mkdir()
    closed.chmod(0o000)
    monkeypatch.setenv("EXOSTAB_CACHE_DIR", str(closed / "cache"))
    try:
        assert store.load_cache() is None
        assert load_rows()[0] == pair()
    finally:
        closed.chmod(0o700)


def test_processes_filling_the_cache_at_once_do_not_disturb_each_other(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # An array job with a shared cache: 6 of 8 processes failed with FileNotFoundError on the one temporary name.
    monkeypatch.delenv("EXOSTAB_OFFLINE")
    monkeypatch.setattr(store, "fetch_rows", lambda where: pair())
    write = store.write_csv
    together = threading.Barrier(2)

    def write_then_wait(rows: Any, path: Path) -> None:
        write(rows, path)
        together.wait(timeout=30)  # both have written their temporary file before either renames it

    monkeypatch.setattr(store, "write_csv", write_then_wait)
    errors: list[BaseException] = []

    def refresh() -> None:
        try:
            store.refresh_cache()
        except BaseException as exc:
            errors.append(exc)

    threads = [threading.Thread(target=refresh) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=60)
    assert errors == []
    cached = store.load_cache()
    assert cached is not None and cached[0] == pair()
    assert sorted(p.name for p in store.cache_dir().iterdir()) == sorted(
        [store.CACHE_META, store.CACHE_TABLE]
    )


def _good_cache(monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.delenv("EXOSTAB_OFFLINE")
    monkeypatch.setattr(store, "fetch_rows", lambda where: pair())
    load_rows()
    return store.cache_dir()


def _without_checksum(d: Path) -> None:
    meta = json.loads((d / store.CACHE_META).read_text())
    del meta["sha256"]
    (d / store.CACHE_META).write_text(json.dumps(meta))


def test_a_stray_quote_is_damage(monkeypatch: pytest.MonkeyPatch) -> None:
    # _csv.Error: field larger than the field limit, as a traceback
    d = _good_cache(monkeypatch)
    table = d / store.CACHE_TABLE
    table.write_text(table.read_text().replace("Host c", '"Host c', 1) + "x" * 200_000)
    _without_checksum(d)
    assert store.load_cache() is None


@pytest.mark.parametrize("cell", ["inf", "1e999"])
def test_an_infinite_integer_in_the_cache_gives_no_traceback(
    monkeypatch: pytest.MonkeyPatch, cell: str
) -> None:
    d = _good_cache(monkeypatch)
    table = d / store.CACHE_TABLE
    text = table.read_text()
    assert ",2,1," in text
    table.write_text(text.replace(",2,1,", f",{cell},1,", 1))
    _without_checksum(d)
    cached = store.load_cache()
    assert cached is not None and cached[0][0]["sy_pnum"] is None


def test_a_non_text_date_in_the_cache_is_damage(monkeypatch: pytest.MonkeyPatch) -> None:
    # `exostab list` failed on it with a TypeError
    d = _good_cache(monkeypatch)
    meta = json.loads((d / store.CACHE_META).read_text())
    meta["retrieved_utc"] = 20260928
    (d / store.CACHE_META).write_text(json.dumps(meta))
    assert store.load_cache() is None


def test_a_directory_in_place_of_the_table_is_damage(monkeypatch: pytest.MonkeyPatch) -> None:
    d = _good_cache(monkeypatch)
    (d / store.CACHE_TABLE).unlink()
    (d / store.CACHE_TABLE).mkdir()
    assert store.load_cache() is None
    rows, info = load_rows()  # and it cannot be replaced: the rows still come, with a message
    assert rows == pair() and "could not be saved" in (info.note or "")


def test_a_row_cut_in_the_middle_is_damage(monkeypatch: pytest.MonkeyPatch) -> None:
    # An old sidecar has no checksum, and the row count still matches: K2-368 b lost its pl_bmassprov and its "estimated".
    d = _good_cache(monkeypatch)
    table = d / store.CACHE_TABLE
    table.write_bytes(table.read_bytes().rstrip()[:-40])
    _without_checksum(d)
    assert store.load_cache() is None


def test_a_tilde_in_the_cache_folder_means_the_home_folder(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    # It created a folder named ~ in every working directory, each with its own download.
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("EXOSTAB_CACHE_DIR", "~/exo-cache")
    assert store.cache_dir() == tmp_path / "exo-cache"


def test_a_line_says_when_the_table_is_downloaded(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.delenv("EXOSTAB_OFFLINE")
    monkeypatch.setattr(store, "fetch_rows", lambda where: pair())
    load_rows()
    assert "Downloading the archive table" in capsys.readouterr().err


def test_offline_flag_and_env() -> None:
    assert store.offline_requested()
    assert load_rows(offline=True)[1].kind == "snapshot"


def test_name_resolution() -> None:
    assert names.normalize("TRAPPIST-1") == names.normalize("trappist 1") == "trappist1"
    s = load_system("trappist 1")
    assert s.name == "TRAPPIST-1" and len(s.planets) == 7
    assert load_system("Kepler-11 b").name == "Kepler-11"
    with pytest.raises(SystemNotFoundError) as err:
        load_system("TRAPIST-1")
    assert "TRAPPIST-1" in err.value.suggestions
    with pytest.raises(SystemNotFoundError, match="No multi-planet system"):
        load_system("Nonexistent-999")
    assert names.all_names(["b", "A", "c"]) == ["A", "b", "c"]


def test_planet_name_that_normalises_to_another_host() -> None:
    # In the archive, the planet "55 Cnc b" (host "55 Cnc") and the host "55 Cnc B" (an M-dwarf companion
    # with its own planets) differ only in case, as do "TOI-2267 b" (host "TOI-2267 A") and "TOI-2267 B".
    hosts = archive.group_by_host(
        [
            row("55 Cnc b", host="55 Cnc"),
            row("55 Cnc e", host="55 Cnc"),
            row("55 Cnc B b", host="55 Cnc B"),
            row("55 Cnc B c", host="55 Cnc B"),
            row("TOI-2267 b", host="TOI-2267 A"),
            row("TOI-2267 c", host="TOI-2267 A"),
            row("TOI-2267 d", host="TOI-2267 B"),
        ]
    )
    assert names.resolve_host("55 Cnc b", hosts) == "55 Cnc"
    assert names.resolve_host("55 Cnc B", hosts) == "55 Cnc B"
    assert names.resolve_host("55 cnc e", hosts) == "55 Cnc"
    assert names.resolve_host("TOI-2267 b", hosts) == "TOI-2267 A"
    assert names.resolve_host("TOI-2267 B", hosts) == "TOI-2267 B"
    # a typed name that matches both is refused instead of silently picking one
    with pytest.raises(names.AmbiguousNameError) as err:
        names.resolve_host("55 cnc b", hosts)
    assert isinstance(err.value, SystemNotFoundError)  # the CLI and the web app report it like a miss
    assert set(err.value.suggestions) == {"55 Cnc", "55 Cnc B"}
    assert "'55 Cnc b'" in str(err.value) and "'55 Cnc B'" in str(err.value)


def test_name_carried_only_by_planets() -> None:
    # The archive's host of Kepler-90 is KOI-351, and only its planet "Kepler-90 i" carries the name; the
    # close matches used to suggest Kepler-990. "TOI-836.01" is an archive name without a final planet letter.
    hosts = archive.group_by_host(
        [
            row("KOI-351 b", host="KOI-351"),
            row("Kepler-90 i", host="KOI-351"),
            row("Kepler-990 b", host="Kepler-990"),
            row("Kepler-990 c", host="Kepler-990"),
            row("TOI-2267 b", host="TOI-2267 A"),
            row("TOI-2267 c", host="TOI-2267 A"),
            row("TOI-2267 d", host="TOI-2267 B"),
            row("TOI-836 b", host="TOI-836"),
            row("TOI-836.01", host="TOI-836", pl_letter="c"),
        ]
    )
    assert names.resolve_host("Kepler-90", hosts) == "KOI-351"
    assert names.resolve_host("kepler 90", hosts) == "KOI-351"
    assert names.resolve_host("Kepler-90 i", hosts) == "KOI-351"
    assert names.resolve_host("TOI-836.01", hosts) == "TOI-836"
    # the planets of two hosts carry the name: refused, as for any other ambiguous name
    with pytest.raises(names.AmbiguousNameError) as err:
        names.resolve_host("TOI-2267", hosts)
    assert set(err.value.suggestions) == {"TOI-2267 A", "TOI-2267 B"}
    assert "of 'TOI-2267 A'" in str(err.value) and "of 'TOI-2267 B'" in str(err.value)
    # the whole query must match: "Kepler-9" and "KOI" are not what the planets are called
    for query in ("Kepler-9", "KOI"):
        with pytest.raises(SystemNotFoundError) as err:
            names.resolve_host(query, hosts)
        assert "KOI-351" not in err.value.suggestions


def test_host_and_planet_names_win_over_the_names_of_other_planets() -> None:
    hosts = archive.group_by_host(
        [
            row("Kepler-90 b", host="Kepler-90"),
            row("Kepler-90 c", host="Kepler-90"),
            row("KOI-351 b", host="KOI-351"),
            row("Kepler-90 i", host="KOI-351"),
            row("HD 5 b", host="HD 5"),
            row("HD 5 c", host="HD 5"),
            row("HD 6 b", host="HD 6"),
            row("HD 5 B d", host="HD 6"),
        ]
    )
    assert names.resolve_host("Kepler-90", hosts) == "Kepler-90"
    assert names.resolve_host("kepler 90", hosts) == "Kepler-90"
    assert names.resolve_host("Kepler-90 i", hosts) == "KOI-351"
    assert names.resolve_host("HD 5 B", hosts) == "HD 5"  # the planet "HD 5 b", once case is ignored


SUGGESTED_HOSTS = archive.group_by_host(
    [
        *(
            row(f"{host} {letter}", host=host)
            for host in (
                "GJ 876",
                "GJ 667 C",
                "GJ 1148",
                "Gl 725 A",
                "Gl 725 B",
                "ups And",
                "tau Cet",
                "55 Cnc",
                "55 Cnc B",
                "nu Oph",
                "47 UMa",
                "14 Her",
                "rho CrB",
                "iot Dra",
                "HD 124",
            )
            for letter in "bc"
        ),
        row("KOI-351 b", host="KOI-351"),
        row("Kepler-90 i", host="KOI-351"),
        row("HD 39091 b", host="HD 39091"),
        row("pi Men c", host="HD 39091"),
    ]
)


@pytest.mark.parametrize(
    ("query", "suggested"),
    [
        ("Gliese 876", ["GJ 876"]),
        ("Gl 876", ["GJ 876"]),
        ("gliese-876", ["GJ 876"]),
        ("Gliese 876 b", ["GJ 876"]),
        ("Gliese 667", ["GJ 667 C"]),
        ("Gliese 667 Cc", ["GJ 667 C"]),
        ("Gliese 725", ["Gl 725 A", "Gl 725 B"]),
        ("GJ 725", ["Gl 725 A", "Gl 725 B"]),
        ("Upsilon Andromedae", ["ups And"]),
        ("upsilon  andromedae", ["ups And"]),
        ("Upsilon Andromedae d", ["ups And"]),
        ("Tau Ceti", ["tau Cet"]),
        ("55 Cancri", ["55 Cnc"]),
        ("55 Cancri e", ["55 Cnc"]),
        ("55 Cancri B", ["55 Cnc", "55 Cnc B"]),
        ("Nu Ophiuchi", ["nu Oph"]),
        ("47 Ursae Majoris", ["47 UMa"]),
        ("14 Herculis", ["14 Her"]),
        ("Rho Coronae Borealis", ["rho CrB"]),
        ("Pi Mensae", ["HD 39091"]),  # the archive's host is HD 39091; only its planet carries the name
        ("Kepler-90 h", ["KOI-351"]),  # the archive's planet is KOI-351 h
        ("Kepler-90h", ["KOI-351"]),
        ("KEPLER-90 H", ["KOI-351"]),
        ("KOI-351 x", ["KOI-351"]),
    ],
)
def test_other_forms_of_a_name_are_suggested_and_never_resolved(query: str, suggested: list[str]) -> None:
    with pytest.raises(SystemNotFoundError) as err:
        names.resolve_host(query, SUGGESTED_HOSTS)
    assert err.value.suggestions == suggested
    assert not isinstance(err.value, names.AmbiguousNameError)


@pytest.mark.parametrize(
    "query",
    [
        "Gliese 87",  # the same number, not the same first digits
        "Gliese 1",
        "Gliese",
        "Tau Cygni",  # the constellation must fit as well as the star
        "Zeta Ceti",
        "Iota Andromedae",  # the letters of Dra occur in order, but the rest must start with the D
        "Tau Crateris",  # it starts with the C of Cet, but the E and T do not follow in order
        "145 Herculis",  # a number must match whole: this is not 14 Her
        "Andromedae Upsilon",
        "Upsilon",
        "HD 1920384",  # the digits of HD 124 in order, but a catalogue number is not an abbreviation
        "Nonexistent-999",
    ],
)
def test_no_suggestion_points_to_the_list_command(query: str) -> None:
    with pytest.raises(SystemNotFoundError) as err:
        names.resolve_host(query, SUGGESTED_HOSTS)
    assert err.value.suggestions == []
    assert str(err.value) == (
        f"No multi-planet system named {query!r} in the archive table. Run exostab list to see the names."
    )


def test_error_text_says_either_what_to_try_or_where_to_look() -> None:
    with pytest.raises(SystemNotFoundError) as err:
        names.resolve_host("Gliese 876", SUGGESTED_HOSTS)
    assert (
        str(err.value)
        == "No multi-planet system named 'Gliese 876' in the archive table. Did you mean: GJ 876?"
    )
    # the snapshot's message keeps the suggestions, or the pointer when there are none
    with pytest.raises(SystemNotFoundError, match=r"offline snapshot.*Did you mean: GJ 876\?"):
        load_system("Gliese 876", offline=True)
    with pytest.raises(SystemNotFoundError, match=r"offline snapshot.*Run exostab list"):
        load_system("Nonexistent-999", offline=True)


@pytest.mark.parametrize(
    ("query", "suggested"),
    [
        ("Kepler-10.01", "Kepler-1001"),  # another star, named only in the header of a full report
        ("K2-3.2", "K2-32"),
        ("KOI-35.03", "KOI-3503"),
        ("BD+08 2823", "BD-08 2823"),
        ("BD-08 2823", "BD+08 2823"),
    ],
)
def test_digits_and_signs_stay_apart(query: str, suggested: str) -> None:
    hosts = archive.group_by_host(
        [row(f"{h} {letter}", host=h) for h in (suggested,) for letter in "bc"]
        + [row(f"Kepler-10 {letter}", host="Kepler-10") for letter in "bc"]
    )
    with pytest.raises(SystemNotFoundError) as err:
        names.resolve_host(
            query, hosts
        )  # D24: a wrong guess would check another system, so it is only suggested
    assert suggested in err.value.suggestions


def test_separators_between_letters_and_digits_are_still_ignored() -> None:
    assert names.normalize("Kepler 10") == names.normalize("KEPLER-10") == "kepler10"
    assert names.normalize("TOI-1233.01") == names.normalize("TOI 1233 01") != names.normalize("TOI-123301")
    hosts = archive.group_by_host(
        [row("BD-08 2823 b", host="BD-08 2823"), row("BD-08 2823 c", host="BD-08 2823")]
    )
    assert names.resolve_host("bd-08  2823", hosts) == "BD-08 2823"
    assert names.resolve_host("BD-08 2823 b", hosts) == "BD-08 2823"


def test_a_candidate_name_suggests_its_host() -> None:
    # TOI-1233: "Did you mean: TOI-1533, TOI-1238, ...", although the planet TOI-1233.01 belongs to HD 108236.
    hosts = archive.group_by_host(
        [
            row("HD 108236 b", host="HD 108236"),
            row("TOI-1233.01", host="HD 108236", pl_letter="c"),
            row("TOI-1533 b", host="TOI-1533"),
            row("TOI-1533 c", host="TOI-1533"),
        ]
    )
    with pytest.raises(SystemNotFoundError) as err:
        names.resolve_host("TOI-1233", hosts)  # a suggestion, never a resolution
    assert err.value.suggestions == ["HD 108236"]
    assert names.resolve_host("TOI-1233.01", hosts) == "HD 108236"


def test_the_hint_points_to_the_list_that_was_searched() -> None:
    # `exostab list` shows the archive's 1,060 hosts, whose names still fail with --offline.
    with pytest.raises(SystemNotFoundError, match=r"Run exostab list --offline to see the names\."):
        load_system("Nonexistent-999", offline=True)


@pytest.mark.parametrize("query", ["two_planet.yaml", "my system.YML", "x.json"])
def test_a_file_name_gets_a_hint_for_from_file(query: str) -> None:
    with pytest.raises(SystemNotFoundError, match=f"use --from-file {query}"):
        names.resolve_host(query, SUGGESTED_HOSTS)


def test_list_counts_a_zero_without_an_uncertainty_as_no_e() -> None:
    # Kepler-1542: list 0, report 4 assumed.
    rows = [
        row("Host b", pl_orbeccen=0.0, pl_orbeccenerr1=None, pl_orbeccenerr2=None),
        row("Host c", pl_orbper=25.0, pl_orbeccen=None),
        row("Host d", pl_orbper=60.0, pl_orbeccen=0.0, pl_orbeccenerr1=0.05, pl_orbeccenerr2=0.0),
        row("Host e", pl_orbper=90.0),
    ]
    assert list_systems(rows)[0].missing_eccentricities == 2
    assert (
        sum(p.eccentricity.provenance is Provenance.ASSUMED for p in system_from_rows(rows, INFO).planets)
        == 2
    )


def test_list_systems_filters() -> None:
    rows, _ = load_rows()
    all_ = list_systems(rows)
    assert all(s.n_planets >= 2 for s in all_)
    four = list_systems(rows, min_planets=4, max_period_days=200)
    assert four and all(s.n_planets >= 4 and (s.max_period_days or 0) <= 200 for s in four)
    assert "TRAPPIST-1" in {s.host for s in four}
    assert "HD 127195" not in {s.host for s in four}
    hd = next(s for s in all_ if s.host == "HD 127195")
    assert hd.minimum_masses == 2


def test_other_names() -> None:
    def names(host: str, planets: str, hosts: set[str]) -> list[str]:
        return other_names(host, planets.split(";"), hosts)

    assert names("KOI-351", "KOI-351 b;Kepler-90 i", set()) == ["Kepler-90"]
    assert names("GJ 876", "GJ 876 b", set()) == ["Gliese 876"]
    assert names("GJ 15 A", "GJ 15 A b", set()) == ["Gliese 15 A"]
    assert names("GJ 1132", "GJ 1132 b", set()) == []  # not one of Gliese's own numbers
    assert names("ups And", "ups And b", set()) == ["Upsilon Andromedae"]
    assert names("55 Cnc", "55 Cnc e", set()) == ["55 Cancri"]
    assert names("HD 39091", "pi Men c;HD 39091 b", set()) == ["pi Men", "Pi Mensae"]
    assert names("AU Mic", "AU Mic b", set()) == ["AU Microscopii"]
    assert names("Proxima Cen", "Proxima Cen b;Proxima Cen d", set()) == ["Proxima Centauri"]
    assert names("V1298 Tau", "V1298 Tau b", set()) == ["V1298 Tauri"]
    # candidates, parts of the host's name, other hosts and unknown abbreviations give no name
    assert names("TOI-216", "TOI-216.01;TOI-216.02", set()) == []
    assert names("Barnard's star", "Barnard b", set()) == []
    assert names("HD 142", "HD 142 A b", set()) == []
    assert names("55 Cnc B", "55 Cnc B b", {"55 Cnc"}) == ["55 Cancri B"]
    assert names("HD 1", "HD 2 b", {"HD 1", "HD 2"}) == []
    assert names("XX Foo", "XX Foo b", set()) == []
