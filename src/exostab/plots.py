"""Figures: ``orbits.png``, ``megno.png`` and ``sweep.png``.

Colours: planets use a fixed categorical order (blue, orange, aqua, yellow, magenta, green, violet,
red) so that planet b always has the same colour; run classifications use a status palette and always
come with a distinct marker shape and a legend label, so no information is carried by colour alone.
"""

from __future__ import annotations

import math
import os
import warnings
from collections.abc import Sequence
from pathlib import Path
from typing import IO, TYPE_CHECKING, Any, TypeVar, cast

# matplotlib validates this variable when it is imported, and exostab only ever uses Agg (below).
os.environ.pop("MPLBACKEND", None)

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import numpy.typing as npt

from .indicators.megno import MEGNO_CHAOTIC, classify_run
from .integrate import RunResult
from .sampling import Realization
from .units import format_years

if TYPE_CHECKING:
    from .analysis import CheckResult

Target = TypeVar("Target", Path, IO[bytes])  # a file path, or an open binary stream (web downloads)

PLANET_COLORS = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#4a3aa7", "#e34948"]
STATUS = {
    "regular": ("#0ca30c", "o", "regular"),
    "chaotic": ("#fab219", "s", "chaotic"),
    "unstable": ("#d03b3b", "X", "close encounter / escape"),
    "inconclusive": ("#8a8984", "D", "inconclusive"),
}
INK, MUTED, GRID = "#0b0b0b", "#52514e", "#e4e3df"
MEGNO_CLIP = 8.0

_RC = {
    "font.size": 9,
    "axes.edgecolor": MUTED,
    "axes.labelcolor": INK,
    "axes.linewidth": 0.6,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.grid": True,
    "grid.color": GRID,
    "grid.linewidth": 0.6,
    "xtick.color": MUTED,
    "ytick.color": MUTED,
    "legend.frameon": False,
    "savefig.dpi": 150,
    "savefig.bbox": "tight",
    "figure.facecolor": "white",
}


def _plotted_megno(megno: float | None, cls: str) -> float:
    """<Y> as plotted: runs stopped by an encounter, and non-finite values, sit at MEGNO_CLIP."""
    if cls == "unstable" or megno is None or not math.isfinite(megno):
        return MEGNO_CLIP
    return min(megno, MEGNO_CLIP)


def _plotted_beta(betas: npt.ArrayLike) -> tuple[npt.NDArray[np.float64], float, float]:
    """AMD ratios as plotted on a log axis, with the axis limits. A log axis can show neither β = ∞
    (resonances overlap even on circular orbits) nor β = 0 (no AMD: circular, coplanar orbits), so they sit
    at the top and bottom edges."""
    b = np.asarray(betas, dtype=float)
    shown = np.append(b[np.isfinite(b) & (b > 0)], 1.0)  # the AMD-stability limit is always in view
    lo, hi = float(shown.min()) / 3, float(shown.max()) * 3
    return np.where(np.isposinf(b), hi, np.where(b == 0, lo, b)), lo, hi


def _plain(text: str) -> str:
    """A name in a title or a label: "$" is not mathtext here, which would fail or change the name."""
    return text.replace("$", r"\$")


def _label(name: str) -> str:
    """A legend label: matplotlib leaves out labels that start with an underscore."""
    return _plain(" " + name if name.startswith("_") else name)


def _save(fig: Any, path: Any, **kwargs: Any) -> None:
    """Save without one warning per character the font lacks: a non-Latin name still gets its figure."""
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", message="Glyph .* missing from font", category=UserWarning)
        fig.savefig(path, **kwargs)


def planet_color(k: int) -> str:
    return PLANET_COLORS[k % len(PLANET_COLORS)]


def _ellipse(
    a: float, e: float, pomega: float, n: int = 400
) -> tuple[npt.NDArray[np.float64], npt.NDArray[np.float64]]:
    f = np.linspace(0, 2 * np.pi, n)
    r = a * (1 - e**2) / (1 + e * np.cos(f))
    return r * np.cos(f + pomega), r * np.sin(f + pomega)


