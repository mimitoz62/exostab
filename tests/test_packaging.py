"""Repository and packaging checks: ignored files, release metadata, sdist contents and workflows."""

from __future__ import annotations

import datetime
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
import yaml
from packaging.version import Version

from exostab import __version__

ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / ".github" / "workflows"
BINDER = ROOT / ".binder"


def test_citation_names_the_package_version() -> None:
    # GitHub's "Cite this repository" and Zenodo read CITATION.cff. A release must cite itself with its release
    # date (release.yml checks the same for the tag). A development version may still cite the release before
    # it, with that release's date, or cite itself without a date: it has not been released.
    cff = yaml.safe_load((ROOT / "CITATION.cff").read_text(encoding="utf-8"))
    cited, version = Version(str(cff["version"])), Version(__version__)
    if version.is_prerelease and cited == version:  # for example 1.1.0.dev0
        assert "date-released" not in cff
        return
    if version.is_prerelease:
        assert cited < version
    else:
        assert cited == version
    datetime.date.fromisoformat(str(cff["date-released"]))


def test_codemeta_matches_the_citation() -> None:
    # Software catalogs read codemeta.json and GitHub reads CITATION.cff, so both name the same release.
    cff = yaml.safe_load((ROOT / "CITATION.cff").read_text(encoding="utf-8"))
    meta = json.loads((ROOT / "codemeta.json").read_text(encoding="utf-8"))
    assert meta["version"] == str(cff["version"])
    assert meta["datePublished"] == str(cff["date-released"])
    assert meta["description"] == " ".join(cff["abstract"].split())
    assert meta["codeRepository"] == cff["repository-code"]
    assert meta["author"][0]["@id"] == cff["authors"][0]["orcid"]


@pytest.mark.skipif(not (ROOT / "overrides" / "home.html").is_file(), reason="the site is not in the sdist")
def test_home_page_structured_data_matches_codemeta() -> None:
    # Search engines read this block and software catalogs read codemeta.json, so both name the same release.
    html = (ROOT / "overrides" / "home.html").read_text(encoding="utf-8")
    block = re.search(r'<script type="application/ld\+json">(.+?)</script>', html, re.DOTALL)
    assert block is not None
    data = json.loads(block[1])
    meta = json.loads((ROOT / "codemeta.json").read_text(encoding="utf-8"))
    for key in (
        "@type",
        "name",
        "url",
        "codeRepository",
        "programmingLanguage",
        "license",
        "version",
        "identifier",
    ):
        assert data[key] == meta[key], key
    author = meta["author"][0]
    assert data["author"]["sameAs"] == author["@id"]
    assert data["author"]["givenName"] == author["givenName"]
    assert data["author"]["familyName"] == author["familyName"]
    assert data["author"]["name"] == f"{author['givenName']} {author['familyName']}"
    # the description is the page's own, which a reader of the page can compare it with
    index = (ROOT / "docs" / "index.md").read_text(encoding="utf-8")
    assert data["description"] == yaml.safe_load(index.split("---")[1])["description"]
    # Google's guidelines ask not to mark up what readers cannot see, so the page's text has the DOI too
    assert f"({data['identifier']})" in index


@pytest.mark.skipif(
    not (ROOT / "docs" / "quickstart.md").is_file(), reason="these pages are not in the sdist"
)
def test_each_documentation_page_has_its_own_description() -> None:
    # A page without one gets the description of the whole site, in search results and in link previews.
    descriptions = {}
    for page in sorted((ROOT / "docs").glob("*.md")):
        text = page.read_text(encoding="utf-8")
        front_matter = yaml.safe_load(text.split("---")[1]) if text.startswith("---\n") else {}
        descriptions[page.name] = front_matter.get("description")
    assert [name for name, description in descriptions.items() if not description] == []
    assert len(set(descriptions.values())) == len(descriptions)


def test_a_release_version_has_a_changelog_section() -> None:
    # release.yml refuses a tag whose version has no "## [X.Y.Z]" section in CHANGELOG.md. Checked on every
    # commit, so that main never claims a release version (with a release date in CITATION.cff) before its
    # changelog section exists; a development version collects its entries under "Unreleased".
    headings = [
        line
        for line in (ROOT / "CHANGELOG.md").read_text(encoding="utf-8").splitlines()
        if line.startswith("## ")
    ]
    wanted = "[Unreleased]" if Version(__version__).is_prerelease else f"[{__version__}]"
    assert any(wanted in heading for heading in headings)


def latest_release() -> Version:
    # A release gives its changelog section a date; "[Unreleased]" has none. So the pins checked below name a
    # version the changelog knows as released, and they must move in the release commit (RELEASING.md).
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    return max(Version(v) for v in re.findall(r"^## \[(.+)\] - \d{4}-\d{2}-\d{2}$", changelog, re.MULTILINE))


