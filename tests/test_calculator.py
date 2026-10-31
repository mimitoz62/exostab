"""The calculator page (docs/javascripts/calculator.js) against the Python functions it ports."""

from __future__ import annotations

import json
import math
import os
import random
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest
import yaml

from exostab.data import load_system, load_system_file
from exostab.indicators import amd, hill
from exostab.sampling import E_MAX, Body, Realization, realizations
from exostab.units import (
    DAY_IN_YR,
    G_SIM,
    MEARTH_IN_MSUN,
    MJUP_IN_MEARTH,
    days_to_years,
    mearth_to_msun,
    period_from_semimajor_axis,
    semimajor_axis_from_period,
    years_to_days,
)

ROOT = Path(__file__).resolve().parents[1]
CALCULATOR = ROOT / "docs" / "javascripts" / "calculator.js"
PAGE = ROOT / "docs" / "calculator.md"
NODE = shutil.which("node")
N_PAIRS = 3000  # docs/calculator.md states this number
REL_TOL = 1e-9

pytestmark = [
    pytest.mark.skipif(not CALCULATOR.is_file(), reason="this page is not in the sdist"),
    # In GitHub Actions a missing node fails in node(), so that CI cannot stay green with the port unchecked.
    pytest.mark.skipif(NODE is None and "GITHUB_ACTIONS" not in os.environ, reason="needs node"),
]

Case = dict[str, Any]


def node(expression: str, data: Any = None) -> Any:
    """The JSON value of an expression in Node, with the calculator as ``calc`` and the input as ``data``."""
    assert NODE is not None
    script = (
        "const calc = require(process.argv[1]);"
        'const data = JSON.parse(require("fs").readFileSync(0, "utf8"));'
        f"const out = {expression};"
        # JSON has no infinite numbers; float() reads the string.
        'process.stdout.write(JSON.stringify(out, (k, v) => (v === Infinity ? "Infinity" : v)));'
    )
    run = subprocess.run(
        [NODE, "-e", script, str(CALCULATOR)],
        input=json.dumps(data),
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
    )
    return json.loads(run.stdout)


def planet_fields(rng: random.Random, star: float, fraction: float, period: float, e: float) -> Case:
    """One planet as the page's form would hold it, with its mass as a fraction of the stellar mass."""
    unit = rng.choice(["earth", "jupiter"])
    scale = MEARTH_IN_MSUN * (MJUP_IN_MEARTH if unit == "jupiter" else 1.0)
    mass = fraction * star / scale
    kind = "axis" if rng.random() < 0.3 else "period"
    orbit = period
    if kind == "axis":
        orbit = semimajor_axis_from_period(days_to_years(period), star + mass * scale)
    return {"mass": repr(mass), "unit": unit, "kind": kind, "orbit": repr(orbit), "e": repr(e)}


def random_case(rng: random.Random) -> Case:
    """A pair from close to very wide, in either order, with light to very heavy planets, circular to very eccentric."""
    star = 10 ** rng.uniform(-1.3, 0.8)
    period = 10 ** rng.uniform(-1, 4)
    if rng.random() < 1 / 6:
        # close giants on nearly circular orbits, the rare place where beta > 1 > beta_H: the critical AMD from
        # resonance overlap is below C_H
        ratio = rng.uniform(1.4, 1.9)
        fractions = [10 ** rng.uniform(-3.5, -2.5), 10 ** rng.uniform(-3.5, -2.5)]
        es = [rng.uniform(0, 0.06), rng.uniform(0, 0.03)]
    else:
        ratio = rng.choice(
            [
                1 + 10 ** rng.uniform(-5, -1),  # closer than any first-order resonance
                rng.uniform(1.05, 2.5),
                rng.uniform(1.85, 2.2),  # either side of the 2:1 resonance, the edge of the AMD domain
                10 ** rng.uniform(0.3, 5),
            ]
        )
        fractions = [10 ** rng.uniform(-9, math.log10(0.5)), 10 ** rng.uniform(-9, math.log10(0.5))]
        es = [
            rng.choice(
                [
                    0.0,
                    10 ** rng.uniform(-5, -1),
                    rng.uniform(0, 0.3),
                    rng.uniform(0, E_MAX),
                    rng.uniform(0, E_MAX),
                ]
            )
            for _ in range(2)
        ]
    planets = [
        planet_fields(rng, star, fractions[0], period, es[0]),
        planet_fields(rng, star, fractions[1], period * ratio, es[1]),
    ]
    rng.shuffle(planets)
    return {"star": repr(star), "a": planets[0], "b": planets[1]}


