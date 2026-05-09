# Coding Conventions

**Analysis Date:** 2026-05-10

## Naming Patterns

**Files:**
- Use lowercase snake_case for command, service, utility, storage, and event modules: `src/features/applications/service.py`, `src/features/events/admin_service.py`, `src/utils/schedule_utils.py`, `src/events/on_member_join.py`.
- Discord view and modal modules often use PascalCase matching the main class name: `src/features/applications/view/ApplicationDMFlow.py`, `src/features/applications/view/ApplicationReviewView.py`, `src/features/tickets/view/TicketControlPanel.py`, `src/features/temp_voice_channels/views/settings/LimitModal.py`.
- Package initializer files are named `__init__.py` and are commonly empty or marker-only: `src/features/applications/__init__.py`, `src/views/__init__.py`.
- Configuration modules are lowercase and live under `config/`: `config/config.py`, `config/command.py`.
- Avoid creating new "test" helper files under command packages; `src/commands/admin/admin_test_welcome.py` is an admin command, not a test file.

**Functions:**
- Use snake_case for free functions and methods: `submit_application_answers` in `src/features/applications/service.py`, `build_embed_from_data` in `src/utils/embeds.py`, `parse_event_reminders` in `src/features/events/service.py`.
- Use leading underscore for module-private helpers: `_status_color`, `_truncate_text`, `_normalize_answers` in `src/features/applications/service.py`; `_get_timeout_seconds`, `_disable_view` in `src/features/applications/view/ApplicationDMFlow.py`.
- Async Discord handlers and storage methods use `async def` and return explicit status values where possible: `send_application_review` in `src/features/applications/service.py`, `SQLAlchemyStorage.create_ticket` in `src/storage/sqlalchemy_storage.py`.
- Cog setup functions use `setup(bot: commands.Bot)` at module bottom: `src/commands/admin/admin_applications.py`, `src/commands/admin/admin_test_welcome.py`.

**Variables:**
- Constants are uppercase at module scope: `EMBED_TOTAL_LIMIT`, `EMBED_REVIEW_BUFFER`, `EMBED_FIELD_VALUE_LIMIT` in `src/features/applications/service.py`; `DEFAULT_TIMEOUT_MINUTES`, `_ACTIVE_SESSIONS` in `src/features/applications/view/ApplicationDMFlow.py`.
- Local variables use snake_case: `review_channel_id`, `applicant_locale`, `role_warning` in `src/features/applications/service.py` and `src/features/applications/view/ApplicationReviewView.py`.
- Config data from JSON/YAML preserves external camelCase keys where the config schema uses them: `timeoutMinutes`, `buttonLabel`, `buttonLink`, `formTitle` in `src/features/applications/view/ApplicationDMFlow.py`.
- Discord IDs are passed and stored as `int` in Discord-facing code and often converted to `str` for storage fields: `src/storage/models.py`, `src/storage/sqlalchemy_storage.py`.

**Types:**
- Use Python 3.11 union syntax for new annotations: `int | None`, `str | None`, `discord.Embed | None` in `src/features/applications/service.py` and `src/features/applications/admin_service.py`.
- Some older modules still use `typing.Optional`, `Dict`, and `List`; follow the local file style when editing older storage/config code: `src/storage/base.py`, `src/storage/sqlalchemy_storage.py`, `src/features/events/service.py`.
- Use `Protocol` classes for storage contracts: `LanguageStorage`, `ApplicationStorage`, `EventStorage`, `TempVoiceChannelStorage` in `src/storage/base.py`.
- Use lightweight result containers when a service returns multiple values: `ApplicationSubmitResult(NamedTuple)` in `src/features/applications/service.py`.
- SQLAlchemy ORM models are PascalCase classes with lowercase table names: `Application`, `Event`, `TempVoiceChannel` in `src/storage/models.py`.

## Code Style

