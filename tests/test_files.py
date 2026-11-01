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
        (GOOD.replace("mass_earth: 5", "mass_earth: {value: abc}"), SystemFileError, "expected a number"),
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


@pytest.mark.parametrize(
    ("text", "key", "line"),
    [
        (  # a missing dash in the list of planets: T b used to vanish, with exit 0
            "star: {mass_msun: 1.0}\nplanets:\n  - name: T b\n    period_days: 10\n    mass_earth: 5\n"
            "    name: T c\n    period_days: 30\n    mass_earth: 8\n  - {name: T d, period_days: 90, mass_earth: 9}\n",
            "name",
            6,
        ),
        (GOOD.replace("period_days: 10", "period_days: 10, period_days: 20"), "period_days", 5),
        (GOOD + "star: {mass_msun: 2.0}\n", "star", 7),
    ],
)
def test_a_repeated_key_is_refused(tmp_path: Path, text: str, key: str, line: int) -> None:
    with pytest.raises(SystemFileError, match=rf"line {line}: the key '{key}' is repeated"):
        load_system_file(write(tmp_path, text))


def test_merge_keys_are_not_repeated_keys() -> None:
    text = "a: &a {x: 1, y: 2}\nb: {<<: *a, <<: *a, x: 3}\n"
    assert files.yaml.load(text, Loader=files._StrictLoader)["b"] == {"x": 3, "y": 2}


@pytest.mark.parametrize(
    "value",
    [
        "{value: 100, err_plus: 200}",
        "{value: 100, err_minus: 20}",
        "{value: 100, err: }",
        "{value: 100, err_plus: , err_minus: 2}",
    ],
)
def test_an_error_bar_on_one_side_or_empty_is_refused(tmp_path: Path, value: str) -> None:
    # Value.has_errors needs both sides, so the value was held fixed in every draw while report.json kept the error.
    with pytest.raises(SystemFileError, match=r"T b\.mass_earth"):
        load_system_file(write(tmp_path, GOOD.replace("mass_earth: 5", f"mass_earth: {value}")))


def test_estimated_mass_cannot_be_an_upper_limit(tmp_path: Path) -> None:
    # mass_kind: estimated used to remove upper_limit: the draws held the limit fixed, and the overall verdict could
    # be unstable, which DECISIONS.md, D27 excludes for upper limits.
    text = GOOD.replace("mass_earth: 5", "mass_earth: {value: 5, upper_limit: true}, mass_kind: estimated")
    with pytest.raises(SystemFileError, match="upper_limit and mass_kind estimated"):
        load_system_file(write(tmp_path, text))


@pytest.mark.parametrize(
    "change",
    [
        ("mass_msun: 1.0", "mass_msun: {value: yes}"),
        ("period_days: 10", "period_days: {value: true}"),
        ("mass_earth: 5", 'mass_earth: {value: "8"}'),
        ("mass_earth: 5", 'mass_earth: {value: 8, err: "1"}'),
        ("mass_earth: 5", "mass_earth: {value: 8, err: no}"),
        ("name: T\n", 'name: T\nepoch_jd: "2460000"\n'),
    ],
)
def test_booleans_and_text_are_not_numbers(tmp_path: Path, change: tuple[str, str]) -> None:
    # float() takes them: yes was a stellar mass of 1, and "8" a mass of 8 M_earth.
    with pytest.raises(SystemFileError, match="number"):
        load_system_file(write(tmp_path, GOOD.replace(*change)))


@pytest.mark.parametrize(
    ("written", "value"),
    [
        ("3e-6", 3e-6),
        ("1e1", 10.0),
        ("3.0e-6", 3e-6),
        ("1E+1", 10.0),
        ("2", 2.0),
        ("-1.5", -1.5),
        (".5", 0.5),
    ],
)
def test_numbers_of_yaml_1_2(written: str, value: float) -> None:
    # YAML 1.1 reads 3e-6 as text, and exostab refused it as "not a number" while 3.0e-6 worked.
    assert files.yaml.load(written, Loader=files._StrictLoader) == pytest.approx(value)