def realization_of(case: Case) -> Realization:
    """The nominal realization of a form's inputs: the arithmetic of data/files.py and sampling.realize."""
    star = float(case["star"])
    bodies = []
    for key in ("a", "b"):
        fields = case[key]
        m_earth = float(fields["mass"]) * (MJUP_IN_MEARTH if fields["unit"] == "jupiter" else 1.0)
        days = float(fields["orbit"])
        if fields["kind"] == "axis":
            days = years_to_days(period_from_semimajor_axis(days, star + m_earth * MEARTH_IN_MSUN))
        bodies.append(
            Body(key, mearth_to_msun(m_earth), days_to_years(days), float(fields["e"]), pomega=0.0, M=0.0)
        )
    bodies.sort(key=lambda b: b.P)
    return Realization(label="nominal", m_star=star, bodies=tuple(bodies))


@pytest.fixture(scope="module")
def pairs() -> list[tuple[Case, Case, Realization]]:
    """Seeded random cases, with the page's result and exostab's realization of each."""
    rng = random.Random(20261031)
    cases = [random_case(rng) for _ in range(N_PAIRS)]
    out = node("data.map((case_) => calc.calculate(case_))", cases)
    assert [o for o in out if "errors" in o] == []
    return [(case, o["result"], realization_of(case)) for case, o in zip(cases, out)]


@pytest.fixture(scope="module")
def printed(pairs: list[tuple[Case, Case, Realization]]) -> list[dict[str, str]]:
    """The text of each slot of the page, for each of the random cases."""
    out: list[dict[str, str]] = node(
        "data.map((case_) => calc.describe(calc.calculate(case_).result))", [case for case, _, _ in pairs]
    )
    return out


def agree(js: Any, py: float, floor: float = 0.0) -> bool:
    if math.isinf(py):
        return bool(js == "Infinity")
    return math.isclose(float(js), py, rel_tol=REL_TOL, abs_tol=floor)


def test_constants_are_those_of_the_package() -> None:
    constants = node("calc.constants")
    # from astropy, whose versions can round them differently
    assert constants.pop("MEARTH_IN_MSUN") == pytest.approx(MEARTH_IN_MSUN, rel=1e-14)
    assert constants.pop("MJUP_IN_MEARTH") == pytest.approx(MJUP_IN_MEARTH, rel=1e-14)
    assert constants.pop("DAY_IN_YR") == pytest.approx(DAY_IN_YR, rel=1e-14)
    assert constants.pop("G_SIM") == pytest.approx(G_SIM, rel=1e-14)
    assert constants.pop("E_MAX") == E_MAX
    assert constants.pop("RATIO_MAX") == hill._RATIO_MAX
    assert constants.pop("EQUIPARTITION") == amd.EQUIPARTITION
    assert constants.pop("R_MMR") == amd.R_MMR
    # computed from the same formula, and only the rounding of pow can differ
    assert constants.pop("ALPHA_2_1") == pytest.approx(amd.ALPHA_2_1, rel=1e-15)
    assert constants.pop("EPS_LIM") == pytest.approx(amd.EPS_LIM, rel=1e-14)
    assert constants == {}


