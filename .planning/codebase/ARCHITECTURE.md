<!-- refreshed: 2026-05-10 -->
# Architecture

**Analysis Date:** 2026-05-10

## System Overview

```text
┌─────────────────────────────────────────────────────────────┐
│                    Pycord Bot Runtime                        │
│                       `main.py`                              │
├──────────────────┬──────────────────┬───────────────────────┤
│ Slash Commands   │ Discord Events   │ Persistent UI Views   │
│ `src/commands`   │ `src/events`     │ `src/features/*/view` │
└────────┬─────────┴────────┬─────────┴──────────┬────────────┘
         │                  │                     │
         ▼                  ▼                     ▼
┌─────────────────────────────────────────────────────────────┐
│                  Feature Service Layer                       │
│ `src/features/applications`, `src/features/events`,          │
│ `src/features/tickets`, `src/features/temp_voice_channels`,  │
│ `src/features/twitch`, `src/utils/news_sender.py`            │
└─────────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────┐
│          Shared Infrastructure and Storage                   │
│ `config/config.py`, `src/utils/database.py`,                 │
│ `src/storage/sqlalchemy_storage.py`, `src/utils/scheduler.py`│
└─────────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────┐
│ External State and Discord APIs                              │
│ `data/data.db`, APScheduler job store, Discord guild state,  │
│ `config/*.json`, `src/languages/i18n/*.json`, Twitch API     │
└─────────────────────────────────────────────────────────────┘
```

## Component Responsibilities

| Component | Responsibility | File |
|-----------|----------------|------|
| Bot bootstrap | Creates `pycord.multicog.Bot`, registers global bot instance, initializes i18n, loads extensions, starts scheduler, health API, persistent views, restoration, and Twitch monitor | `main.py` |
| Extension loader | Dynamically loads event and command Cogs from `src/events`, `src/commands`, and `src/commands/admin` with feature flags | `src/utils/load_extensions.py` |
| Runtime config | Loads YAML config into dot-access dictionaries and resolves `${ENV_VAR}` placeholders | `config/config.py` |
| Command flags | Enables or disables selected command Cogs before extension loading | `config/command.py` |
| Storage facade | Creates a lazy global `LanguageManager`, initializes storage, exposes `get_db()`, `get_language()`, and `set_language()` | `src/utils/database.py` |
| Storage protocol | Defines async storage contracts for language, tickets, applications, events, and temp voice channels | `src/storage/base.py` |
| SQLAlchemy storage | Owns async engine/session lifecycle and implements language, ticket, Twitch state, guild settings, and temp voice persistence | `src/storage/sqlalchemy_storage.py` |
| SQLAlchemy models | Declares database tables for user languages, tickets, applications, events, stream state, guild settings, temp voice, and invites | `src/storage/models.py` |
| Application service | Builds application embeds, submits applications, sends review messages, applies roles, cleans old applications, and notifies users | `src/features/applications/service.py` |
| Application views | Handles panel button, DM wizard session, question views, review buttons, and reason modal | `src/features/applications/view` |
| Event services | Creates/administers event records, posts/refreshes panels, schedules reminders, check-in, and start notifications | `src/features/events/admin_service.py`, `src/features/events/service.py` |
| Ticket service | Creates ticket channels, writes ticket records, sends close controls, and logs creation | `src/features/tickets/create_ticket.py` |
| Temp voice feature | Creates/restores/deletes temporary channels, manages ownership and channel controls | `src/features/temp_voice_channels` |
| Twitch monitor | Polls Twitch streams, updates live roles and notification messages, persists stream state | `src/features/twitch/twitch_monitor.py` |
| Health API | Runs a Flask/Waitress health server in a background thread when enabled | `src/api/health.py` |
| Embed helpers | Converts JSON-like templates into Discord embeds and centralizes footer icon lookup | `src/utils/embeds.py` |
| i18n | Loads locale JSON files and exposes `_()` lookup with default-language fallback | `src/languages/localize.py` |

## Pattern Overview

**Overall:** Event-driven Discord bot with dynamic Cog loading, feature-oriented service modules, persistent Discord UI views, and a shared async SQLAlchemy storage facade.

**Key Characteristics:**
- `main.py` owns process startup and runtime wiring; feature behavior lives in Cogs, views, services, and utility modules.
- `src/commands` and `src/events` expose Pycord Cogs with `setup(bot)` functions that `src/utils/load_extensions.py` loads dynamically.
- User interactions flow through Discord slash commands, event listeners, buttons, selects, and modals into feature services.
- Storage access is centralized through `await get_db()` from `src/utils/database.py`; new durable state should go through `src/storage/base.py` and SQLAlchemy implementation files.
- Bot visual content is split between config/templates (`config/applications.json`, `config/tickets.json`, `src/languages/messages/*.json`) and shared embed builders in `src/utils/embeds.py`.

## Layers

**Bootstrap Layer:**
- Purpose: Start the bot process, register persistent components, and initialize background infrastructure.
- Location: `main.py`
- Contains: `Bot` construction at `main.py:27`, `on_ready` startup work at `main.py:32`, health API startup, scheduler startup, and inline basic slash commands.
- Depends on: `config/config.py`, `src/utils/load_extensions.py`, `src/utils/scheduler.py`, feature view classes, persistent view registration utilities.
- Used by: The Python process entry point `if __name__ == "__main__"` at `main.py:83`.

**Discord Extension Layer:**
- Purpose: Translate Discord commands and events into feature-service calls.
- Location: `src/commands`, `src/events`
- Contains: Pycord Cogs, slash command definitions, event listeners, and `setup(bot)` registration functions.
- Depends on: Feature services under `src/features`, auth in `src/utils/auth.py`, localization, config, and embed helpers.
- Used by: `src/utils/load_extensions.py:11`.

**Persistent UI Layer:**
- Purpose: Represent Discord buttons, selects, modals, and persistent views.
- Location: `src/features/*/view`, `src/views`
- Contains: `discord.ui.View`, `discord.ui.Modal`, and `discord.ui.Select` classes such as `ApplicationPanel`, `ApplicationReviewView`, `EventRegistrationView`, `TicketPanel`, `TempVoiceControlView`, `LanguageSelector`.
- Depends on: Feature services, `get_db()`, `get_language()`, config, i18n, and embed helpers.
- Used by: `main.py`, send utilities in `src/utils/send`, and persistent view registration modules.

**Feature Service Layer:**
- Purpose: Own feature rules and side effects that are too large for Cogs/views.
- Location: `src/features`, selected workflow utilities in `src/utils/news_sender.py` and `src/utils/welcome.py`
- Contains: Application submission/review, event scheduling, ticket creation, temp voice channel management, Twitch monitoring, news broadcast logic.
- Depends on: Discord API objects, storage facade, scheduler, config, localization, and embed utilities.
- Used by: Commands, events, views, scheduled jobs, and startup restoration.

**Storage Layer:**
- Purpose: Persist application state and expose async storage methods.
- Location: `src/storage`, `src/utils/database.py`, `src/utils/db_config.py`
- Contains: Protocol definitions, SQLAlchemy models, SQLAlchemy storage implementation, feature mixins, and database URL helpers.
- Depends on: SQLAlchemy async engine, dotenv database URL loading, runtime config for selected defaults.
- Used by: All features through `await get_db()`.

**Configuration and Template Layer:**
- Purpose: Keep runtime values, module toggles, Discord IDs, message templates, and localized text outside feature code.
- Location: `config`, `src/languages`
- Contains: YAML config, JSON panel/form templates, command toggles, i18n locale files, message JSON.
- Depends on: Filesystem reads and environment variable placeholders.
- Used by: Startup, commands, services, views, embed builders, and localization.

**Background Job Layer:**
- Purpose: Run scheduled sends, reminders, event lifecycle notifications, and monitoring loops.
- Location: `src/utils/scheduler.py`, `src/features/events/service.py`, `src/features/twitch/twitch_monitor.py`, `src/views/news_wizard.py`, `src/utils/news_sender.py`
- Contains: APScheduler singleton, scheduled job functions, Twitch polling loop, scheduled news task.
- Depends on: Synchronous SQLAlchemy job store URL from `src/utils/db_config.py`, global bot lookup in `src/utils/bot_instance.py`, feature services.
- Used by: `main.py:on_ready`, admin command services, and news wizard.

## Data Flow

### Bot Startup Path

1. Load YAML config with optional environment placeholders (`config/config.py:19`).
2. Construct the Pycord bot and store it globally for utilities (`main.py:27`, `src/utils/bot_instance.py:7`).
3. Load locale JSON into Pycord i18n (`main.py:30`, `src/languages/localize.py:17`).
4. Load event and command Cogs dynamically (`main.py:59`, `src/utils/load_extensions.py:11`).
5. Start scheduler and register persistent views on ready (`main.py:32`).
6. Restore temp voice state, register ticket/application/event views, clean old applications, and start Twitch monitoring (`main.py:42` through `main.py:55`).
7. Start the optional health API server if enabled (`main.py:65`, `src/api/health.py:11`).

### Application Submission Path

1. User clicks the persistent Apply button in `ApplicationPanel` (`src/features/applications/view/ApplicationPanel.py:25`).
2. The view validates bot users, application availability, review channel config, pending/accepted applications, and reapply rules using `get_db()` (`src/features/applications/view/ApplicationPanel.py:40`).
3. The view starts a DM wizard and records the active in-memory session (`src/features/applications/view/ApplicationDMFlow.py:549`).
4. `ApplicationSession` asks text/select/button questions and validates answers (`src/features/applications/view/ApplicationDMFlow.py:366`).
5. `submit_application_answers()` creates an application record, updates roles, and sends the review message (`src/features/applications/service.py:195`).
6. Review buttons in `ApplicationReviewView` decide the application, update storage, update roles, DM the user, edit the review embed, and run cleanup (`src/features/applications/view/ApplicationReviewView.py:22`).

### Event Management Path

1. Admin slash commands in `src/commands/admin/admin_events.py` defer and require admin access.
2. `create_event()` validates times, player limit, languages, check-in settings, and writes the event through storage (`src/features/events/admin_service.py:44`).
3. The event panel is posted immediately or scheduled through APScheduler (`src/features/events/admin_service.py:361`).
4. `send_event_panel()` sends an embed plus `EventRegistrationView`, stores Discord message IDs, and registers the persistent view (`src/features/events/service.py:253`).
5. Registration/check-in interactions update storage and call `refresh_event_message()` to rebuild the panel (`src/features/events/service.py:222`).
6. Reminder, check-in-open, and start jobs use global bot lookup to DM users and refresh panels (`src/features/events/service.py:325`, `src/features/events/service.py:344`, `src/features/events/service.py:404`).

### Ticket Creation Path

1. User interacts with `TicketPanel` in `src/features/tickets/view/TicketPanel.py`.
2. Optional modal data is gathered in `TicketFormModal` (`src/features/tickets/view/TicketFormModal.py`).
3. `create_ticket()` checks per-user limits, creates a ticket row, creates a private Discord channel, stores the channel ID, and sends close controls (`src/features/tickets/create_ticket.py:14`).
4. Close/confirm views update storage, notify users, create transcript data, and clean channel state (`src/features/tickets/view/CloseTicketView.py`, `src/features/tickets/view/ConfirmCloseView.py`).

### Temp Voice Path

1. Voice state listener receives joins/leaves (`src/events/on_voice_state_update.py:24`).
2. Lobby joins call `create_temp_channel()` when the user has no reusable empty temp channel (`src/events/on_voice_state_update.py:43`, `src/features/temp_voice_channels/create_temp_channel.py:15`).
3. Channel creation writes Discord permission overwrites, sends `TempVoiceControlView`, and persists channel metadata (`src/features/temp_voice_channels/create_temp_channel.py:15`).
4. Owner leaves trigger auto-claim or scheduled deletion (`src/events/on_voice_state_update.py:183`).
5. Startup restoration reattaches temp voice control views (`main.py:48`, `src/features/temp_voice_channels/restore_temp_channels.py`).

### Twitch Monitor Path

1. `on_ready` obtains and starts the global monitor (`main.py:55`, `src/features/twitch/twitch_monitor.py:394`).
2. `TwitchMonitor.start()` cleans removed streamers and creates the async polling task (`src/features/twitch/twitch_monitor.py:28`).
3. Each loop reads configured streamers, queries Twitch API, compares SQLAlchemy stream state, updates Discord roles/messages, and writes stream state (`src/features/twitch/twitch_monitor.py:104`).

**State Management:**
- Durable state lives in SQLAlchemy tables declared in `src/storage/models.py`.
- Scheduler state is persisted by APScheduler's `SQLAlchemyJobStore` configured in `src/utils/scheduler.py`.
- Runtime singletons include `bot` in `main.py`, `_bot` in `src/utils/bot_instance.py`, `_manager` in `src/utils/database.py`, `_twitch_monitor` in `src/features/twitch/twitch_monitor.py`, and locale cache `LOCALES` in `src/languages/localize.py`.
- In-memory session state is used for active application DM sessions in `src/features/applications/view/ApplicationDMFlow.py`.

## Key Abstractions

**Pycord Cog:**
- Purpose: Register commands and event listeners through extension loading.
- Examples: `src/commands/admin/admin_applications.py`, `src/commands/set_lang.py`, `src/events/on_voice_state_update.py`.
- Pattern: Define a `commands.Cog` class and a module-level `setup(bot)` that calls `bot.add_cog(...)`.

**Persistent Discord View:**
- Purpose: Keep button/select interactions working across bot restarts through stable `custom_id` values and startup registration.
- Examples: `src/features/applications/view/ApplicationPanel.py`, `src/features/applications/view/ApplicationReviewView.py`, `src/features/events/view/EventRegistrationView.py`, `src/features/tickets/view/TicketPanel.py`, `src/features/temp_voice_channels/views/TempVoiceControlView.py`.
- Pattern: Subclass `discord.ui.View`, set `timeout=None` for persistent views, use deterministic `custom_id`, and register in `main.py` or `src/utils/register_persistent_*_views.py`.

**Feature Service:**
- Purpose: Keep workflow logic reusable between Cogs, views, and scheduled jobs.
- Examples: `src/features/applications/service.py`, `src/features/applications/admin_service.py`, `src/features/events/service.py`, `src/features/events/admin_service.py`, `src/features/tickets/create_ticket.py`.
- Pattern: Async functions accept Discord context/entities, call `get_db()`, build embeds, update Discord state, and log outcomes.

**Storage Protocol and Implementation:**
- Purpose: Define durable operations separately from SQLAlchemy internals.
- Examples: `src/storage/base.py`, `src/storage/sqlalchemy_storage.py`, `src/storage/sqlalchemy_applications.py`, `src/storage/sqlalchemy_events.py`.
- Pattern: Add async method signatures to `src/storage/base.py`; implement them in `SQLAlchemyStorage` or a mixin; use dict return payloads for feature services.

**JSON/YAML-Driven Presentation:**
- Purpose: Keep server-specific text and visual styling in config/templates.
- Examples: `config/applications.json`, `config/tickets.json`, `src/languages/messages/welcome_message.json`, `src/utils/embeds.py`.
- Pattern: Load JSON/YAML, normalize Discord limits, call `build_embed_from_data()` or `build_embed_from_template()`.

**Global Bot Access:**
- Purpose: Allow scheduled jobs and utility functions to access the bot when a context cannot be passed directly.
- Examples: `src/utils/bot_instance.py`, `src/features/events/service.py`, `src/utils/send/send_application_panel_message.py`.
- Pattern: Call `set_bot(bot)` once in `main.py`; use `get_bot()` only for background jobs or utilities where passing bot would create awkward dependencies.

## Entry Points

**Process Entry Point:**
- Location: `main.py`
- Triggers: `python main.py`
- Responsibilities: Load config, create the bot, load extensions, start health API, and run the bot with configured token.

**Discord Ready Event:**
- Location: `main.py:32`
- Triggers: Discord gateway ready event.
- Responsibilities: Register persistent views, start scheduler, restore views/state, clean applications, and start Twitch monitoring.

**Dynamic Cog Loading:**
- Location: `src/utils/load_extensions.py:11`
- Triggers: Called during import-time startup from `main.py`.
- Responsibilities: Load `src.events.*`, `src.commands.*`, and `src.commands.admin.*`, respecting `config/command.py` and module config flags.

**Slash Command Cogs:**
- Location: `src/commands`, `src/commands/admin`
- Triggers: Discord slash command invocations.
- Responsibilities: Defer/respond to Discord contexts, enforce admin checks where required, and delegate feature work to services.

**Discord Event Cogs:**
- Location: `src/events`
- Triggers: Discord gateway events.
- Responsibilities: Handle member join and voice state changes.

**Persistent UI Interactions:**
- Location: `src/features/*/view`, `src/views`
- Triggers: Discord button, select, and modal interactions.
- Responsibilities: Validate user interaction, call feature services/storage, and update Discord messages.

**Scheduled Jobs:**
- Location: `src/utils/scheduler.py`, `src/features/events/service.py`, `src/utils/news_sender.py`
- Triggers: APScheduler date triggers and restored job store.
- Responsibilities: Send scheduled panels/news, event reminders, check-in notices, and event start notifications.

**Health HTTP API:**
- Location: `src/api/health.py`
- Triggers: HTTP requests to `/` and `/health`.
- Responsibilities: Return readiness, uptime, guild/user counts, and bot latency.

## Architectural Constraints

- **Threading:** The Discord bot and feature logic run on asyncio. `src/api/health.py` starts Flask/Waitress in a daemon thread. APScheduler uses `AsyncIOScheduler` in `src/utils/scheduler.py`. Twitch monitoring uses `asyncio.create_task()` in `src/features/twitch/twitch_monitor.py`.
- **Global state:** Global runtime state exists in `main.py` (`bot`), `src/utils/bot_instance.py` (`_bot`), `src/utils/database.py` (`_manager`), `src/features/twitch/twitch_monitor.py` (`_twitch_monitor`), `src/languages/localize.py` (`LOCALES`), and `src/features/applications/view/ApplicationDMFlow.py` (`_ACTIVE_SESSIONS`).
- **Circular imports:** Some imports are intentionally deferred inside functions to avoid import-time cycles, such as `ApplicationReviewView` inside `src/features/applications/service.py`, event view imports inside `src/features/events/service.py`, and `TempVoiceControlView` inside `src/features/temp_voice_channels/create_temp_channel.py`.
- **Config dependency:** Many modules import `config.config.config` at import time. New code should avoid reading `.env` directly except through helpers such as `src/utils/db_config.py`.
- **Discord limits:** Application review embeds enforce total and field limits in `src/features/applications/service.py`; new fields should preserve that budget logic.
- **Persistent component IDs:** Persistent views require stable `custom_id` values. New persistent buttons/selects should use deterministic IDs and be re-registered at startup.

## Anti-Patterns

### Hardcoded User-Facing Text In Feature Logic

**What happens:** Some feature modules construct English strings inline while the i18n layer exists.
**Why it's wrong:** Normal-user text should stay localizable through `src/languages/i18n/*.json`, and server-specific visual content should stay in config/templates.
**Do this instead:** Use `from src.languages.localize import _` and add keys to `src/languages/i18n/en.json`, `src/languages/i18n/ru.json`, and `src/languages/i18n/lt.json`; for embed templates, use `src/utils/embeds.py` with JSON config such as `config/applications.json`.

### Direct Storage Implementation Coupling

**What happens:** Feature code can technically import SQLAlchemy storage classes directly.
**Why it's wrong:** The repository uses `src/utils/database.py` as the storage access boundary and `src/storage/base.py` as the contract.
**Do this instead:** Call `db = await get_db()` from `src/utils/database.py`; add new async storage contract methods to `src/storage/base.py` and implement them in `src/storage/sqlalchemy_storage.py` or the relevant mixin.

### Modal-Only Application Workflows

**What happens:** Discord modals cap answer length and do not match the current application flow.
**Why it's wrong:** Applications use a DM wizard with text, textarea, dropdown/select, and button question types; the modal-only path loses required behavior.
**Do this instead:** Extend `src/features/applications/view/ApplicationDMFlow.py` and `config/applications.json`; keep `ApplicationModal.py` as legacy/non-primary code unless explicitly required.

### Startup Registration Without Durable Lookup

**What happens:** Adding a persistent view without a startup registration path makes old messages stop working after restarts.
**Why it's wrong:** Discord persistent components need bot-side registration every process start.
**Do this instead:** Register static views in `main.py` and dynamic views in a `src/utils/register_persistent_*_views.py` utility that reads durable IDs from storage.

## Error Handling

**Strategy:** Catch Discord/API/storage failures at feature boundaries, log with `get_cool_logger()`, return safe user-visible embeds/messages where practical, and keep the bot running.

**Patterns:**
- Startup background tasks catch and log restoration/Twitch failures in `main.py`.
- Feature services catch Discord permission/API errors around role updates, DMs, fetches, channel creation, and message edits.
- Storage methods catch exceptions, log, and return `None`, `False`, `0`, or `[]` depending on contract.
- Admin commands defer ephemerally, validate admin access through `src/utils/auth.py`, and send short ephemeral confirmations.
- Scheduled/background jobs use `get_bot()` and return early if bot/state is unavailable.

## Cross-Cutting Concerns

**Logging:** Use `src/utils/logger.py:get_cool_logger()` per module. Admin-only logs and operational diagnostics are English.

**Validation:** Config and form validation is feature-local: applications normalize questions in `src/features/applications/config.py`, events validate schedules/languages/player limits in `src/features/events/admin_service.py`, and schedule parsing lives in `src/utils/schedule_utils.py`.

**Authentication:** Admin checks use configured admin IDs through `src/utils/auth.py`; application review additionally supports a configured reviewer role in `src/features/applications/view/ApplicationReviewView.py`.

**Localization:** Use `src/languages/localize.py:_()` for normal user-visible strings, backed by `src/languages/i18n/en.json`, `src/languages/i18n/ru.json`, and `src/languages/i18n/lt.json`.

**Embeds:** Prefer `src/utils/embeds.py:build_embed_from_data()`, `build_embed_from_template()`, and `get_embed_icon()` for JSON-driven and standard bot embeds.

---

*Architecture analysis: 2026-05-10*
