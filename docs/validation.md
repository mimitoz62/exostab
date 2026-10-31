---
description: >-
  How exostab is tested against physics and published results: energy conservation, the Hill limit, TRAPPIST-1, GJ 876,
  Kepler-11 and the HD 127195 Research Note, with tolerances and versions.
---

# Validation

The validation suite is in `tests/validation/test_validation.py`. It is slow (about a minute on a 14-core laptop),
so it runs nightly in continuous integration and on demand:

```bash
pytest -m slow
python scripts/validation_summary.py
python scripts/validation_figures.py
```

The first script prints the numbers below. The second draws the figures below and prints the Hill-limit fractions. Run
the two scripts from the repository root with `PYTHONPATH=.`.

The numbers on this page were produced on 2026-10-31 by these two scripts from the tag v1.0.0, with exostab 1.0.0,
REBOUND 5.2.2, NumPy 2.5.4 and Python 3.14.7 on macOS (Apple M4 Pro). They use the bundled archive snapshot of
2026-09-28 and default settings unless stated. `validation_summary.py` prints sections 1, 3 and 4;
`validation_figures.py` prints the fractions of section 2. The robustness measurements quoted in section 2 come from
a separate study of the Hill-limit test (2026-10-04) and are not reproduced by the scripts.

Chaotic integrations are sensitive to floating-point rounding. Counts of chaotic draws can differ by one or two on
other machines, and so can which runs of a chaotic pair meet within a finite horizon. The tests assert only what
does not depend on rounding.

## 1. Energy conservation: inner Solar System

Sun, Mercury, Venus, Earth–Moon, Mars (approximate J2000 elements, coplanar), integrated for 10,000 years. The
energy error is the largest of the 1,200 checks made through every run.

| Integrator | Relative energy error | ⟨Y⟩ | Test tolerance |
|---|---|---|---|
| WHFast, dt = 1.891 d | 1.44 × 10⁻⁹ | 1.999 | < 10⁻⁷ |
| IAS15 | 5.25 × 10⁻¹⁵ | 2.001 | < 10⁻¹² |

![Relative energy error of the inner Solar System with WHFast and IAS15 over 10,000 years](assets/validation/energy.png)

## 2. The Hill limit

For two planets of 10⁻⁵ M☉ around a solar-mass star on circular orbits, exostab's Gladman criterion gives
3.462 mutual Hill radii. The circular-orbit limit tends to 2√3 = 3.464 for small masses.

Inside the limit the planets are not guaranteed to meet, and when they meet is a matter of chaos. Well inside,
every starting phase meets at the first conjunction. Between about 2.4 and 3.46 mutual Hill radii the motion is
chaotic, and the time to the first close encounter is a chaotic transient with a long tail that depends on the
last bit of the initial conditions: in the study of 2026-10-04, moving one starting phase at 3.0 by one unit in
the last place turned "encounter after 1,192 orbits" into "no encounter within 5,000 orbits". Beyond 3.46 the pair
is Hill stable, and no encounter is possible. The tests therefore check only outcomes that cannot depend on
rounding, each for 8 starting phases of the outer planet:

- at 2.2 mutual Hill radii, every phase meets within 5,000 orbits (on this machine within 15 orbits, at the
  first conjunction);
- at 4.0 and 4.5, no phase meets within 5,000 orbits;
- at 3.0, no phase is regular, and at least 6 of 8 meet within 20,000 orbits;
- a synthetic pair 2.5 mutual Hill radii apart gets the overall verdict **unstable** (Hill and N-body both
  unstable).

Until 2026-10-04 the test required every phase to meet within 5,000 orbits at 2.5 and at 3.0. That held on macOS
but failed on Linux (x86_64) in the nightly run: which phases meet within a finite horizon depends on rounding.
In the study of 2026-10-04, 8 phases × 500 copies whose initial conditions were perturbed by a relative 10⁻¹⁴
were integrated at 3.0. 95% of the runs met within 5,000 orbits, 99.4–99.6% within 20,000 (two repetitions) and
99.9% within 10⁶; the others scattered apart through near misses and stayed chaotic (⟨Y⟩ > 13), and none was
regular. The old
requirement failed for 33% of these perturbed sets of 8 phases; the new one failed for none, because never more
than 2 of the 8 phases missed.

