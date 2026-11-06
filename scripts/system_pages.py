"""Write docs/systems/<row id>.md, one page per system of the stability catalog.

    python scripts/system_pages.py catalog/            # folder with catalog.csv and catalog_meta.json

The documentation workflow runs this before scripts/catalog_page.py, whose table links to these pages. The pages are
not committed. Without a catalog folder it writes nothing, and the site has no system pages.
"""

from __future__ import annotations

import csv
import json
import math
import re
import shutil
import sys
from pathlib import Path
from urllib.parse import quote

from exostab.data.names import other_names
from exostab.indicators import AGREEMENT

sys.path.insert(0, str(Path(__file__).resolve().parent))
from catalog_page import CSV_COLUMNS, RULES_VERSION, _num, _release, _row_id

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "systems"
OVERVIEW = "https://exoplanetarchive.ipac.caltech.edu/overview/"
BINDER = "https://mybinder.org/v2/gh/mimitoz62/exostab/main?urlpath="

# The completion rules in plain language; data-assumptions.md has the full table.
RULES = {
    "companion_stars_ignored": "The system has several stars; only the host star is modelled.",
    "controversial_planet": "A planet flagged as controversial in the archive is kept.",
    "coplanar_assumed": "All orbits are taken to lie in one plane.",
    "eccentricity_assumed_zero": "A missing eccentricity is taken as 0.",
    "eccentricity_fixed_zero_by_source": (
        "An eccentricity published as exactly 0 without an uncertainty is treated as missing, and taken as 0."
    ),
    "eccentricity_lower_limit": "An eccentricity given as a lower limit is used at the limit.",
    "eccentricity_upper_limit": "An eccentricity given as an upper limit is used at the limit, with draws below it.",
    "mass_estimated_by_archive": "A mass that the archive estimated from the radius is used.",
    "mass_from_msini_and_inclination": (
        "A mass that the archive computed from m sin i and a measured inclination is used as the true mass."
    ),
    "mass_from_radius_chen_kipping": "A missing mass comes from the radius, with the relation of Chen & Kipping (2017).",
    "mass_kind_unknown": "The archive's label for a mass is one exostab does not know; it is used as a true mass.",
    "mass_lower_limit": "A mass given as a lower limit is used at the limit.",
    "mass_upper_limit": "A mass given as an upper limit is used at the limit, with draws below it.",
    "minimum_mass": "A minimum mass (m sin i) is used as the mass.",
    "msini_of_transiting_planet": "The m sin i of a transiting planet is used as the true mass.",
    "omega_randomized": "A missing argument of periastron is drawn at random for every run.",
    "period_from_semimajor_axis": "A missing period comes from the semi-major axis, by Kepler's third law.",
    "period_lower_limit": "A period given as a lower limit is used at the limit.",
    "period_upper_limit": "A period given as an upper limit is used at the limit.",
    "phase_from_conjunction": "An orbital phase comes from a time of conjunction.",
    "phase_from_periastron": "An orbital phase comes from a time of periastron.",
    "phase_from_transit": "An orbital phase comes from a mid-transit time.",
    "phase_randomized": "A missing orbital phase is drawn at random for every run.",
    "phase_uncertain_at_epoch": "An orbital phase comes from a time so far from the common epoch that it is lost in the draws.",
    "planet_rows_missing": "The table has fewer rows for this star than the archive's count of its planets.",
    "star_mass_inconsistent": "The planet rows give different stellar masses, and one is chosen by a written rule.",
    "star_mass_limit_ignored": "A limit on the stellar mass is not used; a measured value from another row is.",
}

STABLE = "../findings.md#what-stable-means-here-and-what-it-does-not"
MEANING = {
    "stable": (
        "exostab calls this published parameter set stable under these settings: every indicator says stable and no "
        f"draw had a close encounter or escape. [It is not a proof]({STABLE}): the horizon is finite, the orbits are "
        "coplanar, and the verdict rests on the inputs and rules above."
    ),
    "marginal": (
        "exostab cannot call this published parameter set stable under these settings: for example, the indicators "
        "disagree, draws within the uncertainties behave differently, the run is too short for the outer planets, or an "
        "N-body instability rests on upper limits or on modelling one star of several. "
        f"[Marginal does not mean unstable]({STABLE})."
    ),
    "unstable": (
        "The run with the published values and at least 95% of the draws had a close encounter or escape. This is about "
        "this published parameter set under these settings, not a prediction for the planets: see "
        "[Published parameter sets that do not survive integration]"
        "(../findings.md#published-parameter-sets-that-do-not-survive-integration)."
    ),
    "inconclusive": (
        "At least one N-body run, the nominal run or a draw, could not be trusted, so exostab makes no statement on this "
        "published parameter set under these settings. This is not a verdict of stable or unstable."
    ),
}

