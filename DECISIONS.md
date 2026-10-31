# Decisions

Each entry records what was decided, why, and when. Entries D0–D7 were written during setup; D8 to D23 were
written while building v0.1 (2026-09-28), after the references and formulas were checked against their primary
sources (D13). The review of October 2026 changed several rules: the entries concerned carry a dated amendment
that says what changed and why, and D24 onwards are new. Earlier text is kept where it records what was done
before.

## D0 — Environment found (2026-09-28)

- macOS on Apple M4 Pro (14 cores). Python 3.14.7 (default) and 3.12 installed; `uv` and `ffmpeg` present;
  `vhs` and `asciinema` not installed (needed later for the README GIF).
- `gh` 2.97.0 authenticated as `mimitoz62` with `repo` scope.
- Network access works; the NASA Exoplanet Archive TAP endpoint answers in about 2 s.
- The research repository `mimitoz62/hd127195-stability` exists on GitHub (public, MIT). Its
  `paper_analysis.py` is sound and is the starting point for the integration and AMD code: REBOUND 5.2.0,
  units (yr, AU, Msun), WHFast at P_b/30 with spot checks at P_b/60, P_b/100 and IAS15, MEGNO ⟨Y⟩ < 2.2
  counts as regular, close encounter = within the smaller planet Hill radius, escape = beyond 100 a_max,
  critical AMD by minimisation along the collision line.

## D1 — Package name: `exostab` (2026-09-28, chosen by Mehmet)

Checked on 2026-09-28: free on PyPI (`/pypi/exostab/json` returned 404) and free under `mimitoz62` on
GitHub. An unrelated repository `eggls6/exostab2` ("Stability estimates for the three body problem")
exists; the names differ, so no conflict. Alternatives considered: `exostability`, `orbstab`.

## D2 — License: MIT

The brief's default, and the same license as `hd127195-stability`. Not changed, so no question needed.

## D3 — Metadata

Author Mehmet Öz, ORCID 0009-0007-1005-7640, GitHub `mimitoz62`, contact mehmet@mehmet-oz.com
(confirmed by Mehmet on 2026-09-28).

## D4 — Python support: ≥ 3.10, CI on 3.10 to 3.14

- As the brief asks. Caveat: Python 3.10 reaches end of life in October 2026, and the current numpy
  (2.5.x, needs ≥ 3.12), astropy (8.0.x, needs ≥ 3.11) and matplotlib (3.11.x, needs ≥ 3.11) no longer
  support it. On 3.10 pip resolves older releases, so CI must test that combination. Revisit dropping 3.10
  after v0.1.
- Local development uses Python 3.12 in `.venv` (created with `uv venv --python 3.12 .venv`).
- Dependency versions installed on 2026-09-28: rebound 5.2.0, numpy 2.5.3, astropy 8.0.1,
  astroquery 0.4.11, pydantic 2.13.5, typer 0.27.2, rich 15.0.0, matplotlib 3.11.2, platformdirs 4.12.1,
  pytest 9.1.1, hypothesis 6.168.3, ruff 0.16.9, mypy 2.3.1. Only lower bounds are pinned; to be set
  when `pyproject.toml` is written. (The lower bounds were tested on 2026-10-03, D25.)

## D5 — REBOUND ≥ 5.2

Same version as the Research Note, so the HD 127195 validation compares like with like. Wheels exist for
CPython 3.9 to 3.14 on macOS (x86_64, arm64), Linux (manylinux, musllinux) and Windows.

## D6 — Archive columns (verified against `TAP_SCHEMA.columns` on 2026-09-28)

- Table `pscomppars`: 2,663 planet rows had `sy_pnum >= 2` on 2026-09-28.
- **The brief's assumed `rowupdate` column does not exist in `pscomppars`** (the query fails with
  ORA-00904). Traceability will instead use `pl_name`, the per-parameter `*_reflink` columns,
  `pl_bmassprov` (whether a mass is a true mass or m·sin i), the `*lim` limit flags, `pl_controv_flag`
  and the query timestamp.
- Columns to use (name, unit): `pl_name`, `hostname`, `sy_pnum`, `pl_letter`, `pl_orbper` (days),
  `pl_orbsmax` (au), `pl_orbeccen`, `pl_orblper` (deg), `pl_orbincl` (deg), `pl_orbtper` (days),
  `pl_tranmid` (days), `pl_bmassj` / `pl_bmasse` (mass or m·sin i), `pl_bmassprov`, `pl_radj` / `pl_rade`,
  `st_mass` (Msun), `ttv_flag`, plus the `err1`/`err2`, `lim` and `_reflink` variants.
- A local copy of the column list is in `.handoff/pscomppars_columns_2026-09-28.csv` (not committed).

## D7 — SPOCK conflicts with REBOUND 5 (found 2026-09-28; decision needed at v0.2)

`spock` 2.1.1 (latest on PyPI) requires `rebound>=4.0.1,<5.0.0` (and `celmech<1.6`). It cannot be
installed next to the core package's REBOUND 5.2. Options for v0.2: wait for a SPOCK release that
supports REBOUND 5; run SPOCK in a separate environment; or drop it. Dropping it changes the indicator
set, which needs Mehmet's approval.

Resolved on 2026-09-28 by D23: SPOCK runs as an optional indicator in a separate environment.

## D8 — Integration settings (final for v0.1, 2026-09-28; amended 2026-10-04 and 2026-10-13)

| Setting | Value | Why |
|---|---|---|
| Unit system | `sim.units = ("yr", "AU", "Msun")`, set before any particle is added | Brief; the Julian year of astropy and REBOUND agree; `tests/test_units.py` checks G |
| Coordinates | Planets added by period in Jacobi coordinates (REBOUND default) | Same as the Research Note; Rivera et al. (2010) elements are Jacobi |
| Main integrator | WHFast (REBOUND 5.2 defaults: Jacobi, safe mode on, no symplectic corrector) | Brief; fast and symplectic |
| Timestep | 1/30 of the shortest pericentre-passage timescale T_p = P (1−e)^{3/2}/(1+e)^{1/2} | Wisdom (2015) found T_p/20 adequate (as restated by Hadden & Lithwick 2018, who used 1/30); equals P_min/30 for circular orbits (Note's choice, finer than the brief's P_min/20) |
| Cross-check | IAS15 repeats the nominal run with MEGNO; disagreement prevents a "stable" N-body verdict | Brief |
| Run length | 1e4 orbits of the innermost planet (`--orbits`) | Brief. Reports state the horizon in years and never imply Gyr stability. If the outermost planet completes < 100 orbits the N-body verdict cannot be "stable" |
| Close encounter | two planets closer than the mean of their Hill radii, (R_H,j + R_H,k)/2 (REBOUND collision detection, "line" mode); a planet passing within half its Hill radius of the star is not one and makes the run inconclusive (D20, amended 2026-10-04) | Changed from the Research Note's global rule, see D20 |
| Escape | distance from the centre of mass above 100 × the largest semi-major axis | Research Note's rule |
| MEGNO threshold | ⟨Y⟩ ≥ 2.2 is chaotic | See below |
| Energy-error limit | maximum relative energy error > 1e-5 → run "inconclusive"; checked at 1,200 equally spaced times in every run (nominal, draws, IAS15 check, catalog and sweep runs) and at an early stop; the plot samples are a subset of these checks. Until 2026-10-04: sampled 400 times for the nominal run and only at the end for draws | See below |

**MEGNO threshold (uncertain).** ⟨Y⟩ → 2 for quasi-periodic orbits and grows linearly for chaotic ones
(Cincotta & Simó 2000; restated by Goździewski, Migaszewski & Musieliński 2007, arXiv:0802.0254, and Maffione
et al. 2011, arXiv:1108.5481). Published working thresholds vary with integration length: |⟨Y⟩−2| ≤ 0.001 after
1e5 yr (Satyal et al. 2013, arXiv:1211.3956), 2.01 (Maffione et al. 2011, galactic potentials), ⟨Y⟩ ≳ 5 as
"chaotic" on colour scales (Goździewski et al. 2015, arXiv:1510.02776). These four were read in their arXiv
LaTeX sources; their entries in `docs/references.bib` were added on 2026-10-13 after a Crossref check. 2.2 is the
Research Note's value, which the HD 127195 validation reproduces. A lower value would be more conservative.

