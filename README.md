# philiprehberger-health-check

[![Tests](https://github.com/philiprehberger/py-health-check/actions/workflows/publish.yml/badge.svg)](https://github.com/philiprehberger/py-health-check/actions/workflows/publish.yml)
[![PyPI version](https://img.shields.io/pypi/v/philiprehberger-health-check.svg)](https://pypi.org/project/philiprehberger-health-check/)
[![GitHub release](https://img.shields.io/github/v/release/philiprehberger/py-health-check)](https://github.com/philiprehberger/py-health-check/releases)
[![Last updated](https://img.shields.io/github/last-commit/philiprehberger/py-health-check)](https://github.com/philiprehberger/py-health-check/commits/main)
[![License](https://img.shields.io/github/license/philiprehberger/py-health-check)](LICENSE)
[![Bug Reports](https://img.shields.io/github/issues/philiprehberger/py-health-check/bug)](https://github.com/philiprehberger/py-health-check/issues?q=is%3Aissue+is%3Aopen+label%3Abug)
[![Feature Requests](https://img.shields.io/github/issues/philiprehberger/py-health-check/enhancement)](https://github.com/philiprehberger/py-health-check/issues?q=is%3Aissue+is%3Aopen+label%3Aenhancement)
[![Sponsor](https://img.shields.io/badge/sponsor-GitHub%20Sponsors-ec6cb9)](https://github.com/sponsors/philiprehberger)

Health check endpoint builder for web applications.

## Installation

```bash
pip install philiprehberger-health-check
```

## Usage

```python
from philiprehberger_health_check import HealthCheck, checks

hc = HealthCheck()
hc.add("database", lambda: True)
hc.add(*checks.tcp("redis", "localhost", 6379))
hc.add(*checks.disk_space("disk", "/", min_free_gb=2))

result = hc.run()
print(result.status)  # "healthy" or "unhealthy"

for check in result.checks:
    print(f"{check.name}: {'OK' if check.healthy else check.message}")
```

### Check Dependencies

```python
from philiprehberger_health_check import HealthCheck

hc = HealthCheck()
hc.add("database", check_db)
hc.add("migrations", check_migrations, depends_on=["database"])

result = hc.run()
# If "database" fails, "migrations" is skipped automatically
```

### Per-Check Timeouts

```python
from philiprehberger_health_check import HealthCheck

hc = HealthCheck(timeout=10.0)  # global timeout
hc.add("fast-db", check_db, timeout=2.0)  # override for this check
hc.add("slow-report", generate_report, timeout=30.0)

result = hc.run()
# Each check uses its own timeout; others fall back to the global 10s
```

### Remediation Actions

```python
from philiprehberger_health_check import CheckResult, HealthCheck

def restart_cache(result: CheckResult) -> None:
    print(f"Restarting cache after failure: {result.message}")

hc = HealthCheck()
hc.add("cache", check_cache, on_failure=restart_cache)

result = hc.run()
# If "cache" fails, restart_cache is called automatically
```

### Check History and Metrics

```python
from philiprehberger_health_check import HealthCheck

hc = HealthCheck(history_size=50)
hc.add("database", check_db)

hc.run()
hc.run()
hc.run()

history = hc.history("database")  # list of past CheckResult objects
rate = hc.success_rate("database")  # float between 0.0 and 1.0
```

### Async Execution

```python
import asyncio
from philiprehberger_health_check import HealthCheck

hc = HealthCheck()
hc.add("database", check_db)
hc.add("cache", check_cache)
hc.add("migrations", check_migrations, depends_on=["database"])

result = await hc.run_async()
# Independent checks run concurrently; dependencies are respected
```

### Built-in Checks

```python
from philiprehberger_health_check import HealthCheck, checks

hc = HealthCheck()

# TCP connectivity
hc.add(*checks.tcp("postgres", "db.example.com", 5432, timeout=3))

# Disk space
hc.add(*checks.disk_space("storage", "/data", min_free_gb=5))

# Memory usage (Linux only, skipped on other platforms)
hc.add(*checks.memory("ram", max_percent=85))

# Custom check
hc.add(*checks.custom("cache", lambda: cache.ping()))
```

## API

| Function / Class | Description |
|------------------|-------------|
| `HealthCheck(timeout=30.0, history_size=100)` | Create a health check builder with optional global timeout and history size |
| `hc.add(name, fn, depends_on=None, timeout=None, on_failure=None)` | Register a check with optional dependencies, per-check timeout, and failure callback |
| `hc.run()` | Run all checks sequentially and return `HealthResult` |
| `hc.run_async()` | Run checks concurrently, respecting dependency order |
| `hc.history(name)` | Return list of past `CheckResult` objects for a check |
| `hc.success_rate(name)` | Return success rate as a float between 0.0 and 1.0 |
| `checks.tcp(name, host, port, timeout=2)` | TCP connectivity check |
| `checks.disk_space(name, path, min_free_gb=1)` | Disk free space check |
| `checks.memory(name, max_percent=90)` | Memory usage check (Linux) |
| `checks.custom(name, fn)` | Wrap any callable as a check |
| `CheckResult` | Dataclass: `name`, `healthy`, `message`, `duration_ms` |
| `HealthResult` | Dataclass: `status`, `checks`, `uptime_seconds` |

## Development

```bash
pip install -e .
python -m pytest tests/ -v
```

## Support

If you find this package useful, consider giving it a star on GitHub — it helps motivate continued maintenance and development.

[![LinkedIn](https://img.shields.io/badge/Philip%20Rehberger-LinkedIn-0A66C2?logo=linkedin)](https://www.linkedin.com/in/philiprehberger)
[![More packages](https://img.shields.io/badge/more-open%20source%20packages-blue)](https://philiprehberger.com/open-source-packages)

## License

[MIT](LICENSE)
