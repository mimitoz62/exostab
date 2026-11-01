---
hide:
  - navigation
title: "How to read an exostab report card: Hill spacing, AMD and N-body verdicts"
description: >-
  A line-by-line guide to the report card of exostab check, using a real run on TRAPPIST-1: the planet table and its
  marks, mutual Hill radii, the AMD coefficient β, MEGNO and the draws, the overall verdict, the completion rules, the
  output files, and what to do next in the common cases.
---

# How to read a report card

`exostab check` prints a report card: a dense summary of one stability check. This page goes through a real card from
top to bottom. It assumes that you have met Kepler's laws and not much else, and it explains the other terms as they
appear. The formulas and references are in [Methods](methods.md). The [catalog](catalog.md)'s system pages and the
[web app](web.md) show the same indicators, so this page also helps with those.

## The short version

1. Read the line that starts with `Overall:`. It gives the verdict and the reason for it.
2. Read the three indicator headings. Each gives a verdict and how the *draws* came out: the repeats of the test with
   values varied according to the published error bars. So you can see which indicator holds the overall verdict back.
3. Look for marks in the planet table, and read the list under `Data completion`. They say which inputs are assumed,
   estimated, random or only limits.
4. Read the line that starts with `N-body:`. It says how much time the integration covered.

The overall verdict is one of four:

- **stable**: exostab calls this published parameter set stable under these settings. Every indicator says stable, and
  no draw had a close encounter or escape. It is not a proof.
- **marginal**: exostab cannot call this published parameter set stable under these settings. Marginal does not mean
  unstable.
- **unstable**: the run with the published values and at least 95% of the draws had a close encounter or escape. This
  is about the published parameter set under these settings, not a prediction for the planets.
- **inconclusive**: the N-body runs could not be trusted, so exostab makes no statement on this parameter set. This is
  not a verdict of stable or unstable.

## A real card

This card was printed on 31 October 2026 by exostab 1.0.2.dev0, the development version after release 1.0.1, with
REBOUND 5.2.0, NumPy 2.5.3 and Python 3.12.11 on macOS (Apple M4 Pro). `--offline` uses the snapshot of 22 systems
bundled with exostab, so you can repeat the run without a network. `COLUMNS=100` gives the card the width it has in the
README. The [Quickstart](quickstart.md) shows how to install exostab or try it in a browser.

```bash
COLUMNS=100 exostab check "TRAPPIST-1" --offline
```

```text
╭─────────────────────────── exostab 1.0.2.dev0 — stability report card ───────────────────────────╮
│ TRAPPIST-1   M* = 0.0898 ± 0.0023 M☉   7 planets   data: snapshot (2026-09-28)                   │
│                                                                                                  │
│ Planet        P (d)               Mass (M⊕)      e                  ω (deg)       Phase          │
│ TRAPPIST-1 b  1.51083 ± 6e-06     1.37 ± 0.069   0.00622 ± 0.00304  337 ± 34.2    transit        │
│ TRAPPIST-1 c  2.42194 ± 1.8e-05   1.31 ± 0.056   0.00654 ± 0.00188  282 ± 17.1    transit        │
│ TRAPPIST-1 d  4.04922 ± 2.6e-05   0.388 ± 0.012  0.00837 ± 0.00093  -8.73 ± 6.17  transit        │
│ TRAPPIST-1 e  6.10101 ± 3.5e-05   0.692 ± 0.022  0.0051 ± 0.00058   108 ± 8.47    transit        │
│ TRAPPIST-1 f  9.20754 ± 3.2e-05   1.04 ± 0.031   0.0101 ± 0.00068   369 ± 3.11    transit        │
│ TRAPPIST-1 g  12.3524 ± 5.4e-05   1.32 ± 0.038   0.00208 ± 0.00058  191 ± 13.8    transit        │
│ TRAPPIST-1 h  18.7729 ± 0.000214  0.326 ± 0.02   0.00567 ± 0.00121  339 ± 9.66    transit        │
│ ᵃ assumed  ᵈ derived  ᵉ estimated  ʳ randomized per run  < upper limit                           │
│                                                                                                  │
│ Hill spacing    MARGINAL   draws: 0 stable, 20 marginal, 0 unstable                              │
│   Every pair passes the two-planet limit, but TRAPPIST-1 f / TRAPPIST-1 g is only 6.6 mutual     │
│   Hill radii apart, where the heuristic threshold for its eccentricities is 12.0 (Pu & Wu 2015); │
│   long-term stability is not guaranteed by spacing alone.                                        │
│   • For three or more planets the spacing test is a heuristic (Chambers et al. 1996; Pu & Wu     │
│   2015), not a proof.                                                                            │
│ AMD             STABLE   draws: 20 stable, 0 marginal, 0 unstable                                │
│   AMD-stable: largest β = 0.0285 (TRAPPIST-1 d / TRAPPIST-1 e), so collisions are excluded in    │
│   the secular approximation, provided the mutual inclinations carry no more AMD than the         │
│   eccentricities.                                                                                │
│   • β, β_S and β_H assume that the unknown mutual inclinations carry as much AMD as the          │
│   eccentricities (twice the coplanar AMD; Laskar & Petit 2017, Petit et al. 2017). For exactly   │
│   coplanar orbits they are half as large (largest β_p = 0.0142, β_S,p = 0.00015); 'unstable'     │
│   requires the coplanar values, lower bounds for any inclinations, to be ≥ 1.                    │
│ N-body + MEGNO  MARGINAL   draws: 18 stable, 2 marginal, 0 unstable                              │
│   Nominal run regular (<Y> = 2.17) over 41.4 yr (10,000 inner orbits); draws: 18 regular, 2      │
│   chaotic, 0 close encounter/escape of 20.                                                       │
│   • The nominal run is 'regular', but the draws disagree.                                        │
│                                                                                                  │
│ Overall: MARGINAL  Direct integration: the nominal run is regular; of 20 draws, 18 are regular,  │
│ 2 chaotic and 0 had close encounters or escapes. Part of the parameter range allowed by the      │
│ published uncertainties is chaotic. The other indicators cannot guarantee stability (Hill        │
│ spacing: marginal).                                                                              │
│ N-body: 10,000 orbits of the innermost planet = 41.4 yr, WHFast dt = 0.0497 d, checked with      │
│ IAS15; 20 Monte Carlo draws; seed 0; MEGNO chaotic at <Y> ≥ 2.2; energy-error limit 1e-05.       │
│                                                                                                  │
│ Data completion (applied automatically):                                                         │
│ b, c, d, e, f, g, h  Orbital phase set from the transit mid-time, propagated with the period     │
│                      (transit time and period come from different publications).                 │
│ system               All orbits are placed in one plane. Mutual inclinations are not published   │
│                      (sky-plane inclinations do not determine them), and longitudes of the       │
│                      ascending node are not used.                                                │
│ Note: offline snapshot of 22 systems                                                             │
│                                                                                                  │
│ Saved: exostab-results/trappist-1/report.json, exostab-results/trappist-1/orbits.png,            │
│ exostab-results/trappist-1/megno.png                                                             │
╰──────────────────────────────────────────────────────────────────────────────────────────────────╯
Finished in 7.8 s.
```