**Formatting:**
- Ruff import sorting is configured in `pyproject.toml` with `select = ["F", "I"]`; use Ruff-compatible import order.
- No Black, isort, mypy, or formatter configuration is detected. Keep edits compatible with standard 4-space Python indentation and the style already in the edited file.
- Keep line wrapping practical and Ruff-friendly; multiline calls are common in `src/features/applications/service.py`, `src/features/events/service.py`, and `src/storage/sqlalchemy_storage.py`.
- Preserve JSON/YAML-driven visual configuration; do not move server-specific Discord embed text, colors, or footers from `config/*.json`, `config/config.yaml`, or `src/languages/messages/*.json` into Python.

**Linting:**
- Tool: Ruff via `pyproject.toml`.
- Enabled rules: `F` for Pyflakes correctness and `I` for import sorting.
- Primary check command from `AGENTS.md`:
```powershell
$env:UV_CACHE_DIR='.uv-cache'; uv run ruff check main.py src
```
- For targeted changes, run Ruff against touched files or feature directories, for example:
```powershell
$env:UV_CACHE_DIR='.uv-cache'; uv run ruff check src\features\applications
```

## Import Organization

**Order:**
1. Standard library imports: `json`, `time`, `datetime`, `typing`, `urllib.parse`, `asyncio`.
2. Third-party imports: `discord`, `discord.ext.commands`, `pycord.multicog`, `sqlalchemy`, `yaml`.
3. First-party absolute imports from `config` and `src`: `from config.config import config as bot_config`, `from src.utils.logger import get_cool_logger`.
4. Local relative imports only inside tightly scoped packages, mainly sibling view modules: `from .ApplicationReasonModal import ApplicationReasonModal` in `src/features/applications/view/ApplicationReviewView.py`.

**Path Aliases:**
- No Python package alias configuration is detected.
- Use absolute imports rooted at repository packages: `src.*` and `config.*`.
- Avoid deep relative imports across feature boundaries; cross-feature use should stay explicit with `src.features...` paths.

Example import pattern:
```python
from datetime import datetime, timezone

import discord

from config.config import config as bot_config
from src.utils.database import get_db
from src.utils.logger import get_cool_logger
```

## Error Handling

**Patterns:**
- User-facing Discord operations usually catch `discord.Forbidden`, `discord.NotFound`, `discord.HTTPException`, or `discord.DiscordException` and return a compact embed or boolean status: `src/features/applications/service.py`, `src/features/events/service.py`, `src/features/tickets/view/TicketControlPanel.py`.
- Storage methods catch broad exceptions, log context, and return `False`, `None`, `[]`, or a default value instead of propagating: `src/storage/sqlalchemy_storage.py`, `src/storage/sqlalchemy_applications.py`, `src/storage/sqlalchemy_events.py`.
- Config startup errors are fatal and call `sys.exit(1)` after printing a clear message: `config/config.py`.
- Validation helpers raise `ValueError` for invalid input where callers need to show a user-facing error: `src/utils/normalize_unix.py`.
- Async flows use sentinel exceptions for control flow when a user cancels or times out: `ApplicationCancelled` and `ApplicationTimedOut` in `src/features/applications/view/ApplicationDMFlow.py`.
- Do not silently swallow errors unless Discord message cleanup is best-effort; `except Exception: pass` is used only around non-critical UI edits/cleanup in files such as `src/features/applications/view/ApplicationDMFlow.py`.

Recommended storage pattern:
```python
try:
    async with self.session_factory() as session:
        result = await session.execute(...)
        await session.commit()
        return result.rowcount > 0
except Exception as e:
    logger.error(f"Failed to update resource {resource_id}: {e}")
    return False
```

## Logging

**Framework:** Python `logging` through `src.utils.logger.get_cool_logger`.

**Patterns:**
- Create a module-level logger with `logger = get_cool_logger(__name__)`: `main.py`, `src/features/applications/service.py`, `src/utils/news_sender.py`.
- Use `logger.info` for successful admin actions, scheduled jobs, restoration, monitor startup, and state transitions: `main.py`, `src/features/applications/admin_service.py`, `src/features/twitch/twitch_monitor.py`.
- Use `logger.warning` for recoverable missing data, missing translations, or non-fatal permission/DM issues: `src/languages/localize.py`, `src/utils/welcome.py`.
- Use `logger.error` with identifying IDs when an operation fails but execution can continue: `src/features/applications/service.py`, `src/storage/sqlalchemy_storage.py`.
- Use `logger.exception` when stack traces are useful for operational diagnosis: `src/api/health.py`, `src/utils/news_sender.py`, `src/utils/clear_dm_messages.py`.
- Admin-only logs can stay English per `AGENTS.md`; normal user-facing text should be localized.

