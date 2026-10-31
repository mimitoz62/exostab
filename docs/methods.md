---
title: "Methods: Hill spacing, AMD and N-body integration with MEGNO"
description: >-
  How exostab estimates orbital stability: Hill spacing, the angular momentum deficit, N-body integration with MEGNO,
  the propagation of uncertainties and the rules of the overall verdict.
---

# Methods

This page explains, in plain language, what exostab computes and why. Every formula is written out in the
code docstrings too (`src/exostab/indicators/`), and every choice with its reasons is in
[DECISIONS.md](https://github.com/mimitoz62/exostab/blob/main/DECISIONS.md). References are listed at the end;
full entries are in [`references.bib`](references.bib).

## The question

A planetary system is *dynamically stable* if its planets keep roughly the same orbits for a very long time:
no two planets come close to each other, collide, or throw one another out of the system. Planets pull on each
other gently all the time, and most of the time these tugs average out. But if two planets are too close, or
their orbits too elongated, the tugs can build up until the orbits cross.

Stability cannot be proven for more than two planets. exostab therefore asks the question in three different
ways and reports all three answers.

## Step 1: getting the numbers

Parameters come from the NASA Exoplanet Archive's *Planetary Systems Composite Parameters* table
(`pscomppars`; Christiansen et al. 2025; doi:10.26133/NEA13). The table gives one row per planet, with each
value picked from the best available publication. A row can therefore mix numbers from several papers. The
archive's documentation says so explicitly. Missing values are filled by explicit rules, and every rule that
fires is printed in the report; see [Data assumptions](data-assumptions.md).

All orbits are placed in one plane (*coplanar*), because the tilt between two planets' orbits is almost never
measured. Units are years, astronomical units (AU) and solar masses throughout the integrations.

## Step 2: uncertainties

Every published value has error bars. exostab runs the analysis once for the published ("nominal") values and
then again for many random *draws* within the error bars (20 by default). A result that only holds for the exact
published numbers is not trustworthy. The verdict of each indicator stands only if at least 95% of the draws agree
with the nominal one; otherwise it becomes **marginal**. An indicator is **inconclusive** if its nominal run is,
or if more than 20% of the draws are. With `--draws 0` nothing is tested against the uncertainties, so the
overall verdict is at most marginal.

## Indicator 1: Hill spacing

Around every planet there is a region, its *Hill sphere*, where the planet's gravity beats the star's tides. Its
radius is about a (m / 3M★)^(1/3), for a planet of mass m at distance a from a star of mass M★. For two planets
one uses the *mutual Hill radius*, R_H = ((m₁ + m₂) / 3M★)^(1/3) (a₁ + a₂)/2, and measures their separation
Δ = (a₂ − a₁)/R_H in these units (Chambers et al. 1996).

**Two planets.** Using a result of Marchal & Bozis (1982) for the three-body problem, Gladman (1993) showed that
two planets on circular orbits can *never* come close to each other if Δ is larger than about 2√3 ≈ 3.46. For
elongated (eccentric) orbits the limit grows. exostab uses the eccentric form of the criterion (as restated by
Veras & Armitage 2004 and Giuppone et al. 2013). Petit, Laskar & Boué (2018) showed that it can be written with the
angular momentum deficit; the two forms agree in exostab's tests.

**Three or more planets.** There is no such proof. Numerical experiments show that the time until the first close
encounter grows roughly exponentially with the spacing Δ (Chambers et al. 1996). Pu & Wu (2015) found that
Kepler-like systems need Δ ≈ 10 to survive a billion years with circular orbits, and more when the orbits are
eccentric: for the planets of a few Earth masses they simulated, about one more mutual Hill radius per 0.01 of
eccentricity dispersion. In general the extra spacing is 2.4 times the eccentricity divided by the *Hill
eccentricity* e_H = ((m₁ + m₂)/3M★)^(1/3) (their Eq. 15, with the coefficient of the erratum, Pu & Wu 2016).
exostab calls a multi-planet system *stable* by this indicator only if three conditions hold:

- every neighbouring pair has Δ ≥ 12;
- every neighbouring pair has Δ ≥ 10.2 + 2.4 e/e_H, where e is the larger eccentricity of the pair;
- no eccentricity is above 0.05, the largest eccentricity dispersion that Pu & Wu simulated. Comparing each
  planet's eccentricity with that dispersion is a conservative choice.

It calls the system *unstable* if any pair fails the two-planet criterion or has crossing orbits, and *marginal*
otherwise.

## Indicator 2: angular momentum deficit (AMD)

The *angular momentum deficit* measures how far a system is from having perfectly circular, flat orbits:

C = Σₖ Λₖ (1 − √(1 − eₖ²) cos iₖ),  with Λₖ = mₖ √(G M★ aₖ)

(Laskar & Petit 2017). Over long times the planets exchange AMD, making one orbit more elongated and another more
circular, but the total stays constant in the orbit-averaged ("secular") dynamics. So the question becomes: is
there enough AMD in the whole system for two neighbouring orbits to become elongated enough to cross? Laskar &
Petit (2017) computed the smallest AMD that allows crossing, the *critical AMD* C_c, for any pair. They defined
β = C / (Λ' C_c), where Λ' belongs to the outer planet of the pair. If β < 1 for every pair, collisions are
impossible in this approximation. The system is *strongly* AMD-stable if, in addition, the AMD cannot bring the
innermost planet to the star (β_S = C / Λ₁ < 1).

Mutual inclinations also add to the AMD, but they are almost never measured, and exostab places all orbits in one
plane. Like Laskar & Petit (2017) and Petit, Laskar & Boué (2017), it therefore assumes that the unknown
inclinations carry as much AMD as the eccentricities. This doubles the AMD computed from the eccentricities:
β = 2β_p, where β_p is the coplanar value. This is an assumption about the unknown inclinations, not a bound. The
report also gives the coplanar values, which are lower bounds for any inclinations.

Two refinements:

- Close pairs can become chaotic through overlapping *mean-motion resonances*, where the orbital periods are near
  simple ratios such as 3:2. This happens before their orbits cross. Petit, Laskar & Boué (2017) derived a smaller
  critical AMD for this case. They state that it applies only inside the 2:1 resonance (period ratio below 2), and
  they left out pairs whose combined mass exceeds about 0.8% of the star's (ε = (m + m')/M★ above 8.20 × 10⁻³).
  exostab uses it only within that domain, and the collision criterion elsewhere. Its mass limit is 8.11 × 10⁻³, the
  exact value of the paper's limit, which the paper computes from rounded constants (DECISIONS.md, D14). Below the
  paper's switching point (α ≤ α_R, with α = a/a') the paper itself uses the collision criterion, for any ε. A pair
  above the switching point but outside the stated domain is flagged: its β uses the collision criterion, and the AMD
  indicator never calls the system stable, because no published AMD criterion covers resonance overlap there. If the
  planets are so close that resonances overlap even for circular orbits, β is infinite (written as the string "inf"
  in `report.json`, which has no infinite numbers; NaN is written as null).