Release 1.0.1 prints the same card, apart from the version in the title and the run time. On another computer the
counts of chaotic draws can differ by one or two, because chaotic integrations are sensitive to floating-point rounding
([Validation](validation.md)). In a terminal the verdicts are coloured: green for stable, yellow for marginal, red for
unstable and magenta for inconclusive. The rest of this page takes the card apart.

## The header and the data source

```text
╭─────────────────────────── exostab 1.0.2.dev0 — stability report card ───────────────────────────╮
│ TRAPPIST-1   M* = 0.0898 ± 0.0023 M☉   7 planets   data: snapshot (2026-09-28)                   │
```

The title names the version of exostab. The next line gives the name of the system, the mass of its star in solar
masses (`M☉`) with the published uncertainty, and the number of planets. This star has about 9% of the mass of the Sun.
exostab models only the host star, also in a system that has more than one.

`data:` says where the numbers come from:

- `snapshot`: the copy of 22 systems bundled with exostab, used with `--offline`. The date is the day that copy was
  downloaded from the archive.
- `archive`: the table of the NASA Exoplanet Archive, downloaded for this run.
- `archive-cache`: your saved copy of that table, downloaded on the date shown. `--refresh` downloads it again.
- `file`: your own YAML file, given with `--from-file`. There is no date then.

