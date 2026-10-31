"""Archive client, completion rules, cache/snapshot store and name matching."""

from __future__ import annotations

import json
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