def test_numbers_of_random_pairs_agree_with_the_python_functions(
    pairs: list[tuple[Case, Case, Realization]],
) -> None:
    wrong = []
    for case, result, real in pairs:
        inner, outer = real.bodies
        a1, a2 = (float(a) for a in real.semi_major_axes())
        row = hill.pair_table(real)[0]
        info = amd.analyse(real)
        pair = info["pairs"][0]
        gamma = pair["gamma"]
        # Rounding alone decides these beyond the tolerance, in Python as in JavaScript. The margin is a ratio
        # near 1, minus 1. C_H is a difference of terms of order gamma, and beta_H inherits its error. The
        # bisection for the circular limit looks for a margin that, for very unequal masses, is smaller than
        # rounding near its root. There the margin goes as gamma / (1 + gamma)^2 (a_2 / a_1 - 1)^2 and the
        # root as eps^(1/3), so the error of the limit goes as the mass ratio over eps^(2/3).
        margin_floor = 1e-13
        limit_floor = 1e-15 * max(gamma, 1 / gamma) / pair["epsilon"] ** (2 / 3)
        hill_floor = 1e-14 * (1 + gamma)
        beta_hill_floor = (
            pair["beta_hill"] * hill_floor / pair["critical_amd_hill"]
            if not math.isinf(pair["beta_hill"])
            else 0.0
        )
        expected: list[tuple[str, Any, float, float]] = [
            ("a1", result["bodies"][0]["a"], a1, 0.0),
            ("a2", result["bodies"][1]["a"], a2, 0.0),
            ("P1", result["bodies"][0]["P"], inner.P, 0.0),
            ("P2", result["bodies"][1]["P"], outer.P, 0.0),
            ("m1", result["bodies"][0]["m"], inner.m, 0.0),
            ("m2", result["bodies"][1]["m"], outer.m, 0.0),
            ("period_ratio", result["period_ratio"], outer.P / inner.P, 0.0),
            (
                "mutual_hill_radius",
                result["hill"]["mutual_hill_radius"],
                hill.mutual_hill_radius(inner.m, outer.m, a1, a2, real.m_star),
                0.0,
            ),
            ("separation_hill", result["hill"]["separation_hill"], row["separation_hill"], 0.0),
            ("gladman_margin", result["hill"]["gladman_margin"], row["gladman_margin"], margin_floor),
            (
                "gladman_critical_hill",
                result["hill"]["gladman_critical_hill"],
                row["gladman_critical_hill"],
                limit_floor,
            ),
            ("beta_star", result["amd"]["beta_star"], info["beta_star"], 0.0),
            ("beta_star_coplanar", result["amd"]["beta_star_coplanar"], info["beta_star_coplanar"], 0.0),
            (
                "alpha_resonance_switch",
                result["amd"]["alpha_resonance_switch"],
                amd.alpha_resonance_switch(pair["epsilon"]),
                0.0,
            ),
            ("critical_amd_hill", result["amd"]["critical_amd_hill"], pair["critical_amd_hill"], hill_floor),
            ("beta_hill", result["amd"]["beta_hill"], pair["beta_hill"], beta_hill_floor),
            (
                "beta_hill_coplanar",
                result["amd"]["beta_hill_coplanar"],
                pair["beta_hill_coplanar"],
                beta_hill_floor,
            ),
        ]
        for key in ("alpha", "gamma", "epsilon", "relative_amd", "critical_amd", "beta", "beta_coplanar"):
            expected.append((key, result["amd"][key], pair[key], 0.0))
        wrong += [(name, js, py, case) for name, js, py, floor in expected if not agree(js, py, floor)]
    assert wrong == []


def test_functions_on_both_sides_of_their_regimes_agree(
    pairs: list[tuple[Case, Case, Realization]],
) -> None:
    # Each result uses one branch of the critical AMD. Here both are compared for every pair.
    inputs = [
        [r["amd"]["alpha"], r["amd"]["gamma"], r["amd"]["epsilon"], *(b["e"] for b in r["bodies"])]
        for _, r, _ in pairs
    ]
    out = node(
        """data.map(([alpha, gamma, eps, e1, e2]) => ({
          relative_amd: calc.relativeAmd(e1, e2, alpha, gamma),
          critical_eccentricity: calc.criticalEccentricity(alpha, gamma),
          critical_amd_collision: calc.criticalAmdCollision(alpha, gamma),
          alpha_circular_overlap: calc.alphaCircularOverlap(eps),
          critical_amd_mmr: calc.criticalAmdMmr(alpha, gamma, eps),
          critical_amd: calc.criticalAmd(alpha, gamma, eps),
          outside_domain: calc.outsideDomain(alpha, eps),
        }))""",
        inputs,
    )
    wrong = []
    for (alpha, gamma, eps, e1, e2), js in zip(inputs, out):
        critical, branch = amd.critical_amd(alpha, gamma, eps)
        expected = {
            "relative_amd": amd.relative_amd(e1, e2, alpha, gamma),
            "critical_eccentricity": amd.critical_eccentricity(alpha, gamma),
            "critical_amd_collision": amd.critical_amd_collision(alpha, gamma),
            "alpha_circular_overlap": amd.alpha_circular_overlap(eps),
            "critical_amd_mmr": amd.critical_amd_mmr(alpha, gamma, eps),
        }
        wrong += [(k, js[k], py, alpha, gamma, eps) for k, py in expected.items() if not agree(js[k], py)]
        if not agree(js["critical_amd"][0], critical) or js["critical_amd"][1] != branch:
            wrong.append(("critical_amd", js["critical_amd"], (critical, branch), alpha, gamma, eps))
        if js["outside_domain"] != amd.outside_domain(alpha, eps):
            wrong.append(("outside_domain", js["outside_domain"], alpha, gamma, eps))
    assert wrong == []


# The first words of amd.evaluate's summary for each sentence of the page.
AMD_SUMMARIES = {
    "stable": "AMD-stable:",
    "outside_domain": "β < 1 for every pair",
    "weak": "Weakly AMD-stable",
    "hill_stable": "AMD-unstable (β",
    "neither_coplanar": "Neither AMD-stable",
    "neither": "Neither AMD-stable",
}


