"""Data completion rules: how archive rows with missing values become a complete :class:`System`.

Every rule that fires adds a :class:`~exostab.models.CompletionFlag`; the flags are printed in every
report and stored in the JSON output. The rules (DECISIONS.md, D11):

Stellar mass
    The planet rows of one host can give different stellar masses (the composite table picks them per
    planet). If one publication gives more of the measured planet masses than any other and a row gives
    that publication's stellar mass, that value is used, so that those planet-to-star mass ratios are the
    published ones; otherwise the median of the rows, for an even number of rows the lower middle value.
    The disagreement is flagged with every value and its reference. Limits on the stellar mass are not
    used; a system with only a limit is rejected.
Period
    Published period used when present. Otherwise derived from the semi-major axis with Kepler's third
    law ("derived"), except for planets found by microlensing or direct imaging, whose ``pl_orbsmax`` can
    be a projected separation: those systems are rejected. A planet with neither cannot be placed and
    the system is rejected.
Mass
    ``pl_bmassprov`` says what the archive's mass is: "Mass" and "Msin(i)/sin(i)" are true masses;
    "Msini" is a minimum mass (used as the mass, i.e. sin i = 1, unless ``--inclination-prior`` is
    given), except for transiting planets, whose sin i is close to 1; a lower limit on the mass of a
    non-transiting planet is a minimum mass; "M-R relationship" was estimated by the archive from the
    radius ("estimated"). An upper limit is used as the value in the nominal run. A missing mass is
    estimated from the radius with the Chen & Kipping (2017) relation where that relation can be inverted.
Archive-calculated values
    A ``*_reflink`` of "Calculated Value" (the link to ``pscp_calc.html``) means the archive computed the
    number. Planet mass and radius filled from the Chen & Kipping (2017) mass-radius relation are labelled
    "estimated"; every other calculated column is computed from measured quantities and is labelled
    "derived". ``_value`` applies the same rule to every column.
Eccentricity
    Missing -> 0 ("assumed"). Published as exactly 0 without an uncertainty -> also "assumed" and
    flagged: such a value is a circular orbit fixed in the source's fit, not a measurement. An upper
    limit is used as the value in the nominal run. Above ``sampling.E_MAX`` (0.95) the system is
    rejected.
Argument of periastron
    Missing -> drawn uniformly for every run ("randomized").
Orbital phase
    From the transit mid-time of transiting planets; from the time of inferior conjunction or periastron
    of non-transiting planets only if it comes from the same publication as the period (the composite
    table can mix publications, and phases from one orbital solution cannot be combined with periods
    from another) and, for a time of periastron, only if the argument of periastron is published (it
    gives the direction of the periastron); otherwise drawn uniformly for every run ("randomized").
Inclinations and nodes
    All orbits are placed in one plane (coplanar). Sky-plane inclinations do not determine mutual
    inclinations, and the longitudes of the ascending node are not used.
"""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Sequence
from html import unescape
from typing import Any
from urllib.parse import urljoin

from ..models import CompletionFlag, MassKind, Phase, PhaseKind, Planet, Provenance, Star, Value
from ..sampling import E_MAX
from ..units import MEARTH_IN_MSUN, period_from_semimajor_axis, years_to_days
from .archive import ARCHIVE_URL
from .massradius import MassRadiusError, mass_from_radius

Row = dict[str, Any]


class IncompleteSystemError(ValueError):
    """The published data are not sufficient to model the system."""


_HREF = re.compile(r"href=\s*['\"]?([^\s'\">]+)")
_TAG = re.compile(r"<[^>]*>")


def parse_reflink(html: str | None) -> tuple[str | None, str | None]:
    """Split an archive ``*_reflink`` cell into (citation text, URL).

    HTML entities are decoded ("Fulton &amp; Petigura" -> "Fulton & Petigura"), and links relative to the
    archive site (``/docs/pscp_calc.html`` for values the archive calculated) are made absolute.
    """
    if not html:
        return None, None
    m = _HREF.search(html)
    text = unescape(_TAG.sub("", html)).strip() or None
    return text, (urljoin(ARCHIVE_URL, unescape(m.group(1))) if m else None)


