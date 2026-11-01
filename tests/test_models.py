import pytest
from pydantic import ValidationError

from conftest import V, two_planet_system
from exostab.models import DataSource, Phase, PhaseKind, Planet, Provenance, Star, System, Value


def test_value_helpers() -> None:
    assert V(1.0, 0.1).has_errors
    assert not V(1.0).has_errors
    assert not Value(provenance=Provenance.RANDOMIZED).is_known
    with pytest.raises(ValueError, match="missing"):
        Value().require()
    with pytest.raises(ValidationError):
        Value(value=1.0, err_plus=-1.0)


def test_phase_needs_value_unless_random() -> None:
    Phase(kind=PhaseKind.RANDOM)
    with pytest.raises(ValidationError):
        Phase(kind=PhaseKind.TRANSIT)


@pytest.mark.parametrize(
    ("kwargs", "match"),
    [
        ({"period_days": V(-1.0)}, "period"),
        ({"mass_earth": V(0.0)}, "mass"),
        ({"eccentricity": V(1.0)}, "eccentricity"),
    ],
)
def test_planet_validation(kwargs: dict[str, Value], match: str) -> None:
    base = {"name": "x", "period_days": V(10.0), "mass_earth": V(1.0)}
    base.update(kwargs)
    with pytest.raises(ValidationError, match=match):
        Planet(**base)  # type: ignore[arg-type]


def test_star_mass_must_be_positive() -> None:
    with pytest.raises(ValidationError, match="stellar mass"):
        Star(name="s", mass_msun=V(0.0))


def test_system_rules() -> None:
    s = two_planet_system()
    assert s.planet("b").name == "Test b"
    assert s.planet("Test c").name == "Test c"
    with pytest.raises(KeyError):
        s.planet("z")
    p = s.planets[0]
    with pytest.raises(ValidationError, match="at least two"):
        System(name="x", star=s.star, planets=(p,), source=DataSource(kind="file"))
    with pytest.raises(ValidationError, match="ordered"):
        System(name="x", star=s.star, planets=(s.planets[1], s.planets[0]), source=DataSource(kind="file"))
    q = p.model_copy(update={"period_days": V(200.0)})
    with pytest.raises(ValidationError, match="unique"):
        System(name="x", star=s.star, planets=(p, q), source=DataSource(kind="file"))


def _named(*names: str) -> System:
    planets = tuple(
        Planet(name=name, period_days=V(10.0 * (k + 1)), mass_earth=V(1.0)) for k, name in enumerate(names)
    )
    return System(
        name="x", star=Star(name="s", mass_msun=V(1.0)), planets=planets, source=DataSource(kind="file")
    )


def test_planet_lookup_prefers_the_exact_name() -> None:
    # "z B" used to find Z b, which comes first, while the sweep's title said z B
    assert _named("Z b", "z B").planet("z B").name == "z B"
    assert _named("HD 1 b", "HD 1 c").planet("hd 1 c").name == "HD 1 c"
    assert _named("HD 1 b", "HD 1 c").planet("C").name == "HD 1 c"


def test_planet_lookup_refuses_an_ambiguous_letter() -> None:
    # --planet b with HD 1 A b and HD 1 B b took the first without a word
    with pytest.raises(KeyError, match="fits several planets") as err:
        _named("HD 1 A b", "HD 1 B b").planet("b")
    assert "HD 1 A b" in str(err.value) and "HD 1 B b" in str(err.value)
    assert _named("HD 1 A b", "HD 1 B b").planet("B b").name == "HD 1 B b"