def test_verdicts_and_regimes_of_random_pairs_agree_exactly(
    pairs: list[tuple[Case, Case, Realization]],
) -> None:
    wrong = []
    for case, result, real in pairs:
        row = hill.pair_table(real)[0]
        pair = amd.analyse(real)["pairs"][0]
        expected = [
            (result["hill"]["verdict"], hill.classify(real).value),
            (result["hill"]["orbits_cross"], row["orbits_cross"]),
            (result["amd"]["verdict"], amd.classify(real).value),
            (result["amd"]["critical_branch"], pair["critical_branch"]),
            (result["amd"]["outside_domain"], pair["outside_domain"]),
            (result["amd"]["circular_overlap"], pair["circular_overlap"]),
            (result["swapped"], real.bodies[0].name == "b"),
            ([b["key"] for b in result["bodies"]], [b.name for b in real.bodies]),
        ]
        wrong += [(js, py, case) for js, py in expected if js != py]
        # the same sentence as amd.evaluate and hill.evaluate
        amd_summary = amd.evaluate(real, []).summary
        if not amd_summary.startswith(AMD_SUMMARIES[result["amd"]["summary"]]):
            wrong.append((result["amd"]["summary"], amd_summary, case))
        if ("even for exactly coplanar orbits" in amd_summary) != (
            result["amd"]["summary"] == "neither_coplanar"
        ):
            wrong.append((result["amd"]["summary"], amd_summary, case))
        if hill.evaluate(real, []).summary.startswith("Hill stable") != (
            result["hill"]["verdict"] == "stable"
        ):
            wrong.append((result["hill"], case))
    assert wrong == []


def test_the_random_pairs_reach_every_verdict_and_regime(
    pairs: list[tuple[Case, Case, Realization]],
) -> None:
    results = [r for _, r, _ in pairs]
    amd_rows = [r["amd"] for r in results]
    assert {r["hill"]["verdict"] for r in results} == {"stable", "unstable"}
    assert {p["verdict"] for p in amd_rows} == {"stable", "marginal", "unstable"}
    assert {p["summary"] for p in amd_rows} == set(AMD_SUMMARIES)
    assert {p["critical_branch"] for p in amd_rows} == {"collision", "mmr_overlap"}
    assert {p["outside_domain"] for p in amd_rows} == {None, "eps_above_limit", "wide_of_2_1"}
    assert {p["circular_overlap"] for p in amd_rows} == {True, False}
    assert {r["swapped"] for r in results} == {True, False}
    assert {p["beta"] == "Infinity" for p in amd_rows} == {True, False}
    assert {p["beta_hill"] == "Infinity" for p in amd_rows} == {True, False}
    assert {r["hill"]["orbits_cross"] for r in results} == {True, False}
    # the page says "inside the Gladman (1993) limit" of every pair the Hill indicator does not call stable
    assert all(r["hill"]["gladman_margin"] <= 0 for r in results if r["hill"]["orbits_cross"])
    masses = [b["m"] / r["m_star"] for r in results for b in r["bodies"]]
    assert min(masses) < 1e-7 and max(masses) > 0.1
    periods = [r["period_ratio"] for r in results]
    assert min(periods) < 1.001 and max(periods) > 1e4
    eccentricities = [b["e"] for r in results for b in r["bodies"]]
    assert min(eccentricities) == 0 and max(eccentricities) > 0.9


def test_the_inputs_mean_what_they_mean_in_a_yaml_file(
    pairs: list[tuple[Case, Case, Realization]], tmp_path: Path
) -> None:
    for number, (case, _, real) in enumerate(pairs[:200]):
        planets = []
        for key in ("a", "b"):
            fields = case[key]
            planets.append(
                {
                    "name": key,
                    "mass_jupiter" if fields["unit"] == "jupiter" else "mass_earth": float(fields["mass"]),
                    "semimajor_axis_au" if fields["kind"] == "axis" else "period_days": float(
                        fields["orbit"]
                    ),
                    "eccentricity": float(fields["e"]),
                }
            )
        path = tmp_path / f"{number}.yaml"
        path.write_text(
            yaml.safe_dump({"star": {"mass_msun": float(case["star"])}, "planets": planets}), encoding="utf-8"
        )
        nominal = realizations(load_system_file(path), 0, seed=0)[0]
        assert nominal.m_star == real.m_star
        assert [(b.name, b.m, b.P, b.e) for b in nominal.bodies] == [
            (b.name, b.m, b.P, b.e) for b in real.bodies
        ]


def test_numbers_read_as_in_the_reports(pairs: list[tuple[Case, Case, Realization]]) -> None:
    rng = random.Random(7)
    values = [rng.choice([-1, 1]) * 10 ** rng.uniform(-12, 12) for _ in range(500)]
    values += [0.0, 1.0, 100.0, 999.5, 0.0001, 0.00009999, 1e-5, 1e5, 123456.0, 1234567.0]
    for digits in (3, 4, 5, 6, 7):
        out = node(f"data.map((x) => calc.formatG(x, {digits}))", values)
        assert out == [format(x, f".{digits}g") for x in values]
    betas = [r["amd"][key] for _, r, _ in pairs[:500] for key in ("beta", "beta_star", "beta_hill")]
    out = node('data.map((x) => calc.formatBeta(x === "Infinity" ? Infinity : x))', betas)
    assert out == [amd._b(float(x)) for x in betas]