![Fraction of starting phases with a close encounter within 5,000 orbits against the initial separation, with the two Gladman limits](assets/validation/hill_limit.png)

The figure shows one machine and one horizon (5,000 orbits). On this machine all 8 phases meet from 2.0 to 3.1
mutual Hill radii, 7 at 3.2, 6 at 3.3 and none from 3.4 outwards. The boundary moves outward with the horizon: in
the study of 2026-10-04, perturbed runs at 3.4 had encounters after about 8 × 10⁴ orbits, while one phase at 3.3
stayed regular for 10⁶ orbits. Notebook 02 of the Research Note code found that encounters stop between 3.30 and
3.35 within 5,000 orbits, but with a different protocol: an encounter distance of one mutual Hill radius
(exostab: the mean of the two Hill radii, 0.79 mutual Hill radii for equal planets), a time step of P/50 (exostab:
P/30) and a grid step of 0.05. The two results agree only approximately, and exostab does not claim to reproduce
that number.

## 3. Known systems

| System | Data | Hill | AMD | N-body | Overall | Nominal ⟨Y⟩ (WHFast / IAS15) | Draws: regular / chaotic / encounter |
|---|---|---|---|---|---|---|---|
| TRAPPIST-1 | archive snapshot | marginal | stable | marginal | **marginal** | 2.1709 / 2.1685 | 18 / 2 / 0 |
| GJ 876 | Rivera et al. (2010) coplanar fit | unstable | marginal | stable | **marginal** | 1.9925 / 1.9951 | 20 / 0 / 0 |
| GJ 876 | archive snapshot (random phases) | unstable | marginal | marginal | **marginal** | 3.9795 / 3.7621 | 3 / 5 / 12 |
| Kepler-11 | archive snapshot | marginal | marginal | marginal | **marginal** | 1.7855 / 1.7857 | 10 / 8 / 2 |

No draw of these four runs is inconclusive. What the tests require (from the project brief) and why:

- **TRAPPIST-1**, a resonant chain: stable or marginal, never unstable. ✔ Over 10,000 orbits of TRAPPIST-1 b
  (41 years) the nominal run is regular. It is not regular over longer runs: ⟨Y⟩ is 2.42 after 30,000 orbits and
  6.46 after 50,000 (WHFast; 5.26 with IAS15), with `exostab check "TRAPPIST-1" --offline --draws 0` and
  `--orbits 30000` or `50000`.
- **GJ 876**, in a Laplace resonance: expected stable. The archive does not provide usable orbital phases for
  GJ 876, and with random phases the resonance is destroyed (12 of 20 draws have close encounters). The test
  therefore uses the published four-planet solution of Rivera et al. (2010, Table 3), with its mean anomalies,
  and requires the **N-body** verdict to be stable ✔. The Hill and AMD criteria are only sufficient conditions
  or heuristics, and they fail for this resonance-protected system. By design, the conservative overall verdict is therefore
  marginal, not stable.
- **Kepler-11**, a compact six-planet system: expected stable over the test horizon. The test requires that the
  nominal configuration (archive values, phases from the transit times) completes 10,000 orbits of Kepler-11 b
  (282 years) without a close encounter, that it is regular with both integrators, and that the N-body and
  overall verdicts are not unstable ✔. The nominal Hill test fails narrowly for the f/g pair, because the archive
  gives only upper limits for planet g (25 M⊕ and e < 0.15) and the nominal run uses them; the Hill verdict is
  marginal because the draws disagree. Across the Monte Carlo draws, 2 of 20 have close encounters. The
  archive's eccentricity error bars are wide (e.g. e_b = 0.045 +0.068), and independent draws sometimes make
  neighbouring orbits nearly cross. The N-body verdict is therefore marginal. This is reported as found.

![GJ 876: final MEGNO of 20 draws with the published phases and with random phases](assets/validation/gj876.png)

## 4. The HD 127195 Research Note

