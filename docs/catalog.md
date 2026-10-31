---
hide:
  - navigation
  - toc
title: Stability catalog of known multi-planet exoplanet systems
description: >-
  Hill spacing, AMD and N-body verdicts for the multi-planet systems in the NASA Exoplanet Archive, recomputed every
  week.
---

# Stability catalog

exostab's three indicators for the multi-planet systems in the NASA Exoplanet Archive's Planetary Systems
Composite Parameters table, recomputed every week by the
[catalog workflow](https://github.com/mimitoz62/exostab/blob/main/.github/workflows/catalog.yml).
[What the catalog shows](findings.md) describes the results of the catalog of 26 October 2026 and how firm they are.


!!! warning "Read the verdicts with their caveats"
    Every system is checked with the same settings. Missing orbital phases are drawn at random,
    minimum masses are used as masses, and orbits are coplanar. A resonant system can therefore look marginal or
    unstable here, although the full solution of one paper shows it is stable (GJ 876 is the standard example).
    Masses and eccentricities that are only upper limits are used at the limit, with draws below it; a system
    whose instability rests on them is shown as marginal. Systems exostab cannot model (for example circumbinary
    planets, a planet with neither mass nor radius, or a host whose other planets orbit a companion star) are
    listed as skipped with the reason. A run in which a planet passes within half its Hill radius of the star
    gets no verdict. The catalog uses 10 draws and `exostab check` 20 by default, so a verdict can differ
    (TOI-270 on 26 October 2026: stable here, marginal with the defaults). Add `--draws 10` to match the
    catalog's settings. With 10 draws, one draw can change a verdict: in three local rebuilds of the catalog of
    26 October 2026 with different seeds, 50 of the 1,044 verdicts differ, 10 of them between marginal and
    unstable ([details](findings.md#how-firm-these-numbers-are)). Run `exostab check "<name>"` to see every
    assumption, or `--from-file` with a published solution.

*This copy of the page has no catalog table: it was generated without a catalog. The documentation workflow builds
the [published page](https://mimitoz62.github.io/exostab/catalog/) from the newest catalog on the branch [`catalog-data`](https://github.com/mimitoz62/exostab/tree/catalog-data).*