@pytest.mark.parametrize("written", ["010", "0x10", "0o17", "0b11", "1:30", "12:30:00", "045", "00"])
def test_numbers_that_only_yaml_1_1_reads_are_refused(tmp_path: Path, written: str) -> None:
    # 010 was 8, 0x10 was 16 and 1:30 was 90: no accepted number changes, and these are no longer accepted.
    with pytest.raises(SystemFileError, match=f"expected a number or a mapping, got '{written}'"):
        load_system_file(write(tmp_path, GOOD.replace("period_days: 10", f"period_days: {written}")))


@pytest.mark.parametrize(
    "content",
    [
        b"name: Caf\xe9\n",  # Latin-1
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR",
        "name: T\n".encode("utf-16"),
    ],
)
def test_a_file_that_is_not_utf8_is_refused(tmp_path: Path, content: bytes) -> None:
    path = tmp_path / "s.yaml"
    path.write_bytes(content)
    with pytest.raises(SystemFileError, match="is not a UTF-8 text file"):
        load_system_file(path)


@pytest.mark.parametrize(
    "text",
    [
        GOOD + "notes: 2024-02-30\n",  # ValueError from the date constructor
        GOOD + "notes: !!float abc\n",  # ValueError
        GOOD + "notes: !!bool abc\n",  # KeyError
        GOOD + "notes: !!timestamp abc\n",  # AttributeError
        "[" * 2000,  # RecursionError
        GOOD + "notes: " + "1" * 5000 + "\n",  # ValueError for an integer of too many digits
    ],
)
def test_what_yaml_cannot_construct_is_refused(tmp_path: Path, text: str) -> None:
    with pytest.raises(SystemFileError, match="is not valid YAML"):
        load_system_file(write(tmp_path, text))


def test_a_reference_is_text(tmp_path: Path) -> None:
    # reference: 2017 used to end in a pydantic traceback; a year or a number is a fair citation
    s = load_system_file(write(tmp_path, GOOD.replace("mass_earth: 5", "mass_earth: 5, reference: 2017")))
    assert s.planet("b").mass_earth.reference == "2017"
    s = load_system_file(
        write(tmp_path, GOOD.replace("mass_earth: 5", "mass_earth: {value: 5, reference: 2017}"))
    )
    assert s.planet("b").mass_earth.reference == "2017"
    for reference in ("[a, b]", "{a: b}", "yes"):
        for text in (
            f"mass_earth: 5, reference: {reference}",
            f"mass_earth: {{value: 5, reference: {reference}}}",
        ):
            with pytest.raises(SystemFileError, match="reference must be text"):
                load_system_file(write(tmp_path, GOOD.replace("mass_earth: 5", text)))


@pytest.mark.parametrize(
    "text",
    [
        GOOD + "1: x\nfoo: y\n",
        GOOD.replace("mass_msun: 1.0", "mass_msun: 1.0, 1: x, foo: y"),
        GOOD.replace("period_days: 10", "period_days: 10,5").replace(
            "mass_earth: 5", "mass_earth: 5, foo: y"
        ),
        GOOD.replace("mass_earth: 5", "mass_earth: 5, 1: x, ecentricity: y"),
        GOOD.replace("mass_earth: 5", "mass_earth: {value: 5, 1: x, foo: y}"),
    ],
)
def test_unknown_keys_of_mixed_types_are_named(tmp_path: Path, text: str) -> None:
    # sorted() failed on a number next to a string (a decimal comma gives the key 5): a TypeError, not this message
    with pytest.raises(SystemFileError, match="unknown"):
        load_system_file(write(tmp_path, text))


HUGE = "1" + "0" * 400


@pytest.mark.parametrize(
    "change",
    [
        ("period_days: 10", f"period_days: {HUGE}"),
        ("mass_earth: 5", f"mass_earth: {HUGE}"),
        ("mass_earth: 5", f"mass_earth: {{value: {HUGE}}}"),
        ("mass_earth: 5", f"mass_earth: {{value: 5, err: {HUGE}}}"),
        ("name: T\n", f"name: T\nepoch_jd: {HUGE}\n"),
    ],
)
def test_integers_too_large_for_a_float_are_refused(tmp_path: Path, change: tuple[str, str]) -> None:
    with pytest.raises(SystemFileError, match="finite number"):
        load_system_file(write(tmp_path, GOOD.replace(*change)))


