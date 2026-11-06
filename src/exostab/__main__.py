"""``python -m exostab``: the command line, for when the ``exostab`` script is not on PATH."""

from .cli import app

if __name__ == "__main__":  # pragma: no cover
    app(prog_name="exostab")
