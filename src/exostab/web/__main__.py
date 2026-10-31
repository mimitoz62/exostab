"""``python -m exostab.web``: start the web app from an installed package with the ``[web]`` extra.

It runs ``streamlit run`` on the packaged copy of ``streamlit_app.py``; extra arguments are passed on, e.g.
``python -m exostab.web --server.port 8502``. They come after the launcher's own settings, so they can
override them.
"""

from __future__ import annotations

import sys
from pathlib import Path

SCRIPT = Path(__file__).with_name("streamlit_app.py")
# The wheel has no .streamlit/config.toml, so these are its settings. Without them, the first run outside a
# clone stops at Streamlit's email prompt, and nothing is served until Enter is pressed; usage statistics are on
# and the toolbar has a Deploy button. In headless mode no browser opens: the terminal shows the address.
SETTINGS = [
    "--server.headless",
    "true",
    "--browser.gatherUsageStats",
    "false",
    "--client.toolbarMode",
    "viewer",
]
# exostab is installed from GitHub, not PyPI, so the hint points to the install commands instead of naming one
MISSING = (
    "The web app needs the optional [web] extra (Streamlit and Plotly). Install it in the same way as exostab, "
    'with "exostab[web]" in place of "exostab": https://mimitoz62.github.io/exostab/quickstart/'
)


def main(args: list[str] | None = None) -> int:
    try:
        import streamlit.web.cli as stcli
    except ImportError:
        print(MISSING, file=sys.stderr)
        return 1
    sys.argv = ["streamlit", "run", str(SCRIPT), *SETTINGS, *(sys.argv[1:] if args is None else args)]
    stcli.main()  # a click command: it exits with Streamlit's exit code
    return 0


if __name__ == "__main__":
    sys.exit(main())
