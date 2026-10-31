---
title: Changes between the weekly stability catalogs
description: >-
  What changed from one weekly exostab catalog to the next: systems added and removed, and rows whose overall verdict
  differs. A change here is not a discovery and says nothing about the planets.
---

# Changes between catalogs

exostab's [stability catalog](catalog.md) is recomputed every week. This page compares each catalog with the one
before it: the systems added and removed, and the rows whose overall verdict differs.

!!! warning "A change here is not a discovery"
    A change means that the rows of a system differ between two catalogs. It says nothing about the planets. A verdict
    can change for three reasons, and this page cannot tell which one applies:

    - **The archive's values changed.** The NASA Exoplanet Archive's table now gives other values for the system.
    - **The code changed.** The catalogs were computed with other code or other settings. A development version such
      as 1.0.2.dev0 can name different code from one week to the next.
    - **Chance.** The draws and any missing orbital angles are random. The seed stays the same, so the same values and
      the same code on the same platform repeat a row. A small change in any of these can give other runs, and with 10
      draws, one draw can change a verdict: in three local rebuilds of the catalog of 26 October 2026 with different
      seeds, 50 of the 1,044 verdicts differ ([how firm the verdicts are](findings.md#how-firm-these-numbers-are)).

    With the same seed, values and code, two catalogs that agree show determinism, not robustness. Each verdict
    describes a published parameter set under the catalog's settings. [Stable is not a proof, and marginal does not
    mean unstable](findings.md#what-stable-means-here-and-what-it-does-not). [Unstable is not a prediction for the
    planets](findings.md#published-parameter-sets-that-do-not-survive-integration).

The overall verdict is the catalog's column `overall`: stable, marginal, unstable or inconclusive. A row has no verdict
if it is skipped, over the time limit or an error, and a row with no verdict in both catalogs is not listed. The time
limit is in wall-clock seconds, so a slower machine alone can put a row over it. A system is added or removed when the
archive's table gains or loses it as a system with at least two planets, when the code changes which hosts get a row,
or when a run covers only part of the table. That does not say when its planets were found, and a renamed host counts
as both. Draws are given as regular / chaotic / with a close encounter or escape, as in the catalog's table; draws whose
integration could not be trusted are not counted, so the three can add up to less than the number of draws.

*This copy of the page has no comparisons: it was generated without the weekly catalogs. The documentation workflow
builds the [published page](https://mimitoz62.github.io/exostab/catalog-changes/) from the files in `archive/` on the branch [`catalog-data`](https://github.com/mimitoz62/exostab/tree/catalog-data).*
