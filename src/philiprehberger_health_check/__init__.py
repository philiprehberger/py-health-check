"""Health check endpoint builder for web applications."""

from __future__ import annotations

import shutil
import socket
import time
from dataclasses import dataclass, field
from typing import Callable


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


class HealthCheck:
    """Builder for health check endpoints."""

    def __init__(self) -> None:
        self._checks: list[tuple[str, Callable[[], bool]]] = []
        self._start_time: float = time.perf_counter()

    def add(self, name: str, fn: Callable[[], bool]) -> None:
        """Add a named check function.

        The function should return True if healthy, or raise an exception
        to indicate failure.
        """
        self._checks.append((name, fn))

    def run(self) -> HealthResult:
        """Run all registered checks and return the aggregate result."""
        results: list[CheckResult] = []
        all_healthy = True

        for name, fn in self._checks:
            start = time.perf_counter()
            try:
                healthy = fn()
                duration_ms = (time.perf_counter() - start) * 1000
                if not healthy:
                    all_healthy = False
                results.append(CheckResult(
                    name=name,
                    healthy=healthy,
                    duration_ms=duration_ms,
                ))
            except Exception as exc:
                duration_ms = (time.perf_counter() - start) * 1000
                all_healthy = False
                results.append(CheckResult(
                    name=name,
                    healthy=False,
                    message=str(exc),
                    duration_ms=duration_ms,
                ))

        uptime = time.perf_counter() - self._start_time

        return HealthResult(
            status="healthy" if all_healthy else "unhealthy",
            checks=results,
            uptime_seconds=uptime,
        )


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