## Comments

**When to Comment:**
- Use docstrings for public utilities, storage/model classes, and helper functions with non-obvious behavior: `src/utils/embeds.py`, `src/storage/sqlalchemy_storage.py`, `src/languages/localize.py`.
- Use short comments to explain compatibility workarounds or Discord/platform constraints: asyncpg statement cache comments in `src/storage/sqlalchemy_storage.py`, Discord embed budget comments in `src/features/applications/service.py`.
- Avoid comments that restate simple assignments. Prefer naming helpers clearly, for example `_format_answer_value` in `src/features/applications/service.py`.
- Keep comments near the rule they justify; avoid broad commentary unrelated to the edited behavior.

**JSDoc/TSDoc:**
- Not applicable. This is a Python repository.

## Function Design

**Size:** Prefer small helpers for parsing, formatting, validation, and embed construction. Large Discord flows are split into views/session methods rather than a single command body: `ApplicationSession.ask_question`, `ask_choice_question`, `ask_text_question`, and `wait_for_text_answer` in `src/features/applications/view/ApplicationDMFlow.py`.

**Parameters:** Pass Discord context/client/user/guild objects explicitly into services and embed builders when the footer, locale, permissions, or channel lookup depends on context: `build_application_client_embed` in `src/features/applications/service.py`, `build_event_notice_embed` in `src/features/events/service.py`.

**Return Values:** Use clear operational return values:
- `bool` for success/failure operations: `send_application_review`, `apply_application_roles`, `refresh_event_message`.
- `int | None` for created row IDs: `SQLAlchemyStorage.create_ticket`, `SQLAlchemyApplicationMixin.create_application`.
- `dict | None` or `list[dict]` for storage reads: `src/storage/base.py`, `src/storage/sqlalchemy_storage.py`.
- `discord.Embed` or `(discord.Embed, discord.ui.View)` for UI builders: `build_application_started_response`, `build_event_response_embed`.

Prescriptive pattern for Discord command handlers:
```python
await ctx.defer(ephemeral=True)
if not await require_admin(ctx):
    return

await service_function(ctx, ...)
```

Prescriptive pattern for user-facing responses:
- Prefer Discord embeds unless plain text is clearly better.
- Use `src.utils.embeds.build_embed_from_data` or `build_embed_from_template` for JSON/template-driven embeds.
- Use `get_embed_icon(ctx)` for standard footers and pass the bot/client in DMs when the footer should show the bot icon.
- Use `_` from `src.languages.localize` for normal user-visible strings, with keys in `src/languages/i18n/en.json`, `src/languages/i18n/ru.json`, and `src/languages/i18n/lt.json`.

## Module Design

**Exports:** Modules generally expose concrete functions/classes directly; there are no explicit `__all__` exports. Import the specific function/class needed from its module: `from src.features.applications.service import cleanup_old_applications`.

**Barrel Files:** Barrel files are not actively used. `__init__.py` files are mostly package markers, including `src/views/__init__.py` and feature package initializers.

**Feature Boundaries:**
- Commands live in `src/commands/` and `src/commands/admin/` and should stay thin: parse/defer/authenticate, then call services.
- Domain behavior lives in `src/features/<feature>/service.py` or `admin_service.py`: `src/features/applications/service.py`, `src/features/events/service.py`.
- Discord UI components live under feature `view/` or `views/` directories: `src/features/applications/view/`, `src/features/tickets/view/`, `src/features/temp_voice_channels/views/`.
- Storage contracts live in `src/storage/base.py`; SQLAlchemy implementations live in `src/storage/sqlalchemy_storage.py`, `src/storage/sqlalchemy_applications.py`, and `src/storage/sqlalchemy_events.py`.
- Shared helpers live in `src/utils/`; prefer existing helpers before creating new utility modules.

---

*Convention analysis: 2026-05-10*
