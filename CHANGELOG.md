# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project uses
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- The catalog has three new columns, `hill_summary`, `amd_summary` and `overall_summary`, with the report card's
  sentences. A system's page built from them has a section, Why this verdict; a page built from an older catalog keeps
  its general text.
- The web app says when a run covers fewer than 10,000 orbits, and that a short run's N-body verdict can look better than
  a longer one's.
- The calculator has an example, TRAPPIST-1 f and g, and says why it and a system's page can differ on one pair.
- A system's page says that its command needs exostab installed, links to the Quickstart, and spells out and links the
  names of the indicators. Its Binder link carries the catalog's seed, run length and draws, and starts the run.
- `examples/solar_system.yaml`: the eight planets from NASA's fact sheets, and a FAQ entry that quotes what exostab says
  about them.
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

- `examples/trappist1_agol2021.yaml`, the transit-timing solution of Agol et al. (2021, Table 2), with every ω increased by
  180° because their code uses f = 270° − ω. A validation test checks that its nominal run is regular over 10,000 orbits
  with three seeds and that its transit periods match Ducrot et al. (2020), and that the table's ω typed unchanged does
  not. The page of TRAPPIST-1 has a short note on what exostab's runs show and what published dynamical studies found.

### Changed

- The AMD row of a system's page and the data dictionary now state the limits of β: the secular approximation, which
  leaves out mean-motion resonances, and the assumption about the inclinations.
- The overall summary no longer says that regular runs with failing analytic indicators are "typical of systems
  protected by mean-motion resonances". It now gives each failing indicator's own summary. When no draw is regular it
  says so, instead of "part of the parameter range". Verdicts do not change.
- The documentation's pages have more descriptive titles, for browser tabs and search engines. The titles of the system
  pages no longer repeat the name of the site, and the CLI reference has its own description: `scripts/cli_page.py`
  now writes `docs/cli.md`.
- The catalog's schema.org Dataset names its creator's ORCID iD in the form Google's documentation asks for, and adds
  the version, the variables and the technique.
- The README, `CITATION.cff` and `codemeta.json` say what exostab does: it reports whether published parameters pass
  three tests of stability, and how that holds up within the uncertainties. The first Zenodo record keeps the old text
  until the next release.
- The BibTeX of the software has the DOI of version 1.0.1, and the catalog's citation names the dated file of that
  version. The validation page and the README say that the nominal label of TRAPPIST-1 is for seed 0, and give seeds 0 to 7.

### Fixed

- The docs said that exostab takes every ω as the planet's, which does not fix the number. They now say that it uses ω as
  published, with mid-transit at f = 90° − ω, and how to type a value from a source that uses f = 270° − ω. The code has
  not changed (D9, amended).
- The download URLs in the catalog's schema.org Dataset led to pages that do not exist. They now name
  `data/catalog.csv` and `data/catalog.parquet`, where the site serves the files.
- The catalog's filter and the web app's search box now find Proxima Cen as `Proxima Centauri` and V1298 Tau as
  `V1298 Tauri`, and the pages of these two systems give those names.
- Methods said that the Solar System is AMD-unstable because Mercury could collide with Venus. That reason is not in
  the arXiv source of Laskar & Petit (2017), which attributes it to the large AMD of the giant planets. The page now
  says so.
- Web app: a what-if value moved on one system or planet is no longer applied to the next one picked, where it silently
  changed the run. Every move of a control is kept: every second consecutive move used to be lost, and so was the table
  edit after typing into a column that is empty for every planet.
- YAML files: these are now refused with a message that names the field, where they were silently misread: a repeated
  key (a missing dash dropped a planet), an error on one side only or an empty one, `err` next to `err_plus` or
  `err_minus`, an error bar or a value of 0 on an upper limit, `mass_kind: estimated` with `upper_limit`, booleans or
  text where a number belongs, integers that only YAML 1.1 reads as numbers (`010`, `0x10`, `1:30`), names and notes
  that are not text or hold control characters, planet names that differ only in case or spaces, a radius that is not
  positive, and values no real system has. `3e-6` is now a number. Files that are not UTF-8, that PyYAML cannot read, or
  with `reference: 2017`, numeric keys next to unknown ones, huge integers or a negative mass no longer give a traceback.
- A non-finite time, angle or drawn value no longer becomes a NaN phase, which was reported as a close encounter and
  overall unstable. A table cell of `inf` counts as missing; a value that cannot be drawn is refused.
