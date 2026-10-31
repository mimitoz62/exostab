---
title: 'exostab: traceable orbital-stability indicators for known exoplanet systems'
tags:
  - Python
  - astronomy
  - exoplanets
  - orbital dynamics
  - dynamical stability
  - N-body simulations
authors:
  - name: Mehmet Öz
    orcid: 0009-0007-1005-7640
    affiliation: 1
affiliations:
  - name: Independent Researcher, Istanbul, Türkiye
    index: 1
date: 28 September 2026
bibliography: paper.bib
---

<!--
DRAFT. Not yet submittable: JOSS requires the repository to have been public, with development spread over
time, for more than six months before submission (so not before about April 2027), and evidence of research use.
Before submitting, the author must check every statement, update the numbers and the research impact
statement, and confirm the AI usage disclosure (it must be true in every detail). Word count (body, without
this comment and the references) is checked by .github/workflows/paper.yml: 750–1750 words.
-->

# Summary

Whether a planetary system is dynamically stable, meaning its planets keep their orbits for the lifetime of the
star instead of colliding or being ejected, is one of the first questions asked about a newly discovered
multi-planet system. It constrains orbital eccentricities, masses and mutual inclinations that observations
leave uncertain. `exostab` is a Python package, command-line tool and web application that gives this answer
for any multi-planet system in the NASA Exoplanet Archive [@christiansen2025; @nea13], or for parameters
supplied by the user. It reports three indicators side by side: the Hill-stability criterion
[@marchal1982; @gladman1993] with a multi-planet spacing heuristic [@chambers1996; @pu2015]; the angular
momentum deficit (AMD) criteria [@laskar2017; @petit2017; @petit2018]; and direct N-body integrations with
REBOUND [@rein2012] using the WHFast [@rein2015whfast] and IAS15 [@rein2015ias15] integrators and the MEGNO chaos
indicator [@cincotta2000; @rein2016]. The machine-learned SPOCK classifier [@tamayo2020] can be added as an
optional fourth indicator. It repeats the analysis for Monte Carlo draws within the published uncertainties and
combines the indicators into a deliberately conservative overall verdict. Every assumption made to complete
missing data is recorded in a versioned JSON report next to the seed, software versions, integrator settings and
the archive rows used.

# Statement of need

Published orbital solutions are rarely complete enough to integrate directly. In the Planetary Systems
Composite Parameters table of the NASA Exoplanet Archive on 28 September 2026, 44% of the planets in
multi-planet systems had masses estimated from their radii [@chen2017], 19% had only minimum masses, 11% had
no eccentricity and 62% no argument of periastron. Orbital phases were often missing or came from a different
publication than the period, which matters because resonant systems can be stable only for particular phases.
Setting up a stability test therefore involves many small decisions, each of which can change the answer
without being reported.

`exostab` makes these decisions explicit and repeatable. It is aimed at students and educators who want a
quick, honest first answer with the caveats visible; at amateur and professional astronomers who want to test
a system or a "what if" variation of it (`exostab sweep`, or the sliders of the web app) before setting up
their own integrations; and at researchers who want indicators for the whole archive in one table, which a
weekly workflow recomputes and publishes as a catalog. Because the indicators answer different questions
(sufficient analytic conditions versus a finite-time numerical test), the tool never reports one without the
others, and it states when they disagree instead of choosing the most comfortable answer.

# State of the field

REBOUND [@rein2012] is the standard open-source N-body package for planetary dynamics and provides the
integrators and variational equations that `exostab` uses; `exostab` builds on it rather than duplicating it.
SPOCK [@tamayo2020] predicts the long-term stability of compact systems of three or more planets with a machine-
learned classifier trained on short integrations. The analytic criteria used here are published as equations
[@gladman1993; @laskar2017; @petit2017; @petit2018]. These tools and papers assume that the user already has a
complete and consistent set of initial conditions and knows which approximations apply. What `exostab` adds is
the layer between the archive and these methods: completion rules with provenance for every value, the
propagation of published uncertainties, a common verdict vocabulary with documented thresholds, validation
against published results, and outputs that can be traced and reproduced.

A contribution to REBOUND or SPOCK was considered instead of a separate package. That scope (archive access,
data completion, reporting and a web interface) lies outside a general-purpose integrator. SPOCK 2.1.1 also
requires REBOUND below version 5, while `exostab` needs REBOUND 5.2, so `exostab` runs SPOCK on request as a
separate process in its own environment and exchanges JSON with it, without importing it.

# Software design

