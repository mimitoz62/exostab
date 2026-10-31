---
title: "Classroom exercise: Hill, AMD and N-body answers for real systems"
description: >-
  A classroom exercise for a dynamics or exoplanet course: in a Colab notebook, students compare the Hill, AMD and
  N-body answers for real systems and explain what a short integration cannot show. With answer notes for teachers.
---

# Classroom exercise

A notebook for an upper-undergraduate dynamics or exoplanet course. Students compare exostab's Hill, AMD and N-body
answers for TRAPPIST-1, HD 127195 and Kepler-36, and explain what a short integration cannot show. It is planned for
about 90 minutes, in a browser, with a Google account and no local install.

!!! warning "Not yet tried with a class"

    This exercise has not yet been tried with a class, and the notebook has not yet been run in Colab itself. The times
    below are estimates. If you use it, an [issue](https://github.com/mimitoz62/exostab/issues/new/choose) saying what
    worked and what did not would help.

[Open in Google Colab](https://colab.research.google.com/github/mimitoz62/exostab/blob/main/examples/exostab_exercise.ipynb){ .md-button .md-button--primary }
[Notebook on GitHub](https://github.com/mimitoz62/exostab/blob/main/examples/exostab_exercise.ipynb){ .md-button }

## Learning goals

The exercise aims to teach students to:

- say what Hill spacing, the AMD and an N-body run with MEGNO each test, what each takes as input and what time span it
  speaks about;
- compute a Hill spacing from a and m, and relate a sweep in eccentricity to the eccentric form of the Hill criterion;
- read ⟨Y⟩ against time, estimate a Lyapunov time and say what no finite run can show;
- separate what a what-if run shows about an input from what it does not show about the planets.

## Prerequisites

Kepler's third law, the orbital elements a, e and ω, and the idea of chaos. Students read short Python cells but need
not write any. Each student needs a Google account. The notebook also runs in a local Jupyter without one, which is how
the notes below were made. After the install cell, no run needs the archive: every run uses the snapshot of 22 systems
bundled with exostab.

## Time

| Part | What students do | Plan | Cells compute, measured | Stated for Colab |
|---|---|---|---|---|
| Set-up | Save a copy in Drive, install | 5 min | | about 1 min |
| (a) TRAPPIST-1 | Compare the three answers; compute Δ by hand | 20 min | 21 s | 1.5 min |
| (b) HD 127195 | Sweep e, with two seeds; relate it to the Hill criterion | 20 min | 6 s | 30 s |
| (c) TRAPPIST-1 | Longer runs: ⟨Y⟩, the draws, a Lyapunov time | 20 min | 86 s | 6.5 min |
| (d) Kepler-36 | What-if runs in e, from a YAML file | 20 min | 39 s | 3 min |
| To finish | Rewrite one overstated sentence | 5 min | | |

The plan adds up to 90 minutes and is a guess: the notebook has about 2,900 words of text and eleven compound questions,
and students can read on while a cell runs. For a 50-minute class, do the set-up, (a) and (c) in class, and set (b), (d)
and the last sentence as homework; in a new session, students first use Runtime → Run all. The computing times were
measured with `jupyter nbconvert --execute` on 1 November 2026, on one core of an Apple M4 Pro, because exostab uses all
cores but one and Colab's free tier is expected to offer two. The notebook states about 4 times these values, rounded
up, about 11 minutes in all. That factor is a cautious guess, not a measurement: a Linux runner of GitHub Actions took
about twice as long as this laptop for the default check of TRAPPIST-1, whose IAS15 run is its slowest.

## What students hand in

The notebook as an `.ipynb` file (File → Download), with its outputs and the answers in its text cells: eleven questions
in four tasks and one sentence to rewrite. Mark the reasoning and the use of the student's own numbers, not agreement
with the numbers below, because chaotic numbers can differ. This page is public, so students can find these notes.

## Answer notes

These are the results of the notebook, run from a clean Python 3.13 environment with `jupyter nbconvert --execute`, as
the workflow `Browser paths` does, on 1 November 2026: exostab 1.0.1 (the tag v1.0.1), REBOUND 5.2.2 and NumPy 2.5.4 on
macOS (Apple M4 Pro), one worker process, the snapshot of 28 September 2026 and seed 0 unless stated.

**What can differ between computers.** Hill spacing, the margin, β and the Hill and AMD verdicts do not depend on the
integration. ⟨Y⟩, the number of chaotic draws and the end of a chaotic run can differ; they are marked †, and an N-body
or overall verdict could differ with them, although none did in the two runs here. Colab runs on Linux, and this
notebook has not been run there yet. In a † cell, a value after a semicolon is a stand-in for Linux: a second run on the
same computer, with REBOUND 5.2.2 rebuilt to use the `rand_r` of glibc, the C library of Linux. REBOUND draws the random
starting direction of MEGNO's tangent vector with that function. For two commands of the quickstart notebook that the
Linux runner of `Browser paths` ran on 31 October 2026 (exostab 1.0.0, with the same integration code), this build gives
the runner's numbers: ⟨Y⟩ = 2.19 for the default check of TRAPPIST-1 and 6.59 at e = 0.2 in its sweep, where the
unchanged macOS build gives 2.17 and 6.98. Rounding matters in longer runs: changing the starting values of TRAPPIST-1
by a few units in the last place leaves ⟨Y⟩ at 2.17 over 10,000 orbits, and moves it between 6.46 and 6.48 over 50,000
and between 15.4 and 23.5 over 100,000.

### Task (a)

`exostab check "TRAPPIST-1" --offline`: 10,000 orbits, 20 draws, 41.4 years.

```text
Hill spacing    MARGINAL   draws: 0 stable, 20 marginal, 0 unstable
AMD             STABLE   draws: 20 stable, 0 marginal, 0 unstable
N-body + MEGNO  MARGINAL   draws: 18 stable, 2 marginal, 0 unstable
  Nominal run regular (<Y> = 2.17) over 41.4 yr (10,000 inner orbits); draws: 18 regular, 2 chaotic, 0
  close encounter/escape of 20.
Overall: MARGINAL  Direct integration: the nominal run is regular; of 20 draws, 18 are regular, 2 chaotic
and 0 had close encounters or escapes. Part of the parameter range allowed by the published uncertainties
is chaotic. The other indicators cannot guarantee stability (Hill spacing: marginal).
```

With the `rand_r` of glibc, ⟨Y⟩ = 2.19†, with the same counts. Both values are close to the threshold of 2.2.

| Pair | P₂/P₁ | Δ | Two-planet limit | Needed for stable |
|---|---|---|---|---|
| b / c | 1.603 | 10.05 | 3.46 | 12.0 |
| c / d | 1.672 | 12.74 | 3.48 | 12.0 |
| d / e | 1.507 | 11.85 | 3.46 | 12.0 |
| e / f | 1.509 | 10.17 | 3.46 | 12.0 |
| f / g | 1.342 | 6.57 | 3.46 | 12.0 |
| g / h | 1.520 | 10.51 | 3.48 | 12.0 |

- **(a1)** The nominal run is regular, but 18 of 20 draws† are 90%, below the 95% that an N-body stable needs, so the
  verdict is marginal. The system fails Δ ≥ 12: only c / d passes, and f / g falls furthest short. By hand, R_H = (7.089
  × 10⁻⁶ / 0.2694)^(1/3) × 0.04267 AU = 0.001269 AU and Δ = 0.00833 / 0.001269 ≈ 6.56.
- **(a2)** The period ratios are close to 8:5, 5:3, 3:2, 3:2, 4:3 and 3:2. Δ takes only a and m. The N-body run also
  takes the orbital phases (here from transit times), and near a resonance the phases can keep two planets apart. The
  rule of Δ ≈ 12 concerns survival over about a billion years, in simulations extrapolated from shorter runs (Pu & Wu
  2015), and this run covers 41 years. So marginal says that spacing alone does not guarantee stability, and regular
  says that no chaos was detected within 41 years. That label is not settled: ⟨Y⟩ is close to the threshold and has not
  converged, and another seed, which changes only MEGNO's random starting direction, can make the nominal run chaotic
  (task (c)). Neither verdict contradicts the other, and neither is a proof. AMD adds that the eccentricities are too
  small for neighbouring orbits to cross in the secular approximation (largest β = 0.0285), if the unknown inclinations
  carry no more AMD than the eccentricities.

### Task (b)

What-if runs. `exostab sweep "HD 127195" --planet b --param e --range 0 0.4 --steps 21 --offline`, 10,000 orbits per
value. Δ is 4.371 in every row. From e_b = 0.30 to 0.40 all three N-body columns show a close encounter†, and Hill and
AMD stay unstable.

| e_b | Margin | Hill | β | AMD | N-body and ⟨Y⟩† | N-body, seed 2† |
|---|---|---|---|---|---|---|
| 0.00 | +0.00508 | stable | 0.260 | stable | regular, 2; 2 | regular |
| 0.02 | +0.00489 | stable | 0.297 | stable | regular, 2; 2 | regular |
| 0.04 | +0.00432 | stable | 0.408 | stable | chaotic, 9.82; 8.68 | regular |
| 0.06 | +0.00337 | stable | 0.593 | stable | regular, 2; 2 | regular |
| 0.08 | +0.00205 | stable | 0.852 | stable | regular, 2; 2 | regular |
| 0.10 | +0.00034 | stable | 1.186 | marginal | regular, 2; 2 | regular |
| 0.12 | -0.00175 | unstable | 1.594 | marginal | regular, 2; 2 | regular |
| 0.14 | -0.00422 | unstable | 2.078 | unstable | regular, 1.32; 1.89 | chaotic |
| 0.16 | -0.00707 | unstable | 2.638 | unstable | chaotic, 33.6; 26.8 | chaotic |
| 0.18 | -0.01031 | unstable | 3.275 | unstable | regular, 1.84; 1.97 | chaotic |
| 0.20 | -0.01394 | unstable | 3.990 | unstable | chaotic, 62; 78 | encounter |
| 0.22 | -0.01796 | unstable | 4.783 | unstable | encounter | encounter |
| 0.24 | -0.02238 | unstable | 5.656 | unstable | encounter | encounter |
| 0.26 | -0.02719 | unstable | 6.609 | unstable | encounter; chaotic, 385 | encounter |
| 0.28 | -0.03240 | unstable | 7.644 | unstable | encounter | encounter |

The next cell prints, on both builds:

```text
Δ from the formula: 4.371; sweep: 4.371
Margin at e_b = 0.1 from the formula: +0.00034; sweep: +0.00034
The margin reaches 0 at e_b = 0.104
Estimate from the equal-mass expansion: e_b = 0.099 (e_H = 0.0679)
The radial ranges of the two orbits touch, a_b (1 + e_b) = a_c (1 - e_c), at e_b = 0.281
```

- **(b1)** AMD goes from stable to marginal between 0.08 and 0.10, where β passes 1, and from marginal to unstable
  between 0.12 and 0.14. Hill goes from stable to unstable between 0.10 and 0.12. The first chaotic run† is at 0.04, the
  first close encounter† at 0.22, and between them the N-body column goes back and forth.
- **(b2)** Δ contains only a and m, and the sweep changes only e. The eccentricity enters through γ₁ ≈ 1 − e₁²/2, so the
  left side of the criterion falls by about μ₁/(μ₁ + μ₂γ₂δ) e₁² ≈ 0.47 e_b², and the margin is close to 0.00508 − 0.47
  e_b²: the parabola in the middle panel. The expansion comes from δ ≈ 1 + ε, which gives left side ≈ 1 + 3μ₁μ₂ε²/α² −
  (μ₁e₁² + μ₂e₂²)/α, and from Δ ≈ 2ε/e_H. It gives the spacing of the full criterion to 1.6% here and about 0.3% for
  Kepler-36. It is less accurate for very unequal masses: off by up to 3.6% in the cases tried with planet masses up to
  3 × 10⁻⁵ of the star's and e up to 0.05. The margin reaches 0 at 0.104, well before the first close encounter at 0.22†
  and the touching radial ranges at 0.281. The regular runs from 0.12 to 0.14 do not contradict the Hill column: the
  criterion is a sufficient condition. Above the limit a close encounter is excluded; below it a close encounter is not
  excluded, and nothing more. Unstable in the Hill column means that the test fails.
- **(b3)** The seed changes the random phases and the starting direction of MEGNO's tangent vector, not a, m or e. Hill
  and AMD do not use them, so they do not change. At e_b = 0.04, seed 0 is chaotic† and seed 2 regular†. A row of the
  N-body column therefore describes one choice of unknown phases, for a parameter set in which m sin i serves as the
  mass and the archive's values of ω are radian values listed as degrees (DECISIONS.md, D18). It is not an answer for
  the real planets.

### Task (c)

Not what-if runs: only the length changes. `exostab check "TRAPPIST-1" --offline --orbits N`, with `--draws 10` or
`--draws 0` as in the table and `--no-ias15 --no-plots`. In every row Hill spacing is marginal, AMD stable, N-body
marginal and the overall verdict marginal, on both builds. r/c/e counts the draws as regular, chaotic, or ended by a
close encounter or escape. The table's λ is twice the `lyapunov_per_yr` of `report.json`, which holds REBOUND's
`lyapunov()`: that is the slope of ⟨Y⟩ against time, and with a difference growing as exp(λt), ⟨Y⟩ grows as λt/2 ([Valk
et al. 2009](https://arxiv.org/abs/0810.1859), a⋆ = λ/2).

| Orbits | Years | Nominal run | ⟨Y⟩† | 1/λ (yr)† | r/c/e† |
|---|---|---|---|---|---|
| 10,000 | 41 | regular | 2.17; 2.19 | 91; 42 | 9/1/0; 9/1/0 |
| 30,000 | 124 | chaotic | 2.42; 2.54 | 238; 113 | no draws |
| 50,000 | 207 | chaotic | 6.46; 6.72 | 31; 27 | 2/8/0; 1/9/0 |
| 100,000 | 414 | chaotic | 19.03; 18.92 | 10; 10 | no draws |
| 200,000 | 827 | chaotic | 38.07; 33.78 | 10; 11 | no draws |

The run with the IAS15 check, `--orbits 50000 --draws 0`, ends with ⟨Y⟩ = 6.46† for WHFast and 5.26† for IAS15 (6.72†
and 5.52† with the `rand_r` of glibc). The last line of the table's cell, 10,000 orbits with seed 3, is chaotic with ⟨Y⟩
= 2.46† on both builds.

- **(c1)** ⟨Y⟩ stays near 2, with a bump close to 2.2 at about 40 years, and passes 2.2 for good at about 100 to 110
  years, more than twice the default run. WHFast and IAS15 agree until about 150 years. Both are accurate, but not
  identical: in a separate run, not in the notebook, their positions differ by about 10⁻⁶ AU after one year and about 3
  × 10⁻³ AU after 150 years. In a chaotic run a small difference grows by a factor e per Lyapunov time, so the two ⟨Y⟩
  curves part once the motion is strongly chaotic. Rounding differences between computers grow in the same way, in
  longer runs. At 10,000 orbits the larger cause is the random starting direction used by MEGNO (see above).
- **(c2)** Only the N-body results change: the nominal run goes from regular to chaotic, and the chaotic draws from 1 of
  10 to 8 or 9 of 10†. Hill and AMD use only the starting values, so run length cannot change them. The overall verdict
  stays marginal, but what lies behind it changes. In the two longest rows 1/λ is 10 to 11 years†. The growth of ⟨Y⟩
  between them gives λ ≈ 2 × (38.07 − 19.03) / (827 − 414) per year, so 1/λ ≈ 11 years†, or 14 with the `rand_r` of
  glibc. The default run therefore covers about three or four Lyapunov times, too few for a value of λ: 1/λ is 91 or 42
  years† over 10,000 orbits. As a check, in a separate run, not in the notebook, the tangent vector that MEGNO
  integrates grows with an e-folding time of 11 or 14 years† from 200 to 827 years. The rate is not steady: about 40
  years† from 40 to 100 years, and 7 to 9† from 165 to 248. Chaotic says that nearby trajectories separate
  exponentially, so the details of an orbit cannot be followed for long. It does not say that a close encounter happens,
  or when: the runs in the table have none, within 827 years.
- **(c3)** 200,000 orbits took 8.8 s here, so 2.4 × 10¹¹ orbits would take about 122 days of one core, longer in Colab,
  for one run without draws. No finite run can show that the motion stays regular, or that no close encounter happens,
  after its end: a run of length T says only "no instability found within T". The row of 10,000 orbits is the example:
  with seed 0 it is regular, and the same values are chaotic by 30,000. The line with seed 3 shows that the label at
  10,000 orbits is not settled either: only MEGNO's random starting direction changes. In separate runs with seeds 0 to
  15, not in the notebook, the nominal run is chaotic for 10 of the 16 seeds at 10,000 orbits, 1 at 20,000, 15 at 30,000
  and all 16 at 50,000 (with the `rand_r` of glibc: 11, 0, 15 and 16)†. All of this describes this parameter set in
  exostab's model (coplanar orbits, values from several publications, no tides or relativity), not the real planets.

### Task (d)

`--draws 10`, 10,000 orbits (380 years). The first two rows use the published values; the others are what-if runs. For
the limits, e_b and e_c are upper limits of 0.039 and 0.033, so the draws lie below them. r/c/e as in task (c).

| Run | Hill | AMD | N-body | Overall | Margin | β |
|---|---|---|---|---|---|---|
| Archive row, e assumed 0 | stable | stable | stable | stable | +0.00088 | 0.000 |
| The file, no e given | stable | stable | stable | stable | +0.00088 | 0.000 |
| What-if: e = 0.005 | stable | stable | stable | stable | +0.00085 | 0.089 |
| What-if: e = 0.01 | stable | stable | marginal | marginal | +0.00078 | 0.357 |
| What-if: e = 0.02 | stable | marginal | marginal | marginal | +0.00048 | 1.429 |
| What-if: e = 0.03 | marginal | marginal | marginal | marginal | -0.00002 | 3.216 |
| What-if: e = 0.04 | unstable | unstable | marginal | marginal | -0.00072 | 5.717 |
| What-if: limits, seed 0 | marginal | marginal | marginal | marginal | -0.00036 | 4.412 |
| What-if: limits, seed 1 | marginal | marginal | marginal | marginal | -0.00036 | 4.412 |
| What-if: limits, seed 2 | marginal | marginal | marginal | marginal | -0.00036 | 4.412 |

| Run | Nominal run† | r/c/e† |
|---|---|---|
| Archive row, e assumed 0 | regular, ⟨Y⟩ = 2; 2 | 10/0/0; 10/0/0 |
| What-if: e = 0.005 | regular, ⟨Y⟩ = 2; 2 | 10/0/0; 10/0/0 |
| What-if: e = 0.01 | regular, ⟨Y⟩ = 2; 2 | 9/1/0; 9/1/0 |
| What-if: e = 0.02 | chaotic, ⟨Y⟩ = 321; 142 | 7/3/0; 7/3/0 |
| What-if: e = 0.03 | chaotic, ⟨Y⟩ = 458; 378 | 5/5/0; 4/6/0 |
| What-if: e = 0.04 | encounter at 0.0444 yr | 4/3/3; 4/2/4 |
| What-if: limits, seed 0 | encounter at 0.0468 yr | 8/2/0; 8/2/0 |
| What-if: limits, seed 1 | encounter at 30.4 yr; 146 yr | 9/1/0; 9/1/0 |
| What-if: limits, seed 2 | chaotic, ⟨Y⟩ = 391; 399 | 6/4/0; 6/4/0 |

The expansion from task (b) gives margin 0 at e = 0.029. The limits row of seed 0 repeats the what-if run in [What the
catalog shows](findings.md#what-stable-means-here-and-what-it-does-not).

- **(d1)** Both eccentricities are marked ᵃ (assumed), and ω is random. β is the AMD divided by the critical AMD of the
  pair, here the smallest AMD that lets mean-motion resonances overlap. With e = 0 the AMD is 0, so β = 0 by
  construction; the report card says that the test says nothing about the real eccentricities. The file gives the
  archive run's numbers exactly, draw by draw, so a later change comes from the changed input and not from a copying
  error.
- **(d2)** N-body differs first, at e = 0.01 (one chaotic draw†), then AMD at 0.02 (β above 1), then Hill at 0.03, where
  the margin is just below 0, as the expansion predicts. The overall verdict leaves stable at 0.01. It stays marginal at
  0.04, where the nominal run and 3 or 4 draws† end in a close encounter, because an overall unstable needs at least 95%
  of the draws. With the limits, the verdicts, the margin and β stay the same across the seeds, and the end of the
  nominal run† and the draws† do not. That points to the input that the archive's row does not give and exostab draws at
  random: ω, along with e in the draws.
- **(d3)** There is no contradiction: the run with e = 0 tests one chosen input over 380 years, and Deck et al. (2012)
  sample initial conditions consistent with the observations over up to about 200 million years. 380 years is about 38
  of their Lyapunov times, so the length of the run alone does not explain the regular result: with the same length, the
  what-if runs at e = 0.02 and above are chaotic or end in a close encounter. *What they show about the input:* the
  stable verdict rests on the assumed e. With seed 0 it holds at e = 0.005 and is lost at 0.01. With seed 2, in a
  separate run on both builds, not in the notebook, it holds at 0.01 and is lost at 0.02 (`exostab check --from-file
  exostab-results/kepler36-whatif-e0.01.yaml --draws 10 --seed 2`, and the same with `e0.02`). Both values are well
  below the published limits. *What they do not show about the planets:* they do not measure e, and equal values on both
  planets are a choice. They do not show that the real orbits are chaotic. A run that ends in a close encounter after
  0.05 years cannot describe planets that Kepler observed for years; at most it rules out that combination of values, in
  a model with coplanar orbits and a random ω.

### To finish

For example: "With the archive snapshot of 28 September 2026, 10,000 orbits and seed 0, exostab calls Kepler-36 stable
(10 draws). That verdict rests on e = 0 assumed for both planets and on coplanar orbits, and a what-if run with e = 0.02
on both does not keep it. It calls TRAPPIST-1 marginal (20 draws): Hill spacing is marginal, AMD stable, and with this
seed the nominal run is regular over 41 years, close to the threshold of 2.2, and chaotic over longer runs. Marginal
does not mean unstable, and neither verdict is a proof."

## What has been checked

- The notebook ran from a clean environment without errors on macOS, once with each build of REBOUND, and each question
  was checked against what the cells show.
- It has not been run in Colab, which needs a sign-in, or on Linux. Once the workflow `Browser paths` has run it, its
  artifact `executed-notebooks` holds a run on Linux to compare with these notes.
- It has not been tried with students, so the plan of about 90 minutes is untested.

The references are in [Methods](methods.md#references) and [What the catalog shows](findings.md#references), except
Valk, S., Delsate, N., Lemaître, A. & Carletti, T. 2009, Advances in Space Research 43, 1509,
doi:10.1016/j.asr.2009.02.014.

> This research has made use of the NASA Exoplanet Archive, which is operated by the California Institute of
> Technology, under contract with the National Aeronautics and Space Administration under the Exoplanet
> Exploration Program.
