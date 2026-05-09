# Codebase Concerns

**Analysis Date:** 2026-05-10

## Tech Debt

**Large mixed-responsibility modules:**
- Issue: Several modules combine Discord UI construction, business rules, persistence calls, API calls, localization, and error handling in a single file.
- Files: `src/views/news_wizard.py`, `src/utils/news_sender.py`, `src/storage/sqlalchemy_storage.py`, `src/features/temp_voice_channels/views/TempVoiceControlView.py`, `src/features/events/service.py`, `src/features/applications/view/ApplicationDMFlow.py`, `src/features/applications/service.py`
- Impact: Feature changes require editing long files with many implicit dependencies, increasing regression risk around Discord limits, permissions, and localization.
- Fix approach: Split by responsibility. Keep Discord view classes in `src/features/*/view/`, move pure formatting/building helpers into feature-local service/helper modules, keep database operations in `src/storage/*`, and cover each extracted unit with focused tests.

**Storage errors collapse into falsey values:**
- Issue: Storage methods catch broad `Exception` and return `None`, `False`, or `[]`, making database failures look like missing records or valid empty results.
- Files: `src/storage/sqlalchemy_storage.py`, `src/storage/sqlalchemy_events.py`, `src/storage/sqlalchemy_applications.py`
- Impact: User-facing flows can continue after partial persistence failure, while callers cannot distinguish "not found" from "database unavailable." This affects language preferences, tickets, applications, events, Twitch state, and temp voice state.
- Fix approach: Return explicit result objects or raise typed storage exceptions at the storage boundary. Convert known not-found cases into domain statuses in feature services, not in the storage layer.

**Manual schema drift handling:**
- Issue: `Base.metadata.create_all` is paired with ad hoc `ALTER TABLE` statements for only event columns.
- Files: `src/storage/sqlalchemy_storage.py`, `src/storage/models.py`, `src/storage/sqlalchemy_events.py`, `src/storage/sqlalchemy_applications.py`
- Impact: New model fields outside the covered event additions are not migrated into existing databases. SQLite may appear healthy while PostgreSQL/MySQL deployments diverge.
- Fix approach: Add a migration tool such as Alembic or a small versioned migration runner. Keep schema changes out of `initialize()` except for bootstrapping empty databases.

**Global singletons and module-level runtime state:**
- Issue: Bot, storage manager, Twitch monitor, Twitch API client, scheduler, localization maps, and active application sessions live in module-level globals.
- Files: `src/utils/bot_instance.py`, `src/utils/database.py`, `src/features/twitch/twitch_monitor.py`, `src/utils/twitch_api.py`, `src/utils/scheduler.py`, `src/languages/localize.py`, `src/features/applications/view/ApplicationDMFlow.py`
- Impact: Tests and reconnect/reload paths inherit state across runs. Application DM sessions are memory-only and disappear on process restart, while persistent Discord views survive.
- Fix approach: Introduce explicit lifecycle setup/teardown and pass dependencies into feature services. Keep transient session state either in storage or in a bounded in-memory registry with cleanup and test reset hooks.

**Command loading is hardcoded by filename:**
- Issue: Extension loading encodes command toggles with per-file `if filename == ...` branches and loads admin submodules separately.
- Files: `src/utils/load_extensions.py`, `config/command.py`, `src/commands/`, `src/commands/admin/`
- Impact: New commands can be loaded unintentionally if a developer forgets to update `src/utils/load_extensions.py` or `config/command.py`.
- Fix approach: Use a declarative command registry or module-level metadata. Make the default for unknown admin modules explicit and test command discovery.

**Mixed text localization coverage:**
- Issue: Normal-user application DM strings and several temp voice/user responses are hardcoded English instead of going through `src.languages.localize._`.
- Files: `src/features/applications/view/ApplicationDMFlow.py`, `src/features/applications/view/ApplicationReviewView.py`, `src/features/temp_voice_channels/views/TempVoiceControlView.py`, `main.py`
- Impact: User-facing workflows can display English text to Russian/Lithuanian users, violating the repository i18n convention.
- Fix approach: Add keys to `src/languages/i18n/en.json`, `src/languages/i18n/ru.json`, and `src/languages/i18n/lt.json`; localize all normal-user visible strings in feature code.

## Known Bugs

