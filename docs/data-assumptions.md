---
title: "Data and assumptions: archive values and completion rules"
description: >-
  Where exostab's parameters come from and how gaps are filled: the NASA Exoplanet Archive's composite table, the
  completion rules, orbital phases, Monte Carlo draws and YAML input.
---

# Data and assumptions

## Source

Parameters come from the NASA Exoplanet Archive's **Planetary Systems Composite Parameters** table (`pscomppars`,
doi:[10.26133/NEA13](https://doi.org/10.26133/NEA13)), queried through its Table Access Protocol (TAP) service with
astroquery. exostab downloads all planets in systems with two or more planets (`sy_pnum >= 2`, about 2,700 rows)
once, stores them in your user cache folder, and reuses the copy until you pass `--refresh`. The copy is written
atomically and its row count and checksum are checked when it is read, so an interrupted download cannot leave a
truncated table behind. Every report records:

- the table name and service URL;
- when the table was downloaded (`data.retrieved_utc` in `report.json`);
- the archive row of every planet (`pl_name`);
- the publication behind every value (`reference`, `reference_url`).

`--offline` (or `EXOSTAB_OFFLINE=1`) uses the snapshot of 22 well-known systems bundled with the package. The
snapshot is also used, with a warning in the report, if the archive cannot be reached and there is no cache. A
system that is missing from the snapshot is then reported as missing from the snapshot, not from the archive.

> This research has made use of the NASA Exoplanet Archive, which is operated by the California Institute of
> Technology, under contract with the National Aeronautics and Space Administration under the Exoplanet
> Exploration Program.

Please also cite Christiansen et al. (2025, PSJ 6, 186) and the table DOI with the access date, and the
publications behind the values you use. Their references are in `report.json`.

### A caution about the composite table

The archive picks each parameter of a planet separately: the value from the planet's default publication if it
exists, otherwise the most precise one. One row can therefore combine a period from one paper, an eccentricity from
another and a transit time from a third. The archive's documentation calls the table "not necessarily
self-consistent". This matters most for orbital phases (below).

The same holds for the host star: every planet row carries its own stellar mass, and the rows of one host can
disagree. In the table of 2026-10-31, 200 of the 1,079 hosts have rows with different stellar masses, 61 of them by
more than 10%. A measured planet mass scales with the stellar mass its publication assumed, so exostab uses the
stellar mass of the publication that gives more of the measured planet masses than any other, if a row gives that
publication's value (47 of the 198 of these hosts that can be modelled). Otherwise it uses the median of the rows;
for an even number of rows whose two middle values differ, it uses the lower one, because a smaller star gives larger
planet-to-star mass ratios and is the less stable choice. The result does not depend on the order in which the archive
returns the rows. The flag `star_mass_inconsistent` lists every value with its reference and says which rule chose the
value.
Planet masses that a publication derived with a different stellar mass are not rescaled. Limits on the stellar
mass are not used.

## Completion rules

Every rule that fires adds a line to the report card and an entry to `system.flags` in `report.json`. The table
lists every flag exostab can set.

| Missing or special value | What exostab does | Flag |
|---|---|---|
| Eccentricity | 0, labelled "assumed" | `eccentricity_assumed_zero` |
| Eccentricity published as exactly 0 without an uncertainty | treated like a missing eccentricity: such a value is a circular orbit fixed in the source's fit, not a measurement; 0 in every run, labelled "assumed" | `eccentricity_fixed_zero_by_source` |
| Eccentricity or planet mass given as an upper limit | the nominal run uses the limit (normally the hardest case, though a mass limit need not be for AMD: see [Methods](methods.md#step-3-the-overall-verdict)); draws are uniform between 0 and the limit. These draws do not sample a measurement uncertainty, so an N-body instability that rests on them gives an overall "marginal", never "unstable". Upper limits on other values are not accepted | `eccentricity_upper_limit`, `mass_upper_limit` |
| Eccentricity given as a lower limit | the limit is used as the value | `eccentricity_lower_limit` |
| Period given as a limit | the limit is used as the value | `period_upper_limit`, `period_lower_limit` |
| Argument of periastron ω | drawn uniformly in [0°, 360°) for every run | `omega_randomized` |
| Longitude of the ascending node Ω | not used: in a coplanar system only ϖ = Ω + ω matters, and randomizing ω covers it | (part of `coplanar_assumed`) |
| Inclinations | all orbits in one plane; sky-plane inclinations do not give the angles between orbits | `coplanar_assumed` |
| Mass is m sin i (`pl_bmassprov = Msini`) of a non-transiting planet, or a lower limit on the mass of a non-transiting planet | used as the mass (sin i = 1); `--inclination-prior isotropic` draws one inclination per draw (cos i uniform, sin i ≥ 0.1) and divides the minimum masses by sin i | `minimum_mass`, `mass_lower_limit` |
| Mass is m sin i of a transiting planet | used as the true mass (sin i is close to 1), not scaled by the inclination prior | `msini_of_transiting_planet` |
| Other mass lower limit | the limit is used as the value | `mass_lower_limit` |
| Mass computed by the archive from m sin i and a measured inclination | used as the true mass | `mass_from_msini_and_inclination` |
| Mass estimated by the archive from the radius | used, labelled "estimated" | `mass_estimated_by_archive` |
| The archive's label for a mass (`pl_bmassprov`) is missing or not one exostab knows | used as a true mass | `mass_kind_unknown` |
| Mass marked `mass_kind: estimated` in a YAML file | used, labelled "estimated" | `mass_estimated_in_file` |
| No mass at all, radius known | Chen & Kipping (2017) relation, for radii up to 11.3 R⊕; refused above, where the relation gives no unique mass | `mass_from_radius_chen_kipping` |
| No period, semi-major axis known | Kepler's third law, except for planets found by microlensing or direct imaging (see the last row) | `period_from_semimajor_axis` |
| Planet rows give different stellar masses | the rule above | `star_mass_inconsistent` |
| Some rows give only a limit on the stellar mass | not used; the measured value of the other rows is used | `star_mass_limit_ignored` |
| Several stars in the system | only the host star is modelled; an N-body instability then gives an overall "marginal", because the planets may orbit different stars or a companion may change their orbits | `companion_stars_ignored` |
| Planet flagged controversial | kept, flagged | `controversial_planet` |
| Orbital phase | from a transit, conjunction or periastron time, or drawn at random (below) | `phase_from_transit`, `phase_from_conjunction`, `phase_from_periastron`, `phase_randomized` |
| Reference time so far from the common epoch that the propagated uncertainty of the phase is above one full turn | used, with the numbers unchanged; in the draws the phase is effectively random | `phase_uncertain_at_epoch` |
| A single-star host has fewer rows than the archive's count of its planets (`sy_pnum`) | the rows there are, are used. If more than 1% of such hosts lack rows, the archive's answer counts as cut and does not replace the cache | `planet_rows_missing` |
| Value changed in the web app | used as edited; listed in the report. The flags about the value it replaces no longer apply and are dropped, except that a minimum mass stays one | `edited_in_web_app`, `what_if_in_web_app` |
| Argument of periastron cleared in the web app for a planet whose phase comes from a time of periastron | the planet's longitude is random in every run | `phase_random_without_omega` |
| Circumbinary planets; a planet with no mass and no radius, or only a radius above 11.3 R⊕; no period and no semi-major axis; no period for a planet found by microlensing or direct imaging (the archive's `pl_orbsmax` is then "the projected separation in the plane of the sky", which gives neither the orbit nor the spacing of the planets); a published eccentricity above 0.95; no stellar mass, or only a limit on it; only one planet row for the host (its other planets orbit a companion star) | the system is rejected with the reason | — |

On the table of 2026-10-31, 1,044 of the 1,079 hosts with `sy_pnum >= 2` can be modelled. The 35 rejected hosts
are 11 microlensing or imaging systems without a period, 10 with a single planet row, 8 circumbinary systems, 5
with a planet that has neither a mass nor a usable radius and 1 without a stellar mass.

### Orbital phases

Where each planet is along its orbit at the start of the integration matters a lot for resonant systems.

1. **Transiting planets:** the phase follows from the mid-transit time. At mid-transit the true anomaly is
   f = 90° − ω (Winn 2010). It is propagated to a common
   epoch with the period, and the uncertainties of both enter every draw. The archive does not standardize ω:
   some publications give the planet's ω, others that of the star's reflex orbit, which differs by 180°, and the
   values are "as-reported for each publication" (archive column documentation). exostab uses every ω as published,
   in f = 90° − ω. For an eccentric planet a wrong convention is not a rotation of the whole system: the planet stays
   where its transit puts it while its periastron flips, so the starting configuration changes and an eccentric
   system near a resonance can get a different N-body verdict.
2. **Non-transiting planets with a time of conjunction or of periastron:** used only if it comes from the same
   publication as the period. A phase from one orbital solution combined with a period from another would be
   meaningless. A time of periastron is used only if the argument of periastron is also published: without ω
   the direction of the periastron, and with it the planet's position relative to the other planets, is unknown.
   A time of periastron that several planets share is most likely an epoch, not a periastron time (GJ 876); it
   is not used.
3. **Otherwise:** the phase is drawn at random for every run, the nominal run included, and the report says so.

### Monte Carlo draws

Each draw takes every value from a *split normal* distribution: one Gaussian half with the upper error bar and one
with the lower. Values without published errors are held fixed. Values that are only upper limits are drawn
uniformly between 0 and the limit. Negative eccentricities are set to 0 and drawn eccentricities are capped at
0.95. A published (nominal) eccentricity above 0.95 is not accepted, because the nominal run would otherwise check
a different orbit from the one the report shows. Masses, periods and the stellar mass are redrawn until positive.
Phases are propagated from their reference times to the common epoch with the drawn periods. Draws are
independent: correlations in the published posteriors are ignored, which usually widens the spread of outcomes.
The same `--seed` gives the same draws.

## Your own parameters

`exostab check --from-file system.yaml` reads a YAML file.
[`examples/two_planet.yaml`](https://github.com/mimitoz62/exostab/blob/main/examples/two_planet.yaml) shows every
key, with the alternatives in comments; the [Quickstart](quickstart.md#check-a-system) has the line that downloads it.
[`examples/hd127195_note.yaml`](https://github.com/mimitoz62/exostab/blob/main/examples/hd127195_note.yaml) contains
the inputs of the HD 127195 Research Note. The same
completion rules apply to anything left out. Unknown keys, repeated keys, values that are not finite numbers and
contradictory input are refused with a message that names the field. So are:

- values no real system has: a stellar mass outside 0.001–1000 M☉, a planet not below its star, a period outside
  0.001–1e12 d, a semi-major axis above 1e7 AU, a time beyond 1e7 in absolute value, and a value whose upper error
  reaches past these limits;
- an error on one side only (`err_plus` without `err_minus`), `err` next to `err_plus` or `err_minus`, and an error bar
  or a value of 0 on an upper limit;
- booleans or text where a number belongs, and integers with a leading zero, a base prefix or colons, which YAML 1.1
  reads as other numbers (`010` as 8, `1:30` as 90). `3e-6` is a number;
- names and notes that are not text. YAML reads an unquoted `No`, `Yes`, `On` or `Off` as a boolean, so put such a name
  in quotes. Control characters are refused too, and planet names must differ by more than case or surrounding spaces.

A value is a number or a mapping `{value, err}` / `{value, err_plus, err_minus}`, optionally with `reference`.
Planet masses and eccentricities can also be `{value, upper_limit: true}` (a YAML boolean); an upper limit on any
other value is refused.

| Key | Unit | Notes |
|---|---|---|
| `name`, `notes` | — | system name (default: the file name); free text kept with the report |
| `epoch_jd` | JD | epoch of mean anomalies and mean longitudes; required when a file combines them with transit or periastron times |
| `star.name`, `star.mass_msun` | M☉ | the only star keys |
| `planets[].name` | — | at least two planets |
| `period_days` | d | or `semimajor_axis_au` (AU), from which the period follows by Kepler's third law (`period_from_semimajor_axis`); if both are given they must agree within 10% (or three times the axis's relative error) |
| `mass_earth` / `mass_jupiter` / `mass_msun` | M⊕ / M♃ / M☉ | one of them; or only `radius_earth` (R⊕), and the mass comes from Chen & Kipping (2017) (`mass_from_radius_chen_kipping`) |
| `mass_kind` | — | `true` (default), `minimum` (m sin i, `minimum_mass`) or `estimated` (`mass_estimated_in_file`); a radius-only planet takes no other kind than `estimated` |
| `eccentricity` | — | missing → 0 (`eccentricity_assumed_zero`); above 0.95 refused |
| `omega_deg` | deg | argument of periastron; missing → random in every run (`omega_randomized`). With `transit_time_jd`, the planet is placed at true anomaly f = 90° − ω at that time. Type ω unchanged if your source uses f = 90° − ω (Winn 2010, Eq. 6; EXOFAST's ω★, Eastman et al. 2013, Eq. 11), and add 180° if it uses f = 270° − ω (NbodyGradient, used by Agol et al. 2021; see `examples/trappist1_agol2021.yaml`). The words planet's and star's do not settle it: each source defines its own reference direction |
| `mean_longitude_deg`, `mean_anomaly_deg`, `transit_time_jd`, `periastron_time_jd` | deg / JD | at most one; the mean anomaly and the time of periastron need `omega_deg`; none → random phase (`phase_randomized`) |
| `reference` | — | citation for every value of the planet that has none of its own |