# pscp_calc.html fills planet mass and radius from the Chen & Kipping (2017) mass-radius relation.
# Every other quantity on that page is computed from measured inputs.
_MASS_RADIUS_COLUMNS = frozenset({"pl_bmasse", "pl_bmassj", "pl_rade", "pl_radj"})


def _archive_calculated(ref: str | None, url: str | None) -> bool:
    """True when the cell's reference is the archive's own calculated value."""
    return ref == "Calculated Value" or (url is not None and "pscp_calc.html" in url)


def _value(row: Row, base: str, *, provenance: Provenance = Provenance.MEASURED) -> Value:
    """Value with archive errors (err1 >= 0 is the upper error, err2 <= 0 the lower one).

    A reference of "Calculated Value" is not a measurement. For every column, the label follows
    ``pscp_calc.html``: "estimated" when the archive filled the column from a mass-radius relation,
    "derived" when it computed the column from other measured quantities.
    """
    ref, url = parse_reflink(row.get(base + "_reflink"))
    if _archive_calculated(ref, url):
        provenance = Provenance.ESTIMATED if base in _MASS_RADIUS_COLUMNS else Provenance.DERIVED
    e1, e2 = row.get(base + "err1"), row.get(base + "err2")
    return Value(
        value=row.get(base),
        err_plus=abs(e1) if e1 is not None else None,
        err_minus=abs(e2) if e2 is not None else None,
        provenance=provenance,
        reference=ref,
        reference_url=url,
    )


def _flag(planet: str | None, parameter: str, rule: str, message: str) -> CompletionFlag:
    return CompletionFlag(planet=planet, parameter=parameter, rule=rule, message=message)


def _star_mass_key(row: Row) -> tuple[float, str, str, str]:
    """The stellar-mass entry of one planet row: value, errors and citation (for grouping and sorting)."""
    ref = parse_reflink(row.get("st_mass_reflink"))[0] or ""
    return float(row["st_mass"]), str(row.get("st_masserr1")), str(row.get("st_masserr2")), ref


def _star_mass_rows(rows: Sequence[Row]) -> list[Row]:
    """Rows with a measured stellar mass (not missing, not a limit)."""
    return [r for r in rows if r.get("st_mass") is not None and r.get("st_masslim") not in (1, -1)]


def _measured_mass_rows(rows: Sequence[Row]) -> list[Row]:
    """Rows with a measured planet mass (RV, TTV or astrometry; not estimated from the radius), which scales
    with the stellar mass the publication assumed."""
    return [r for r in rows if r.get("pl_bmasse") is not None and mass_kind(r) is not MassKind.ESTIMATED]


def _mass_publication(rows: Sequence[Row]) -> str | None:
    """The publication of more measured planet masses than any other, or None (no measured mass, or a tie)."""
    counts = Counter(parse_reflink(r.get("pl_bmasse_reflink"))[0] for r in _measured_mass_rows(rows))
    counts.pop(None, None)
    top = counts.most_common(2)
    if not top or (len(top) == 2 and top[1][1] == top[0][1]):
        return None
    return top[0][0]


def _star_mass_pool(rows: Sequence[Row]) -> tuple[list[Row], str | None]:
    """The rows among which the stellar mass is chosen, and the publication that decided it (or None)."""
    usable = _star_mass_rows(rows)
    paper = _mass_publication(rows)
    if paper is not None:
        same = [r for r in usable if parse_reflink(r.get("st_mass_reflink"))[0] == paper]
        if same:
            return same, paper
    return usable, None


