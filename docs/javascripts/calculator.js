// Hill-spacing and AMD calculator for one pair of planets (docs/calculator.md). The numbers are a port of
// src/exostab/indicators/hill.py and amd.py, with the same formulas, constants and verdicts for two planets, and the
// result keys are those of hill.pair_table and amd.analyse. tests/test_calculator.py loads this file in Node and
// compares it with the Python functions, so a change to one of them must reach the other.
// Works with Material for MkDocs instant navigation (document$) and with plain page loads.
(function () {
  // exostab.units, from astropy: M_earth in M_sun, M_jup in M_earth, the day in Julian years, G in AU^3 / (M_sun yr^2)
  var MEARTH_IN_MSUN = 3.0034893488507934e-6;
  var MJUP_IN_MEARTH = 317.8284065946748;
  var DAY_IN_YR = 0.0027378507871321013;
  var G_SIM = 39.476926408897626;
  var E_MAX = 0.95; // sampling.E_MAX: the largest eccentricity exostab integrates
  var RATIO_MAX = 1e6; // hill._RATIO_MAX
  var R_MMR = 0.80199; // amd.R_MMR
  var EQUIPARTITION = 2; // amd.EQUIPARTITION: C = 2 C_p, unknown inclinations carry as much AMD as the eccentricities
  var ALPHA_2_1 = Math.pow(2, -2 / 3); // amd.ALPHA_2_1
  var EPS_LIM = Math.pow(((1 - ALPHA_2_1) * Math.pow(3, 6 / 7)) / (4 * Math.pow(R_MMR, 2 / 7)), 3.5); // amd.EPS_LIM
  // A limit of this page, not of exostab (DECISIONS.md, D35): the smallest planet mass, in stellar masses. Far below
  // it, rounding decides the search for the circular-orbit Gladman limit.
  var MASS_RATIO_MIN = 1e-12;

  function square(x) {
    return x * x;
  }

  // _numerics.bisect
  function bisect(f, lo, hi) {
    var xtol = 1e-14;
    var flo = f(lo);
    var fhi = f(hi);
    if (flo === 0) return lo;
    if (fhi === 0) return hi;
    if (flo > 0 === fhi > 0) throw new Error("root not bracketed");
    for (var i = 0; i < 200; i++) {
      var mid = 0.5 * (lo + hi);
      var fmid = f(mid);
      if (fmid === 0 || hi - lo < xtol * Math.max(1, Math.abs(mid))) return mid;
      if (fmid > 0 === flo > 0) {
        lo = mid;
        flo = fmid;
      } else {
        hi = mid;
      }
    }
    return 0.5 * (lo + hi);
  }

  // hill.mutual_hill_radius
  function mutualHillRadius(m1, m2, a1, a2, mStar) {
    return (Math.pow((m1 + m2) / (3 * mStar), 1 / 3) * (a1 + a2)) / 2;
  }

  // hill.separation_in_hill_radii
  function separationInHillRadii(m1, m2, a1, a2, mStar) {
    return (a2 - a1) / mutualHillRadius(m1, m2, a1, a2, mStar);
  }

  // hill.gladman_margin: LHS / RHS - 1 of the Gladman (1993) criterion, positive means Hill stable. Planet 1 is inner.
  function gladmanMargin(m1, m2, a1, a2, e1, e2, mStar) {
    var mu1 = m1 / mStar;
    var mu2 = m2 / mStar;
    var alpha = mu1 + mu2;
    var g1 = Math.sqrt(1 - square(e1));
    var g2 = Math.sqrt(1 - square(e2));
    var delta = Math.sqrt(a2 / a1);
    var lhs = Math.pow(alpha, -3) * (mu1 + mu2 / square(delta)) * square(mu1 * g1 + mu2 * g2 * delta);
    var rhs = 1 + (Math.pow(3, 4 / 3) * mu1 * mu2) / Math.pow(alpha, 4 / 3);
    return lhs / rhs - 1;
  }

  // hill.gladman_critical_separation: the limit in mutual Hill radii for two circular orbits
  function gladmanCriticalSeparation(m1, m2, mStar) {
    function f(ratio) {
      return gladmanMargin(m1, m2, 1, ratio, 0, 0, mStar);
    }
    var hi = 10;
    while (f(hi) <= 0 && hi < RATIO_MAX) hi *= 2;
    return separationInHillRadii(m1, m2, 1, bisect(f, 1 + 1e-12, hi), mStar);
  }

  // amd.relative_amd
  function relativeAmd(eIn, eOut, alpha, gamma) {
    return gamma * Math.sqrt(alpha) * (1 - Math.sqrt(1 - square(eIn))) + 1 - Math.sqrt(1 - square(eOut));
  }

  // amd.critical_eccentricity
  function criticalEccentricity(alpha, gamma) {
    if (!(alpha > 0 && alpha < 1)) throw new Error("alpha must be in (0, 1)");
    function F(e) {
      return alpha * e + (gamma * e) / Math.sqrt(alpha * (1 - square(e)) + square(gamma) * square(e)) - 1 + alpha;
    }
    return bisect(F, 0, Math.min(1, 1 / alpha - 1));
  }

  // amd.critical_amd_collision
  function criticalAmdCollision(alpha, gamma) {
    var eC = criticalEccentricity(alpha, gamma);
    return relativeAmd(eC, 1 - alpha - alpha * eC, alpha, gamma);
  }

  // amd.alpha_circular_overlap
  function alphaCircularOverlap(eps) {
    return 1 - (4 * Math.pow(R_MMR, 2 / 7) * Math.pow(eps, 2 / 7)) / Math.pow(3, 6 / 7);
  }

  // amd.alpha_resonance_switch
  function alphaResonanceSwitch(eps) {
    function P(x) {
      return 729 * Math.pow(x, 7) - 9 * 512 * R_MMR * eps * Math.pow(x, 3) - 16384 * square(R_MMR * eps);
    }
    return 1 - (P(1) > 0 ? bisect(P, 1e-12, 1) : 1);
  }

  // amd.critical_amd_mmr
  function criticalAmdMmr(alpha, gamma, eps) {
    if (alpha >= alphaCircularOverlap(eps)) return 0;
    var x = 1 - alpha;
    var g = (81 * Math.pow(x, 5)) / (512 * R_MMR * eps) - (32 * R_MMR * eps) / (9 * square(x));
    g = Math.max(g, 0);
    var s = gamma * Math.sqrt(alpha);
    return ((square(g) / 2) * s) / (1 + s);
  }

  // amd.critical_amd: the critical AMD and its regime
  function criticalAmd(alpha, gamma, eps) {
    if (eps <= EPS_LIM && alpha > Math.max(alphaResonanceSwitch(eps), ALPHA_2_1)) {
      return [criticalAmdMmr(alpha, gamma, eps), "mmr_overlap"];
    }
    return [criticalAmdCollision(alpha, gamma), "collision"];
  }

  // amd.outside_domain: why a pair lies outside the domain of Petit et al. (2017), or null if it does not
  function outsideDomain(alpha, eps) {
    if (alpha <= alphaResonanceSwitch(eps)) return null;
    if (eps > EPS_LIM) return "eps_above_limit";
    if (alpha <= ALPHA_2_1) return "wide_of_2_1";
    return null;
  }

  // amd.critical_amd_hill
  function criticalAmdHill(alpha, gamma, eps) {
    var masses = (Math.pow(3, 4 / 3) * Math.pow(eps, 2 / 3) * gamma) / square(1 + gamma);
    var term = (alpha / (gamma + alpha)) * (1 + masses);
    return gamma * Math.sqrt(alpha) + 1 - Math.pow(1 + gamma, 1.5) * Math.sqrt(term);
  }

  // hill.pair_table and hill.classify for two planets
  function hillOfPair(m1, m2, a1, a2, e1, e2, mStar) {
    var margin = gladmanMargin(m1, m2, a1, a2, e1, e2, mStar);
    var cross = a1 * (1 + e1) >= a2 * (1 - e2);
    return {
      mutual_hill_radius: mutualHillRadius(m1, m2, a1, a2, mStar),
      separation_hill: separationInHillRadii(m1, m2, a1, a2, mStar),
      gladman_critical_hill: gladmanCriticalSeparation(m1, m2, mStar),
      gladman_margin: margin,
      orbits_cross: cross,
      verdict: cross || margin <= 0 ? "unstable" : "stable",
    };
  }

  // amd.analyse and amd.classify for two planets, and which sentence amd.evaluate would choose as its summary
  function amdOfPair(m1, m2, a1, a2, e1, e2, mStar) {
    var lam1 = m1 * Math.sqrt(a1); // Lambda_k / sqrt(G M_*): the common factor cancels in every ratio
    var lam2 = m2 * Math.sqrt(a2);
    var coplanar = lam1 * (1 - Math.sqrt(1 - square(e1))) + lam2 * (1 - Math.sqrt(1 - square(e2)));
    var alpha = a1 / a2;
    var gamma = m1 / m2;
    var eps = (m1 + m2) / mStar;
    var critical = criticalAmd(alpha, gamma, eps);
    var rel = coplanar / lam2;
    var betaP = critical[0] > 0 ? rel / critical[0] : Infinity;
    var hillLimit = criticalAmdHill(alpha, gamma, eps);
    var betaHp = hillLimit > 0 ? rel / hillLimit : Infinity;
    var row = {
      alpha: alpha,
      gamma: gamma,
      epsilon: eps,
      alpha_resonance_switch: alphaResonanceSwitch(eps),
      relative_amd: rel,
      critical_amd: critical[0],
      critical_branch: critical[1],
      beta: EQUIPARTITION * betaP,
      beta_coplanar: betaP,
      circular_overlap: eps <= EPS_LIM && alpha >= alphaCircularOverlap(eps),
      outside_domain: outsideDomain(alpha, eps),
      critical_amd_hill: hillLimit,
      beta_hill: EQUIPARTITION * betaHp,
      beta_hill_coplanar: betaHp,
      beta_star: EQUIPARTITION * (coplanar / lam1), // amd.analyse: beta_Sp = C_p / Lambda_1
      beta_star_coplanar: coplanar / lam1,
    };
    if (!row.outside_domain && row.beta < 1 && row.beta_star < 1) row.verdict = "stable";
    else if (row.beta_coplanar >= 1 && row.beta_hill_coplanar >= 1) row.verdict = "unstable";
    else row.verdict = "marginal";
    if (row.verdict === "stable") row.summary = "stable";
    else if (row.beta < 1) row.summary = row.outside_domain ? "outside_domain" : "weak";
    else if (row.beta_hill < 1) row.summary = "hill_stable";
    else row.summary = row.verdict === "unstable" ? "neither_coplanar" : "neither";
    return row;
  }

  // Python's format(x, ".<digits>g"), so that numbers read as they do in exostab's reports.
  function formatG(x, digits) {
    if (x === 0) return "0";
    var parts = x.toExponential(digits - 1).split("e");
    var exponent = Number(parts[1]);
    if (exponent < -4 || exponent >= digits) {
      var mantissa = parts[0].indexOf(".") === -1 ? parts[0] : parts[0].replace(/\.?0+$/, "");
      var digitsOfExponent = (Math.abs(exponent) < 10 ? "0" : "") + Math.abs(exponent);
      return mantissa + "e" + (exponent < 0 ? "-" : "+") + digitsOfExponent;
    }
    var fixed = x.toFixed(digits - 1 - exponent);
    return fixed.indexOf(".") === -1 ? fixed : fixed.replace(/\.?0+$/, "");
  }

  // amd._b
  function formatBeta(x) {
    return x === Infinity ? "∞" : formatG(x, 3);
  }

  // The form's text, as read from the page or from a link, to a result or a list of what is wrong with it. Fields have
  // the shape of PRESETS below, and an error names the input it belongs to.
  function calculate(fields) {
    var errors = [];
    function fail(field, message) {
      errors.push({ field: field, message: message });
    }
    // NaN for text that is no number: the comparisons below then add nothing to the error named here.
    function number(field, text, label) {
      var t = String(text).trim();
      var x = /^[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?$/.test(t) ? Number(t) : NaN;
      var shown = t.slice(0, 30);
      if (t === "") fail(field, label + ": enter a number.");
      else if (isNaN(x)) fail(field, label + ': "' + shown + '" is not a number. Write decimals with a point, as in 0.05.');
      else if (!isFinite(x)) fail(field, label + ": " + shown + " is too large to compute with.");
      return x;
    }
    var mStar = number("star", fields.star, "Stellar mass");
    if (mStar <= 0) fail("star", "Stellar mass must be above zero.");
    var planets = ["a", "b"].map(function (key) {
      var name = "Planet " + key.toUpperCase();
      var p = fields[key];
      var mass = number(key + "_mass", p.mass, name + " mass");
      if (mass <= 0) fail(key + "_mass", name + " mass must be above zero.");
      if (p.unit !== "earth" && p.unit !== "jupiter") {
        fail(key + "_unit", name + " mass: choose Earth or Jupiter masses.");
      }
      var what = p.kind === "axis" ? "semi-major axis" : "period";
      var orbit = number(key + "_orbit", p.orbit, name + " " + what);
      if (orbit <= 0) fail(key + "_orbit", name + " " + what + " must be above zero.");
      var e = number(key + "_e", p.e, name + " eccentricity");
      if (e < 0 || e > E_MAX) {
        fail(key + "_e", name + " eccentricity must be between 0 and " + E_MAX + ", the largest exostab integrates.");
      }
      return { key: key, name: name, mass: mass, unit: p.unit, kind: p.kind, orbit: orbit, e: e };
    });
    if (errors.length) return { errors: errors };

    // The conversion exostab makes for a YAML file: masses go through Earth masses (data/files.py, sampling.realize),
    // and a semi-major axis becomes a period with Kepler's third law for the star and this planet alone
    // (units.period_from_semimajor_axis). The planets are then sorted by period (sampling.realize).
    var bodies = planets.map(function (p) {
      var mEarth = p.unit === "jupiter" ? p.mass * MJUP_IN_MEARTH : p.mass;
      var days = p.orbit;
      if (p.kind === "axis") {
        var total = mStar + mEarth * MEARTH_IN_MSUN;
        days = (2 * Math.PI * Math.sqrt(Math.pow(p.orbit, 3) / (G_SIM * total))) / DAY_IN_YR;
      }
      return { key: p.key, name: p.name, m: mEarth * MEARTH_IN_MSUN, days: days, P: days * DAY_IN_YR, e: p.e };
    });
    var tooExtreme = { errors: [{ field: null, message: "These values are too small or too large to compute with." }] };
    if (!bodies.every(function (b) { return b.P > 0 && isFinite(b.P); })) return tooExtreme;
    bodies.forEach(function (b) {
      if (b.m >= mStar) {
        var masses = formatG(b.m, 4) + " against " + formatG(mStar, 4) + " solar masses.";
        fail(b.key + "_mass", b.name + " mass is not below the stellar mass: " + masses);
      } else if (b.m < MASS_RATIO_MIN * mStar) {
        fail(b.key + "_mass", b.name + " mass is below " + MASS_RATIO_MIN + " of the stellar mass, too small for this page.");
      }
    });
    if (planets[0].kind === "axis" && planets[1].kind === "axis" && planets[0].orbit === planets[1].orbit) {
      fail("b_orbit", "The two planets have the same semi-major axis, so neither is the outer planet.");
    } else if (bodies[0].days === bodies[1].days) {
      fail("b_orbit", "The two planets have the same period, so neither is the outer planet.");
    }
    if (errors.length) return { errors: errors };

    var swapped = bodies[0].P > bodies[1].P;
    var inner = swapped ? bodies[1] : bodies[0];
    var outer = swapped ? bodies[0] : bodies[1];
    // Realization.semi_major_axes: from a period, the Jacobi semi-major axis, with the mass of the star and of the
    // planets out to this one, as REBOUND sets it. The outer planet thus has the larger semi-major axis.
    inner.a = Math.pow((G_SIM * (mStar + inner.m) * square(inner.P)) / (4 * square(Math.PI)), 1 / 3);
    outer.a = Math.pow((G_SIM * (mStar + inner.m + outer.m) * square(outer.P)) / (4 * square(Math.PI)), 1 / 3);
    if (!(inner.a > 0 && isFinite(outer.a))) return tooExtreme;
    var periodRatio = outer.P / inner.P;
    try {
      var hill = hillOfPair(inner.m, outer.m, inner.a, outer.a, inner.e, outer.e, mStar);
      var amd = amdOfPair(inner.m, outer.m, inner.a, outer.a, inner.e, outer.e, mStar);
      // Far beyond any star or orbit, Lambda or the period ratio no longer fits in a number, as in the Python
      // functions, and the semi-major axes can round to the same value. No verdict goes out on such numbers.
      if (!(amd.alpha < 1 && isFinite(periodRatio) && isFinite(amd.relative_amd) && isFinite(amd.beta_star))) {
        return tooExtreme;
      }
      return {
        result: {
          m_star: mStar,
          swapped: swapped,
          bodies: [inner, outer],
          period_ratio: periodRatio,
          hill: hill,
          amd: amd,
        },
      };
    } catch (err) {
      return tooExtreme; // bisect without a root, as for a stellar mass of 1e-320: no old result may stay on the page
    }
  }

  // The sentence for the Hill verdict, after hill.evaluate, which says "inside the limit" of crossing orbits too.
  // tests/test_calculator.py finds a negative margin for crossing orbits in all its random pairs.
  function hillSentence(r) {
    var h = r.hill;
    if (h.verdict === "stable") {
      return (
        "Hill stable: separation " + h.separation_hill.toFixed(2) + " mutual Hill radii, above the Gladman (1993) " +
        "limit of " + h.gladman_critical_hill.toFixed(2) + " for circular orbits (eccentricities included in the test). " +
        "For two planets on coplanar orbits this is a rigorous sufficient condition against close encounters. It does " +
        "not exclude the escape of the outer planet."
      );
    }
    return (
      "Not Hill stable: this pair is inside the Gladman (1993) limit" +
      (h.orbits_cross ? " and its orbits can cross" : "") +
      ", so close encounters are not excluded (a mean-motion resonance can still protect the pair)."
    );
  }

  // The sentence for the AMD verdict, after amd.evaluate, for one pair.
  function amdSentence(r) {
    var p = r.amd;
    var beta = formatBeta(p.beta);
    var betaS = formatBeta(p.beta_star);
    var betaH = formatBeta(p.beta_hill);
    var coplanar = "β_p = " + formatBeta(p.beta_coplanar) + ", β_H,p = " + formatBeta(p.beta_hill_coplanar);
    if (p.summary === "stable" && r.bodies[0].e === 0 && r.bodies[1].e === 0) {
      return (
        "AMD-stable only because both eccentricities are 0, so the AMD, β and β_S are all 0. If they are assumed and not " +
        "measured, this test says nothing about the real eccentricities."
      );
    }
    if (p.summary === "stable") {
      return (
        "AMD-stable: β = " + beta + " and β_S = " + betaS + ", so collisions are excluded in the secular approximation, " +
        "provided the mutual inclinations carry no more AMD than the eccentricities."
      );
    }
    if (p.summary === "outside_domain") {
      return (
        "β = " + beta + " is below 1, but this pair lies outside the domain Petit et al. (2017) state for the critical " +
        "AMD, so AMD stability is not claimed" +
        (p.beta_star >= 1 ? "; the AMD could also bring the inner planet to the star (β_S = " + betaS + ")." : ".")
      );
    }
    if (p.summary === "weak") {
      return (
        "Weakly AMD-stable: no planet-planet collisions (β = " + beta + "), but the AMD could in principle bring the inner " +
        "planet to the star (β_S = " + betaS + ")."
      );
    }
    if (p.summary === "hill_stable") {
      return (
        "AMD-unstable (β = " + beta + ") but Hill stable in the AMD framework (β_H = " + betaH + "): close encounters are " +
        "excluded in that framework, chaos is not."
      );
    }
    if (p.summary === "neither_coplanar") {
      return (
        "Neither AMD-stable (β = " + beta + ") nor Hill stable (β_H = " + betaH + "), even for exactly coplanar orbits (" +
        coplanar + "): the AMD allows close encounters. It does not follow that they happen."
      );
    }
    return (
      "Neither AMD-stable (β = " + beta + ") nor Hill stable (β_H = " + betaH + ") if the mutual inclinations carry as " +
      "much AMD as the eccentricities; not 'unstable', because the coplanar values (" + coplanar + ") are not both ≥ 1."
    );
  }

  function regimeText(p) {
    if (p.critical_branch === "collision") {
      return "Here the collision regime: C_c = " + formatG(p.critical_amd, 3) + " (Laskar & Petit 2017).";
    }
    if (p.critical_amd === 0) {
      return (
        "Here the resonance-overlap regime, and resonances overlap even for circular orbits: C_c = 0, so β is infinite " +
        "(Petit et al. 2017)."
      );
    }
    return "Here the resonance-overlap regime: C_c = " + formatG(p.critical_amd, 3) + " (Petit et al. 2017).";
  }

  // After the notes of amd.evaluate.
  function domainText(p) {
    var alpha = "α = " + formatG(p.alpha, 3);
    var alphaR = "α_R = " + formatG(p.alpha_resonance_switch, 3);
    var eps = "ε = " + formatG(p.epsilon, 3);
    var lim = "ε_lim = " + (EPS_LIM * 1e3).toFixed(2) + "e-3";
    if (p.outside_domain === "eps_above_limit") {
      return (
        eps + " is above " + lim + " and " + alpha + " is above " + alphaR + ". Petit et al. (2017) excluded such pairs, " +
        "whose circular-orbit resonance-overlap limit lies wide of the 2:1 resonance. β uses the collision criterion, " +
        "and the AMD verdict is at most marginal."
      );
    }
    if (p.outside_domain === "wide_of_2_1") {
      return (
        alpha + " is at or wide of the 2:1 resonance, where Petit et al. (2017) consider first-order resonance overlap " +
        "meaningless although α is above " + alphaR + ". β uses the collision criterion, and the AMD verdict is at most " +
        "marginal."
      );
    }
    if (p.epsilon > EPS_LIM) {
      return (
        eps + " is above " + lim + ", but " + alpha + " is at or below " + alphaR + ", where Petit et al. (2017) use the " +
        "collision criterion of Laskar & Petit (2017), as for any pair far from first-order resonance overlap."
      );
    }
    if (p.critical_branch === "mmr_overlap") {
      return "Here " + alpha + " is above " + alphaR + " and above the 2:1 resonance, and " + eps + " is at most " + lim + ".";
    }
    return (
      "Here " + alpha + " is at or below " + alphaR + " for " + eps + ", where Petit et al. (2017) use the collision " +
      "criterion."
    );
  }

  // The text of every [data-calc] element of the page.
  function describe(r) {
    var inner = r.bodies[0];
    var outer = r.bodies[1];
    var h = r.hill;
    var p = r.amd;
    var innerName = "planet " + inner.key.toUpperCase();
    var outerName = "planet " + outer.key.toUpperCase();
    return {
      hill_verdict: h.verdict,
      amd_verdict: p.verdict,
      order: r.swapped
        ? "Swapped: " + innerName + " is the inner planet (index 1 below) and " + outerName + " the outer one (index 2), " +
          "because the outer planet is the one with the larger semi-major axis."
        : inner.name + " is the inner planet (index 1 below) and " + outerName + " the outer one (index 2).",
      periods: formatG(inner.days, 7) + " d, " + formatG(outer.days, 7) + " d",
      axes: formatG(inner.a, 7) + " au, " + formatG(outer.a, 7) + " au",
      period_ratio: formatG(r.period_ratio, 6),
      hill_sentence: hillSentence(r),
      mutual_hill_radius: formatG(h.mutual_hill_radius, 4) + " au",
      separation_hill: h.separation_hill.toFixed(2),
      gladman_critical_hill: h.gladman_critical_hill.toFixed(2),
      gladman_margin:
        (h.gladman_margin > 0 ? "+" : h.gladman_margin < 0 ? "−" : "") + formatG(Math.abs(h.gladman_margin), 3),
      orbits_cross: h.orbits_cross ? "yes" : "no",
      apsides:
        "Inner apocentre a₁(1 + e₁) = " + formatG(inner.a * (1 + inner.e), 5) + " au; outer pericentre a₂(1 − e₂) = " +
        formatG(outer.a * (1 - outer.e), 5) + " au.",
      amd_sentence: amdSentence(r),
      beta: formatBeta(p.beta),
      beta_coplanar: formatBeta(p.beta_coplanar),
      relative_amd: formatG(p.relative_amd, 3),
      regime: p.critical_branch === "collision" ? "collision" : "resonance overlap",
      regime_text: regimeText(p),
      domain: p.outside_domain ? "outside" : "inside",
      domain_text: domainText(p),
      beta_star: formatBeta(p.beta_star),
      beta_star_coplanar: formatBeta(p.beta_star_coplanar),
      beta_hill: formatBeta(p.beta_hill),
      beta_hill_coplanar: formatBeta(p.beta_hill_coplanar),
    };
  }

  // The examples of docs/calculator.md, which says where each comes from. tests/test_calculator.py checks them against
  // the bundled snapshot.
  function planet(mass, orbit, e) {
    return { mass: mass, unit: "earth", kind: "period", orbit: orbit, e: e };
  }
  var PRESETS = {
    "jupiter-saturn": { star: "1", a: planet("317.83", "4332.589", "0.0487"), b: planet("95.16", "10755.699", "0.052") },
    "kepler-36": { star: "1.034", a: planet("3.83", "13.86825", "0"), b: planet("7.13", "16.21865", "0") },
    "gj-876": { star: "0.32", a: planet("723.2235", "61.1166", "0.0324"), b: planet("226.9846", "30.0881", "0.25591") },
  };

  // The inputs in a link, for example ?star=1&a_mass=3.8&a_unit=earth&a_period=13.9&a_e=0&b_mass=...&b_axis=0.13&b_e=0.
  // The text is kept as it was typed. A link with both a_period and a_axis uses the period.
  function queryFromFields(fields) {
    var params = new URLSearchParams();
    params.set("star", fields.star);
    ["a", "b"].forEach(function (key) {
      var p = fields[key];
      params.set(key + "_mass", p.mass);
      params.set(key + "_unit", p.unit);
      params.set(key + "_" + p.kind, p.orbit);
      params.set(key + "_e", p.e);
    });
    return params.toString();
  }

  // The fields of a link, or null if it has none of ours (search.highlight, for one, adds ?h=...). An input the link
  // leaves out stays empty, so that calculate says what is missing; a missing unit means Earth masses.
  function fieldsFromQuery(search) {
    var params = new URLSearchParams(search);
    var names = ["star"];
    ["a", "b"].forEach(function (key) {
      ["mass", "unit", "period", "axis", "e"].forEach(function (name) {
        names.push(key + "_" + name);
      });
    });
    if (!names.some(function (name) { return params.has(name); })) return null;
    function text(name) {
      return params.has(name) ? params.get(name) : "";
    }
    function fromLink(key) {
      var axis = params.has(key + "_axis") && !params.has(key + "_period");
      return {
        mass: text(key + "_mass"),
        unit: params.has(key + "_unit") ? params.get(key + "_unit") : "earth",
        kind: axis ? "axis" : "period",
        orbit: text(key + (axis ? "_axis" : "_period")),
        e: text(key + "_e"),
      };
    }
    return { star: text("star"), a: fromLink("a"), b: fromLink("b") };
  }

  var api = {
    constants: {
      MEARTH_IN_MSUN: MEARTH_IN_MSUN,
      MJUP_IN_MEARTH: MJUP_IN_MEARTH,
      DAY_IN_YR: DAY_IN_YR,
      G_SIM: G_SIM,
      E_MAX: E_MAX,
      RATIO_MAX: RATIO_MAX,
      R_MMR: R_MMR,
      EQUIPARTITION: EQUIPARTITION,
      ALPHA_2_1: ALPHA_2_1,
      EPS_LIM: EPS_LIM,
    },
    bisect: bisect,
    mutualHillRadius: mutualHillRadius,
    separationInHillRadii: separationInHillRadii,
    gladmanMargin: gladmanMargin,
    gladmanCriticalSeparation: gladmanCriticalSeparation,
    relativeAmd: relativeAmd,
    criticalEccentricity: criticalEccentricity,
    criticalAmdCollision: criticalAmdCollision,
    alphaCircularOverlap: alphaCircularOverlap,
    alphaResonanceSwitch: alphaResonanceSwitch,
    criticalAmdMmr: criticalAmdMmr,
    criticalAmd: criticalAmd,
    outsideDomain: outsideDomain,
    criticalAmdHill: criticalAmdHill,
    formatG: formatG,
    formatBeta: formatBeta,
    calculate: calculate,
    describe: describe,
    queryFromFields: queryFromFields,
    fieldsFromQuery: fieldsFromQuery,
    PRESETS: PRESETS,
  };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  if (typeof document === "undefined") return;

  function setup() {
    var app = document.getElementById("calc-app");
    if (!app || app.dataset.ready) return;
    app.dataset.ready = "1";
    app.hidden = false;
    var form = document.getElementById("calc-form");
    var errorBox = document.getElementById("calc-errors");
    var errorList = errorBox.querySelector("ul");
    var verdicts = document.getElementById("calc-verdicts");
    var result = document.getElementById("calc-result");
    var order = document.querySelector('[data-calc="order"]');
    var copyNote = document.getElementById("calc-copy-note");
    var timer = null;

    function readFields() {
      function read(key) {
        return {
          mass: form.elements[key + "_mass"].value,
          unit: form.elements[key + "_unit"].value,
          kind: form.elements[key + "_kind"].value,
          orbit: form.elements[key + "_orbit"].value,
          e: form.elements[key + "_e"].value,
        };
      }
      return { star: form.elements.star.value, a: read("a"), b: read("b") };
    }

    // A unit a link gets wrong selects nothing, so calculate asks for one.
    function fillForm(fields) {
      form.elements.star.value = fields.star;
      ["a", "b"].forEach(function (key) {
        var p = fields[key];
        form.elements[key + "_mass"].value = p.mass;
        form.elements[key + "_unit"].value = p.unit;
        form.elements[key + "_kind"].value = p.kind;
        form.elements[key + "_orbit"].value = p.orbit;
        form.elements[key + "_e"].value = p.e;
      });
    }

    function writeLink(fields) {
      try {
        // history.state: Material keeps the scroll position there. Safari limits how often this may be called.
        history.replaceState(history.state, "", location.pathname + "?" + queryFromFields(fields) + location.hash);
      } catch (err) {
        return;
      }
    }

    // Material has made the links of a page absolute, with the query of the page as it was loaded, and following a
    // link can load the page again. So a link to a heading of this page has to keep the inputs.
    function updateLinksToHeadings() {
      Array.prototype.forEach.call(document.querySelectorAll('a[href*="#"]'), function (link) {
        if (link.pathname === location.pathname) link.search = location.search;
      });
    }

    // Text that has not changed is not written again, so that the status region is announced only when it changes.
    function showErrors(errors) {
      Array.prototype.forEach.call(form.querySelectorAll("[aria-invalid]"), function (input) {
        input.removeAttribute("aria-invalid");
      });
      errors.forEach(function (error) {
        if (error.field) form.elements[error.field].setAttribute("aria-invalid", "true");
      });
      var messages = errors.map(function (error) {
        return error.message;
      });
      if (messages.join("") !== errorList.textContent) {
        errorList.textContent = "";
        messages.forEach(function (message) {
          errorList.appendChild(document.createElement("li")).textContent = message;
        });
      }
      errorBox.hidden = errors.length === 0;
      verdicts.hidden = errors.length > 0;
      result.hidden = errors.length > 0;
    }

    function showResult(slots) {
      Array.prototype.forEach.call(app.querySelectorAll("[data-calc]"), function (el) {
        var name = el.getAttribute("data-calc");
        if (el.textContent !== slots[name]) el.textContent = slots[name];
        if (name === "hill_verdict" || name === "amd_verdict") el.className = "verdict-" + slots[name];
      });
      order.classList.toggle("calc-swapped", slots.order.indexOf("Swapped") === 0);
    }

    function update(withLink) {
      var fields = readFields();
      var out = calculate(fields);
      showErrors(out.errors || []);
      if (out.result) showResult(describe(out.result));
      copyNote.textContent = "";
      if (withLink) writeLink(fields);
      updateLinksToHeadings();
    }

    function updateNow() {
      clearTimeout(timer);
      update(true);
    }

    // After a pause in typing, so that "1e-3" is not called wrong at "1e". The page may be gone by then (instant
    // navigation).
    form.addEventListener("input", function () {
      clearTimeout(timer);
      timer = setTimeout(function () {
        if (form.isConnected) update(true);
      }, 250);
    });
    form.addEventListener("change", updateNow);
    form.addEventListener("submit", function (event) {
      event.preventDefault();
      updateNow();
    });
    Array.prototype.forEach.call(app.querySelectorAll("[data-preset]"), function (button) {
      button.addEventListener("click", function () {
        fillForm(PRESETS[button.getAttribute("data-preset")]);
        updateNow();
      });
    });
    document.getElementById("calc-copy").addEventListener("click", function () {
      var fields = readFields();
      writeLink(fields);
      // From the form, not the address: the browser may have refused to update the address (writeLink).
      var link = location.origin + location.pathname + "?" + queryFromFields(fields);
      function say(text) {
        copyNote.textContent = text;
      }
      var failed = "Could not copy. This is the link: " + link;
      if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(link).then(function () {
          say("Link copied.");
        }, function () {
          say(failed);
        });
      } else {
        say(failed);
      }
    });

    // A link shows its result. Without one the page opens with the first example, and the address stays as it is.
    function fromAddress() {
      fillForm(fieldsFromQuery(location.search) || PRESETS["jupiter-saturn"]);
      update(false);
    }
    // Back and forward within the page, after a link to a heading. The page may be gone by then, as above.
    window.onpopstate = function () {
      if (form.isConnected) fromAddress();
    };
    fromAddress();
    // With instant navigation Material has already scrolled, when the calculator did not yet take up its place on the
    // page. So scroll again, by Material's rule: to the saved position, or else to the heading in the address.
    if (history.state && history.state.y) {
      window.scrollTo(0, history.state.y);
    } else if (!history.state && location.hash) {
      var heading = document.getElementById(location.hash.slice(1));
      if (heading) heading.scrollIntoView();
    }
  }
  if (typeof document$ !== "undefined") { document$.subscribe(setup); } else { document.addEventListener("DOMContentLoaded", setup); }
})();