- For two planets, Petit, Laskar & Boué (2018) wrote the Hill criterion in AMD form. exostab uses it to tell
  "AMD-unstable but Hill stable" (marginal) from "neither" (unstable).

The AMD indicator says *stable* if the system is strongly AMD-stable with β = 2β_p and every pair lies in the
domain above. It says *unstable* only for two planets that are neither AMD-stable nor Hill stable even with the
coplanar AMD (β_p ≥ 1 and β_H,p ≥ 1), so the assumption about the inclinations never strengthens a claim of
instability. Everything else is *marginal*. A planet whose eccentricity is not measured gets e = 0 and adds no
AMD; the report then says that β and β_S are lower limits, and that an AMD-stable verdict holds only under that
assumption.

AMD instability does not mean the system will fall apart. The Solar System itself is AMD-unstable, because the giant
planets hold far more AMD than the orbits of the inner planets need to cross (Laskar & Petit 2017). It means only
that AMD conservation cannot rule collisions out.

## Indicator 3: direct N-body integration and MEGNO

The most direct test is to compute the orbits forward in time. exostab uses REBOUND (Rein & Liu 2012) with WHFast
(Rein & Tamayo 2015), a fast *symplectic* integrator. Symplectic integrators keep the energy error bounded, so
they can run for very long times. The time step is 1/30 of the shortest pericentre-passage time of any planet,
T_p = P (1 − e)^(3/2) / (1 + e)^(1/2): the time a planet takes to swing through its closest approach to the star.
For near-circular orbits this is 1/30 of the innermost period. Wisdom (2015) found T_p/20 adequate (as restated by
Hadden & Lithwick 2018). The nominal run is repeated with IAS15 (Rein & Spiegel 2015), an adaptive high-accuracy
integrator, as a check.

Surviving is not enough, because a chaotic system can survive for a while and then fall apart. exostab therefore
also computes the chaos indicator **MEGNO**, ⟨Y⟩ (Cincotta & Simó 2000; Cincotta, Giordano & Simó 2003), from
REBOUND's variational equations (Rein & Tamayo 2016). MEGNO tracks how fast two infinitely close copies of the
system drift apart. For regular (quasi-periodic) motion ⟨Y⟩ settles at 2; for chaotic motion it keeps growing.
exostab counts ⟨Y⟩ ≥ 2.2 as chaotic. This threshold is a judgment call. Published choices range from
|⟨Y⟩ − 2| ≤ 0.001 after 10⁵ years (Satyal, Quarles & Hinse 2013) and 2.01 (Maffione, Giordano & Cincotta 2011)
to ⟨Y⟩ ≳ 5 on the colour scales of Goździewski et al. (2015); see DECISIONS.md, D8.

