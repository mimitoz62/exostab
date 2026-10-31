---
title: "Quickstart: check a known multi-planet system"
description: >-
  Try exostab in a browser or install it, then check a known multi-planet system, vary one parameter and find systems
  in the NASA Exoplanet Archive.
---

# Quickstart

## Try it without installing

The [stability catalog](catalog.md) needs nothing: look up a system in the table of the multi-planet systems in the
archive, recomputed every week. To run exostab itself in a browser:

- [Google Colab](https://colab.research.google.com/github/mimitoz62/exostab/blob/main/examples/exostab_quickstart.ipynb)
  runs `exostab check` and `exostab sweep` in a notebook, and needs a Google account.
- [GitHub Codespaces](https://codespaces.new/mimitoz62/exostab?quickstart=1) opens the web app and a copy of the
  repository, needs a GitHub account and uses your free monthly hours.
- [Binder](https://mybinder.org/v2/gh/mimitoz62/exostab/main?urlpath=exostab/) opens the web app and needs no account;
  the first start can take several minutes, and the session ends after 10 minutes without activity.

Colab and Binder install release 1.0.1; a codespace installs the current code of the repository. A shareable link made
in the web app on Binder or in a codespace points at that session: it works only while the session runs, and other
people may not be able to open it.

With [uv](https://docs.astral.sh/uv/) and git, one command runs exostab without a permanent install. It downloads
about 350 MB into uv's cache. `--offline` uses the bundled snapshot of 22 well-known systems; leave it out to use the
live archive.

```bash
uvx --from git+https://github.com/mimitoz62/exostab@v1.0.1 exostab check "TRAPPIST-1" --offline
```

## Install

```bash
python3 --version
python3 -m venv .venv
source .venv/bin/activate
pip install "exostab @ git+https://github.com/mimitoz62/exostab@v1.0.1"
```

This installs release 1.0.1 from GitHub; `pip install git+https://github.com/mimitoz62/exostab` installs the
current development version instead. A release on PyPI is planned. Requires Python 3.10 or newer; exostab is
tested on Linux and macOS. The first line shows your version, and `/usr/bin/python3` on macOS is 3.9. If yours is older
than 3.10, install a newer Python first, for example from [python.org](https://www.python.org/downloads/). In a new
terminal, run the `source` line again.

The `pip` line needs git. Without git, install the wheel of the release; `uvx --from` takes the same URL:

```bash
pip install https://github.com/mimitoz62/exostab/releases/download/v1.0.1/exostab-1.0.1-py3-none-any.whl
```

Optional extras use the same form: `web` adds the web app, and `catalog` the Parquet output of `exostab catalog build`.

```bash
pip install "exostab[web] @ git+https://github.com/mimitoz62/exostab@v1.0.1"
pip install "exostab[catalog] @ git+https://github.com/mimitoz62/exostab@v1.0.1"
```

Without git, put the wheel's URL after the `@`:

```bash
pip install "exostab[web] @ https://github.com/mimitoz62/exostab/releases/download/v1.0.1/exostab-1.0.1-py3-none-any.whl"
```

Without the `[catalog]` extra, `exostab catalog build` writes `catalog.csv` but no `catalog.parquet`, and does not
say so.

## Check a system

```bash
exostab check "TRAPPIST-1"
```

Give a host or planet name as the archive writes it, for example KOI-351 (Kepler-90), GJ 876 (Gliese 876), ups And
(Upsilon Andromedae) or 55 Cnc (55 Cancri); `exostab list` shows the names.

The first run downloads the archive's multi-planet table (about 2,700 rows; 7 s on 13 October 2026) and caches
it. The report card shows:

- the parameters used, with a mark on every value that was assumed, derived, estimated or randomized;
- one verdict per indicator, with an explanation;
- the overall verdict;
- the data-completion rules that were applied.

The folder `exostab-results/trappist-1/` then contains `report.json`, `orbits.png` and `megno.png`.

Useful options:

```bash
exostab check "HD 127195" --orbits 100000 --draws 50 --seed 7 --out results/
exostab check "HD 127195" --inclination-prior isotropic
exostab check "HD 127195" --budget fast
exostab check "Kepler-11" --offline
```

`--inclination-prior isotropic` draws true masses from random inclinations, `--budget fast` chooses the run length and
the number of draws to fit about 10 s, and `--offline` uses the bundled snapshot, with no network.

To check your own parameters, download the example file, which shows every key, and edit it (the `examples/` folder
exists only in a clone of the repository):

```bash
curl -fsSLO https://raw.githubusercontent.com/mimitoz62/exostab/v1.0.1/examples/two_planet.yaml
exostab check --from-file two_planet.yaml
```

## Explore one parameter

```bash
exostab sweep "HD 127195" --planet b --param e --range 0 0.6 --steps 25
```

This writes `sweep.csv`, `sweep.png` and `sweep.json` (seed, run length, range, steps and the command): MEGNO, the
Hill spacing and the AMD ratio as the eccentricity of planet b changes, all other parameters fixed. `--range` is
required for `--param mass`, `period` and `omega`; for `e` it defaults to 0 to 0.5.

## Find systems

```bash
exostab list --min-planets 4 --max-period-days 200
```

## Web app

```bash
python -m exostab.web
```

This starts the browser version locally (it needs the `[web]` extra).
See [Web app](web.md).