`examples/hd127195_note.yaml` holds the inputs of the Research Note (Öz 2026, prepared for Research Notes of the
AAS; code in [mimitoz62/hd127195-stability](https://github.com/mimitoz62/hd127195-stability)). The run uses the
Note's settings where exostab has them: 20,000 orbits of planet b, 200 draws and MEGNO < 2.2 regular; seed 42.
The time step is exostab's own, 1/30 of the shortest pericentre-passage time: 16.43 d for the best fit, about 8%
smaller than the Note's P_b/30 = 17.82 d, and smaller still for draws with a larger e_b.

| Quantity | Research Note | exostab | Test tolerance |
|---|---|---|---|
| a_b, a_c (AU) | 1.42125, 1.91684 | 1.42125, 1.91684 | 10⁻⁵ relative |
| Period ratio | 1.566 | 1.566 | 10⁻⁵ relative |
| Separation (mutual Hill radii) | 4.37 | 4.371 | 10⁻³ relative |
| Best-fit ⟨Y⟩, WHFast / IAS15 | 2.000 / 2.000 | 1.999 / 1.999 | ± 0.02 (WHFast); regular, < 2.2 (IAS15) |
| Draws regular | 134 / 200 | 133 / 200 | ± 3 binomial σ (± 20) |
| Draws with close encounters | 9 / 200 | 5 / 200 | ± 3 binomial σ (± 9) |
| Draws chaotic, no encounter | 57 / 200 | 51 / 200 | not tested separately |
| Draws inconclusive (energy error above 10⁻⁵) | — (no energy criterion) | 11 / 200 | at most 10% of the draws, all chaotic by MEGNO |
| Draws passing the collision AMD test (Note's convention) | 200 / 200 | 200 / 200 | all |
| AMD limit, equal eccentricities (Note's convention) | 0.148 | 0.1478 | ± 0.0005 |
| Conclusion | best fit regular; a substantial part of the AMD-stable parameter space is chaotic | N-body: nominal stable, verdict marginal; overall marginal | exact |

![HD 127195: counts of regular, chaotic and close-encounter draws, exostab against the Research Note](assets/validation/hd127195.png)

The draws cannot match the Note one-to-one because the random number streams differ. The regular fraction agrees
closely (133 against 134). exostab finds fewer close encounters (5 against 9); the difference is inside the
tolerance of 3 binomial standard deviations, but the comparison has little power for so rare an outcome.

The 11 inconclusive draws reached the end of the run without a close encounter, with ⟨Y⟩ between 755 and 1,508,
so they are chaotic by MEGNO. Their largest relative energy errors, 1.01–1.58 × 10⁻⁵, are just above exostab's
limit. exostab checks the energy error at 1,200 times through every run (DECISIONS.md, D8), and WHFast's error
peaks at pericentre passages; the Note applied no energy criterion. These draws therefore belong to the Note's
chaotic class: counted as chaotic, exostab has 51 + 11 = 62 chaotic draws against the Note's 57, and the regular
and close-encounter comparisons above do not change. Before exostab checked the energy error over the whole run
(until 2026-10-04), the same seed gave 133 regular, 62 chaotic and 5 close encounters.

The AMD rows use the Note's convention: the coplanar AMD (the eccentricities alone), α from the period ratio and
the collision criterion of Laskar & Petit (2017). exostab's AMD indicator differs in two ways (see
[Methods](methods.md)). It takes the AMD as twice the coplanar value (β = 2β_p, Laskar & Petit 2017), and it uses
the resonance-overlap criterion of Petit, Laskar & Boué (2017), which the Note did not use and which applies to
this pair: α = 0.7415 lies above α_R = 0.7288, and ε = 9.4 × 10⁻⁴ is below ε_lim = 8.11 × 10⁻³. With both, the
equal-eccentricity limit for β = 1 is 0.0713 instead of 0.1478, and 137 of the 200 draws are strongly
AMD-stable (185 with the coplanar AMD alone). The AMD indicator gives 137 stable, 49 marginal and 14 unstable
draws, and its verdict is *marginal*.

## 5. Reproducibility

On the same platform and software versions, the same seed gives identical runs (tested). On another platform,
floating-point rounding can change chaotic runs and with them a verdict;
[What the catalog shows](findings.md#how-firm-these-numbers-are) gives the numbers for the catalog. Each `report.json`
stores the seed, the versions of exostab, REBOUND, NumPy, astropy and Python, the integrator and time step, the run
length and the archive download date. Each
`sweep.json` stores the seed, the run length, the range and number of steps, the integrator and time step, the
command and the creation time.
