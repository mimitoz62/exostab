---
description: What changed in each release of exostab.
---

# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project uses
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [1.0.0] - 2026-10-16

First public release.

### Added

- `exostab check`: stability indicators for any multi-planet system in the NASA Exoplanet Archive's Planetary
  Systems Composite Parameters table (`pscomppars`), or for a system described in a YAML file (`--from-file`),
  with a report card, `report.json`, `orbits.png` and `megno.png`.
- Three indicators, each giving stable, marginal, unstable or inconclusive:
    - Hill spacing: the Gladman (1993) two-planet criterion, and for three or more planets a spacing heuristic whose
      required spacing grows with the eccentricities (Pu & Wu 2015, 2016);
    - angular momentum deficit (Laskar & Petit 2017), with the resonance-overlap criterion of Petit, Laskar & Boué
      (2017) within the domain the paper states, and the Hill criterion in AMD form for two planets (Petit, Laskar &
      Boué 2018); the unknown mutual inclinations are assumed to carry as much AMD as the eccentricities (β = 2β_p);
    - direct N-body integration with REBOUND (WHFast, with an IAS15 check of the nominal run) and the MEGNO chaos
      indicator. Close encounters are detected for every pair of planets, the energy error is checked at 1,200 times
      in every run, and a run in which a planet passes very close to the star gets no verdict.
- An optional fourth indicator, the SPOCK classifier (Tamayo et al. 2020), run with `--spock` in a separate
  environment built by `scripts/make_spock_env.sh`.
- Monte Carlo draws within the published uncertainties (`--draws`, reproducible with `--seed`), an optional
  isotropic inclination prior for minimum masses (`--inclination-prior`), and a conservative overall verdict. It is
  never "unstable" when the evidence rests on published upper limits, on the nominal run alone, or on a
  single-star model of a system with several stars, and never "stable" without draws or with a close encounter
  among the draws. The summary is built from the draw counts.
- Explicit, flagged data-completion rules (DECISIONS.md, D11 and D24), a disk cache of the archive table with
  `--refresh`, and a bundled offline snapshot of 22 systems (`--offline`).
- `--budget fast|thorough|<seconds>` chooses the run length and the number of draws from a measured integration
  speed.
- `exostab sweep` (one parameter at a time; writes `sweep.csv`, `sweep.png` and `sweep.json`), `exostab list` and
  `exostab catalog build`.
- A Streamlit web app (`python -m exostab.web`, with the `[web]` extra): system search, editable parameters,
  what-if sliders, a time budget, interactive figures, downloads and shareable links.
- A weekly catalog workflow that publishes `catalog.csv`, `catalog.parquet` and `catalog_meta.json` on the branch
  `catalog-data`, a sortable catalog page in the documentation, and an optional Zenodo dataset upload.
- Documentation (methods, data assumptions, validation with figures, CLI reference, web app, catalog, citing
  exostab) and a validation suite: the inner Solar System, the Hill limit, TRAPPIST-1, GJ 876, Kepler-11 and the
  HD 127195 Research Note.
- A documentation site in the colours of the exostab logo, with a landing page, link previews and fonts served
  from the site itself; the logo set (`docs/assets/logo/`); a social preview image drawn by
  `scripts/make_social_preview.py`; and a terminal recording of a check made by `scripts/make_demo_gif.py`.
- Project links for Discussions and for citing exostab in the package metadata.
- A release workflow that checks that the tag, `__version__`, `CITATION.cff` and this file agree, and tests the
  built wheel with the fast and validation suites before anything is published.

### Notes

- `report.json` follows report schema 1.3 (shipped as `exostab/schemas/report.schema.json`). Infinite numbers
  are written as "inf" or "-inf", NaN as null.
- Python 3.10 to 3.14, tested on Linux and macOS. REBOUND 5.2 or newer (below 6) is required; the lower bounds
  of the other dependencies are tested in CI (DECISIONS.md, D25).
- Install from GitHub: `pip install "exostab @ git+https://github.com/mimitoz62/exostab@v1.0.0"`. A release on
  PyPI is planned.
