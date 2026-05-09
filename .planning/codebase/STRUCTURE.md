# Codebase Structure

**Analysis Date:** 2026-05-10

## Directory Layout

```text
BebraLand-Discord-Bot-2/
├── main.py                    # Bot process entry point and startup wiring
├── pyproject.toml             # Python project metadata, dependencies, Ruff config
├── uv.lock                    # Locked uv dependency graph
├── AGENTS.md                  # Repository guidance for future agents
├── config/                    # Runtime YAML config, examples, command flags, JSON feature templates
├── data/                      # Runtime data directory for SQLite and scheduled files
├── examples/                  # Example Pycord app command/view snippets
├── src/                       # Bot source code
│   ├── api/                   # Optional HTTP health API
│   ├── commands/              # Pycord slash command Cogs
│   │   └── admin/             # Admin slash command group and subcommands
│   ├── events/                # Pycord gateway event Cogs
│   ├── features/              # Feature-specific services, views, and workflows
│   │   ├── applications/      # Application panels, DM wizard, reviews, role updates
│   │   ├── events/            # Event panels, registrations, reminders, check-in
│   │   ├── temp_voice_channels/ # Temporary voice channel lifecycle and controls
│   │   ├── tickets/           # Ticket panels, modals, channel lifecycle
│   │   └── twitch/            # Twitch panel and stream monitor
│   ├── languages/             # i18n locale files, constants, message templates
│   ├── storage/               # Storage protocols, SQLAlchemy models, SQLAlchemy implementation
│   ├── utils/                 # Shared infrastructure and workflow helpers
│   │   └── send/              # Reusable "send panel/message" helpers
│   └── views/                 # Shared/global views and modals not owned by one feature package
├── .planning/codebase/        # Generated codebase maps for GSD commands
└── temp/                      # Scratch/legacy/test material, not the primary source tree
```

## Directory Purposes

**`config`:**
- Purpose: Runtime configuration and feature-owned JSON templates.
- Contains: YAML config loader, example config, command enable flags, application/ticket templates.
- Key files: `config/config.py`, `config/config.example.yaml`, `config/config.yaml`, `config/command.py`, `config/applications.json`, `config/tickets.json`.

**`src/api`:**
- Purpose: Optional monitoring HTTP endpoint.
- Contains: Flask/Waitress health server running in a background thread.
- Key files: `src/api/health.py`.

**`src/commands`:**
- Purpose: User-facing and admin slash command Cogs loaded by `src/utils/load_extensions.py`.
- Contains: One module per command area, plus `src/commands/admin` for multicog admin subcommands.
- Key files: `src/commands/set_lang.py`, `src/commands/rules.py`, `src/commands/toggle_invites.py`, `src/commands/invite_user_context.py`, `src/commands/admin/admin_group.py`.

**`src/commands/admin`:**
- Purpose: Admin command group and feature administration commands.
- Contains: Multicog subcommands decorated with `@subcommand("admin")`.
- Key files: `src/commands/admin/admin_applications.py`, `src/commands/admin/admin_events.py`, `src/commands/admin/admin_send_news.py`, `src/commands/admin/admin_send_ticket_panel.py`, `src/commands/admin/admin_send_twitch_panel.py`.

**`src/events`:**
- Purpose: Discord gateway event Cogs.
- Contains: Member join handling and voice state handling.
- Key files: `src/events/on_member_join.py`, `src/events/on_voice_state_update.py`.

**`src/features`:**
- Purpose: Feature modules that hold business logic, Discord views, and service workflows.
- Contains: Feature subpackages for applications, events, temp voice, tickets, and Twitch.
- Key files: `src/features/applications/service.py`, `src/features/events/service.py`, `src/features/tickets/create_ticket.py`, `src/features/temp_voice_channels/create_temp_channel.py`, `src/features/twitch/twitch_monitor.py`.

