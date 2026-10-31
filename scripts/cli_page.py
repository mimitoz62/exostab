"""Write docs/cli.md, the CLI reference: Typer's generated page below its own title and description.

    python scripts/cli_page.py                  # writes docs/cli.md
    python scripts/cli_page.py /tmp/cli.md      # writes a copy, which CI compares with docs/cli.md

Typer's generator writes no front matter, and without a description the page would have the site's in search results.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "docs" / "cli.md"
TYPER_DOCS = ("-m", "typer", "exostab.cli", "utils", "docs", "--name", "exostab", "--title", "CLI reference")

FRONT_MATTER = """---
title: Command line reference for check, sweep, list and catalog
description: >-
  The options of exostab's commands: check for the report card of one system, sweep to vary one parameter of one
  planet, list to find systems in the NASA Exoplanet Archive, and catalog for batch runs.
---

"""


def main() -> None:
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else OUT
    subprocess.run([sys.executable, *TYPER_DOCS, "--output", str(out)], check=True, stdout=subprocess.DEVNULL)
    out.write_text(FRONT_MATTER + out.read_text(encoding="utf-8"), encoding="utf-8")
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