**Unauthenticated message deletion slash command:**
- Symptoms: `/clear` in `main.py` deletes messages from the current channel without `require_admin`, Discord permission checks in code, localization, or amount validation.
- Files: `main.py`
- Trigger: Any user who can invoke the registered `/clear` command and whose interaction reaches `ctx.channel.purge(limit=amount)`.
- Workaround: Disable or remove the top-level command registration until it uses `src.utils.auth.require_admin` and validates `amount`.

**Application review channel fetch can fail outside error handling:**
- Symptoms: `send_application_review` converts `review_channel_id` with `int()` and calls `guild.fetch_channel()` without catching malformed IDs, `NotFound`, `Forbidden`, or network errors.
- Files: `src/features/applications/service.py`, `config/config.example.yaml`
- Trigger: `modules.applications.review_channel_id` is unset, set to a non-numeric placeholder, points to a missing channel, or the bot lacks channel access.
- Workaround: Configure a valid review channel ID and permissions. Add validation and `discord.DiscordException` handling before application submission reaches persistence.

**Twitch monitor task is fire-and-forget:**
- Symptoms: `TwitchMonitor.start()` creates `_monitor_loop()` with `asyncio.create_task()` but does not retain the task, await it during shutdown, or cancel it.
- Files: `src/features/twitch/twitch_monitor.py`, `main.py`
- Trigger: Bot reconnect/reload/shutdown paths or repeated startup paths that call `get_twitch_monitor(bot).start()`.
- Workaround: Store the task on `TwitchMonitor`, cancel/await it in `stop()`, and gate startup on both `is_running` and task state.

**Twitch stream notifications use the first guild:**
- Symptoms: Live role changes and notification cleanup operate on `self.bot.guilds[0]`.
- Files: `src/features/twitch/twitch_monitor.py`
- Trigger: Bot joins more than one guild or the configured Twitch role/channel belongs to a guild that is not first in `bot.guilds`.
- Workaround: Resolve the guild from `bot_config.modules.twitch.channel_id` or add an explicit guild ID to `config/config.yaml`.

**Event registration race can overfill main slots or duplicate users:**
- Symptoms: Registration checks existing rows and main count before inserting, but there is no database uniqueness constraint or transaction-level lock around `(event_id, user_id)` and capacity.
- Files: `src/storage/models.py`, `src/storage/sqlalchemy_events.py`, `src/features/events/view/EventRegistrationView.py`
- Trigger: Multiple users register at the same time near capacity, or the same user double-clicks/retries during latency.
- Workaround: Add database constraints, handle `IntegrityError`, and move capacity assignment into a serialized transaction per event.

## Security Considerations

**Destructive command lacks authorization:**
- Risk: Users can delete channel history if the slash command is available to them.
- Files: `main.py`, `src/utils/auth.py`
- Current mitigation: None in `main.py`; admin commands under `src/commands/admin/` use `require_admin`.
- Recommendations: Require `src.utils.auth.require_admin(ctx)`, validate purge limits, use localized embed responses, and consider Discord application command permissions.

**Health endpoint exposes operational metadata on all interfaces:**
- Risk: `/health` binds to `0.0.0.0` and returns readiness, guild count, user count, uptime, and latency without authentication.
- Files: `src/api/health.py`, `main.py`, `config/config.example.yaml`
- Current mitigation: Only bot-level health data is exposed; no secrets are returned.
- Recommendations: Bind to localhost behind a reverse proxy where possible, make host configurable, and avoid exposing user/guild counts on public endpoints unless required.

**Scheduler database URL renders password-visible connection strings:**
- Risk: `get_scheduler_database_url()` returns a sync URL with `hide_password=False`, so future logs or exception messages around the scheduler can expose database credentials.
- Files: `src/utils/db_config.py`, `src/utils/scheduler.py`
- Current mitigation: The returned URL is not directly logged in the current scheduler setup.
- Recommendations: Use `hide_password=True` for logging and keep credential-bearing strings scoped to connection construction only.