The package separates data, physics and presentation. `exostab.data` queries the archive through the Table
Access Protocol with astroquery [@ginsburg2019], caches the result on disk, and falls back to a bundled snapshot
of 22 systems when offline. Its completion rules turn each archive row into validated `pydantic` models in which
every value carries its provenance ("measured", "derived", "assumed", "estimated", "randomized" or "upper
limit") and every applied rule adds a flag to the report. Orbital phases are taken from transit times, or from
a conjunction or periastron time only when it comes from the same publication as the period, because the
composite table can mix publications. Units are converted once with astropy [@astropy2022] into the years,
astronomical units and solar masses set explicitly in REBOUND.

`exostab.sampling` turns a system into a nominal set of initial conditions and seeded Monte Carlo draws. Each
indicator in `exostab.indicators` maps its result to one of four verdicts (stable, marginal, unstable,
inconclusive), and a verdict stands only if 95% of the draws agree with the nominal one. The multi-planet spacing
threshold grows with eccentricity [@pu2015; @pu2015erratum]. The AMD criteria assume, as their authors do for
catalogue systems, that the unknown mutual inclinations carry as much AMD as the eccentricities, and the
resonance-overlap criterion is used only within the domain its authors state [@petit2017]. N-body runs use a time
step of one thirtieth of the shortest pericentre-passage time [@wisdom2015; @hadden2018], detect close encounters
for every pair of planets, and repeat the nominal run with IAS15. A run is declared inconclusive if its relative
energy error, checked at 1,200 times through every run, exceeds 10⁻⁵, or if a planet passes within half its Hill
radius of the star, where unmodelled tides, relativity and stellar size matter. SPOCK, when enabled, can make the
overall verdict marginal but never unstable. The overall verdict is "stable" only if all indicators agree, draws
were run and no draw has a close encounter, and "unstable" only on direct numerical evidence of close encounters
or escapes that rests neither on values published only as upper limits nor on a single-star model of a system
with several stars. A time-budget mode measures the integration speed of a system and chooses the run length and
number of draws that fit. The command-line interface (Typer and Rich), the Streamlit web app and the catalog
workflow are thin layers over the same `check_system` function, so all three give identical results for the same
inputs and seed. The web app caches results by a hash of all inputs and encodes them in a shareable link.

A validation suite runs nightly in continuous integration. It checks energy conservation for the inner Solar
System, the Hill limit for two planets, that TRAPPIST-1 [@agol2021] is never classified unstable, that GJ 876
integrated with the four-planet solution of @rivera2010 is regular, and that the nominal Kepler-11 configuration
[@lissauer2013] survives the test horizon. It also reproduces the HD 127195 analysis described below. Near the
Hill limit the time to the first close encounter is a chaotic transient that depends on floating-point rounding,
so those tests assert only outcomes that cannot depend on it.

# Research impact statement

`exostab` grew out of an N-body study of the two giant planets of the red giant HD 127195 [@figueira2026],
prepared by the author for Research Notes of the AAS. With the inputs and settings of that study, `exostab`
reproduces its geometry exactly and, in the study's convention, its AMD limits, and its Monte Carlo
classification within the statistical tolerance: 133 of 200 draws are regular and 5 have close encounters,
compared with 134 and 9 in the study. Of the remaining draws, 51 are chaotic and 11 are chaotic but inconclusive,
because their energy error exceeds the limit that `exostab` applies and the study did not; the study found 57
chaotic draws. Building and validating the package also exposed a data problem of practical interest: a time of
periastron that is really the osculating epoch shared by all planets of GJ 876. The archive also stores the
HD 127195 arguments of periastron in radians under a degree label, which the study had noted; the validation
therefore uses the study's own inputs. Both are documented in the repository. A weekly workflow recomputes the
indicators for every host with two or more planets in the archive table (1,070 on 28 September 2026, of which
1,034 can be modelled; the others are listed with the reason) and publishes them as a catalog on a branch of the
repository.

<!-- Author: replace or extend this section with evidence of use by others (issues, citations, teaching,
publications) before submission; aspirational statements are not accepted by JOSS. -->

# AI usage disclosure

Claude Code (Anthropic), running the model Claude Opus 5.5 (`claude-opus-5-5`), was used under the author's
direction during September and October 2026 to write most of the source code, tests, documentation and a first
draft of this paper, to check references against Crossref, arXiv and DataCite, and to extract equations from the
arXiv sources of the cited papers. The author defined the scientific requirements, chose the methods and
thresholds recorded in the repository's decision log, reviewed the code and the outputs, ran the validation
suite, and is responsible for all content.

<!-- Author: confirm each statement above (models, versions, scope, and what you personally reviewed) before
submission; JOSS treats an incomplete or inaccurate disclosure as a serious breach. -->

# Acknowledgements

This research has made use of the NASA Exoplanet Archive, which is operated by the California Institute of
Technology, under contract with the National Aeronautics and Space Administration under the Exoplanet
Exploration Program. No financial support was received for this work.

# References
