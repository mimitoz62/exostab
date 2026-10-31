---
title: Hill stability and AMD calculator for two planets
description: >-
  Mutual Hill radius and Hill stability calculator for two planets, in the browser with no install and no server: the
  separation in mutual Hill radii, the Gladman (1993) criterion and the AMD-stability coefficient.
---

# Hill stability and AMD calculator for two planets

Enter a star and two planets to get their mutual Hill radius, their separation in mutual Hill radii, the Gladman (1993)
Hill stability criterion and the AMD-stability coefficient β. The page computes in your browser, with nothing to install
and no server doing the work, and uses the same formulas and constants as exostab's Hill and AMD indicators. It
evaluates two analytic criteria for one pair and one set of numbers, which is much less than a stability check:
see [what this does not show](#what-this-does-not-show).

The mutual Hill radius of two planets is R_H = ((m₁ + m₂) / 3M★)^(1/3) (a₁ + a₂)/2. Gladman (1993) showed that two
planets on circular, coplanar orbits can never come close to each other if they are more than about 2√3 ≈ 3.46 mutual
Hill radii apart. For eccentric orbits the limit grows, and the calculator includes that.

<noscript markdown="1">
!!! warning "This calculator needs JavaScript"
    JavaScript is off or blocked in this browser, so the page cannot compute anything here. The
    [stability catalog](catalog.md) can be read without it, and [Methods](methods.md) gives the formulas.
</noscript>

<div id="calc-app" hidden>
<form id="calc-form" class="calc-form" autocomplete="off" novalidate>
<div class="calc-presets" role="group" aria-labelledby="calc-presets-label">
<span id="calc-presets-label">Examples:</span>
<button type="button" class="md-button" data-preset="jupiter-saturn">Jupiter and Saturn</button>
<button type="button" class="md-button" data-preset="kepler-36">Kepler-36 b and c</button>
<button type="button" class="md-button" data-preset="gj-876">GJ 876 b and c</button>
<a href="#where-the-examples-come-from">Where they come from</a>
</div>
<div class="calc-field">
<label for="calc-star">Stellar mass (solar masses)</label>
<div class="calc-control"><input id="calc-star" name="star" type="text" spellcheck="false"></div>
</div>
<div class="calc-planets">
<fieldset>
<legend>Planet A</legend>
<div class="calc-field">
<label for="calc-a-mass">Mass</label>
<div class="calc-control">
<input id="calc-a-mass" name="a_mass" type="text" spellcheck="false">
<select name="a_unit" aria-label="Mass unit of planet A"><option value="earth">Earth masses</option><option value="jupiter">Jupiter masses</option></select>
</div>
</div>
<div class="calc-field">
<label for="calc-a-orbit">Orbit</label>
<div class="calc-control">
<input id="calc-a-orbit" name="a_orbit" type="text" spellcheck="false">
<select name="a_kind" aria-label="Orbit of planet A given as"><option value="period">period (days)</option><option value="axis">semi-major axis (au)</option></select>
</div>
</div>
<div class="calc-field">
<label for="calc-a-e">Eccentricity</label>
<div class="calc-control"><input id="calc-a-e" name="a_e" type="text" spellcheck="false"></div>
</div>
</fieldset>
<fieldset>
<legend>Planet B</legend>
<div class="calc-field">
<label for="calc-b-mass">Mass</label>
<div class="calc-control">
<input id="calc-b-mass" name="b_mass" type="text" spellcheck="false">
<select name="b_unit" aria-label="Mass unit of planet B"><option value="earth">Earth masses</option><option value="jupiter">Jupiter masses</option></select>
</div>
</div>
<div class="calc-field">
<label for="calc-b-orbit">Orbit</label>
<div class="calc-control">
<input id="calc-b-orbit" name="b_orbit" type="text" spellcheck="false">
<select name="b_kind" aria-label="Orbit of planet B given as"><option value="period">period (days)</option><option value="axis">semi-major axis (au)</option></select>
</div>
</div>
<div class="calc-field">
<label for="calc-b-e">Eccentricity</label>
<div class="calc-control"><input id="calc-b-e" name="b_e" type="text" spellcheck="false"></div>
</div>
</fieldset>
</div>
</form>
<h2>Result</h2>
<div role="status">
<p id="calc-verdicts" class="calc-verdicts">Hill spacing: <span data-calc="hill_verdict"></span>. AMD:
<span data-calc="amd_verdict"></span>.</p>
<div id="calc-errors" class="calc-errors" hidden><p>No result, because of the input:</p><ul></ul></div>
</div>
<div id="calc-result">
<p>These are the verdicts of exostab's Hill and AMD indicators for exactly these numbers, with nothing integrated and
no uncertainties. A stable verdict is not a proof that the pair is long-lived. Marginal does not mean unstable, and
unstable means that a criterion fails, not that the planets meet. See <a href="#what-this-does-not-show">what this
does not show</a>.</p>
<p data-calc="order"></p>
<h3>The orbits used</h3>
<dl class="calc-results">
<div><dt>Periods P₁, P₂</dt><dd class="calc-value" data-calc="periods"></dd></div>
<div><dt>Semi-major axes a₁, a₂</dt><dd class="calc-value" data-calc="axes"></dd>
<dd class="calc-meaning">Jacobi semi-major axes, as exostab computes them from the periods, with the mass of the star
and of the planets out to this one. A semi-major axis you enter first becomes a period for the star and that planet
alone, as in exostab's YAML files, so the outer value can differ slightly from what you entered.</dd></div>
<div><dt>Period ratio P₂ / P₁</dt><dd class="calc-value" data-calc="period_ratio"></dd>
<dd class="calc-meaning">Near a simple ratio such as 3:2 or 2:1 a mean-motion resonance is possible. This number alone
cannot tell, and the criteria below include resonances only as far as the critical AMD does.</dd></div>
</dl>
<h3>Hill spacing</h3>
<p data-calc="hill_sentence"></p>
<dl class="calc-results">
<div><dt>Mutual Hill radius R_H</dt><dd class="calc-value" data-calc="mutual_hill_radius"></dd>
<dd class="calc-meaning">R_H = ((m₁ + m₂) / 3M★)^(1/3) (a₁ + a₂)/2, the convention of Chambers et al. (1996) and Pu
&amp; Wu (2015). Some papers use a₁ in place of the mean of a₁ and a₂, so compare values with care.</dd></div>
<div><dt>Separation Δ</dt><dd class="calc-value" data-calc="separation_hill"></dd>
<dd class="calc-meaning">Δ = (a₂ − a₁) / R_H, in mutual Hill radii. For two circular, coplanar orbits with these masses
the Gladman (1993) limit is <span data-calc="gladman_critical_hill"></span>; for two small, equal masses it tends to 2√3
≈ 3.46. Eccentric orbits need a wider separation, which the margin below includes.</dd></div>
<div><dt>Gladman (1993) margin</dt><dd class="calc-value" data-calc="gladman_margin"></dd>
<dd class="calc-meaning">The left side over the right side of the criterion for eccentric orbits, as restated by Veras
&amp; Armitage (2004) and Giuppone et al. (2013), minus 1. Positive means Hill stable: for two planets on coplanar
orbits, a rigorous sufficient condition against close encounters (Marchal &amp; Bozis 1982; Gladman 1993), which does
not exclude the escape of the outer planet. Zero or below means that close encounters are not excluded, not that they
happen.</dd></div>
<div><dt>Can the orbits cross?</dt><dd class="calc-value" data-calc="orbits_cross"></dd>
<dd class="calc-meaning"><span data-calc="apsides"></span> The orbits can cross, for some orientation, if the inner
apocentre reaches the outer pericentre. The Hill indicator then says unstable.</dd></div>
</dl>
<h3>Angular momentum deficit</h3>
<p data-calc="amd_sentence"></p>
<dl class="calc-results">
<div><dt>AMD-stability coefficient β</dt><dd class="calc-value" data-calc="beta"></dd>
<dd class="calc-meaning">β = C / (Λ' C_c) (Laskar &amp; Petit 2017), where Λ' = m₂ √(G M★ a₂) belongs to the outer
planet and C_c is the critical AMD below. Inclinations are almost never measured, so exostab follows Laskar &amp;
Petit in taking C = 2C_p, twice the coplanar AMD, here with C_p / Λ' = <span data-calc="relative_amd"></span>: the
unknown inclinations are assumed to carry as much AMD as the eccentricities. This is an assumption, not a bound. Below
1, collisions are excluded in the orbit-averaged dynamics if it holds. For exactly coplanar orbits β_p =
<span data-calc="beta_coplanar"></span>, a lower bound for any inclinations.</dd></div>
<div><dt>Regime of the critical AMD</dt><dd class="calc-value" data-calc="regime"></dd>
<dd class="calc-meaning">The critical AMD C_c is the smallest AMD that lets the two orbits cross. Close pairs can
become chaotic before that, through overlapping first-order mean-motion resonances, and then a smaller critical AMD
applies. <span data-calc="regime_text"></span></dd></div>
<div><dt>Domain of the criterion</dt><dd class="calc-value" data-calc="domain"></dd>
<dd class="calc-meaning">Petit et al. (2017) state the resonance-overlap criterion for pairs inside the 2:1 resonance
(α = a₁/a₂ above 2^(−2/3) ≈ 0.63) with ε = (m₁ + m₂)/M★ at most ε_lim = 8.11 × 10⁻³ (8.20 × 10⁻³ in the paper, from
rounded constants). A pair above their switching point α_R but outside this domain is never called AMD-stable.
<span data-calc="domain_text"></span></dd></div>
<div><dt>Inner planet to the star, β_S</dt><dd class="calc-value" data-calc="beta_star"></dd>
<dd class="calc-meaning">β_S = C / Λ₁, with Λ₁ of the inner planet and the same C. At 1 or above, the AMD could in
principle bring the inner planet to the star. The AMD verdict is stable only if β and β_S are both below 1 (strongly
AMD-stable); β_S does not enter the verdict unstable. For exactly coplanar orbits β_S,p =
<span data-calc="beta_star_coplanar"></span>.</dd></div>
<div><dt>Hill stability in AMD form, β_H</dt><dd class="calc-value" data-calc="beta_hill"></dd>
<dd class="calc-meaning">β_H = C / (Λ' C_H) (Petit, Laskar &amp; Boué 2018), infinite if C_H is not positive. It tells
AMD-unstable but Hill stable (marginal) from neither. The verdict unstable needs β_p ≥ 1 and β_H,p ≥ 1, here β_H,p =
<span data-calc="beta_hill_coplanar"></span>. These coplanar values are lower bounds, so the assumption about the
inclinations never strengthens that verdict.</dd></div>
</dl>
<div class="calc-copy">
<button type="button" id="calc-copy" class="md-button">Copy link to this result</button>
<span id="calc-copy-note" role="status"></span>
</div>
</div>
</div>

## What this does not show

This page does not show that a pair is stable or safe. It evaluates two analytic criteria for the numbers you enter,
and failing them does not show that a pair is unstable either.

- **No N-body integration.** Nothing is computed forward in time, so there is no MEGNO and no test for chaos. A pair can
  pass both criteria and still be chaotic.
- **No resonances beyond what the criteria include.** The critical AMD includes the overlap of first-order mean-motion
  resonances, in the domain of Petit et al. (2017), and nothing more. A resonance can protect a pair that fails the
  criteria, and this page cannot see that.
- **No uncertainties.** Each number is taken as exact. A published value has error bars, and a verdict can change
  within them. `exostab check` repeats the analysis for draws within the uncertainties, and a verdict stands only if at
  least 95% of them agree.
- **No other planets.** Only these two bodies count. In a system of three or more planets, exostab adds up the AMD of
  all of them and uses a heuristic for the spacing, for which no proof exists, so a pair can fare differently there.
- **No inclinations.** The Hill test takes the orbits as coplanar, and β only assumes how much AMD the inclinations
  carry. A minimum mass m sin i counts as the true mass, and a larger true mass can change a verdict.

A fuller check is [`exostab check`](quickstart.md) or the [stability catalog](catalog.md). They integrate the orbits and
propagate the published uncertainties, and `exostab check` lists every assumption. With `--from-file` it takes your own
parameters. [Methods](methods.md) explains the indicators.

## Where the examples come from

- **Jupiter and Saturn**: masses as ratios to Earth's, sidereal periods and eccentricities from NASA's fact sheets for
  [Jupiter](https://nssdc.gsfc.nasa.gov/planetary/factsheet/jupiterfact.html) (updated 2 October 2024) and
  [Saturn](https://nssdc.gsfc.nasa.gov/planetary/factsheet/saturnfact.html) (updated 18 March 2025), around a star of 1
  solar mass. The other planets are left out. exostab's indicators call this pair stable, but the Solar System as a
  whole is AMD-unstable, because Mercury could in principle collide with Venus (Laskar & Petit 2017).
- **Kepler-36 b and c**: exostab's bundled snapshot of the NASA Exoplanet Archive's composite table, retrieved on 28
  September 2026, whose stellar mass, planet masses and periods come from Vissapragada et al. (2020). Both
  eccentricities are 0 in the snapshot, a value that paper fixes in its light-curve fit. The AMD is therefore 0, and the
  AMD test says nothing about the real eccentricities. exostab calls this parameter set stable, yet Deck et al. (2012)
  found the orbits chaotic for initial conditions consistent with the observations
  ([details](findings.md#what-stable-means-here-and-what-it-does-not)).
- **GJ 876 b and c**: the same snapshot, whose values for these planets and the star come from Rivera et al. (2010).
  Planets d and e are left out. Planet A is b, which has the longer period, so the page swaps the two. The Hill
  indicator says unstable and the AMD indicator marginal. With the published four-planet solution of Rivera et al.
  (2010) and its orbital phases, these two indicators say the same, yet all 20 N-body draws of `exostab check` are
  regular, because the planets are locked in a resonance. The snapshot has no usable phases, and with random phases most
  draws are not regular ([Validation](validation.md)).

`exostab check "Kepler-36" --offline` and `exostab check "GJ 876" --offline` use the same snapshot and show the same
values, for the whole system.

## How the page computes

The formulas and constants are those of
[`hill.py`](https://github.com/mimitoz62/exostab/blob/main/src/exostab/indicators/hill.py) and
[`amd.py`](https://github.com/mimitoz62/exostab/blob/main/src/exostab/indicators/amd.py), whose docstrings give the
equations, and [Methods](methods.md) explains them. The verdicts are those of the two indicators for two planets and
one set of parameters:

- **Hill spacing** says *stable* if the Gladman margin is positive and the orbits cannot cross, and *unstable*
  otherwise.
- **AMD** says *stable* if β < 1 and β_S < 1 and the pair lies inside the domain of the criterion, *unstable* if β_p ≥ 1
  and β_H,p ≥ 1, and *marginal* otherwise.

You can enter the planets in either order, because the outer planet is the one with the larger semi-major axis. As in
exostab, the planets are sorted by period, and each period then gives a Jacobi semi-major axis, which puts the longer
period further out. Masses and orbits are converted with the constants exostab takes from astropy.

The page accepts eccentricities from 0 to 0.95, the largest exostab integrates, and planet masses from 10⁻¹² of the
stellar mass up to the stellar mass, not included. exostab itself sets no such limits on the masses. These choices are
in [DECISIONS.md](https://github.com/mimitoz62/exostab/blob/main/DECISIONS.md) (D35).

[`tests/test_calculator.py`](https://github.com/mimitoz62/exostab/blob/main/tests/test_calculator.py) compares the
page's code with the Python functions on 3,000 seeded random pairs, crossing orbits and pairs outside the domain of the
AMD criterion among them. Every verdict and regime must agree exactly, and every number to a relative tolerance of
10⁻⁹, with a small absolute allowance for the few numbers that come from a difference of nearly equal terms, where
rounding alone exceeds that tolerance. It also checks the words and digits the page prints for each pair.

The inputs stay in the address of the page, so a link to a result opens that result. Opening such a link sends the
inputs to the server that hosts this site, as part of the address.

## References

- Chambers, J. E., Wetherill, G. W. & Boss, A. P. 1996, Icarus 119, 261, doi:10.1006/icar.1996.0019
- Deck, K. M., Holman, M. J., Agol, E., et al. 2012, ApJ 755, L21, doi:10.1088/2041-8205/755/1/l21
- Giuppone, C. A., Morais, M. H. M. & Correia, A. C. M. 2013, MNRAS 436, 3547, doi:10.1093/mnras/stt1831
- Gladman, B. 1993, Icarus 106, 247, doi:10.1006/icar.1993.1169
- Laskar, J. & Petit, A. C. 2017, A&A 605, A72, doi:10.1051/0004-6361/201630022
- Marchal, C. & Bozis, G. 1982, Celestial Mechanics 26, 311, doi:10.1007/bf01230725
- Petit, A. C., Laskar, J. & Boué, G. 2017, A&A 607, A35, doi:10.1051/0004-6361/201731196
- Petit, A. C., Laskar, J. & Boué, G. 2018, A&A 617, A93, doi:10.1051/0004-6361/201833088
- Pu, B. & Wu, Y. 2015, ApJ 807, 44, doi:10.1088/0004-637x/807/1/44
- Rivera, E. J., Laughlin, G., Butler, R. P., et al. 2010, ApJ 719, 890, doi:10.1088/0004-637x/719/1/890
- Veras, D. & Armitage, P. J. 2004, Icarus 172, 349, doi:10.1016/j.icarus.2004.06.012
- Vissapragada, S., Jontof-Hutter, D., Shporer, A., et al. 2020, AJ 159, 108, doi:10.3847/1538-3881/ab65c8
