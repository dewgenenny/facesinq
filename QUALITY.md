# Quality Standards

This document defines the engineering quality bar for FaceSinq and serves as the implementation contract for CI gates.

---

## Toolchain

| Concern | Tool | Why |
|---|---|---|
| Linting + formatting | `ruff` | Single tool replacing flake8, black, and isort; fast, zero-config by default |
| Testing | `pytest` + `pytest-cov` | Standard Python test runner with coverage reporting |
| Security scanning | GitHub CodeQL | Already active; catches real vulnerability classes |
| Dependency alerts | GitHub Dependabot | Passive; flags outdated/vulnerable packages |

Add to `requirements-dev.txt` (new file, not installed in production):
```
ruff
pytest
pytest-cov
pytest-mock
```

---

## Code Style

Enforced by `ruff` with minimal configuration in `pyproject.toml`:

```toml
[tool.ruff]
line-length = 100
target-version = "py39"

[tool.ruff.lint]
select = ["E", "F", "W", "I"]   # pycodestyle errors/warnings + pyflakes + isort
ignore = ["E501"]                 # line length enforced by formatter, not linter
```

Run locally:
```bash
ruff check .          # lint
ruff format .         # format
ruff check --fix .    # auto-fix safe issues
```

---

## Testing Strategy

### What to test

The codebase divides naturally into three testable layers:

**1. Unit tests — pure logic, no I/O**

These have no external dependencies and should be fast and comprehensive:

- `utils.py`: `should_skip_user`, `extract_user_id_from_text`, `parse_user_data`
- `leaderboard.py`: ranking, streak calculation, score formatting
- `image_utils.py`: grid layout construction
- `game_manager.py`: quiz option selection logic, score calculation

**2. Integration tests — real DB, mocked Slack**

Use an in-memory SQLite database (already supported by the app). Mock only the Slack SDK client, not the database:

- `database_helpers.py`: all CRUD functions against a test schema
- `models.py`: ORM relationships, encryption round-trips
- `game_manager.py`: full quiz session lifecycle (create → answer → score)

**3. Route tests — Flask test client**

Use Flask's built-in test client. Mock Slack signature verification and the Slack SDK:

- Happy paths for all slash commands (`opt-in`, `opt-out`, `quiz`, `leaderboard`, `score`, `mode`, `reset-quiz`, `reset-score`)
- Reject unsigned requests (verify the 403 path)
- OAuth callback flow
- `app_home.py` block rendering (snapshot-style: assert structure, not pixel equality)

### What not to test

- The Slack SDK itself
- SQLAlchemy internals
- The Alembic migration runner (test that migrations produce the correct schema separately if needed)
- Docker build correctness

### Test layout

```
tests/
  conftest.py          # shared fixtures: in-memory DB, Flask test client, mock Slack client
  unit/
    test_utils.py
    test_leaderboard.py
    test_image_utils.py
    test_game_logic.py
  integration/
    test_database_helpers.py
    test_quiz_lifecycle.py
  routes/
    test_slash_commands.py
    test_oauth.py
    test_events.py
```

### Coverage target

- **Initial target: 70%** — achievable from a standing start, meaningful signal
- **Steady-state target: 80%** — raise once test infrastructure is established
- Coverage is measured across `app.py`, `game_manager.py`, `database_helpers.py`, `utils.py`, `leaderboard.py`, `slack_client.py`
- Exclude: migration scripts, one-off data scripts (`fix_data.py`, `inspect_data.py`, etc.), `create_encryption_key.py`

Run locally:
```bash
pytest --cov=. --cov-report=term-missing --cov-fail-under=70
```

---

## CI Pipeline

The existing `docker-publish.yml` only builds and pushes. Add a `quality` job that gates the build.

### Proposed pipeline

```
push / PR
    │
    ▼
┌─────────────────────────────┐
│  quality job                │  runs on every push + every PR
│  1. ruff check .            │
│  2. ruff format --check .   │
│  3. pytest --cov --fail=70  │
└────────────┬────────────────┘
             │ must pass
             ▼
┌─────────────────────────────┐
│  build job (existing)       │  master-only: Docker build, push, sign, deploy
└─────────────────────────────┘
```

The `build` job must declare `needs: quality`. This ensures no image is ever built from code that fails linting or tests.

### Environment for tests in CI

Tests use SQLite in-memory — no secrets or external services required. Set these in the workflow:

```yaml
env:
  DATABASE_URL: sqlite:///:memory:
  ENCRYPTION_KEY: ${{ secrets.TEST_ENCRYPTION_KEY }}   # any valid Fernet key
  SLACK_SIGNING_SECRET: test_secret
```

---

## Branch and PR Workflow

**Rule:** No direct pushes to `master` except automated commits from CI (the deployment image update).

- All changes go through a feature branch and a pull request
- PRs require the `quality` CI job to pass before merge
- Enable "Require status checks to pass before merging" on the `master` branch protection rule in GitHub settings
- One approving review required for non-trivial changes (optional for solo work, recommended when collaborating)

---

## Housekeeping Items (pre-implementation)

These issues exist today and should be resolved as part of standing up the quality tooling:

1. **`requirements.txt` is UTF-16 encoded** — re-save as UTF-8. `pip` may fail silently on some platforms.
2. **`print()` used for logging** — replace with `logger.*` calls. `ruff` will flag these as `T201` once the rule is enabled.
3. **One-off scripts at repo root** (`fix_data.py`, `inspect_data.py`, `migrate_*.py`, `update_db_schema.py`, `verify_scoring.py`) — move to a `scripts/` directory and exclude from coverage measurement.
4. **`quiz_app.py`** — unclear purpose; audit and either integrate or delete.