Each run is classified as:

- **regular**: no close encounter or escape, and ⟨Y⟩ < 2.2;
- **chaotic**: no close encounter or escape, but ⟨Y⟩ ≥ 2.2;
- **unstable**: two planets came closer than the mean of their Hill radii, or a planet moved beyond 100 times
  the largest orbit;
- **inconclusive**: the relative energy error exceeded 10⁻⁵ at any of 1,200 equally spaced checks through the
  run, so the numbers cannot be trusted; or a planet came closer to the star than half its own Hill radius
  (a *star approach*), where tides, general relativity and the size of the star, none of which is modelled, can
  decide what happens.

Every run checks its energy error at the same 1,200 times: the nominal run, each Monte Carlo draw, the IAS15
check, and the runs of the catalog and of `exostab sweep`. The time series kept for the plots is a subset of these
checks, so it cannot change any result, and the command line, the web app and the catalog give the same verdicts
for the same inputs, run length, draws and seed. WHFast's energy error oscillates and peaks at pericentre
passages, so the error at the end of a run alone can be far below its maximum. A star approach is not a close
encounter between planets and does not stop the run; if two planets later meet, or a planet escapes, the run is
still unstable.

The N-body verdict follows the 95% rule of Step 2. It also cannot be *stable* if WHFast and IAS15 disagree on the
nominal run, or if the outermost planet completes fewer than 100 orbits within the run (increase `--orbits`).

By default each run lasts 10,000 orbits of the innermost planet. That is a short time compared with the age of a
planetary system, and exostab never claims more than "no instability found within this time". A configuration
that looks regular over 10,000 orbits can turn out to be chaotic over a longer run: the nominal TRAPPIST-1
configuration of the bundled snapshot gives ⟨Y⟩ = 2.17 over 10,000 orbits and 6.46 over 50,000
(`exostab check "TRAPPIST-1" --offline --orbits 50000 --draws 0`).

## Optional indicator 4: SPOCK

With `--spock`, exostab also asks SPOCK (Tamayo et al. 2020), a machine-learned classifier trained on compact
three-planet systems. It estimates, from a short integration, whether a system of three or more planets survives
a billion orbits of its innermost planet. Each set of parameters counts as stable if the estimate is at least 0.34,
the threshold that gave a 10% false-positive rate in the original paper. The estimate is not a calibrated
probability, and the current model (SPOCK 2.x) has no published threshold, so SPOCK can make the overall verdict
marginal but never unstable on its own.

