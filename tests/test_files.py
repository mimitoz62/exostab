import re
from pathlib import Path

import pytest

from conftest import EXAMPLES
from exostab.data import IncompleteSystemError, SystemFileError, files, load_system_file
from exostab.models import MassKind, PhaseKind, Provenance
from exostab.units import MJUP_IN_MEARTH


def write(tmp_path: Path, text: str) -> Path:
    p = tmp_path / "s.yaml"
    p.write_text(text)
    return p


GOOD = """
name: T
star: {mass_msun: 1.0}
planets:
  - {name: T b, period_days: 10, mass_earth: 5}
  - {name: T c, period_days: 30, mass_earth: 8}
"""


def test_examples_load() -> None:
    s = load_system_file(EXAMPLES / "two_planet.yaml")
    assert s.epoch_jd == 2460000.0
    c = s.planet("c")
    assert c.mass_kind is MassKind.MINIMUM
    assert c.mass_earth.value == pytest.approx(0.5 * MJUP_IN_MEARTH)
    assert c.eccentricity.provenance is Provenance.UPPER_LIMIT
    assert c.phase.kind is PhaseKind.TRANSIT
    assert c.omega_deg.provenance is Provenance.RANDOMIZED
    hd = load_system_file(EXAMPLES / "hd127195_note.yaml")
    assert hd.planet("b").phase.kind is PhaseKind.MEAN_LONGITUDE
    assert hd.source.kind == "file" and hd.source.note


def test_example_shows_every_key() -> None:
    # The docs point to this file as the format reference, and it says it shows every supported field.
    text = (EXAMPLES / "two_planet.yaml").read_text(encoding="utf-8")
    keys = files.TOP_KEYS | files.STAR_KEYS | files.PLANET_KEYS | files.VALUE_KEYS
    missing = sorted(k for k in keys if not re.search(rf"(^|[\s{{,]){k}:", text, flags=re.MULTILINE))
    assert missing == []


def test_defaults_and_flags(tmp_path: Path) -> None:
    s = load_system_file(write(tmp_path, GOOD))
    rules = {f.rule for f in s.flags}
    assert {"eccentricity_assumed_zero", "omega_randomized", "phase_randomized", "coplanar_assumed"} <= rules


def test_alternative_units_and_fields(tmp_path: Path) -> None:
    s = load_system_file(
        write(
            tmp_path,
            """
epoch_jd: 2450010.0
star: {mass_msun: {value: 1.0, err_plus: 0.1, err_minus: 0.05}}
planets:
  - {name: b, semimajor_axis_au: {value: 0.1, err: 0.001}, radius_earth: 1.5, mean_anomaly_deg: 10,
     omega_deg: 5}
  - {name: c, semimajor_axis_au: 0.2, mass_msun: 3.0e-6, periastron_time_jd: 2450000.0, eccentricity: 0.1,
     omega_deg: 30}
""",
        )
    )
    b, c = s.planets
    assert b.mass_kind is MassKind.ESTIMATED
    assert b.period_days.provenance is Provenance.DERIVED and b.period_days.has_errors
    assert not c.period_days.has_errors
    assert c.mass_earth.value == pytest.approx(0.9988, rel=1e-3)
    assert s.star.mass_msun.err_minus == 0.05
    assert s.name == "s"


