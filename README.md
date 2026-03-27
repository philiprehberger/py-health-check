# philiprehberger-health-check

[![Tests](https://github.com/philiprehberger/py-health-check/actions/workflows/publish.yml/badge.svg)](https://github.com/philiprehberger/py-health-check/actions/workflows/publish.yml)
[![PyPI version](https://img.shields.io/pypi/v/philiprehberger-health-check.svg)](https://pypi.org/project/philiprehberger-health-check/)
[![License](https://img.shields.io/github/license/philiprehberger/py-health-check)](LICENSE)
[![Sponsor](https://img.shields.io/badge/sponsor-GitHub%20Sponsors-ec6cb9)](https://github.com/sponsors/philiprehberger)

Health check endpoint builder for web applications.

## Installation

```bash
pip install philiprehberger-health-check
```

## Usage

### Basic Health Check

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

### Built-in Checks

```python
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

| Name | Description |
|------|-------------|
| `HealthCheck()` | Create a health check builder |
| `hc.add(name, fn)` | Register a check (fn returns bool or raises) |
| `hc.run()` | Run all checks and return `HealthResult` |
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

## License

MIT