# For a catalog with the report card's sentences, which _why prints above this text.
MARGINAL_WITH_REASONS = (
    "exostab cannot call this published parameter set stable under these settings, for the reasons above. "
    f"[Marginal does not mean unstable]({STABLE})."
)

CAVEATS = """The catalog checks each system it can model with the same settings, and with {draws} draws, one draw can change a
verdict ([how firm the verdicts are](../findings.md#how-firm-these-numbers-are)). A resonant system can look marginal or
unstable here although the full solution of one paper shows it is stable. The verdict describes the values in the archive's
composite table, which can combine several publications ([Data and assumptions](../data-assumptions.md))."""

# Hand-written notes for well-known systems, only from papers someone has read. They state what these runs show.
NOTES = {
    "TRAPPIST-1": """**About the real planets.** This page tests the archive's composite values, which for TRAPPIST-1 combine three
papers: periods and masses from [Agol et al. (2021)](https://doi.org/10.3847/psj/abd022), eccentricities and ω from
[Grimm et al. (2018)](https://doi.org/10.1051/0004-6361/201732233), and transit times from
[Ducrot et al. (2020)](https://doi.org/10.1051/0004-6361/201937392). What follows is about exostab's runs on the bundled snapshot (`--offline`) with seed 0, not a statement that the planets
are stable or unstable. Over 100,000 orbits of planet b (414 years) these values are chaotic in the nominal run and in all 20 draws, with
no close encounter or escape. The solution of one paper, Agol et al. (2021), in
[this file](https://github.com/mimitoz62/exostab/blob/main/examples/trappist1_agol2021.yaml), behaves differently: over the
same 414 years its nominal run and 19 of 20 draws are regular (18 and 20 of 20 with seeds 1 and 2), and its nominal run stays regular over 1,000,000 orbits
(about 4,100 years; seeds 0 to 3, WHFast). exostab's overall verdict for that file stays marginal, because Hill spacing does not depend on run
length.

Published dynamical studies run far longer. Agol et al. (2021) integrated 10,000
samples of their posterior for 10 Myr and report all of them stable. [Tamayo et al. (2017)](https://doi.org/10.3847/2041-8213/aa70ea)
find that about 42% of configurations drawn from the posterior then available become unstable within 5 Myr, against about 3%
of resonant configurations generated through disk migration; of 21 of the latter run to 50 Myr, four become unstable.""",
}

CITE = "## How to cite\n\nTo cite this page, use [the catalog's citation](../catalog.md#how-to-cite-the-catalog).\n"


def binder_url(system: str, row: dict[str, str] | None = None) -> str:
    """The web app on Binder with this system selected (the app's query parameter `system`, encoded for urlpath).

    With a row, the link also carries the row's settings, and the app starts the run by itself.
    """
    query = f"system={quote(system, safe='')}"
    if row is not None:
        query += f"&budget=60&seed={row['seed']}&orbits={float(row['orbits']):g}&draws={row['draws']}&run=1"
    return BINDER + quote(f"exostab/?{query}", safe="")


def _text(value: str) -> str:
    """Archive text safe to place in Markdown."""
    return re.sub(r"([\\`*_\[\]])", r"\\\1", value).replace("<", "&lt;")


def _verdict(value: str) -> str:
    return f'<span class="verdict-{value}">{value}</span>'


def _explain(column: str) -> str:
    """The meaning of a column from the catalog page's data dictionary, without what an empty value means."""
    text = re.sub(r" Empty without a verdict\.$", "", CSV_COLUMNS[column][1])
    return text.replace("`inf` (∞ on the pages) means", "∞ means")


def _front(system: str, names: list[str], title: str, summary: str) -> str:
    also = f" ({', '.join(names)})" if names else ""
    # JSON strings are valid YAML, whatever the name holds.
    title_yaml = json.dumps(f"{system}{also}: {title}", ensure_ascii=False)
    summary_yaml = json.dumps(f"{system}{also}: {summary}", ensure_ascii=False)
    return f"---\ntemplate: system.html\nsearch:\n  exclude: true\ntitle: {title_yaml}\ndescription: {summary_yaml}\n---\n"


