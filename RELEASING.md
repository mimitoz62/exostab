# Releasing exostab

This file is for maintainers. It lists the one-time account setup for each place exostab is published, and the
steps to cut a release. Every service below is optional except GitHub itself: a release that only reaches
GitHub is complete.

## Already set up

- **Documentation** on GitHub Pages: Settings → Pages → Source "GitHub Actions", and the repository variable
  `DEPLOY_DOCS` = `true`. `.github/workflows/docs.yml` deploys https://mimitoz62.github.io/exostab/ on every push
  to `main` and after every weekly catalog.
- **Private vulnerability reporting**, which `SECURITY.md` and the issue template point to.

## PyPI (optional)

`.github/workflows/release.yml` uploads to PyPI with trusted publishing (no API token is stored), but only when
the repository variable `PUBLISH_PYPI` is `true`. Set it up before the tag whose version should be the first on
PyPI; a version already released on GitHub is not uploaded afterwards.

1. Create an account at https://pypi.org/account/register/ and turn on two-factor authentication (PyPI
   requires it for uploads).
2. Open https://pypi.org/manage/account/publishing/ and add a pending publisher for GitHub with exactly:
   - PyPI project name: `exostab`
   - Owner: `mimitoz62`
   - Repository name: `exostab`
   - Workflow name: `release.yml`
   - Environment name: `pypi`

   A pending publisher does not reserve the name; the project is created by the first upload.
3. On GitHub: Settings → Secrets and variables → Actions → Variables → New repository variable `PUBLISH_PYPI`
   with the value `true`.
4. Optional: Settings → Environments → New environment `pypi` → Required reviewers → yourself. Each upload then
   waits for your approval. (Without this step GitHub creates the environment, with no rules, at the first
   upload.)

To pause PyPI uploads, delete the variable or set it to anything other than `true`.

The upload of 1.0.1 on 2026-10-31 failed with `invalid-publisher`, which means PyPI has no pending publisher with
exactly the values of step 2. So `PUBLISH_PYPI` is unset, and 1.0.1 went to GitHub and Zenodo only. To finish: check
step 2 at https://pypi.org/manage/account/publishing/, set the variable, and release the next version, whose install
lines can then say `pip install exostab`.

## Zenodo (software DOI)

Set up on 2026-10-31. With its GitHub integration switched on, Zenodo archives every published GitHub release,
pre-releases included, and gives it a DOI. Its metadata (title, authors with ORCID, license, keywords) come from
`CITATION.cff`.

1. Log in at https://zenodo.org with "Log in with GitHub" and authorize Zenodo.
2. Open https://zenodo.org/account/settings/github/, press "Sync now" if the repository is not listed, and switch
   on `mimitoz62/exostab`. Do this before the first release: earlier releases are not archived.
3. Publish a release (below). The record appears on the same page a few minutes later.
4. The concept DOI, which always resolves to the latest version, is 10.5281/zenodo.23844658. It is in `README.md`
   ("Citing exostab"), `docs/citing.md`, `docs/index.md`, `codemeta.json`, the structured data of `overrides/home.html`
   and, as `doi:`, in `CITATION.cff`.

Do not publish GitHub pre-releases for testing: Zenodo would archive them as versions of exostab.

## Streamlit Community Cloud (web app)