**Local secret and runtime artifacts exist in ignored directories:**
- Risk: `.env`, `config/config.yaml`, `data/data.db`, and env-like files under `temp/envs/` exist in the working tree. They are ignored, but accidental copy/paste, archive, or manual git add can leak secrets or production data.
- Files: `.env`, `config/config.yaml`, `data/data.db`, `temp/envs/.env copy`, `temp/envs/BebraLandReal.env`, `temp/envs/mysql.env`, `temp/envs/postgres.env`, `temp/envs/sqlite.env`, `.gitignore`
- Current mitigation: `.env`, `config/config.yaml`, `data/`, and `temp/` are ignored.
- Recommendations: Keep real env files outside the repository tree, add secret scanning to CI, and document that `temp/envs/` must not be used for durable credential storage.

**Admin identity depends on static user IDs only:**
- Risk: `is_admin` checks `ctx.user.id` against `bot_config.bot.admin_list`; role-based admin authorization is not used for most admin commands.
- Files: `src/utils/auth.py`, `config/config.example.yaml`, `src/commands/admin/`
- Current mitigation: Application review buttons also allow `modules.applications.reviewer_role_id`.
- Recommendations: Normalize configured IDs to integers, support role-based admin checks where appropriate, and fail closed on malformed admin config.

## Performance Bottlenecks

**News broadcasts are serial and rate-limit-prone:**
- Problem: News broadcasts send to channels and members one recipient at a time with a fixed one-second delay.
- Files: `src/utils/news_sender.py`, `src/commands/admin/admin_send_news.py`
- Cause: `_broadcast_news` loops through target channels and members sequentially, fetching each member language and sending each DM inline.
- Improvement path: Use a bounded queue with rate-limit-aware workers, persist broadcast status for long runs, and produce progress summaries instead of holding one interaction flow open.

**Event embed refresh reads all registrations every time:**
- Problem: Event message refresh loads all event registrations to compute counts and render lists.
- Files: `src/features/events/service.py`, `src/storage/sqlalchemy_events.py`
- Cause: `build_event_embed` calls `get_event_registrations` and filters/counts in Python.
- Improvement path: Add aggregate storage methods for counts and limit list reads to the displayed rows. Keep full registration exports separate from panel refresh.

**Twitch API client creates a new HTTP session per call:**
- Problem: Each Twitch token, stream, and user lookup opens a new `aiohttp.ClientSession`.
- Files: `src/utils/twitch_api.py`, `src/features/twitch/twitch_monitor.py`
- Cause: The client does not own a reusable session or close lifecycle.
- Improvement path: Create one `aiohttp.ClientSession` per `TwitchAPIClient`, close it during bot shutdown, and batch or parallelize streamer checks within Twitch API rate limits.

**Default intents request all Discord intents:**
- Problem: The bot starts with `discord.Intents.all()`.
- Files: `main.py`
- Cause: Feature code does not declare a minimal intent set.
- Improvement path: Define required intents per feature and only enable privileged intents that the bot actually needs, such as members for role/member workflows.

## Fragile Areas

**Applications DM wizard:**
- Files: `src/features/applications/view/ApplicationDMFlow.py`, `src/features/applications/service.py`, `src/features/applications/config.py`, `config/applications.json`
- Why fragile: The flow relies on memory-only `_ACTIVE_SESSIONS`, long-lived Discord views, free-form JSON config, and manual answer validation. Several user-visible messages are hardcoded.
- Safe modification: Validate `config/applications.json` before starting the flow, keep question count/options under Discord limits, preserve `APPLICATION_ANSWER_MAX`, and test cancel/timeout/skip/retry paths.
- Test coverage: No first-party tests cover application session state, text validation, config normalization, or review submission.

**News scheduling and payload composition:**
- Files: `src/utils/news_sender.py`, `src/views/news_wizard.py`, `src/views/news_modal.py`, `src/commands/admin/admin_send_news.py`, `src/utils/scheduler.py`
- Why fragile: Immediate sends, scheduled sends, image handling, placeholder replacement, embedded JSON, link components, localization, ghost pings, and summaries all share the same large helper.
- Safe modification: Preserve Discord limits of 10 embeds, 5 rows, 5 components per row, field length limits, and allowed mention handling. Add tests for `_message_payload_for`, `_view_from_components`, `_broadcast_members`, and scheduled image cleanup before broad changes.
- Test coverage: Only ignored temp scheduler experiments exist; there is no committed test suite for news payload or scheduler behavior.

