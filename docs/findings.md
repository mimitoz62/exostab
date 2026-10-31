---
description: >-
  What exostab's catalog of 26 October 2026 shows: 619 of 1,044 checked multi-planet systems are called stable,
  512 of them with every eccentricity assumed 0, and 6 published parameter sets do not survive integration.
---

# What the catalog shows

Every week, exostab checks each multi-planet system in the NASA Exoplanet Archive's composite table with three
indicators: Hill spacing, the angular momentum deficit (AMD) and N-body integration with MEGNO
([Methods](methods.md)). Each system it can model gets a verdict: stable, marginal, unstable or inconclusive.

This page describes one of those catalogs: the one of **26 October 2026**, computed with exostab 1.0.0 from that
day's table (Christiansen et al. 2025; doi:10.26133/NEA13). Every system had the same settings: 10,000 orbits of the
innermost planet, 10 draws within the published uncertainties and seed 0. The [catalog page](catalog.md) shows the
newest weekly catalog, so its counts can differ from the ones here. The commands behind the numbers are under
[How to reproduce](#how-to-reproduce).

The main results:

- **Verdicts.** Of the 1,079 systems, 1,044 could be checked and 35 are skipped, each with a reason. Of the checked
  systems, 619 are stable (59.3%), 413 marginal (39.6%), 6 unstable and 6 inconclusive.
- **Planet count.** The stable share falls from 71.8% of 2-planet systems to 43.4% of 3, 25.3% of 4, 3.4% of 5 and
  0 of 14 with 6 to 8 planets.
- **Inputs.** 512 of the 619 stable verdicts have every eccentricity assumed 0, and 415 of those also have every
  mass estimated from the radius. 28 use published values for every eccentricity, true mass and orbital phase.
- **Integration.** Six published parameter sets do not survive integration: the run with the published values and
  10 of 10 draws have a close encounter or escape. That is a statement about the parameter sets, not a prediction for
  the planets.
- **Upper limits.** A run of HD 215152 with the mass upper limits of the composite table has close encounters or
  escapes in 10 of 10 draws. In a what-if run with its published minimum masses, all 10 draws are regular.
- **Firmness.** Across three local rebuilds with different seeds, 50 of the 1,044 verdicts (4.8%) change.

Any verdict can be opened up. `exostab check "Kepler-36" --draws 10` runs one system with the catalog's settings and
shows the values used, the completion rules and the reasons for its verdict ([Quickstart](quickstart.md)).

## More planets, fewer stable verdicts

The share of checked systems called stable falls with every added planet.

![Two charts. Left: stacked bars of the overall verdicts by number of planets. The stable share is 71.8% of 699 two-planet systems, 43.4% of 219 three-planet systems, 25.3% of 83 four-planet systems, 3.4% of 29 five-planet systems and 0 of 14 systems with 6 to 8 planets; nearly all the others are marginal. Right: lines of the share each indicator calls stable for 2, 3 and 4 or more planets. Hill falls from 86.0% to 43.4% and 18.3%, AMD from 75.3% to 68.5% and 46.8%, and N-body from 79.4% to 69.4% and 51.6%.](assets/findings/verdicts-by-planet-count.png)

**Figure 1.** Left: overall verdict by number of planets, for the 1,044 checked systems of the catalog of
26 October 2026. Right: the share of those systems that each indicator calls stable. Each system has 10,000 orbits
of the innermost planet, 10 draws and coplanar orbits, with gaps filled by written rules. From three planets up, the
Hill indicator uses a stricter rule, so part of the drop from 2 to 3 planets comes from the rule. Marginal does not
mean unstable. These are verdicts under one set of settings, not a census of which systems are stable.

| Planets | Checked | Stable | Marginal | Unstable | Inconclusive | Stable share |
|---|---|---|---|---|---|---|
| 2 | 699 | 502 | 188 | 5 | 4 | 71.8% |
| 3 | 219 | 95 | 122 | 1 | 1 | 43.4% |
| 4 | 83 | 21 | 62 | 0 | 0 | 25.3% |
| 5 | 29 | 1 | 28 | 0 | 0 | 3.4% |
| 6 to 8 | 14 | 0 | 13 | 0 | 1 | 0 of 14 |

Part of the drop from 2 to 3 planets comes from a stricter rule. For two planets, the Hill indicator uses the
criterion of Gladman (1993). From three planets up, exostab's rule, based on Pu & Wu (2015), asks for at least 12
mutual Hill radii between neighbours, more if the orbits are eccentric, and no eccentricity above 0.05; see
[Methods](methods.md#indicator-1-hill-spacing).
Between 2 and 3 planets the Hill share falls from 86.0% to 43.4%, while the AMD share falls from 75.3% to 68.5% and
the N-body share from 79.4% to 69.4%. Among the 3-planet systems the Hill rule sets the count: the 95 systems it
calls stable are exactly the 95 that are stable overall. The two-planet criterion alone, applied to every pair with
the nominal values, would pass 92.4% of the 2-planet systems and 89.0% of the 3-planet systems.

Kepler-292 is the only stable system with five or more planets. That verdict rests on every eccentricity assumed 0
and every mass estimated from the radius.

## What the stable verdicts rest on

Of the 1,044 checked systems, 619 are called stable. Most of those verdicts rest on values that were assumed or
estimated:

- 512 have every eccentricity assumed 0. Of these, 415 also have every mass estimated from the radius, and 97 do
  not.
- 79 have at least one eccentricity that is not assumed, with other inputs assumed, minimum masses or upper limits.
  That eccentricity is a published value in 68 of them, and only upper limits in 11.
- 28 use published values for every eccentricity, true mass and phase, with no upper limit. Of these, 22 also have
  every argument of periastron published and a single star.

![Two charts. Left: bars of the 619 stable verdicts by what they rest on: 415 with every eccentricity assumed 0 and every mass estimated from the radius, 97 with every eccentricity assumed 0 and some masses not estimated from the radius, 79 with some eccentricities not assumed and other inputs assumed, minimum masses or limits, and 28 with published values for every eccentricity, true mass and phase. Right: the share of checked systems called stable, with every eccentricity assumed 0 against at least one not assumed: 98.3% against 35.4% for 2 planets, 70.5% against 2.3% for 3 planets, and 41.2% against 1.3% for 4 or more planets.](assets/findings/what-stable-rests-on.png)

**Figure 2.** Left: what the 619 stable verdicts of the catalog of 26 October 2026 rest on. Right: the share of
checked systems called stable, with every eccentricity assumed 0 and with at least one not assumed (a published value
or limit). "Assumed 0" includes an eccentricity published as exactly 0 without an uncertainty; e is the
eccentricity. The gap on the right has two sources: different kinds of system, and the value of e that enters the
tests (see the text below). Stable means no sign of instability under these settings, not a proof.

An eccentricity published as exactly 0 without an uncertainty counts as assumed: exostab treats it as a circular orbit
fixed in the source's fit, not as a measurement ([Data and assumptions](data-assumptions.md#completion-rules)). With
every eccentricity at 0 the AMD indicator has little to test. Its coefficient β is 0 in 585 of the 588 checked systems
with every eccentricity assumed, and the report says that an AMD-stable verdict then holds only under that assumption.

Seen from the other side, 82 of the 1,044 checked systems (7.9%) have published values for every eccentricity, true
mass and phase, with no upper limit. Of these, 28 are stable, 54 marginal and 0 unstable.

With every eccentricity assumed, 512 of 588 systems are stable (87.1%); with at least one not assumed, 107 of 456 are
(23.5%), and leaving out the 29 with nothing but upper limits, 96 of 427 are (22.5%). That gap in Figure 2 has two
sources.

The first source is that these are different kinds of system. In the first group, every planet was found by transit
in 93.5% of the systems and by radial velocity in 2.4%, and 74.0% have every mass estimated from the radius. In the
second group these shares are 32.0%, 43.4% and 5.5%.

The second source is the value of e, which enters the tests: with every e at 0, AMD passes in 579 of the 588 systems of
the first group. The gap stays within one kind of system. Where every planet was found by transit, the stable share is
88.4% against 26.0% (486 of 550 and 38 of 146), and if no mass is estimated either, 73.6% against 33.6% (53 of 72 and
36 of 107). Where every planet was found by radial velocity, it is 78.6% against 22.7% (11 of 14 and 45 of 198).

What-if runs, not catalog results, change only the eccentricities and keep the catalog's code and settings. With every
e of the second group removed, so that it is assumed 0, 266 of its 456 systems are stable (58.3%). That closes 55% of
the gap. AMD then calls 428 of them stable instead of 156, Hill spacing 343 instead of 199 and N-body 334 instead of
205. In the other direction, e = 0.05 on every planet of the first group leaves 442 of its 588 systems stable, all of
them stable in the catalog. With e = 0.1, 322 stay stable, none with three or more planets, because the Hill rule for
those systems allows no eccentricity above 0.05.

The figure does not show that measuring an eccentricity makes a system less stable. It shows how much of the stable
count rests on an assumption.

## Published parameter sets that do not survive integration

Six published parameter sets get the overall verdict unstable. That verdict needs close encounters or escapes in the
nominal run, which uses the published values, and in at least 95% of the draws (with 10 draws, in all of them), no input
that is only an upper limit, and a single star ([Methods](methods.md#step-3-the-overall-verdict)).

| Published parameter set | Planets | Draws with a close encounter or escape | Smallest spacing (mutual Hill radii) | Nominal encounter after, WHFast / IAS15 (yr) | Nominal orbits meet |
|---|---|---|---|---|---|
| BD+20 2457 | 2 | 10 of 10 | 2.09 | 5.27 / 5.27 | no |
| HD 81817 | 2 | 10 of 10 | 2.17 | 6.27 / 6.28 | no |
| HD 5319 | 2 | 10 of 10 | 2.41 | 86.5 / 61.3 | yes |
| HD 99706 (two publications) | 2 | 10 of 10 | 2.43 | 181 / 234 | yes |
| HD 200964 | 2 | 10 of 10 | 2.62 | 23.3 / 23.3 | yes |
| HD 153557 | 3 | 10 of 10 | 8.88 | 0.467 / 0.467 | yes |

The catalog does not store encounter times, so that column comes from a local rerun with the same settings (macOS,
REBOUND 5.2.0), with both of exostab's integrators. Encounter times in a chaotic run can depend on floating-point
rounding ([Validation](validation.md)), and the two integrators differ for HD 5319 and HD 99706, so read them as rough
values.

The last column tests the nominal ellipses of neighbouring planets, in one plane, with the published arguments of
periastron. In HD 5319 they only just meet, by 0.007 AU. exostab's own test of a pair is weaker: it compares the
apastron of the inner orbit with the periastron of the outer one, whatever the directions of the two. These radial
ranges also overlap in BD+20 2457, although with the published ω its ellipses do not meet.

Each row says that this published parameter set does not survive integration with exostab's settings. It does not
describe what the real planets do. A real system can still be fine, for these reasons:

- **Independent Keplerian fits.** A fit of independent Keplerian orbits ignores the pull between the planets, so
  orbits that fit the data may not last. The composite table can also combine publications: in HD 99706, planet b
  comes from Luhn et al. (2019) and planet c from Bryan et al. (2016). The run uses the stellar mass of 1.46 solar
  masses from the first; the fit for planet c used 1.72.
- **Coplanar orbits.** exostab places all orbits in one plane. For an earlier orbital solution of HD 5319, Kane (2016)
  found that coplanar orbits destabilise rapidly and that specific mutual inclinations allow stable configurations
  over long timescales.
- **Resonance not represented.** A mean-motion resonance can protect crossing orbits, but only with the right periods
  and phases. For an earlier orbital solution of HD 200964, Wittenmyer et al. (2012) conclude that the planets are
  feasible only if trapped in a 4:3 resonance, on orbits inside narrow islands of stability. The catalog's values, from
  Luhn et al. (2019), have a period ratio of 1.406, away from 4:3.

Minimum masses are not such a reason. Every one of these runs uses m sin i as the mass of at least one body, but
m sin i is the low end of each mass, and larger true masses shrink the spacing. In what-if runs, not catalog results,
with every m sin i divided by sin 60° or by sin 30°, all six stay overall unstable, with close encounters or escapes
in 10 of 10 draws. What m sin i leaves open is the orientation of the orbits, which the point on coplanar orbits
covers.

Two more studies bear on these rows. For BD+20 2457, whose composite values come from the discovery paper (Niedzielski
et al. 2009), Horner et al. (2014) find strong instability on short timescales across a wide range of plausible
values, and suggest that any massive companions must move on orbits significantly different from those of the discovery
work. For HD 81817, Bang et al. (2020) attribute the 627.4-day signal to stellar activity and only the 1047.1-day
signal to a companion. The composite table lists two companions, both from Feng et al. (2022), who argue against that
diagnosis and for a Keplerian origin of the shorter signal, so the two papers disagree. This page gives no cause for
HD 99706 and HD 153557.

## Where stability runs point to the table, not to dynamics

Some runs say more about a value in the table than about the planets. When the composite table gives only an upper
limit for a mass, the nominal run uses the limit and the draws lie below it. An instability found this way only
constrains the limited values, so the overall verdict is marginal, not unstable
([Methods](methods.md#step-3-the-overall-verdict)).

HD 215152 is an example. Its four planets have periods of 5.76 to 25.2 days. The composite table gives them masses of
469 to 975 Earth masses, marked as upper limits, from Kiefer et al. (2021), who constrain true masses with Gaia
astrometry. The archive's Planetary Systems table (`ps`) also holds the minimum masses of Delisle et al. (2018): m sin i
of 1.72 to 2.88 Earth masses. Both can be correct, because a true mass can lie below the limit and above m sin i. The
catalog runs the composite table's values, so it tests the limits.

| HD 215152 | Catalog: composite upper limits | What-if, not a catalog result: m sin i |
|---|---|---|
| Masses (Earth masses) | 469 to 975 | 1.72 to 2.88 |
| Draws: regular / chaotic / close encounter or escape | 0 / 0 / 10 | 10 / 0 / 0 |
| Hill | unstable | marginal |
| AMD | marginal | stable |
| N-body | unstable | stable |
| Overall | marginal | marginal |

The what-if run is a local run (macOS, REBOUND 5.2.0) with the catalog's code and settings, and with only the four
masses replaced. It is not a catalog result, and m sin i is not the true mass either. It shows that the close
encounters come from the limit values, so here the runs point to the table, not to the dynamics of the planets.

Mass upper limits enter 90 of the 1,044 checked systems. Kiefer et al. (2021) are the source of the limits for 21
planets on 10 hosts.

## How firm these numbers are

The three catalogs computed with exostab 1.0.0, those of 16, 19 and 26 October 2026, are identical in every verdict and
number across all 1,079 rows. Only the download date and the run times differ. They are identical because the seed and
the values that enter the runs did not change. That shows determinism, not robustness.

To see how much depends on the draws, the catalog was rebuilt locally three times, with seeds 0, 1 and 2:

| Verdict | Seed 0 | Seed 1 | Seed 2 |
|---|---|---|---|
| Stable | 620 | 609 | 610 |
| Marginal | 412 | 420 | 421 |
| Unstable | 6 | 13 | 10 |
| Inconclusive | 6 | 2 | 3 |

- 50 of the 1,044 verdicts (4.8%) differ among the three seeds: 36 between stable and marginal, 10 between marginal and
  unstable and 4 between marginal and inconclusive.
- 595 of the 619 published stable verdicts hold in all three. Of the 28 stable verdicts with published inputs, 23 do.
- Five of the six unstable verdicts hold in all three. HD 99706 is marginal with seed 2. An unstable verdict needs all
  10 draws, so one draw can move a verdict between marginal and unstable.
- The pattern by planet count holds: the stable share is 72.0%, 71.0% and 70.8% for 2 planets and 43.4%, 42.5% and
  43.4% for 3.
- Verdicts differ for 7 of the 588 systems with every eccentricity assumed (1.2%), 43 of the 456 with at least one not
  assumed (9.4%) and 19 of the 135 with a random phase (14.1%). An assumed e = 0 is held fixed in every draw, so
  those verdicts have less to vary. That says nothing about the assumption itself.
- The same seed, 0, on another platform and REBOUND version changes 3 of the 1,044 verdicts (HD 12661, HD 169830 and
  TOI-776). The REBOUND version is not the reason: on macOS, seed 0 gives the same verdicts and numbers in every row
  with REBOUND 5.2.0 and 5.2.2.

These rebuilds were local (macOS, REBOUND 5.2.0), with an archive table that reproduces the catalog's Hill and AMD
numbers, while the published catalog comes from continuous integration (Linux, REBOUND 5.2.2). Only three seeds were
run, with 10 draws each, so these numbers show the size of the effect, not a precise rate. They cannot be computed from
the published catalog and the archive table alone, because the rebuilt catalogs are not published; the commands that
make them are under [How to reproduce](#how-to-reproduce).

## What "stable" means here and what it does not

Stable means that every indicator says stable under these settings and that no draw had a close encounter or escape.
It is not a proof:

- **The horizon is finite.** Each run lasts 10,000 orbits of the innermost planet. The median is 169 years, and the 10
  to 90% range is 47 to 2,055 years. That is short compared with the age of a planetary system.
- **Orbits are coplanar.** All orbits lie in one plane, because the angles between them are almost never measured.
- **The inputs are the ones above.** Most stable verdicts rest on assumed eccentricities.

Kepler-36 shows what this can hide. The catalog calls it stable: 10 of 10 draws are regular over 380 years. Its planets
have the smallest spacing of any stable system, 4.75 mutual Hill radii, and both have e = 0, listed without an
uncertainty from Vissapragada et al. (2020). That paper fixes e = 0 only in its light-curve fit; its dynamical fit gives
eccentricity-vector components of up to about 0.05. Deck et al. (2012) integrated initial conditions consistent with
the observations and found the orbits "chaotic with a Lyapunov time of only ~10 years". Only about 4.5% of their sample
showed no large-scale instabilities over about 200 million years. In a what-if run, not a catalog result, with the
upper limits of Carter et al. (2012) from the `ps` table (e = 0.039 and 0.033) and seed 0, the verdict is marginal, with
8 regular and 2 chaotic draws, and the nominal run ends in a close encounter after 0.05 years. ω is drawn at random, so
the details depend on the seed: seed 1 gives 9 regular and 1 chaotic draw, with the encounter after 30 years, and seed 2
gives 6 and 4, with a nominal run that completes and is chaotic. All three are marginal. So the stable verdict holds
with e = 0 and not at those limits.

Marginal means that exostab cannot call the system stable under these settings: the indicators disagree, draws within
the uncertainties behave differently, or the run is too short for the outer planets. It does not mean that a system is
falling apart. TRAPPIST-1 (7 planets; 9 regular and 1 chaotic draw) and Kepler-90 (8 planets, listed in the archive's
table as KOI-351; 10 regular draws) are both marginal in this catalog. In 153 of the 413 marginal systems the N-body
verdict is stable, and Hill or AMD, which can fail for a system that stays regular over the run, is not. In 89 more, all
10 draws are regular but the outermost planet completes fewer than 100 orbits, so the N-body verdict cannot be stable.

## How to reproduce

```bash
git clone https://github.com/mimitoz62/exostab
cd exostab
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
git show origin/catalog-data:archive/catalog-2026-10-26.csv > oct26.csv
python scripts/catalog_findings.py oct26.csv --out findings
```

[`scripts/catalog_findings.py`](https://github.com/mimitoz62/exostab/blob/main/scripts/catalog_findings.py) prints the
numbers of this page and draws the two figures, in about 20 seconds. Only the comparison with other catalogs and the
what-if runs with other eccentricities need more (below).

The catalog names the completion rules of each system but not the planets they apply to, so the script recomputes what
each verdict rests on from the archive table: the cached copy, or a download if there is none (`--refresh` downloads it
again). Its first lines say how many catalog rows that table reproduces. With the table of 31 October 2026, all 1,044
checked systems keep their Hill and AMD verdicts and numbers, and all 35 skipped systems keep their reason. With a later
table some rows may not reproduce, and the numbers about inputs then describe that table.

The script also repeats the runs of the six unstable systems and makes the what-if runs, with values from the `ps`
table and with larger minimum masses. These runs are local, and chaotic runs can differ on other machines
([Validation](validation.md)).

The comparison of the weekly catalogs and the numbers of the local rebuilds need those catalogs. The rebuilds are not
published, so these commands make them first. A rebuild took about 13 minutes with 8 worker processes on an Apple
M4 Pro.

```bash
git show origin/catalog-data:archive/catalog-2026-10-16.csv > oct16.csv
git show origin/catalog-data:archive/catalog-2026-10-19.csv > oct19.csv
for seed in 0 1 2; do
  exostab catalog build --out seed$seed --seed $seed \
    --orbits 10000 --draws 10 --max-seconds 300
done
python scripts/catalog_findings.py oct26.csv --out findings \
  --earlier oct16.csv oct19.csv \
  --rebuilds seed0/catalog.csv seed1/catalog.csv seed2/catalog.csv
```

To compare REBOUND versions, install the other version in a second environment, build seed 0 again and give the script
the two catalogs, one of them through `--earlier`. It prints the columns that differ.

The what-if runs with other eccentricities repeat each system with its new values: once for the systems with at least
one eccentricity not assumed, and twice for the others. Add `--eccentricity-what-if`; `--jobs` sets the number of worker
processes. They took about 14 minutes with 11 worker processes on the same computer.

The numbers on this page were produced on 2026-10-31 with exostab 1.0.1.dev0, whose check code is that of 1.0.0, and
with REBOUND 5.2.0, NumPy 2.5.3 and Python 3.12.11 on macOS (Apple M4 Pro). The verdicts and draw counts are those of
the published catalog (Linux, REBOUND 5.2.2).

> This research has made use of the NASA Exoplanet Archive, which is operated by the California Institute of
> Technology, under contract with the National Aeronautics and Space Administration under the Exoplanet
> Exploration Program.

## References

- Bang, T.-Y., Lee, B.-C., Perdelwitz, V., et al. 2020, A&A 638, A148, doi:10.1051/0004-6361/201936613
- Bryan, M. L., Knutson, H. A., Howard, A. W., et al. 2016, ApJ 821, 89, doi:10.3847/0004-637x/821/2/89
- Carter, J. A., Agol, E., Chaplin, W. J., et al. 2012, Science 337, 556, doi:10.1126/science.1223269
- Christiansen, J. L., et al. 2025, PSJ 6, 186, doi:10.3847/psj/ade3c2
- Deck, K. M., Holman, M. J., Agol, E., et al. 2012, ApJ 755, L21, doi:10.1088/2041-8205/755/1/l21
- Delisle, J.-B., Ségransan, D., Dumusque, X., et al. 2018, A&A 614, A133, doi:10.1051/0004-6361/201732529
- Feng, F., Butler, R. P., Vogt, S. S., et al. 2022, ApJS 262, 21, doi:10.3847/1538-4365/ac7e57
- Gladman, B. 1993, Icarus 106, 247, doi:10.1006/icar.1993.1169
- Horner, J., Wittenmyer, R. A., Hinse, T. C. & Marshall, J. P. 2014, MNRAS 439, 1176, doi:10.1093/mnras/stu081
- Kane, S. R. 2016, ApJ 830, 105, doi:10.3847/0004-637x/830/2/105
- Kiefer, F., Hébrard, G., Lecavelier des Etangs, A., et al. 2021, A&A 645, A7, doi:10.1051/0004-6361/202039168
- Luhn, J. K., Bastien, F. A., Wright, J. T., et al. 2019, AJ 157, 149, doi:10.3847/1538-3881/aaf5d0
- Niedzielski, A., Nowak, G., Adamów, M. & Wolszczan, A. 2009, ApJ 707, 768, doi:10.1088/0004-637x/707/1/768
- Pu, B. & Wu, Y. 2015, ApJ 807, 44, doi:10.1088/0004-637x/807/1/44
- Vissapragada, S., Jontof-Hutter, D., Shporer, A., et al. 2020, AJ 159, 108, doi:10.3847/1538-3881/ab65c8
- Wittenmyer, R. A., Horner, J. & Tinney, C. G. 2012, ApJ 761, 165, doi:10.1088/0004-637x/761/2/165
