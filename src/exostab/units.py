"""Unit conversions between published values and the simulation unit system.

All simulations use years, astronomical units and solar masses (REBOUND ``sim.units = ("yr", "AU",
"Msun")``). Published values are converted with :mod:`astropy.units` so that the conversion factors
have a single, documented origin. The year is the Julian year (365.25 days) in both astropy and
REBOUND; ``tests/test_units.py`` checks that the two libraries agree on G in these units.
"""

from __future__ import annotations

import math

import astropy.constants as const
import astropy.units as u

SIM_UNITS = ("yr", "AU", "Msun")

DAY_IN_YR: float = float((1 * u.day).to(u.yr).value)
MEARTH_IN_MSUN: float = float((1 * u.M_earth).to(u.M_sun).value)
MJUP_IN_MSUN: float = float((1 * u.M_jup).to(u.M_sun).value)
MJUP_IN_MEARTH: float = float((1 * u.M_jup).to(u.M_earth).value)
REARTH_IN_RJUP: float = float((1 * u.R_earth).to(u.R_jup).value)

# Gravitational constant in AU^3 / (Msun yr^2).
G_SIM: float = float(const.G.to(u.au**3 / (u.M_sun * u.yr**2)).value)


def format_years(t: float) -> str:
    """Human-readable time span: "41.4 yr", "14,634 yr", "1.2e+07 yr"."""
    if t < 100:
        return f"{t:.3g} yr"
    if t < 1e7:
        return f"{t:,.0f} yr"
    return f"{t:.3g} yr"


def format_count(n: float) -> str:
    """Human-readable count: "10,000", "1e+07"."""
    return f"{n:,.0f}" if n < 1e7 else f"{n:.3g}"


def format_orbits(n: float) -> str:
    """A number of completed orbits, rounded down to one decimal: 99.96 orbits are not yet "100"."""
    return f"{math.floor(n * 10) / 10:g}"


def days_to_years(days: float) -> float:
    return days * DAY_IN_YR


def years_to_days(years: float) -> float:
    return years / DAY_IN_YR


def mearth_to_msun(m: float) -> float:
    return m * MEARTH_IN_MSUN


def msun_to_mearth(m: float) -> float:
    return m / MEARTH_IN_MSUN


def period_from_semimajor_axis(a_au: float, total_mass_msun: float) -> float:
    """Kepler's third law: orbital period in years for semi-major axis ``a_au`` (AU)."""
    return 2 * math.pi * math.sqrt(a_au**3 / (G_SIM * total_mass_msun))


def semimajor_axis_from_period(p_yr: float, total_mass_msun: float) -> float:
    """Kepler's third law: semi-major axis in AU for period ``p_yr`` (years)."""
    return float((G_SIM * total_mass_msun * p_yr**2 / (4 * math.pi**2)) ** (1 / 3))
