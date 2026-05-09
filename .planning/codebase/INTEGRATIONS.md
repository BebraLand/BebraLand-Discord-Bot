# External Integrations

**Analysis Date:** 2026-05-10

## APIs & External Services

**Discord:**
- Discord Bot API - Primary application platform for slash commands, persistent views, embeds, DMs, roles, channels, and guild/member operations.
  - SDK/Client: `py-cord` via `discord` imports in `main.py`, `src/commands/**/*.py`, `src/events/*.py`, and `src/features/**/*.py`.
  - Auth: `DISCORD_BOT_TOKEN` through `config/config.example.yaml` and `bot_config.bot.token` in `main.py`.

**Twitch:**
- Twitch OAuth client credentials flow - Retrieves app access tokens from `https://id.twitch.tv/oauth2/token`.
  - SDK/Client: `aiohttp.ClientSession` in `src/utils/twitch_api.py`.
  - Auth: `TWITCH_CLIENT_ID`, `TWITCH_CLIENT_SECRET`.
- Twitch Helix API - Polls stream and user data from `https://api.twitch.tv/helix/streams` and `https://api.twitch.tv/helix/users`.
  - SDK/Client: custom async client `TwitchAPIClient` in `src/utils/twitch_api.py`.
  - Auth: OAuth bearer token generated from Twitch client credentials.

**Google Calendar:**
- Google Calendar event URL generator - Builds user-facing add-to-calendar links at `https://calendar.google.com/calendar/render`.
  - SDK/Client: no SDK; URL construction with `urllib.parse.urlencode` in `src/features/events/service.py`.
  - Auth: Not required.

**Static Web Links and Hosted Assets:**
- BebraLand wiki/rules links - Referenced in `config/applications.json` and `src/languages/messages/rules.json`.
  - SDK/Client: Discord embed/link rendering only.
  - Auth: Not required.
- Hosted image URLs - Referenced by Discord embed templates in `config/applications.json` and `src/languages/messages/welcome_message.json`.
  - SDK/Client: Discord embeds fetch the images externally.
  - Auth: Not required.

## Data Storage

**Databases:**
- SQLite local database
  - Connection: `DATABASE_URL`, defaulting to `sqlite+aiosqlite:///data/data.db` in `src/utils/db_config.py`.
  - Client: SQLAlchemy async engine with `aiosqlite` in `src/storage/sqlalchemy_storage.py`.
  - Current local file: `data/data.db` exists.
- PostgreSQL-compatible database
  - Connection: `DATABASE_URL` using `postgresql+asyncpg://...` or legacy `postgresql://` / `postgres://` converted by `src/storage/factory.py`.
  - Client: SQLAlchemy async engine, with asyncpg URL support in code. `asyncpg` is not declared in active `pyproject.toml`.
- MySQL/MariaDB-compatible database
  - Connection: `DATABASE_URL` using `mysql+aiomysql://...`, `mysql://...`, or `mariadb://...` converted by `src/storage/factory.py`.
  - Client: SQLAlchemy async engine, with aiomysql URL support in code. `aiomysql` is not declared in active `pyproject.toml`.
- APScheduler job store
  - Connection: `get_scheduler_database_url()` derives a synchronous SQLAlchemy URL from `DATABASE_URL` in `src/utils/db_config.py`.
  - Client: `SQLAlchemyJobStore` in `src/utils/scheduler.py`.

**File Storage:**
- Local filesystem only.
- YAML config: `config/config.yaml`.
- JSON panels/templates: `config/applications.json`, `config/tickets.json`, `src/languages/messages/*.json`.
- i18n locale files: `src/languages/i18n/en.json`, `src/languages/i18n/ru.json`, `src/languages/i18n/lt.json`.
- Scheduled file directory exists at `data/scheduled_files`.

**Caching:**
- In-process singleton cache for Twitch API client in `src/utils/twitch_api.py`.
- In-process singleton cache for Twitch monitor in `src/features/twitch/twitch_monitor.py`.
- In-process singleton cache for language/storage manager in `src/utils/database.py`.
- APScheduler persisted jobs through SQLAlchemy job store; no Redis/memcached service detected.

## Authentication & Identity

**Auth Provider:**
- Discord - Bot authentication and Discord user/guild identity.
  - Implementation: Pycord bot token login via `bot.run(bot_config.bot.token)` in `main.py`.
- Twitch - Application OAuth for API polling.
  - Implementation: client credentials grant in `src/utils/twitch_api.py`.
- Admin authorization - Custom Discord user/role checks.
  - Implementation: `src/utils/auth.py` uses configured admin values and Discord context.

## Monitoring & Observability

**Error Tracking:**
- None detected. No Sentry, OpenTelemetry, hosted error tracker, or metrics exporter was found.

**Logs:**
- Python logging wrapper in `src/utils/logger.py`.
- Integration failures are logged in `src/utils/twitch_api.py`, `src/features/twitch/twitch_monitor.py`, `src/storage/sqlalchemy_storage.py`, `src/utils/database.py`, and `src/api/health.py`.
- Health status exposed through Flask routes in `src/api/health.py`.

## CI/CD & Deployment

**Hosting:**
- Not detected. The repository contains no Dockerfile, docker-compose file, Procfile, platform config, or deployment workflow.
- Runtime expects a long-running Python process and optional HTTP health port from `config/config.yaml`.

**CI Pipeline:**
- None detected. No `.github/workflows` files were found.

## Environment Configuration

**Required env vars:**
- `DISCORD_BOT_TOKEN` - Discord bot login token, referenced by `config/config.example.yaml`.
- `DATABASE_URL` - Optional but recommended for persistent production storage; defaults to local SQLite when missing.
- `TWITCH_CLIENT_ID` - Required for Twitch monitoring to fetch OAuth tokens.
- `TWITCH_CLIENT_SECRET` - Required for Twitch monitoring to fetch OAuth tokens.
- `BOT_CONFIG_PATH` - Optional override for runtime YAML config path.
- `STORAGE_TYPE` - Legacy optional value; read but effectively ignored by the SQLAlchemy storage factory.

**Secrets location:**
- `.env` file present - contains environment configuration and must not be read or committed with real secrets.
- `.env.example` file present - safe example location for env var names.
- `config/config.yaml` supports `${ENV_VAR}` substitution through `config/config.py`; keep real tokens in env vars rather than hardcoding YAML.

## Webhooks & Callbacks

**Incoming:**
- `GET /health` - Health check endpoint in `src/api/health.py`.
- `GET /` - Basic service info endpoint in `src/api/health.py`.
- Discord gateway events and interactions - handled through Pycord in `main.py`, `src/events/*.py`, `src/commands/**/*.py`, and persistent views under `src/features/**/view/**/*.py`.

**Outgoing:**
- Discord API calls - Sends/edits/deletes messages, DMs users, manages roles, creates channels, fetches members/channels/messages through Pycord across `src/features/**/*.py` and `src/commands/**/*.py`.
- Twitch OAuth and Helix API calls - Outgoing HTTP POST/GET requests in `src/utils/twitch_api.py`.
- No incoming third-party webhooks were detected.
- No outgoing webhook POST integrations were detected.

---

*Integration audit: 2026-05-10*
