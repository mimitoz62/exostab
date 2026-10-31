<h1 align="center">
  <a href="https://github.com/mimitoz62/exostab">
    <picture>
      <source media="(prefers-color-scheme: dark)" srcset="https://raw.githubusercontent.com/mimitoz62/exostab/main/docs/assets/logo/logo-dark.svg">
      <img alt="exostab" src="https://raw.githubusercontent.com/mimitoz62/exostab/main/docs/assets/logo/logo-light.svg" width="300">
    </picture>
  </a>
</h1>

<p align="center">
  <b>Is this planetary system dynamically stable?</b><br>
  A quick, traceable first answer for known multi-planet systems:<br>
  three indicators side by side, published uncertainties propagated, every assumption shown.
</p>

<p align="center">
  <a href="https://github.com/mimitoz62/exostab/actions/workflows/ci.yml"><img alt="Tests" src="https://img.shields.io/github/actions/workflow/status/mimitoz62/exostab/ci.yml?branch=main&amp;label=tests"></a>
  <a href="https://github.com/mimitoz62/exostab/actions/workflows/nightly.yml"><img alt="Nightly validation" src="https://img.shields.io/github/actions/workflow/status/mimitoz62/exostab/nightly.yml?branch=main&amp;label=validation"></a>
  <a href="https://mimitoz62.github.io/exostab/"><img alt="Documentation" src="https://img.shields.io/github/actions/workflow/status/mimitoz62/exostab/docs.yml?branch=main&amp;label=docs"></a>
  <a href="https://doi.org/10.5281/zenodo.23844658"><img alt="DOI" src="https://zenodo.org/badge/DOI/10.5281/zenodo.23844658.svg"></a>
  <a href="https://github.com/mimitoz62/exostab/releases"><img alt="Latest release" src="https://img.shields.io/github/v/release/mimitoz62/exostab?label=release"></a>
  <a href="https://github.com/mimitoz62/exostab/blob/main/pyproject.toml"><img alt="Python 3.10–3.14" src="https://img.shields.io/badge/python-3.10%E2%80%933.14-blue"></a>
  <a href="https://github.com/mimitoz62/exostab/blob/main/LICENSE"><img alt="License: MIT" src="https://img.shields.io/badge/license-MIT-blue"></a>
</p>

<p align="center">
  <a href="https://mimitoz62.github.io/exostab/"><b>Documentation</b></a> ·
  <a href="https://github.com/mimitoz62/exostab#quickstart"><b>Quickstart</b></a> ·
  <a href="https://mimitoz62.github.io/exostab/methods/"><b>Methods</b></a> ·
  <a href="https://github.com/mimitoz62/exostab#validation-at-a-glance"><b>Validation</b></a> ·
  <a href="https://mimitoz62.github.io/exostab/catalog/"><b>Catalog</b></a> ·
  <a href="https://github.com/mimitoz62/exostab#citing-exostab"><b>Cite</b></a>
</p>

<p align="center">
  Try it without installing:
  <a href="https://mimitoz62.github.io/exostab/catalog/">look up a system in the catalog</a> ·
  <a href="https://colab.research.google.com/github/mimitoz62/exostab/blob/main/examples/exostab_quickstart.ipynb">run it in Colab</a> ·
  <a href="https://mybinder.org/v2/gh/mimitoz62/exostab/main?urlpath=exostab/">open the web app on Binder</a>
</p>

<p align="center">
  <img alt="Terminal recording of exostab check &quot;TRAPPIST-1&quot; --offline: a report card with the parameters of the seven planets, Hill spacing marginal, AMD stable, N-body + MEGNO marginal, overall verdict marginal, and the data-completion rules that were applied" src="https://raw.githubusercontent.com/mimitoz62/exostab/main/docs/assets/demo.gif" width="720">
  <br>
  <sub><i>Real output of <code>exostab check "TRAPPIST-1" --offline</code> (bundled archive snapshot of 2026-09-28,
  default settings), rendered by <a href="https://github.com/mimitoz62/exostab/blob/main/scripts/make_demo_gif.py">scripts/make_demo_gif.py</a>.
  Nothing in the image is edited by hand.</i></sub>
</p>

## What exostab answers

Name a known multi-planet system, and exostab tells you whether its planets are likely to keep their orbits, and
how firmly the data support that answer.

It takes the system's parameters from the [NASA Exoplanet Archive](https://exoplanetarchive.ipac.caltech.edu/)
(the Planetary Systems Composite Parameters table, `pscomppars`) or from a YAML file you write. Every missing value
is filled by a written rule, and every rule that fires is printed with the result. exostab then asks the stability
question in three independent ways, for the published values and for 20 random draws within the published error
bars, and combines the answers into one deliberately conservative verdict: **stable**, **marginal**, **unstable** or
**inconclusive**. When the indicators disagree, it says so instead of picking the most comfortable answer.

**Who it is for.** Students and educators who want a quick first answer with the caveats visible. Amateur and
professional astronomers who want to test a system, or a "what if" variation of it, before setting up their own
integrations. Researchers who want the same indicators for the whole archive in one table.

**Why it exists.** Published orbital solutions are rarely complete enough to integrate directly. In the archive's
composite table on 28 September 2026, 44% of the planets in multi-planet systems had masses estimated from their
radii, 19% had only minimum masses, 11% had no eccentricity and 62% no argument of periastron. Each gap forces a
small decision that can change the answer. exostab makes those decisions explicit and repeatable.

## Quickstart