def star_mass_row(rows: Sequence[Row]) -> Row | None:
    """The planet row whose stellar mass is used for the whole system, or None if no row has one.

    The composite table picks the stellar parameters separately for each planet row, so the rows of one
    host can give different stellar masses, and the archive returns the rows in no particular order. A
    measured planet mass scales with the stellar mass its publication assumed (m sin i as M_*^(2/3) from
    radial velocities, m as M_* from transit-timing mass ratios), so if one publication gives more of the
    measured masses than any other and a row gives that publication's stellar mass, that value is used.
    Otherwise the rule is the median of the rows' values, for an even number of rows the lower of the two
    middle values (a smaller star gives larger planet-to-star mass ratios, the less stable choice). Among
    rows with the chosen value, the most common (errors, reference) wins, then the first in sort order, so
    the result never depends on the row order. Limits on the stellar mass are not values and are not used.
    """
    pool, _ = _star_mass_pool(rows)
    if not pool:
        return None
    values = sorted(float(r["st_mass"]) for r in pool)
    median = values[(len(values) - 1) // 2]
    same = [r for r in pool if r["st_mass"] == median]
    counts = Counter(_star_mass_key(r) for r in same)
    return min(same, key=lambda r: (-counts[_star_mass_key(r)], _star_mass_key(r)))


def _star_mass_entry(row: Row) -> str:
    """One stellar-mass entry in words, e.g. "0.56 +0.06/-0.06 from Xie 2014" (solar masses)."""
    text = f"{row['st_mass']:g}"
    e1, e2 = row.get("st_masserr1"), row.get("st_masserr2")
    if e1 is not None and e2 is not None:
        text += f" +{abs(e1):g}/-{abs(e2):g}"
    return f"{text} from {parse_reflink(row.get('st_mass_reflink'))[0] or 'an unnamed source'}"


def _star_mass_flag(rows: Sequence[Row], chosen: Row) -> CompletionFlag | None:
    """Flag listing the stellar masses of the planet rows when they disagree."""
    usable = _star_mass_rows(rows)
    groups: dict[tuple[float, str, str, str], list[Row]] = {}
    for r in usable:
        groups.setdefault(_star_mass_key(r), []).append(r)
    if len(groups) < 2:
        return None
    entries = [
        f"{_star_mass_entry(rs[0])} ({', '.join(sorted(str(r['pl_name']) for r in rs))})"
        for _, rs in sorted(groups.items())
    ]
    pool, paper = _star_mass_pool(rows)
    values = sorted(float(r["st_mass"]) for r in pool)
    split = values[(len(values) - 1) // 2] != values[len(values) // 2]  # even count, two middle values differ
    even = " (the lower of the two middle values, the less stable choice)" if split else ""
    if paper is not None:
        planets = sorted(
            str(r["pl_name"])
            for r in _measured_mass_rows(rows)
            if parse_reflink(r.get("pl_bmasse_reflink"))[0] == paper
        )
        why = f"the stellar mass of the publication of the measured masses of {', '.join(planets)}" + (
            f", the median of its rows{even}" if len(set(values)) > 1 else ""
        )
    else:
        why = f"the median of the rows{even}"
    return _flag(
        None,
        "st_mass",
        "star_mass_inconsistent",
        f"The planet rows give different stellar masses in solar masses: {'; '.join(entries)}. Used: "
        f"{_star_mass_entry(chosen)}, {why}. Planet masses derived with another stellar mass are not "
        "rescaled.",
    )


def complete_star(rows: Sequence[Row]) -> tuple[Star, list[CompletionFlag]]:
    r0 = rows[0]
    host = str(r0["hostname"])
    flags: list[CompletionFlag] = []
    if any(r.get("cb_flag") == 1 for r in rows):
        raise IncompleteSystemError(
            f"{host} is a circumbinary system; exostab models a single host star and cannot check it."
        )
    # A limit on the stellar mass is not used: drawing the mass uniformly below an upper limit gives stars of
    # almost no mass, and the limit itself is the most stable choice (Hill radii scale as M*^(-1/3)).
    limits = [r for r in rows if r.get("st_mass") is not None and r.get("st_masslim") in (1, -1)]
    chosen = star_mass_row(rows)
    if chosen is None and limits:
        raise IncompleteSystemError(
            f"{host}: the archive gives only a limit on the stellar mass; supply a measured stellar mass "
            "with --from-file."
        )
    if chosen is None:
        raise IncompleteSystemError(f"{host}: the stellar mass is missing; supply it with --from-file.")
    mass = _value(chosen, "st_mass")
    inconsistent = _star_mass_flag(rows, chosen)
    if inconsistent is not None:
        flags.append(inconsistent)
    if limits:
        flags.append(
            _flag(
                None,
                "st_mass",
                "star_mass_limit_ignored",
                "The rows of "
                + ", ".join(sorted(str(r["pl_name"]) for r in limits))
                + " give only a limit on the stellar mass; the measured value of the other rows is used.",
            )
        )
    n_stars = int(r0.get("sy_snum") or 1)
    if n_stars > 1:
        flags.append(
            _flag(
                None,
                "sy_snum",
                "companion_stars_ignored",
                f"The system has {n_stars} stars; only the host star is modelled. A close stellar "
                "companion could change the dynamics.",
            )
        )
    return Star(name=host, mass_msun=mass, n_stars=n_stars), flags


_PROJECTED_SEPARATION_METHODS = ("Microlensing", "Imaging")


def _period(row: Row, name: str, m_star: float, flags: list[CompletionFlag]) -> Value:
    if row.get("pl_orbper") is not None:
        v = _value(row, "pl_orbper")
        if row.get("pl_orbperlim") in (1, -1):
            kind = "upper" if row["pl_orbperlim"] == 1 else "lower"
            flags.append(
                _flag(
                    name, "pl_orbper", f"period_{kind}_limit", f"Period is a {kind} limit; the limit is used."
                )
            )
        return v
    a = row.get("pl_orbsmax")
    if a is None:
        raise IncompleteSystemError(
            f"{name}: neither the orbital period nor the semi-major axis is published."
        )
    if row.get("discoverymethod") in _PROJECTED_SEPARATION_METHODS:
        # The archive defines pl_orbsmax for these planets as "the projected separation in the plane of the
        # sky" (pscomppars column documentation); some imaging values come from orbit fits, but the table
        # does not say which. A projected separation gives neither the orbit nor the order of the planets.
        raise IncompleteSystemError(
            f"{name}: no orbital period is published, and for a planet found by "
            f"{str(row['discoverymethod']).lower()} the archive's pl_orbsmax = {a:g} AU can be the "
            "projected separation on the sky rather than the semi-major axis, so the orbit cannot be placed. "
            "Supply the orbit with --from-file if a published orbit fit exists."
        )
    m_p = (row.get("pl_bmasse") or 0.0) * MEARTH_IN_MSUN
    P = years_to_days(period_from_semimajor_axis(a, m_star + m_p))
    err = None
    if row.get("pl_orbsmaxerr1") is not None and row.get("pl_orbsmaxerr2") is not None:
        rel = 0.5 * (abs(row["pl_orbsmaxerr1"]) + abs(row["pl_orbsmaxerr2"])) / a
        err = 1.5 * rel * P  # P ~ a^(3/2)
    ref, url = parse_reflink(row.get("pl_orbsmax_reflink"))
    flags.append(
        _flag(
            name,
            "pl_orbper",
            "period_from_semimajor_axis",
            f"Period not published; derived from a = {a:g} AU with Kepler's third law ({P:.4g} d).",
        )
    )
    return Value(
        value=P, err_plus=err, err_minus=err, provenance=Provenance.DERIVED, reference=ref, reference_url=url
    )


_PROV = {
    "Mass": MassKind.TRUE,
    "Msin(i)/sin(i)": MassKind.TRUE,
    "Msini": MassKind.MINIMUM,
    "M-R relationship": MassKind.ESTIMATED,
}


def mass_kind(row: Row) -> MassKind:
    """What the published mass of an archive row means.

    ``pl_bmassprov`` gives the kind, refined with two flags: a transiting planet (``tran_flag = 1``) has an
    inclination close to 90 deg, so its "Msini" is its true mass; a lower limit (``pl_bmasselim = -1``) on the
    mass of a non-transiting planet has an unknown inclination and is in practice an m sin i, so it is a
    minimum mass (relevant for ``--inclination-prior``).
    """
    kind = _PROV.get(row.get("pl_bmassprov") or "Mass", MassKind.TRUE)
    transiting = row.get("tran_flag") == 1
    if kind is MassKind.MINIMUM and transiting:
        return MassKind.TRUE
    if kind is MassKind.TRUE and row.get("pl_bmasselim") == -1 and not transiting:
        return MassKind.MINIMUM
    return kind


def _mass(row: Row, name: str, flags: list[CompletionFlag]) -> tuple[Value, MassKind]:
    if row.get("pl_bmasse") is None:
        radius = row.get("pl_rade")
        if radius is None:
            raise IncompleteSystemError(f"{name}: neither a mass nor a radius is published.")
        try:
            m = mass_from_radius(radius)
        except MassRadiusError as exc:
            raise IncompleteSystemError(f"{name}: mass not published and {exc}") from exc
        flags.append(
            _flag(
                name,
                "pl_bmasse",
                "mass_from_radius_chen_kipping",
                f"Mass not published; estimated as {m:.3g} Earth masses from R = {radius:g} Earth radii "
                "with the Chen & Kipping (2017) mass-radius relation.",
            )
        )
        return Value(
            value=m, provenance=Provenance.ESTIMATED, reference="Chen & Kipping 2017"
        ), MassKind.ESTIMATED
    prov_text = row.get("pl_bmassprov") or "Mass"
    kind = mass_kind(row)
    value = _value(
        row,
        "pl_bmasse",
        provenance=Provenance.ESTIMATED if kind is MassKind.ESTIMATED else Provenance.MEASURED,
    )
    if prov_text == "Msini" and kind is MassKind.TRUE:
        incl = row.get("pl_orbincl")
        flags.append(
            _flag(
                name,
                "pl_bmasse",
                "msini_of_transiting_planet",
                "The archive gives m sin i, but the planet transits"
                + (f" (i = {incl:g} deg)" if incl is not None else "")
                + ", so sin i is close to 1: used as the true mass, not scaled by --inclination-prior.",
            )
        )
    elif kind is MassKind.MINIMUM and prov_text == "Msini":
        flags.append(
            _flag(
                name,
                "pl_bmasse",
                "minimum_mass",
                "Only the minimum mass m sin i is known; it is used as the mass (sin i = 1) unless "
                "--inclination-prior is set.",
            )
        )
    elif kind is MassKind.ESTIMATED:
        flags.append(
            _flag(
                name,
                "pl_bmasse",
                "mass_estimated_by_archive",
                "Mass not measured; the archive estimated it from the planet radius with a mass-radius "
                "relation.",
            )
        )
    elif prov_text == "Msin(i)/sin(i)":
        flags.append(
            _flag(
                name,
                "pl_bmasse",
                "mass_from_msini_and_inclination",
                "Mass computed by the archive from m sin i and a measured inclination.",
            )
        )
    if row.get("pl_bmasselim") == 1:
        value = value.model_copy(update={"provenance": Provenance.UPPER_LIMIT})
        flags.append(
            _flag(
                name,
                "pl_bmasse",
                "mass_upper_limit",
                f"Only an upper limit ({value.value:g} Earth masses) is published; the nominal run uses the "
                "limit, draws are uniform below it.",
            )
        )
    elif row.get("pl_bmasselim") == -1 and kind is MassKind.MINIMUM and prov_text != "Msini":
        flags.append(
            _flag(
                name,
                "pl_bmasse",
                "mass_lower_limit",
                "The mass is a lower limit and the planet does not transit (inclination unknown); the "
                "limit is treated as a minimum mass m sin i: used as the mass (sin i = 1) unless "
                "--inclination-prior is set.",
            )
        )
    elif row.get("pl_bmasselim") == -1:
        flags.append(
            _flag(name, "pl_bmasse", "mass_lower_limit", "The mass is a lower limit; the limit is used.")
        )
    return value, kind


def _eccentricity(row: Row, name: str, flags: list[CompletionFlag]) -> Value:
    if row.get("pl_orbeccen") is None:
        flags.append(
            _flag(name, "pl_orbeccen", "eccentricity_assumed_zero", "Eccentricity not published; assumed 0.")
        )
        return Value(value=0.0, provenance=Provenance.ASSUMED)
    v = _value(row, "pl_orbeccen")
    if not 0 <= v.require() < 1:
        raise IncompleteSystemError(f"{name}: published eccentricity {v.value} is outside [0, 1).")
    if v.require() > E_MAX:
        raise IncompleteSystemError(
            f"{name}: published eccentricity {v.value:g} is above {E_MAX:g}, the largest eccentricity "
            "exostab integrates; the system is not checked rather than checked with a different orbit."
        )
    no_errors = not (row.get("pl_orbeccenerr1") or row.get("pl_orbeccenerr2"))  # missing or zero
    if v.value == 0 and no_errors and row.get("pl_orbeccenlim") not in (1, -1):
        # A measured eccentricity has an uncertainty; exactly 0 without one is a circular orbit that the
        # source fixed in its fit (all eccentricities of the DR25 KOI table, for example). Same as a
        # missing eccentricity: e = 0 in every run, labelled "assumed".
        source = v.reference or "the source"
        flags.append(
            _flag(
                name,
                "pl_orbeccen",
                "eccentricity_fixed_zero_by_source",
                f"Eccentricity published as exactly 0 without an uncertainty ({source}): a circular orbit "
                "fixed in the fit, not a measurement. Treated as assumed: e = 0 in every run.",
            )
        )
        return v.model_copy(update={"provenance": Provenance.ASSUMED})
    if row.get("pl_orbeccenlim") == 1:
        flags.append(
            _flag(
                name,
                "pl_orbeccen",
                "eccentricity_upper_limit",
                f"Only an upper limit e < {v.value:g} is published; the nominal run uses the limit, draws are "
                "uniform below it.",
            )
        )
        return v.model_copy(update={"provenance": Provenance.UPPER_LIMIT})
    if row.get("pl_orbeccenlim") == -1:
        flags.append(
            _flag(
                name,
                "pl_orbeccen",
                "eccentricity_lower_limit",
                "The eccentricity is a lower limit; the limit is used.",
            )
        )
    return v


def _omega(row: Row, name: str, flags: list[CompletionFlag]) -> Value:
    if row.get("pl_orblper") is None:
        flags.append(
            _flag(
                name,
                "pl_orblper",
                "omega_randomized",
                "Argument of periastron not published; drawn uniformly in [0, 360) deg for every run.",
            )
        )
        return Value(provenance=Provenance.RANDOMIZED)
    return _value(row, "pl_orblper")


def _same_reference(row: Row, base: str) -> bool:
    return parse_reflink(row.get(base + "_reflink"))[0] == parse_reflink(row.get("pl_orbper_reflink"))[0]


def _phase(row: Row, name: str, duplicated_tper: bool, flags: list[CompletionFlag]) -> Phase:
    has_tranmid = row.get("pl_tranmid") is not None
    transiting = row.get("tran_flag") == 1
    if has_tranmid and transiting:
        note = ""
        if not _same_reference(row, "pl_tranmid"):
            note = " (transit time and period come from different publications)"
        flags.append(
            _flag(
                name,
                "pl_tranmid",
                "phase_from_transit",
                f"Orbital phase set from the transit mid-time, propagated with the period{note}.",
            )
        )
        return Phase(kind=PhaseKind.TRANSIT, value=_value(row, "pl_tranmid"))
    if has_tranmid and _same_reference(row, "pl_tranmid"):
        flags.append(
            _flag(
                name,
                "pl_tranmid",
                "phase_from_conjunction",
                "Orbital phase set from the published time of inferior conjunction.",
            )
        )
        return Phase(kind=PhaseKind.TRANSIT, value=_value(row, "pl_tranmid"))
    usable_tper = (
        row.get("pl_orbtper") is not None and _same_reference(row, "pl_orbtper") and not duplicated_tper
    )
    if usable_tper and row.get("pl_orblper") is not None:
        flags.append(
            _flag(
                name,
                "pl_orbtper",
                "phase_from_periastron",
                "Orbital phase set from the published time of periastron.",
            )
        )
        return Phase(kind=PhaseKind.PERIASTRON, value=_value(row, "pl_orbtper"))
    if usable_tper:
        # A time of periastron fixes the mean anomaly, but the periastron direction (omega) is drawn at
        # random, so the planet's mean longitude, and every angle between planets, would be random in
        # every run.
        why = (
            "a time of periastron is published but not the argument of periastron, so the direction of the "
            "periastron, and with it the planet's position relative to the other planets, is unknown"
        )
    elif row.get("pl_orbtper") is not None and duplicated_tper:
        why = (
            "several planets share the same published time of periastron, which is likely an epoch "
            "rather than a periastron time"
        )
    elif has_tranmid or row.get("pl_orbtper") is not None:
        why = "the published reference time comes from a different publication than the period"
    else:
        why = "no transit, conjunction or periastron time is published"
    flags.append(
        _flag(name, "phase", "phase_randomized", f"Orbital phase drawn uniformly for every run: {why}.")
    )
    return Phase(kind=PhaseKind.RANDOM)


def complete_planets(rows: Sequence[Row], m_star: float) -> tuple[list[Planet], list[CompletionFlag]]:
    """Planets (ordered by period) and the completion flags raised while building them."""
    flags: list[CompletionFlag] = []
    tpers = [r.get("pl_orbtper") for r in rows if r.get("pl_orbtper") is not None]
    planets = []
    for r in rows:
        name = str(r["pl_name"])
        period = _period(r, name, m_star, flags)
        mass, kind = _mass(r, name, flags)
        planets.append(
            Planet(
                name=name,
                archive_name=name,
                period_days=period,
                mass_earth=mass,
                mass_kind=kind,
                eccentricity=_eccentricity(r, name, flags),
                omega_deg=_omega(r, name, flags),
                phase=_phase(r, name, tpers.count(r.get("pl_orbtper")) > 1, flags),
                radius_earth=_value(r, "pl_rade") if r.get("pl_rade") is not None else None,
                inclination_deg=_value(r, "pl_orbincl") if r.get("pl_orbincl") is not None else None,
                semimajor_axis_au=_value(r, "pl_orbsmax") if r.get("pl_orbsmax") is not None else None,
            )
        )
        if r.get("pl_controv_flag") == 1:
            flags.append(
                _flag(
                    name,
                    "pl_controv_flag",
                    "controversial_planet",
                    "The archive flags this planet as controversial (its existence has been questioned).",
                )
            )
    planets.sort(key=lambda p: p.period_days.require())
    return planets, flags


def coplanar_flag() -> CompletionFlag:
    return _flag(
        None,
        "inclination",
        "coplanar_assumed",
        "All orbits are placed in one plane. Mutual inclinations are not published (sky-plane inclinations "
        "do not determine them), and longitudes of the ascending node are not used.",
    )


def period_from_a_days(a_au: float, m_total_msun: float) -> float:
    return years_to_days(period_from_semimajor_axis(a_au, m_total_msun))
