"""Health check endpoint builder for web applications."""

from __future__ import annotations

import asyncio
import shutil
import socket
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Callable

_DEFAULT_TIMEOUT: float = 30.0
_DEFAULT_HISTORY_SIZE: int = 100


@dataclass
class CheckResult:
    """Result of an individual health check."""

    name: str
    healthy: bool
    message: str = ""
    duration_ms: float = 0.0


@dataclass
class HealthResult:
    """Aggregate result of all health checks."""

    status: str
    checks: list[CheckResult] = field(default_factory=list)
    uptime_seconds: float = 0.0


@dataclass
class _CheckEntry:
    """Internal representation of a registered check."""

    name: str
    fn: Callable[[], bool]
    depends_on: list[str] | None
    timeout: float | None
    on_failure: Callable[[CheckResult], None] | None


class HealthCheck:
    """Builder for health check endpoints."""

    def __init__(
        self,
        *,
        timeout: float = _DEFAULT_TIMEOUT,
        history_size: int = _DEFAULT_HISTORY_SIZE,
    ) -> None:
        self._checks: list[_CheckEntry] = []
        self._start_time: float = time.perf_counter()
        self._timeout: float = timeout
        self._history_size: int = history_size
        self._history: dict[str, deque[CheckResult]] = {}

    def add(
        self,
        name: str,
        fn: Callable[[], bool],
        depends_on: list[str] | None = None,
        *,
        timeout: float | None = None,
        on_failure: Callable[[CheckResult], None] | None = None,
    ) -> None:
        """Add a named check function.

        The function should return True if healthy, or raise an exception
        to indicate failure.

        Args:
            name: Unique name for this check.
            fn: Callable that returns True if healthy.
            depends_on: Optional list of check names that must pass first.
                If a dependency check failed, this check is skipped.
            timeout: Per-check timeout in seconds. Overrides the global
                timeout set on the ``HealthCheck`` instance. Defaults to
                the global timeout.
            on_failure: Optional callable invoked with the ``CheckResult``
                when the check fails. Useful for automated remediation.
        """
        self._checks.append(_CheckEntry(
            name=name,
            fn=fn,
            depends_on=depends_on,
            timeout=timeout,
            on_failure=on_failure,
        ))
        if name not in self._history:
            self._history[name] = deque(maxlen=self._history_size)

    def history(self, name: str) -> list[CheckResult]:
        """Return the list of past results for a named check.

        Args:
            name: The check name.

        Returns:
            List of ``CheckResult`` objects in chronological order.

        Raises:
            KeyError: If no check with the given name has been registered.
        """
        if name not in self._history:
            raise KeyError(f"Unknown check: {name!r}")
        return list(self._history[name])

    def success_rate(self, name: str) -> float:
        """Return the success rate for a named check as a float between 0 and 1.

        If no results have been recorded yet, returns ``1.0`` (optimistic
        default).

        Args:
            name: The check name.

        Returns:
            Float between 0.0 and 1.0.

        Raises:
            KeyError: If no check with the given name has been registered.
        """
        if name not in self._history:
            raise KeyError(f"Unknown check: {name!r}")
        entries = self._history[name]
        if not entries:
            return 1.0
        return sum(1 for r in entries if r.healthy) / len(entries)

    def _record_result(self, result: CheckResult) -> None:
        """Store a result in history and run remediation if needed."""
        if result.name in self._history:
            self._history[result.name].append(result)

    def _find_on_failure(self, name: str) -> Callable[[CheckResult], None] | None:
        """Look up the on_failure callback for a check by name."""
        for entry in self._checks:
            if entry.name == name:
                return entry.on_failure
        return None

    def _run_on_failure(self, result: CheckResult) -> None:
        """Execute the on_failure callback if the check failed."""
        if not result.healthy:
            callback = self._find_on_failure(result.name)
            if callback is not None:
                try:
                    callback(result)
                except Exception:
                    pass  # Remediation errors must not break the health check

    def _resolve_timeout(self, entry: _CheckEntry) -> float:
        """Return the effective timeout for a check entry."""
        return entry.timeout if entry.timeout is not None else self._timeout

    def run(self) -> HealthResult:
        """Run all registered checks and return the aggregate result."""
        results: list[CheckResult] = []
        all_healthy = True
        failed_names: set[str] = set()

        for entry in self._checks:
            # Check if any dependency failed
            if entry.depends_on:
                failed_dep = next(
                    (dep for dep in entry.depends_on if dep in failed_names), None
                )
                if failed_dep is not None:
                    all_healthy = False
                    failed_names.add(entry.name)
                    result = CheckResult(
                        name=entry.name,
                        healthy=False,
                        message=f"Skipped: dependency '{failed_dep}' failed",
                    )
                    self._record_result(result)
                    self._run_on_failure(result)
                    results.append(result)
                    continue

            effective_timeout = self._resolve_timeout(entry)
            start = time.perf_counter()
            try:
                healthy = _run_with_timeout(entry.fn, effective_timeout)
                duration_ms = (time.perf_counter() - start) * 1000
                if not healthy:
                    all_healthy = False
                    failed_names.add(entry.name)
                result = CheckResult(
                    name=entry.name,
                    healthy=healthy,
                    duration_ms=duration_ms,
                )
            except Exception as exc:
                duration_ms = (time.perf_counter() - start) * 1000
                all_healthy = False
                failed_names.add(entry.name)
                result = CheckResult(
                    name=entry.name,
                    healthy=False,
                    message=str(exc),
                    duration_ms=duration_ms,
                )

            self._record_result(result)
            self._run_on_failure(result)
            results.append(result)

        uptime = time.perf_counter() - self._start_time

        return HealthResult(
            status="healthy" if all_healthy else "unhealthy",
            checks=results,
            uptime_seconds=uptime,
        )

    async def run_async(self) -> HealthResult:
        """Run all checks concurrently using asyncio.gather.

        Dependency ordering is respected: checks with dependencies wait
        for their dependencies to complete first. Independent checks run
        concurrently.

        Returns:
            HealthResult with results from all checks.
        """
        results_map: dict[str, CheckResult] = {}
        failed_names: set[str] = set()
        events: dict[str, asyncio.Event] = {}

        for entry in self._checks:
            events[entry.name] = asyncio.Event()

        async def _run_check(entry: _CheckEntry) -> CheckResult:
            # Wait for dependencies
            if entry.depends_on:
                for dep in entry.depends_on:
                    if dep in events:
                        await events[dep].wait()

                failed_dep = next(
                    (dep for dep in entry.depends_on if dep in failed_names), None
                )
                if failed_dep is not None:
                    failed_names.add(entry.name)
                    result = CheckResult(
                        name=entry.name,
                        healthy=False,
                        message=f"Skipped: dependency '{failed_dep}' failed",
                    )
                    results_map[entry.name] = result
                    self._record_result(result)
                    self._run_on_failure(result)
                    events[entry.name].set()
                    return result

            effective_timeout = self._resolve_timeout(entry)
            start = time.perf_counter()
            try:
                healthy = await asyncio.wait_for(
                    asyncio.get_event_loop().run_in_executor(None, entry.fn),
                    timeout=effective_timeout,
                )
                duration_ms = (time.perf_counter() - start) * 1000
                if not healthy:
                    failed_names.add(entry.name)
                result = CheckResult(
                    name=entry.name,
                    healthy=healthy,
                    duration_ms=duration_ms,
                )
            except asyncio.TimeoutError:
                duration_ms = (time.perf_counter() - start) * 1000
                failed_names.add(entry.name)
                result = CheckResult(
                    name=entry.name,
                    healthy=False,
                    message=f"Timed out after {effective_timeout}s",
                    duration_ms=duration_ms,
                )
            except Exception as exc:
                duration_ms = (time.perf_counter() - start) * 1000
                failed_names.add(entry.name)
                result = CheckResult(
                    name=entry.name,
                    healthy=False,
                    message=str(exc),
                    duration_ms=duration_ms,
                )

            results_map[entry.name] = result
            self._record_result(result)
            self._run_on_failure(result)
            events[entry.name].set()
            return result

        tasks = [_run_check(entry) for entry in self._checks]
        await asyncio.gather(*tasks)

        # Preserve original registration order
        ordered_results = [results_map[entry.name] for entry in self._checks]
        all_healthy = all(r.healthy for r in ordered_results)
        uptime = time.perf_counter() - self._start_time

        return HealthResult(
            status="healthy" if all_healthy else "unhealthy",
            checks=ordered_results,
            uptime_seconds=uptime,
        )