@pytest.mark.parametrize(
    ("planet", "match"),
    [
        ("semimajor_axis_au: 0.1, mass_msun: -2", r"T b\.mass_msun: mass must be positive, got -2"),
        ("semimajor_axis_au: 0.1, mass_msun: -1", r"T b\.mass_msun: mass must be positive, got -1"),
        ("period_days: 10, mass_msun: -1", r"T b\.mass_msun: mass must be positive, got -1"),
        (
            "period_days: 10, mass_jupiter: {value: -1, err: 1}",
            r"T b\.mass_jupiter: mass must be positive, got -1",
        ),
    ],
)
def test_a_negative_mass_is_refused_with_its_key_and_value(tmp_path: Path, planet: str, match: str) -> None:
    # "math domain error", a ZeroDivisionError or "complex" next to an axis; "-332946.07832806994" (in Earth masses)
    # next to a period
    text = GOOD.replace("period_days: 10, mass_earth: 5", planet)
    assert text != GOOD
    with pytest.raises(SystemFileError, match=match):
        load_system_file(write(tmp_path, text))


@pytest.mark.parametrize(
    ("change", "match"),
    [
        (("mass_msun: 1.0", "mass_msun: 1.0e+100"), r"star\.mass_msun: 1e\+100"),
        (("mass_msun: 1.0", "mass_msun: 1.0e-6"), r"star\.mass_msun: 1e-06"),
        (
            ("mass_msun: 1.0", "mass_msun: {value: 1.0, err: 1.0e+300}"),
            r"star\.mass_msun: 1 \(with its error",
        ),
        (("period_days: 10", "semimajor_axis_au: 1.0e+103"), r"T b\.semimajor_axis_au: 1e\+103"),
        (("period_days: 10", "semimajor_axis_au: 1.0e+18"), r"T b\.semimajor_axis_au: 1e\+18"),
        (
            ("period_days: 10", "semimajor_axis_au: 1.0e-300"),
            r"T b\.semimajor_axis_au: 1e-300 AU gives a period of 0",
        ),
        (("period_days: 10", "period_days: 1.0e+50"), r"T b\.period_days: 1e\+50"),
        (("period_days: 10", "period_days: 1.0e-6"), r"T b\.period_days: 1e-06"),
        (
            ("period_days: 10", "period_days: {value: 10, err: 1.0e+300}"),
            r"T b\.period_days: 10 \(with its error",
        ),
        (("period_days: 10", "period_days: -5"), r"T b\.period_days: -5"),
        (("mass_earth: 5", "mass_msun: 2.0"), r"T b\.mass_msun: 2\.0 is not below the stellar mass"),
        (("mass_earth: 5", "mass_earth: {value: 5, err: 1.0e+300}"), r"T b\.mass_earth: 5 \(with its error"),
        (("mass_earth: 5", "mass_earth: 5, transit_time_jd: 1.0e+308"), r"T b\.transit_time_jd: 1e\+308"),
        (("mass_earth: 5", "mass_earth: 5, transit_time_jd: -1.0e+308"), r"T b\.transit_time_jd: -1e\+308"),
        (
            ("mass_earth: 5", "mass_earth: 5, transit_time_jd: {value: 2460000, err: 1.0e+300}"),
            "with its error",
        ),
        (("name: T\n", "name: T\nepoch_jd: 1.0e+308\n"), "epoch_jd = 1e.308 is not a plausible Julian date"),
    ],
)
def test_impossible_values_are_refused_with_their_key(
    tmp_path: Path, change: tuple[str, str], match: str
) -> None:
    # Tracebacks, runs that never end and verdicts for stars of 1e30 solar masses. A time of 1e308 became a NaN phase,
    # reported as a close encounter and overall UNSTABLE.
    with pytest.raises(SystemFileError, match=match):
        load_system_file(write(tmp_path, GOOD.replace(*change)))