*Amended 2026-10-13.* The v0.1 text added that a lower value would, at 1e4 orbits, also flag regular orbits whose
⟨Y⟩ has not converged, "for example TRAPPIST-1's nominal run gives 2.17 with both WHFast and IAS15". That example
was wrong: the same configuration (bundled snapshot, seed 0) is chaotic over longer runs, with ⟨Y⟩ = 2.42 after
3e4 orbits and 6.46 (WHFast) / 5.26 (IAS15) after 5e4 (`exostab check "TRAPPIST-1" --offline --draws 0
--orbits 30000` and `50000`). The 2.17 at 1e4 orbits is an early stage of a chaotic run. The threshold is kept at
2.2, but no measured case now shows that a lower one would mislabel regular orbits; improvement tracked in
issue #6.

**Energy-error limit (uncertain).** Measured maxima over the 1,200 checks (`scripts/validation_summary.py`,
2026-10-13): 1.44e-9 (inner Solar System, 1e4 yr), 4.5e-8 (GJ 876, Rivera et al. 2010 fit), 4.8e-8 (Kepler-11),
2.4e-7 (TRAPPIST-1), 3.8e-6 (HD 127195 best fit with the Note's inputs). 11 of the 200 HD 127195 draws of the
validation, all chaotic by MEGNO, exceed 1e-5 (1.01e-5 to 1.58e-5) and are inconclusive. 1e-5 leaves room for
chaotic runs whose MEGNO is still meaningful while catching broken integrations. Petit et al. (2018) used 1e-8
with a higher-order integrator. Improvement tracked in issue #7.

**Energy checks over the whole run (amended 2026-10-04).** Until then the energy error was measured only where
plot samples were taken: 400 times in the CLI's nominal run, 300 in the web app's, and only at the final instant
for every Monte Carlo draw and every catalog run. WHFast's error oscillates and peaks at pericentre passages, so
the end value can be orders of magnitude below the maximum. Draws and catalog runs above 1e-5 therefore got
verdicts, and the catalog could differ from `exostab check` (HD 10180 with the same settings: marginal against
inconclusive). Now every run checks the error at `ENERGY_CHECKS` = 1,200 equally spaced times, plus at an early
stop, and the plot samples are a subset of these checks, so they cannot change a result. Why 1,200 (a convention,
uncertain): on identical trajectories (archive cache of 2026-09-28, 1,044 hosts, seed 0, nominal and 10 draws,
1e4 orbits, 10,933 completed WHFast runs), the number of runs above 1e-5 was 6 with the end value only, 27 with
400 checks, 33 with 1,200 and 35 with 4,800. The maximum keeps growing with the number of checks because the
peaks are narrow, so no finite grid is exact; host verdicts were identical with 1,200 and 4,800 checks. Against
the end-only rule, 7 hosts changed with catalog settings: HD 10180, HD 176986, HD 47366, KMT-2021-BLG-1077L,
OGLE-2018-BLG-1011L and OGLE-2019-BLG-0468L became inconclusive, and TYC 1422-614-1 went from stable to marginal.
The checks cost under 0.5% of a 1e4-orbit run (measured on Kepler-11, TRAPPIST-1 and HD 10180). For runs shorter
than about 40 orbits many checks fall within one step and are skipped, which is correct but leaves fewer
effective checks.

## D9 — Orbital phases (resolved, 2026-09-28; amended 2026-10-03 and 2026-10-13)

The composite table can take each parameter from a different publication (archive documentation,
`pscp_about.html`, `pscp_calc.html`). Phases are therefore used only when they are safe to combine with the
period:

1. Transiting planet (`tran_flag = 1`) with `pl_tranmid`: phase from the transit time, whatever its
   reference (transit times are direct observations); the report notes when the period comes from another
   publication. Uncertainties of the transit time and the period are propagated to the common epoch in
   every draw.
2. Non-transiting planet with a time of conjunction (`pl_tranmid`): used only if it comes from the same
   publication as the period.
3. Time of periastron (`pl_orbtper`): used only if from the same publication as the period **and** not shared
   by several planets of the system **and** the argument of periastron is published. Without ω the direction of
   the periastron, and so the planet's longitude, would be random in every run (the last condition was added on
   2026-10-03, D24). (GJ 876 lists 2450602.093 for all four planets: that is the osculating epoch of Rivera et
   al. 2010, not a time of periastron.)
4. Otherwise the mean anomaly is drawn uniformly in every run, including the nominal run, and the N-body
   verdict carries a note that resonant systems can look unstable with random phases.

The common epoch is the reference time that minimises the summed variance of the propagated phases. Mean
anomalies and mean longitudes (user files only) refer to `epoch_jd`. A file that combines them with transit or
periastron times must give `epoch_jd`; it is not inferred (2026-10-03, D24).

Mid-transit is at true anomaly f = π/2 − ω (Winn 2010, Eq. 6), with ω the argument of periastron of the planet's
orbit. The archive does not standardize ω: its column documentation for `pl_orblper` says that some publications
refer to the planet's orbit and others to the star's reflex orbit, which differs by 180°, and that the values are
"as-reported for each publication". exostab takes every ω as the planet's.

*Amended 2026-10-13.* The v0.1 text said that if a publication gives the star's ω, then "for a common convention
across all planets of a coplanar system the error is a rotation of the whole system and does not affect the
dynamics". That is wrong for phases taken from transit times. The transit fixes each planet's true longitude at
π/2; an ω off by π flips the periastron while the planet stays on the line of sight, so its mean longitude moves
by about 4e cos ω to first order in e (the e cos ω term that also sets the time between transit and occultation,
Winn 2010), and relative phases, distances and resonant angles change with it. The review of October 2026 showed constructed eccentric,
near-resonant pairs whose N-body verdict changes with the convention; for Kepler-9 the starting geometry changes
but the verdict does not. Only for phases from a time of periastron is a common offset of π a rigid rotation.
How many archive values use the star's convention is unknown, so nothing is converted automatically; recording
or testing the convention is tracked in issue #11.

## D10 — HD 127195 validation target (final; amended 2026-10-13)

The validation uses `examples/hd127195_note.yaml`, which holds the Note's own inputs (`paper_analysis.py`
`BEST`/`ERR`, angles converted from radians to degrees), and the Note's settings where exostab has them (2e4
orbits of b, 200 draws, MEGNO < 2.2). The time step is exostab's own T_p/30 (D8): 16.43 d for the best fit, about
8% smaller than the Note's P_b/30 = 17.82 d. (Until 2026-10-13 this entry said "WHFast at P_b/30", which is the
Note's setting, not exostab's.) Tolerances (`tests/validation/test_validation.py`):

- geometry (a_b, a_c, period ratio, 4.37 mutual Hill radii): relative 1e-5 to 1e-3;
- best-fit ⟨Y⟩ = 2.00 ± 0.02 with WHFast; the IAS15 run must be regular (⟨Y⟩ < 2.2). (Until 2026-10-13 this
  entry claimed ± 0.02 for IAS15 too, which the test does not check.)
- Monte Carlo fractions within 3 binomial standard deviations of 134/200 regular and 9/200 close encounters
  (draws are independent Gaussians in both codes, but the random streams differ);
- at most 10% of the draws inconclusive, and every inconclusive draw chaotic by MEGNO (since 2026-10-04);
- every draw passes the Laskar & Petit (2017) collision criterion with the coplanar AMD (Note N7);
- AMD limit for equal eccentricities 0.1478 ± 0.0005 with the coplanar AMD (Note N11);
- conclusion: nominal regular, N-body verdict marginal, overall marginal.

Measured on 2026-09-28 (seed 42): 133 regular, 62 chaotic, 5 close encounters. Measured on 2026-10-13, with the
energy checked over the whole run (D8): 133 regular, 51 chaotic, 5 close encounters and 11 inconclusive. The 11
are chaotic by MEGNO (⟨Y⟩ 755 to 1,508) with energy errors of 1.01e-5 to 1.58e-5; the Note had no energy
criterion, so they belong to its chaotic class.

