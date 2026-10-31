---
template: home.html
title: Orbital stability for known exoplanet systems
description: >-
  exostab estimates the orbital stability of known multi-planet systems with Hill spacing, the angular momentum
  deficit and N-body integrations with MEGNO, propagates the published uncertainties and shows every assumption.
hide:
  - navigation
  - toc
---

<!-- The hero (logo, title, buttons, install line and terminal recording) is in overrides/home.html. -->

## Three indicators, one conservative verdict

Stability cannot be proven for more than two planets, so exostab asks the question in three different ways and
reports all three answers side by side. When they disagree, it says so instead of picking the most comfortable
answer.
{ .exo-lead }

<div class="grid cards exo-grid-2" markdown>

-   :material-orbit:{ .lg .middle } __Hill spacing__

    ---

    The Gladman (1993) criterion for two planets, in its form for eccentric orbits, and for three or more the
    spacing heuristic of Chambers et al. (1996) with the eccentricity-dependent requirement of Pu & Wu (2015).

    [:octicons-arrow-right-24: Methods](methods.md)

-   :material-scale-balance:{ .lg .middle } __Angular momentum deficit__

    ---

    Is there enough AMD for two orbits to cross? Laskar & Petit (2017), with the resonance-overlap and Hill
    refinements of Petit, Laskar & Boué (2017, 2018).

    [:octicons-arrow-right-24: Methods](methods.md)

-   :material-chart-timeline-variant:{ .lg .middle } __N-body integration and MEGNO__

    ---

    Direct integration with REBOUND's WHFast, repeated with IAS15 as a check, and the MEGNO chaos indicator
    to tell regular from chaotic motion.

    [:octicons-arrow-right-24: Methods](methods.md)

-   :material-robot-outline:{ .lg .middle } __SPOCK, optional__

    ---

    The machine-learned classifier of Tamayo et al. (2020) for systems of three or more planets, run in its own
    environment with `--spock`. It can make the verdict marginal, never unstable on its own.

    [:octicons-arrow-right-24: Methods](methods.md)

</div>

## Built to be traced and reproduced

<div class="grid cards" markdown>

-   :material-clipboard-text-search-outline:{ .lg .middle } __Every assumption shown__

    ---

    Gaps in the archive are filled by explicit rules. Every value carries its provenance, and every rule that
    fires is printed on the report card and stored in `report.json`.

    [:octicons-arrow-right-24: Data and assumptions](data-assumptions.md)

-   :material-dice-multiple-outline:{ .lg .middle } __Uncertainties propagated__

    ---

    Seeded Monte Carlo draws within the published error bars. An indicator's verdict stands only if at least
    95% of the draws agree with the nominal one.

    [:octicons-arrow-right-24: Methods](methods.md)

-   :material-shield-check-outline:{ .lg .middle } __A conservative verdict__

    ---

    *Stable* only if every indicator agrees and no N-body draw has a close encounter; *unstable* only if the
    integration shows close encounters or escapes for the nominal values and at least 95% of the draws, no
    input is only an upper limit, and the system has a single star. Mixed evidence is reported as *marginal*,
    with the reason.

    [:octicons-arrow-right-24: Methods](methods.md)

-   :material-replay:{ .lg .middle } __Reproducible__

    ---

    The same seed gives the same draws. `report.json` records the seed, the software versions, the integrator
    settings and the archive download date.

    [:octicons-arrow-right-24: Validation](validation.md)

-   :material-check-decagram-outline:{ .lg .middle } __Validated__

    ---

    Energy conservation, the Hill limit, TRAPPIST-1, GJ 876, Kepler-11 and a reproduction of the HD 127195
    Research Note run nightly in continuous integration.

    [:octicons-arrow-right-24: Validation](validation.md)

-   :material-console-line:{ .lg .middle } __Command line, web app, catalog__

    ---

    `exostab check` for one system and `exostab sweep` for "what if" scans, a Streamlit app with sliders, and a
    weekly catalog of the archive's multi-planet systems.

    [:octicons-arrow-right-24: Catalog](catalog.md)

</div>

## Get started

