"""Markdown notes for the GitHub release "catalog" (run: python scripts/catalog_release_notes.py catalog/)."""

from __future__ import annotations

import csv
import json
import sys
from collections import Counter
from pathlib import Path


def notes(folder: Path) -> str:
    meta = json.loads((folder / "catalog_meta.json").read_text(encoding="utf-8"))
    rows = list(csv.DictReader((folder / "catalog.csv").open(encoding="utf-8")))
    counts = Counter(r["overall"] if r["status"] == "ok" else r["status"] for r in rows)
    s = meta["settings"]
    lines = [
        f"Stability indicators for {meta['n_systems']} multi-planet systems of the NASA Exoplanet Archive "
        f"(Planetary Systems Composite Parameters, downloaded {(meta.get('data_retrieved_utc') or '?')[:10]}), "
        f"computed {meta['created_utc'][:10]} with exostab {meta['exostab_version']}.",
        "",
        f"Settings: {s['orbits']:,.0f} orbits of the innermost planet, {s['draws']} Monte Carlo draws, seed "
        f"{s['seed']}, at most {s['max_seconds']:g} s per system.",
        "",
        "Overall verdicts: "
        + ", ".join(f"{k}: {v}" for k, v in sorted(counts.items(), key=lambda kv: -kv[1]))
        + ".",
        "",
        "`catalog.csv`, `catalog.parquet` and `catalog_meta.json` are the latest version; files with a date in "
        "their name are kept for reference. Column definitions and caveats: "
        "https://mimitoz62.github.io/exostab/catalog/",
        "",
        "The catalog data are licensed under CC BY 4.0: see `LICENSE`.",
        "",
        "This research has made use of the NASA Exoplanet Archive, which is operated by the California Institute "
        "of Technology, under contract with the National Aeronautics and Space Administration under the "
        "Exoplanet Exploration Program.",
    ]
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    sys.stdout.write(notes(Path(sys.argv[1])))