**`src/features/applications`:**
- Purpose: Application panel, DM wizard, reviewer workflow, role changes, and application cleanup.
- Contains: `service.py` for workflow logic, `admin_service.py` for admin command handlers, `config.py` for JSON/config normalization, `view/` for Discord UI.
- Key files: `src/features/applications/service.py`, `src/features/applications/admin_service.py`, `src/features/applications/config.py`, `src/features/applications/view/ApplicationPanel.py`, `src/features/applications/view/ApplicationDMFlow.py`, `src/features/applications/view/ApplicationReviewView.py`.

**`src/features/events`:**
- Purpose: Event creation, registration, panel refresh, reminders, check-in, cancellation, and notifications.
- Contains: Admin services, user-facing event services, and event registration view.
- Key files: `src/features/events/admin_service.py`, `src/features/events/service.py`, `src/features/events/view/EventRegistrationView.py`.

**`src/features/temp_voice_channels`:**
- Purpose: Temporary voice channel creation, deletion, restoration, ownership, invites, permissions, and settings.
- Contains: Workflow functions plus nested `views/`, `views/selectors/`, and `views/settings/`.
- Key files: `src/features/temp_voice_channels/create_temp_channel.py`, `src/features/temp_voice_channels/delete_temp_channel.py`, `src/features/temp_voice_channels/restore_temp_channels.py`, `src/features/temp_voice_channels/views/TempVoiceControlView.py`, `src/features/temp_voice_channels/views/settings/TempVoiceSettingsView.py`.

**`src/features/tickets`:**
- Purpose: Ticket panel, ticket creation, close flow, transcripts, and DM notifications.
- Contains: Ticket lifecycle functions and `view/` UI modules.
- Key files: `src/features/tickets/create_ticket.py`, `src/features/tickets/create_transcript.py`, `src/features/tickets/view/TicketPanel.py`, `src/features/tickets/view/TicketFormModal.py`, `src/features/tickets/view/CloseTicketView.py`.

**`src/features/twitch`:**
- Purpose: Twitch live status panel and background stream monitor.
- Contains: Monitor service and persistent panel view.
- Key files: `src/features/twitch/twitch_monitor.py`, `src/features/twitch/view/TwitchPanel.py`.

**`src/languages`:**
- Purpose: Localization, language constants, and JSON message templates.
- Contains: i18n locale JSON files in `src/languages/i18n`, legacy/template message JSON in `src/languages/messages`, localization helper.
- Key files: `src/languages/localize.py`, `src/languages/lang_constants.py`, `src/languages/i18n/en.json`, `src/languages/i18n/ru.json`, `src/languages/i18n/lt.json`, `src/languages/messages/welcome_message.json`, `src/languages/messages/rules.json`.

**`src/storage`:**
- Purpose: Durable data contracts and SQLAlchemy persistence.
- Contains: Protocol definitions, ORM models, factory, unified storage implementation, application/event mixins.
- Key files: `src/storage/base.py`, `src/storage/models.py`, `src/storage/factory.py`, `src/storage/sqlalchemy_storage.py`, `src/storage/sqlalchemy_applications.py`, `src/storage/sqlalchemy_events.py`.

**`src/utils`:**
- Purpose: Shared infrastructure, helpers, and cross-feature workflows.
- Contains: Database manager, DB URL helpers, scheduler singleton, logger, auth, embeds, persistent view registration, Twitch API client, news sender, welcome message helper, schedule parsing, send helpers.
- Key files: `src/utils/database.py`, `src/utils/db_config.py`, `src/utils/scheduler.py`, `src/utils/load_extensions.py`, `src/utils/embeds.py`, `src/utils/auth.py`, `src/utils/news_sender.py`, `src/utils/twitch_api.py`.

**`src/utils/send`:**
- Purpose: Send reusable panels/dropdowns to channels by ID.
- Contains: Small async functions called by admin services and scheduled jobs.
- Key files: `src/utils/send/send_application_panel_message.py`, `src/utils/send/send_ticket_panel_message.py`, `src/utils/send/send_twitch_panel.py`, `src/utils/send/send_language_dropdown.py`, `src/utils/send/send_rules_panel.py`.

