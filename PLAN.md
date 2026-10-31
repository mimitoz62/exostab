# exostab — plan

exostab is an open-source tool that tells you whether a known exoplanet system is dynamically
stable, using three independent indicators (Hill spacing, angular momentum deficit, N-body + MEGNO)
and parameters fetched from the NASA Exoplanet Archive.

This file is the working plan. Decisions and their reasons live in [DECISIONS.md](DECISIONS.md); open work is
in [WHATS_NEXT.md](WHATS_NEXT.md) and the GitHub issues.

## Status (2026-10-31)

Everything planned for v0.1, v0.2 and v1.0 below is built. The first public release, **1.0.0** (DECISIONS.md, D26),
was published on GitHub on 2026-10-16.

- The repository https://github.com/mimitoz62/exostab is public, with CI, the nightly validation suite, the docs
  site (https://mimitoz62.github.io/exostab/) and the weekly catalog workflow running. The catalogs on the branch
  `catalog-data` of 2026-10-05 and 2026-10-12 were computed with a development version, before the review fixes
  below. Those of 2026-10-16, 2026-10-19 and 2026-10-26 were computed with 1.0.0.
- A review in October 2026 led to about 80 fixes (verdict rules, AMD and Hill criteria, energy checks, data
  completion, CLI, web app, packaging). They are recorded in DECISIONS.md (amendments dated 2026-10-03 to
  2026-10-13 and D24–D32) and described in the docs.

Before tagging v1.0.0 (done):

- [x] Push `main` and check that CI, the nightly suite and the docs deployment pass.
- [x] README and docs site design with the current output (logo, landing page, Citing page, social preview,
  demo recording).
- [x] Open the proposed issues listed in WHATS_NEXT.md, and close #1, #3, #4 and #5, which are implemented.
- [x] Release as described in RELEASING.md (version, `CITATION.cff` date and the date of the `[1.0.0]` section of
  CHANGELOG.md together).

Account-side and optional: PyPI trusted publishing, the Zenodo software DOI, Streamlit Community Cloud and the
catalog's Zenodo dataset (RELEASING.md).

## v0.1 — minimum viable product (done)

- [x] References and formulas verified (D13); `docs/references.bib`.
- [x] Package, data layer (archive, cache, snapshot, completion rules), three indicators, report and JSON schema,
  plots, CLI (`check`, `sweep`, `list`, `catalog build`).
- [x] Unit, property and CLI tests (CI requires 85% coverage); validation suite (16 slow tests).
- [x] Docs, CI workflows, repository files; public repository; issues #1–#13 (WHATS_NEXT.md).

## v0.2 (done)

- [x] Streamlit web app: search, editable table, what-if sliders, time budget, interactive plots, shareable URL,
  downloads, result cache keyed on an input hash (#1, #5). It runs locally (`python -m exostab.web`); the
  repository is prepared for Streamlit Community Cloud, but no hosted instance exists (#2).
- [x] Time-budget mode `--budget` (#3).
- [x] Optional SPOCK indicator for 3+ planet systems, in a separate environment because SPOCK needs REBOUND < 5
  (D23, #4). Whether to keep this design is Mehmet's decision (D23).

## v1.0 (done, except the Zenodo DOI)

- [x] Weekly GitHub Actions catalog job (all archive systems with ≥ 2 planets, per-system time cap) →
  `catalog.csv`, `catalog.parquet` and `catalog_meta.json` on the branch `catalog-data` (not release assets,
  D21) and a sortable docs table.
- [x] MkDocs Material site on GitHub Pages (Quickstart, CLI reference, Web app, Methods, Data assumptions,
  Validation, Catalog, FAQ, Citing, Changelog).
- [x] `CITATION.cff` and a draft `paper/paper.md` (JOSS; not submittable before about April 2027, D22).
- [ ] Zenodo DOI with the first archived release.