def test_a_mass_error_larger_than_the_value_stays_accepted(tmp_path: Path) -> None:
    # Not impossible: DECISIONS.md, D11 redraws until positive, and the card shows what was typed.
    s = load_system_file(write(tmp_path, GOOD.replace("mass_msun: 1.0", "mass_msun: {value: 1.0, err: 5}")))
    assert s.star.mass_msun.err_plus == 5
    # a truncated JD is a real way to write a time: it stays accepted (and is flagged if the phase is lost on the way)
    load_system_file(write(tmp_path, GOOD.replace("mass_earth: 5", "mass_earth: 5, transit_time_jd: 5000.5")))


@pytest.mark.parametrize(
    "change",
    [
        ("name: T\n", 'name: "a\\uD800b"\n'),
        ("name: T\n", 'name: "a\\e[31mred"\n'),
        ("name: T b", 'name: "T\\e[31mb"'),
        ("mass_msun: 1.0", 'mass_msun: 1.0, name: "s\\x07"'),
        ("name: T\n", 'name: T\nnotes: "a\\uD800b"\n'),
        ("name: T\n", 'name: T\nnotes: "a\\e[31mred"\n'),
    ],
)
def test_control_characters_and_lone_surrogates_are_refused(tmp_path: Path, change: tuple[str, str]) -> None:
    # A surrogate crashed the card after the whole run; an escape sequence reached the terminal as such.
    with pytest.raises(SystemFileError, match="control character"):
        load_system_file(write(tmp_path, GOOD.replace(*change)))


def test_notes_can_have_several_lines(tmp_path: Path) -> None:
    s = load_system_file(write(tmp_path, GOOD + 'notes: "one\\n\\ttwo"\n'))
    assert s.source.note == "one\n\ttwo"


@pytest.mark.parametrize(
    "text",
    [
        "name: [a, b]\n" + GOOD.replace("name: T\n", ""),
        "name: {a: b}\n" + GOOD.replace("name: T\n", ""),
        "name: No\n"
        + GOOD.replace("name: T\n", ""),  # YAML 1.1 reads it as false, and the file name was used
        "name: 2017\n" + GOOD.replace("name: T\n", ""),
        GOOD.replace("name: T b", "name: No"),  # became "planet 1"
        GOOD.replace("name: T b", "name: Yes"),  # became "True"
        GOOD.replace("mass_msun: 1.0", "name: [a], mass_msun: 1.0"),
        GOOD + "notes: {x: y}\n",  # printed as Python text
        GOOD + "notes: [x]\n",
    ],
)
def test_names_and_notes_must_be_text(tmp_path: Path, text: str) -> None:
    with pytest.raises(SystemFileError, match="must be text"):
        load_system_file(write(tmp_path, text))


def test_quoted_names_are_accepted(tmp_path: Path) -> None:
    s = load_system_file(
        write(tmp_path, GOOD.replace("name: T b", 'name: "No"').replace("name: T\n", 'name: "2017"\n'))
    )
    assert s.name == "2017" and s.planets[0].name == "No"


def test_nested_aliases_cannot_grow_a_report_or_a_message(tmp_path: Path) -> None:
    # A 398-byte file wrote a report.json of 11.6 MB through its notes.
    levels = ["&a0 [x, x, x, x, x, x, x, x, x, x]"]
    levels += [f"&a{k} [{', '.join([f'*a{k - 1}'] * 10)}]" for k in range(1, 7)]
    with pytest.raises(SystemFileError) as err:
        load_system_file(write(tmp_path, "notes: [" + ", ".join(levels) + "]\n" + GOOD))
    assert "must be text" in str(err.value) and len(str(err.value).replace(str(tmp_path), "")) < 500


@pytest.mark.parametrize(
    "value",
    [
        "{value: 5, err: 1, err_plus: 9}",
        "{value: 5, err: 1, err_minus: 9}",
        "{value: 5, err: 1, upper_limit: true}",
    ],
)
def test_contradictory_error_keys_are_refused(tmp_path: Path, value: str) -> None:
    # {value: 5, err: 1, err_plus: 9} became +9/-1, and an upper limit printed <5 while the draws ignored err.
    with pytest.raises(SystemFileError, match=r"T b\.mass_earth"):
        load_system_file(write(tmp_path, GOOD.replace("mass_earth: 5", f"mass_earth: {value}")))