**`src/views`:**
- Purpose: Shared or legacy global UI components not nested under a specific feature package.
- Contains: Language selector, rules panel, news modal/wizard.
- Key files: `src/views/language_selector.py`, `src/views/rules_panel.py`, `src/views/news_modal.py`, `src/views/news_wizard.py`.

**`data`:**
- Purpose: Runtime persistence location.
- Contains: SQLite database by default and scheduled file payloads.
- Key files: `data/data.db` when using the default `sqlite+aiosqlite:///data/data.db`, `data/scheduled_files`.

**`examples`:**
- Purpose: Reference examples for Pycord commands and views.
- Contains: Example app command and view files.
- Key files: `examples/app_commands`, `examples/views`.

**`temp`:**
- Purpose: Scratch, legacy, or experimental material.
- Contains: Old/test files and local scratch directories.
- Key files: Not a primary code location for new production code.

## Key File Locations

**Entry Points:**
- `main.py`: Process entry point, bot construction, `on_ready`, extension loading, health API startup, bot run call.
- `src/utils/load_extensions.py`: Dynamic loader for event and command Cogs.
- `src/commands/*`: Slash command entry points.
- `src/events/*`: Discord gateway event entry points.
- `src/features/*/view/*.py`: Button/select/modal interaction entry points.

**Configuration:**
- `config/config.py`: YAML loader and dot-access config object.
- `config/config.yaml`: Runtime config for local deployment. Do not expose secrets.
- `config/config.example.yaml`: Example/default config shape.
- `config/command.py`: Command enable/disable flags.
- `config/applications.json`: Application panel, button labels, question config, and embed JSON.
- `config/tickets.json`: Ticket panel/categories/form template config.
- `pyproject.toml`: Project metadata, dependencies, Python version, Ruff lint selection.

**Core Logic:**
- `src/features/applications/service.py`: Application submission/review/roles/cleanup.
- `src/features/applications/view/ApplicationDMFlow.py`: DM application wizard session state and question flow.
- `src/features/events/service.py`: Event embed/panel/registration refresh and scheduled notifications.
- `src/features/events/admin_service.py`: Event admin command workflows.
- `src/features/tickets/create_ticket.py`: Ticket channel and storage creation.
- `src/features/temp_voice_channels/create_temp_channel.py`: Temp channel creation and control panel.
- `src/features/twitch/twitch_monitor.py`: Twitch polling and Discord notification workflow.
- `src/utils/news_sender.py`: News preview, sending, scheduled payload, and broadcast summary logic.

**Storage:**
- `src/storage/base.py`: Async protocol contracts.
- `src/storage/models.py`: SQLAlchemy table models.
- `src/storage/sqlalchemy_storage.py`: Main async SQLAlchemy storage implementation.
- `src/storage/sqlalchemy_applications.py`: Application-specific SQLAlchemy mixin.
- `src/storage/sqlalchemy_events.py`: Event-specific SQLAlchemy mixin.
- `src/utils/database.py`: Lazy global manager and `get_db()` facade.
- `src/utils/db_config.py`: Async/sync database URL helpers and default SQLite URL.

**Discord UI:**
- `src/features/applications/view/ApplicationPanel.py`: Persistent application panel.
- `src/features/applications/view/ApplicationReviewView.py`: Persistent reviewer buttons.
- `src/features/events/view/EventRegistrationView.py`: Event registration/check-in view.
- `src/features/tickets/view/TicketPanel.py`: Persistent ticket panel.
- `src/features/temp_voice_channels/views/TempVoiceControlView.py`: Temp voice control panel.
- `src/views/language_selector.py`: Language selection dropdown.
- `src/views/news_wizard.py`: News composition/scheduling wizard.

**Localization and Presentation:**
- `src/languages/localize.py`: i18n setup and `_()` translation lookup.
- `src/languages/i18n/en.json`: English translation keys.
- `src/languages/i18n/ru.json`: Russian translation keys.
- `src/languages/i18n/lt.json`: Lithuanian translation keys.
- `src/languages/messages/welcome_message.json`: Welcome message embed template.
- `src/languages/messages/rules.json`: Rules embed template.
- `src/utils/embeds.py`: JSON-to-Discord-embed helpers and footer icon lookup.