def page(row: dict[str, str], meta: dict[str, object], systems: set[str]) -> str:
    """The Markdown of one system's page."""
    system = row["system"]
    names = other_names(system, filter(None, row["archive_rows"].split(";")), systems)
    date = str(meta["created_utc"])[:10]
    ok = row["status"] == "ok"
    if ok:
        title = "orbital stability verdicts"  # the site's template adds " - exostab" to the page's title
        call = (
            "makes no statement on this published parameter set"
            if row["overall"] == "inconclusive"
            else f"calls this published parameter set {row['overall']}"
        )
        summary = (
            f"exostab {call} under the settings of its catalog of {date}. "
            "Hill spacing, AMD and N-body verdicts with the numbers behind them."
        )
    else:
        title = "no verdict in the stability catalog"
        summary = (
            f"exostab's stability catalog of {date} has no verdict for this system, and gives the reason."
        )
    parts = [_front(system, names, title, summary), f"# {_text(system)}\n"]
    if names:
        parts.append(
            f"**Other names:** {', '.join(_text(n) for n in names)}. The catalog uses the archive's name.\n"
        )
    settings = (
        f"{float(row['orbits']):,.0f} orbits of the innermost planet, {row['draws']} draws within the published "
        f"uncertainties, seed {row['seed']}"
    )
    source = f"computed {date} with exostab {row['exostab_version']} from archive data of {row['data_retrieved_utc'][:10]}"
    if ok:
        parts.append(
            f"From [exostab's stability catalog](../catalog.md#{_row_id(system)}), {source}. "
            f"Settings: {settings}, a horizon of {_num(row['t_end_yr'], ',.0f')} years.\n"
        )
    else:
        parts.append(f"From [exostab's stability catalog](../catalog.md#{_row_id(system)}), {source}.\n")
    if _release(row["exostab_version"]) < RULES_VERSION:
        parts.append(
            f'!!! note "This catalog was computed with earlier rules"\n    exostab {_text(row["exostab_version"])} '
            "is a version whose verdict rules differ from those described in [Methods](../methods.md).\n"
        )
    parts.append(_verdicts(row, settings) if ok else _no_verdict(row))
    if ok or row["status"] == "timeout":
        parts.append(
            "## Run it yourself\n\nWith the catalog's settings, on the archive's current table:\n\n"
            f'```bash\nexostab check "{system}" --draws 10\n```\n\n'
            "The numbers can differ with the archive's table, the platform and the software versions; chaotic runs are "
            "sensitive to these.\n\n"
            "This needs exostab installed: see the [Quickstart](../quickstart.md#install), or its "
            "[one-line uvx command](../quickstart.md#try-it-without-installing).\n\n"
            + _binder_sentence(row, ok)
        )
    parts.append(
        f"## At the archive\n\n[{_text(system)} at the NASA Exoplanet Archive]({OVERVIEW}{quote(system)}).\n"
    )
    parts.append(CITE)
    return "\n".join(parts)


def _binder_sentence(row: dict[str, str], ok: bool) -> str:
    system = row["system"]
    if not ok:  # a row over the time limit must not start a run by itself
        return (
            f"Or [open it in the web app on Binder]({binder_url(system)}), which runs the latest release; the first "
            "start can take some minutes. The app has its own run length, so its verdict can differ.\n"
        )
    return (
        f"Or [open it in the web app on Binder]({binder_url(system, row)}), with the catalog's run length and draws; "
        "the run starts by itself once the session opens, and the first start can take some minutes. The app runs the "
        "latest release on the archive's current table. If that run would take too long on the server, the app says so "
        "and chooses a shorter one, and a shorter run can change the N-body verdict.\n"
    )


def _no_verdict(row: dict[str, str]) -> str:
    what = "was over the time limit" if row["status"] == "timeout" else f"is listed as {row['status']}"
    rows, them = ("planet row", "it") if row["n_planets"] == "1" else ("planet rows", "them")
    return (
        f"## No verdict\n\nThis system {what} in this catalog, so it has no verdict.\n\n"
        f"**Reason:** {_text(row['reason'])}\n\n"
        f"The host has {row['n_planets']} {rows} in the archive's table. This says what exostab could do with "
        f"{them}, not whether the system is stable. "
        "[Data and assumptions](../data-assumptions.md#completion-rules) lists what exostab rejects.\n"
    )


def _card_sentence(text: str) -> str:
    """A report card's sentence for a page, which has no notes of its own to point to."""
    return _text(re.sub(r"see the (N-body )?notes", r"see the \1notes of exostab check", text))