def orbits_figure(nominal: Realization, run: RunResult, title: str, path: Target) -> Target:
    """Top-down view: initial orbits (lines) and positions sampled during the nominal run (dots)."""
    a = nominal.semi_major_axes()
    with plt.rc_context(cast(Any, _RC)):
        fig, ax = plt.subplots(figsize=(6.2, 6.0))
        ax.plot(0, 0, marker="*", ms=12, color="#eda100", mec=INK, mew=0.5, zorder=5, ls="none")
        for k, b in enumerate(nominal.bodies):
            c = planet_color(k)
            x, y = _ellipse(float(a[k]), b.e, b.pomega)
            ax.plot(x, y, color=c, lw=1.4, label=_label(b.name), zorder=3)
            xs, ys = run.series.get(f"x{k}"), run.series.get(f"y{k}")
            if xs and ys:
                ax.scatter(xs, ys, s=4, color=c, alpha=0.35, lw=0, zorder=2)
        lim = 1.15 * max(float(a[k]) * (1 + b.e) for k, b in enumerate(nominal.bodies))
        if run.series.get("x0"):
            pts = [
                abs(v) for k in range(len(nominal.bodies)) for v in run.series[f"x{k}"] + run.series[f"y{k}"]
            ]
            lim = max(lim, 1.05 * max(pts))
        ax.set_xlim(-lim, lim)
        ax.set_ylim(-lim, lim)
        ax.set_aspect("equal")
        ax.set_xlabel("x (AU)")
        ax.set_ylabel("y (AU)")
        status = {
            "completed": "",
            "encounter": " — stopped at a close encounter",
            "escape": " — stopped at an escape",
        }
        ax.set_title(
            f"{_plain(title)}: nominal orbits (lines) and positions over {format_years(run.t_end)} (dots)"
            f"{status.get(run.status, '')}",
            fontsize=9,
            color=INK,
            loc="left",
        )
        ax.legend(loc="upper right", fontsize=8, ncol=1 if len(nominal.bodies) <= 4 else 2)
        _save(fig, path, format="png")
        plt.close(fig)
    return path


def megno_figure(runs: Sequence[RunResult], ias15: RunResult | None, title: str, path: Target) -> Target:
    """MEGNO and energy error of the nominal run over time, and the final <Y> of every run."""
    nominal = runs[0]
    with plt.rc_context(cast(Any, _RC)):
        fig = plt.figure(figsize=(10, 5.2))
        gs = fig.add_gridspec(2, 2, width_ratios=[1.35, 1], height_ratios=[1.6, 1], hspace=0.12, wspace=0.28)
        ax_y = fig.add_subplot(gs[0, 0])
        ax_e = fig.add_subplot(gs[1, 0], sharex=ax_y)
        ax_d = fig.add_subplot(gs[:, 1])
        t = np.asarray(nominal.series.get("t", []))
        if t.size:
            ax_y.plot(
                t,
                np.minimum(nominal.series["megno"], MEGNO_CLIP),
                color=PLANET_COLORS[0],
                lw=1.6,
                label=f"WHFast (nominal, <Y> = {nominal.megno:.3f})",
            )
            ax_e.semilogy(
                t[1:], np.maximum(nominal.series["energy_error"][1:], 1e-17), color=PLANET_COLORS[0], lw=1.2
            )
        if ias15 is not None and ias15.series.get("t"):
            ax_y.plot(
                ias15.series["t"],
                np.minimum(ias15.series["megno"], MEGNO_CLIP),
                color=PLANET_COLORS[1],
                lw=1.4,
                ls="--",
                label=f"IAS15 check (<Y> = {ias15.megno:.3f})",
            )
            ax_e.semilogy(
                ias15.series["t"][1:],
                np.maximum(ias15.series["energy_error"][1:], 1e-17),
                color=PLANET_COLORS[1],
                lw=1.0,
                ls="--",
            )
        ax_y.axhline(2.0, color=MUTED, lw=0.8, ls=":")
        ax_y.axhline(MEGNO_CHAOTIC, color=MUTED, lw=0.8, ls="--")
        ax_y.text(
            0.995,
            MEGNO_CHAOTIC,
            f"chaotic above {MEGNO_CHAOTIC:g} ",
            color=MUTED,
            fontsize=7.5,
            va="bottom",
            ha="right",
            transform=ax_y.get_yaxis_transform(),
        )
        ax_y.set_ylabel("MEGNO <Y>")
        ax_y.set_title(f"{_plain(title)}: nominal run", fontsize=9, loc="left", color=INK)
        ax_y.legend(loc="lower right", fontsize=7.5)
        plt.setp(ax_y.get_xticklabels(), visible=False)
        ax_e.set_ylabel("|ΔE / E|")
        ax_e.set_xlabel("time (yr)")

        classes = [classify_run(r) for r in runs[1:]]
        ys = [_plotted_megno(r.megno, c) for r, c in zip(runs[1:], classes, strict=True)]
        order = np.argsort(ys)
        for cls, (color, marker, label) in STATUS.items():
            idx = [i for i in range(len(ys)) if classes[order[i]] == cls] if ys else []
            if idx:
                ax_d.scatter(
                    idx,
                    [ys[order[i]] for i in idx],
                    s=26,
                    color=color,
                    marker=marker,
                    lw=0.6,
                    edgecolor="white",
                    label=f"{label} ({len(idx)})",
                    zorder=3,
                )
        ax_d.axhline(MEGNO_CHAOTIC, color=MUTED, lw=0.8, ls="--")
        ax_d.set_xlabel("Monte Carlo draws, sorted by <Y>")
        ax_d.set_ylabel(f"final <Y> (close encounters shown at {MEGNO_CLIP:g})")
        ax_d.set_title(f"{len(ys)} draws within the uncertainties", fontsize=9, loc="left", color=INK)
        if ys:
            ax_d.legend(loc="upper left", fontsize=7.5)
        else:
            ax_d.text(
                0.5,
                0.5,
                "no draws",
                ha="center",
                va="center",
                transform=ax_d.transAxes,
                color=MUTED,
            )
        _save(fig, path, format="png")
        plt.close(fig)
    return path