Note: with the Petit et al. (2017) resonance-overlap refinement, which the Note did not use, the pair falls in
the "MMR overlap" branch (α = 0.7415 > α_R = 0.7288, ε = 9.4e-4 < ε_lim) and some draws are AMD-unstable, so
exostab's AMD verdict for these inputs is "marginal" although every draw passes the collision criterion. With
β = 2β_p (D14, since 2026-10-03) the AMD indicator's draws are 137 stable, 49 marginal and 14 unstable (185, 1 and
14 with the coplanar AMD); the equal-eccentricity limit for β = 1 is 0.0713.

## D11 — Data completion rules (final for v0.1; amended 2026-10-03, 2026-10-04 and 2026-10-31)

As in the brief, plus these choices:

- Missing eccentricity → 0, "assumed"; a published 0 without an uncertainty likewise (D24). Upper limits
  (`*lim = 1`) on planet masses and eccentricities: the nominal run uses the limit (worst case for stability)
  and draws are uniform between 0 and the limit; limits on other values, including the stellar mass, are not
  used (D24). A limit is a worst case only for a stable verdict: an N-body instability found with limited values
  gives an overall "marginal" (D27). Lower limits are used as values, flagged.
- Draws: split normal on asymmetric errors; negative eccentricities set to 0 (as in the Note), draws capped at
  0.95; a nominal eccentricity above 0.95 is rejected (D24); masses, periods and stellar mass redrawn until
  positive. Values without errors are held fixed.
- **Deviation:** the longitude of the ascending node is not randomized. exostab integrates coplanar systems,
  in which Ω and ω only enter as ϖ = Ω + ω; randomizing ω (when it is missing) is equivalent.
- Sky-plane inclinations are not used (they do not give mutual inclinations); all orbits coplanar, flagged.
- m sin i: used as the mass (sin i = 1) by default; `--inclination-prior isotropic` draws one inclination per
  draw for the whole system with cos i uniform, truncated at sin i ≥ 0.1 (true mass ≤ 10 × minimum mass, the
  largest factor in the Note's scan). The nominal run always uses minimum masses. Since 2026-10-03, an "Msini" of
  a transiting planet is a true mass, and a mass lower limit of a non-transiting planet is a minimum mass (D24).
- Mass from radius: the archive already fills missing masses with the Chen & Kipping (2017) relation
  (`pl_bmassprov = "M-R relationship"`, 44% of planets in multi-planet systems on 2026-09-28); these are
  flagged "estimated". For the few rows with no mass at all, and for YAML files, exostab inverts the same
  relation for radii below 11.3 R⊕ and refuses above (the relation is degenerate there; the archive itself
  computes no mass between 11.1 and 14.3 R⊕).
- Circumbinary systems (`cb_flag`) are rejected; companion stars (`sy_snum > 1`) are ignored with a flag, and an
  N-body instability of such a system gives an overall "marginal" (D27).
- Period missing but semi-major axis present → period from Kepler's third law, "derived", except for planets
  found by microlensing or direct imaging, which are rejected (D24).
- Stellar mass: chosen among the planet rows by the rule of D24.
- Hosts with only one planet row are rejected (`sy_pnum` counts planets around all stars of the system).

On 2026-09-28, 1,044 of the 1,070 hosts with `sy_pnum ≥ 2` could be modelled; 26 were rejected with a stated
reason. After D24 (same cache): 1,034 can be modelled and 36 are rejected (10 with a single planet row, 10
microlensing or imaging systems without a period, 8 circumbinary, 6 with a planet that has neither a mass nor a
usable radius, 1 without a period or semi-major axis, 1 without a stellar mass). Every rejected host appears in
the catalog as skipped, with the reason (before 2026-10-04 the 10 hosts with a single planet row were left out
of it).

*Amended 2026-10-31.* "Worst case for stability" above is too strong for a mass limit and the AMD indicator:
β_S = C / Λ₁ grows as the innermost planet gets lighter. exostab calls BD-06 1339 stable with the archive's limit of
1,523 M⊕ for planet b (β_S = 0.011). In a run with a YAML file, with the planet's m sin i of 8.5 M⊕ (Lo Curto et al.
2013), β_S = 1.96, and AMD and the overall verdict are marginal. A stable result therefore describes the values that
were run, not every value below a mass limit. For Hill spacing and the integration, the limit is normally the hardest
case. The rule is unchanged: only its reasoning and the documentation changed (`docs/methods.md`).

## D12 — Hill indicator (final for v0.1; amended 2026-10-03 and 2026-10-04)

- Two planets: the eccentric Gladman (1993) criterion in the form restated by Veras & Armitage (2004, Eqs.
  2.5 and 2.8) and Giuppone et al. (2013, Eq. 3), with μ_i = m_i/M_* and without the next-order mass term.
  It is algebraically the Petit et al. (2018) Hill criterion (tested). Failing it gives "unstable" for the
  Hill indicator ("close encounters not excluded"), with the note that resonances can protect a pair.
- Mutual Hill radius ((m_1+m_2)/3M_*)^{1/3} (a_1+a_2)/2 (Chambers et al. 1996; Pu & Wu 2015). In these units
  the circular Gladman limit is 2√3 up to terms of order μ^{2/3}: 3.463 for two Earth masses, 3.462 for two
  1e-5 M☉ planets and 3.429 for two Jupiter masses. (The Research Note's notebook quotes 3.35 for 1e-5 M☉: that
  is the lowest-order criterion normalised to a_1, converted to mean-a Hill radii. The two differ at order
  μ^{1/3}; neither changes the Note's conclusions. Keeping the omitted next-order mass term would give 3.441 for
  Earth masses; omitting it is conservative.)
- Three or more planets: heuristic. "Unstable" if any adjacent pair fails the two-planet criterion or has
  crossing orbits. "Stable" only if every adjacent pair has Δ ≥ max(12, 10.2 + 2.4 max(e_j, e_k)/e_H), with
  e_H = ((m_j+m_k)/3M_*)^{1/3}, and no eccentricity is above 0.05. "Marginal" otherwise.
- Source: Pu & Wu (2015), from 7-planet systems of 3–9 M⊕ around a solar-mass star:
  - K_50 ≈ 10.2 for circular, coplanar orbits to survive 1 Gyr (Eq. 12, extrapolated from 10 Myr);
  - eccentricity raises K_50 to K_50(0,0) + σ_e/0.01 for μ ~ 1e-5 (Eq. 14), or K_50(0,0) + 2.4 σ_e/e_H in
    general (Eq. 15 as corrected by Pu & Wu 2016; the arXiv version prints "0.4 ×"), measured at 1 Myr for
    σ_e ≤ 0.05;
  - 12 is their value for σ_e ≈ 0.02 and is kept as a floor, so the test is never looser than in v0.1.
- For comparison, Obertas et al. (2017) find 8.5–8.6 for 10^9–10^10 orbits of five Earth-mass planets on circular
  orbits.
