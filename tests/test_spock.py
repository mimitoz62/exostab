"""Optional SPOCK indicator: the bridge (with a fake worker) and, if a SPOCK environment is configured, the
real worker."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest
from typer.testing import CliRunner

from exostab.analysis import CheckSettings, check_system
from exostab.cli import app
from exostab.data import load_system
from exostab.indicators import Verdict
from exostab.indicators import spock as sp
from exostab.indicators.hill import pair_table
from exostab.sampling import Body, Realization, realizations

FAKE = """
import json, sys
req = json.load(sys.stdin)
n = len(req["systems"])
values = {values}
json.dump({{"p_stable": [values[i % len(values)] for i in range(n)], "spock": "fake", "rebound": "4.x"}}, sys.stdout)
"""


def fake_worker(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, values: list[float], body: str | None = None
) -> None:
    script = tmp_path / "worker.py"
    script.write_text(body if body is not None else FAKE.format(values=values))
    monkeypatch.setattr(sp, "WORKER", script)


def trio() -> Realization:
    return Realization(
        "nominal", 1.0, tuple(Body(f"p{k}", 3e-5, 0.1 * 1.5**k, 0.01, 0.0, k) for k in range(3))
    )


def test_classify_and_domain() -> None:
    assert sp.classify(0.34) is Verdict.STABLE and sp.classify(0.33) is Verdict.UNSTABLE
    far = Realization(
        "x",
        1.0,
        (Body("a", 1e-9, 0.1, 0, 0, 0), Body("b", 3e-5, 1.0, 0, 0, 0), Body("c", 3e-5, 10.0, 0, 0, 0)),
    )
    notes = " ".join(sp.domain_warnings(far))
    assert "mass ratio" in notes and "30 mutual Hill radii" in notes
    assert sp.domain_warnings(trio()) == []


def three(m: float, a_ratio: float) -> Realization:
    """Three planets of mass m (M_sun) around a solar-mass star with a constant semi-major-axis ratio."""
    return Realization(
        "x", 1.0, tuple(Body(f"p{k}", m, a_ratio ** (1.5 * k), 0.0, 0.0, 0.0) for k in range(3))
    )


def test_domain_spacing_uses_the_training_codes_hill_radius() -> None:
    """SPOCK's training set was generated with R_H = a_i ((m_i + m_{i+1}) / (3 M_*))^(1/3) and separations up to 30.

    dtamayo/spock, run_integrations/runfunctions.py: ``hill12 = a1*((M1+M2)/3.)**(1./3.)`` with ``betamax = 30``
    in run_random, ``eH = ((m1+m2)/3.)**(1./3.)`` with ``maxHillradii = 30`` in get_resonant. Tamayo et al.
    (2020) print their Eq. 1 without the 3, which made the check start only at 43.3 of these radii.
    """
    e_h = (6e-5 / 3) ** (1 / 3)
    real = three(3e-5, 1.6)
    a = real.semi_major_axes()
    for (_, d), a1, a2 in zip(sp.spock_spacings(real), a[:-1], a[1:]):
        assert d == pytest.approx((a2 - a1) / (a1 * e_h))
    # 32 of the training code's radii, but only 22.3 of the Hill indicator's: outside the training range
    wide = three(3e-5, 1 + 32 * e_h)
    assert all(r["separation_hill"] < 30 for r in pair_table(wide))
    assert [round(d, 1) for _, d in sp.spock_spacings(wide)] == [32.0, 32.0]
    assert any("training range" in n and "p0 / p1 (32.0)" in n for n in sp.domain_warnings(wide))
    # mass ratios of 1e-6: 35.8 of the training code's radii (24.8 without the 3), outside the training range
    small = three(1e-6, 1.313)
    assert [round(d, 1) for _, d in sp.spock_spacings(small)] == [35.8, 35.8]
    assert any("p0 / p1 (35.8)" in n for n in sp.domain_warnings(small))
    # 25 of the training code's radii are inside it
    inside = three(3e-5, 1 + 25 * e_h)
    assert all(d < 30 for _, d in sp.spock_spacings(inside))
    assert sp.domain_warnings(inside) == []


def test_spock_python_lookup(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("EXOSTAB_SPOCK_PYTHON", raising=False)
    assert sp.spock_python() is None
    monkeypatch.setenv("EXOSTAB_SPOCK_PYTHON", "/x/python")
    assert sp.spock_python() == "/x/python" and sp.spock_python("/y") == "/y"


def test_evaluate_with_fake_worker(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fake_worker(tmp_path, monkeypatch, [0.9])
    res = sp.evaluate(trio(), [trio()] * 4, sys.executable)
    assert res.verdict is Verdict.STABLE and res.details["versions"]["spock"] == "fake"
    assert "0.9" in res.summary and res.draws is not None and res.draws.stable == 4
    fake_worker(tmp_path, monkeypatch, [0.0, 0.9])
    res = sp.evaluate(trio(), [trio()] * 3, sys.executable)
    assert res.nominal_verdict is Verdict.UNSTABLE and "already became unstable" in res.summary
    assert res.verdict is Verdict.MARGINAL
    with pytest.raises(ValueError, match="three or more"):
        sp.evaluate(Realization("x", 1.0, trio().bodies[:2]), [], sys.executable)


@pytest.mark.parametrize(
    ("body", "match"),
    [
        ("import sys; sys.exit(3)", "exit 3"),
        ("print('not json')", "unexpected answer"),
        ("import json,sys; json.load(sys.stdin); print(json.dumps({'p_stable': []}))", "different number"),
    ],
)
def test_worker_failures(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, body: str, match: str) -> None:
    fake_worker(tmp_path, monkeypatch, [], body=body)
    with pytest.raises(sp.SpockUnavailableError, match=match):
        sp.predict([trio()], sys.executable)
    with pytest.raises(sp.SpockUnavailableError, match="could not run"):
        sp.predict([trio()], str(tmp_path / "no-such-python"))


def test_check_system_adds_spock_for_three_planets(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fake_worker(tmp_path, monkeypatch, [0.1])
    settings = CheckSettings(orbits=100, draws=2, jobs=1, ias15_check=False, spock_python=sys.executable)
    res = check_system(load_system("TOI-270"), settings)
    assert res.report.indicators["spock"].verdict is Verdict.UNSTABLE
    assert res.report.overall.verdict is not Verdict.STABLE and res.report.settings.spock
    two = check_system(load_system("Kepler-36"), settings)
    assert "spock" not in two.report.indicators


def test_cli_spock(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    runner = CliRunner()
    monkeypatch.delenv("EXOSTAB_SPOCK_PYTHON", raising=False)
    r = runner.invoke(app, ["check", "TOI-270", "--spock"])
    assert r.exit_code == 2 and "make_spock_env" in r.output
    fake_worker(tmp_path, monkeypatch, [0.8])
    out = tmp_path / "o"
    args = [
        "check",
        "TOI-270",
        "--spock-python",
        sys.executable,
        "--orbits",
        "100",
        "--draws",
        "1",
        "--jobs",
        "1",
        "--no-plots",
        "--no-ias15",
        "--out",
        str(out),
    ]
    r = runner.invoke(app, args)
    assert r.exit_code == 0, r.output
    assert json.loads((out / "report.json").read_text())["indicators"]["spock"]["verdict"] == "stable"
    r = runner.invoke(
        app,
        [
            "check",
            "Kepler-36",
            "--spock-python",
            sys.executable,
            "--orbits",
            "100",
            "--draws",
            "0",
            "--jobs",
            "1",
            "--no-plots",
            "--out",
            str(out),
        ],
    )
    assert r.exit_code == 0 and "skipped" in r.output
    fake_worker(tmp_path, monkeypatch, [], body="import sys; sys.exit(1)")
    r = runner.invoke(app, args)
    assert r.exit_code == 1 and "SPOCK worker failed" in r.output


@pytest.mark.skipif(not os.environ.get("EXOSTAB_SPOCK_PYTHON"), reason="no SPOCK environment configured")
def test_real_spock_worker() -> None:
    """Runs the real SPOCK classifier (scripts/make_spock_env.sh, then export EXOSTAB_SPOCK_PYTHON)."""
    reals = realizations(load_system("TRAPPIST-1"), 2, seed=0)
    probs, versions = sp.predict(reals, os.environ["EXOSTAB_SPOCK_PYTHON"])
    assert versions["spock"] == "2.1.1" and versions["rebound"].startswith("4.")
    assert all(0.0 <= p <= 1.0 for p in probs)


def test_a_wrong_interpreter_is_found_before_any_integration(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # It failed after the whole integration (15 s for TRAPPIST-1 at 20,000 orbits), with no folder saved.
    def integrate(*args: object, **kwargs: object) -> None:
        raise AssertionError("the run should have been refused before any integration")

    monkeypatch.setattr("exostab.indicators.megno.run_many", integrate)
    out = tmp_path / "o"
    r = CliRunner().invoke(
        app, ["check", "TRAPPIST-1", "--spock-python", "/nonexistent/python", "--out", str(out)]
    )
    assert r.exit_code == 2 and "could not run the SPOCK environment" in " ".join(r.output.split())
    assert not out.exists()
    failing = tmp_path / "fails"
    failing.write_text("#!/bin/sh\nexit 3\n")
    failing.chmod(0o755)
    with pytest.raises(sp.SpockUnavailableError, match="exited with code 3"):
        sp.probe(str(failing))
    sp.probe(sys.executable)


def test_an_empty_interpreter_is_refused(tmp_path: Path) -> None:
    # An unset shell variable in --spock-python "$PY": a run without SPOCK and no message.
    r = CliRunner().invoke(app, ["check", "TRAPPIST-1", "--spock-python", "", "--out", str(tmp_path / "o")])
    assert r.exit_code == 2 and "--spock-python is empty" in " ".join(r.output.split())
