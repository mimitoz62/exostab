---
description: >-
  The exostab web app runs the same stability analysis as the command line in a browser: search a system, edit its
  parameters, try what-if changes, and download the report and figures.
---

# Web app

The web app runs the same analysis as `exostab check` in a browser: search a system, edit its parameters, try
"what if" changes, and download the report and figures. There is no permanent hosted version. You can run it on your
own computer, or try it without installing it:

- [Binder](https://mybinder.org/v2/gh/mimitoz62/exostab/main?urlpath=exostab/) needs no account. The first start can
  take several minutes, and the session ends after 10 minutes without activity.
- [GitHub Codespaces](https://codespaces.new/mimitoz62/exostab?quickstart=1) needs a GitHub account and uses your free
  monthly hours.

A shareable link made in either of them points at that session: it works only while the session runs, and other people
may not be able to open it.

## Running it locally

In the virtual environment from the [Quickstart](quickstart.md#install):

```bash
pip install "exostab[web] @ git+https://github.com/mimitoz62/exostab@v1.0.0"
python -m exostab.web
```

If Streamlit asks for an email address, press Enter. Then open http://localhost:8501. Options after the command go to
`streamlit run` (for example `python -m exostab.web --server.port 8502`). In a clone of the repository,
`streamlit run streamlit_app.py` does the same.

## Using it

1. **Pick a system** in the sidebar. The search box filters as you type. Names are the archive's: Kepler-90, for
   example, is listed as KOI-351. Data come from the NASA Exoplanet Archive or from the offline snapshot of 22
   systems. The archive table is downloaded on first use and then
   reused from the same cache folder as the command line; the app does not download it again by itself. Running
   `exostab check --refresh` on the same computer updates the cache, and the app picks the new table up within a
   day or when it is restarted. If the archive cannot be reached and there is no cache, the app uses the snapshot
   and says so. The data date is shown above the parameter table.
2. **Edit parameters** in the table if you want: period, mass, eccentricity (up to 0.95), argument of periastron.
   Leave ω empty to draw it at random. The published uncertainties are kept for the Monte Carlo draws, and every
   change is listed in the report.
3. **What if?** Use the sliders to scale one planet's mass, set its eccentricity (up to 0.95), or move it to a
   different period ratio with the planet just inside it, after your table edits. A slider changes the planet
   only when you move it.
4. **Choose a time budget** (5–120 s) and press **Run**. The app measures how fast this system integrates and
   picks the run length and number of draws that fit (see [`--budget`](cli.md)). It always integrates in a single
   process, also when run locally, so a given budget covers fewer orbits and draws than `exostab check --budget`
   on a multi-core computer. A verdict here can therefore differ from `exostab check`, which uses 20 draws by
   default, and from the [catalog](catalog.md), which uses 10.
5. **Read the result.** It shows the overall verdict, the indicators with their explanations, the
   data-completion rules that were applied, and interactive figures (orbits, MEGNO over time, all draws).
6. **Download** `report.json`, `orbits.png` and `megno.png`, or copy the **shareable link**.

The run length chosen for a budget and the results are cached by a SHA-256 hash of every input, so a repeated
view, a reload or the same link opened again on the same server is instant.

## What a shared link pins

A link encodes the system name, the data source (archive or snapshot), your table edits and what-if changes, the
time budget, the seed, the treatment of minimum masses, whether SPOCK was added, and the run length (orbits and
draws). Values that the app's own controls cannot produce are not used: the budget is clamped to 5–120 s, and an
invalid seed, run length, table edit or what-if change falls back to the default.

A link does not pin:

- **the data.** It holds no parameter values and no download date, so it runs on the archive table of the server
  that opens it. On another computer, or after the cache was refreshed, the table can differ. The data date and
  the input hash shown with the result tell whether two runs used the same inputs. For a fixed data set, choose
  the offline snapshot; the published values used in a run are in its `report.json`.
- **the run length, if it is too expensive.** The link's run length is used only if, at the speed measured on the
  server that opens it, it is estimated to take at most 120 s (the largest budget). Otherwise the run length is
  chosen for the link's budget on that server, and a note says so. When a link's run length is used as given,
  the report does not claim that a budget chose it.

## Hosting

The repository is prepared for [Streamlit Community Cloud](https://streamlit.io/cloud), which hosts public apps
from public GitHub repositories for free, but no hosted instance exists yet. Its documented resources are
0.078–2 CPU cores and 690 MB–2.7 GB of memory, and apps without traffic for 12 hours go to sleep until someone
wakes them. Deployment uses:

- entry point `streamlit_app.py`;
- dependencies from the root `requirements.txt` (`streamlit==1.64.0` and `.[web]`);
- Python 3.12, chosen under "Advanced settings";
- settings from `.streamlit/config.toml`.

`RELEASING.md` in the repository describes the setup. Hugging Face Spaces was the planned fallback, but since
July 2026 Streamlit/Docker Spaces need a paid plan (checked 2026-09-28).
