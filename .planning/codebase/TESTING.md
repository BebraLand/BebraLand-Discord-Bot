# Testing Patterns

**Analysis Date:** 2026-05-10

## Test Framework

**Runner:**
- Not detected.
- No `pytest`, `unittest`, `coverage`, `tox`, `nox`, `jest`, or `vitest` configuration is present in `pyproject.toml` or repository config files.
- No dedicated `tests/` directory is present.
- `src/commands/admin/admin_test_welcome.py` is an admin Discord command for manually sending a welcome message, not an automated test.

**Assertion Library:**
- Not detected.
- Repository search finds no automated `assert`-based test files.

**Run Commands:**
```bash
# Automated test suite: Not detected
```

Project verification commands from `AGENTS.md`:
```powershell
$env:UV_CACHE_DIR='.uv-cache'; uv run python -m compileall main.py src
$env:UV_CACHE_DIR='.uv-cache'; uv run ruff check main.py src
```

Targeted verification examples from `AGENTS.md`:
```powershell
$env:UV_CACHE_DIR='.uv-cache'; uv run python -m compileall src\features\applications
$env:UV_CACHE_DIR='.uv-cache'; uv run ruff check src\features\applications
```

## Test File Organization

**Location:**
- Not detected.
- No automated test directory or co-located `*_test.py` / `test_*.py` files are present.
- Do not place automated tests in `src/commands/admin/`; files there are Discord command modules, including `src/commands/admin/admin_test_welcome.py`.

**Naming:**
- Not detected for automated tests.
- Recommended future pattern for this Python repo: `tests/test_<module_or_feature>.py` for unit tests and `tests/<feature>/test_<behavior>.py` for feature-scoped tests.

**Structure:**
```text
tests/                         # Not currently present
├── test_utils_embeds.py        # Suggested for pure utility tests
├── test_applications_service.py
└── features/
    └── applications/
        └── test_dm_flow.py
```

## Test Structure

**Suite Organization:**
```python
# Not currently present in repo.
# Suggested pattern for pure helpers:

from src.features.applications.service import get_application_retention_days


def test_get_application_retention_days_clamps_negative_values(monkeypatch):
    ...
```

**Patterns:**
- Automated setup pattern: Not detected.
- Automated teardown pattern: Not detected.
- Automated assertion pattern: Not detected.
- Current quality gate pattern is syntax compilation plus Ruff linting through `uv`.
- Manual behavior checks happen through Discord admin commands and bot flows, such as `src/commands/admin/admin_test_welcome.py`, application review buttons in `src/features/applications/view/ApplicationReviewView.py`, and panel sender commands in `src/commands/admin/`.

## Mocking

**Framework:** Not detected.

**Patterns:**
```python
# Not currently present in repo.
# Suggested future pattern for async Discord/storage tests:

from unittest.mock import AsyncMock, Mock


async def test_service_sends_review_message(monkeypatch):
    fake_db = Mock()
    fake_db.get_application = AsyncMock(return_value={...})
    ...
```

**What to Mock:**
- Discord network objects and methods: `discord.ApplicationContext`, `discord.Interaction`, `discord.Guild.fetch_channel`, `discord.Client.fetch_user`, `discord.Member.add_roles`, `discord.Member.remove_roles`.
- Bot singleton access from `src/utils/bot_instance.py` when testing scheduler or background flows.
- Database accessor `src.utils.database.get_db` for service-level tests.
- Scheduler `src.utils.scheduler.scheduler` when testing schedule creation in `src/features/events/service.py` or `src/features/applications/admin_service.py`.
- File/config loaders where JSON/YAML content drives behavior: `src/features/applications/config.py`, `src/utils/embeds.py`, `config/config.py`.

**What NOT to Mock:**
- Pure parsing and formatting helpers should be tested directly without mocks: `normalize_event_languages`, `parse_event_reminders`, `format_user_list`, `build_calendar_url` in `src/features/events/service.py`; `_truncate_text`, `_normalize_answers`, `get_application_retention_days` in `src/features/applications/service.py`; `replace_placeholders` and `build_embed_from_data` in `src/utils/embeds.py`.
- SQLAlchemy model definitions in `src/storage/models.py` should not be mocked for schema tests; use a temporary SQLite database when storage tests are added.
- Translation fallback behavior in `src/languages/localize.py` should use controlled in-memory locale data rather than mocking the `_` function everywhere.

## Fixtures and Factories

**Test Data:**
```python
# Not currently present in repo.
# Suggested factory shape for service tests:

def make_application(**overrides):
    data = {
        "id": 1,
        "user_id": "123",
        "guild_id": 456,
        "answers": [],
        "status": "pending",
        "created_at": 1_700_000_000,
    }
    data.update(overrides)
    return data
```

