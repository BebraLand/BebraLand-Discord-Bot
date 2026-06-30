# AGENTS.md

Guidance for Codex and future agents working in this repository.

## Project

BebraLand Discord bot built with Pycord, SQLAlchemy storage, YAML runtime config, and JSON message/form templates.

Primary goals:
- Keep Discord UI clean and embed-first where it makes sense.
- Keep user-facing text localizable through `src/languages/i18n/*.json`.
- Keep server-specific visual style in config/templates, not hardcoded in Python.

## Commands

Use `uv` for checks:

```powershell
$env:UV_CACHE_DIR='.uv-cache'; uv run python -m compileall main.py src
$env:UV_CACHE_DIR='.uv-cache'; uv run ruff check main.py src
```

For narrower changes, compile/lint only touched files.

## Style

- Prefer Discord embeds for bot responses unless plain text is clearly better.
- Use `src.utils.embeds.build_embed_from_data` / `build_embed_from_template` for JSON-driven embeds.
- Do not force global footer, footer icon, or color when a feature is explicitly JSON/template-driven.
- Use `get_embed_icon(ctx)` for standard bot embeds. In DMs, pass the bot/client as context when the footer should show the bot icon, not the user avatar.
- Keep admin/status embeds compact and safe under Discord limits.
- Keep config-owned visual content in JSON/YAML files, not hardcoded into Python.
- Avoid unrelated refactors when fixing feature bugs.

## i18n

All user-facing strings that can appear to normal users should go through:

```python
from src.languages.localize import _
```

Use keys in:
- `src/languages/i18n/en.json`
- `src/languages/i18n/ru.json`
- `src/languages/i18n/lt.json`

Admin-only logs can stay English. New user-visible embeds/buttons/messages should add translations for all three languages when practical.

## Applications

Application panel config lives in `config/applications.json`.

Panel embeds are Discord/Discohook-style JSON:

```json
{
  "embeds": [
    {
      "title": "Apply",
      "description": "Click Apply.",
      "color": 7425077,
      "footer": {
        "text": "BebraLand team",
        "icon_url": "https://example.com/logo.png"
      }
    }
  ],
  "buttonLabel": "Apply"
}
```

Question types:
- `text` waits for a DM message and caps answer at 100 chars.
- `textarea` waits for a DM message and allows longer answers.
- `dropdown`, `select`, `choice` render a select menu from `options`.
- `button`, `buttons` render buttons from `options`.

Optional per-question link button:

```json
{
  "buttonLabel": "Rules",
  "buttonLink": "https://bebraland.auuruum.me/wiki/rules/"
}
```

Applications use a DM wizard, not Discord modals. Do not reintroduce modal-only limits as the main flow.

Application database cleanup:
- Keep `pending` and `accepted`.
- Delete only old `rejected` and `revoked` rows based on `modules.applications.retention_days`.
- `retention_days: 0` disables cleanup.

Admin review embeds must stay under Discord embed total limits. If adding more fields, preserve the total-budget guard in `build_application_review_embed`.

## Config

Runtime config:
- `config/config.yaml`
- example/default shape in `config/config.example.yaml`

Do not commit secrets or real tokens. Keep examples generic.

## Storage

Storage protocol is in `src/storage/base.py`; SQLAlchemy implementation is in `src/storage/sqlalchemy_storage.py`.

When adding storage methods:
- Update the protocol.
- Add implementation in SQLAlchemy storage.
- Keep methods async.
- Prefer status-preserving cleanup over deleting active/important records.

## Verification Notes

Common targeted checks:

```powershell
$env:UV_CACHE_DIR='.uv-cache'; uv run python -m compileall src\features\applications
$env:UV_CACHE_DIR='.uv-cache'; uv run ruff check src\features\applications
```

If `uv` fails with sandbox access errors, request escalation for the same command.

## graphify

This project has a knowledge graph at graphify-out/ with god nodes, community structure, and cross-file relationships.

When the user types `/graphify`, use the installed graphify skill or instructions before doing anything else.

Rules:
- For codebase questions, first run `graphify query "<question>"` when graphify-out/graph.json exists. Use `graphify path "<A>" "<B>"` for relationships and `graphify explain "<concept>"` for focused concepts. These return a scoped subgraph, usually much smaller than GRAPH_REPORT.md or raw grep output.
- Dirty graphify-out/ files are expected after hooks or incremental updates; dirty graph files are not a reason to skip graphify. Only skip graphify if the task is about stale or incorrect graph output, or the user explicitly says not to use it.
- If graphify-out/wiki/index.md exists, use it for broad navigation instead of raw source browsing.
- Read graphify-out/GRAPH_REPORT.md only for broad architecture review or when query/path/explain do not surface enough context.
- After modifying code, run `graphify update .` to keep the graph current (AST-only, no API cost).