@pytest.mark.parametrize(
    ("text", "error", "match"),
    [
        ("- a", SystemFileError, "mapping"),
        ("star: {mass_msun: 1}\nplanets: [{period_days: 1, mass_earth: 1}]", SystemFileError, "at least two"),
        ("planets: []", SystemFileError, "star"),
        (GOOD + "extra: 1", SystemFileError, "unknown top-level"),
        (GOOD.replace("mass_earth: 5", "mass_earth: 5, foo: 1"), SystemFileError, "unknown keys"),
        (GOOD.replace("mass_earth: 5", "mass_earth: 5, mass_jupiter: 1"), SystemFileError, "only one"),
        (GOOD.replace("mass_earth: 5", "mass_earth: {err: 1}"), SystemFileError, "missing 'value'"),
        (GOOD.replace("mass_earth: 5", "mass_earth: {value: 1, bad: 2}"), SystemFileError, "unknown keys"),
        (GOOD.replace("mass_earth: 5", "mass_earth: yes"), SystemFileError, "number"),
        (GOOD.replace("mass_earth: 5", "mass_earth: [1]"), SystemFileError, "number"),
        (GOOD.replace("mass_earth: 5", "mass_earth: {value: abc}"), SystemFileError, "could not convert"),
        (GOOD.replace("mass_earth: 5", "mass_earth: 5, mass_kind: weird"), SystemFileError, "mass_kind"),
        (GOOD.replace(", mass_earth: 5", ""), IncompleteSystemError, "give a mass"),
        (GOOD.replace(", mass_earth: 5", ", radius_earth: 13"), IncompleteSystemError, "giant-planet"),
        (GOOD.replace("period_days: 10, ", ""), IncompleteSystemError, "period_days"),
        (
            GOOD.replace("mass_earth: 5", "mass_earth: 5, mean_anomaly_deg: 1, mean_longitude_deg: 2"),
            SystemFileError,
            "at most one",
        ),
        (GOOD.replace("mass_earth: 5", "mass_earth: 5, eccentricity: 1.5"), SystemFileError, "eccentricity"),
        (GOOD.replace("mass_earth: 5", "mass_earth: 5, eccentricity: 0.97"), SystemFileError, "above 0.95"),
        # a mean anomaly or a time of periastron places the planet relative to its periastron, whose direction
        # omega_deg gives; without it the planet's longitude would be random in every run
        (GOOD.replace("mass_earth: 5", "mass_earth: 5, mean_anomaly_deg: 30"), SystemFileError, "omega_deg"),
        (
            GOOD.replace("mass_earth: 5", "mass_earth: 5, periastron_time_jd: 2460000.0"),
            SystemFileError,
            "omega_deg",
        ),
        # invalid values give a SystemFileError naming the field, not a traceback
        (
            GOOD.replace("mass_msun: 1.0", "mass_msun: -1.0"),
            SystemFileError,
            "star: .*stellar mass must be positive",
        ),
        (
            GOOD.replace("period_days: 10", "semimajor_axis_au: 0"),
            SystemFileError,
            "semimajor_axis_au must be",
        ),
        (
            GOOD.replace("period_days: 10", "semimajor_axis_au: -0.3"),
            SystemFileError,
            "semimajor_axis_au must be",
        ),
        ("epoch_jd: 2460000 BJD\n" + GOOD, SystemFileError, "epoch_jd"),
        (GOOD.replace("name: T c", "name: T b"), SystemFileError, "unique"),
        ("star: [", SystemFileError, "not valid YAML"),
        ("star: {mass_msun: 1}\nplanets: [1, 2]", SystemFileError, "must be a mapping"),
    ],
)
def test_errors(tmp_path: Path, text: str, error: type[Exception], match: str) -> None:
    with pytest.raises(error, match=match):
        load_system_file(write(tmp_path, text))


@pytest.mark.parametrize(
    "change",
    [
        ("mass_earth: 5", "mass_earth: 5, omega_deg: .nan"),
        ("mass_earth: 5", "mass_earth: 5, mean_longitude_deg: .nan"),
        ("mass_earth: 5", "mass_earth: 5, transit_time_jd: .nan"),
        ("mass_earth: 5", "mass_earth: .inf"),
        ("mass_earth: 5", "mass_jupiter: 1.0e+308"),  # finite in the file, infinite in Earth masses
        ("period_days: 10", "period_days: .inf"),
        ("period_days: 10", "period_days: {value: 10, err: .nan}"),
        ("period_days: 10", "semimajor_axis_au: -.inf"),
        ("mass_msun: 1.0", "mass_msun: .nan"),
        ("name: T\n", "name: T\nepoch_jd: .nan\n"),
    ],
)
def test_non_finite_numbers_are_refused(tmp_path: Path, change: tuple[str, str]) -> None:
    # YAML reads .nan and .inf as floats (and yaml.dump writes a missing float as .nan). A NaN angle, time or
    # epoch stopped every run at once, reported as a close encounter: an "unstable" verdict from invalid input.
    # Infinite masses or periods ended in tracebacks from the indicators.
    text = GOOD.replace(*change)
    assert text != GOOD
    with pytest.raises(SystemFileError, match="finite"):
        load_system_file(write(tmp_path, text))


MIXED = """
name: Mix
star: {mass_msun: 1.0}
planets:
  - {name: Mix b, period_days: 10, mass_earth: 5, omega_deg: 0, mean_anomaly_deg: 10}
  - {name: Mix c, period_days: 25, mass_earth: 8, transit_time_jd: 2459000.0}
"""


def test_mean_anomalies_next_to_reference_times_need_an_epoch(tmp_path: Path) -> None:
    # A mean anomaly or longitude only means something at a stated epoch. Without epoch_jd it used to be taken
    # at whichever transit or periastron time choose_epoch picked, an arbitrary relative phase.
    with pytest.raises(SystemFileError, match="epoch_jd"):
        load_system_file(write(tmp_path, MIXED))
    with pytest.raises(SystemFileError, match="epoch_jd"):
        load_system_file(write(tmp_path, MIXED.replace("mean_anomaly_deg", "mean_longitude_deg")))
    s = load_system_file(write(tmp_path, "epoch_jd: 2459003.0\n" + MIXED))
    assert s.epoch_jd == 2459003.0
    # angles alone share a common, unspecified epoch, and reference times alone need none
    load_system_file(write(tmp_path, MIXED.replace("transit_time_jd: 2459000.0", "mean_longitude_deg: 90")))
    load_system_file(
        write(tmp_path, MIXED.replace("omega_deg: 0, mean_anomaly_deg: 10", "transit_time_jd: 2459001"))
    )


def test_missing_file() -> None:
    with pytest.raises(SystemFileError, match="cannot read"):
        load_system_file("/nonexistent/system.yaml")