def test_every_result_fills_every_slot_of_the_page(printed: list[dict[str, str]]) -> None:
    slots = set(re.findall(r'data-calc="(\w+)"', PAGE.read_text(encoding="utf-8")))
    for texts in printed:
        assert slots <= set(texts)
        assert all(
            isinstance(text, str) and text and not re.search("NaN|Infinity|undefined", text)
            for text in texts.values()
        )


def test_the_page_prints_the_numbers_of_the_result(
    pairs: list[tuple[Case, Case, Realization]], printed: list[dict[str, str]]
) -> None:
    # The tests above compare the results with the Python functions. Here the digits are those of the result
    # in the formats of the reports, so rounding cannot make them differ between platforms.
    wrong = []
    for texts, (case, result, _) in zip(printed, pairs):
        inner, outer = result["bodies"]
        h, p = result["hill"], result["amd"]
        margin = h["gladman_margin"]
        expected = {
            "hill_verdict": h["verdict"],
            "amd_verdict": p["verdict"],
            "periods": f"{inner['days']:.7g} d, {outer['days']:.7g} d",
            "axes": f"{inner['a']:.7g} au, {outer['a']:.7g} au",
            "period_ratio": f"{result['period_ratio']:.6g}",
            "mutual_hill_radius": f"{h['mutual_hill_radius']:.4g} au",
            "separation_hill": f"{h['separation_hill']:.2f}",
            "gladman_critical_hill": f"{h['gladman_critical_hill']:.2f}",
            "gladman_margin": ("+" if margin > 0 else "−" if margin < 0 else "") + f"{abs(margin):.3g}",
            "orbits_cross": "yes" if h["orbits_cross"] else "no",
            "apsides": (
                f"Inner apocentre a₁(1 + e₁) = {inner['a'] * (1 + inner['e']):.5g} au; "
                f"outer pericentre a₂(1 − e₂) = {outer['a'] * (1 - outer['e']):.5g} au."
            ),
            "relative_amd": f"{p['relative_amd']:.3g}",
            "regime": "collision" if p["critical_branch"] == "collision" else "resonance overlap",
            "domain": "outside" if p["outside_domain"] else "inside",
        }
        for key in (
            "beta",
            "beta_coplanar",
            "beta_star",
            "beta_star_coplanar",
            "beta_hill",
            "beta_hill_coplanar",
        ):
            expected[key] = amd._b(float(p[key]))
        wrong += [(slot, texts[slot], text, case) for slot, text in expected.items() if texts[slot] != text]
    assert wrong == []