The report warns when a planet's mass lies outside SPOCK's training range (10⁻⁷ to 10⁻⁴ of the star's mass), or
when neighbours are more than 30 mutual Hill radii apart as SPOCK's training set measured them. The code that
generated that training set uses R_H = a_i ((m_i + m_{i+1})/3M★)^(1/3), with the semi-major axis of the inner
planet; Tamayo et al. (2020, Eq. 1) print the formula without the 3. This radius differs from the one the Hill
indicator uses.

SPOCK currently needs REBOUND 4, so it cannot be installed next to exostab, which needs REBOUND 5. It is therefore
deliberately not a pip extra: it runs in a separate Python environment built by `scripts/make_spock_env.sh`, which
needs uv and a C compiler. Without a clone of the repository, download the script first:

```bash
curl -fsSLO https://raw.githubusercontent.com/mimitoz62/exostab/main/scripts/make_spock_env.sh
bash make_spock_env.sh
export EXOSTAB_SPOCK_PYTHON=~/.exostab-spock/bin/python
```

Running the script again rebuilds the environment.

## Step 3: the overall verdict

- **unstable**: the direct integration shows close encounters or escapes for the published values and for at
  least 95% of the draws; draws were run; none of the inputs is only a published upper limit; and the system has
  a single star;
- **inconclusive**: the N-body integrations could not be trusted;
- **stable**: every indicator says stable (SPOCK too, when it is enabled), draws were run, and no N-body draw had
  a close encounter or escape;
- **marginal**: everything else, in particular whenever the indicators disagree.

Some of these conditions need a word of explanation:

- **Upper limits.** When the archive publishes only an upper limit for a mass or an eccentricity, the nominal run
  uses the limit and the draws are uniform below it. For Hill spacing and the integration, the limit is normally the
  hardest case. For AMD a mass limit need not be: β_S = C / Λ₁ grows as the innermost planet gets lighter. A stable
  result therefore describes the values that were run, not every value below a mass limit. exostab calls BD-06 1339
  stable with the archive's limit of 1,523 Earth masses for planet b (β_S = 0.011). In a run with a YAML file, not a
  catalog result, the planet's m sin i of 8.5 Earth masses gives β_S = 1.96, so AMD and the overall verdict are
  marginal. An instability found with limits only constrains the limited values. The archive's masses of the four
  planets of HD 215152, for example, are upper limits of 469 to 975 Earth masses, for orbital periods of 6 to
  25 days. The overall verdict is then marginal, and the report names the limits.
- **No draws.** With `--draws 0` the verdict is at most marginal, whichever way the nominal run points.
- **A close encounter among the draws.** The 95% rule lets an indicator stay stable with 1 failing draw in 20.
  A close encounter within the published uncertainties is direct evidence of instability, so it still blocks an
  overall stable verdict. Chaotic draws, and draws that fail the analytic criteria, are listed in the summary but
  do not block it.
- **Several stars.** Only the host star is modelled. In a system with more than one star the planets may orbit
  different stars, or a companion may change their orbits, so an N-body instability gives marginal, not unstable.

The summary is built from the draw counts and names the reason for the verdict. A typical *marginal* case is a
system in a resonance, such as GJ 876: the analytic criteria fail, but the integration shows regular motion. The
report explains which indicators disagree and why.

## References

- Chambers, J. E., Wetherill, G. W. & Boss, A. P. 1996, Icarus 119, 261, doi:10.1006/icar.1996.0019
- Christiansen, J. L., et al. 2025, PSJ 6, 186, doi:10.3847/psj/ade3c2
- Cincotta, P. M. & Simó, C. 2000, A&AS 147, 205, doi:10.1051/aas:2000108
- Cincotta, P. M., Giordano, C. M. & Simó, C. 2003, Physica D 182, 151, doi:10.1016/s0167-2789(03)00103-9
- Giuppone, C. A., Morais, M. H. M. & Correia, A. C. M. 2013, MNRAS 436, 3547, doi:10.1093/mnras/stt1831
- Gladman, B. 1993, Icarus 106, 247, doi:10.1006/icar.1993.1169
- Goździewski, K., Migaszewski, C., Panichi, F. & Szuszkiewicz, E. 2015, MNRAS 455, L104,
  doi:10.1093/mnrasl/slv156
- Hadden, S. & Lithwick, Y. 2018, AJ 156, 95, doi:10.3847/1538-3881/aad32c
- Laskar, J. & Petit, A. C. 2017, A&A 605, A72, doi:10.1051/0004-6361/201630022
- Maffione, N. P., Giordano, C. M. & Cincotta, P. M. 2011, International Journal of Non-Linear Mechanics 46, 23,
  doi:10.1016/j.ijnonlinmec.2010.06.008
- Marchal, C. & Bozis, G. 1982, Celestial Mechanics 26, 311, doi:10.1007/bf01230725
- Petit, A. C., Laskar, J. & Boué, G. 2017, A&A 607, A35, doi:10.1051/0004-6361/201731196
- Petit, A. C., Laskar, J. & Boué, G. 2018, A&A 617, A93, doi:10.1051/0004-6361/201833088
- Pu, B. & Wu, Y. 2015, ApJ 807, 44, doi:10.1088/0004-637x/807/1/44
- Pu, B. & Wu, Y. 2016, ApJ 819, 170 (erratum to Pu & Wu 2015), doi:10.3847/0004-637x/819/2/170
- Rein, H. & Liu, S.-F. 2012, A&A 537, A128, doi:10.1051/0004-6361/201118085
- Rein, H. & Spiegel, D. S. 2015, MNRAS 446, 1424, doi:10.1093/mnras/stu2164
- Rein, H. & Tamayo, D. 2015, MNRAS 452, 376, doi:10.1093/mnras/stv1257
- Rein, H. & Tamayo, D. 2016, MNRAS 459, 2275, doi:10.1093/mnras/stw644
- Satyal, S., Quarles, B. & Hinse, T. C. 2013, MNRAS 433, 2215, doi:10.1093/mnras/stt888
- Tamayo, D., Cranmer, M., Hadden, S., Rein, H., et al. 2020, PNAS 117, 18194, doi:10.1073/pnas.2001258117
- Veras, D. & Armitage, P. J. 2004, Icarus 172, 349, doi:10.1016/j.icarus.2004.06.012
- Wisdom, J. 2015, AJ 150, 127, doi:10.1088/0004-6256/150/4/127