**Background Work:**
- `src/utils/scheduler.py`: APScheduler singleton with SQLAlchemy job store.
- `src/features/events/service.py`: Event reminder/check-in/start scheduled job functions.
- `src/utils/news_sender.py`: Scheduled news task.
- `src/features/twitch/twitch_monitor.py`: Twitch background polling loop.

**Testing:**
- No primary `tests/` directory is present in the scanned repo.
- Verification is command-based through compile and Ruff checks documented in `AGENTS.md`.

## Naming Conventions

**Files:**
- Command modules use lowercase snake_case: `src/commands/set_lang.py`, `src/commands/toggle_invites.py`.
- Admin command modules use `admin_*` snake_case: `src/commands/admin/admin_events.py`, `src/commands/admin/admin_applications.py`.
- Event modules use `on_*` snake_case: `src/events/on_member_join.py`, `src/events/on_voice_state_update.py`.
- Service modules use concise snake_case names: `src/features/applications/service.py`, `src/features/events/admin_service.py`.
- Discord view/modal/select modules often use PascalCase class-matching filenames: `ApplicationPanel.py`, `TicketPanel.py`, `TempVoiceControlView.py`, `TransferUserSelect.py`.
- Config/template files use descriptive lowercase JSON/YAML names: `config/applications.json`, `config/tickets.json`, `config/config.example.yaml`.

**Directories:**
- Feature directories use lowercase snake_case: `src/features/temp_voice_channels`.
- View subdirectories are named `view` for applications/events/tickets/twitch and `views` for temp voice channels; follow the existing directory name inside the feature being changed.
- Selector and settings controls live under nested directories when a feature already has them: `src/features/temp_voice_channels/views/selectors`, `src/features/temp_voice_channels/views/settings`.

**Classes and Functions:**
- Cog, view, modal, select, model, and service classes use PascalCase: `ApplicationsAdmin`, `ApplicationPanel`, `ApplicationSession`, `SQLAlchemyStorage`, `TwitchMonitor`.
- Async workflow functions use snake_case and should be awaited: `create_event`, `send_event_panel`, `create_ticket`, `create_temp_channel`, `get_db`.
- Module globals use uppercase for constants and leading underscore for private runtime state: `APPLICATION_ANSWER_MAX`, `_ACTIVE_SESSIONS`, `_manager`, `_twitch_monitor`.

## Where to Add New Code

**New Slash Command:**
- Primary code: Add a Cog module under `src/commands` for normal commands or `src/commands/admin` for admin commands.
- Registration: Include a module-level `setup(bot)` that calls `bot.add_cog(...)`.
- Admin commands: Use `@subcommand("admin")` and call `await require_admin(ctx)` from `src/utils/auth.py`.
- Feature logic: Put non-trivial workflow logic in the relevant `src/features/<feature>/service.py` or `admin_service.py`, then call it from the Cog.

**New Discord Event Handler:**
- Primary code: Add a Cog module under `src/events`.
- Registration: Include `setup(bot)`; `src/utils/load_extensions.py` loads non-`__*` `.py` files automatically.
- Feature logic: Delegate to `src/features/<feature>` modules when the handler grows beyond event routing.

**New Feature:**
- Primary code: Create `src/features/<feature_name>/`.
- Suggested layout: `service.py` for user-facing workflow logic, `admin_service.py` for admin command workflows, `view/` for Pycord UI classes, and optional `config.py` for JSON/YAML normalization.
- Commands: Add command Cogs in `src/commands` or `src/commands/admin`.
- Storage: Add protocol methods to `src/storage/base.py`, models to `src/storage/models.py`, and SQLAlchemy implementation in `src/storage/sqlalchemy_storage.py` or a feature mixin.

