---
name: tdd-extra
description: "Supplement to TDD skill for test environment mode: local dev site (real API at warframe.test) vs CI/cassette mode (VCR playback). Use when setting up new tests, running tests locally, or explaining how contributors without dev site access should run the suite."
---

# Test Environment Modes

Supplement to the TDD skill. Defines two test execution modes — **local dev site** (real API) and **cassette mode** (VCR playback) — with configuration guidance and a default that protects contributors without dev site access.

## The two modes

| Mode | API calls | Who uses it | Default |
|------|-----------|-------------|---------|
| **Local dev site** | Real HTTP to `warframe.test` / `api.warframe.test` | Primary developer during active feature work | No |
| **Cassette** | Recorded VCR playback, no network | CI and all contributors | Yes |

### Local dev site mode

For the primary developer who has the Warframe.Market dev site running locally. Uses **real API calls** against:

- **Site host**: `warframe.test`
- **API host**: `api.warframe.test`

Use this mode when:

- Developing a new feature or endpoint and you need to exercise real HTTP flows before cassettes exist.
- Verifying that a recorded cassette faithfully reproduces real behavior.
- Debugging a test that fails in cassette mode but you suspect is a real API issue.

**Never commit cassettes recorded against the dev site** unless the dev site data is stable and reproducible. Real dev site responses can drift with local data changes.

### Cassette mode

The default mode for every contributor. VCR records and replays HTTP responses from `tests/cassettes/`. No network calls reach the live API.

Use this mode when:

- Running the full test suite before committing or opening a PR.
- You don't have access to the dev site (most contributors).
- You want fast, deterministic test runs in CI.

## Default: cassette mode

**All contributors should start with cassette mode.** The dev site is not available to everyone; defaulting to cassette mode means the test suite runs out-of-the-box for any fork or PR.

When writing a test that needs the dev site:

1. Run with cassette mode first — check if an existing cassette covers the case.
2. If not, record a new cassette (see below).
3. Only fall back to dev site mode if recording is impossible or the cassette would be brittle.

## Recording new cassettes

When adding a new test that calls a real endpoint:

```bash
VCR_RECORD_MODE=once pytest tests/test_feature.py -k test_something
```

This hits the **live API** (not the dev site) and writes a cassette to `tests/cassettes/`. After recording:

1. Verify the cassette was written.
2. Run the test again **without** `VCR_RECORD_MODE` to confirm playback works.
3. Commit the cassette file.

## VCR configuration

VCR settings live in the test fixtures or conftest. Key settings:

- **Record mode**: `once` (record only if no cassette exists).
- **Cassette directory**: `tests/cassettes/` (committed to version control).
- **Matcher**: match on `method` and `url` (path and query params).
- **Filter headers**: strip authorization and sensitive request/response headers.

## How tests switch modes

Tests that need dev site access should set the mode explicitly rather than relying on environment variables. Use a test class attribute or decorator:

```python
class TestNewEndpoint(TestCase):
    use_dev_site = False  # Default to cassette mode
    cassette_name = "test_new_endpoint.json"
```

The test base class or fixture checks this flag and configures VCR or the test client accordingly. This makes the mode decision visible in the test file itself, so contributors know at a glance whether the test needs the dev site or will work with just the cassettes.

## Adding a new endpoint — full checklist

1. Write a failing test with `use_dev_site = False` (cassette mode default).
2. Record a cassette with `VCR_RECORD_MODE=once`.
3. Implement the endpoint to pass the test.
4. Re-run the test in playback mode to confirm.
5. Verify the cassette file is committed.
6. If the endpoint requires dev site data, note that in the test comment so future contributors know why.

## Reference: AGENTS.md

The `AGENTS.md` file at the project root documents the TDD workflow and VCR cassette conventions. This skill adds the local dev site mode as a branch the primary developer uses. Always cross-reference when adding or modifying test infrastructure.
