# Technology Stack

**Analysis Date:** 2026-05-10

## Languages

**Primary:**
- Python 3.11.15 - Bot runtime, Discord commands/views, storage, health API, scheduler, and integrations in `main.py` and `src/**/*.py`.

**Secondary:**
- YAML - Runtime bot configuration in `config/config.yaml`, with example shape in `config/config.example.yaml`.
- JSON - Discord embed/panel templates and i18n data in `config/applications.json`, `config/tickets.json`, `src/languages/i18n/*.json`, and `src/languages/messages/*.json`.
- TOML - Python project/dependency metadata and Ruff settings in `pyproject.toml`.

## Runtime

**Environment:**
- CPython 3.11.15, with project requirement `>=3.11` declared in `pyproject.toml`.
- Discord gateway bot process launched from `main.py`.
- Optional background HTTP health server in `src/api/health.py`.
- Background scheduled jobs through APScheduler in `src/utils/scheduler.py`.

**Package Manager:**
- uv 0.11.8
- Lockfile: present (`uv.lock`)
- Active dependency manifest: `pyproject.toml`
- Legacy dependency snapshot: `requirements-old.txt` exists but includes many packages not declared in active project dependencies.

## Frameworks

**Core:**
- Pycord 2.7.2 - Discord bot framework, slash commands, persistent views, embeds, channels, roles, and DMs (`main.py`, `src/commands/**/*.py`, `src/features/**/view/**/*.py`).
- pycord-multicog 2.1.1 - Multi-cog bot class and admin subcommand grouping (`main.py`, `src/commands/admin/*.py`).
- SQLAlchemy 2.0.49 - Async ORM and schema creation for storage (`src/storage/sqlalchemy_storage.py`, `src/storage/models.py`).
- APScheduler 3.11.2 - Async scheduled jobs persisted through SQLAlchemyJobStore (`src/utils/scheduler.py`, `src/features/events/service.py`, `src/views/news_wizard.py`).
- Flask 3.1.3 - Health API route definitions (`src/api/health.py`).
- Waitress 3.0.2 - Preferred WSGI server for the health API (`src/api/health.py`).

**Testing:**
- Not detected in active dependencies. No committed project test framework config was found.
- `temp/scheduling/APScheduler_test.py` and `temp/scheduling/fastscheduler_test.py` exist as scratch/test scripts outside the main `src` tree.

**Build/Dev:**
- Ruff - Lint rules configured in `pyproject.toml` with `select = ["F", "I"]`.
- Python compileall - Used by repository instructions for syntax validation of `main.py` and `src`.
- uv - Used for dependency resolution, lockfile management, and command execution.

## Key Dependencies

**Critical:**
- `py-cord` 2.7.2 - Provides Discord API client, commands, interactions, views, channels, guild members, roles, and embeds.
- `pycord-i18n` 1.2.1 - Localizes registered Discord commands and provides translation plumbing in `src/languages/localize.py`.
- `pycord-multicog` 2.1.1 - Supports the bot/cog organization used by `main.py` and admin commands.
- `sqlalchemy` 2.0.49 - Owns database engine/session setup, ORM models, table creation, and storage queries.
- `aiosqlite` 0.22.1 - Async SQLite driver for the default local database URL `sqlite+aiosqlite:///data/data.db`.
- `apscheduler` 3.11.2 - Runs event reminders, event start/check-in notifications, application cleanup, and other scheduled jobs.
- `aiohttp` 3.13.5 - HTTP client used by the Twitch API client in `src/utils/twitch_api.py` through Pycord transitive/runtime dependency resolution.

**Infrastructure:**
- `flask` 3.1.3 - Defines `GET /` and `GET /health` endpoints in `src/api/health.py`.
- `waitress` 3.0.2 - Serves the Flask health app on `0.0.0.0` when available.
- `python-dotenv` 1.2.2 - Loads `.env` for database configuration in `src/utils/db_config.py`.
- `pyyaml` 6.0.3 - Loads `config/config.yaml` in `config/config.py`.
- `tzlocal` 5.3.1 and `tzdata` 2026.2 - Timezone support pulled by scheduler/date handling.

## Configuration

**Environment:**
- `BOT_CONFIG_PATH` optionally overrides the YAML config path in `config/config.py`; default is `config/config.yaml`.
- `DISCORD_BOT_TOKEN` is referenced by `config/config.example.yaml` through `${DISCORD_BOT_TOKEN}` and consumed as `bot_config.bot.token` by `main.py`.
- `DATABASE_URL` is loaded from process environment or `.env` by `src/utils/db_config.py`; default is `sqlite+aiosqlite:///data/data.db`.
- `TWITCH_CLIENT_ID` and `TWITCH_CLIENT_SECRET` are read directly by `src/utils/twitch_api.py`.
- `STORAGE_TYPE` is read in `src/utils/database.py` for backward compatibility and passed through as a legacy ignored value.
- `.env` and `.env.example` are present. Do not read or commit real secret values.

**Build:**
- `pyproject.toml` - Project metadata, dependency declarations, and Ruff lint selection.
- `uv.lock` - Locked dependency graph.
- `config/config.example.yaml` - Safe example runtime configuration.
- `config/config.yaml` - Real runtime configuration file. Treat as environment-specific and avoid placing secrets directly in it.
- `config/applications.json`, `config/tickets.json`, and `src/languages/messages/*.json` - JSON-driven Discord UI/template content.

## Platform Requirements

**Development:**
- Windows PowerShell commands are documented in `AGENTS.md`.
- Use `uv` commands with local cache: `$env:UV_CACHE_DIR='.uv-cache'; uv run python -m compileall main.py src`.
- Use Ruff for linting: `$env:UV_CACHE_DIR='.uv-cache'; uv run ruff check main.py src`.
- A configured `config/config.yaml` is required at runtime unless `BOT_CONFIG_PATH` points elsewhere.
- Discord bot token and Twitch API credentials should be supplied through environment variables.

**Production:**
- Long-running Python process running `main.py`.
- Discord gateway access with required intents (`discord.Intents.all()` in `main.py`).
- Optional health endpoint served by Waitress/Flask when `health.enabled` is true in `config/config.yaml`.
- Persistent storage defaults to local SQLite at `data/data.db`; SQLAlchemy code also accepts PostgreSQL/MySQL/MariaDB-style URLs when compatible async/sync drivers are installed.
- No Dockerfile, docker-compose file, or CI workflow was detected in the repository root or `.github/`.

---

*Stack analysis: 2026-05-10*