@pytest.mark.parametrize("name", ["exostab_quickstart.ipynb", "exostab_exercise.ipynb"])
def test_notebook_has_no_outputs_and_installs_the_latest_release(name: str) -> None:
    # Colab shows the file as committed, so outputs would look like the results of the visitor's own run.
    notebook = json.loads((ROOT / "examples" / name).read_text(encoding="utf-8"))
    code = [cell for cell in notebook["cells"] if cell["cell_type"] == "code"]
    assert code and [c["id"] for c in code if c["outputs"] or c["execution_count"] is not None] == []
    pins = re.findall(r"@v(\d+\.\d+\.\d+)", "".join("".join(cell["source"]) for cell in notebook["cells"]))
    assert pins and {Version(pin) for pin in pins} == {latest_release()}


@pytest.mark.skipif(
    not (ROOT / "docs" / "quickstart.md").is_file(), reason="these pages are not in the sdist"
)
def test_install_lines_name_the_latest_release() -> None:
    # Every form RELEASING.md lists: an older pin still works after a release, so nothing else would notice it.
    pins = re.compile(
        r"@v(\d+\.\d+\.\d+)"
        r"|/releases/download/v(\d+\.\d+\.\d+)/"
        r"|/exostab-(\d+\.\d+\.\d+)-py3"
        r"|raw\.githubusercontent\.com/mimitoz62/exostab/v(\d+\.\d+\.\d+)/"
        r"|[Rr]elease (\d+\.\d+\.\d+)"
        r"|Version (\d+\.\d+\.\d+)"
    )
    for name in ("README.md", "docs/index.md", "docs/quickstart.md", "docs/web.md", "overrides/home.html"):
        text = (ROOT / name).read_text(encoding="utf-8")
        named = {Version(version) for match in pins.findall(text) for version in match if version}
        assert named == {latest_release()}, name


def test_code_blocks_have_no_comments() -> None:
    # Interactive zsh, the default shell on macOS, does not treat # as a comment. Pasted, the words of a comment
    # become arguments, and an apostrophe in one opens a quote that swallows every later line.
    pages = [ROOT / "README.md", ROOT / "CONTRIBUTING.md", *sorted((ROOT / "docs").glob("*.md"))]
    blocks = [
        (page.name, line)
        for page in pages
        if page.is_file()  # the sdist has only some of them
        for block in re.findall(r"```bash\n(.*?)```", page.read_text(encoding="utf-8"), re.DOTALL)
        for line in block.splitlines()
    ]
    assert blocks and [(name, line) for name, line in blocks if re.search(r"(^|\s)#", line)] == []


@pytest.mark.skipif(not BINDER.is_dir(), reason=".binder is not in the sdist")
def test_binder_installs_the_wheel_of_the_latest_release() -> None:
    wheel = re.search(
        r"^exostab\[web\] @ https://github\.com/mimitoz62/exostab/releases/download/"
        r"v(.+)/exostab-(.+)-py3-none-any\.whl$",
        (BINDER / "requirements.txt").read_text(encoding="utf-8"),
        re.MULTILINE,
    )
    assert wheel is not None and {Version(v) for v in wheel.groups()} == {latest_release()}
    assert os.access(BINDER / "postBuild", os.X_OK)  # git mode 100755


def pyproject() -> dict[str, Any]:
    if sys.version_info >= (3, 11):
        import tomllib
    else:  # pytest depends on tomli before Python 3.11
        import tomli as tomllib
    return tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))


def test_sdist_ships_what_the_tests_load() -> None:
    # The sdist contains tests/, so packagers run them from it; these are the project files the tests read.
    include = pyproject()["tool"]["hatch"]["build"]["targets"]["sdist"]["include"]
    needed = ["src/exostab", "tests", "examples", "scripts", "streamlit_app.py", "docs/cli.md"]
    assert [path for path in needed if path not in include] == []


def test_the_extras_have_the_bounds_of_dev() -> None:
    # The CI job `lowest` installs .[dev] at its lower bounds and checks each of them, so the extras that users install
    # must ask for the same versions.
    extras = pyproject()["project"]["optional-dependencies"]
    assert [r for name in ("catalog", "web") for r in extras[name] if r not in extras["dev"]] == []


