"""Write docs/systems/<row id>.md, one page per system of the stability catalog.

    python scripts/system_pages.py catalog/            # folder with catalog.csv and catalog_meta.json

The documentation workflow runs this before scripts/catalog_page.py, whose table links to these pages. The pages are
not committed. Without a catalog folder it writes nothing, and the site has no system pages.
"""

from __future__ import annotations

import csv
import json
import re
import shutil
import sys
from pathlib import Path
from urllib.parse import quote

from exostab.data.names import other_names

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

CAVEATS = """The catalog checks each system it can model with the same settings, and with {draws} draws, one draw can change a
verdict ([how firm the verdicts are](../findings.md#how-firm-these-numbers-are)). A resonant system can look marginal or
unstable here although the full solution of one paper shows it is stable. The verdict describes the values in the archive's
composite table, which can combine several publications ([Data and assumptions](../data-assumptions.md))."""


def binder_url(system: str) -> str:
    """The web app on Binder with this system selected (the app's query parameter `system`, encoded for urlpath)."""
    return BINDER + quote(f"exostab/?system={quote(system, safe='')}", safe="")


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
        title = "orbital stability verdicts from exostab"
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
        title = "no verdict in the exostab catalog"
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
            f"Or [open it in the web app on Binder]({binder_url(system)}), which runs the latest release; the first "
            "start can take some minutes. The app has its own run length, so its verdict can differ.\n"
        )
    parts.append(
        f"## At the archive\n\n[{_text(system)} at the NASA Exoplanet Archive]({OVERVIEW}{quote(system)}).\n"
    )
    return "\n".join(parts)


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


def _verdicts(row: dict[str, str], settings: str) -> str:
    table = [
        "## Verdicts\n",
        "| Indicator | Verdict | Number | What the number means |",
        "|---|---|---|---|",
        f"| Overall | {_verdict(row['overall'])} | — | Combines the three, by the rule in "
        "[Methods](../methods.md#step-3-the-overall-verdict). |",
        f"| Hill spacing | {_verdict(row['hill'])} | {_num(row['hill_min_separation'], '.2f')} mutual Hill radii | "
        f"{_explain('hill_min_separation')} |",
        f"| AMD | {_verdict(row['amd'])} | β = {_num(row['amd_beta_max'], '.3g')} | {_explain('amd_beta_max')} |",
        f"| N-body | {_verdict(row['nbody'])} | ⟨Y⟩ = {_num(row['megno_nominal'], '.3f')} | "
        f"{_explain('megno_nominal')} |",
        "",
        f"**Draws** ({row['draws']}): {row['nbody_regular']} regular, {row['nbody_chaotic']} chaotic, "
        f"{row['nbody_unstable']} with a close encounter or escape, {row['nbody_inconclusive']} inconclusive.\n",
        f"**Largest energy error of the nominal run:** {_num(row['energy_error_nominal'], '.1e')} (relative).\n",
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
        MEANING.get(row["overall"], "") + "\n",
        CAVEATS.format(draws=row["draws"]) + "\n",
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
