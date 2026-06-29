# BebraLand Discord Bot

BebraLand Discord bot built with Pycord, SQLAlchemy storage, YAML runtime config, JSON message templates, and localized user-facing text.

## Features

- Application system with DM question flow, staff review buttons, role updates, and optional cleanup of old rejected/revoked applications.
- Ticket system with configurable categories, forms, staff controls, logs, and transcripts.
- Temporary voice channels with owner controls, invites, kicks, permissions, limits, bitrate, and region settings.
- Twitch live monitoring with live-role/ping support.
- Dynamic Discord presence from Twitch, Minecraft server status, scheduled events, and fallback messages.
- Discord scheduled event registration/check-in helpers.
- Rules, language selector, welcome, radio, and news/admin message tools.
- Health API endpoint for uptime monitoring.
- Admin diagnostics for config, permissions, role hierarchy, JSON templates, database access, and disabled-module mismatches.

## Requirements

- Python 3.11+
- `uv`
- A Discord bot token
- SQLite by default, or a SQLAlchemy-compatible database URL

## Setup

1. Clone the repository.
2. Copy `.env.example` to `.env` and set `DISCORD_BOT_TOKEN`.
3. Copy `config/config.example.yaml` to `config/config.yaml`.
4. Replace every `CHANGE_ME` value in `config/config.yaml` with IDs from your Discord server.
5. Edit `config/applications.json` and `config/tickets.json` for your server flow.
6. Run the bot:

```powershell
uv run python main.py
```

## Configuration

Runtime config lives in `config/config.yaml`. The example file documents the expected shape:

- `bot`: token, language, timezone, prefix, admins.
- `embeds`: shared colors and footer icon.
- `messages`: message cleanup limits.
- `health`: local health API toggle and port.
- `modules.welcome`: welcome behavior.
- `modules.news`: localized news channels.
- `modules.tickets`: ticket category, log channel, support role, and limits.
- `modules.applications`: review channel, reviewer role, verified/pending/unverified roles, and retention.
- `modules.twitch`: streamers, live role, ping role, channel, and check interval.
- `modules.events`: Discord scheduled event integration.
- `modules.status`: dynamic bot presence sources.
- `modules.temp_voice`: lobby/category, permissions, defaults, and owner controls.

Do not commit real tokens, production `config/config.yaml`, or runtime databases.

## JSON Templates

Application and ticket forms are configured through JSON:

- `config/applications.json`
- `config/tickets.json`

Message/embed templates live in:

- `src/languages/messages/language.json`
- `src/languages/messages/rules.json`
- `src/languages/messages/twitch.json`
- `src/languages/messages/welcome.json`

Most message templates support Discord/Discohook-style `embeds` data.

## Localization

User-facing text should use translation keys from:

- `src/languages/i18n/en.json`
- `src/languages/i18n/ru.json`
- `src/languages/i18n/lt.json`

When adding a new normal-user message, add translations for all supported languages when practical.

## Useful Admin Commands

- `/admin diagnostics`: checks database access, configured channels/roles, guild permissions, per-channel permissions, role hierarchy, JSON templates, and disabled modules with configured IDs.
- `/admin send_ticket_panel`: posts the ticket panel.
- `/admin applications`: manages application panel/review actions.
- `/admin events`: manages event tools.
- `/admin send_rules`: posts the rules panel.
- `/admin language_selector`: posts the language selector.
- `/admin send_news`: sends localized news.
- `/admin send_twitch_panel`: posts the Twitch panel.

Exact command availability depends on loaded cogs and bot permissions.

## Verification

Compile and lint the project with:

```powershell
$env:UV_CACHE_DIR='.uv-cache'; uv run python -m compileall main.py src
$env:UV_CACHE_DIR='.uv-cache'; uv run ruff check main.py src
```

For diagnostics-only changes:

```powershell
$env:UV_CACHE_DIR='.uv-cache'; uv run python -m compileall src\commands\admin\admin_diagnostics.py
$env:UV_CACHE_DIR='.uv-cache'; uv run ruff check src\commands\admin\admin_diagnostics.py
```

## Troubleshooting

Run `/admin diagnostics` after changing server IDs, roles, permissions, or JSON templates. The command highlights the common problems that stop the bot from working correctly:

- Missing or invalid channel/role IDs.
- Bot missing guild-level permissions.
- Bot missing permissions in configured channels.
- Bot role placed below roles it needs to assign.
- Broken JSON or unusable embed template files.
- Disabled modules that still have configured IDs.
- Database connection failures.