def _why(row: dict[str, str]) -> str:
    """The card's own sentences for this row; nothing for a catalog built before they were columns."""
    if not row.get("overall_summary"):
        return ""
    lines = ["## Why this verdict\n"]
    if row["hill"] != "stable":
        lines.append(f"- **Hill spacing, for the published values:** {_card_sentence(row['hill_summary'])}")
    if row["amd"] != "stable":
        lines.append(f"- **AMD, for the published values:** {_card_sentence(row['amd_summary'])}")
    lines.append(f"- **Overall:** {_card_sentence(row['overall_summary'])}")
    lines.append("")
    n = int(row["draws"])
    if n:
        lines.append(
            f"An indicator's verdict for the published values stands only if at least {AGREEMENT:.0%} of the draws share "
            f"it: with {n} draws, {math.ceil(AGREEMENT * n)} of {n}.\n"
        )
    # A nominal run stopped by a close encounter has no such label. An unstable N-body verdict rests on that, an
    # inconclusive one on a run that was not trusted, and in a marginal one it can be so: the CSV does not record it.
    if row["nbody"] in ("stable", "marginal") and 2.1 <= float(row.get("megno_nominal") or "nan") < 2.3:
        lines.append(
            "The nominal run's ⟨Y⟩ is close to the threshold of 2.2. Unless that run was stopped by a close encounter, "
            "its label of regular or chaotic can change with the seed or the platform this close to it, so it is not "
            "firm.\n"
        )
    return "\n".join(lines) + "\n"


def _meaning(row: dict[str, str]) -> str:
    if row["overall"] == "marginal" and row.get("overall_summary"):
        return MARGINAL_WITH_REASONS
    return MEANING.get(row["overall"], "")


def _verdicts(row: dict[str, str], settings: str) -> str:
    # What separates a pair on this page from the same pair in the calculator, which looks at two planets alone.
    try_pair = "Try a pair in the [calculator](../calculator.md)"
    if int(row["n_planets"]) >= 3:
        try_pair += (
            ", which looks at two planets alone: with three or more, exostab also asks for at least 12 mutual Hill radii, "
            "a heuristic, so the calculator can call stable a pair that is marginal here"
        )
    table = [
        "## Verdicts\n",
        "| Indicator | Verdict | Number | What the number means |",
        "|---|---|---|---|",
        f"| Overall | {_verdict(row['overall'])} | — | Combines the three, by the rule in "
        "[Methods](../methods.md#step-3-the-overall-verdict). |",
        f"| [Hill spacing](../reading-a-report.md#hill-spacing) | {_verdict(row['hill'])} | {_num(row['hill_min_separation'], '.2f')} mutual Hill radii | "
        f"{_explain('hill_min_separation')} {try_pair}. |",
        f"| [Angular momentum deficit (AMD)](../reading-a-report.md#angular-momentum-deficit-amd) | "
        f"{_verdict(row['amd'])} | β = {_num(row['amd_beta_max'], '.3g')} | {_explain('amd_beta_max')} |",
        f"| [N-body and MEGNO](../reading-a-report.md#n-body-integration-and-megno) | {_verdict(row['nbody'])} | ⟨Y⟩ = {_num(row['megno_nominal'], '.3f')} | "
        f"{_explain('megno_nominal')} |",
        "",
        f"**Draws** ({row['draws']}): {row['nbody_regular']} regular, {row['nbody_chaotic']} chaotic, "
        f"{row['nbody_unstable']} with a close encounter or escape, {row['nbody_inconclusive']} inconclusive.\n",
        f"**Largest energy error of the nominal run:** {_num(row['energy_error_nominal'], '.1e')} (relative).\n",
        _why(row),
        "## Planets\n",
        ", ".join(_text(n) for n in row["archive_rows"].split(";")) + "\n",
        "## Completion rules applied\n",
        "exostab fills gaps in the archive's values by written rules "
        "([Data and assumptions](../data-assumptions.md#completion-rules)). For this system:\n",
    ]
    for rule in filter(None, row["completion_rules"].split(";")):
        table.append(f"- {RULES.get(rule, 'See Data and assumptions.')} (`{rule}`)")
    table += [
        "",
        "## What the verdict means\n",
        _meaning(row) + "\n",
        CAVEATS.format(draws=row["draws"]) + "\n",
        *([NOTES[row["system"]] + "\n"] if row["system"] in NOTES else []),
        "[How to read a report card](../reading-a-report.md) explains these indicators and verdicts step by step.\n",
    ]
    return "\n".join(table)


def write_all(folder: Path) -> int:
    rows = list(csv.DictReader((folder / "catalog.csv").open(encoding="utf-8")))
    meta = json.loads((folder / "catalog_meta.json").read_text(encoding="utf-8"))
    systems = {r["system"] for r in rows}
    shutil.rmtree(OUT, ignore_errors=True)
    OUT.mkdir(parents=True)
    for row in rows:
        (OUT / f"{_row_id(row['system'])}.md").write_text(page(row, meta, systems), encoding="utf-8")
    return len(rows)


def main() -> None:
    folder = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    if folder is None or not (folder / "catalog.csv").exists():
        print("no catalog folder: no system pages written")
        return
    print(f"wrote {write_all(folder)} pages to {OUT}")


if __name__ == "__main__":
    main()