def sentences_of(result: Case) -> dict[str, str]:
    """How the page's sentences must begin for a result: the words of each verdict or regime, its numbers."""
    inner, outer = result["bodies"]
    h, p = result["hill"], result["amd"]
    if h["verdict"] == "stable":
        hill_sentence = (
            f"Hill stable: separation {h['separation_hill']:.2f} mutual Hill radii, above the Gladman (1993) "
            f"limit of {h['gladman_critical_hill']:.2f} for circular orbits (eccentricities included in the "
            "test). For two planets on coplanar orbits this is a rigorous sufficient condition"
        )
    else:
        crossing = " and its orbits can cross" if h["orbits_cross"] else ""
        hill_sentence = (
            f"Not Hill stable: this pair is inside the Gladman (1993) limit{crossing}, so close encounters "
            "are not excluded"
        )

    beta, beta_s, beta_h = (amd._b(float(p[key])) for key in ("beta", "beta_star", "beta_hill"))
    neither = f"Neither AMD-stable (β = {beta}) nor Hill stable (β_H = {beta_h})"
    beta_p, beta_hp = (amd._b(float(p[key])) for key in ("beta_coplanar", "beta_hill_coplanar"))
    coplanar = f"β_p = {beta_p}, β_H,p = {beta_hp}"
    to_the_star = f"; the AMD could also bring the inner planet to the star (β_S = {beta_s})."
    amd_sentence = {
        "stable": f"AMD-stable: β = {beta} and β_S = {beta_s}, so collisions are excluded",
        "outside_domain": (
            f"β = {beta} is below 1, but this pair lies outside the domain Petit et al. (2017) state for "
            "the critical AMD, so AMD stability is not claimed"
            f"{to_the_star if float(p['beta_star']) >= 1 else '.'}"
        ),
        "weak": (
            f"Weakly AMD-stable: no planet-planet collisions (β = {beta}), but the AMD could in principle "
            f"bring the inner planet to the star (β_S = {beta_s})."
        ),
        "hill_stable": f"AMD-unstable (β = {beta}) but Hill stable in the AMD framework (β_H = {beta_h})",
        "neither_coplanar": f"{neither}, even for exactly coplanar orbits ({coplanar})",
        "neither": (
            f"{neither} if the mutual inclinations carry as much AMD as the eccentricities; not 'unstable', "
            f"because the coplanar values ({coplanar}) are not both ≥ 1."
        ),
    }[p["summary"]]
    if p["summary"] == "stable" and inner["e"] == 0 and outer["e"] == 0:
        amd_sentence = "AMD-stable only because both eccentricities are 0"

    if p["critical_branch"] == "collision":
        regime = f"Here the collision regime: C_c = {p['critical_amd']:.3g} (Laskar & Petit 2017)."
    elif p["critical_amd"] == 0:
        regime = (
            "Here the resonance-overlap regime, and resonances overlap even for circular orbits: C_c = 0,"
        )
    else:
        regime = f"Here the resonance-overlap regime: C_c = {p['critical_amd']:.3g} (Petit et al. 2017)."

    alpha, alpha_r = f"α = {p['alpha']:.3g}", f"α_R = {p['alpha_resonance_switch']:.3g}"
    eps, lim = f"ε = {p['epsilon']:.3g}", f"ε_lim = {amd.EPS_LIM * 1e3:.2f}e-3"
    if p["outside_domain"] == "eps_above_limit":
        domain = f"{eps} is above {lim} and {alpha} is above {alpha_r}."
    elif p["outside_domain"] == "wide_of_2_1":
        domain = f"{alpha} is at or wide of the 2:1 resonance"
    elif p["epsilon"] > amd.EPS_LIM:
        domain = f"{eps} is above {lim}, but {alpha} is at or below {alpha_r},"
    elif p["critical_branch"] == "mmr_overlap":
        domain = f"Here {alpha} is above {alpha_r} and above the 2:1 resonance, and {eps} is at most {lim}."
    else:
        domain = f"Here {alpha} is at or below {alpha_r} for {eps},"

    first, second = inner["key"].upper(), outer["key"].upper()
    return {
        "order": (f"Swapped: planet {first}" if result["swapped"] else f"Planet {first}")
        + f" is the inner planet (index 1 below) and planet {second} the outer one (index 2)",
        "hill_sentence": hill_sentence,
        "amd_sentence": amd_sentence,
        "regime_text": regime,
        "domain_text": domain,
    }


def test_the_sentences_of_the_page_fit_the_result(
    pairs: list[tuple[Case, Case, Realization]], printed: list[dict[str, str]]
) -> None:
    wrong = []
    for texts, (case, result, _) in zip(printed, pairs):
        expected = sentences_of(result)
        wrong += [
            (slot, texts[slot], text, case)
            for slot, text in expected.items()
            if not texts[slot].startswith(text)
        ]
    assert wrong == []


def test_the_presets_are_what_the_page_says() -> None:
    presets = node("calc.PRESETS")
    page = PAGE.read_text(encoding="utf-8")
    assert re.findall(r'data-preset="([\w-]+)"', page) == list(presets)
    out = node(
        "Object.fromEntries(Object.entries(data).map(([k, v]) => [k, calc.calculate(v).result]))", presets
    )
    words = {k: (o["hill"]["verdict"], o["amd"]["verdict"], o["swapped"]) for k, o in out.items()}
    assert words == {
        "jupiter-saturn": ("stable", "stable", False),
        "kepler-36": ("stable", "stable", False),
        "gj-876": ("unstable", "marginal", True),
    }
    assert [o["amd"]["outside_domain"] for o in out.values()] == [None, None, "eps_above_limit"]
    assert [o["amd"]["critical_branch"] for o in out.values()] == ["collision", "mmr_overlap", "collision"]
    for name, fields in presets.items():
        real = realization_of(fields)
        assert out[name]["hill"]["verdict"] == hill.classify(real).value
        assert out[name]["amd"]["verdict"] == amd.classify(real).value
    assert out["kepler-36"]["amd"]["beta"] == 0
    # NASA's fact sheets, read on 31 October 2026
    assert presets["jupiter-saturn"] == {
        "star": "1",
        "a": {"mass": "317.83", "unit": "earth", "kind": "period", "orbit": "4332.589", "e": "0.0487"},
        "b": {"mass": "95.16", "unit": "earth", "kind": "period", "orbit": "10755.699", "e": "0.052"},
    }