def test_upper_limit_mass_flag(tmp_path: Path) -> None:
    s = load_system_file(
        write(tmp_path, GOOD.replace("mass_earth: 5", "mass_earth: {value: 5, upper_limit: true}"))
    )
    assert "mass_upper_limit" in {f.rule for f in s.flags}


@pytest.mark.parametrize(
    "change",
    [
        ("mass_msun: 1.0", "mass_msun: {value: 1.0, upper_limit: true}"),
        ("period_days: 10", "period_days: {value: 10, upper_limit: true}"),
        ("mass_earth: 5", "mass_earth: 5, omega_deg: {value: 90, upper_limit: true}"),
        ("mass_earth: 5", "mass_earth: 5, transit_time_jd: {value: 2460000.0, upper_limit: true}"),
        ("mass_earth: 5", "mass_earth: 5, mean_longitude_deg: {value: 30, upper_limit: true}"),
        ("mass_earth: 5", "mass_earth: 5, radius_earth: {value: 2, upper_limit: true}"),
    ],
)
def test_upper_limits_only_on_planet_masses_and_eccentricities(
    tmp_path: Path, change: tuple[str, str]
) -> None:
    # Draws are uniform between 0 and an upper limit: meaningful for a planet mass or an eccentricity, not
    # for a stellar mass, a period, an angle or an absolute time, which used to be accepted without any flag.
    with pytest.raises(SystemFileError, match="upper_limit"):
        load_system_file(write(tmp_path, GOOD.replace(*change)))


def test_semimajor_axis_is_kept_and_checked_against_the_period(tmp_path: Path) -> None:
    # The axis used to be dropped without a check when a period was also given.
    one_au = GOOD.replace("period_days: 10", "period_days: 365.25, semimajor_axis_au: 1.0")
    s = load_system_file(write(tmp_path, one_au))
    b = s.planet("b")
    assert b.semimajor_axis_au is not None and b.semimajor_axis_au.value == 1.0
    assert b.period_days.provenance is Provenance.MEASURED
    # P = 10 d around 1 Msun is a = 0.09 AU, not 5 AU
    with pytest.raises(SystemFileError, match="semimajor_axis_au = 5 AU disagrees"):
        load_system_file(
            write(tmp_path, GOOD.replace("period_days: 10", "period_days: 10, semimajor_axis_au: 5.0"))
        )
    # an axis alone is kept too
    s = load_system_file(write(tmp_path, GOOD.replace("period_days: 10", "semimajor_axis_au: 0.1")))
    assert s.planet("b").semimajor_axis_au is not None


@pytest.mark.parametrize("key", ["circumbinary: true", "n_stars: 2", "mass_msun_err: 0.1"])
def test_unknown_star_keys_are_refused(tmp_path: Path, key: str) -> None:
    # They were silently ignored: a binary modelled as a single star without a flag, or an error bar lost.
    with pytest.raises(SystemFileError, match="star: unknown keys"):
        load_system_file(write(tmp_path, GOOD.replace("mass_msun: 1.0", f"mass_msun: 1.0, {key}")))


def test_mass_kind_must_match_the_mass_given(tmp_path: Path) -> None:
    # a radius-only planet gets a mass-radius estimate, which is not a measured or minimum mass
    for kind in ("minimum", "true"):
        text = GOOD.replace("mass_earth: 5", f"radius_earth: 2.0, mass_kind: {kind}")
        with pytest.raises(SystemFileError, match="mass_kind"):
            load_system_file(write(tmp_path, text))
    # a mass the file declares estimated is labelled and flagged like an archive estimate
    s = load_system_file(
        write(tmp_path, GOOD.replace("mass_earth: 5", "mass_earth: 5, mass_kind: estimated"))
    )
    b = s.planet("b")
    assert b.mass_kind is MassKind.ESTIMATED and b.mass_earth.provenance is Provenance.ESTIMATED
    assert "mass_estimated_in_file" in {f.rule for f in s.flags if f.planet == "T b"}


def test_upper_limit_must_be_a_boolean(tmp_path: Path) -> None:
    # the quoted string "no" is truthy and used to count as an upper limit
    text = GOOD.replace("mass_earth: 8", 'mass_earth: 8, eccentricity: {value: 0.1, upper_limit: "no"}')
    with pytest.raises(SystemFileError, match="true or false"):
        load_system_file(write(tmp_path, text))
    s = load_system_file(write(tmp_path, text.replace('"no"', "false")))
    assert s.planet("c").eccentricity.provenance is Provenance.MEASURED
    s = load_system_file(write(tmp_path, text.replace('"no"', "true")))
    assert s.planet("c").eccentricity.provenance is Provenance.UPPER_LIMIT


def test_solar_system_example_loads():
    s = load_system_file(EXAMPLES / "solar_system.yaml")
    assert s.planets[0].name == "Mercury" and len(s.planets) == 8
    assert "nssdc.gsfc.nasa.gov" in (EXAMPLES / "solar_system.yaml").read_text(encoding="utf-8")