- Uncertain:
  - the larger e of each pair stands in for the system's Rayleigh dispersion σ_e (conservative: the mean of a
    Rayleigh distribution is 1.25 σ_e);
  - 0.05 is the largest dispersion Pu & Wu simulated, not a limit on single eccentricities, which were often
    larger in their samples. Comparing each planet's e with it, and never calling such a system "stable", is a
    conservative choice (wording corrected on 2026-10-04: the summary used to call e > 0.05 "beyond the
    calibrated range");
  - systems with fewer planets need somewhat less spacing;
  - K_50 is a 50%-survival spacing, not a guarantee.
- History: v0.1 (2026-09-28) required a fixed Δ ≥ 12 for every adjacent pair. Changed on 2026-10-03 because the
  fixed value ignored the eccentricities, which Pu & Wu find raise the required spacing. Measured effect on
  2026-10-03: on the bundled snapshot, HD 219134 (e up to 0.148), TOI-270, L 98-59 and Kepler-51 lose Hill
  "stable" (combined or in most draws), and TOI-270's overall verdict goes from stable to marginal; in the
  2026-09-28 archive cache, 35 systems lose Hill "stable". Improvement tracked in issue #8.

## D13 — Reference verification (2026-09-28)

Every entry in `docs/references.bib` was checked against its Crossref record (articles), arXiv, or DataCite
(the archive's dataset DOIs); raw responses were kept locally. Formulas were copied from the arXiv LaTeX
sources (Laskar & Petit 2017; Petit et al. 2017, 2018; Chen & Kipping 2017; Rivera et al. 2010; Winn 2010)
and cross-checked numerically in the tests. Differences from the brief:

- Cincotta & Simó (2000)'s title is "Simple tools to study global dynamics in non-axisymmetric galactic
  potentials – I"; Tamayo et al. (2020)'s is "Predicting the long-term stability of compact multiplanet
  systems"; Winn (2010)'s chapter is "Transits and Occultations".
- The archive now asks to cite Christiansen et al. (2025, PSJ 6, 186), which replaces Akeson et al. (2013).
- Not verifiable from open sources: Gladman (1993), Chambers et al. (1996), Cincotta & Simó (2000) and
  Wisdom (2015) are not on arXiv. Their bibliographic data are verified; statements attributed to them in
  the docs rely on the restatements cited next to them.

Added on 2026-10-13, each checked against its Crossref record: the four MEGNO-threshold sources of D8
(Goździewski et al. 2007 and 2015, Maffione et al. 2011, Satyal et al. 2013) and, in `paper/paper.bib`, the
Pu & Wu (2016) erratum. The HD 127195 Research Note is not published (D34), so it has no record to check
and no BibTeX entry; it is cited in the text with a link to its code repository.

## D14 — AMD indicator (final for v0.1; amended 2026-10-03 and 2026-10-04)

- Inclinations. exostab can compute only the coplanar AMD C_p (cos i = 1), which is a lower bound on the AMD for
  any mutual inclinations. It follows the convention of Laskar & Petit (2017, Sect. 6: "we use β=2β_p",
  "β_S=2β_Sp") and Petit et al. (2017, Sect. 5.1: "β=2β_p"), which takes the total AMD as C = 2C_p (equipartition
  between the eccentricities and the unknown mutual inclinations):
  - β = 2C_p/(Λ' C_c) for every adjacent pair;
  - β_S = 2C_p/Λ_1;
  - β_H = 2β_H,p.
  The coplanar values are reported next to them (details: `beta_coplanar`, `beta_star_coplanar`,
  `beta_hill_coplanar`; `equipartition_factor` = 2).
- The factor 2 is a statistical assumption, not a bound. C/C_p is 2.04 for the inner Solar System and 1.37 for
  all eight planets (Laskar & Petit 2017, Table 1), and large mutual inclinations can push it above 2.
- Critical AMD: Petit et al. (2017), restricted to the domain the paper states:
  - first-order resonance overlap C_MMR for ε ≤ ε_lim and α > max(α_R(ε), 2^{−2/3});
  - the collision criterion C_c (Laskar & Petit 2017) otherwise;
  - β = ∞ for α ≥ α_cir, and only for ε ≤ ε_lim.
- ε_lim = 8.11e-3, the exact root of α_cir(ε) = 2^{−2/3}. The paper's 8.20e-3 comes from rounded constants.
- Why the restriction: for ε > 3.1e-3 the paper's switching rule alone (α > α_R) would apply C_MMR wide of the
  2:1, where the paper says first-order overlap "makes no sense". Its Table E.1 nevertheless lists β^MMR for
  HD 128311 b/c at α = 0.623; exostab follows the text.
- Pairs outside the domain: a pair with α > α_R and either ε > ε_lim (excluded from the paper's sample) or
  α ≤ 2^{−2/3} is flagged (details: `outside_domain`); its β uses the collision criterion, and the system is never
  "stable" by this indicator, because no published AMD criterion accounts for resonance overlap there. A pair
  with α ≤ α_R uses the collision criterion whatever its ε: that is what Petit et al.'s switching rule gives
  there, and the criterion with which Laskar & Petit (2017) classified their catalogue, massive pairs included
  (their Fig. 5 lists HD 147018, HD 168443, HD 169830 and nu Oph, whose wide giant pairs have ε > ε_lim, as
  strongly AMD-stable). Such pairs get a note, not a cap.
- Verdicts:
  - "stable": strongly AMD-stable with C = 2C_p (all β < 1 and β_S < 1), with every pair inside the domain;
  - "unstable": a two-planet system with coplanar β_p ≥ 1 and β_H,p ≥ 1 (Petit et al. 2018). These hold for any
    mutual inclinations, so the equipartition assumption never strengthens a claim of instability;
  - "marginal": everything else, including weakly AMD-stable systems.
- The Hill form is used only for two planets because Petit et al. (2018) note that it does not carry over to
  tightly packed multi-planet systems.
- Planets whose eccentricity is assumed (missing, or 0 without an uncertainty, D24) add no AMD. Since 2026-10-04
  the report names them and says that β and β_S are lower limits; if every eccentricity is assumed, the summary
  says that an AMD-stable verdict rests on that assumption alone. The verdict itself is unchanged (issue proposed:
  "Say when Hill/AMD verdicts rest on assumed circular orbits").
- History: v0.1 (2026-09-28) used the coplanar AMD, β = C_p/(Λ' C_c), with C_MMR for every pair with α > α_R and
  β = ∞ above α_cir, and called "unstable" any two-planet system with β ≥ 1 and β_H ≥ 1. On 2026-10-03 the factor
  2 and the domain were introduced, with every pair of ε > ε_lim capped. On 2026-10-04 the cap was limited to
  α > α_R, after the review found that it removed AMD "stable" from wide giant pairs that Laskar & Petit (2017)
  list as strongly AMD-stable (HD 147018 and HD 168443 are now AMD-stable again). Measured effect of the factor 2
  on 2026-10-03 (archive cache of 2026-09-28, 20 draws, seed 0): 48 AMD verdicts go from stable to marginal, and
  25 overall verdicts from stable to marginal. For HD 127195 (bundled snapshot, default settings) the AMD verdict
  goes from stable to marginal (stable draws 19 → 15 of 20); its overall verdict stays marginal.

## D15 — Verdict combination (final for v0.1; amended 2026-10-04)

- Per indicator: the nominal verdict stands only if ≥ 95% of the draws share it, otherwise "marginal";
  "inconclusive" if the nominal run is, or if > 20% of the draws are. Without draws the nominal verdict is
  returned unchanged.
- Overall: "unstable" only on direct N-body evidence (nominal and ≥ 95% of draws) that rests on no upper-limit
  input, on at least one draw and on a single star; "inconclusive" if the N-body indicator is; "stable" only if
  every indicator says stable, draws were run, and no N-body draw had a close encounter or escape; "marginal"
  otherwise. The overall summary is built from the draw counts. Disagreement is never collapsed into a confident
  verdict.
- v0.1 (2026-09-28) had "stable" only if all three indicators say stable and "unstable" on direct N-body evidence
  alone; the conditions on upper limits, draws, close-encounter draws and companion stars were added on
  2026-10-04 (D27).

## D16 — How the brief's validation expectations are tested

- TRAPPIST-1 "stable or marginal, never unstable": overall verdict in {stable, marginal} and N-body verdict
  not unstable, from the archive snapshot. Measured: marginal.
- GJ 876 "stable": the archive has no usable phases for GJ 876 (D9), and with random phases the Laplace
  resonance is destroyed (archive run: 12 of 20 draws have close encounters). The test therefore uses the
  Rivera et al. (2010) coplanar solution with its mean anomalies (`tests/validation/systems/`) and requires
  the **N-body** verdict to be stable (measured: 20/20 draws regular, ⟨Y⟩ = 1.99). The Hill and AMD criteria
  fail for this resonance-protected system, so the overall verdict is "marginal" by design (D15).
- Kepler-11 "stable over the test horizon": the nominal configuration (archive values, phases from the
  transit times) completes 1e4 orbits of b without close encounters and is regular with WHFast and IAS15;
  N-body and overall verdicts are not "unstable". Measured: the Monte Carlo over the archive uncertainties
  gives 10 regular, 8 chaotic and 2 close encounters of 20 draws (the eccentricity errors are large and the
  draws ignore correlations), so the N-body verdict is "marginal". Reported as found. The nominal Hill test fails
  narrowly for f/g, because the nominal run uses the archive's upper limits for planet g (25 M⊕, e < 0.15).
- Synthetic pair past the Hill limit: overall "unstable" (tested at 2.5 mutual Hill radii). What the Hill-limit
  tests assert: D32.

## D17 — Other deviations and additions (2026-09-28)

- Dependencies: PyYAML added to the core (needed for `--from-file`); no SciPy (a bisection helper
  suffices); pyarrow is an optional `[catalog]` extra for Parquet output.
- CLI options beyond the brief's examples, needed for the tests, the offline demo and speed: `--offline`,
  `--jobs`, `--no-plots`, `--no-ias15`, `--limit` (list), `--max-seconds` (catalog). `sweep --param` accepts
  e, mass (Earth masses), period (days) and omega (degrees).
- Default output folder: `exostab-results/<system>/`; `--out` writes directly into the given folder.
- `catalog build` defaults to 10 draws and a 120 s cap per system; systems over the cap are recorded as
  "timeout" rather than silently shortened.
- The mypy configuration has no fixed `python_version`: recent numpy stubs only type-check for ≥ 3.12,
  and CI runs mypy on every supported version.

## D18 — Archive data issues found (2026-09-28)

- HD 127195: `pl_orblper` = 3.10 and 4.12 "deg". These are the radian values of Figueira et al. (2026,
  Table 2), whose degree label is a typo (noted in the Research Note). Phases are not published in the
  archive, so they are randomized anyway; ω enters only through the apsidal orientation. Reported to the
  archive's helpdesk on 2026-10-16, together with the GJ 876 entry below.
- GJ 876: `pl_orbtper` is the osculating epoch for all four planets (D9).
- `pl_bmassprov` takes the value "M-R relationship", which is not in the archive's column documentation.

## D19 — Time-budget mode (2026-09-28, issue #3)

`--budget fast|thorough|<seconds>` (10 s, 120 s) measures this system's WHFast and IAS15 speed with short runs
and picks the most thorough preset (orbits, draws) from (2e3, 8), (5e3, 10), (1e4, 20), (2e4, 30), (5e4, 50),
(1e5, 100) whose estimated wall time fits. The estimate is overhead (1.5 s) + 1.3 × max(total CPU time /
workers, longest single run); 1.3 is the slowdown measured with all cores busy on an Apple M4 Pro. Runs never go
below the cheapest preset (a warning is printed instead). The IAS15 check is now started first because it is
the longest single job. Measured on TRAPPIST-1: "fast" chose (1e4, 20), estimated 8 s, took 7.8 s; "thorough"
chose (1e5, 100), estimated 90 s, took 82 s. Because the choice depends on the machine, `report.json` records the
chosen orbits and draws and the budget; repeating with `--orbits/--draws/--seed` reproduces the run exactly.

## D20 — Close encounters are detected per pair of planets (2026-09-28; amended 2026-10-04 and 2026-10-13)

Until now a run stopped when any two bodies came closer than the smallest planetary Hill radius (the Research
Note's rule, a single REBOUND `exit_min_distance`). The full catalog run showed the flaw: in K2-157 the
ultra-short-period Earth-mass planet has a Hill radius of 1e-4 AU, so the two outer giants passed within
0.0085 AU of each other (inside planet d's Hill radius) without stopping the run, and WHFast then lost accuracy
(relative energy error 5%). Now each planet gets a REBOUND collision radius of half its Hill radius, with
"line" collision detection (which also catches passages between two steps). A close encounter is therefore two
planets closer than the mean of their Hill radii. For two similar planets this is the Note's rule. Effects on the
validation set: none, except GJ 876 with random archive phases, where two draws changed (3 / 5 / 12 instead of
3 / 6 / 10 + 1 inconclusive): the formerly inconclusive draw and one chaotic draw are now close encounters. (Until
2026-10-13 this entry said that one draw changed.) Measured cost: none.

**A planet passing the star is not a close encounter (amended 2026-10-04).** The v0.1 implementation used
`collision_resolve = "halt"`. REBOUND's collision search also pairs every planet with the star (radius 0), so a
planet closer to the star than half its own Hill radius, a(1−e) < 0.5 a (m/3M_*)^{1/3}, i.e. e above about 0.965
for 1 M_J and 0.925 for 10 M_J around 1 M☉, stopped the run as a close encounter and made it unstable. The
Research Note's `exit_min_distance` rule and SPOCK's set-up share this side effect. Now a Python collision
callback halts only for two planets and records a star approach without stopping the run. A run that reaches its
end after a star approach gets the status `star_approach` and is inconclusive. It is not evidence of a
planet-planet instability, but exostab models neither tides, nor general relativity, nor stellar or planetary
radii, which can decide what happens that close, so it must not count as regular either. This is the conservative
choice and is uncertain (issue proposed: "Use a physical threshold for planets passing close to the star"). The
distance (0.5 R_H) is not a physical limit; it is kept because it is where the search fired before. If two planets
later meet or a body escapes, the run is still unstable. Examples measured on 2026-10-04: `exostab sweep` of
HD 168443 b at e = 0.94–0.95 was unstable at the first pericentre and is now inconclusive; with catalog settings,
Kepler-539 and TOI-4600 have one such draw each and became inconclusive; with CLI defaults TOI-4600 goes from
marginal to inconclusive (3 star-approach draws, 5 of 20 inconclusive).

## D21 — Weekly catalog and its DOI (2026-09-28; amended 2026-10-04 and 2026-10-13)

- `.github/workflows/catalog.yml` runs every Monday: `exostab catalog build --refresh` over every host with two or
  more planets, with 10,000 orbits of the innermost planet, 10 draws, seed 0 and a cap of **300 s of wall time
  per system** (systems over the cap are listed as "timeout"). A full local run on 2026-09-28 (1,060 hosts, 13
  workers on an Apple M4 Pro) took 9.3 minutes, 6,436 CPU-seconds in total, 46 s for the slowest system; no
  system timed out at the 120 s default. On GitHub's `ubuntu-latest` runner, the step "Build the catalog" of the
  two scheduled runs so far took 109 minutes (2026-10-05) and 68 minutes (2026-10-12), with the code of exostab
  0.1.0.dev0 (step times from the GitHub API); the earlier estimate of 1–1.5 hours was too low for the first run.
  How long the current code takes there has not been measured.
- Results go to the branch `catalog-data` (one commit per week, dated CSV copies in `archive/`), not to a GitHub
  release: Zenodo archives every published GitHub release, pre-releases included, as a new version of the
  software record (invenio-github 7.1.2 source, checked 2026-09-28), which would mix weekly data into the
  software DOI. The docs workflow copies the latest files to the site and renders `docs/catalog.md` as a sortable
  table.
- DOI for the catalog: optional. Once the maintainer creates a Zenodo dataset record and stores `ZENODO_TOKEN`
  (secret) and `ZENODO_CATALOG_RECORD` (variable), the workflow publishes a new version of that record every
  week through Zenodo's documented deposit API (`scripts/zenodo_catalog.py`, tested against a fake server only;
  it must be tried on sandbox.zenodo.org first).
- Amended 2026-10-04: the catalog has a row for every host with `sy_pnum ≥ 2` (1,070 on 2026-09-28), the hosts
  with a single planet row included as skipped. A worker still running 5 s after SIGTERM at the cap is killed
  with SIGKILL. A full 12-worker build on the 2026-09-28 data took 695 s, against 754 s before the whole-run
  energy checks (D8), so there is no measurable slowdown (concurrent load not controlled).
- Amended 2026-10-13: the workflow published its first catalogs on `catalog-data` on 2026-10-05 and 2026-10-12.
  Both were computed with exostab 0.1.0.dev0, before the changes of October 2026 recorded here, and will be
  replaced by the first weekly run after those changes reach `main`.

## D22 — JOSS paper draft (2026-09-28; amended 2026-10-13)

`paper/paper.md` follows the JOSS requirements checked on 2026-09-28: 750–1750 words (checked by
`scripts/paper_wordcount.py` in `.github/workflows/paper.yml`), the six required sections (Summary, Statement of
need, State of the field, Software design, Research impact statement, AI usage disclosure) and `paper.bib` with
DOIs and full journal names. It cannot be submitted yet: JOSS (scope update of January 2026) desk-rejects
repositories that have not been public, with development spread over time, for more than six months, so the
earliest submission is about April 2027, with regular releases in between. The AI usage disclosure and the
research impact statement must be confirmed and updated by Mehmet before submission. On 2026-10-13 the draft was
updated for SPOCK, the current validation numbers and the catalog.

## D23 — SPOCK as an optional indicator in a separate environment (2026-09-28, issue #4; amended 2026-10-03 and 2026-10-04)

SPOCK 2.1.1 (latest) pins `rebound<5` and crashes with REBOUND 5.2 (it uses `sim.N_real` and `sim.ri_whfast`, and
sets attributes REBOUND 5 no longer allows); no branch or pull request adds REBOUND 5 support (checked
2026-09-28). exostab therefore runs SPOCK as a separate program: `scripts/make_spock_env.sh` builds a Python 3.12
environment with the tested versions (spock 2.1.1, rebound 4.6.0, reboundx 4.6.2, celmech 1.5.8, xgboost 2.1.4,
scikit-learn 1.5.2, plus pandas and ipython, which SPOCK and celmech import without declaring them), and
`exostab check --spock` sends the initial conditions of every run to `indicators/spock_worker.py` in that
environment as JSON. SPOCK is GPL-3.0; it is not imported or distributed by exostab (MIT). On macOS the worker
restarts itself with `DYLD_LIBRARY_PATH` set to the libomp that scikit-learn bundles, so no Homebrew install is
needed.

Verdicts: estimate ≥ 0.34 → stable, else unstable, per run; 0.34 is Tamayo et al. (2020)'s threshold for a 10%
false-positive rate on the resonant hold-out set (the retrained 2.x model has no published threshold). SPOCK can
make the overall verdict marginal but never unstable by itself; it runs only for three or more planets; the
report warns outside the training domain (mass ratios 1e-7–1e-4, and spacings above 30 mutual Hill radii in the
radius of SPOCK's training set, see the amendment below). Measured: TRAPPIST-1 estimate 0.706 (20/20 draws above
the threshold). The indicator set of v0.1 is unchanged unless `--spock` is given; whether to keep, change or drop
this design is Mehmet's decision (issue #4).

*Amended 2026-10-03.* SPOCK is deliberately not a pip extra, because an extra would have to install REBOUND < 5
next to exostab's REBOUND 5. `scripts/make_spock_env.sh` is in the sdist but not in the wheel; pip users download
it from https://raw.githubusercontent.com/mimitoz62/exostab/main/scripts/make_spock_env.sh. Running it again
rebuilds the environment (`UV_VENV_CLEAR=1`), and a target folder that exists but is not a virtual environment is
refused. Only SPOCK and the packages around it are pinned (spock, rebound, reboundx, celmech, xgboost,
scikit-learn, safetensors); torch, numpy and the other transitive dependencies are not. A rebuild on 2026-10-03
installed torch 2.14.1 and sympy 1.14.0rc1, and `tests/test_spock.py` passed with it.

*Amended 2026-10-04: the spacing of the training domain.* v0.1 measured spacings in the Hill indicator's mutual
Hill radius. On 2026-10-03 it was changed to the paper's Eq. 1, R_H = a_i ((m_i + m_{i+1})/M_*)^{1/3}. The code
that generated SPOCK's training set (dtamayo/spock, `run_integrations/runfunctions.py`: `run_random` and
`get_resonant`) uses a_i ((m_i + m_{i+1})/(3M_*))^{1/3}, with spacings up to 30 of these radii, and the paper's
lower limit of 3.5 radii, "the Hill stability limit", matches 2√3 only with the factor 3. exostab now uses the
training code's radius and warns above 30. With the inner semi-major axis it differs from the Hill indicator's
radius: 30 of these radii are 21.3 of the Hill indicator's for two planets of 3e-5 M_* and 26.5 for 1e-6.

## D24 — Data completion after the October 2026 review (2026-10-03; amended 2026-10-04 and 2026-10-31)

Measured on the archive cache of 2026-09-28 (2,663 rows, 1,070 hosts) unless stated.

- **Stellar mass.** The composite table picks `st_mass` per planet row. 216 hosts have more than one (value,
  errors, reference) entry, 198 differ in the value and 61 by more than 10%, and the archive returns rows in no
  fixed order (v0.1 used whichever row came first). A measured planet mass scales with the stellar mass its
  publication assumed (m sin i as M_*^{2/3} from radial velocities, m as M_* from transit-timing mass ratios).
  Rule since 2026-10-04: if one publication gives more of the measured (not radius-estimated) planet masses than
  any other and a row gives that publication's stellar mass, that value is used (47 hosts); otherwise the median
  of the rows, for an even number with differing middle values the lower one (a smaller star gives larger
  planet-to-star mass ratios, the less stable choice). Ties go to the most common (errors, reference). The flag
  `star_mass_inconsistent` lists every value and says which rule chose it. The median rule alone was used from
  2026-10-03; the publication rule changes the value for 10 hosts (among them Kepler-968 0.76 → 0.681, Kepler-282
  0.86 → 0.97, HD 114386 0.6 → 0.8), with no verdict change found. Against the first-row rule of v0.1, 81 hosts
  got a different M_* on 2026-10-03, and the Hill or AMD verdicts (20 draws, seed 0) of 5 changed, all towards
  less confidence: Kepler-114 (nominal Hill), Kepler-81 (Hill), Kepler-58 and HD 155358 (AMD) went from stable to
  marginal, and HIP 57274's Hill indicator no longer fails. *Uncertain:* planet masses derived with another M_*
  are not rescaled (issue proposed: "Rescale planet masses to the stellar mass used, or propagate the
  stellar-mass spread").
- **Stellar-mass limits** (`st_masslim` ≠ 0) are not used: a measured value from another row is used
  (`star_mass_limit_ignored`), otherwise the system is rejected. None occur today.
- **Upper limits** are allowed only on planet masses and eccentricities, where the limit is the worst case for
  stability. For the stellar mass the limit is the most stable case, and drawing it uniformly from 0 is
  meaningless. YAML refuses other limits, and sampling refuses misplaced ones.
- **e = 0 without an uncertainty** is a circular orbit fixed in the source's fit (all 1,031 DR25 KOI
  eccentricities): "assumed", flag `eccentricity_fixed_zero_by_source`. 554 hosts and 1,266 planets are affected.
  The numbers are unchanged (held at 0, as a missing e is).
- **e above E_MAX = 0.95** (nominal value or upper limit) is rejected instead of capped in the nominal run. None
  occur today. The reason for the 0.95 cap itself is not yet documented (issue proposed: "Document or revisit
  the 0.95 eccentricity cap; make `sweep --param e` consistent with it").
- **No period, microlensing or imaging planet:** rejected, because `pl_orbsmax` can be the projected sky
  separation (archive column definition: "for exoplanets detected via gravitational microlensing or direct
  imaging, the projected separation in the plane of the sky"). 10 hosts are newly rejected, so 1,034 of 1,070 can
  be modelled. *Uncertain* for imaging planets with orbit fits (PDS 70 c, TYC 8998-760-1 b): rejected
  conservatively (issue proposed: "Accept directly imaged planets whose semi-major axis comes from an orbit fit").
- **Time of periastron** is used only when the argument of periastron is also published (D9).
- **Mass kind:** "Msini" of a transiting planet is a true mass (`msini_of_transiting_planet`). A lower limit on
  the mass of a non-transiting planet is a minimum mass. 19 planets in 14 hosts change; default runs are
  unchanged.
- **YAML:** if `semimajor_axis_au` is given with `period_days`, the two must agree within max(10%, 3σ_a/a).
  *Uncertain tolerance:* 10% allows stellar masses from different sources, since a ∝ M_*^{1/3}. Unknown star keys
  are refused, `mass_kind` must match the mass given, and non-finite numbers (`.nan`, `.inf`) are refused (since
  2026-10-04: a NaN angle or epoch used to stop every integration at once, which was reported as a close
  encounter). `epoch_jd` is required when mean anomalies or mean longitudes are combined with transit or
  periastron times, and `mean_anomaly_deg` and `periastron_time_jd` need `omega_deg`.
- **Names:** exact host and planet names win ("55 Cnc b" is 55 Cnc, not the companion star 55 Cnc B); an
  ambiguous normalised name raises an error. When only the offline snapshot was searched, a missing system is
  reported as missing from the snapshot (in the web app too, since 2026-10-04).
- **Cache:** written atomically; the row count and SHA-256 are checked on load.

*Amended 2026-10-31.* **Upper limits:** the limit is not always the worst case (see the amendment of D11). **Names:**
a name that only planets carry now finds their host when the whole query is a planet name without its final letter.
The archive's host of Kepler-90 i is KOI-351, and "Kepler-90" used to get the suggestion Kepler-990. If the planets of
several hosts carry the name ("TOI-2267"), the query is refused as ambiguous. Other forms of a name ("Gliese 876",
"Upsilon Andromedae", "Kepler-90 h") are guesses, so they are only suggested in the error and never resolved: a wrong
guess would check another system. When there is no suggestion, the error points to `exostab list`, and in the web app
to its search box.

## D25 — Dependency lower bounds are tested (2026-10-03)

The lower bounds in `pyproject.toml` had never been installed. pip keeps an installed version that satisfies a
bound, so a bound that does not work breaks real installations. Measured on Python 3.10 with uv's lowest-direct
resolution:

- typer: 0.12.0–0.12.3 cannot parse `str | None` options, and 0.12.4–0.15.3 crash or misbehave with click ≥ 8.2.
  So typer ≥ 0.16, which works with click 8.0.0, 8.1.8 and 8.5.0.
- pydantic: 2.5–2.10 write a different JSON schema than the shipped `report.schema.json` (2.10.6 fails the schema
  test, 2.11.0 passes). So pydantic ≥ 2.11.
- hatchling: 1.21–1.25 cannot read the PEP 639 `license-files` array, and 1.26 writes legacy license metadata. So
  hatchling ≥ 1.27.

With these bounds and every other direct dependency at its own lower bound (numpy 1.24.0, astropy 5.3,
astroquery 0.4.7, rebound 5.2.0, matplotlib 3.7.0, rich 13.0.0, platformdirs 3.0.0, pyyaml 6.0, streamlit
1.50.0, plotly 6.0.0, pyarrow 14.0.0, pytest 8.0.0), the fast suite passes. The CI job `lowest` repeats this and
also builds the wheel without isolation using hatchling 1.27.0. That job resolves transitive dependencies to their
newest versions, so old transitive versions are covered only by the click spot checks above.

## D26 — Version 1.0.0 and what a release must pass (2026-10-03; amended 2026-10-04)

The first public release is 1.0.0 (Mehmet's choice: it covers the three milestones of the brief). `CITATION.cff`
carries the version and, for a release, `date-released`. A unit test keeps it consistent with `__version__`, and
another requires a `## [X.Y.Z]` section in `CHANGELOG.md` for a release version and an `[Unreleased]` section for
a development version. The release workflow refuses a tag that does not match `__version__`, `CITATION.cff` and a
`CHANGELOG.md` section. Until the release, the version is `1.0.0.dev0` (since 2026-10-04: the version had been
set to 1.0.0 with a release date before the changelog section existed); release preparation sets the version, the
`CITATION.cff` date and the date of the `[1.0.0]` section together (RELEASING.md).

Nothing is published, to PyPI or to GitHub and Zenodo, unless the built wheel passes ruff, mypy, the fast suite
and the CLI smoke test (Ubuntu and macOS, Python 3.10 and 3.14) and the slow validation suite (Ubuntu and macOS,
Python 3.12). Requiring the validation suite is the conservative choice. It adds about five minutes to a release
and blocks publishing while any comparison with published results fails. On 2026-10-03 the nightly run failed
the Hill-limit test at 3.0 mutual Hill radii on Ubuntu only; that test was replaced on 2026-10-04 (D32).

PyPI is optional (repository variable `PUBLISH_PYPI`). Setup steps for every service are in `RELEASING.md`.

## D27 — Overall verdict: upper limits, zero draws, close-encounter draws and multiple stars (2026-10-04; amended 2026-10-31)

- **Upper limits never give overall "unstable".** When an input is only a published upper limit, the nominal run
  uses the limit and the draws are uniform below it (D11). That is the worst case for a stable verdict, which
  therefore stands, but an N-body instability found this way only constrains the limited values. Example: the
  archive's masses of the four planets of HD 215152 are upper limits of 469 to 975 M⊕ (cache of 2026-09-28). Such
  a system is "marginal", not "inconclusive", because the integration itself is trustworthy and "inconclusive"
  keeps its meaning (the runs cannot be trusted). Any limited input triggers the rule, not only one that took
  part in the encounter: the conservative minimum. Its cost: KOI-319, whose instability persisted in a review
  measurement with planet b at a mass-radius estimate, also drops from unstable to marginal (issues proposed:
  "Keep an 'unstable' verdict that does not depend on the upper-limit values" and "Use a physical nominal mass
  instead of a loose upper limit"). With weekly-catalog settings HD 215152, HR 8799 and KOI-319 change from
  unstable to marginal.
- **Zero draws.** With `--draws 0` nothing is tested against the uncertainties, so the overall verdict is at most
  "marginal", in both directions. The per-indicator verdicts stay nominal, because a per-indicator "marginal"
  would make the indicators add the false note that the draws disagree.
- **One close-encounter draw blocks an overall "stable".** The per-indicator 95% rule (D15) lets the N-body
  indicator say "stable" with 1 encounter in 20 draws. Tamayo et al. (2020) treat Hill-sphere crossing as
  instability, which is exostab's encounter test (D20), and 1 failing draw in 20 bounds the unstable fraction only
  below about 22% (one-sided 95% binomial limit). The uncertainty against this choice: the draws
  ignore correlations in the published posteriors, so one failing draw can be an unphysical combination. Mehmet to
  confirm (issue proposed: "Decide: should one close-encounter draw block an overall 'stable'?"). Chaotic N-body
  draws and draws failing the analytic criteria are reported in the summary and in `overall.reasons`, but do not
  change the verdict. Measured with CLI defaults (cache of 2026-09-28, seed 0): HD 152843, HD 207832 and
  KMT-2022-BLG-1818L change from stable to marginal; the 10-draw weekly catalog is not affected.
- **Several stars.** Only the host star is modelled (D11). In a system with more than one star (`sy_snum > 1`),
  the planets may orbit different stars, or a companion may change their orbits, so an N-body instability gives
  "marginal". Kepler-132 b and c, whose periods differ by 4%, cannot stably orbit one star. Kepler-132, Kepler-197
  and Kepler-444 change from unstable to marginal (10 draws, 1e4 orbits); the last two are unstable because of
  their large measured eccentricities, and are downgraded too (issue proposed on modelling companion stars).
- The overall summary is built from the draw counts and never claims more than they show; a stable summary lists
  any draws that failed an indicator.

*Amended 2026-10-31.* "The worst case for a stable verdict, which therefore stands" holds for Hill spacing and the
integration, but not always for AMD: see the amendment of D11. The rule is unchanged.

## D28 — Shared web-app links are validated and cost-limited (2026-10-03; amended 2026-10-04)

A link is untrusted input. `decode_state` accepts only what the app itself can produce: a finite budget clamped
to 5–120 s, a seed in 0..2^31−1, at most the longest budget preset (1e5 orbits, 100 draws), table edits within the
columns' ranges (period ≥ 1e-3 d, mass ≥ 1e-6 M⊕, e ≤ 0.95), and a what-if using a slider mass factor,
0 ≤ e ≤ 0.95 and a period ratio between 1 and 1e5 (the widest adjacent pair in the archive is about 1.1e4 apart in
period). Anything else falls back to the default. A link's run length is used only if `budget.estimate_seconds`
at the speed measured on the server (one process, IAS15 check included) is at most `BUDGET_MAX` = 120 s;
otherwise the run length chosen for the link's budget on that server is used and the page says so. Because of
this a link made on a fast machine may not reproduce exactly on a slow server. The estimate is a linear
extrapolation of short timing runs and does not include SPOCK, so it is not a hard wall-clock limit (issue
proposed: "Web app: enforce a wall-clock limit on integrations, not only an estimated cost"). The cache key and the
report use the resolved run length. `settings.budget_s` is recorded only when the budget chose the run length on
this server, so a hand-made link never claims a budget it did not use. A link does not pin the archive data
(it holds no values and no download date); docs/web.md says so.

## D29 — Infinity in report.json, and report schema 1.3 (2026-10-03)

JSON has no infinities. Non-finite floats are written as the strings "inf" / "-inf" and NaN as null, so an
infinite AMD β (resonance overlap on circular orbits, the most unstable case) is no longer confused with a missing
value. This matches catalog.csv, which writes "inf". `float("inf")` parses the string, and pydantic float fields
accept it.

The report schema went from 1.2 to 1.3 with the changes of October 2026: this encoding, new completion flags, new
keys in the indicator details (for example `beta_coplanar`, `outside_domain` and `star_approach`), the status
value `star_approach`, and overall summaries built from the draw counts. *Uncertain:* the AMD values `beta`,
`beta_star` and `beta_hill` now mean twice the coplanar value, and `total_amd_relative_to_lambda_1` was removed.
These sit in the free-form `details`, so the JSON Schema itself does not change, but the module's own rule counts
a renamed or removed field as a major change; whether this needs 2.0 was decided in D33 (it stays 1.3).

## D30 — `exostab sweep --range` has no default except for e (2026-10-03)

The old default (0, 0.5) suits only the eccentricity, and inventing defaults for mass, period and omega would be
guesswork. `--param e` keeps 0 to 0.5; the other parameters require `--range`. Both ends are checked with the same
rules as each swept value before anything runs. `sweep.json` records the seed, run length, range, steps,
integrator, time step, command and creation time.

## D31 — Packaged web entry point (2026-10-03; amended 2026-10-31)

`python -m exostab.web` runs `streamlit run` on `src/exostab/web/streamlit_app.py`, a packaged copy of the root
`streamlit_app.py`; the root file stays for clones and Streamlit Community Cloud. The SPOCK setup script is not
packaged; the CLI gives its GitHub URL (it needs uv and a C compiler, not a clone).

*Amended 2026-10-31.* The wheel has no `.streamlit/config.toml`, so the launcher passes its settings on the command
line, before the user's arguments, which can override them: `--server.headless true`,
`--browser.gatherUsageStats false` and `--client.toolbarMode viewer`. Without the first, the first run outside a clone
stopped at Streamlit's email prompt, and nothing was served until Enter was pressed. In headless mode no browser opens,
as in a clone, and Streamlit looks up the public IP address at every start and prints it as External URL.
`--browser.serverAddress localhost` would avoid that, but it has not been tried in a codespace or behind Binder's proxy,
which use this launcher, so it stays out for now.

## D32 — What the Hill-limit validation asserts (2026-10-04)

Inside the Gladman limit the time to the first close encounter is a chaotic transient that depends on the last
bit of the initial conditions: at 3.0 mutual Hill radii, moving one starting phase by one unit in the last place
turned an encounter after 1,192 orbits into no encounter within 5,000. The v0.1 test asserted that all 8 phases
meet within 5,000 orbits at 2.5 and at 3.0. In a study of 501 sets of 8 phases whose initial conditions were
perturbed by a relative 1e-14 (standing in for other platforms), that failed in 33% of the sets at 3.0 and in
about 29% at 2.5, and it failed on CI on Ubuntu x86_64. The test now asserts only outcomes that cannot depend on
rounding: at 2.2 every phase meets (at the first conjunction); at 4.0 and 4.5, beyond the limit, none meets
within 5,000 orbits; and at 3.0 no phase is regular and at least 6 of 8 meet within 2e4 orbits. In the perturbed
sets at 3.0, never more than 2 of 8 phases missed within 2e4 orbits, and the runs that missed stayed chaotic
(⟨Y⟩ > 13). Notebook 02's "encounters stop between 3.30 and 3.35" used a different encounter distance (one mutual
Hill radius), time step (P/50) and grid, and is no longer claimed as reproduced (docs/validation.md).

## D33 — Release decisions for 1.0.0 (2026-10-16)

- **Version and maturity.** The first public release is 1.0.0 (the owner's choice: it completes the three
  milestones of the brief). The classifier is "Development Status :: 4 - Beta", not "5 - Production/Stable": no
  one outside the project has used exostab yet, and the thresholds behind the verdicts have open calibration
  issues. Within 1.x, the CLI options, the verdict vocabulary and the report fields are kept; a change that removes
  or renames any of them needs 2.0.
- **Report schema 1.3, not 2.0.** The AMD values in the indicator details changed meaning, and one key was removed,
  between schemas 1.2 and 1.3 (D29). No schema before 1.3 was ever released, so no published report or consumer is
  affected, and the public schema history starts at 1.3. From here on the rule in `report.py` applies as written.
- **Schema `$id`.** The `$id` is https://mimitoz62.github.io/exostab/schemas/report-1.3.json. The docs workflow
  copies the generated schema to that path, so the identifier resolves. Older `$id` values pointed at a GitHub URL
  that did not exist.

## D34 — Licence of the catalog data, and the status of the Research Note (2026-10-31)

- **Catalog data: CC BY 4.0** (the owner's choice). It covers what exostab computes, and reuse has to credit the catalog
  wherever such rights apply to data. The archive's own acknowledgement request stays. The weekly job copies
  `scripts/catalog_data_license.txt` to the branch `catalog-data`, because the licence must travel with the files.
- **Research Note: "prepared for Research Notes of the AAS", not "submitted".** The files said "submitted" from
  28 September, but the Note's own repository says "prepared for", and Crossref and arXiv show no record on 31 October.
  "Prepared for" holds whatever the journal's records show, so it replaces the stronger word until the owner gives a
  status or a DOI.

## D35 — The two-planet calculator (2026-10-31)

- **A port, kept in step by a test.** The documentation site has no Python, so `docs/javascripts/calculator.js` repeats
  the formulas, constants and two-planet verdicts of `indicators/hill.py` and `indicators/amd.py`.
  `tests/test_calculator.py` compares the two on random pairs. A few numbers are differences of nearly equal terms (the
  Gladman margin and C_H, which β_H divides by), and the search for the circular-orbit limit looks for a margin smaller
  than rounding when the masses are very unequal. There the test allows for rounding, in absolute terms, and nowhere
  else. Without `node` the test skips, except in GitHub Actions, where it fails, so that CI cannot stay green with the
  port unchecked.
- **No overall verdict.** The page gives the verdict of each of the two indicators for the numbers entered, without
  draws. `overall_verdict` needs an integration and draws, and a combined word would suggest a check that did not take
  place.
- **Input limits.** Eccentricities up to `E_MAX`, as in exostab's loaders. Planet masses from 1e-12 stellar masses,
  because rounding decides `gladman_critical_separation` far below that (for 1e-6 and 1e-18 stellar masses it gives 2.51,
  and for 1e-6 and 1e-19 it gives 0), and below the stellar mass. The loaders set neither mass limit. Two planets with
  the same period or semi-major axis are refused, because neither would be the outer planet; exostab accepts equal
  periods and takes the first planet as the inner one. Values so far out of range that Λ or the period ratio no longer
  fits in a number (a stellar mass of 1e300 with masses to match) are refused too: `amd.analyse` gives β = NaN there,
  and the page gives no verdict on that.
- **Which planet is the outer one.** A semi-major axis becomes a period for the star and that planet alone, as in
  `data/files.py`, and the planets are sorted by period, as in `sampling.realize`. The Jacobi semi-major axes of
  `Realization.semi_major_axes` then always grow outwards, so "the larger semi-major axis" holds for the values the page
  shows. Entered axes closer than about m / 3M★ can come out in the other order; such pairs fail the Hill test either
  way.