@pytest.mark.parametrize(("preset", "host"), [("kepler-36", "Kepler-36"), ("gj-876", "GJ 876")])
def test_the_presets_from_the_snapshot_have_its_values(preset: str, host: str) -> None:
    fields = node("calc.PRESETS")[preset]
    system = load_system(host, offline=True)
    assert system.source.kind == "snapshot" and str(system.source.retrieved_utc).startswith("2026-09-28")
    assert float(fields["star"]) == system.star.mass_msun.value
    for key, letter in (("a", "b"), ("b", "c")):
        planet = system.planet(letter)
        assert fields[key]["unit"] == "earth" and fields[key]["kind"] == "period"
        assert float(fields[key]["mass"]) == planet.mass_earth.value
        assert float(fields[key]["orbit"]) == planet.period_days.value
        assert float(fields[key]["e"]) == planet.eccentricity.value


def test_the_page_states_the_test_it_has() -> None:
    assert f"on {N_PAIRS:,} seeded random pairs" in " ".join(PAGE.read_text(encoding="utf-8").split())


PLANET_A = {"mass": "10", "unit": "earth", "kind": "period", "orbit": "10", "e": "0"}
PLANET_B = {"mass": "10", "unit": "earth", "kind": "period", "orbit": "30", "e": "0"}


WRONG_INPUT: list[tuple[str, Case, Case, str | None, str]] = [
    ("", {}, {}, "star", "Stellar mass: enter a number"),
    ("abc", {}, {}, "star", '"abc" is not a number'),
    ("1,5", {}, {}, "star", "Write decimals with a point"),
    ("Infinity", {}, {}, "star", "is not a number"),
    ("1e999", {}, {}, "star", "too large"),
    ("0", {}, {}, "star", "Stellar mass must be above zero"),
    ("-1", {}, {}, "star", "Stellar mass must be above zero"),
    ("1", {"mass": ""}, {}, "a_mass", "Planet A mass: enter a number"),
    ("1", {"mass": "-3"}, {}, "a_mass", "Planet A mass must be above zero"),
    ("1", {"unit": ""}, {}, "a_unit", "choose Earth or Jupiter masses"),
    ("1", {}, {"unit": "saturn"}, "b_unit", "Planet B mass: choose"),
    ("1", {"orbit": "x"}, {}, "a_orbit", "Planet A period"),
    ("1", {"kind": "axis", "orbit": "0"}, {}, "a_orbit", "Planet A semi-major axis must be above zero"),
    ("1", {"e": ""}, {}, "a_e", "Planet A eccentricity: enter a number"),
    ("1", {"e": "-0.1"}, {}, "a_e", "between 0 and 0.95"),
    ("1", {}, {"e": "0.96"}, "b_e", "the largest exostab integrates"),
    ("0.001", {"mass": "10", "unit": "jupiter"}, {}, "a_mass", "not below the stellar mass"),
    # exactly the stellar mass: this text is the value of MEARTH_IN_MSUN in the page's code
    ("3.0034893488507934e-6", {"mass": "1"}, {"mass": "0.5"}, "a_mass", "not below the stellar mass"),
    # Just below the limit. The edges of the accepted input, further down, have 3.4e-7 just above it.
    ("1", {"mass": "3.3e-7"}, {}, "a_mass", "too small"),
    ("1", {"orbit": "30"}, {}, "b_orbit", "same period"),
    (
        "1",
        {"kind": "axis", "orbit": "1", "mass": "1"},
        {"kind": "axis", "orbit": "1"},
        "b_orbit",
        "same semi-major axis",
    ),
    ("1", {"orbit": "1e-200"}, {}, None, "too small or too large"),
    ("1", {}, {"orbit": "1e200"}, None, "too small or too large"),
    # Far beyond any star or orbit: Lambda overflows, Lambda underflows, the masses vanish and bisect finds no
    # root, the period ratio overflows, the semi-major axes round to the same value. No verdict may come of these.
    (
        "1e300",
        {"mass": "1e300", "unit": "jupiter", "orbit": "1e-100"},
        {"mass": "1e300", "unit": "jupiter", "orbit": "2e-100", "e": "0.1"},
        None,
        "too small or too large",
    ),
    (
        "1e-300",
        {"mass": "1e-300", "unit": "jupiter"},
        {"mass": "1e-300", "unit": "jupiter"},
        None,
        "too small or too large",
    ),
    ("1e-320", {"mass": "1e-320"}, {"mass": "1e-320"}, None, "too small or too large"),
    ("1", {"orbit": "1e-158"}, {"orbit": "1e155"}, None, "too small or too large"),
    (
        "1e-200",
        {"mass": "1e-201", "orbit": "1e-58"},
        {"mass": "1e-201", "orbit": "1.00001e-58"},
        None,
        "too small or too large",
    ),
]


