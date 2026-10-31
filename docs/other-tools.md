---
title: "exostab and other tools: REBOUND, SPOCK, ExoNAMD, Mercury and the archive"
description: >-
  How exostab relates to REBOUND, SPOCK, ExoNAMD, Mercury, SWIFT, the NASA Exoplanet Archive, Exostab 2.0 and the
  published AMD-stability catalogues: what each does, how it differs, and when to use it.
---

# exostab and other tools

exostab takes a known multi-planet system from the NASA Exoplanet Archive, or parameters you give it, and reports Hill
spacing, the angular momentum deficit (AMD) and an N-body integration with MEGNO. It repeats them for draws within the
published error bars and prints each rule it used to fill gaps in the data; [Data and assumptions](data-assumptions.md)
and [Methods](methods.md) state its other assumptions. It uses some of the tools below and replaces none of them. For
each one, this page says what it does, how it differs from exostab, and when to use it instead of exostab or together
with it.

What the page says about other tools comes mainly from their own documentation, repositories, code records and papers,
read on 31 October and 1 November 2026. It can go out of date. If something here is wrong, please
[open an issue](https://github.com/mimitoz62/exostab/issues).

## What exostab does not do

exostab is not a replacement for a long integration or a dedicated dynamical study. By default it integrates for 10,000
orbits of the innermost planet, which is 41.4 years for TRAPPIST-1, and it stops a run at the first close encounter
between planets. It places all orbits in one plane, draws parameters independently from their error bars, and does not
model tides, general relativity, stellar evolution or companion stars. It does not fit observations.
[Methods](methods.md) gives the details, and [Validation](validation.md) says what exostab has been compared with.

A stable verdict means that exostab calls the parameter set it used stable under these settings. It is not a proof. A
marginal verdict does not mean unstable.

exostab has no refereed paper yet. A draft for the Journal of Open Source Software is in the repository and has not been
submitted. For now, cite the software with its DOI, the papers behind the methods and the archive, as
[Citing exostab](citing.md) describes.

## REBOUND

[REBOUND](https://rebound.hanno-rein.de/) (Rein & Liu 2012) is an N-body integrator written in C, with a Python module
and integrators such as WHFast, IAS15 and MERCURIUS; the set-up, the run length and the reading of the result are up
to you. exostab uses WHFast (Rein & Tamayo 2015), IAS15 (Rein & Spiegel 2015) and MEGNO from REBOUND, in one fixed
set-up, and adds the archive's values, the completion rules, the draws, the analytic indicators and a verdict. Use
REBOUND directly for a longer run, inclined orbits, another integrator, a run through close encounters, or added physics
such as general relativity and tides with [REBOUNDx](https://reboundx.readthedocs.io/) (Tamayo, Rein, Shi & Hernandez
2020). [REBOUND's README](https://github.com/hannorein/rebound#papers) lists the papers that describe the code, for your
own citations.

The key `nominal` in `report.json` holds the starting values of exostab's nominal run, as Jacobi elements with
inclination and node 0, and `settings` holds its time step and length. The MEGNO value ⟨Y⟩ depends on the seed of the
variational particles, so a restart need not match the report unless it uses the same seed, which `megno_seed(seed, 0)`
in `exostab.indicators.megno` derives from `settings.seed`. For the nominal TRAPPIST-1 run over 10,000 orbits, different
seeds give values on both sides of exostab's chaotic threshold of 2.2.

## SPOCK

[SPOCK](https://github.com/dtamayo/spock) collects machine-learned and analytical tools for estimating the stability of
compact planetary configurations, given as a REBOUND simulation. Its FeatureClassifier (Tamayo et al. 2020) gives an
estimate, which SPOCK's README calls a probability, that a three-planet system is stable past a billion orbits, and
exostab can run it as an optional fourth indicator, with `exostab check --spock`, for three or more planets. It runs in
a separate Python environment, because SPOCK 2.1.1 needs REBOUND below version 5 and exostab needs version 5, and it can
make the overall verdict marginal but never unstable on its own ([Methods](methods.md#optional-indicator-4-spock)). Use
SPOCK directly for configurations you set up yourself, or for its other models, such as the instability times of its
DeepRegressor (Cranmer et al. 2021).

## ExoNAMD

[ExoNAMD](https://exonamd.readthedocs.io/) (Bocchieri, Zak & Turrini 2026) is a Python package that computes the
normalized AMD, a measure of a system's dynamical excitation, from NASA Exoplanet Archive data, in one form with
relative inclinations and in another with the spin-orbit angle. Its authors present it as a lower limit on past
excitation, to complement stability metrics, which concern the future. exostab asks a different question of the AMD,
whether a system has enough of it for orbits to cross, and uses no spin-orbit angles. Use ExoNAMD to compare dynamical
excitation between systems; its authors describe its use "in combination with metrics such as AMD, MEGNO, and SPOCK", so
the two can be read side by side.

## Published AMD-stability catalogues

exostab is not the first to sort known systems by AMD stability. Laskar & Petit (2017) applied the criterion to 131
multi-planet systems from the [Extrasolar Planets Encyclopaedia](https://exoplanet.eu/), those with measured masses,
semi-major axes and eccentricities for all their planets, and their coefficients are in the
[VizieR catalogue J/A+A/605/A72](https://doi.org/10.26093/cds/vizier.36050072). Petit, Laskar & Boué (2017) applied
their resonance-overlap criterion to 111 of these systems. Earlier work also tested Kepler candidate systems with
numerical integrations (Lissauer et al. 2011) and Hill spacing (Fabrycky et al. 2014), using a mass-radius relation.

exostab's AMD indicator uses these criteria and says stable only for what Laskar & Petit call "strong AMD-stable". The
weekly [catalog](catalog.md) takes the NASA Exoplanet Archive's composite table, fills gaps by stated rules, and reports
Hill spacing and N-body integration as well. Because it fills gaps, many of its verdicts rest on assumptions: 512 of the
619 stable verdicts of 26 October 2026 have every eccentricity assumed 0 ([What the catalog shows](findings.md)).

Use the published tables for the coefficients as their authors computed them. Those of Laskar & Petit use the collision
criterion and a mean eccentricity, √⟨e²⟩, that includes the error bars, so they are not directly comparable with
exostab's nominal `beta`, which uses the central value and, for close pairs, resonance overlap. Cite these papers as
prior work when you report the AMD stability of known systems.

## Mercury, SWIFT and other long-term integrators

Each of these integrates the initial conditions you give it, for as long as you choose, and leaves the reading of the
result to you.

- [Mercury](https://ascl.net/1201.008) ([code](https://github.com/smirik/mercury); Chambers 1999) is a package for
  orbital integrations in solar-system dynamics, and its ASCL entry names the long-term stability of the planetary
  system among its uses. It records close encounters, ejections and collisions, and its hybrid integrator permits close
  encounters between massive bodies.
- [SWIFT](https://www2.boulder.swri.edu/~hal/swift.html) (Levison & Duncan 1994) integrates massive bodies together with
  test particles, with a choice of four integrators.
- [SyMBA](https://doi.org/10.1086/300541), the symplectic massive body algorithm of Duncan, Levison & Lee (1998), uses a
  multiple time step method for close encounters.
- [Swiftest](https://github.com/MintonGroup/swiftest) (Wishard et al. 2023) is a rewrite of the Swifter package for the
  long-term dynamics of n-body systems with a dominant central body.
- [GENGA](https://bitbucket.org/sigrimm/genga) (Grimm & Stadel 2014) is a hybrid symplectic integrator that runs on
  GPUs.

This is the work exostab does not replace. Its default run is 10,000 orbits of the innermost planet, and the billion
orbits of SPOCK's classifier are 100,000 times that; `--orbits` lengthens the run but keeps the same simplified set-up.
Use one of these codes when your question depends on a long integration, or REBOUND itself, whose documentation calls
its MERCURIUS integrator (Rein et al. 2019) "very similar to MERCURY". exostab can be a first look, and `nominal` in
`report.json` gives the starting values it used, as Jacobi elements: convert them if a code expects elements relative
to the star.

## NASA Exoplanet Archive

The [NASA Exoplanet Archive](https://exoplanetarchive.ipac.caltech.edu/) is "an online astronomical exoplanet and
stellar catalog and data service", and exostab takes its values from the archive's
[Planetary Systems Composite Parameters table](https://exoplanetarchive.ipac.caltech.edu/docs/pscp_about.html), which
the archive calls "a more complete, though not necessarily self-consistent, set of parameters". The archive's overview
and table schema list no stability indicator; exostab adds the indicators and records the publication behind each value.
Go to the archive for the values and their sources. For the solution of one paper, the archive points to its Planetary
Systems table, with one row per planet per reference: write the values to
[a YAML file](data-assumptions.md#your-own-parameters) and run `exostab check --from-file`. Cite the archive too
(Christiansen et al. 2025; [The data](citing.md#the-data)).

## Exostab 2.0

[Exostab 2.0](https://exostab2.readthedocs.io) is an unrelated project with a similar name. It is an online service,
with a [web tool](https://apexgroup.web.illinois.edu/stability/index.html) and an API, that gives stability limits for
circumbinary planets from a database of long-term simulations (Georgakarakos et al. 2024). That paper describes it as a
reboot of ExoStab (Pilat-Lohinger & Eggl 2011), an earlier web tool for the dynamical stability of extrasolar planets,
which has the same name as this project and is also unrelated to it. exostab models a single host star and rejects
circumbinary systems, so use Exostab 2.0 for a planet that orbits two stars.

## celmech

[celmech](https://celmech.readthedocs.io/) (Hadden & Tamayo 2022) is a Python package of numerical tools for celestial
mechanics, designed to interface closely with REBOUND. Its functions `AMD_stable_Q` and `AMD_stability_coefficients`
take a REBOUND simulation and follow Laskar & Petit (2017), while exostab has its own AMD code and adds the draws and
the other indicators. celmech's coefficients use the simulation's own AMD. For a coplanar simulation they are close to
exostab's `beta_coplanar`, which is half of `beta`, for pairs where exostab uses the collision criterion.
`AMD_stable_Q` tests the pairs, not the star. Use celmech when you want these coefficients inside your own REBOUND work.

## The Exo-Striker

[The Exo-Striker](https://github.com/3fon3fonov/exostriker) (Trifonov 2019) fits radial velocities and transits and
performs N-body simulations, and its feature list includes an instant AMD stability check and a long-term stability
check with SyMBA and MVS. exostab fits nothing: it takes published values or the values you give it. Use the Exo-Striker
when you are fitting your own data; to run exostab's indicators on the result, write the solution to
[a YAML file](data-assumptions.md#your-own-parameters) and use `exostab check --from-file`.

## ARDENT

[ARDENT](https://github.com/manustalport/ardent) (Stalport et al. 2025) computes exoplanet detection limits from radial
velocity data and adds an orbital stability constraint, with analytic criteria based on the AMD and, for the cases these
leave open, REBOUND's WHFast over 10⁴ orbits of the outermost planet. exostab does not inject planets or give detection
limits. Use ARDENT to ask where a further planet could be, or whether a candidate is dynamically plausible.

## References

- Bocchieri, A., Zak, J. & Turrini, D. 2026, A&A 706, A222,
  [doi:10.1051/0004-6361/202557279](https://doi.org/10.1051/0004-6361/202557279)
- Chambers, J. E. 1999, MNRAS 304, 793,
  [doi:10.1046/j.1365-8711.1999.02379.x](https://doi.org/10.1046/j.1365-8711.1999.02379.x)
- Christiansen, J. L., et al. 2025, PSJ 6, 186, [doi:10.3847/psj/ade3c2](https://doi.org/10.3847/psj/ade3c2)
- Cranmer, M., Tamayo, D., Rein, H., et al. 2021, PNAS 118, e2026053118,
  [doi:10.1073/pnas.2026053118](https://doi.org/10.1073/pnas.2026053118)
- Duncan, M. J., Levison, H. F. & Lee, M. H. 1998, AJ 116, 2067,
  [doi:10.1086/300541](https://doi.org/10.1086/300541)
- Fabrycky, D. C., Lissauer, J. J., Ragozzine, D., et al. 2014, ApJ 790, 146,
  [doi:10.1088/0004-637x/790/2/146](https://doi.org/10.1088/0004-637x/790/2/146)
- Georgakarakos, N., Eggl, S., Ali-Dib, M. & Dobbs-Dixon, I. 2024, AJ 168, 224,
  [doi:10.3847/1538-3881/ad7a78](https://doi.org/10.3847/1538-3881/ad7a78)
- Grimm, S. L. & Stadel, J. G. 2014, ApJ 796, 23,
  [doi:10.1088/0004-637x/796/1/23](https://doi.org/10.1088/0004-637x/796/1/23)
- Hadden, S. & Tamayo, D. 2022, AJ 164, 179,
  [doi:10.3847/1538-3881/ac8d01](https://doi.org/10.3847/1538-3881/ac8d01)
- Laskar, J. & Petit, A. C. 2017, A&A 605, A72,
  [doi:10.1051/0004-6361/201630022](https://doi.org/10.1051/0004-6361/201630022); tables at the CDS,
  [doi:10.26093/cds/vizier.36050072](https://doi.org/10.26093/cds/vizier.36050072)
- Levison, H. F. & Duncan, M. J. 1994, Icarus 108, 18,
  [doi:10.1006/icar.1994.1039](https://doi.org/10.1006/icar.1994.1039)
- Lissauer, J. J., Ragozzine, D., Fabrycky, D. C., et al. 2011, ApJS 197, 8,
  [doi:10.1088/0067-0049/197/1/8](https://doi.org/10.1088/0067-0049/197/1/8)
- Petit, A. C., Laskar, J. & Boué, G. 2017, A&A 607, A35,
  [doi:10.1051/0004-6361/201731196](https://doi.org/10.1051/0004-6361/201731196)
- Pilat-Lohinger, E. & Eggl, S. 2011, ExoStab: A www-Tool to verify the Dynamical Stability of Extra-solar Planets,
  Publications of the Astronomy Department of the Eötvös University 20, [volume](https://real-eod.mtak.hu/19160/)
- Rein, H. & Liu, S.-F. 2012, A&A 537, A128,
  [doi:10.1051/0004-6361/201118085](https://doi.org/10.1051/0004-6361/201118085)
- Rein, H., Hernandez, D. M., Tamayo, D., et al. 2019, MNRAS 485, 5490,
  [doi:10.1093/mnras/stz769](https://doi.org/10.1093/mnras/stz769)
- Rein, H. & Spiegel, D. S. 2015, MNRAS 446, 1424,
  [doi:10.1093/mnras/stu2164](https://doi.org/10.1093/mnras/stu2164)
- Rein, H. & Tamayo, D. 2015, MNRAS 452, 376, [doi:10.1093/mnras/stv1257](https://doi.org/10.1093/mnras/stv1257)
- Stalport, M., Cretignier, M., Naponiello, L. & Van Grootel, V. 2025, A&A 702, L2,
  [doi:10.1051/0004-6361/202556044](https://doi.org/10.1051/0004-6361/202556044)
- Tamayo, D., Cranmer, M., Hadden, S., Rein, H., et al. 2020, PNAS 117, 18194,
  [doi:10.1073/pnas.2001258117](https://doi.org/10.1073/pnas.2001258117)
- Tamayo, D., Rein, H., Shi, P. & Hernandez, D. M. 2020, MNRAS 491, 2885,
  [doi:10.1093/mnras/stz2870](https://doi.org/10.1093/mnras/stz2870)
- Trifonov, T. 2019, The Exo-Striker, Astrophysics Source Code Library, [ascl:1906.004](https://ascl.net/1906.004)
- Wishard, C., Pouplin, J., Elliott, J., et al. 2023, JOSS 8, 5409,
  [doi:10.21105/joss.05409](https://doi.org/10.21105/joss.05409)