**Temporary voice channel control panel:**
- Files: `src/features/temp_voice_channels/views/TempVoiceControlView.py`, `src/features/temp_voice_channels/create_temp_channel.py`, `src/features/temp_voice_channels/restore_temp_channels.py`, `src/storage/sqlalchemy_storage.py`
- Why fragile: The view mutates Discord channel permissions directly from button handlers and depends on persisted ownership/channel rows after restarts.
- Safe modification: Keep owner checks before each action, fetch current owner from storage, preserve existing permission overwrites, and handle stale/deleted channels idempotently.
- Test coverage: No first-party tests cover permission overwrite generation, ownership transfer, restore behavior, or stale channel cleanup.

**Storage model evolution:**
- Files: `src/storage/models.py`, `src/storage/base.py`, `src/storage/sqlalchemy_storage.py`, `src/storage/sqlalchemy_events.py`, `src/storage/sqlalchemy_applications.py`
- Why fragile: The storage protocol spans many feature domains, but migrations are manual and methods often return falsey values on failure.
- Safe modification: Update `src/storage/base.py` first, then implementation mixins, then callers. Add compatibility migrations and tests using a temporary SQLite database.
- Test coverage: No first-party tests verify the protocol implementation, schema initialization, migrations, or status-preserving cleanup.

**Localization loading:**
- Files: `src/languages/localize.py`, `src/languages/i18n/en.json`, `src/languages/i18n/ru.json`, `src/languages/i18n/lt.json`
- Why fragile: Malformed locale files are silently skipped, missing keys fall back at runtime, and callers format translated strings without compile-time validation.
- Safe modification: Add a locale key parity check and placeholder parity check. Fail checks in CI when one locale misses a key used by source.
- Test coverage: No first-party tests validate locale JSON, missing-key behavior, or format placeholders.

## Scaling Limits

**Application sessions:**
- Current capacity: One memory entry per `(user_id, guild_id)` active session in `_ACTIVE_SESSIONS`.
- Limit: Sessions disappear on process restart and can become stale if the process dies before `finally` clears them.
- Scaling path: Store active application state in the database with expiration timestamps, and restore or invalidate sessions on startup.

**News broadcast fanout:**
- Current capacity: Sequential sends with one-second sleeps can take minutes or hours for large role/user sets.
- Limit: Long broadcasts can exceed interaction expectations, lose progress on restart, and hit Discord DM failures at scale.
- Scaling path: Persist broadcast jobs, process recipients in bounded batches, and record per-recipient delivery state.

**Event registration consistency:**
- Current capacity: Suitable for low-concurrency button usage.
- Limit: Concurrent registrations near `player_limit` can produce incorrect positions or over-capacity main lists without database constraints.
- Scaling path: Add unique indexes and serialized capacity assignment, or implement a per-event lock with database-enforced uniqueness as the final guard.

**Local SQLite fallback:**
- Current capacity: Single-process local development or small deployment.
- Limit: If primary storage configuration fails, production can silently switch to `data/data.db`, splitting state from the intended database.
- Scaling path: Make fallback opt-in for production, fail closed when `DATABASE_URL` is set but unreachable, and alert on fallback activation.

## Dependencies at Risk

**py-cord and pycord ecosystem packages:**
- Risk: Core bot behavior depends on Pycord-specific APIs and `pycord-i18n`/`pycord-multicog`.
- Impact: Discord API changes or package stagnation can affect slash commands, persistent views, localization, and extension loading.
- Migration plan: Keep Pycord usage isolated in view/command modules. Avoid spreading Pycord-only constructs into pure services so a future discord.py/nextcord migration is bounded.

**APScheduler SQLAlchemyJobStore with async app storage:**
- Risk: Runtime storage uses async SQLAlchemy URLs while APScheduler uses a converted synchronous URL.
- Impact: Driver mismatch or unsupported URL conversion can break scheduled jobs independently from bot storage.
- Migration plan: Add startup validation for both async storage and scheduler job store. Consider a scheduler adapter that owns URL conversion and health checks.

**Unpinned transitive behavior despite lockfile:**
- Risk: `pyproject.toml` uses lower bounds only, relying on `uv.lock` for reproducibility.
- Impact: Environments that ignore `uv.lock` can install newer dependency versions with incompatible behavior.
- Migration plan: Treat `uv.lock` as required for deployment, document `uv sync --locked`, and run CI with the lockfile.

## Missing Critical Features

