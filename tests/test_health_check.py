"""Tests for philiprehberger_health_check."""

from __future__ import annotations

import asyncio
import time

from philiprehberger_health_check import CheckResult, HealthCheck, checks


# ---------------------------------------------------------------------------
# Basic checks
# ---------------------------------------------------------------------------

def test_passing_check() -> None:
    hc = HealthCheck()
    hc.add("ok", lambda: True)
    result = hc.run()
    assert result.status == "healthy"
    assert len(result.checks) == 1
    assert result.checks[0].healthy is True
    assert result.checks[0].name == "ok"


def test_failing_check() -> None:
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


# ---------------------------------------------------------------------------
# Dependencies
# ---------------------------------------------------------------------------

def test_dependency_skip_on_failure() -> None:
    def _fail() -> bool:
        raise RuntimeError("db down")

    hc = HealthCheck()
    hc.add("database", _fail)
    hc.add("migrations", lambda: True, depends_on=["database"])
    result = hc.run()
    assert result.status == "unhealthy"
    assert result.checks[1].healthy is False
    assert "Skipped" in result.checks[1].message


def test_dependency_passes_when_parent_healthy() -> None:
    hc = HealthCheck()
    hc.add("database", lambda: True)
    hc.add("migrations", lambda: True, depends_on=["database"])
    result = hc.run()
    assert result.status == "healthy"
    assert all(c.healthy for c in result.checks)


# ---------------------------------------------------------------------------
# Per-check timeout
# ---------------------------------------------------------------------------

def test_per_check_timeout_triggers() -> None:
    def _slow() -> bool:
        time.sleep(5)
        return True

    hc = HealthCheck()
    hc.add("slow", _slow, timeout=0.1)
    result = hc.run()
    assert result.status == "unhealthy"
    assert result.checks[0].healthy is False
    assert "Timed out" in result.checks[0].message


def test_per_check_timeout_overrides_global() -> None:
    """A per-check timeout shorter than the global timeout should trigger."""
    def _slow() -> bool:
        time.sleep(5)
        return True

    hc = HealthCheck(timeout=60.0)
    hc.add("slow", _slow, timeout=0.1)
    result = hc.run()
    assert result.checks[0].healthy is False
    assert "Timed out" in result.checks[0].message


def test_global_timeout_applies_when_no_per_check() -> None:
    def _slow() -> bool:
        time.sleep(5)
        return True

    hc = HealthCheck(timeout=0.1)
    hc.add("slow", _slow)
    result = hc.run()
    assert result.checks[0].healthy is False
    assert "Timed out" in result.checks[0].message


def test_fast_check_within_timeout() -> None:
    hc = HealthCheck()
    hc.add("fast", lambda: True, timeout=5.0)
    result = hc.run()
    assert result.status == "healthy"


# ---------------------------------------------------------------------------
# History and metrics
# ---------------------------------------------------------------------------

def test_history_records_results() -> None:
    hc = HealthCheck()
    hc.add("db", lambda: True)
    hc.run()
    hc.run()
    hist = hc.history("db")
    assert len(hist) == 2
    assert all(r.healthy for r in hist)


def test_history_unknown_check_raises() -> None:
    hc = HealthCheck()
    try:
        hc.history("nonexistent")
        assert False, "Expected KeyError"
    except KeyError:
        pass


def test_success_rate_all_pass() -> None:
    hc = HealthCheck()
    hc.add("ok", lambda: True)
    hc.run()
    hc.run()
    hc.run()
    assert hc.success_rate("ok") == 1.0


def test_success_rate_with_failures() -> None:
    call_count = 0

    def _alternating() -> bool:
        nonlocal call_count
        call_count += 1
        if call_count % 2 == 0:
            raise RuntimeError("fail")
        return True

    hc = HealthCheck()
    hc.add("flaky", _alternating)
    hc.run()  # pass
    hc.run()  # fail
    hc.run()  # pass
    hc.run()  # fail
    assert hc.success_rate("flaky") == 0.5


def test_success_rate_no_results_returns_one() -> None:
    hc = HealthCheck()
    hc.add("fresh", lambda: True)
    assert hc.success_rate("fresh") == 1.0


def test_success_rate_unknown_check_raises() -> None:
    hc = HealthCheck()
    try:
        hc.success_rate("nonexistent")
        assert False, "Expected KeyError"
    except KeyError:
        pass


def test_history_respects_max_size() -> None:
    hc = HealthCheck(history_size=3)
    hc.add("db", lambda: True)
    for _ in range(5):
        hc.run()
    assert len(hc.history("db")) == 3


# ---------------------------------------------------------------------------
# Remediation actions (on_failure)
# ---------------------------------------------------------------------------

def test_on_failure_called_on_failing_check() -> None:
    remediation_calls: list[CheckResult] = []

    def _fail() -> bool:
        raise RuntimeError("connection lost")

    def _remediate(result: CheckResult) -> None:
        remediation_calls.append(result)

    hc = HealthCheck()
    hc.add("db", _fail, on_failure=_remediate)
    hc.run()
    assert len(remediation_calls) == 1
    assert remediation_calls[0].name == "db"
    assert remediation_calls[0].healthy is False


def test_on_failure_not_called_on_passing_check() -> None:
    remediation_calls: list[CheckResult] = []

    def _remediate(result: CheckResult) -> None:
        remediation_calls.append(result)

    hc = HealthCheck()
    hc.add("ok", lambda: True, on_failure=_remediate)
    hc.run()
    assert len(remediation_calls) == 0


def test_on_failure_error_does_not_break_health_check() -> None:
    def _fail() -> bool:
        raise RuntimeError("down")

    def _bad_remediation(result: CheckResult) -> None:
        raise RuntimeError("remediation exploded")

    hc = HealthCheck()
    hc.add("db", _fail, on_failure=_bad_remediation)
    hc.add("ok", lambda: True)
    result = hc.run()
    assert result.status == "unhealthy"
    assert result.checks[1].healthy is True


def test_on_failure_called_for_skipped_dependency() -> None:
    remediation_calls: list[str] = []

    def _fail() -> bool:
        raise RuntimeError("db down")

    def _remediate(result: CheckResult) -> None:
        remediation_calls.append(result.name)

    hc = HealthCheck()
    hc.add("database", _fail, on_failure=_remediate)
    hc.add("migrations", lambda: True, depends_on=["database"], on_failure=_remediate)
    hc.run()
    assert "database" in remediation_calls
    assert "migrations" in remediation_calls


# ---------------------------------------------------------------------------
# Async execution
# ---------------------------------------------------------------------------

def test_run_async_basic() -> None:
    hc = HealthCheck()
    hc.add("ok", lambda: True)

    result = asyncio.get_event_loop().run_until_complete(hc.run_async())
    assert result.status == "healthy"


def test_run_async_records_history() -> None:
    hc = HealthCheck()
    hc.add("ok", lambda: True)

    asyncio.get_event_loop().run_until_complete(hc.run_async())
    assert len(hc.history("ok")) == 1
