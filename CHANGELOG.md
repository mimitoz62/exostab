# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project uses
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- A DOI that always resolves to the latest version: [10.5281/zenodo.23844658](https://doi.org/10.5281/zenodo.23844658), in `CITATION.cff`, the README and
  the page on citing exostab.
- After each weekly catalog, the documentation workflow sends the site's URLs to IndexNow (`scripts/indexnow.py`), so
  that Bing and other search engines that take part can learn of new pages with no account. Success confirms receipt,
  not indexing.
- A documentation page, Changes between catalogs (`catalog-changes/`), and an Atom feed (`catalog-changes.xml`),
  generated at build time by `scripts/catalog_changes.py` from `archive/` on the branch `catalog-data`. For consecutive
  catalogs under the current verdict rules, the page lists the systems added and removed and the rows whose overall
  verdict changed, and the feed gives the counts. The page says why a verdict can change between catalogs, and that a
  change is not a discovery.
- The catalog page links to the pages of some well-known systems, such as TRAPPIST-1 and KOI-351 (Kepler-90), and the
  home page to a few of them. Each system's page links to the catalog's citation.
- The home page names the DOI, and describes the software as schema.org `SoftwareSourceCode` for search engines: version,
  licence, author with ORCID and DOI. `tests/test_packaging.py` checks it against `codemeta.json`.
- A documentation page, How to read a report card (`docs/reading-a-report.md`), which goes through the card of a real
  run on TRAPPIST-1 line by line and says what to do next in the common cases. The README, the home page, the
  Quickstart, the web app page, the FAQ and the system pages of the catalog link to it, and `tests/test_report_cli.py`
  checks the lines of its card that do not depend on the integration.
- A documentation page, Hill stability and AMD calculator for two planets (`docs/calculator.md`), evaluates the Hill and AMD
  criteria for one pair of planets in the browser, with no install and no server, and says what that does not show. A
  link keeps the inputs. `tests/test_calculator.py` compares its code with the Python functions on 3,000 seeded random
  pairs when `node` is on the PATH, and fails in GitHub Actions if it is not.
- A classroom exercise for a dynamics or exoplanet course: a notebook for Google Colab
  (`examples/exostab_exercise.ipynb`), in which students compare the Hill, AMD and N-body answers for real systems and
  explain what a short integration cannot show, and a page for teachers with answer notes (`docs/exercise.md`). It has
  not yet been tried with a class. The workflow `Browser paths` also runs this notebook, and `tests/test_packaging.py`
  checks that it has no outputs and installs the latest release.
- A documentation page, exostab and other tools (`docs/other-tools.md`), with links from the FAQ and the README: what
  exostab does not do, and how it relates to REBOUND, SPOCK, ExoNAMD, the published AMD-stability catalogues, long-term
  integrators such as Mercury and SWIFT, the NASA Exoplanet Archive, Exostab 2.0, celmech, the Exo-Striker and ARDENT.

### Changed

- The documentation's pages have more descriptive titles, for browser tabs and search engines. The titles of the system
  pages no longer repeat the name of the site, and the CLI reference has its own description: `scripts/cli_page.py`
  now writes `docs/cli.md`.
- The catalog's schema.org Dataset names its creator's ORCID iD in the form Google's documentation asks for, and adds
  the version, the variables and the technique.

### Fixed

- The download URLs in the catalog's schema.org Dataset led to pages that do not exist. They now name
  `data/catalog.csv` and `data/catalog.parquet`, where the site serves the files.
- The catalog's filter and the web app's search box now find Proxima Cen as `Proxima Centauri` and V1298 Tau as
  `V1298 Tauri`, and the pages of these two systems give those names.
- Methods said that the Solar System is AMD-unstable because Mercury could collide with Venus. That reason is not in
  the arXiv source of Laskar & Petit (2017), which attributes it to the large AMD of the giant planets. The page now
  says so.

## [1.0.1] - 2026-10-31

### Added

- The catalog's filter and the web app's search box also find a system by its other names: `Kepler-90` finds KOI-351,
  `Gliese 876` finds GJ 876 and `Upsilon Andromedae` finds ups And.
- Each release gets a DOI from Zenodo.
- Three ways to try exostab in a browser with no install: a notebook for Google Colab
  (`examples/exostab_quickstart.ipynb`), a dev container for GitHub Codespaces (`.devcontainer/`) and a Binder
  configuration (`.binder/`) that serves the web app at `<session URL>/exostab/`. The notebook and Binder install the
  latest release; a codespace installs the checkout. The README and the Quickstart link to them and say what each
  needs.
- A nightly workflow, `Browser paths`, runs the notebook on Python 3.13 on Linux and the commands of the dev container
  in its image, apart from the validation workflow, because the notebook needs the live archive. `tests/test_packaging.py` checks that the notebook has no outputs, that the notebook, Binder and the
  install lines of the documentation name the latest release, and that the code blocks of the documentation have no
  comments, which break when pasted into zsh, the default shell on macOS.
- A documentation page, What the catalog shows (`docs/findings.md`), on the catalog of 26 October 2026: the stable
  share by number of planets, what the stable verdicts rest on, the six published parameter sets that do not survive
  integration, mass upper limits as inputs, and how firm the numbers are. `scripts/catalog_findings.py` computes its
  numbers and draws its figures from a catalog CSV and the archive table.
- Each row of the catalog page has its own link (`catalog/#trappist-1`), and the published page describes the catalog
  as a schema.org Dataset for dataset search engines. `codemeta.json` describes the software for software catalogs;
  `tests/test_packaging.py` checks it against `CITATION.cff`.
- Each system in the catalog has its own documentation page (`systems/trappist-1/`), generated at build time by
  `scripts/system_pages.py` and linked from the System column of the table: its verdicts and the numbers behind them,
  or the reason for no verdict, its other names, the command to run it and links to the archive and to the web app.
- The catalog page defines every column of `catalog.csv` and every key of `catalog_meta.json`, and says how to cite
  the catalog. The catalog data are now licensed under CC BY 4.0 (`LICENSE` on the branch `catalog-data`).
- The README and the FAQ say that most of the code, tests and documentation were written with an AI coding assistant
  under the author's direction. The FAQ says why the catalog, `exostab check` and the web app can differ for one system.

### Changed

- The Catalog tab of the documentation is a section with the table and the new page, and the table page links to it.
- The install instructions in the README and the documentation check the Python version, use a virtual environment
  and give a form without git, with the release's wheel. They say what the `uvx` line needs and that it downloads
  about 350 MB, and they name the catalog as the option that needs no installation.
- The catalog page has a title and description of its own, and so has every other documentation page except the CLI
  reference, which CI compares with the generated help text.
- The validation numbers in the README and the documentation are from the tag v1.0.0 with REBOUND 5.2.2. They are the
  same as those of 13 October 2026 from `1.0.0.dev0` with REBOUND 5.2.0.
- The code after the release calls itself `1.0.1.dev0`, so a report or a catalog made with it no longer says 1.0.0.
- The filter of the catalog page ignores case, spaces and punctuation, as `exostab check` does, says what the names
  are, and says so when no system matches.
- The README, the documentation and the help of `exostab catalog build` no longer say "any" or "every" multi-planet
  system where some are skipped: 1,044 of the 1,079 systems of 26 October 2026 were checked.

### Fixed

- `exostab sweep --param e` refuses eccentricities above `E_MAX` (0.95), as `exostab check` does, instead of
  integrating orbits up to e < 1.
- `python -m exostab.web` starts at once outside a clone. It used to stop at Streamlit's first-run email prompt,
  and nothing was served until Enter was pressed. It also turns off Streamlit's usage statistics and Deploy button, as
  the repository's own configuration does. As in a clone, no browser opens; the terminal shows the address. Later
  arguments override these settings.
- A name that the archive gives only to planets finds their host: "Kepler-90" gives KOI-351, whose planets include
  Kepler-90 i, instead of suggesting Kepler-990. A name that the planets of several hosts carry ("TOI-2267") is
  refused as ambiguous.
- The error for an unknown name suggests the host for other forms of its name, which are never resolved on their
  own: "Gliese 876" and "Gl 876" suggest GJ 876, "Upsilon Andromedae" ups And, "Kepler-90 h" and "Kepler-90h"
  KOI-351. When there is no suggestion, it points to `exostab list`, and in the web app to its search box.
- An error message that quotes a name with square brackets no longer ends in a traceback (`exostab check "[/red]"`).
- Documentation: names are the archive's, with examples, and `exostab list` shows them. `--from-file` examples that
  needed a clone of the repository first download the example file.
- Documentation: the README no longer says that the published catalogs come from a development version: those of 16,
  19 and 26 October 2026 are computed with 1.0.0. The catalog's caveats say that a resonant system can look marginal or
  unstable, and that the catalog uses 10 draws where `exostab check` uses 20, so a verdict can differ (TOI-270). The
  numbers of hosts in `docs/data-assumptions.md` are those of the table of 31 October 2026.
- Documentation and `--seed` help: the same seed gives identical runs on the same platform and software versions, not
  on every platform. Hill spacing and AMD are sufficient conditions or heuristics, not only sufficient conditions. An
  upper limit is no longer called the worst case for stability: a mass limit need not be for AMD, because a lighter
  innermost planet raises β_S (BD-06 1339).
- `report.json` labels a radius that the archive calculated as `estimated`, not `measured`, and any other column the
  archive calculated as `derived`. No number or verdict changes.
- `exostab check` no longer stops with "root not bracketed" when an inner body is very massive (above about
  0.7 times the stellar mass): the circular-orbit Gladman limit is now searched beyond a_2 / a_1 = 10 (#26).

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