@pytest.mark.skipif(
    shutil.which("git") is None or not (ROOT / ".git").exists(), reason="needs a git checkout"
)
def test_coverage_data_files_are_ignored() -> None:
    # [tool.coverage.run] parallel = true leaves .coverage.<host>.pid<N>.<random> files behind.
    names = [".coverage", ".coverage.host.local.pid1544.XoShmcrx.HYzE0XwvftFh"]
    r = subprocess.run(
        ["git", "check-ignore", "--no-index", *names], cwd=ROOT, capture_output=True, text=True, check=False
    )
    assert r.stdout.split() == names


@pytest.mark.skipif(not WORKFLOWS.is_dir(), reason="workflows are not in the sdist")
def test_documents_named_in_workflows_exist() -> None:
    # The workflows point maintainers to setup instructions (RELEASING.md, DECISIONS.md, ...).
    names = {
        name for path in WORKFLOWS.glob("*.yml") for name in re.findall(r"\b[A-Z]+\.md\b", path.read_text())
    }
    assert names and [name for name in sorted(names) if not (ROOT / name).is_file()] == []


@pytest.mark.skipif(not WORKFLOWS.is_dir(), reason="workflows are not in the sdist")
def test_workflow_pipelines_keep_the_exit_status() -> None:
    # A step without `shell:` runs as `bash -e {0}`, without pipefail, so `cmd | tail` succeeds even when cmd
    # fails. `shell: bash` runs `bash --noprofile --norc -eo pipefail {0}`.
    pipe = re.compile(r"(?<!\|)\|(?!\|)")
    unsafe = []
    for path in sorted(WORKFLOWS.glob("*.yml")):
        workflow = yaml.safe_load(path.read_text(encoding="utf-8"))
        default = workflow.get("defaults", {}).get("run", {}).get("shell")
        for job_id, job in workflow["jobs"].items():
            shell = job.get("defaults", {}).get("run", {}).get("shell", default)
            for step in job.get("steps", []):
                if pipe.search(step.get("run", "")) and step.get("shell", shell) != "bash":
                    unsafe.append(f"{path.name}: {job_id}: {step.get('name') or step['run'][:60]}")
    assert unsafe == []


@pytest.mark.skipif(not WORKFLOWS.is_dir(), reason="workflows are not in the sdist")
def test_ci_runs_once_for_a_pull_request_and_for_each_push_to_main() -> None:
    # A push to the branch of a pull request started a second run of the same commit. Pull requests from forks get
    # only the pull_request event, so it has no filter.
    workflow = yaml.safe_load((WORKFLOWS / "ci.yml").read_text(encoding="utf-8"))
    on = workflow[True]  # YAML 1.1 reads the key `on` as true
    assert on == {
        "push": {"branches": ["main"], "tags": ["v*"]},
        "pull_request": None,
        "workflow_dispatch": None,
    }


@pytest.mark.skipif(
    not WORKFLOWS.is_dir() or os.name == "nt" or shutil.which("bash") is None,
    reason="needs the workflows and a POSIX shell",
)
@pytest.mark.parametrize(
    ("ls_remote", "returncode", "ran"),
    [
        (
            0,
            0,
            [
                "scripts/system_pages.py catalog-latest",
                "scripts/catalog_page.py catalog-latest",
                "scripts/catalog_changes.py archive",
            ],
        ),
        (2, 0, ["scripts/catalog_page.py", "scripts/catalog_changes.py"]),  # no branch catalog-data yet
        (128, 1, []),  # origin did not answer
    ],
)
def test_the_docs_use_catalog_placeholders_only_when_the_branch_does_not_exist(
    tmp_path: Path, ls_remote: int, returncode: int, ran: list[str]
) -> None:
    # Any failed fetch of catalog-data gave placeholder pages, which the deploy job put over the live catalog.
    steps = yaml.safe_load((WORKFLOWS / "docs.yml").read_text(encoding="utf-8"))["jobs"]["build"]["steps"]
    script = next(step["run"] for step in steps if "catalog-data" in step.get("name", ""))
    stubs = tmp_path / "bin"
    stubs.mkdir()
    # As git does: without the branch, or without an answer, the fetch fails too.
    git = f'case "$1" in ls-remote) exit {ls_remote} ;; fetch) [ {ls_remote} -eq 0 ] || exit 128 ;; esac'
    (stubs / "git").write_text(f"#!/bin/sh\n{git}\n", encoding="utf-8")
    (stubs / "python").write_text('#!/bin/sh\necho "$*" >> ran.txt\n', encoding="utf-8")
    for stub in stubs.iterdir():
        stub.chmod(0o755)
    env = {**os.environ, "PATH": f"{stubs}{os.pathsep}{os.environ['PATH']}"}
    result = subprocess.run(  # a step without `shell:` runs as `bash -e {0}`
        ["bash", "-e", "-c", script], cwd=tmp_path, env=env, capture_output=True, text=True, check=False
    )
    assert result.returncode == returncode, result.stderr
    log = tmp_path / "ran.txt"
    assert (log.read_text(encoding="utf-8").splitlines() if log.exists() else []) == ran


