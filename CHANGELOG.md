# Changelog

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