1. Log in at https://share.streamlit.io with "Continue with GitHub" and authorize Streamlit.
2. Create app → "Deploy a public app from GitHub", with:
   - Repository: `mimitoz62/exostab`, branch `main`
   - Main file path: `streamlit_app.py`
   - App URL: `exostab` (https://exostab.streamlit.app, if the name is still free)
   - Advanced settings → Python version: 3.12. No secrets are needed.
3. Deploy. Dependencies come from `requirements.txt` (`streamlit==1.64.0` and `.[web]`), settings from
   `.streamlit/config.toml`. The app redeploys on every push to `main`.
4. Add the app's URL to `README.md` and `docs/web.md`.

## Trying exostab in a browser (Colab, Codespaces, Binder)

No account or setting is needed on the maintainer's side: each service reads its files from the repository
(`examples/exostab_quickstart.ipynb`, `.devcontainer/devcontainer.json` and `.binder/`). The notebook and Binder
install the release they name, and a codespace installs the checkout. Visitors use their own accounts and quotas: a
Google account for Colab, a GitHub account for Codespaces, none for Binder. The workflow `Browser paths` runs the
notebook every night on Python 3.13 on Linux, and the image and commands of `.devcontainer/devcontainer.json` without
the editor around them. It is not part of the nightly validation, because the notebook needs the live archive and the
validation badge should not fail when the archive is down. Nothing runs the Binder files automatically, and the
workflow does not open a real codespace, so the steps below are their only test.

After merging to `main`:

1. Open https://mybinder.org/v2/gh/mimitoz62/exostab/main?urlpath=exostab/ once and wait until the web app appears.
   Binder builds an image for every new commit of `main`. Without this step, the next visitor waits for the build.
2. If `.binder/` changed, press Run in that app and look at the verdict and the figures.
3. If the notebook changed, open
   https://colab.research.google.com/github/mimitoz62/exostab/blob/main/examples/exostab_quickstart.ipynb and use
   Runtime → Run all.
4. If `.devcontainer/` changed, open https://codespaces.new/mimitoz62/exostab?quickstart=1 and press Run in the app
   that opens in the preview. Then delete the codespace at https://github.com/codespaces: it uses your free hours.

## Social preview image

GitHub shows a link-preview image when the repository is shared: Settings → General → Social preview → Edit →
Upload an image, with `docs/assets/social-preview.png` (1280 × 640). The documentation site uses the same file
for its link previews. To redraw it, for example after the logo or the TRAPPIST-1 result changes, run
`python scripts/make_social_preview.py --font-dir <folder with Source Sans 3>`; without that font it falls back to
DejaVu Sans and says so.

## Weekly catalog

`.github/workflows/catalog.yml` runs every Monday at 04:23 UTC with no setup: it recomputes the catalog, commits
`catalog.csv`, `catalog.parquet` and `catalog_meta.json` to the branch `catalog-data`, and starts the docs
workflow so the catalog page is updated. The full log is in the run's `catalog` artifact (`build.log`).

- To run it now: Actions → Weekly catalog → Run workflow, with limit `0` (all systems). A smaller limit
  publishes a partial catalog until the next full run.
- Run it right after pushing a `main` that changes the verdict rules or the catalog columns (as the first push of
  the 1.0.0 code does): until the run finishes (the first two runs took about 70 and 110 minutes), the catalog
  page shows the previous catalog. A catalog computed with a version older than `RULES_VERSION` in
  `scripts/catalog_page.py` is shown with a notice that its rules differ, and the page of changes between catalogs
  leaves it out; raise that constant whenever the rules change again.
- Optional DOI for the catalog (a Zenodo dataset, separate from the software DOI):
  1. After the first full catalog exists, create a new upload on Zenodo with its three files (from the branch
     `catalog-data`), resource type "Dataset", and publish it. Note its record id (the number in
     `https://zenodo.org/records/<id>`).
  2. Zenodo → Applications → Personal access tokens → New token with the scopes `deposit:write` and
     `deposit:actions`.
  3. On GitHub: repository secret `ZENODO_TOKEN` = the token; repository variable `ZENODO_CATALOG_RECORD` = the
     record id. From then on every weekly run publishes a new version of that record
     (`scripts/zenodo_catalog.py`).
  4. Try it on https://sandbox.zenodo.org first (separate account, token and record): also set the variable
     `ZENODO_URL` = `https://sandbox.zenodo.org`, run the workflow, then delete `ZENODO_URL` and switch the
     token and record id to the real ones.
  5. Then add the concept DOI of the real record as `identifier` in `_dataset` of `scripts/catalog_page.py`, and put
     it in `_citation` in place of the sentence that a DOI will follow.
- A docs run that a catalog starts, or that is started by hand, sends the site's URLs to IndexNow
  (`scripts/indexnow.py`, no account) once the site is deployed; a push sends nothing. The log of the job `indexnow`
  should say `IndexNow received <n> URLs (HTTP 200)` or `(HTTP 202)`, which confirms receipt and not indexing. A 403 or
  422 points at the key file (`docs/<key>.txt`) or `keyLocation`. A failed call does not fail the run, so nothing
  announces it: look at that log from time to time.

## Cutting a release

1. Check that CI and the nightly validation suite pass on `main` (Actions tab). The release workflow runs both
   suites again and stops before publishing if either fails.
2. Choose the version `X.Y.Z` ([semantic versioning](https://semver.org/)) and set it in four places:
   - `src/exostab/__init__.py`: `__version__ = "X.Y.Z"`;
   - `CITATION.cff`: `version: "X.Y.Z"` and `date-released: "YYYY-MM-DD"` (the release date);
   - `codemeta.json`: `version` and `datePublished`, the same values;
   - `CHANGELOG.md`: move the entries under "Unreleased" to a new section `## [X.Y.Z] - YYYY-MM-DD`, and copy
     the file to `docs/changelog.md`, below that page's front matter. For 1.0.0 the section
     `## [1.0.0] - unreleased` already exists, below an empty `## [Unreleased]` heading that
     `tests/test_packaging.py` requires while the version is a development version: replace "unreleased" with the
     release date, then copy the file.

   Also change the version in these places:
   - `@v1.0.1` in the install lines of `README.md`, `overrides/home.html`, `docs/index.md`, `docs/quickstart.md` and
     `docs/web.md`, and in the first code cell and the last text cell of `examples/exostab_quickstart.ipynb`;
   - `v1.0.1` and `1.0.1` in the wheel URLs of `README.md`, `docs/quickstart.md` and `.binder/requirements.txt`;
   - `v1.0.1` in the `raw.githubusercontent.com` URLs: the example file in `README.md`, `docs/index.md` and
     `docs/quickstart.md`, and the SPOCK script in `README.md`;
   - "release 1.0.1" in the text of `README.md` and `docs/quickstart.md`, and "Version 1.0.1" in `overrides/home.html`;
   - `"version": "1.0.1"` in the structured data of `overrides/home.html`.

   Re-read the notebook's text: it quotes results and the snapshot date of the release it installs.
   `tests/test_packaging.py` fails until all of these name the version of the newest dated section of `CHANGELOG.md`.
3. If the report card has changed, regenerate `docs/assets/demo.gif` with `python scripts/make_demo_gif.py` (it
   runs the real command, so do it after setting the version) and look at it. Then commit, push to `main` and
   wait for CI to pass.
4. Tag and push the tag:

   ```bash
   git tag -a vX.Y.Z -m "exostab X.Y.Z"
   git push origin vX.Y.Z
   ```

5. The Release workflow then:
   - checks that the tag, `__version__` and `CITATION.cff` give the same version, that `CITATION.cff` has a
     `date-released`, and that `CHANGELOG.md` has a section for the version;
   - builds the wheel and sdist and tests the wheel on Ubuntu and macOS: ruff, mypy, the fast suite and the CLI
     with Python 3.10 and 3.14, and the validation suite (`pytest -m slow`) with Python 3.12;
   - uploads to PyPI if `PUBLISH_PYPI` is `true`;
   - creates the GitHub release with the CHANGELOG section as notes. Zenodo archives it only if its GitHub
     integration was switched on before the release (see Zenodo above).
6. If the workflow fails before anything is published, fix the problem on `main`, delete the tag
   (`git push --delete origin vX.Y.Z` and `git tag -d vX.Y.Z`) and tag again. Once a version is on PyPI its
   number cannot be used again: release `X.Y.Z+1` instead.
7. Announce the release only after the tag is pushed and the GitHub release exists. The `pip` and `uvx` lines in
   the README and on the documentation's landing page, the SPOCK setup script's URL, the install cell of the notebook
   and the release badge all point to the tag, and fail or read "no releases" until then. Binder cannot build until
   the wheel is on the GitHub release.
8. Once the GitHub release exists, do the steps after merging in "Trying exostab in a browser" above: the release
   commit changed the pins of the notebook and of Binder.
9. Set `__version__` in `src/exostab/__init__.py` to the next development version, for example `X.Y.(Z+1).dev0`, and
   commit it. Otherwise the code on `main`, which a codespace, the weekly catalog and `pip install git+...` use, gives
   the version of the release in its reports although it differs from the tag. `CITATION.cff` keeps citing the release.