@pytest.mark.skipif(not WORKFLOWS.is_dir(), reason="workflows are not in the sdist")
def test_a_release_pull_request_runs_the_notebooks_with_its_own_checkout() -> None:
    # The release commit moves the notebooks' pin to a tag that is pushed only after the merge, so on the release pull
    # request the install failed, and both notebooks with it.
    workflow = yaml.safe_load((WORKFLOWS / "browser-paths.yml").read_text(encoding="utf-8"))
    steps = workflow["jobs"]["notebook"]["steps"]
    swap = next(i for i, step in enumerate(steps) if "install this checkout" in step.get("name", ""))
    assert swap < next(i for i, step in enumerate(steps) if "jupyter nbconvert" in step.get("run", ""))
    assert steps[swap]["if"] == "github.event_name == 'pull_request'"
    pin = re.search(r'sed -i "s#(.+?)#', steps[swap]["run"])
    assert pin is not None
    url = pin[1].replace("$tag", f"v{latest_release()}")
    for name in ("exostab_quickstart.ipynb", "exostab_exercise.ipynb"):
        notebook = (ROOT / "examples" / name).read_text(encoding="utf-8")
        assert f"examples/{name}" in steps[swap]["run"] and url in notebook, name


@pytest.mark.skipif(not WORKFLOWS.is_dir(), reason="workflows are not in the sdist")
def test_the_weekly_catalog_is_built_without_write_permission() -> None:
    # The build runs the newest release of every dependency for about two hours. With a token that can write, any of
    # them could push to main or move a tag, so its job only reads and keeps no token on disk.
    workflow = yaml.safe_load((WORKFLOWS / "catalog.yml").read_text(encoding="utf-8"))
    assert workflow["permissions"] == {"contents": "read"}
    jobs = workflow["jobs"]
    checkout = next(s for s in jobs["catalog"]["steps"] if s.get("uses", "").startswith("actions/checkout@"))
    assert "permissions" not in jobs["catalog"] and checkout["with"]["persist-credentials"] is False
    writers = {name for name, job in jobs.items() if "write" in job.get("permissions", {}).values()}
    assert writers == {"publish", "docs"}
    installs = [s for name in writers for s in jobs[name]["steps"] if "pip install" in s.get("run", "")]
    assert installs == []


@pytest.mark.skipif(not WORKFLOWS.is_dir(), reason="workflows are not in the sdist")
def test_the_validation_badge_does_not_depend_on_the_live_archive() -> None:
    # The README's validation badge shows the status of nightly.yml, which should not fail when the archive is down.
    nightly = yaml.safe_load((WORKFLOWS / "nightly.yml").read_text(encoding="utf-8"))
    offline = {job_id: job.get("env", {}).get("EXOSTAB_OFFLINE") for job_id, job in nightly["jobs"].items()}
    assert offline == {"validation": "1"}
    assert "exostab list --refresh" in (WORKFLOWS / "archive.yml").read_text(encoding="utf-8")


@pytest.mark.skipif(not WORKFLOWS.is_dir(), reason="workflows are not in the sdist")
def test_indexnow_follows_a_dispatched_deployment_in_a_job_of_its_own() -> None:
    # The weekly catalog starts the docs workflow with workflow_dispatch, and a push must send nothing. GitHub prepares
    # every action of a job before its first step, so the jobs that deploy must not mention IndexNow at all.
    assert "gh workflow run docs.yml" in (WORKFLOWS / "catalog.yml").read_text(encoding="utf-8")
    workflow = yaml.safe_load((WORKFLOWS / "docs.yml").read_text(encoding="utf-8"))
    jobs = workflow["jobs"]
    assert "indexnow" not in str(jobs["build"]).lower() and "indexnow" not in str(jobs["deploy"]).lower()
    job = jobs["indexnow"]
    # With no status function in `if`, the job also needs `deploy` to have succeeded.
    assert job["if"] == "github.event_name == 'workflow_dispatch'" and job["needs"] == "deploy"
    # A failed call leaves the run green, and the job has only the workflow's read permission.
    assert job["continue-on-error"] is True and "permissions" not in job
    assert workflow["permissions"] == {"contents": "read"}
    # All of it is silent if it breaks: the run stays green and no other test would notice.
    assert job["steps"][0]["uses"].startswith("actions/checkout@")
    run = job["steps"][-1]["run"]
    assert "--output sitemap.xml https://mimitoz62.github.io/exostab/sitemap.xml" in run
    assert "python3 scripts/indexnow.py sitemap.xml" in run