=== "No install"

    The [stability catalog](catalog.md) needs nothing: look up a system in the table of the archive's multi-planet
    systems, recomputed every week. [What the catalog shows](findings.md) describes its results and how
    firm they are.

    To run exostab itself in a browser, use
    [Google Colab](https://colab.research.google.com/github/mimitoz62/exostab/blob/main/examples/exostab_quickstart.ipynb)
    (needs a Google account), [GitHub Codespaces](https://codespaces.new/mimitoz62/exostab?quickstart=1) (needs a
    GitHub account and uses your free monthly hours) or
    [Binder](https://mybinder.org/v2/gh/mimitoz62/exostab/main?urlpath=exostab/) (needs no account; the first start
    can take several minutes, and the session ends after 10 minutes without activity). More in the
    [Quickstart](quickstart.md#try-it-without-installing).

=== "Command line"

    ```bash
    python3 --version
    python3 -m venv .venv
    source .venv/bin/activate
    pip install "exostab @ git+https://github.com/mimitoz62/exostab@v1.0.0"
    exostab check "TRAPPIST-1"
    exostab list --min-planets 4 --max-period-days 200
    ```

    You need Python 3.10 or newer: the first line shows your version, and `/usr/bin/python3` on macOS is 3.9. The
    `pip` line needs git; the [Quickstart](quickstart.md#install) has the form without git. Names are the archive's, for example KOI-351 (Kepler-90), GJ 876 (Gliese 876), ups And (Upsilon Andromedae) and 55 Cnc
    (55 Cancri); `exostab list` shows them. The first `check` downloads the archive's multi-planet table once
    (about 2,700 rows) and caches it; `--offline` uses a bundled snapshot of 22 well-known systems. A package on
    PyPI is planned; until then, install from GitHub.

=== "Web app"

    In the virtual environment from the [Quickstart](quickstart.md#install):

    ```bash
    pip install "exostab[web] @ git+https://github.com/mimitoz62/exostab@v1.0.0"
    python -m exostab.web
    ```

    If Streamlit asks for an email address, press Enter. Then open <http://localhost:8501>. Search a system, edit
    its parameters, try "what if" changes with sliders, choose a time budget, and download the report or a
    shareable link to the run. There is no permanent hosted version: the app runs on your own computer, or for a
    while on Binder or GitHub Codespaces, as the [Quickstart](quickstart.md#try-it-without-installing) describes.
    More in [Web app](web.md).

=== "Your own parameters"

    ```bash
    curl -fsSLO https://raw.githubusercontent.com/mimitoz62/exostab/v1.0.0/examples/two_planet.yaml
    exostab check --from-file two_planet.yaml
    exostab sweep "HD 127195" --planet b --param e --range 0 0.6 --steps 25
    ```

    A YAML file describes a system the archive does not have, or a published solution you want to test; the
    example above shows every key, and the repository's
    [`examples/`](https://github.com/mimitoz62/exostab/tree/main/examples) folder has a second one. `sweep`
    varies one parameter of one planet and records every indicator.

[Quickstart](quickstart.md){ .md-button .md-button--primary }
[CLI reference](cli.md){ .md-button }

## What a check gives you

A report card in the terminal, like the one in the recording above, and three files: `report.json`, `orbits.png`
and `megno.png`. The excerpt below is from `exostab check "TRAPPIST-1" --offline` (bundled archive snapshot of
2026-09-28, default settings).
{ .exo-lead }

??? example "`report.json`, selected keys"

    ```json
    {
      "schema_version": "1.3",
      "data": {
        "source": "snapshot",
        "table": "pscomppars",
        "retrieved_utc": "2026-09-28T13:57:30+00:00"
      },
      "system": {
        "planets": [
          {
            "name": "TRAPPIST-1 b",
            "eccentricity": {
              "value": 0.00622,
              "err_plus": 0.00304,
              "err_minus": 0.00304,
              "provenance": "measured",
              "reference": "Grimm et al. 2018",
              "reference_url": "https://ui.adsabs.harvard.edu/abs/2018A&A...613A..68G/abstract"
            }
          }
        ],
        "flags": [
          {
            "planet": "TRAPPIST-1 b",
            "parameter": "pl_tranmid",
            "rule": "phase_from_transit",
            "message": "Orbital phase set from the transit mid-time, propagated with the period (transit time and period come from different publications)."
          }
        ]
      },
      "settings": {
        "seed": 0,
        "orbits": 10000.0,
        "draws": 20,
        "integrator": "whfast",
        "check_integrator": "ias15",
        "megno_threshold": 2.2,
        "energy_error_max": 1e-05
      },
      "software": {
        "exostab": "1.0.0",
        "rebound": "5.2.0",
        "numpy": "2.5.3",
        "python": "3.12.11"
      },
      "overall": {
        "verdict": "marginal",
        "reasons": [
          "Hill spacing: marginal",
          "N-body + MEGNO: marginal"
        ]
      }
    }
    ```

## How it works

<div class="exo-steps" markdown>

<div class="exo-step" markdown>
__Fetch__

The NASA Exoplanet Archive's composite table (`pscomppars`), downloaded once and cached; a bundled snapshot of
22 systems offline; or your own YAML file.
</div>

<div class="exo-step" markdown>
__Complete__

Explicit rules fill the gaps. Each value is tagged measured, derived, assumed, estimated, randomized or upper
limit, and each rule adds a flag.
</div>

<div class="exo-step" markdown>
__Sample and integrate__

The nominal parameters and seeded Monte Carlo draws go through the Hill, AMD and N-body indicators, in
parallel worker processes.
</div>

<div class="exo-step" markdown>
__Report__

A conservative overall verdict, the report card, `report.json`, `orbits.png` and `megno.png`.
</div>

</div>

[:octicons-arrow-right-24: Read the methods](methods.md)

## What the verdicts mean

<div class="exo-verdicts" markdown>

<div class="exo-verdict exo-verdict--stable" markdown>
:material-check-circle-outline: __stable__
{ .exo-verdict__name }

The indicator's condition for stability holds for the nominal parameters and for at least 95% of the draws.
</div>

<div class="exo-verdict exo-verdict--marginal" markdown>
:material-scale-unbalanced: __marginal__
{ .exo-verdict__name }

Borderline, or the draws within the uncertainties disagree with the nominal parameters.
</div>

<div class="exo-verdict exo-verdict--unstable" markdown>
:material-close-circle-outline: __unstable__
{ .exo-verdict__name }

The indicator predicts instability for the nominal parameters and for at least 95% of the draws.
</div>

<div class="exo-verdict exo-verdict--inconclusive" markdown>
:material-help-circle-outline: __inconclusive__
{ .exo-verdict__name }

The indicator could not be evaluated reliably, for example because the integration's energy error was too
large.
</div>

</div>

The Hill and AMD criteria are *sufficient* conditions or heuristics: failing them means stability is not guaranteed,
not that the system falls apart. With the published four-planet solution of Rivera et al. (2010), GJ 876 is unstable by
Hill spacing and marginal by AMD, yet every N-body draw is regular, because its planets are locked in a resonance.

## Validated against physics and reference results

<div class="exo-stats" markdown>

<div class="exo-stat" markdown>
<span class="exo-stat__value">1.44 × 10⁻⁹</span>
Relative energy error of the inner Solar System over 10,000 years with WHFast (test limit 10⁻⁷).
</div>

<div class="exo-stat" markdown>
<span class="exo-stat__value">3.4624</span>
Mutual Hill radii: the Gladman limit for two planets of 10⁻⁵ M☉ on circular orbits around a solar-mass star
(it tends to 2√3 = 3.4641 for small masses).
</div>

<div class="exo-stat" markdown>
<span class="exo-stat__value">20 / 20</span>
Regular N-body draws for GJ 876 with the published four-planet solution of Rivera et al. (2010).
</div>

<div class="exo-stat" markdown>
<span class="exo-stat__value">133 / 200</span>
Regular draws for HD 127195 with the inputs of the Research Note (submitted, not yet published), which found
134 / 200.
</div>

</div>

These numbers come from `python scripts/validation_summary.py` (31 October 2026, macOS). The suite runs nightly in
continuous integration.

[:octicons-arrow-right-24: Full validation, with tolerances and versions](validation.md)

## Know the limits

!!! note "What a verdict does not tell you"

    - **Finite horizon.** The default run is 10,000 orbits of the innermost planet (41.4 years for TRAPPIST-1,
      14,634 years for HD 127195). "No chaos detected" over that span is not proof of stability over billions
      of years.
    - **Coplanar orbits.** Mutual inclinations are almost never measured, so all orbits are placed in one plane.
    - **Independent draws.** Parameters are drawn independently from their error bars, ignoring the
      correlations in the published posteriors.
    - **Not modelled.** Tides, general relativity, stellar evolution and companion stars. Circumbinary systems
      are rejected.

    The [methods](methods.md) and the [FAQ](faq.md) explain each choice.

## Cite exostab

If exostab helps your work, please cite the software, the methods behind the indicators you report and the
NASA Exoplanet Archive. [Citing exostab](citing.md) has a BibTeX entry and the list of references.
What changed in each release is in the [changelog](changelog.md).

<p class="exo-meta">
exostab is free and open-source software under the MIT License, written by
Mehmet Öz (<a href="https://orcid.org/0009-0007-1005-7640">ORCID 0009-0007-1005-7640</a>).
Questions, bug reports and requests for systems are welcome on
<a href="https://github.com/mimitoz62/exostab/issues">GitHub</a>.
</p>