def sweep_figure(rows: Sequence[dict[str, Any]], param_label: str, title: str, path: Path) -> Path:
    """MEGNO, Hill spacing margin and AMD ratio along a one-parameter sweep."""
    x = np.array([r["value"] for r in rows])
    with plt.rc_context(cast(Any, _RC)):
        fig, axes = plt.subplots(3, 1, figsize=(7.5, 7.2), sharex=True, gridspec_kw={"hspace": 0.12})
        ax = axes[0]
        for cls, (color, marker, label) in STATUS.items():
            sel = [i for i, r in enumerate(rows) if r["nbody_class"] == cls]
            if sel:
                ax.scatter(
                    x[sel],
                    [_plotted_megno(rows[i]["megno"], cls) for i in sel],
                    color=color,
                    marker=marker,
                    s=30,
                    edgecolor="white",
                    lw=0.6,
                    label=label,
                    zorder=3,
                )
        ax.axhline(MEGNO_CHAOTIC, color=MUTED, lw=0.8, ls="--")
        ax.set_ylabel(f"MEGNO <Y>\n(encounters at {MEGNO_CLIP:g})")
        ax.set_title(_plain(title), fontsize=9, loc="left", color=INK)
        ax.legend(fontsize=7.5, loc="upper left")
        ax = axes[1]
        ax.plot(x, [r["hill_margin_min"] for r in rows], color=PLANET_COLORS[0], lw=1.6, marker="o", ms=3)
        ax.axhline(0.0, color=MUTED, lw=0.8, ls="--")
        ax.set_ylabel("Gladman margin,\nclosest pair\n(Hill stable above 0)")
        ax = axes[2]
        beta = np.array([r["amd_beta_max"] for r in rows], dtype=float)
        y, lo, hi = _plotted_beta(beta)
        regular = np.isfinite(beta) & (beta > 0)
        ax.plot(x, np.where(regular, y, np.nan), color=PLANET_COLORS[2], lw=1.6, marker="o", ms=3)
        for edge, marker, label in (
            (np.isposinf(beta), "^", "β = ∞: resonances overlap even on circular orbits (drawn at the top)"),
            (beta == 0, "v", "β = 0: circular, coplanar orbits (drawn at the bottom)"),
        ):
            if edge.any():
                ax.scatter(
                    x[edge],
                    y[edge],
                    color=PLANET_COLORS[2],
                    marker=marker,
                    s=30,
                    label=label,
                    clip_on=False,
                    zorder=3,
                )
        ax.axhline(1.0, color=MUTED, lw=0.8, ls="--")
        ax.set_yscale("log")
        ax.set_ylim(lo, hi)
        ax.set_ylabel("largest AMD ratio β = 2β_p\n(no collisions below 1)")
        if np.isposinf(beta).any() or (beta == 0).any():
            ax.legend(fontsize=7.5, loc="best")
        ax.set_xlabel(_plain(param_label))
        _save(fig, path)
        plt.close(fig)
    return path


def check_figures(result: CheckResult, out_dir: Path) -> list[Path]:
    name = result.report.system.name
    return [
        orbits_figure(result.realizations[0], result.runs[0], name, out_dir / "orbits.png"),
        megno_figure(result.runs, result.ias15, name, out_dir / "megno.png"),
    ]