def _run_with_timeout(fn: Callable[[], bool], timeout: float) -> bool:
    """Run a callable with a timeout using a thread.

    Args:
        fn: The check function.
        timeout: Maximum seconds to wait.

    Returns:
        The boolean result of the check function.

    Raises:
        TimeoutError: If the function does not complete within the timeout.
        Exception: Any exception raised by the function.
    """
    import concurrent.futures

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(fn)
        try:
            return future.result(timeout=timeout)
        except concurrent.futures.TimeoutError:
            raise TimeoutError(f"Timed out after {timeout}s") from None


class checks:
    """Namespace for built-in check helpers."""

    @staticmethod
    def tcp(
        name: str,
        host: str,
        port: int,
        timeout: float = 2,
    ) -> tuple[str, Callable[[], bool]]:
        """Check TCP connectivity to a host and port."""

        def _check() -> bool:
            conn = socket.create_connection((host, port), timeout=timeout)
            conn.close()
            return True

        return (name, _check)

    @staticmethod
    def disk_space(
        name: str,
        path: str = "/",
        min_free_gb: float = 1,
    ) -> tuple[str, Callable[[], bool]]:
        """Check that a path has at least *min_free_gb* free disk space."""

        def _check() -> bool:
            usage = shutil.disk_usage(path)
            free_gb = usage.free / (1024 ** 3)
            if free_gb < min_free_gb:
                raise RuntimeError(
                    f"Only {free_gb:.2f} GB free (need {min_free_gb} GB)"
                )
            return True

        return (name, _check)

    @staticmethod
    def memory(
        name: str,
        max_percent: float = 90,
    ) -> tuple[str, Callable[[], bool]]:
        """Check that memory usage is below *max_percent*.

        Reads ``/proc/meminfo`` on Linux. On other platforms the check
        always passes.
        """

        def _check() -> bool:
            try:
                with open("/proc/meminfo") as f:
                    lines = f.readlines()

                info: dict[str, int] = {}
                for line in lines:
                    parts = line.split()
                    if len(parts) >= 2:
                        key = parts[0].rstrip(":")
                        info[key] = int(parts[1])

                total = info.get("MemTotal", 0)
                available = info.get("MemAvailable", 0)
                if total == 0:
                    return True

                used_percent = ((total - available) / total) * 100
                if used_percent > max_percent:
                    raise RuntimeError(
                        f"Memory usage {used_percent:.1f}% exceeds "
                        f"{max_percent}%"
                    )
            except FileNotFoundError:
                pass  # Not on Linux — skip check
            return True

        return (name, _check)

    @staticmethod
    def custom(
        name: str,
        fn: Callable[[], bool],
    ) -> tuple[str, Callable[[], bool]]:
        """Wrap any callable as a named check."""
        return (name, fn)


__all__ = [
    "CheckResult",
    "HealthResult",
    "HealthCheck",
    "checks",
]