- An empty or cut answer from the archive (no rows, QUERY_STATUS=OVERFLOW, or more than 1% of single-star hosts with
  fewer rows than `sy_pnum`) no longer replaces a good cache. A single such host gets the flag `planet_rows_missing`.
- `catalog build` exits with 1 when no system was computed, reports an archive outage in one line, says when the snapshot
  replaced the archive table (`data_note` in `catalog_meta.json`), counts its error rows, and says when Parquet was
  skipped. `--seed` is limited to what Parquet stores, and a Parquet failure still writes the meta file. Ctrl-C stops its
  workers quietly and saves the finished rows in `catalog.partial.csv`.
- Names that differ in digits or in the sign of a declination (`Kepler-10.01`, `BD+08 2823`) no longer reach another
  star: they get a suggestion. A candidate's name suggests its host (`TOI-1233`), and the hint for a name that is not
  found fits the case: `exostab list --offline`, or `--from-file` for a file name.
- `--orbits`, `--max-seconds` and `--max-period-days` refuse NaN and infinity, `--draws` and `--steps` have a maximum,
  an empty `--out` or `--spock-python` is refused, and `--offline` with `--refresh` is refused. A wrong SPOCK
  interpreter is found before the integration, and the SPOCK message gives the raw URL of the script.
- `sweep` varies the planet named in its first argument, refuses a letter that fits two planets, and names the planet it
  varied. Its table tells close values apart and lists the assumptions, and a range that overflows, a mass above the star
  or a period out of range is refused.
- An output folder that cannot be written is found before the integration, with a one-line error, and a long or non-Latin
  system name gets a folder of its own. A cache folder that cannot be used no longer loses the download, or crashes the
  web app. Parallel first runs no longer collide on a temporary file. More kinds of damage to the cache are ignored and
  rebuilt, and a tilde in `EXOSTAB_CACHE_DIR` means the home folder.
- A stalled archive connection times out, and a line says when the table is downloaded. SIGTERM and SIGHUP no longer leave
  workers running, Ctrl-C stops `check` and `sweep` at once, also after the speed measurement of `--budget`, and a worker
  that dies gives one line.
- Non-UTF-8 output, square brackets or emoji codes in paths, names and notes, `$` or a leading underscore in names on
  figures, and an invalid `MPLBACKEND` no longer crash a run or change what is printed. `python -m exostab` works.
- A mass ratio too small to evaluate, and impossible table cells, give one line naming the pair or the column instead of a
  traceback; a catalog's reason is one clean sentence. The reason for a rejection no longer depends on the row order.
- Web app: crafted links no longer give a traceback or an endless run. The table and links take periods up to 1e12 d and
  masses up to 1e7 Earth masses. A name from a link is shown literally, and the page says when part of a link was lost,
  when SPOCK is not available, when a budget cannot be met, and when a kept run length exceeds it. Internal error texts
  are replaced by plain ones.
- Web app: after an edit, the flags of the replaced value are dropped, and the summary says that the run uses changed
  values instead of published uncertainties. Clearing ω of a planet phased from periastron gets a flag and the random-phase
  note. The table shows upper limits as such, and the assumptions are listed before Run. After a change of data source,
  the label and the search box follow; the address bar follows after an error too; the box shows the host of another name;
  and after an archive failure the app tries again within minutes, not after a day. The page on the input hash says what
  a different hash means.
- Messages no longer name command-line options where they also reach the browser, or say "not published" about a file.
  They name the value as written (`eccentricity 0.9500001`, `T b.mass_msun`, a 0.4 s budget), an orbit count below 100
  is not rounded up to it, and one of a thing is singular. New flags say that an error on a radius is not propagated
  (in the message of `mass_from_radius_chen_kipping`), `phase_uncertain_at_epoch` and `mass_kind_unknown`, and
  `star_mass_inconsistent` says when only the sources of one value differ.
- The report card says what `--inclination-prior isotropic` did, keeps the text of the assumptions next to long names,
  and folds planet names when narrow. `exostab list` no longer cuts values, when piped or narrow, and its `no e` counts a
  0 without an uncertainty. The help no longer cuts the default folder or the script's URL, and `Saved:` stays on one line.
  A note says when `--no-plots` leaves figures of an earlier run.

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