**Location:**
- Not detected.
- Suggested future locations:
  - Shared factories: `tests/fixtures.py` or `tests/conftest.py`.
  - Feature-specific fixtures: `tests/features/applications/conftest.py`.
  - JSON/YAML config fixtures: `tests/fixtures/config/`, using generic values only.

## Coverage

**Requirements:** None enforced.

**View Coverage:**
```bash
# Not available; coverage tooling is not configured.
```

If coverage is introduced, prefer focused thresholds around pure logic and storage behavior before attempting to cover Pycord UI callback surfaces.

## Test Types

**Unit Tests:**
- Not currently implemented.
- Highest-value unit candidates:
  - `src/utils/embeds.py`: placeholder replacement, JSON-to-embed conversion, timestamp/color handling.
  - `src/features/applications/service.py`: answer normalization/truncation, retention-day parsing, review embed budget handling.
  - `src/features/applications/view/ApplicationDMFlow.py`: timeout parsing, answer validation, active session tracking.
  - `src/features/events/service.py`: language/reminder parsing, calendar URL generation, check-in window logic.
  - `src/languages/localize.py`: translation lookup and fallback behavior.

**Integration Tests:**
- Not currently implemented.
- Highest-value integration candidates:
  - SQLAlchemy storage against temporary SQLite using `src/storage/sqlalchemy_storage.py`, `src/storage/sqlalchemy_applications.py`, `src/storage/sqlalchemy_events.py`, and `src/storage/models.py`.
  - Config loading with environment substitution in `config/config.py`.
  - Application cleanup behavior that must preserve `pending` and `accepted` rows while deleting old `rejected` and `revoked` rows.

**E2E Tests:**
- Not used.
- Discord E2E flows are currently manual through bot commands, panels, buttons, and DMs:
  - Application panel and DM wizard: `src/features/applications/view/ApplicationPanel.py`, `src/features/applications/view/ApplicationDMFlow.py`.
  - Application review: `src/features/applications/view/ApplicationReviewView.py`.
  - Tickets: `src/features/tickets/view/TicketPanel.py`, `src/features/tickets/create_ticket.py`.
  - Temp voice channel controls: `src/features/temp_voice_channels/views/TempVoiceControlView.py`.

## Common Patterns

**Async Testing:**
```python
# Not currently present in repo.
# Suggested future pattern if pytest-asyncio is added:

import pytest


@pytest.mark.asyncio
async def test_submit_application_returns_failure_embed(monkeypatch):
    ...
```

Async code is pervasive. Future tests need async support for:
- Discord command/service functions in `src/commands/`, `src/features/`, and `src/views/`.
- Storage methods in `src/storage/base.py` and SQLAlchemy implementations.
- Scheduler/background functions in `src/features/events/service.py`, `src/features/twitch/twitch_monitor.py`, and `src/utils/news_sender.py`.

**Error Testing:**
```python
# Not currently present in repo.
# Suggested future pattern:

async def test_apply_application_roles_handles_forbidden():
    member = ...
    member.add_roles.side_effect = discord.Forbidden(response=..., message="forbidden")
    ok, error = await apply_application_roles(member, "accepted")
    assert ok is False
    assert "permission" in error.lower()
```

Important error paths to cover when tests are added:
- `discord.Forbidden` role-management failures in `src/features/applications/service.py`.
- Missing/fetch-failed channels in `src/features/events/service.py` and `src/features/applications/service.py`.
- Malformed application answer JSON in `_normalize_answers` in `src/features/applications/service.py`.
- Missing or invalid config files in `config/config.py`.
- SQLAlchemy operation failures returning safe defaults in `src/storage/sqlalchemy_storage.py`.

## Manual Verification

**Compile:**
```powershell
$env:UV_CACHE_DIR='.uv-cache'; uv run python -m compileall main.py src
```

**Lint:**
```powershell
$env:UV_CACHE_DIR='.uv-cache'; uv run ruff check main.py src
```

**Feature-targeted Checks:**
```powershell
$env:UV_CACHE_DIR='.uv-cache'; uv run python -m compileall src\features\applications
$env:UV_CACHE_DIR='.uv-cache'; uv run ruff check src\features\applications
```

**Manual Discord Checks:**
- Admin welcome DM check: `src/commands/admin/admin_test_welcome.py`.
- Application panel send/status/revoke commands: `src/commands/admin/admin_applications.py`.
- Application DM wizard and review flow: `src/features/applications/view/ApplicationDMFlow.py`, `src/features/applications/view/ApplicationReviewView.py`.
- Event panel registration/check-in flow: `src/features/events/view/EventRegistrationView.py`, `src/features/events/service.py`.

---

*Testing analysis: 2026-05-10*