@pytest.mark.parametrize("value", ["0", "-0.1"])
def test_an_upper_limit_must_be_positive(tmp_path: Path, value: str) -> None:
    text = GOOD.replace(
        "mass_earth: 5", f"mass_earth: 5, eccentricity: {{value: {value}, upper_limit: true}}"
    )
    with pytest.raises(SystemFileError, match="an upper limit must be positive"):
        load_system_file(write(tmp_path, text))


@pytest.mark.parametrize("radius", ["-2", "0", "{value: -2, err: 1}"])
def test_a_radius_must_be_positive_next_to_a_mass_too(tmp_path: Path, radius: str) -> None:
    # Alone it was refused; next to a mass, -2 was written to report.json.
    text = GOOD.replace("mass_earth: 5", f"mass_earth: 5, radius_earth: {radius}")
    with pytest.raises(SystemFileError, match=r"T b\.radius_earth must be positive"):
        load_system_file(write(tmp_path, text))


@pytest.mark.parametrize(("first", "second"), [("Z b", "z B"), ("T b", '" T b"'), ("T b", '"T b "')])
def test_planet_names_differing_only_in_case_or_spaces_are_refused(
    tmp_path: Path, first: str, second: str
) -> None:
    # sweep --planet ignores case, so it varied one planet while the title named the other.
    text = GOOD.replace("name: T b", f"name: {first}").replace("name: T c", f"name: {second}")
    with pytest.raises(SystemFileError, match="differ only in case or surrounding spaces"):
        load_system_file(write(tmp_path, text))


def test_an_error_on_a_radius_is_said_to_be_ignored(tmp_path: Path) -> None:
    # examples/two_planet.yaml shows this form, and the estimated mass is fixed in every draw.
    def message(radius: str) -> str:
        text = GOOD.replace("mass_earth: 5", f"radius_earth: {radius}")
        s = load_system_file(write(tmp_path, text))
        return next(f.message for f in s.flags if f.rule == "mass_from_radius_chen_kipping")

    assert "radius error is not propagated" in message("{value: 2, err: 1}")
    assert "radius error" not in message("2")


def test_messages_name_the_value_as_written(tmp_path: Path) -> None:
    # "eccentricity 0.95 is above 0.95", and "T: planet names must be unique" (which name?)
    with pytest.raises(SystemFileError, match=r"eccentricity 0\.9500001 is above 0\.95"):
        load_system_file(
            write(tmp_path, GOOD.replace("mass_earth: 5", "mass_earth: 5, eccentricity: 0.9500001"))
        )
    with pytest.raises(SystemFileError, match="unique, but 'T b' is used twice"):
        load_system_file(write(tmp_path, GOOD.replace("name: T c", "name: T b")))
    with pytest.raises(SystemFileError, match=r"T b\.mass_earth: expected a number, got None"):
        load_system_file(write(tmp_path, GOOD.replace("mass_earth: 5", "mass_earth: {value: }")))


def test_a_reference_time_far_from_the_epoch_is_flagged(tmp_path: Path) -> None:
    # A truncated JD 5000.5 next to 2455000.5: the card said "transit" for a phase 58 turns uncertain.
    text = """
name: T
star: {mass_msun: 1.0}
planets:
  - {name: T b, period_days: {value: 10, err: 0.01}, mass_earth: 5, transit_time_jd: {value: 5000.5, err: 0.001}}
  - {name: T c, period_days: {value: 20.5, err: 0.01}, mass_earth: 5, transit_time_jd: {value: 2455000.5, err: 0.001}}
"""
    s = load_system_file(write(tmp_path, text))
    flagged = {f.planet: f.message for f in s.flags if f.rule == "phase_uncertain_at_epoch"}
    assert len(flagged) == 1 and "full turns" in next(iter(flagged.values()))
    # no flag at close reference times, and the phases are unchanged
    s = load_system_file(write(tmp_path, text.replace("value: 5000.5", "value: 2455001.5")))
    assert "phase_uncertain_at_epoch" not in {f.rule for f in s.flags}
