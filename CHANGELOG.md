# Changelog

## 0.3.1 (2026-03-31)

- Standardize README to 3-badge format with emoji Support section
- Update CI checkout action to v5 for Node.js 24 compatibility

## 0.3.0 (2026-03-28)

- Add per-check timeout configuration via `add(name, fn, timeout=5.0)` to override the global timeout
- Add configurable global timeout on `HealthCheck(timeout=30.0)`
- Add check result history with `checker.history(name)` returning past results
- Add `checker.success_rate(name)` returning a float between 0 and 1
- Add remediation actions via `add(name, fn, on_failure=callable)` that run automatically on check failure
- Timeout support for both synchronous `run()` and asynchronous `run_async()`

## 0.2.0 (2026-03-27)

- Add `depends_on` parameter to `add()` for check dependency ordering
- Add `run_async()` method for concurrent check execution with `asyncio.gather`
- Dependent checks are skipped when their dependency fails
- Add issue templates, PR template, and Dependabot config
- Update README with full badge set and Support section

## 0.1.0 (2026-03-21)

- Initial release
- Health check builder with `add()` and `run()` methods
- Built-in checks: TCP, disk space, memory, custom
- Uptime tracking and per-check duration measurement
