---
title: Command line reference for check, sweep, list and catalog
description: >-
  The options of exostab's commands: check for the report card of one system, sweep to vary one parameter of one
  planet, list to find systems in the NASA Exoplanet Archive, and catalog for batch runs.
---

# CLI reference

Is this planetary system dynamically stable? Hill spacing, AMD and N-body/MEGNO indicators for known exoplanet systems, with every assumption shown.

**Usage**:

```console
$ exostab [OPTIONS] COMMAND [ARGS]...
```

**Options**:

* `--version`: Show the version and exit.
* `--help`: Show this message and exit.

Web app: python -m exostab.web (needs the \[web] extra: https://mimitoz62.github.io/exostab/quickstart/).

**Commands**:

* `check`: Stability report card for one system.
* `sweep`: Vary one parameter of one planet.
* `list`: List multi-planet systems in the archive.
* `catalog`: Batch stability catalog of archive systems.

## `exostab check`

Stability report card for one system (archive name or --from-file).

**Usage**:

```console
$ exostab check [OPTIONS] [name]
```

**Arguments**:

* `name`: Host or planet name, e.g. &quot;TRAPPIST-1&quot;.

**Options**:

* `--from-file <file>`: Read the system from a YAML file instead of the archive.
* `--orbits <float range>`: N-body run length, in orbits of the innermost planet [default: 10000].  [x&gt;=10]
* `--draws <int range>`: Monte Carlo draws within the published uncertainties [default: 20]. With 0 nothing is tested against the uncertainties, and the overall verdict is never stable or unstable.  [x&gt;=0]
* `--budget <str>`: Choose --orbits and --draws to fit a wall-clock budget: &#x27;fast&#x27; (about 10 s), &#x27;thorough&#x27; (about 2 min) or a number of seconds.
* `--seed <int range>`: Random seed: the same seed gives the same draws and, on the same platform and software versions, the same results.  [default: 0; x&gt;=0]
* `--out <path>`: Output folder (default: exostab-results/&lt;system&gt;).
* `--inclination-prior <none|isotropic>`: For minimum masses: &#x27;none&#x27; uses m sin i as the mass; &#x27;isotropic&#x27; draws the inclination (cos i uniform, sin i &gt;= 0.1) in every draw.  [default: none]
* `--no-ias15`: Skip the IAS15 check of the nominal run.
* `--no-plots`: Do not write PNG figures.
* `--spock`: Add SPOCK&#x27;s machine-learned classifier (3+ planets). Needs a separate SPOCK environment, built by scripts/make_spock_env.sh (https://github.com/mimitoz62/exostab/blob/main/scripts/make_spock_env.sh); its python is taken from --spock-python or EXOSTAB_SPOCK_PYTHON.
* `--spock-python <str>`: Python interpreter of the SPOCK environment.
* `-j, --jobs <int range>`: Worker processes (default: all cores but one).  [x&gt;=1]
* `--refresh`: Query the archive again instead of using the disk cache.
* `--offline`: Use only the bundled offline snapshot (22 systems).
* `--help`: Show this message and exit.

## `exostab sweep`

Vary one parameter of one planet and record every indicator (nominal parameters otherwise).

**Usage**:

```console
$ exostab sweep [OPTIONS] [name]
```

**Arguments**:

* `name`: Host or planet name.

**Options**:

* `--planet <str>`: Planet letter or full name, e.g. &#x27;b&#x27;.  [default: b]
* `--param <e|mass|period|omega>`: e (eccentricity), mass (Earth masses), period (days) or omega (deg).  [default: e]
* `--range <float float>...`: Start and end values, in the unit of --param [default for e: 0 0.5; required for mass, period and omega].
* `--steps <int range>`: Number of values.  [default: 25; x&gt;=2]
* `--from-file <file>`: Read the system from a YAML file instead of the archive.
* `--orbits <float range>`: N-body run length, in orbits of the innermost planet.  [default: 10000.0; x&gt;=10]
* `--seed <int range>`: Random seed: the same seed gives the same draws and, on the same platform and software versions, the same results.  [default: 0; x&gt;=0]
* `--out <path>`: Output folder (default: exostab-results/&lt;system&gt;).
* `-j, --jobs <int range>`: Worker processes (default: all cores but one).  [x&gt;=1]
* `--refresh`: Query the archive again instead of using the disk cache.
* `--offline`: Use only the bundled offline snapshot (22 systems).
* `--help`: Show this message and exit.

## `exostab list`

List multi-planet systems in the archive table.

**Usage**:

```console
$ exostab list [OPTIONS]
```

**Options**:

* `--min-planets <int range>`: Minimum number of planets.  [default: 2; x&gt;=2]
* `--max-period-days <float>`: Only systems whose planets all have periods below this (days).
* `--limit <int range>`: Show at most this many systems (0: all).  [default: 0; x&gt;=0]
* `--refresh`: Query the archive again instead of using the disk cache.
* `--offline`: Use only the bundled offline snapshot (22 systems).
* `--help`: Show this message and exit.

## `exostab catalog`

Batch stability catalog of archive systems.

**Usage**:

```console
$ exostab catalog [OPTIONS] COMMAND [ARGS]...
```

**Options**:

* `--help`: Show this message and exit.

**Commands**:

* `build`: Compute the catalog of multi-planet systems.

### `exostab catalog build`

Compute indicators for the multi-planet systems and write catalog.csv (+ catalog.parquet).

**Usage**:

```console
$ exostab catalog build [OPTIONS]
```

**Options**:

* `--limit <int range>`: Process at most this many systems (0: all).  [default: 0; x&gt;=0]
* `--out <path>`: Output folder.  [default: catalog]
* `--orbits <float range>`: N-body run length, in orbits of the innermost planet.  [default: 10000.0; x&gt;=10]
* `--draws <int range>`: Monte Carlo draws per system (with 0 no overall verdict is stable or unstable).  [default: 10; x&gt;=0]
* `--seed <int range>`: Random seed: the same seed gives the same draws and, on the same platform and software versions, the same results.  [default: 0; x&gt;=0]
* `--max-seconds <float range>`: Wall-clock cap per system; systems that exceed it are recorded as &#x27;timeout&#x27;.  [default: 120.0; x&gt;=1]
* `-j, --jobs <int range>`: Worker processes (default: all cores but one).  [x&gt;=1]
* `--refresh`: Query the archive again instead of using the disk cache.
* `--offline`: Use only the bundled offline snapshot (22 systems).
* `--help`: Show this message and exit.
