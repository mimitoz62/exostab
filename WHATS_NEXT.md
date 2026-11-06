# What's next

Open work is tracked in the [GitHub issues](https://github.com/mimitoz62/exostab/issues). Items 1–13 below are
issues [#1](https://github.com/mimitoz62/exostab/issues/1)–[#13](https://github.com/mimitoz62/exostab/issues/13);
the list after them links the issues opened after the October 2026 review. Decisions referred to
as Dn are in [DECISIONS.md](DECISIONS.md).

## Issues #1–#13

1. [#1](https://github.com/mimitoz62/exostab/issues/1) **Streamlit web app.** Done (`python -m exostab.web`);
   closed with the 1.0.0 release.
2. [#2](https://github.com/mimitoz62/exostab/issues/2) **Deploy the web app.** The repository is prepared for
   Streamlit Community Cloud (`requirements.txt`, `.streamlit/config.toml`, steps in RELEASING.md); deploying needs
   Mehmet's account. No hosted instance exists yet.
3. [#3](https://github.com/mimitoz62/exostab/issues/3) **Time-budget mode** (`--budget`). Done (D19); closed with the 1.0.0 release.
4. [#4](https://github.com/mimitoz62/exostab/issues/4) **SPOCK as an optional fourth indicator.** Done, in a
   separate environment because SPOCK 2.1.1 needs REBOUND < 5 (D23); closed with the 1.0.0 release. Whether to keep this design is
   Mehmet's decision.
5. [#5](https://github.com/mimitoz62/exostab/issues/5) **Interactive plots** for the web app. Done; closed with the 1.0.0 release.
6. [#6](https://github.com/mimitoz62/exostab/issues/6) **Calibrate the MEGNO threshold against run length** (D8).
   ⟨Y⟩ ≥ 2.2 is the Research Note's choice. TRAPPIST-1's nominal configuration shows the dependence: ⟨Y⟩ = 2.17
   after 1e4 orbits, 6.46 after 5e4.
7. [#7](https://github.com/mimitoz62/exostab/issues/7) **Calibrate the energy-error limit** (D8). The limit is
   10⁻⁵, checked at 1,200 times in every run; the maximum found grows with the number of checks.
8. [#8](https://github.com/mimitoz62/exostab/issues/8) **Multi-planet spacing threshold** (D12). 12 mutual Hill
   radii is now a floor, and the required spacing grows with eccentricity (Pu & Wu 2015, Eq. 15 as corrected in
   2016); eccentricities above 0.05 never give stable. Remaining: calibrate the eccentricity term beyond 0.05 and
   its dependence on the number of planets.
9. [#9](https://github.com/mimitoz62/exostab/issues/9) **Correlated uncertainties.** Draws are independent; use
   published posterior samples where they exist.
10. [#10](https://github.com/mimitoz62/exostab/issues/10) **Self-consistent solutions** from the archive's `ps`
    table, so that phases, periods and eccentricities come from one paper where possible (D9).
11. [#11](https://github.com/mimitoz62/exostab/issues/11) **Stellar vs planetary ω.** The archive does not
    standardize the convention, and for transit-derived phases of eccentric planets a wrong convention changes
    the starting configuration, not just its orientation (D9, corrected 2026-10-13).
12. [#12](https://github.com/mimitoz62/exostab/issues/12) **Longer horizons for hierarchical systems.** The run
    length is set by the innermost planet; fewer than 100 orbits of the outermost planet currently only prevent a
    "stable" N-body verdict (with a note).
13. [#13](https://github.com/mimitoz62/exostab/issues/13) **Python 3.10** reaches end of life in October 2026;
    decide whether to drop it.

## Issues opened after the October 2026 review

The review of October 2026 left these open questions; each issue gives the current conservative choice
and the DECISIONS.md entry behind it. Smaller items were merged into them or added as comments to #6–#13.

- [#14](https://github.com/mimitoz62/exostab/issues/14) Upper limits: use physical nominal masses, and keep 'unstable' when it does not depend on the limits
- [#15](https://github.com/mimitoz62/exostab/issues/15) Verdicts that rest on eccentricities assumed to be 0
- [#16](https://github.com/mimitoz62/exostab/issues/16) Decide how much Monte Carlo evidence an overall 'stable' needs
- [#17](https://github.com/mimitoz62/exostab/issues/17) AMD: replace the fixed equipartition factor (β = 2β_p) with sampled mutual inclinations
- [#18](https://github.com/mimitoz62/exostab/issues/18) AMD: find a criterion for pairs outside the domain of Petit et al. (2017) instead of capping them at marginal
- [#19](https://github.com/mimitoz62/exostab/issues/19) Companion stars: detect planets that cannot orbit one star, and model companions where possible
- [#20](https://github.com/mimitoz62/exostab/issues/20) Rescale planet masses to the stellar mass used, or propagate the stellar-mass spread
- [#21](https://github.com/mimitoz62/exostab/issues/21) Very eccentric orbits: justify the e ≤ 0.95 cap and use a physical distance for star approaches
- [#22](https://github.com/mimitoz62/exostab/issues/22) Name the actual reasons in the indicator and overall summaries
- [#23](https://github.com/mimitoz62/exostab/issues/23) Radii calculated by the archive are labelled 'measured' in report.json Closed by #34.
- [#24](https://github.com/mimitoz62/exostab/issues/24) YAML files: base the semimajor_axis_au / period_days consistency check on the uncertainties
- [#25](https://github.com/mimitoz62/exostab/issues/25) `exostab sweep --param e` accepts eccentricities above the 0.95 cap that `exostab check` refuses Closed by #31.
- [#26](https://github.com/mimitoz62/exostab/issues/26) `gladman_critical_separation` raises 'root not bracketed' for a very massive inner body Closed by #32.
- [#27](https://github.com/mimitoz62/exostab/issues/27) Web app: stop a run at a wall-clock limit, not only at an estimated cost
- [#28](https://github.com/mimitoz62/exostab/issues/28) Web app: tie shared links to the archive data they were made with
- [#29](https://github.com/mimitoz62/exostab/issues/29) SPOCK environment: ship the setup script with the package and pin the whole environment

## Account-side actions for Mehmet (not issues)

- Done 2026-10-16: helpdesk tickets to the NASA Exoplanet Archive about HD 127195 b and c (`pl_orblper` = 3.10 and
  4.12 "deg" are radian values) and GJ 876 (`pl_orbtper` is the osculating epoch for all four planets) (D18).
  Update D18 when the archive replies.
- PyPI trusted publishing, the Zenodo software DOI, Streamlit Community Cloud and the catalog's Zenodo dataset:
  see RELEASING.md. GitHub Pages and private vulnerability reporting are already set up.