def test_wrong_input_is_named() -> None:
    forms = [
        {"star": star, "a": {**PLANET_A, **a}, "b": {**PLANET_B, **b}} for star, a, b, _, _ in WRONG_INPUT
    ]
    out = node("data.map((fields) => calc.calculate(fields).errors)", forms)
    for (star, a, b, field, words), errors in zip(WRONG_INPUT, out):
        assert [e["field"] for e in errors] == [field], (star, a, b)
        assert words in errors[0]["message"], (star, a, b)


def test_values_at_any_magnitude_are_refused_or_read_well() -> None:
    rng = random.Random(42)

    def planet(star: float) -> Case:
        fraction = rng.choice([1e-12, 0.999999, 10 ** rng.uniform(-12, 0)])
        return {
            "mass": repr(fraction * star / MEARTH_IN_MSUN),
            "unit": "earth",
            "kind": rng.choice(["period", "axis"]),
            "orbit": repr(10 ** rng.uniform(-323, 308)),
            "e": rng.choice(["0", "0.01", "0.95"]),
        }

    stars = [10 ** rng.uniform(-323, 308) for _ in range(20000)]
    forms = [{"star": repr(star), "a": planet(star), "b": planet(star)} for star in stars]
    out = node(
        """data.map((fields) => {
          const { result } = calc.calculate(fields);
          return result ? [fields, result.amd.alpha, calc.describe(result)] : null;
        })""",
        forms,
    )
    answered = [o for o in out if o is not None]
    assert len(answered) > 1000
    wrong = [
        o
        for o in answered
        if not 0 < o[1] < 1 or any(re.search("NaN|Infinity|undefined", text) for text in o[2].values())
    ]
    assert wrong == []


def test_only_two_eccentricities_of_exactly_0_are_called_so() -> None:
    # 1e-9 is not 0, though the AMD rounds to 0: the sentence must not say that both are 0.
    forms = [{"star": "1", "a": {**PLANET_A, "e": e}, "b": {**PLANET_B, "e": e}} for e in ("0", "1e-9")]
    zero, tiny = node(
        "data.map((fields) => calc.describe(calc.calculate(fields).result).amd_sentence)", forms
    )
    assert zero.startswith("AMD-stable only because both eccentricities are 0")
    assert tiny.startswith("AMD-stable: β = 0 and β_S = 0")


def test_the_edges_of_the_accepted_input_give_a_result() -> None:
    forms = [{"star": "1", "a": {**PLANET_A, "e": "0.95"}, "b": {**PLANET_B, "e": " 0.5 "}}]
    # just below the mass of the star and just above the smallest mass, on either orbit and together
    heavy, light = {"mass": "1047", "unit": "jupiter"}, {"mass": "3.4e-7", "unit": "earth"}
    for a, b in ((heavy, {}), ({}, heavy), (light, {}), ({}, light), (heavy, light), (light, heavy)):
        forms.append({"star": "1", "a": {**PLANET_A, **a}, "b": {**PLANET_B, **b}})
    out = node("data.map((fields) => calc.calculate(fields))", forms)
    for fields, result in zip(forms, out):
        real = realization_of(fields)
        assert result["result"]["hill"]["verdict"] == hill.classify(real).value
        assert result["result"]["amd"]["verdict"] == amd.classify(real).value


def test_a_link_keeps_the_inputs() -> None:
    case = random_case(random.Random(1))
    for fields in (*node("calc.PRESETS").values(), case):
        assert node("calc.fieldsFromQuery(calc.queryFromFields(data))", fields) == fields
    # text as typed, also text that needs escaping or is wrong
    fields = {
        "star": "1&x=2",
        "a": {**PLANET_A, "mass": "<b>"},
        "b": {**PLANET_B, "kind": "axis", "e": "1e-3"},
    }
    assert node("calc.fieldsFromQuery(calc.queryFromFields(data))", fields) == fields


def test_a_link_can_be_partial() -> None:
    searches = ["", "?h=hill", "?star=1", "?a_mass=2&a_unit=jupiter&a_axis=0.5&a_period=10&b_axis=1&b_e=0.1"]
    empty, highlight, star, planets = node("data.map((search) => calc.fieldsFromQuery(search))", searches)
    assert empty is None and highlight is None  # search.highlight adds ?h=
    assert star["star"] == "1" and star["a"] == {**PLANET_A, "mass": "", "orbit": "", "e": ""}
    assert planets["star"] == ""
    assert planets["a"] == {"mass": "2", "unit": "jupiter", "kind": "period", "orbit": "10", "e": ""}
    assert planets["b"] == {"mass": "", "unit": "earth", "kind": "axis", "orbit": "1", "e": "0.1"}
    # what the link leaves out is named, not filled in
    errors = node("data.map((fields) => calc.calculate(fields).errors)", [star, planets])
    assert all(errors)