The table behind the first three is the archive's
[Planetary Systems Composite Parameters](data-assumptions.md#source). It has one row per planet and picks each value
separately, so one row can combine numbers from several papers. The line `Note:`, near the bottom of the card, says
when the snapshot is in use. If the archive cannot be reached and you have no saved copy, exostab falls back on the
snapshot and says so there.

Without `--offline`, on the archive's table of 31 October 2026, TRAPPIST-1 gets the same verdicts and draw counts as on
this card.

## The planet table and its marks

```text
│ Planet        P (d)               Mass (M⊕)      e                  ω (deg)       Phase          │
│ TRAPPIST-1 b  1.51083 ± 6e-06     1.37 ± 0.069   0.00622 ± 0.00304  337 ± 34.2    transit        │
│ TRAPPIST-1 c  2.42194 ± 1.8e-05   1.31 ± 0.056   0.00654 ± 0.00188  282 ± 17.1    transit        │
│ TRAPPIST-1 d  4.04922 ± 2.6e-05   0.388 ± 0.012  0.00837 ± 0.00093  -8.73 ± 6.17  transit        │
│ TRAPPIST-1 e  6.10101 ± 3.5e-05   0.692 ± 0.022  0.0051 ± 0.00058   108 ± 8.47    transit        │
│ TRAPPIST-1 f  9.20754 ± 3.2e-05   1.04 ± 0.031   0.0101 ± 0.00068   369 ± 3.11    transit        │
│ TRAPPIST-1 g  12.3524 ± 5.4e-05   1.32 ± 0.038   0.00208 ± 0.00058  191 ± 13.8    transit        │
│ TRAPPIST-1 h  18.7729 ± 0.000214  0.326 ± 0.02   0.00567 ± 0.00121  339 ± 9.66    transit        │
│ ᵃ assumed  ᵈ derived  ᵉ estimated  ʳ randomized per run  < upper limit                           │
```

The planets are listed from the inside out, by orbital period.

| Column | What it is |
|---|---|
| `P (d)` | The orbital period in days. Kepler's third law turns it into the size of the orbit, the semi-major axis a. |
| `Mass (M⊕)` | The mass of the planet, in Earth masses. |
| `e` | The eccentricity of the orbit: 0 is a circle, and larger values are more elongated. |
| `ω (deg)` | The argument of periastron: the direction of the point of the orbit closest to the star, as an angle. Values are as published, so 369 is the same direction as 9. |
| `Phase` | What fixes where the planet starts on its orbit. `transit`: a time of mid-transit or of inferior conjunction, when the planet passes between us and the star. `periastron`: a time of closest approach to the star. `mean anomaly` and `mean longitude`: an angle from a YAML file. `random`: nothing usable is published, so the start is drawn at random. |

`±` is the published uncertainty, and `+a/−b` means that the upper and lower uncertainties differ. The card rounds the
numbers; `report.json` has them in full, with the publication behind each one.

A number without a mark is a value as its source gives it. In the archive's table that is a published value, or one the
archive computed from published numbers, and then the list under `Data completion` says so. All the values of TRAPPIST-1
are published, so its table has no marks. Many systems have gaps. Kepler-292, from the archive's table of 31 October
2026 (`exostab check "Kepler-292"`), shows three kinds of filled-in value:

```text
│ Kepler-292   M* = 0.865 +0.021/−0.029 M☉   5 planets   data: archive-cache (2026-10-31)          │
│                                                                                                  │
│ Planet        P (d)               Mass (M⊕)  e   ω (deg)  Phase                                  │
│ Kepler-292 b  2.58083 ± 2e-05     2.3ᵉ       0ᵃ  random   transit                                │
│ Kepler-292 c  3.71534 ± 3.3e-05   2.76ᵉ      0ᵃ  random   transit                                │
│ Kepler-292 d  7.05568 ± 4.3e-05   5.6ᵉ       0ᵃ  random   transit                                │
│ Kepler-292 e  11.979 ± 0.000101   7.61ᵉ      0ᵃ  random   transit                                │
│ Kepler-292 f  20.8342 ± 0.000184  6.12ᵉ      0ᵃ  random   transit                                │
```

The marks mean:

| On the card | Legend | What it means | Real example |
|---|---|---|---|
| `ᵃ` | assumed | An eccentricity that is missing, or published as exactly 0 without an uncertainty. exostab uses 0 in every run. | `0ᵃ` (Kepler-292 b) |
| `ᵈ` | derived | Computed from other published numbers, such as a period from the semi-major axis by Kepler's third law. On the archive's table of 31 October 2026, no system that exostab can model has this mark. A YAML file that gives `semimajor_axis_au` and no period gets it. | `365.256ᵈ` (a YAML file) |
| `ᵉ` | estimated | A mass that was not measured. It comes from the radius of the planet, through a mass-radius relation. | `2.3ᵉ` (Kepler-292 b) |
| `random` | randomized per run | A value that is not published, so it is drawn uniformly at random for every run, the run with the published values included. There is no number to show, so the table prints the word `random`. The legend's `ʳ` stands for the same thing, and in this version no number carries it. | `random` (Kepler-292 b) |
| `<` | upper limit | Only an upper limit is published, for a mass or an eccentricity. The run with the published values uses the limit, and the draws are uniform between 0 and the limit. | `<0.6` (HR 8799 d), `<2.74e+03` (HD 10180 c) |

One more label has no letter. `(m sin i)` after a mass, as in `219 ± 1.4 (m sin i)` (ups And b), means that only the
minimum mass is known. Radial velocities measure m sin i, where i is the tilt of the orbit against the sky. exostab uses
it as the mass, so sin i = 1, unless you pass `--inclination-prior isotropic`. Lower limits, and limits on a period,
have no mark of their own: the limit is used as the value, and the list under `Data completion` says so.

## Hill spacing

```text
│ Hill spacing    MARGINAL   draws: 0 stable, 20 marginal, 0 unstable                              │
│   Every pair passes the two-planet limit, but TRAPPIST-1 f / TRAPPIST-1 g is only 6.6 mutual     │
│   Hill radii apart, where the heuristic threshold for its eccentricities is 12.0 (Pu & Wu 2015); │
│   long-term stability is not guaranteed by spacing alone.                                        │
│   • For three or more planets the spacing test is a heuristic (Chambers et al. 1996; Pu & Wu     │
│   2015), not a proof.                                                                            │
```

All three indicator blocks have the same form. The heading gives the name, the verdict and how the draws came out. A
draw is a copy of the system with its values varied according to the published error bars ([below](#the-draws)). Then
comes a summary of the result for the published values, which the card calls *nominal*, and then notes, marked with
bullets.

Hill spacing asks whether neighbouring orbits are far enough apart.

**The mutual Hill radius.** Around every planet there is a region, its *Hill sphere*, where the planet's gravity beats
the star's tides. Its radius is about a (m / 3M★)^(1/3), for a planet of mass m at distance a from a star of mass M★.
For two neighbouring planets, exostab uses the *mutual Hill radius*

R_H = ((m₁ + m₂) / 3M★)^(1/3) (a₁ + a₂)/2

and measures the distance between their orbits in that unit: Δ = (a₂ − a₁) / R_H. It is a natural ruler, because heavier
planets disturb each other from further away.

You can check the 6.6 on the card with a calculator. With a in AU, P in years and M★ in solar masses, Kepler's third
law reads a³ = M★ P². For planets f and g:

- P = 9.20754 d and 12.3524 d, which are 0.02521 yr and 0.03382 yr. With M★ = 0.0898 this gives a = 0.03850 AU and
  0.04683 AU, with a mean of 0.04267 AU.
- The masses add up to 1.04 + 1.32 = 2.36 Earth masses, which is 7.09 × 10⁻⁶ solar masses (one Earth mass is
  3.003 × 10⁻⁶ solar masses). So ((m₁ + m₂) / 3M★)^(1/3) = (7.09 × 10⁻⁶ / 0.2694)^(1/3) = 0.0297.
- R_H = 0.0297 × 0.04267 AU = 0.00127 AU, and Δ = (0.04683 − 0.03850) / 0.00127 = 6.6.

**The rule.**

- *Two planets.* Using a result of Marchal & Bozis (1982) for the three-body problem, Gladman (1993) showed that two
  planets on circular orbits can never come close to each other if Δ is larger than about 2√3 ≈ 3.46. This does not
  exclude the escape of the outer planet. For elongated orbits the limit grows. exostab says stable outside this limit,
  and unstable inside it or if the orbits cross.
- *Three or more planets.* There is no such proof. Numerical experiments show that the time until the first close
  encounter grows roughly exponentially with Δ (Chambers et al. 1996). So exostab uses a *heuristic*, a rule of thumb
  from simulations of this kind (Pu & Wu 2015). It says stable only if every neighbouring pair has Δ ≥ 12, every
  neighbouring pair has Δ ≥ 10.2 + 2.4 e/e_H, and no eccentricity is above 0.05. Here e is the larger eccentricity of
  the pair, and e_H is the factor ((m₁ + m₂) / 3M★)^(1/3) from above. It says unstable if any pair fails the two-planet
  limit or has crossing orbits, and marginal otherwise.

**This card.** Every pair of TRAPPIST-1 clears the two-planet limit of about 3.46. For f and g the second requirement
gives 10.2 + 2.4 × 0.0101 / 0.0297 = 11.0, so the threshold is the 12.0 on the card. Five of the six pairs are below 12:
from the inside out they have Δ = 10.1, 12.7, 11.9, 10.2, 6.6 and 10.5. The card names only the pair that falls furthest
short, and `report.json` lists all of them. The verdict is marginal for the published values and for all 20 draws.

Failing this test means that spacing alone cannot guarantee stability. It does not mean that the planets meet. Planets
in a *mean-motion resonance*, whose periods are near a simple ratio such as 3:2, can stay regular at smaller spacings.
The neighbours of TRAPPIST-1 have period ratios of 1.60, 1.67, 1.51, 1.51, 1.34 and 1.52, close to 8:5, 5:3, 3:2, 3:2,
4:3 and 3:2.

??? note "The other summaries you may see in this block"

    | Summary begins | Meaning | Verdict for the published values |
    |---|---|---|
    | `Hill stable: separation …` | Two planets, outside the limit. | stable |
    | `Not Hill stable: …` | A pair is inside the limit, or its orbits cross. Close encounters are not excluded, although a resonance can still protect the pair. | unstable |
    | `Every adjacent pair is at least 12 mutual Hill radii apart …` | Three or more planets, and the rule above holds. | stable |
    | `Every pair passes the two-planet limit, but … is only …` | Three or more planets, and a pair is closer than its threshold, as on this card. | marginal |
    | `Every pair passes the two-planet limit and the spacing threshold, but …` | Three or more planets, spaced widely enough, but with an eccentricity above 0.05. | marginal |

    The verdict in the heading also counts the draws, so it can differ from the summary. L 98-59, for example, has a
    summary that begins `Every adjacent pair is at least 12` under the heading `MARGINAL`, with a note that the draws
    disagree.

## Angular momentum deficit (AMD)

```text
│ AMD             STABLE   draws: 20 stable, 0 marginal, 0 unstable                                │
│   AMD-stable: largest β = 0.0285 (TRAPPIST-1 d / TRAPPIST-1 e), so collisions are excluded in    │
│   the secular approximation, provided the mutual inclinations carry no more AMD than the         │
│   eccentricities.                                                                                │
│   • β, β_S and β_H assume that the unknown mutual inclinations carry as much AMD as the          │
│   eccentricities (twice the coplanar AMD; Laskar & Petit 2017, Petit et al. 2017). For exactly   │
│   coplanar orbits they are half as large (largest β_p = 0.0142, β_S,p = 0.00015); 'unstable'     │
│   requires the coplanar values, lower bounds for any inclinations, to be ≥ 1.                    │
```

This indicator asks whether the system holds enough elongation for two neighbouring orbits to cross.

**The deficit.** A planet on a circular orbit has the angular momentum Λ = m √(G M★ a). An elongated orbit of the same
size has less, by the factor √(1 − e²), and a tilted orbit has less along the common axis, by the factor cos i. The
*angular momentum deficit* is what all the planets together lack, compared with circular orbits in one plane:

C = Σₖ Λₖ (1 − √(1 − eₖ²) cos iₖ)

Over long times the planets trade this deficit, so that one orbit becomes more elongated and another more circular. In
the orbit-averaged dynamics the total stays constant. That approximation is what the card calls *secular*.

**What β means.** So exostab asks: if one neighbouring pair took all of the AMD, could its orbits cross? β gives the
answer for each pair, as a single number: the AMD of the whole system divided by the smallest AMD that would let the
orbits of this pair cross, the *critical AMD* of Laskar & Petit (2017). In symbols, β = C / (Λ' C_c), where Λ' belongs
to the outer planet.

- β < 1: there is not enough AMD, so this pair cannot collide in this approximation. The approximation leaves out
  mean-motion resonances, which can change the AMD, and β < 1 does not exclude chaos. Laskar & Petit (2017) expect
  long-term stability from it only in the absence of mean-motion resonances.
- β ≥ 1: conservation of AMD cannot rule a collision out. It does not say that one happens. The Solar System itself is
  AMD-unstable, because the giant planets hold far more AMD than the orbits of the inner planets need to cross
  (Laskar & Petit 2017).

Close pairs can become chaotic through overlapping resonances before their orbits cross, so for them exostab uses the
smaller critical AMD of Petit, Laskar & Boué (2017), and a note names those pairs. If resonances overlap even on
circular orbits, β is infinite (`∞` on the card).

The other symbols are variations on β:

| Symbol | What it is |
|---|---|
| β_S | The same question for the innermost planet and the star: could the AMD bring that planet to the star? |
| β_H | Two planets only: the Hill criterion above, written with the AMD. |
| β_p, β_S,p, β_H,p | The same three with only the AMD of the eccentricities (*coplanar*, all orbits in one plane). |

**Why the card says "provided".** The *mutual inclinations*, the angles between orbits, are almost never measured, and
exostab places all orbits in one plane. Like Laskar & Petit (2017), it assumes that the unknown tilts carry as much AMD
as the eccentricities. This doubles the AMD, so β = 2β_p. That is an assumption, not a bound. The coplanar values are
lower bounds for any tilts, so exostab uses them when it says unstable: the assumption never strengthens a claim of
instability.

**The rule.** The verdict is stable if β < 1 for every pair and β_S < 1, with every pair in the range where the critical
AMD of Petit et al. (2017) applies. It is unstable only for two planets that are neither AMD-stable nor Hill stable even
with the coplanar AMD (β_p ≥ 1 and β_H,p ≥ 1). Everything else is marginal.

**This card.** The largest β is 0.0285, for planets d and e, far below 1. The note gives β_S,p = 0.00015, so β_S =
0.0003. The verdict is stable for the published values and for all 20 draws. TRAPPIST-1 is a chain of pairs near
mean-motion resonances, so this verdict is compatible with the chaotic runs below. This test is only as good as the
eccentricities that go into it. A planet with `0ᵃ` adds no AMD, and a note then says that β and β_S are lower limits. If
every eccentricity is assumed, the summary warns that the test says nothing about the real eccentricities
([below](#stable-with-assumed-eccentricities)).

??? note "The other summaries you may see in this block"

    | Summary begins | Meaning | Verdict for the published values |
    |---|---|---|
    | `AMD-stable: largest β = …` | β < 1 for every pair, and β_S < 1, as on this card. | stable |
    | `AMD-stable only because no eccentricity is measured` | Every eccentricity is assumed, so the AMD and every β are 0. | stable |
    | `Weakly AMD-stable` | β < 1 for every pair, but β_S ≥ 1: no pair can collide in this approximation, but the AMD could in principle bring the innermost planet to the star. | marginal |
    | `AMD-unstable: … of … adjacent pairs have β ≥ 1` | Three or more planets, with at least one pair at β ≥ 1. | marginal |
    | `AMD-unstable (β = …) but Hill stable in the AMD framework` | Two planets. Close encounters are impossible, but chaos is not excluded. | marginal |
    | `Neither AMD-stable (β = …) nor Hill stable (β_H = …), even for exactly coplanar orbits` | Two planets, with β_p ≥ 1 and β_H,p ≥ 1. | unstable |
    | `Neither AMD-stable (β = …) nor Hill stable (β_H = …) if the mutual inclinations carry …` | Two planets that fail only with the doubled AMD. | marginal |
    | `β < 1 for every pair …, but … outside the domain` | Every β is below 1, but a pair lies outside the range of the critical AMD. | marginal |

    Notes with ε_lim, α and α_R are about that range, where ε = (m + m') / M★ and α = a / a' for a pair. A note that
    ends with `the AMD verdict is at most marginal` means that the AMD indicator will not say stable because of that
    pair. A two-planet system can still get the verdict unstable, as HD 82943 does, because that verdict uses β_p and
    β_H,p. A note that says `α ≤ α_R` only says which critical AMD was used.

## N-body integration and MEGNO

```text
│ N-body + MEGNO  MARGINAL   draws: 18 stable, 2 marginal, 0 unstable                              │
│   Nominal run regular (<Y> = 2.17) over 41.4 yr (10,000 inner orbits); draws: 18 regular, 2      │
│   chaotic, 0 close encounter/escape of 20.                                                       │
│   • The nominal run is 'regular', but the draws disagree.                                        │
```

This is the most direct test: exostab computes the orbits forward in time. The *nominal run* uses the published values.
It lasts 10,000 orbits of the innermost planet (`inner orbits` on the card), here 41.4 years. The integrator is WHFast,
from the REBOUND package, which is fast and keeps the energy error bounded. The nominal run is repeated with a second,
slower integrator of high accuracy, IAS15, as a check.

**MEGNO.** Surviving is not enough, because a chaotic system can survive for a while and then fall apart. So every run
also computes the chaos indicator MEGNO, written `<Y>` on the card and ⟨Y⟩ in this documentation. It tracks how fast two
infinitely close copies of the system drift apart. For regular motion ⟨Y⟩ settles at 2, and for chaotic motion it keeps
growing (Cincotta & Simó 2000). exostab counts ⟨Y⟩ ≥ 2.2 as chaotic. That threshold is a judgment call, explained in
[Methods](methods.md#indicator-3-direct-n-body-integration-and-megno). ⟨Y⟩ is read once, at the end of the run. In a
short run it may not have settled yet, and it can end below 2. Any value below 2.2 counts as regular, so 1.1 is not more
regular than 2.0.

**What a run can be.** Each run gets one of four labels. The heading of the block counts the same runs in the words of
the verdicts, so `18 stable, 2 marginal` in the heading and `18 regular, 2 chaotic` in the summary say the same thing.

| Label | What happened | In the heading |
|---|---|---|
| regular | No close encounter or escape, and ⟨Y⟩ < 2.2. No chaos was found within this run. | stable |
| chaotic | No close encounter or escape, but ⟨Y⟩ ≥ 2.2. The motion is so sensitive to its start that the run says little about what comes later. | marginal |
| close encounter or escape | Two planets came closer than the mean of their Hill radii, or a planet moved beyond 100 times the largest orbit. The run stops there. | unstable |
| inconclusive | The relative energy error exceeded 10⁻⁵ at any of 1,200 checks through the run, so the numbers cannot be trusted. Or a planet came closer to the star than half its own Hill radius, where tides, general relativity and the size of the star, none of which is modelled, can decide what happens. | inconclusive |

Chaotic does not mean that the orbits break up. Chaotic orbits can stay bounded for far longer than a run of this
length; the orbits of the Solar System are themselves chaotic (Laskar 1989). So a chaotic run is a reason for caution,
not a prediction of an encounter.

The total energy should stay constant, so the energy error shows how far the computation has drifted.

### The draws

Published values have error bars, and a result that holds only for the exact published numbers is not trustworthy. So
exostab repeats the analysis for 20 *draws* by default. In each draw, every value is taken at random from a bell curve
(a split normal) with its peak at the published value and the upper and lower error bars as its widths. So about a third
of the drawn values lie outside the error bars. Random sampling of this kind is called Monte Carlo. Values without
published errors are held fixed, and values that are only upper limits are uniform below the limit. The draws ignore
correlations between the published values, which usually widens the spread of outcomes. The same `--seed` gives the same
draws. [Data and assumptions](data-assumptions.md#monte-carlo-draws) has the details.

All three indicators use the draws in the same way:

- The verdict for the published values stands only if at least 95% of the draws share it: 19 of 20 here, and 10 of 10 in
  the catalog, which uses 10 draws. Otherwise the indicator says marginal.
- The indicator says inconclusive if its nominal run is, or if more than 20% of its draws are.

Two more conditions apply only to the N-body verdict. It cannot be stable if WHFast and IAS15 disagree on the nominal
run, or if the outermost planet completes fewer than 100 orbits. A note on the card says so when either happens.

**This card.** The nominal run is regular, but only 18 of the 20 draws are, and 19 are needed. So the N-body verdict is
marginal, and the note says that the draws disagree.

The nominal ⟨Y⟩ of 2.17 is also just below the threshold. Run the same values for longer and the run is labelled
chaotic: ⟨Y⟩ = 2.42 over 30,000 orbits and 6.46 over 50,000 (`exostab check "TRAPPIST-1" --offline --orbits 50000
--draws 0`). Regular means only that no chaos was found within the run, and 41.4 years is a short time compared with the
age of a planetary system.

## The overall verdict

```text
│ Overall: MARGINAL  Direct integration: the nominal run is regular; of 20 draws, 18 are regular,  │
│ 2 chaotic and 0 had close encounters or escapes. Part of the parameter range allowed by the      │
│ published uncertainties is chaotic. The other indicators cannot guarantee stability (Hill        │
│ spacing: marginal).                                                                              │
│ N-body: 10,000 orbits of the innermost planet = 41.4 yr, WHFast dt = 0.0497 d, checked with      │
│ IAS15; 20 Monte Carlo draws; seed 0; MEGNO chaotic at <Y> ≥ 2.2; energy-error limit 1e-05.       │
```

**How the three combine.** The overall verdict is deliberately conservative, and it is not an average. exostab applies
these rules in this order:

1. **inconclusive**, if the N-body verdict is inconclusive.
2. If the N-body verdict is unstable: **unstable**, if draws were run, no input is only a published upper limit and the
   system has a single star. Otherwise **marginal**, because the instability may come from the limits or from the
   single-star model, or was not tested against the uncertainties.
3. **stable**, if every indicator says stable, draws were run and no N-body draw had a close encounter or escape.
4. **marginal**, in every other case.

So:

- Only the integration can make the overall verdict unstable. Hill spacing and AMD are sufficient conditions or
  heuristics: passing them says something, but failing them means only that stability is not guaranteed.
- One indicator that does not say stable is enough to prevent an overall stable.
- One close encounter among the draws also prevents it, even though the 95% rule lets the N-body verdict stay stable.
  Chaotic draws, and draws that fail Hill spacing or AMD, are listed in the summary but do not prevent it.
- With `--draws 0` the verdict is at most marginal, because nothing was tested against the uncertainties.
- With `--spock`, a fourth block appears. [SPOCK](methods.md#optional-indicator-4-spock) can make the overall verdict
  marginal, but never unstable on its own.

**This card.** AMD says stable, but Hill spacing and N-body say marginal, so rule 4 applies. The summary gives the two
reasons: 2 of the 20 draws are chaotic, and the spacing does not meet the rule for three or more planets.

!!! note "Marginal does not mean unstable"

    exostab cannot call this published parameter set stable under these settings: the evidence is mixed. That is not a
    prediction for the planets, and a card cannot settle what the real planets do. You will see this verdict often. It
    is the verdict of 18 of the 21 snapshot systems that exostab can model, and of 413 of the 1,044 systems checked in
    the catalog of 26 October 2026.

**The settings line.** The line below the summary records how the run was made:

| On the card | What it means | Change it with |
|---|---|---|
| `10,000 orbits of the innermost planet = 41.4 yr` | The length of each run. | `--orbits` |
| `WHFast dt = 0.0497 d` | The time step: 1/30 of the shortest pericentre-passage time of any planet, T_p = P (1 − e)^(3/2) / (1 + e)^(1/2), the time a planet takes to swing through its closest approach to the star. For near-circular orbits this is 1/30 of the innermost period. | no option |
| `checked with IAS15` | The nominal run was repeated with IAS15. | `--no-ias15` |
| `20 Monte Carlo draws` | The number of draws. | `--draws` |
| `seed 0` | The start of the random numbers: the draws, any random angles and the start of the MEGNO calculation. On the same platform and software versions, the same seed gives the same results. | `--seed` |
| `MEGNO chaotic at <Y> ≥ 2.2` and `energy-error limit 1e-05` | The two thresholds above. | no option |

With `--budget`, exostab chooses the run length and the number of draws to fit a time, and this line says so.

## Data completion

```text
│ Data completion (applied automatically):                                                         │
│ b, c, d, e, f, g, h  Orbital phase set from the transit mid-time, propagated with the period     │
│                      (transit time and period come from different publications).                 │
│ system               All orbits are placed in one plane. Mutual inclinations are not published   │
│                      (sky-plane inclinations do not determine them), and longitudes of the       │
│                      ascending node are not used.                                                │
│ Note: offline snapshot of 22 systems                                                             │
```

The archive rarely has every number an integration needs. exostab fills each gap by a written rule, and every rule that
fires prints a line here: on the left the planets it applies to, or `system`, and on the right what was done. In
`report.json` these lines are the *flags*, each with a short code (`system.flags`). Read this list before you lean on a
verdict, because it says what the verdict rests on.

On this card there are two. The phase of each planet comes from a transit time, carried to a common start with the
period, although that time and the period come from different papers. And all orbits lie in one plane, because transit
and radial-velocity inclinations are measured against the sky, not against each other. That second line is on every
card, and it is the reason for the "provided" in the AMD summary.

The lines you will see most often:

| The line says | What it means for your reading |
|---|---|
| `Eccentricity not published; assumed 0.` or `Eccentricity published as exactly 0 without an uncertainty …` | e = 0 in every run, so the draws do not vary it, and the planet adds no AMD. A verdict then holds under that assumption. |
| `Argument of periastron not published; drawn uniformly …` | ω is random in every run. |
| `Orbital phase drawn uniformly for every run: …` | The starting positions are random. A system protected by a resonance can look chaotic or unstable with random phases. |
| `Only the minimum mass m sin i is known; …` | The true mass can be larger, and larger masses shrink the spacing. |
| `Mass not measured; the archive estimated it …` or `Mass not published; estimated …` | The mass comes from the radius, not from a measurement of the mass. |
| `Only an upper limit … is published; …` | The nominal run uses the limit, and the draws lie below it. An instability found this way gives an overall marginal. |
| `The system has 2 stars; only the host star is modelled. …` | A companion could change the orbits. An instability gives an overall marginal. |
| `The planet rows give different stellar masses …` or `The planet rows give one stellar mass with different errors or sources …` | The rows of one host disagree, and the line says which value a written rule chose. |
| `The archive flags this planet as controversial …` | Its existence has been questioned. It is kept in the run. |

[Data and assumptions](data-assumptions.md#completion-rules) lists every rule. The line `Note:` is not a rule: it says
that the snapshot is in use, or that the archive could not be reached.

## The files it writes

```text
│ Saved: exostab-results/trappist-1/report.json, exostab-results/trappist-1/orbits.png,            │
│ exostab-results/trappist-1/megno.png                                                             │
╰──────────────────────────────────────────────────────────────────────────────────────────────────╯
Finished in 7.8 s.
```

exostab writes three files to a folder named after the system, in `exostab-results/` below the folder you ran it in. A
new run of the same system overwrites them. `--out` chooses another folder, and `--no-plots` leaves out the figures. The
last line of the output is the run time.

- **`report.json`** is the full record of the check, with a versioned schema. It holds what the card rounds or leaves
  out: the publication behind each value (`system.planets`), the flags (`system.flags`), the spacing of every pair
  (`indicators.hill.details.pairs`), β of every pair (`indicators.amd.details.pairs`), the outcome of every draw
  (`indicators.nbody.details.draws`), the settings and the versions of the software. It is the file to keep when you
  write about a run.
- **`orbits.png`** is a view from above: the starting orbits as lines, and the positions during the nominal run as dots.
- **`megno.png`** shows the N-body indicator:

![Three panels from the megno.png of this run. Top left: MEGNO against time for the nominal run, with WHFast and IAS15. Both curves jump to about 2, stay near 2 for about 20 years, then climb to 2.17, just below a dashed line at 2.2 marked chaotic. Bottom left: the relative energy error against time, around 10 to the power of minus 8 for WHFast and around 10 to the power of minus 15 for IAS15. Right: the final MEGNO of the 20 draws, sorted; 18 lie below 2.2 and 2 above it.](assets/reading-a-report/trappist-1-megno.png)

**Figure 1.** The `megno.png` of the run on this page. Top left: ⟨Y⟩ of the nominal run with both integrators. It stays
near 2 for about 20 years and then starts to climb, the start of the chaos that the longer runs show. Bottom left: the
relative energy error, far below the limit of 10⁻⁵. Right: the final ⟨Y⟩ of each draw, sorted. Most of the regular draws
end below 2: in 41.4 years their ⟨Y⟩ has not settled. The two above the dashed line are the chaotic draws on the card. A
draw with a close encounter or escape would be drawn at 8.

## Common cases, and what to do next

The cards in this section were printed in the same way as the one above: same version, date, computer and defaults,
apart from the options named. They use the snapshot, so you can repeat them with `--offline`, except where the archive's
table is named. A line with `…` stands for lines of the card that are left out here.

### Marginal: the draws disagree

This is the card above: the nominal run is regular, but some draws are chaotic.

**What it means.** exostab cannot call this published parameter set stable under these settings. Planets f and g are
closer than the spacing rule asks, in all 20 draws, and 2 of the 20 draws are chaotic over this 41.4-year run. That is
not a prediction for the planets.

**What to do next.**

- Run longer, and see whether the runs stay regular. With `--orbits 30000` the nominal run and 8 of the 20 draws are
  chaotic, and with `--orbits 100000` (414 years) the nominal run and all 20 draws are, still with no close encounter or
  escape. No run length can make this overall verdict stable, because Hill spacing does not depend on it. With
  `--draws 0` a longer run takes less time, and the verdict is then at most marginal.
- Try other seeds, to see how firm the counts are. For TRAPPIST-1, `--seed 1` and `--seed 2` both give 17 regular and 3
  chaotic draws. The values of the nominal run stay the same, but the seed also sets the random start of the MEGNO
  calculation. So the ⟨Y⟩ of the nominal run changes: 2.17, 2.16 and 2.38 for seeds 0, 1 and 2, and with `--seed 2` that
  run is labelled chaotic. A ⟨Y⟩ this close to 2.2 is not a firm label. The overall verdict is marginal in all three.
- The list under `Data completion` says that transit times and periods come from different papers. To test the solution
  of one paper, write it in a YAML file and run it with `--from-file`
  ([your own parameters](data-assumptions.md#your-own-parameters)). For TRAPPIST-1 the repository has one:
  `exostab check --from-file examples/trappist1_agol2021.yaml`, the solution of Agol et al. (2021). Over the same 41
  years, with seed 0, its nominal ⟨Y⟩ is 1.27 and 19 of 20 draws are regular; its overall verdict stays marginal, because Hill spacing
  does not depend on the orbital phases. The header of
  [the file](https://github.com/mimitoz62/exostab/blob/main/examples/trappist1_agol2021.yaml) says why every ω in it has
  180° added.

### Stable, with assumed eccentricities

`exostab check "Kepler-36" --offline`:

```text
│ Kepler-36   M* = 1.03 ± 0.022 M☉   2 planets   data: snapshot (2026-09-28)                       │
│                                                                                                  │
│ Planet       P (d)             Mass (M⊕)        e   ω (deg)  Phase                               │
│ Kepler-36 b  13.8682 ± 0.0005  3.83 +0.11/−0.1  0ᵃ  random   transit                             │
│ Kepler-36 c  16.2187 ± 0.0001  7.13 ± 0.18      0ᵃ  random   transit                             │
…
│ AMD             STABLE   draws: 20 stable, 0 marginal, 0 unstable                                │
│   AMD-stable only because no eccentricity is measured: every planet is assumed to be on a        │
│   circular orbit, so the AMD and every β are 0. The test says nothing about the real             │
│   eccentricities.                                                                                │
…
│ Overall: STABLE  All indicators agree: no sign of instability for the nominal parameters or any  │
│ of the 20 draws. The N-body test covers only the integrated time span, not the age of the        │
│ system.                                                                                          │
```

**What it means.** exostab calls this published parameter set stable under these settings, with e = 0 in every run. The
draws do not vary an assumed eccentricity, and AMD has nothing to test. So the verdict holds under that assumption, and
it is not a proof. This is the most common kind of stable verdict: in the catalog of 26 October 2026, 512 of the 619
stable verdicts have every eccentricity assumed 0
([What the catalog shows](findings.md#what-the-stable-verdicts-rest-on)).

**What to do next.**

- See how much rests on the assumption, by varying one eccentricity. This makes one run per row, without draws and with
  the other values fixed, so planet c stays at e = 0:

    ```bash
    exostab sweep "Kepler-36" --planet b --param e --range 0 0.1 --steps 11 --offline
    ```

    ```text
           Kepler-36: sweep of e for planet b
    ┏━━━━━━━┳━━━━━━━━━━┳━━━━━━┳━━━━━━━━━━┳━━━━━━━━━━┓
    ┃ value ┃ N-body   ┃ <Y>  ┃ Hill     ┃ AMD      ┃
    ┡━━━━━━━╇━━━━━━━━━━╇━━━━━━╇━━━━━━━━━━╇━━━━━━━━━━┩
    │ 0     │ regular  │ 2    │ stable   │ stable   │
    │ 0.01  │ regular  │ 2.02 │ stable   │ stable   │
    │ 0.02  │ chaotic  │ 6.17 │ stable   │ stable   │
    │ 0.03  │ chaotic  │ 137  │ stable   │ marginal │
    │ 0.04  │ chaotic  │ 435  │ stable   │ marginal │
    │ 0.05  │ chaotic  │ 498  │ stable   │ marginal │
    │ 0.06  │ chaotic  │ 430  │ unstable │ unstable │
    │ 0.07  │ unstable │ —    │ unstable │ unstable │
    │ 0.08  │ unstable │ —    │ unstable │ unstable │
    │ 0.09  │ unstable │ —    │ unstable │ unstable │
    │ 0.1   │ unstable │ —    │ unstable │ unstable │
    └───────┴──────────┴──────┴──────────┴──────────┘
    ```

    In this sweep the N-body run is chaotic from e = 0.02, AMD stops saying stable at 0.03, and Hill spacing at 0.06. So
    the stable verdict on the card rests on an eccentricity close to 0. In the N-body column, `unstable` is the label
    close encounter or escape, and `—` means that ⟨Y⟩ is not meaningful for a stopped run.

- Look for a published eccentricity or limit, and run it with `--from-file`.
  [What the catalog shows](findings.md#what-stable-means-here-and-what-it-does-not) describes such a run for Kepler-36,
  which comes out marginal.

### Marginal: the N-body runs are regular, but Hill or AMD cannot guarantee stability

`exostab check "Kepler-9" --offline`:

```text
│ Hill spacing    MARGINAL   draws: 0 stable, 20 marginal, 0 unstable                              │
│   Every pair passes the two-planet limit, but Kepler-9 b / Kepler-9 c is only 11.1 mutual Hill   │
│   radii apart, where the heuristic threshold for its eccentricities is 14.1 (Pu & Wu 2015,       │
│   extrapolated beyond σ_e = 0.05); long-term stability is not guaranteed by spacing alone.       │
…
│ N-body + MEGNO  STABLE   draws: 20 stable, 0 marginal, 0 unstable                                │
│   Nominal run regular (<Y> = 2.06) over 43.6 yr (10,000 inner orbits); draws: 20 regular, 0      │
│   chaotic, 0 close encounter/escape of 20.                                                       │
│                                                                                                  │
│ Overall: MARGINAL  The N-body integration shows regular motion for the nominal parameters and    │
│ all 20 draws. The other indicators cannot guarantee stability (Hill spacing: marginal). Every    │
│ pair passes the two-planet limit, but Kepler-9 b / Kepler-9 c is only 11.1 mutual Hill radii     │
│ apart, where the heuristic threshold for its eccentricities is 14.1 (Pu & Wu 2015, extrapolated  │
│ beyond σ_e = 0.05); long-term stability is not guaranteed by spacing alone.                      │
```

**What it means.** The integration found no sign of instability within 43.6 years, but the analytic test cannot back
that up. Hill spacing and AMD can fail for a system that stays regular over the run. The integration covers only a short
time, and the analytic tests reach further but make approximations. In the catalog of 26 October 2026, this is what 153
of the 413 marginal verdicts look like. `extrapolated beyond σ_e = 0.05` says that an eccentricity of the pair is above
0.05, the largest spread of eccentricities in the simulations behind the threshold.

**What to do next.**

- See which pair holds the verdict back, and compare its period ratio with simple ratios. Here c and b have
  38.9853 / 19.2389 = 2.03, close to 2:1. A ratio near a simple fraction is a hint, not a proof of a resonance. The
  standard example of this case is [GJ 876](validation.md#3-known-systems) with the published four-planet solution of
  Rivera et al. (2010): unstable by Hill spacing and marginal by AMD, yet every N-body draw is regular.
- Run longer. A longer run cannot change Hill spacing or AMD, so the overall verdict cannot become stable, but it shows
  whether the regular motion lasts. With `--orbits 100000`, the nominal run of Kepler-9 is chaotic (⟨Y⟩ = 12.96 over 436
  years), and so are 4 of the 20 draws.
- For a resonant pair the phases matter. If a paper gives a full dynamical solution, run that with `--from-file`.

### Marginal: the run is short for the outer planet

`exostab check "ups And" --offline`:

```text
│ N-body + MEGNO  MARGINAL   draws: 20 stable, 0 marginal, 0 unstable                              │
│   Nominal run regular (<Y> = 2.00) over 126 yr (10,000 inner orbits); draws: 20 regular, 0       │
│   chaotic, 0 close encounter/escape of 20.                                                       │
│   • The outermost planet completes only 36.1 orbits in this run, fewer than 100; a longer run is │
│   needed for a meaningful test of the outer planets.                                             │
│                                                                                                  │
│ Overall: MARGINAL  Every WHFast run is regular (the nominal parameters and all 20 draws), but    │
│ the N-body verdict is only marginal: the outermost planet completes only 36.1 orbits, fewer than │
│ the 100 needed to judge it (a longer run is needed). The other indicators cannot guarantee       │
│ stability (Hill spacing: marginal, AMD: marginal).                                               │
```

**What it means.** The run is counted in orbits of the innermost planet. In a wide system the outer planets then
complete few orbits, too few to judge them. All the runs are regular, but the test is too short. In the catalog of 26
October 2026, 89 of the 413 marginal verdicts look like this.

**What to do next.** Increase `--orbits` to at least 100 × P_outermost / P_innermost. Here that is
100 × 1276.46 / 4.61703 ≈ 27,650, so `--orbits 30000`, which takes about three times as long:

```text
│ N-body + MEGNO  STABLE   draws: 20 stable, 0 marginal, 0 unstable                                │
│   Nominal run regular (<Y> = 2.00) over 379 yr (30,000 inner orbits); draws: 20 regular, 0       │
│   chaotic, 0 close encounter/escape of 20.                                                       │
```

The N-body verdict is now stable. The overall verdict stays marginal, for the reason of the previous case. Where Hill
spacing and AMD already say stable, the longer run can change the overall verdict too: on the archive's table of
31 October 2026, exostab calls K2-73 marginal with the defaults and stable with `--orbits 14000`. Both of its
eccentricities are assumed 0, so read that verdict as in [the case above](#stable-with-assumed-eccentricities).

### Unstable

`exostab check "HD 82943" --offline`:

```text
│ Planet      P (d)            Mass (M⊕)   e               ω (deg)    Phase                        │
│ HD 82943 c  220.078 ± 0.051  623 ± 14.9  0.366 ± 0.0097  117 ± 1.7  random                       │
│ HD 82943 b  441.47 ± 0.35    534 ± 8.9   0.162 ± 0.036   301 ± 3.4  random                       │
…
│ N-body + MEGNO  UNSTABLE   draws: 0 stable, 1 marginal, 19 unstable                              │
│   Nominal run: close encounter after 126 yr (210 of 10,000 planned inner orbits); draws: 0       │
│   regular, 1 chaotic, 19 close encounter/escape of 20.                                           │
│   • The orbital phases of HD 82943 c, HD 82943 b are not published and are drawn at random in    │
│   every run (the nominal run included). A system protected by a mean-motion resonance can look   │
│   chaotic or unstable for random phases; a YAML system file with measured phases can be used to  │
│   test the real configuration.                                                                   │
│                                                                                                  │
│ Overall: UNSTABLE  Direct integration finds close encounters or escapes for the nominal          │
│ parameters and for 19 of 20 draws within the published uncertainties.                            │
```

**What it means.** exostab calls this published parameter set unstable under these settings. The numbers in the table do
not survive integration. That is a statement about these numbers, not a prediction for the planets. Common reasons: the
values come from independent orbit fits or from several papers, the orbits are placed in one plane, the error bars are
wide, or a resonance is not represented. Here the phases are random, and the period ratio of 2.006 is close to 2:1. A
resonance protects a pair only with the right periods and phases, so these runs do not test that configuration.
[What the catalog shows](findings.md#published-parameter-sets-that-do-not-survive-integration) goes through such cases.

One draw can decide this verdict. The catalog of 26 October 2026 uses 10 draws, so it needs all 10 to have a close
encounter or escape. HD 82943 has 9 there, and the catalog calls it marginal.

**What to do next.**

- Read the N-body notes and the list under `Data completion`: are the phases random, and do values come from different
  papers?
- Look up the publication behind each value in `report.json`, write the orbital solution of one paper in a YAML file,
  and run it with `--from-file`.
- If the phases are random, try other seeds. Here `--seed 1` and `--seed 2` also give 19 of 20 draws with a close
  encounter or escape, with the nominal encounter after 1,732 and 11.8 years. So do not read the time of an encounter as
  a prediction.
- When you write about it, say that this published parameter set does not survive integration with these settings.

If the N-body heading says `UNSTABLE` but the overall verdict is marginal, then rule 2 of
[the overall verdict](#the-overall-verdict) applied, and the summary says why: inputs that are only upper limits
(HR 8799, whose `<0.6` and `<0.5` are eccentricities), several stars, or `--draws 0`.

### Inconclusive

`exostab check "HD 10180" --offline`:

```text
│ HD 10180 c  5.75969 ± 0.00028  <2.74e+03   0.073 ± 0.031  328 ± 24  periastron                   │
│ HD 10180 d  16.357 ± 0.0038    <3.3e+03    0.131 ± 0.052  325 ± 23  periastron                   │
…
│ N-body + MEGNO  INCONCLUSIVE   draws: 1 stable, 9 marginal, 4 unstable, 6 inconclusive           │
│   Nominal run inconclusive over 158 yr (10,000 inner orbits); draws: 1 regular, 9 chaotic, 4     │
│   close encounter/escape, 6 inconclusive of 20.                                                  │
│   • WHFast and IAS15 disagree on the nominal run (inconclusive vs chaotic).                      │
│   • The outermost planet completes only 26.1 orbits in this run, fewer than 100; a longer run is │
│   needed for a meaningful test of the outer planets.                                             │
│   • nominal: relative energy error 1.8e-05 exceeds 1e-05; no verdict for this run.               │
│                                                                                                  │
│ Overall: INCONCLUSIVE  The N-body integrations could not be trusted (see the N-body notes), so   │
│ no overall verdict is given.                                                                     │
```

**What it means.** exostab makes no statement on this parameter set: this is not a verdict of stable or unstable. The
nominal run went over the limit on the energy error, so the N-body indicator is inconclusive, whatever the draws show.
Hill spacing and AMD still print their verdicts, but the overall verdict does not use them.

**What to do next.**

- Read the N-body notes. They say which rule fired.
- If it is the energy error, look at the inputs. Here three masses are only upper limits, of about 2,700 to 3,400 Earth
  masses, and the nominal run uses them. To test other values, use `--from-file`. In a what-if run, not a catalog
  result, the limits were replaced by the minimum masses of Kane & Gelino (2014, ApJ 792, 111) from the archive's `ps`
  table: 13, 12 and 23 Earth masses. The energy error of the nominal run is then 5 × 10⁻⁸, and all 20 draws are regular.
  That run is marginal, because the outermost planet still completes only 26 orbits and Hill spacing and AMD are
  marginal too.
- If a planet passed close to the star, exostab cannot help further: it models neither tides, nor general relativity,
  nor the size of the star.

### Skipped: no verdict

`exostab check "Kepler-47" --offline`:

```text
Kepler-47 is a circumbinary system; exostab models a single host star and cannot check it.
```

**What it means.** exostab cannot model this system from the table, so there is no card, no file and no verdict. The
sentence gives the reason, and it says what exostab can do with the data, not whether the system is stable. In the
catalog such a system has the status `skipped` and the same reason: 35 of the 1,079 systems in the catalog of 26 October
2026. The usual reasons are circumbinary planets, a host with a single planet row in the table, a planet without a
period that was found by microlensing or direct imaging, and a planet with neither a mass nor a usable radius.
[Data and assumptions](data-assumptions.md#completion-rules) lists them.

**What to do next.** If a value is missing and a publication gives it, supply the system with `--from-file`. exostab
does not model planets around two stars, so a circumbinary system stays out of reach. In the catalog, the status
`timeout` means something else: the system ran over the catalog's time limit, and `exostab check` has no such limit.

## Where to read more

- [Methods](methods.md): the formulas and references for each indicator and for the overall verdict.
- [Data and assumptions](data-assumptions.md): where the values come from, and all the completion rules.
- [What the catalog shows](findings.md): what the verdicts of the whole catalog rest on, and how firm they are.
- [FAQ](faq.md) and [CLI reference](cli.md): short answers, and every option of `exostab check`.