**First-party automated tests:**
- Problem: The repository has no committed first-party `tests/` suite; only ignored experiments under `temp/` and dependency tests under `.venv`/`.uv-cache` were detected.
- Blocks: Safe refactors of storage, application DM flows, news broadcasts, event registration, and temp voice permission logic.

**CI verification for compile/lint/tests:**
- Problem: No active first-party test suite is available for CI to run beyond compile/lint checks.
- Blocks: Regression detection for Discord payload limits, permissions, role changes, database migrations, and localization key parity.

**Database migrations and indexes:**
- Problem: The schema lacks explicit unique constraints for event registrations and migration tracking.
- Blocks: Reliable capacity enforcement, duplicate prevention, and safe production schema evolution.

**Operational shutdown lifecycle:**
- Problem: Background systems such as health server, scheduler, Twitch monitor, storage engine, and reusable HTTP clients do not share one explicit shutdown path.
- Blocks: Clean restarts, reliable testing, and predictable deployment shutdown behavior.

## Test Coverage Gaps

**Storage protocol and schema:**
- What's not tested: Initialization, fallback behavior, async CRUD methods, event schema additions, application cleanup, and storage protocol conformance.
- Files: `src/storage/base.py`, `src/storage/models.py`, `src/storage/sqlalchemy_storage.py`, `src/storage/sqlalchemy_events.py`, `src/storage/sqlalchemy_applications.py`, `src/utils/database.py`
- Risk: Data loss, schema drift, false success, and production-only database errors.
- Priority: High

**Authorization and admin commands:**
- What's not tested: `require_admin`, top-level `/clear`, admin command guards, reviewer-role checks, malformed admin config.
- Files: `main.py`, `src/utils/auth.py`, `src/commands/admin/`, `src/features/applications/view/ApplicationReviewView.py`
- Risk: Unauthorized destructive actions and broken admin access.
- Priority: High

**Application flow:**
- What's not tested: JSON config normalization, DM start/cancel/timeout, text length limits, select/button answers, review embed size guard, role transitions, cleanup rules.
- Files: `src/features/applications/config.py`, `src/features/applications/view/ApplicationDMFlow.py`, `src/features/applications/service.py`, `src/features/applications/view/ApplicationReviewView.py`
- Risk: Application submissions fail silently, exceed Discord limits, or apply incorrect roles.
- Priority: High

**Event registration and reminders:**
- What's not tested: Language parsing, reminder parsing, registration capacity, duplicate prevention, backup promotion, check-in timing, cancellation notices.
- Files: `src/features/events/service.py`, `src/features/events/admin_service.py`, `src/features/events/view/EventRegistrationView.py`, `src/storage/sqlalchemy_events.py`
- Risk: Incorrect rosters, missed reminders, and inconsistent event panels.
- Priority: High

**News payloads and scheduling:**
- What's not tested: Embed JSON conversion, link components, image positioning, ghost ping allowed mentions, scheduled image cleanup, broadcast summary limits.
- Files: `src/utils/news_sender.py`, `src/views/news_wizard.py`, `src/views/news_modal.py`, `src/commands/admin/admin_send_news.py`, `src/utils/scheduler.py`
- Risk: Broken announcements, unsafe mentions, long-running failed broadcasts, and leaked scheduled image files.
- Priority: High

**Temp voice permissions:**
- What's not tested: Owner checks, lock/unlock/hide/show permission overwrites, transfer ownership, invite/kick/permit/reject selectors, orphan cleanup.
- Files: `src/features/temp_voice_channels/views/TempVoiceControlView.py`, `src/features/temp_voice_channels/views/selectors/`, `src/features/temp_voice_channels/create_temp_channel.py`, `src/features/temp_voice_channels/cleanup_orphaned_channels.py`
- Risk: Users can lose access, retain unwanted access, or control stale channels.
- Priority: Medium

**Localization parity:**
- What's not tested: Key parity across `en`, `ru`, and `lt`; placeholder parity; absence of hardcoded normal-user strings.
- Files: `src/languages/i18n/en.json`, `src/languages/i18n/ru.json`, `src/languages/i18n/lt.json`, `src/languages/localize.py`, `src/features/`, `src/commands/`
- Risk: Runtime fallback keys, formatting errors, and inconsistent user experience by locale.
- Priority: Medium

---

*Concerns audit: 2026-05-10*