**New Persistent View:**
- Implementation: Put the class in the owning feature's `view`/`views` directory.
- Startup registration: Register static views in `main.py` or create/update a `src/utils/register_persistent_*_views.py` helper for dynamic IDs.
- IDs: Use stable deterministic `custom_id` values.

**New Application Question Type:**
- Config parsing: Update `src/features/applications/config.py`.
- DM flow behavior: Update `src/features/applications/view/ApplicationDMFlow.py`.
- Panel/template data: Update `config/applications.json` as needed.
- User strings: Add translations to all files under `src/languages/i18n`.

**New Event Behavior:**
- Admin workflow: Add or extend functions in `src/features/events/admin_service.py`.
- User-facing panel/notification behavior: Add or extend functions in `src/features/events/service.py`.
- Discord controls: Update `src/features/events/view/EventRegistrationView.py`.
- Scheduler jobs: Use the singleton from `src/utils/scheduler.py` and stable job IDs.

**New Ticket Behavior:**
- Ticket lifecycle: Add logic under `src/features/tickets`.
- UI controls: Add view/modal classes under `src/features/tickets/view`.
- Template/category config: Use `config/tickets.json`.
- User strings: Use `src/languages/localize.py:_()` and update locale JSON.

**New Temp Voice Control:**
- Channel workflow: Add functions under `src/features/temp_voice_channels`.
- Buttons/main control panel: Update `src/features/temp_voice_channels/views/TempVoiceControlView.py`.
- Selectors: Add selector classes under `src/features/temp_voice_channels/views/selectors`.
- Settings controls: Add modal/select/view classes under `src/features/temp_voice_channels/views/settings`.

**New Storage Method:**
- Contract: Add async method signature to the relevant protocol in `src/storage/base.py`.
- Model: Add SQLAlchemy table/columns in `src/storage/models.py` if durable schema changes are required.
- Implementation: Add method to `src/storage/sqlalchemy_storage.py`, `src/storage/sqlalchemy_applications.py`, or `src/storage/sqlalchemy_events.py`.
- Access: Use `db = await get_db()` from `src/utils/database.py`.

**New Utility:**
- Shared helpers: Add to `src/utils` when used by multiple features.
- Send helpers: Add to `src/utils/send` when the utility only sends a prebuilt panel/message by channel ID.
- Feature-specific helpers: Keep inside `src/features/<feature>` unless multiple features need them.

**New Localization:**
- Normal user-visible strings: Add keys to `src/languages/i18n/en.json`, `src/languages/i18n/ru.json`, and `src/languages/i18n/lt.json`.
- Lookup: Use `from src.languages.localize import _`.
- Server-specific template text: Prefer `config/*.json` or `src/languages/messages/*.json` plus `src/utils/embeds.py`.

## Special Directories

**`.planning/codebase`:**
- Purpose: Generated architecture/quality/tech maps consumed by GSD planning and execution commands.
- Generated: Yes.
- Committed: Project-dependent; do not treat as runtime source.

**`.codex/environments`:**
- Purpose: Local Codex environment metadata.
- Generated: Yes.
- Committed: Project-dependent.

**`.github`:**
- Purpose: GitHub repository automation such as workflows.
- Generated: No.
- Committed: Yes.

**`.idea`, `.vscode`, `.trae`:**
- Purpose: Local/editor/tooling metadata.
- Generated: Yes.
- Committed: Project-dependent.

**`data`:**
- Purpose: Runtime data such as SQLite database and scheduled files.
- Generated: Yes.
- Committed: Directory may exist, but runtime database contents should be treated as generated/local state.

**`temp`:**
- Purpose: Scratch, old, and test material outside the primary runtime architecture.
- Generated: Mixed.
- Committed: Project-dependent; avoid adding new production code here.

**`__pycache__`, `.mypy_cache`, `.ruff_cache`, `.uv-cache`, `.venv`:**
- Purpose: Python/tool caches and virtual environment.
- Generated: Yes.
- Committed: No.

---

*Structure analysis: 2026-05-10*