**Without installing anything.** The [stability catalog](https://mimitoz62.github.io/exostab/catalog/) needs nothing:
look up a system in the table of the archive's multi-planet systems, recomputed every week. The
[two-planet calculator](https://mimitoz62.github.io/exostab/calculator/) evaluates the Hill and AMD criteria for one
pair of planets on the page itself, with no integration. To run exostab itself in a browser:

- [![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/mimitoz62/exostab/blob/main/examples/exostab_quickstart.ipynb)
  runs `exostab check` and `exostab sweep` in a notebook, and needs a Google account.
- [![Open in GitHub Codespaces](https://github.com/codespaces/badge.svg)](https://codespaces.new/mimitoz62/exostab?quickstart=1)
  opens the web app and a copy of the repository, needs a GitHub account and uses your free monthly hours.
- [![Binder](https://mybinder.org/badge_logo.svg)](https://mybinder.org/v2/gh/mimitoz62/exostab/main?urlpath=exostab/)
  opens the web app and needs no account; the first start can take several minutes, and the session ends after 10
  minutes without activity.

**Without a permanent install** (needs [uv](https://docs.astral.sh/uv/) and git, and downloads about 350 MB into uv's
cache). `--offline` uses the snapshot of 22 well-known systems that ships with exostab; leave it out to use the live
archive:

```bash
uvx --from git+https://github.com/mimitoz62/exostab@v1.0.1 exostab check "TRAPPIST-1" --offline
```

**Or install it** and check a multi-planet system from the archive, by host or planet name. You need Python 3.10 or
newer: the first line shows your version, and `/usr/bin/python3` on macOS is 3.9. [Install](#install) has the form
without git.

```bash
python3 --version
python3 -m venv .venv
source .venv/bin/activate
pip install "exostab @ git+https://github.com/mimitoz62/exostab@v1.0.1"
exostab check "TRAPPIST-1"
```

Names are the archive's, for example KOI-351 (Kepler-90), GJ 876 (Gliese 876), ups And (Upsilon Andromedae) and
55 Cnc (55 Cancri); `exostab list` shows them.

The first check downloads the archive's multi-planet table once (about 2,700 rows; 7 s on 13 October 2026) and
caches it; `--refresh` downloads it again. On a 14-core laptop a default check took about 3 s for the two planets
of HD 127195 and about 8 s for the seven of TRAPPIST-1, and about 15 s for TRAPPIST-1 on one of its cores. A smaller
machine, such as a free cloud session, takes longer. The check prints a report card like the one in the recording
above and saves `report.json`, `orbits.png` and `megno.png` in `exostab-results/trappist-1/`.

TRAPPIST-1 comes out **marginal**, with the bundled snapshot and with the archive table of 13 October 2026. That
means mixed evidence, not "about to fall apart": planets f and g are 6.6 mutual Hill radii apart where the
multi-planet spacing heuristic asks for 12, and 2 of the 20 draws within the published error bars are chaotic over
this 41.4-year run, while the angular momentum deficit rules out collisions in the secular approximation (if the
unknown mutual inclinations carry no more AMD than the eccentricities).
[How to read a report card](https://mimitoz62.github.io/exostab/reading-a-report/) goes through this card line by line.

<details>
<summary><b>The TRAPPIST-1 report card as text</b></summary>

```text
$ exostab check "TRAPPIST-1" --offline
╭───────────────────────────── exostab 1.0.1 — stability report card ──────────────────────────────╮
│ TRAPPIST-1   M* = 0.0898 ± 0.0023 M☉   7 planets   data: snapshot (2026-09-28)                   │
│                                                                                                  │
│ Planet        P (d)               Mass (M⊕)      e                  ω (deg)       Phase          │
│ TRAPPIST-1 b  1.51083 ± 6e-06     1.37 ± 0.069   0.00622 ± 0.00304  337 ± 34.2    transit        │
│ TRAPPIST-1 c  2.42194 ± 1.8e-05   1.31 ± 0.056   0.00654 ± 0.00188  282 ± 17.1    transit        │
│ TRAPPIST-1 d  4.04922 ± 2.6e-05   0.388 ± 0.012  0.00837 ± 0.00093  -8.73 ± 6.17  transit        │
│ TRAPPIST-1 e  6.10101 ± 3.5e-05   0.692 ± 0.022  0.0051 ± 0.00058   108 ± 8.47    transit        │
│ TRAPPIST-1 f  9.20754 ± 3.2e-05   1.04 ± 0.031   0.0101 ± 0.00068   369 ± 3.11    transit        │
│ TRAPPIST-1 g  12.3524 ± 5.4e-05   1.32 ± 0.038   0.00208 ± 0.00058  191 ± 13.8    transit        │
│ TRAPPIST-1 h  18.7729 ± 0.000214  0.326 ± 0.02   0.00567 ± 0.00121  339 ± 9.66    transit        │
│ ᵃ assumed  ᵈ derived  ᵉ estimated  ʳ randomized per run  < upper limit                           │
│                                                                                                  │
│ Hill spacing    MARGINAL   draws: 0 stable, 20 marginal, 0 unstable                              │
│   Every pair passes the two-planet limit, but TRAPPIST-1 f / TRAPPIST-1 g is only 6.6 mutual     │
│   Hill radii apart, where the heuristic threshold for its eccentricities is 12.0 (Pu & Wu 2015); │
│   long-term stability is not guaranteed by spacing alone.                                        │
│   • For three or more planets the spacing test is a heuristic (Chambers et al. 1996; Pu & Wu     │
│   2015), not a proof.                                                                            │
│ AMD             STABLE   draws: 20 stable, 0 marginal, 0 unstable                                │
│   AMD-stable: largest β = 0.0285 (TRAPPIST-1 d / TRAPPIST-1 e), so collisions are excluded in    │
│   the secular approximation, provided the mutual inclinations carry no more AMD than the         │
│   eccentricities.                                                                                │
│   • β, β_S and β_H assume that the unknown mutual inclinations carry as much AMD as the          │
│   eccentricities (twice the coplanar AMD; Laskar & Petit 2017, Petit et al. 2017). For exactly   │
│   coplanar orbits they are half as large (largest β_p = 0.0142, β_S,p = 0.00015); 'unstable'     │
│   requires the coplanar values, lower bounds for any inclinations, to be ≥ 1.                    │
│ N-body + MEGNO  MARGINAL   draws: 18 stable, 2 marginal, 0 unstable                              │
│   Nominal run regular (<Y> = 2.17) over 41.4 yr (10,000 inner orbits); draws: 18 regular, 2      │
│   chaotic, 0 close encounter/escape of 20.                                                       │
│   • The nominal run is 'regular', but the draws disagree.                                        │
│                                                                                                  │
│ Overall: MARGINAL  Direct integration: the nominal run is regular; of 20 draws, 18 are regular,  │
│ 2 chaotic and 0 had close encounters or escapes. Part of the parameter range allowed by the      │
│ published uncertainties is chaotic. The other indicators cannot guarantee stability (Hill        │
│ spacing: marginal).                                                                              │
│ N-body: 10,000 orbits of the innermost planet = 41.4 yr, WHFast dt = 0.0497 d, checked with      │
│ IAS15; 20 Monte Carlo draws; seed 0; MEGNO chaotic at <Y> ≥ 2.2; energy-error limit 1e-05.       │
│                                                                                                  │
│ Data completion (applied automatically):                                                         │
│ b, c, d, e, f, g, h  Orbital phase set from the transit mid-time, propagated with the period     │
│                      (transit time and period come from different publications).                 │
│ system               All orbits are placed in one plane. Mutual inclinations are not published   │
│                      (sky-plane inclinations do not determine them), and longitudes of the       │
│                      ascending node are not used.                                                │
│ Note: offline snapshot of 22 systems                                                             │
│                                                                                                  │
│ Saved: exostab-results/trappist-1/report.json, exostab-results/trappist-1/orbits.png,            │
│ exostab-results/trappist-1/megno.png                                                             │
╰──────────────────────────────────────────────────────────────────────────────────────────────────╯
Finished in 7.6 s.
```

</details>

<details>
<summary><b>Use the results in Python</b> (<code>report.json</code>)</summary>

<br>

There is no documented Python API yet. Every check writes `report.json`, which follows a versioned JSON schema
(currently 1.3) that ships with the package. For the TRAPPIST-1 run above, in the folder where it was run:

```pycon
>>> import json
>>> report = json.load(open("exostab-results/trappist-1/report.json"))
>>> report["overall"]["verdict"]
'marginal'
>>> {k: v["verdict"] for k, v in report["indicators"].items()}
{'hill': 'marginal', 'amd': 'stable', 'nbody': 'marginal'}
>>> report["indicators"]["nbody"]["draws"]
{'n': 20, 'stable': 18, 'marginal': 2, 'unstable': 0, 'inconclusive': 0}
>>> report["indicators"]["amd"]["references"]
['laskar2017', 'petit2017', 'petit2018']
>>> report["data"]["retrieved_utc"], report["settings"]["seed"]
('2026-09-28T13:57:30+00:00', 0)
```

`report["system"]["flags"]` lists every completion rule that was applied, and `report["software"]` the versions of
exostab, REBOUND, NumPy, astropy, pydantic and Python.

</details>

<details>
<summary><b>A system with gaps in its data</b>: the report card for HD 127195 (minimum masses, unknown phases)</summary>

```text
$ exostab check "HD 127195" --offline
╭───────────────────────────── exostab 1.0.1 — stability report card ──────────────────────────────╮
│ HD 127195   M* = 1.34 ± 0.06 M☉   2 planets   data: snapshot (2026-09-28)                        │
│                                                                                                  │
│ Planet       P (d)          Mass (M⊕)             e                 ω (deg)           Phase      │
│ HD 127195 b  534.5 ± 2.85   213 ± 6.36 (m sin i)  0.04 +0.05/−0.03  3.1 ± 1.97        random     │
│ HD 127195 c  836.99 ± 9.35  207 ± 6.36 (m sin i)  0.05 +0.05/−0.04  4.12 +1.21/−2.43  random     │
│ ᵃ assumed  ᵈ derived  ᵉ estimated  ʳ randomized per run  < upper limit                           │
│                                                                                                  │
│ Hill spacing    MARGINAL   draws: 16 stable, 0 marginal, 4 unstable                              │
│   Hill stable: separation 4.37 mutual Hill radii, above the Gladman (1993) limit of 3.44 for     │
│   circular orbits (eccentricities included in the test).                                         │
│   • The nominal parameters give 'stable', but the draws disagree.                                │
│ AMD             MARGINAL   draws: 15 stable, 4 marginal, 1 unstable                              │
│   AMD-stable: largest β = 0.408 (HD 127195 b / HD 127195 c), so collisions are excluded in the   │
│   secular approximation, provided the mutual inclinations carry no more AMD than the             │
│   eccentricities.                                                                                │
│   • The nominal parameters give 'stable', but the draws disagree.                                │
│   • β, β_S and β_H assume that the unknown mutual inclinations carry as much AMD as the          │
│   eccentricities (twice the coplanar AMD; Laskar & Petit 2017, Petit et al. 2017). For exactly   │
│   coplanar orbits they are half as large (largest β_p = 0.204, β_S,p = 0.00221); 'unstable'      │
│   requires the coplanar values, lower bounds for any inclinations, to be ≥ 1.                    │
│   • Critical AMD from first-order resonance overlap (Petit et al. 2017) used for: HD 127195 b /  │
│   HD 127195 c.                                                                                   │
│ N-body + MEGNO  MARGINAL   draws: 13 stable, 6 marginal, 1 unstable                              │
│   Nominal run chaotic (<Y> = 9.82) over 14,634 yr (10,000 inner orbits); draws: 13 regular, 6    │
│   chaotic, 1 close encounter/escape of 20.                                                       │
│   • The orbital phases of HD 127195 b, HD 127195 c are not published and are drawn at random in  │
│   every run (the nominal run included). A system protected by a mean-motion resonance can look   │
│   chaotic or unstable for random phases; supply measured phases with --from-file to test the     │
│   real configuration.                                                                            │
│                                                                                                  │
│ Overall: MARGINAL  Direct integration: the nominal run is chaotic; of 20 draws, 13 are regular,  │
│ 6 chaotic and 1 had close encounters or escapes. Part of the parameter range allowed by the      │
│ published uncertainties is chaotic or unstable. The other indicators cannot guarantee stability  │
│ (Hill spacing: marginal, AMD: marginal).                                                         │
│ N-body: 10,000 orbits of the innermost planet = 14,634 yr, WHFast dt = 16.4 d, checked with      │
│ IAS15; 20 Monte Carlo draws; seed 0; MEGNO chaotic at <Y> ≥ 2.2; energy-error limit 1e-05.       │
│                                                                                                  │
│ Data completion (applied automatically):                                                         │
│ b, c    Only the minimum mass m sin i is known; it is used as the mass (sin i = 1) unless        │
│         --inclination-prior is set.                                                              │
│ b, c    Orbital phase drawn uniformly for every run: no transit, conjunction or periastron time  │
│         is published.                                                                            │
│ system  All orbits are placed in one plane. Mutual inclinations are not published (sky-plane     │
│         inclinations do not determine them), and longitudes of the ascending node are not used.  │
│ Note: offline snapshot of 22 systems                                                             │
│                                                                                                  │
│ Saved: exostab-results/hd-127195/report.json, exostab-results/hd-127195/orbits.png,              │
│ exostab-results/hd-127195/megno.png                                                              │
╰──────────────────────────────────────────────────────────────────────────────────────────────────╯
Finished in 3.0 s.
```

The archive does not list orbital phases for HD 127195, so they are drawn at random, and some random phases are
chaotic. With the phases and uncertainties used in the HD 127195 Research Note
(`exostab check --from-file examples/hd127195_note.yaml --orbits 20000 --draws 200 --seed 42`, from a clone of the
repository), the best fit is regular (⟨Y⟩ = 2.00); of the 200 draws, 133 are regular, 51 chaotic and 5 have close
encounters, and 11 are inconclusive: chaotic by MEGNO, but with an energy error of 1.0–1.6 × 10⁻⁵, just above the
limit. The Note, which had no energy criterion, found 134 regular, 57 chaotic and 9 with close encounters.

</details>

## Install

```bash
python3 --version
python3 -m venv .venv
source .venv/bin/activate
pip install "exostab @ git+https://github.com/mimitoz62/exostab@v1.0.1"
```

This installs release 1.0.1 from GitHub. exostab needs Python 3.10 or newer; 3.10–3.14 are tested on Linux and
macOS in continuous integration. The first line shows your version, and `/usr/bin/python3` on macOS is 3.9. If yours
is older than 3.10, install a newer Python first, for example from [python.org](https://www.python.org/downloads/). In
a new terminal, run the `source` line again. A package on PyPI is planned; until then, install from GitHub.

The `pip` line needs git. Without git, install the wheel of the release; `uvx --from` takes the same URL:

```bash
pip install https://github.com/mimitoz62/exostab/releases/download/v1.0.1/exostab-1.0.1-py3-none-any.whl
```

| Optional extra | What it adds | Install |
|---|---|---|
| `web` | The Streamlit web app (Streamlit, Plotly) | `pip install "exostab[web] @ git+https://github.com/mimitoz62/exostab@v1.0.1"` |
| `catalog` | Parquet output for `exostab catalog build` (pyarrow) | `pip install "exostab[catalog] @ git+https://github.com/mimitoz62/exostab@v1.0.1"` |

Without git, put the wheel's URL after the `@`:

```bash
pip install "exostab[web] @ https://github.com/mimitoz62/exostab/releases/download/v1.0.1/exostab-1.0.1-py3-none-any.whl"
```

<details>
<summary><b>Optional SPOCK indicator</b> (separate environment)</summary>

<br>

SPOCK 2.1.1 needs REBOUND below version 5, while exostab needs REBOUND 5.2, so SPOCK is deliberately not a pip
extra: it runs as a separate program in its own environment. With [uv](https://docs.astral.sh/uv/) and a C
compiler, download the setup script (or run it from a clone of the repository), which creates `~/.exostab-spock`, and
point exostab at the new environment:

```bash
curl -fsSLO https://raw.githubusercontent.com/mimitoz62/exostab/v1.0.1/scripts/make_spock_env.sh
bash make_spock_env.sh
export EXOSTAB_SPOCK_PYTHON=~/.exostab-spock/bin/python
exostab check "TRAPPIST-1" --spock
```

</details>

## Indicators and verdicts

Each indicator asks a different question, so exostab always reports all of them.

| Indicator | The question it asks | It says **stable** when | It says **unstable** when |
|---|---|---|---|
| **Hill spacing**<br><sub>Gladman 1993; Chambers et al. 1996; Pu & Wu 2015</sub> | Are neighbouring orbits far enough apart that the planets can never meet? | Two planets: outside the Gladman limit, eccentricities included. Three or more: also every adjacent pair as widely spaced as Pu & Wu (2015) require for its eccentricities (at least 12 mutual Hill radii), and no eccentricity above 0.05. For three or more planets this is a heuristic, not a proof. | A pair is inside the two-planet limit, or two orbits cross. |
| **Angular momentum deficit (AMD)**<br><sub>Laskar & Petit 2017; Petit, Laskar & Boué 2017, 2018</sub> | Is there enough AMD for two neighbouring orbits to cross, or for the innermost planet to reach the star? | β < 1 for every adjacent pair and for the innermost planet and the star, with the resonance-overlap limit of Petit et al. (2017) for close pairs (a pair outside its domain gives at most marginal). As in Laskar & Petit (2017), the unknown mutual inclinations are assumed to carry as much AMD as the eccentricities. | Two planets only: the pair is neither AMD-stable nor Hill stable in the AMD framework, even for exactly coplanar orbits. |
| **N-body + MEGNO**<br><sub>REBOUND: WHFast, checked with IAS15</sub> | Do the orbits stay regular when they are integrated forward? | No close encounter or escape, and MEGNO ⟨Y⟩ < 2.2 over the run (10,000 orbits of the innermost planet by default), with WHFast and IAS15 in agreement and at least 100 orbits of the outermost planet. | Close encounters or escapes. |
| **SPOCK** (optional)<br><sub>Tamayo et al. 2020</sub> | Does a machine-learned classifier expect three or more planets to survive a billion orbits? | The estimate is at least 0.34. | The estimate is below 0.34. On its own, this makes the overall verdict marginal, never unstable. |

Every verdict must hold for the nominal parameters **and** for at least 95% of the draws (19 of the default 20).
Otherwise it is **marginal**: borderline, or the draws within the uncertainties disagree with the nominal parameters.
**Inconclusive** means the indicator could not be evaluated reliably: in the nominal integration, or in more than
20% of the draws, the relative energy error exceeded 10⁻⁵, or a planet passed so close to the star that tides,
general relativity and the size of the star, none of which is modelled, could decide what happens.

The **overall** verdict is conservative:

- *stable* only if every indicator says stable (SPOCK too, when it is enabled), Monte Carlo draws were run, and no
  N-body draw had a close encounter or escape;
- *unstable* only if the direct integration shows close encounters or escapes for the nominal parameters and for at
  least 95% of the draws. An instability found with inputs that are only published upper limits, with the nominal
  run alone (`--draws 0`), or with a single-star model of a system with several stars gives *marginal* instead;
- *inconclusive* if the N-body integrations could not be trusted;
- *marginal* in every other case, including any disagreement between the indicators.

The summary on the report card gives the draw counts and names the reason. With the default settings, 18 of the 21
snapshot systems that exostab can model come out marginal, one stable (Kepler-36), one unstable (HD 82943, whose
orbital phases are drawn at random because the archive's reference time and periods come from different
publications) and one inconclusive (HD 10180).

> [!IMPORTANT]
> Hill spacing and AMD are *sufficient* conditions or heuristics: failing them means stability is not guaranteed, not
> that the system falls apart. GJ 876 is the standard example. With the published four-planet solution of Rivera et al.
> (2010), Hill spacing says unstable and AMD marginal, yet all 20 N-body draws are regular: the planets are protected
> by a resonance. An N-body *stable*, in turn, means "no instability found within the integrated time" (41.4 years for
> TRAPPIST-1 with the defaults), not stability over billions of years.

## Commands

| Command | What it does | Writes |
|---|---|---|
| `exostab check "Kepler-11"` | Report card for one system, by host or planet name | `report.json`, `orbits.png`, `megno.png` |
| `exostab check --from-file my_system.yaml` | The same for your own parameters (start from [`examples/two_planet.yaml`](https://github.com/mimitoz62/exostab/blob/main/examples/two_planet.yaml)) | the same three files |
| `exostab sweep "HD 127195" --planet b --param e --range 0 0.6` | Varies `e`, `mass`, `period` or `omega` of one planet, the others fixed | `sweep.csv`, `sweep.png`, `sweep.json` |
| `exostab list --min-planets 4 --max-period-days 200` | Lists multi-planet systems in the archive table | (terminal only) |
| `exostab catalog build --limit 50` | Indicators for many systems in one table | `catalog.csv`, `catalog_meta.json`, and `catalog.parquet` with the `catalog` extra |

The `examples/` folder exists only in a clone of the repository. To get the example file without one:

```bash
curl -fsSLO https://raw.githubusercontent.com/mimitoz62/exostab/v1.0.1/examples/two_planet.yaml
exostab check --from-file two_planet.yaml
```

Options worth knowing:

- `--seed N`: the same seed gives the same draws and, on the same platform and software versions, the same results
  (default 0).
- `--orbits` and `--draws`, or `--budget fast|thorough|<seconds>`: run length and number of draws, set directly or
  chosen to fit a wall-clock budget (`fast` is about 10 s, `thorough` about 2 minutes).
- `--inclination-prior isotropic`: for minimum masses, draws an inclination in every draw instead of using m sin i
  as the mass.
- `--offline` and `--refresh`: use the bundled snapshot, or download the archive table again.
- `--out DIR` for the output folder, and `-j N` for the number of worker processes (default: all cores but one).

`exostab COMMAND --help` lists every option, and the [CLI reference](https://mimitoz62.github.io/exostab/cli/)
documents them all.

<details>
<summary><b>Example: what if HD 127195 b were more eccentric?</b></summary>

<br>

A short scan, with 2,000 orbits per value instead of the default 10,000 to keep it quick:

```text
$ exostab sweep "HD 127195" --planet b --param e --range 0 0.6 --steps 7 --orbits 2000 --offline
       HD 127195: sweep of e for planet b
┏━━━━━━━┳━━━━━━━━━━┳━━━━━━┳━━━━━━━━━━┳━━━━━━━━━━┓
┃ value ┃ N-body   ┃ <Y>  ┃ Hill     ┃ AMD      ┃
┡━━━━━━━╇━━━━━━━━━━╇━━━━━━╇━━━━━━━━━━╇━━━━━━━━━━┩
│ 0     │ regular  │ 2    │ stable   │ stable   │
│ 0.1   │ regular  │ 2.01 │ stable   │ marginal │
│ 0.2   │ chaotic  │ 6.98 │ unstable │ unstable │
│ 0.3   │ unstable │ —    │ unstable │ unstable │
│ 0.4   │ unstable │ —    │ unstable │ unstable │
│ 0.5   │ unstable │ —    │ unstable │ unstable │
│ 0.6   │ unstable │ —    │ unstable │ unstable │
└───────┴──────────┴──────┴──────────┴──────────┘
Saved: exostab-results/hd-127195/sweep.csv, exostab-results/hd-127195/sweep.png,
exostab-results/hd-127195/sweep.json
```

All other parameters stay at their nominal values. AMD is the first indicator to change (marginal at e = 0.1); at
e = 0.2 the integration is chaotic and Hill spacing and AMD say unstable, and from e = 0.3 on every run ends in a
close encounter or escape.

</details>

## Web app

The web app runs the same analysis as `exostab check` in a browser. Search a system, edit its parameters, try
"what if" changes with sliders (scale a planet's mass, set its eccentricity, move it to another period ratio), choose
a time budget of 5–120 s, and read the verdicts with interactive figures. Download `report.json` and the plots, or
copy a **shareable link** that encodes the system, your edits, the seed and the run length.

It runs on your own computer, in the virtual environment from [Install](#install):

```bash
pip install "exostab[web] @ git+https://github.com/mimitoz62/exostab@v1.0.1"
python -m exostab.web
```

Then open <http://localhost:8501>. In a clone of the repository,
`streamlit run streamlit_app.py` does the same. There is no permanent hosted version. To try the app without installing
it, use the Binder or Codespaces link under [Quickstart](#quickstart). A shareable link made there points at that session: it works only
while the session runs, and other people may not be able to open it.
Details: [web app documentation](https://mimitoz62.github.io/exostab/web/).

## Stability catalog

A [weekly workflow](https://github.com/mimitoz62/exostab/blob/main/.github/workflows/catalog.yml) computes the
indicators for the multi-planet systems in the archive's composite table with the same settings for all of them:
10,000 orbits of the innermost planet, 10 draws, seed 0 and at most 300 s per system (systems over the cap are
recorded as "timeout"). In the run of 26 October 2026 the table had 1,079 such systems: 1,044 were checked and 35
are listed as skipped, with the reason. It publishes `catalog.csv`, `catalog.parquet` and
`catalog_meta.json` on the branch [`catalog-data`](https://github.com/mimitoz62/exostab/tree/catalog-data), one
commit per week, and the documentation shows them as a
[sortable table](https://mimitoz62.github.io/exostab/catalog/). Each row holds the verdicts, the numbers behind
them, the completion rules applied and the software versions, and each system has its own page, for example
[TRAPPIST-1](https://mimitoz62.github.io/exostab/systems/trappist-1/). The catalogs of 16, 19 and 26 October 2026 are computed
with 1.0.0, and later ones with the code on `main` at the time, as each row records. The catalogs of 5 and 12 October
used a development version whose verdict rules differ; they stay on the branch.
[What the catalog shows](https://mimitoz62.github.io/exostab/findings/) describes the results of the catalog of
26 October 2026 and how firm they are.

Read catalog verdicts with their caveats: missing orbital phases are drawn at random, minimum masses are used as
masses and orbits are coplanar, so a resonant system can look marginal or unstable there although the full solution
of one paper shows it is stable (GJ 876 is the standard example). The catalog uses 10 draws and `exostab check` 20 by
default, so a verdict can differ: TOI-270 is stable in the catalog of 26 October 2026 and marginal with the defaults.
Add `--draws 10` to match the catalog's settings. Run `exostab check "<name>"` to see every assumption, or
`--from-file` with a published solution.

## How it stays honest

A stability verdict is only as good as the inputs and settings behind it, so exostab is built to let you check both.

- **Every gap is filled by a written rule, and flagged.** A missing eccentricity is set to 0, and the AMD indicator
  then says that its verdict rests on that assumption. An unknown argument of periastron or orbital phase is drawn
  at random in every run. A minimum mass (m sin i) is used as the mass, or divided by a random sin i with
  `--inclination-prior isotropic`. All orbits are placed in one plane. Each rule that fires appears on the report
  card and in `report.json` ([all rules](https://mimitoz62.github.io/exostab/data-assumptions/)).
- **Every value carries its provenance**: measured, derived, assumed, estimated, randomized or upper limit, with the
  publication it came from where there is one. A conjunction or periastron time is used only when it comes from the
  same publication as the period, because the composite table can combine values from several papers.
- **Uncertainties are propagated.** Each result is repeated for seeded Monte Carlo draws within the published error
  bars, and a verdict stands only if at least 95% of the draws agree with the nominal one.
- **The integrators check each other.** The nominal run is repeated with IAS15. If WHFast and IAS15 disagree, the
  N-body verdict cannot be *stable*. The energy error is checked over the whole of every run, and a run whose
  relative energy error exceeds 10⁻⁵ is *inconclusive*.
- **Runs are reproducible.** On the same platform and software versions, the same `--seed` gives identical runs (this
  is tested). On another platform, floating-point rounding can change chaotic runs and with them a verdict. Each
  `report.json` stores the seed, the versions of exostab, REBOUND, NumPy, astropy and Python, the integrator and time
  step, the run length, the archive download date and the archive name of every planet.
- **It refuses what it cannot model.** `exostab check "Kepler-47" --offline` answers "Kepler-47 is a circumbinary
  system; exostab models a single host star and cannot check it."
- **Choices are written down.** MEGNO ⟨Y⟩ ≥ 2.2 for chaos, the 10⁻⁵ energy-error limit, the spacing requirement and
  the other defaults are recorded, with sources and reasons, in
  [DECISIONS.md](https://github.com/mimitoz62/exostab/blob/main/DECISIONS.md).

<details>
<summary>What provenance looks like in <code>report.json</code> (HD 127195, real output)</summary>

Part of the entry for planet b, with the source of its eccentricity:

```json
{
  "name": "HD 127195 b",
  "mass_kind": "minimum",
  "eccentricity": {
    "value": 0.04,
    "err_plus": 0.05,
    "err_minus": 0.03,
    "provenance": "measured",
    "reference": "Figueira et al. 2026",
    "reference_url": "https://ui.adsabs.harvard.edu/abs/2026A&A...712A.143F/abstract"
  }
}
```

One of the five completion rules that fired for this system:

```json
{
  "planet": "HD 127195 c",
  "parameter": "pl_bmasse",
  "rule": "minimum_mass",
  "message": "Only the minimum mass m sin i is known; it is used as the mass (sin i = 1) unless --inclination-prior is set."
}
```

</details>

### Validation at a glance

A validation suite compares exostab with physics, published solutions and the HD 127195 Research Note (prepared for
Research Notes of the AAS, not yet published). It runs nightly in continuous integration (`pytest -m slow`).

| Test | Reference or tolerance | exostab |
|---|---|---|
| Inner Solar System, 10,000 years: relative energy error | WHFast (dt = 1.891 d) below 10⁻⁷; IAS15 below 10⁻¹² | 1.44 × 10⁻⁹; 5.25 × 10⁻¹⁵ |
| Gladman limit, two planets of 10⁻⁵ M☉ on circular orbits | tends to 2√3 = 3.4641 mutual Hill radii for small masses | 3.4624 |
| The same pair started at 2.2, 3.0, 4.0 and 4.5 mutual Hill radii, 8 starting phases each | every phase meets at 2.2; none is regular at 3.0; none meets at 4.0 or 4.5 | as expected |
| TRAPPIST-1, a resonant chain (archive snapshot) | stable or marginal, never unstable | Hill marginal, AMD stable, N-body marginal: overall **marginal**; nominal ⟨Y⟩ 2.1709 (WHFast) / 2.1685 (IAS15); draws 18 regular, 2 chaotic, 0 encounters |
| GJ 876, a Laplace resonance (Rivera et al. 2010 fit) | N-body stable | N-body **stable**, ⟨Y⟩ 1.9925 / 1.9951, all 20 draws regular; overall marginal by design, because Hill spacing (unstable) and AMD (marginal) fail |
| Kepler-11, six compact planets (archive snapshot) | the nominal configuration is regular over the test horizon | nominal run regular with both integrators over 282.1 years (⟨Y⟩ 1.7855 / 1.7857); draws 10 regular, 8 chaotic, 2 encounters: N-body **marginal**, reported as found |
| HD 127195 Research Note inputs (20,000 orbits, 200 draws, seed 42) | 134 regular, 57 chaotic, 9 encounters; best-fit ⟨Y⟩ 2.000 | 133 regular, 51 chaotic, 5 encounters, 11 inconclusive (regular and encounter fractions within 3 binomial σ); best fit ⟨Y⟩ 1.9994 |

The numbers were produced on 31 October 2026 by `scripts/validation_summary.py` and the slow test suite from the tag
v1.0.0, with exostab 1.0.0, REBOUND 5.2.2, NumPy 2.5.4 and Python 3.14.7 on macOS (Apple M4 Pro), with the bundled
archive snapshot and default settings unless stated. Chaotic integrations are sensitive to floating-point rounding,
so counts of chaotic draws can differ by one or two on other machines. The HD 127195 draws cannot match the Note one
to one because the random number streams differ. Full results, tolerances and figures:
[validation](https://mimitoz62.github.io/exostab/validation/).

## Limitations

- **Finite horizon.** The default N-body run is 10,000 orbits of the innermost planet (41.4 years for TRAPPIST-1,
  14,634 years for HD 127195). "No chaos detected" over that span is not proof of stability over billions of years.
- **Coplanar orbits.** Mutual inclinations are almost never measured, so all orbits are placed in one plane. The
  AMD indicator assumes, as Laskar & Petit (2017) do, that the unknown inclinations carry as much AMD as the
  eccentricities; strongly inclined systems can carry more.
- **Phases.** The composite table mixes publications, and exostab uses a published phase only when it is safe to
  combine with the period. Otherwise it draws phases at random. Resonant systems can then look marginal or unstable:
  with archive data, 12 of 20 GJ 876 draws have close encounters.
- **Independent draws.** Parameters are drawn independently from their error bars, ignoring the correlations in the
  published posteriors. This tends to overstate the fraction of unstable configurations.
- **Thresholds are judgment calls.** MEGNO ⟨Y⟩ ≥ 2.2 counts as chaotic, the energy-error limit is 10⁻⁵, and the
  multi-planet spacing threshold is at least 12 mutual Hill radii and grows with eccentricity (Pu & Wu 2015); above
  e = 0.05 the spacing heuristic never says stable. Each choice is documented, with its uncertainty, in
  [DECISIONS.md](https://github.com/mimitoz62/exostab/blob/main/DECISIONS.md).
- **One star.** Only the host star is modelled. Companion stars are not, so in a system with several stars an N-body
  instability gives *marginal*, and circumbinary systems are rejected.
- **Not modelled.** Tides, general relativity and stellar evolution.
- **Estimated masses.** Many archive masses come from a mass–radius relation or are minimum masses (m sin i). Every
  such case is flagged in the report.

## Documentation

The documentation is at [mimitoz62.github.io/exostab](https://mimitoz62.github.io/exostab/):
[Quickstart](https://mimitoz62.github.io/exostab/quickstart/) ·
[CLI reference](https://mimitoz62.github.io/exostab/cli/) ·
[Web app](https://mimitoz62.github.io/exostab/web/) ·
[Classroom exercise](https://mimitoz62.github.io/exostab/exercise/) ·
[Methods](https://mimitoz62.github.io/exostab/methods/) (equations and references) ·
[Data and assumptions](https://mimitoz62.github.io/exostab/data-assumptions/) ·
[Validation](https://mimitoz62.github.io/exostab/validation/) ·
[Catalog](https://mimitoz62.github.io/exostab/catalog/) ·
[What the catalog shows](https://mimitoz62.github.io/exostab/findings/) ·
[FAQ](https://mimitoz62.github.io/exostab/faq/) ·
[Changelog](https://mimitoz62.github.io/exostab/changelog/) ·
[Design decisions](https://github.com/mimitoz62/exostab/blob/main/DECISIONS.md)

## Citing exostab

If you use exostab, please cite the software, the methods behind the indicators you report, and the NASA Exoplanet
Archive.

**The software.** Use [CITATION.cff](https://github.com/mimitoz62/exostab/blob/main/CITATION.cff) (GitHub's
"Cite this repository" button), and give the version you used; every `report.json` records it. The DOI
[10.5281/zenodo.23844658](https://doi.org/10.5281/zenodo.23844658) always resolves to the latest version, and each version also has its own. In BibTeX:

```bibtex
@software{oz_exostab,
  author  = {{\"O}z, Mehmet},
  title   = {exostab: honest, traceable orbital-stability indicators for known exoplanet systems},
  year    = {2026},
  version = {1.0.1},
  doi     = {10.5281/zenodo.23844658},
  url     = {https://github.com/mimitoz62/exostab}
}
```

**The methods.** Every `report.json` lists, for each indicator, the BibTeX keys of the methods it used (for example
`["laskar2017", "petit2017", "petit2018"]` for AMD). The full entries are in
[docs/references.bib](https://github.com/mimitoz62/exostab/blob/main/docs/references.bib), and
[Citing exostab](https://mimitoz62.github.io/exostab/citing/) lists which papers go with which indicator.

**The data.** The NASA Exoplanet Archive asks users to cite Christiansen et al. (2025) and, for the Planetary Systems
Composite Parameters table, [doi:10.26133/NEA13](https://doi.org/10.26133/NEA13) with the access date. The archive
date of every run is stored in its `report.json` (`data.retrieved_utc`).

## Related work

exostab grew out of the Research Note *N-body Stability Constraints on the Two Giant Planets of the Red Giant
HD 127195* (Öz 2026, prepared for Research Notes of the AAS) and its code,
[mimitoz62/hd127195-stability](https://github.com/mimitoz62/hd127195-stability).

exostab is not to be confused with [Exostab 2.0](https://exostab2.readthedocs.io), an unrelated web service for the
stability limits of circumbinary planets, which exostab does not model.

[exostab and other tools](https://mimitoz62.github.io/exostab/other-tools/) says how exostab relates to REBOUND, SPOCK,
ExoNAMD, the published AMD-stability catalogues, long-term integrators and others, and when to use which.

## Contributing

Bug reports, questions about specific systems and proposals for new indicators are all welcome. Please use the
[issue forms](https://github.com/mimitoz62/exostab/issues/new/choose) (*Bug report*, *Request or question about a
system* and *New indicator*) or [Discussions](https://github.com/mimitoz62/exostab/discussions).

[CONTRIBUTING.md](https://github.com/mimitoz62/exostab/blob/main/CONTRIBUTING.md) explains the development setup
(`pip install -e ".[dev]"`), the checks (a fast test suite, at least 85% coverage in CI, and the slow validation
suite) and the scientific standards, including one rule worth repeating here: never weaken a validation tolerance to
make a test pass. This project follows a
[code of conduct](https://github.com/mimitoz62/exostab/blob/main/CODE_OF_CONDUCT.md). Please report security
problems privately, as described in [SECURITY.md](https://github.com/mimitoz62/exostab/blob/main/SECURITY.md).

## Acknowledgments

> This research has made use of the NASA Exoplanet Archive, which is operated by the California Institute of
> Technology, under contract with the National Aeronautics and Space Administration under the Exoplanet Exploration
> Program.

exostab is built on [REBOUND](https://github.com/hannorein/rebound) (Rein & Liu 2012) with WHFast (Rein & Tamayo
2015), IAS15 (Rein & Spiegel 2015) and its variational equations for MEGNO (Rein & Tamayo 2016), and on astropy,
astroquery, NumPy, Matplotlib, pydantic, Typer, Rich, Streamlit and Plotly. The AMD criteria are from Laskar & Petit
(2017) and Petit, Laskar & Boué (2017, 2018). [SPOCK](https://github.com/dtamayo/spock) (Tamayo et al. 2020;
GPL-3.0) is used, when enabled, as a separate program in its own environment.

Most of the code, tests and documentation were written with an AI coding assistant (Claude Code) under the author's
direction.

exostab is an independent project. It is not affiliated with or endorsed by NASA, Caltech/IPAC or the NASA Exoplanet
Archive.

## License

MIT. See [LICENSE](https://github.com/mimitoz62/exostab/blob/main/LICENSE). Copyright (c) 2026 Mehmet Öz.

The catalog data on the branch `catalog-data` are licensed under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).

---

<p align="center">
  <sub>
    exostab is maintained by Mehmet Öz
    (<a href="https://orcid.org/0009-0007-1005-7640">ORCID 0009-0007-1005-7640</a>,
    <a href="https://github.com/mimitoz62">@mimitoz62</a>).
    Questions about a system are welcome as <a href="https://github.com/mimitoz62/exostab/issues/new/choose">issues</a>;
    for anything else, write to <a href="mailto:mehmet@mehmet-oz.com">mehmet@mehmet-oz.com</a>.
  </sub>
</p>
