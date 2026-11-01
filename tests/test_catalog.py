"""The batch catalog: same verdicts as `exostab check`, and every host accounted for."""

from __future__ import annotations

import json
import multiprocessing as mp
import signal
import sys
import time
from pathlib import Path
from typing import Any

import pytest
from rich.console import Console

from exostab.analysis import CheckSettings, check_system
from exostab.catalog import build
from exostab.catalog.build import CatalogSettings, check_one
from exostab.data import load_rows, system_from_rows
from exostab.data.archive import group_by_host


@pytest.mark.parametrize("host", ["HD 82943", "HD 10180"])
def test_catalog_row_matches_exostab_check(host: str) -> None:
    """The catalog keeps no time series, but its energy check and verdicts are those of `exostab check`."""
    rows, info = load_rows()
    rs = group_by_host(rows)[host]
    settings = CatalogSettings(orbits=500, draws=2, seed=0)
    row = check_one(rs, info, settings)
    res = check_system(system_from_rows(rs, info), CheckSettings(orbits=500, draws=2, seed=0, jobs=1))
    rep = res.report
    assert row["status"] == "ok"
    assert row["overall"] == rep.overall.verdict.value
    assert [row[k] for k in ("hill", "amd", "nbody")] == [
        rep.indicators[k].verdict.value for k in ("hill", "amd", "nbody")
    ]
    assert row["energy_error_nominal"] == res.runs[0].energy_error
    assert row["megno_nominal"] == res.runs[0].megno
    counts = rep.indicators["nbody"].details["classification_counts"]
    assert [row[f"nbody_{c}"] for c in counts] == list(counts.values())


def test_hosts_with_a_single_planet_row_are_recorded_as_skipped(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """sy_pnum >= 2 also selects hosts whose other planets orbit a companion star (e.g. WASP-94 A)."""
    rows, info = load_rows()
    hosts = group_by_host(rows)
    lonely = {**hosts["HD 82943"][0], "hostname": "Lonely A"}
    monkeypatch.setattr(build, "load_rows", lambda **_: ([*hosts["Kepler-47"], lonely], info))
    _, out = build.build_catalog(CatalogSettings(orbits=100, draws=0, jobs=2), tmp_path)
    by_host = {r["system"]: r for r in out}
    assert set(by_host) == {"Kepler-47", "Lonely A"}
    assert by_host["Lonely A"]["status"] == "skipped" and by_host["Lonely A"]["n_planets"] == 1
    assert "only one planet around Lonely A" in by_host["Lonely A"]["reason"]
    assert json.loads((tmp_path / "catalog_meta.json").read_text())["n_systems"] == 2


def _ignore_sigterm(ready: Any) -> None:
    """Stands for a worker inside a long C call whose Python SIGTERM handler cannot run (coverage's)."""
    signal.signal(signal.SIGTERM, signal.SIG_IGN)
    ready.set()
    time.sleep(120)


def test_a_worker_that_does_not_stop_on_sigterm_is_killed() -> None:
    ctx = mp.get_context("spawn")
    ready = ctx.Event()
    p = ctx.Process(target=_ignore_sigterm, args=(ready,), daemon=True)
    p.start()
    assert ready.wait(60)
    t0 = time.monotonic()
    build._stop(p, grace_s=0.5)
    assert not p.is_alive() and p.exitcode == -signal.SIGKILL
    assert time.monotonic() - t0 < 10


class _CtrlCAfter(Console):
    """A console on which Ctrl-C is pressed right after the first finished system is printed."""

    def __init__(self, text: str) -> None:
        super().__init__(record=True, width=120, emoji=False)
        self.text = text

    def print(self, *args: Any, **kwargs: Any) -> None:
        super().print(*args, **kwargs)
        if self.text in str(args[0]):
            raise KeyboardInterrupt


def test_ctrl_c_stops_the_workers_and_keeps_what_finished(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Exit 130 with worker noise, and no output folder: the finished rows were lost.
    rows, info = load_rows()
    hosts = group_by_host(rows)
    monkeypatch.setattr(build, "load_rows", lambda **_: ([*hosts["Kepler-47"], *hosts["TRAPPIST-1"]], info))
    console = _CtrlCAfter("Kepler-47")
    t0 = time.monotonic()
    with pytest.raises(KeyboardInterrupt):
        build.build_catalog(CatalogSettings(orbits=1e8, draws=2, jobs=2), tmp_path, console=console)
    assert time.monotonic() - t0 < 60  # the integration of TRAPPIST-1 takes much longer
    assert "Stopped: 1 of 2 systems finished" in console.export_text()
    assert (tmp_path / build.PARTIAL_CSV).exists()
    assert not (tmp_path / "catalog.csv").exists()  # a partial file cannot be published as the catalog
    assert "Kepler-47" in (tmp_path / build.PARTIAL_CSV).read_text()


def test_the_worker_stays_silent_on_ctrl_c(monkeypatch: pytest.MonkeyPatch) -> None:
    def interrupted(*args: object) -> None:
        raise KeyboardInterrupt

    monkeypatch.setattr(build, "check_one", interrupted)
    rows, info = load_rows()

    class NoQueue:
        def put(self, item: object) -> None:
            raise AssertionError("nothing to report")

    build._worker(group_by_host(rows)["Kepler-36"], info, CatalogSettings(), NoQueue())


def test_a_parquet_failure_still_writes_the_meta_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pa = pytest.importorskip("pyarrow")
    import pyarrow.parquet as pq

    def fails(table: object, path: object) -> None:
        raise pa.ArrowInvalid("value out of range")

    monkeypatch.setattr(pq, "write_table", fails)
    console = Console(record=True, width=120)
    paths, _ = build.build_catalog(
        CatalogSettings(orbits=100, draws=0, jobs=1), tmp_path, limit=1, console=console
    )
    assert (tmp_path / "catalog_meta.json").exists() and (tmp_path / "catalog.csv").exists()
    assert not any(p.name == "catalog.parquet" for p in paths)
    assert "catalog.parquet was not written" in console.export_text()


def test_it_is_said_when_parquet_is_skipped(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Without pyarrow an older catalog.parquet stayed beside a new catalog.csv, and nothing said Parquet was skipped.
    monkeypatch.setitem(sys.modules, "pyarrow", None)
    (tmp_path / "catalog.parquet").write_text("old")
    console = Console(record=True, width=120)
    build.build_catalog(CatalogSettings(orbits=100, draws=0, jobs=1), tmp_path, limit=1, console=console)
    text = " ".join(console.export_text().split())
    assert "catalog.parquet was not written: pyarrow is not installed" in text
    assert "An older catalog.parquet in this folder was not updated" in text


def test_the_reason_of_an_impossible_row_is_one_clean_sentence() -> None:
    # The reason column held pydantic's multi-line text with its URL.
    rows, info = load_rows()
    rs = [dict(r) for r in group_by_host(rows)["Kepler-11"]]
    rs[0]["pl_bmasse"] = 0.0
    row = check_one(rs, info, CatalogSettings(orbits=100, draws=0))
    assert row["status"] == "skipped" and "pl_bmasse" in row["reason"]
    assert "\n" not in row["reason"] and "pydantic" not in row["reason"]
