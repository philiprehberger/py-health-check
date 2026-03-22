"""Tests for philiprehberger_health_check."""

from __future__ import annotations

import time

from philiprehberger_health_check import HealthCheck, checks


def test_passing_check() -> None:
    hc = HealthCheck()
    hc.add("ok", lambda: True)
    result = hc.run()
    assert result.status == "healthy"
    assert len(result.checks) == 1
    assert result.checks[0].healthy is True
    assert result.checks[0].name == "ok"


def test_failing_check() -> None:
    hc = HealthCheck()
    hc.add("fail", lambda: (_ for _ in ()).throw(RuntimeError("boom")))  # type: ignore[attr-defined]

    def _fail() -> bool:
        raise RuntimeError("boom")

    hc = HealthCheck()
    hc.add("fail", _fail)
    result = hc.run()
    assert result.status == "unhealthy"
    assert len(result.checks) == 1
    assert result.checks[0].healthy is False
    assert "boom" in result.checks[0].message


def test_mixed_checks_result_unhealthy() -> None:
    hc = HealthCheck()
    hc.add("good", lambda: True)

    def _bad() -> bool:
        raise RuntimeError("down")

    hc.add("bad", _bad)
    result = hc.run()
    assert result.status == "unhealthy"
    assert result.checks[0].healthy is True
    assert result.checks[1].healthy is False


def test_custom_check() -> None:
    hc = HealthCheck()
    name, fn = checks.custom("custom-ok", lambda: True)
    hc.add(name, fn)
    result = hc.run()
    assert result.status == "healthy"
    assert result.checks[0].name == "custom-ok"


def test_uptime_increases() -> None:
    hc = HealthCheck()
    hc.add("ok", lambda: True)
    time.sleep(0.05)
    result = hc.run()
    assert result.uptime_seconds >= 0.04
