# Notion Sync — NotebookLM Tracker

5-database Notion Tracker mirrors the NotebookLM workspace. Load when the task involves Notion IDs, sync scripts, schema questions, or the automatic hook.

## Architecture

The Notion workspace holds the **NotebookLM Tracker** — 5 databases under the 📚 NotebookLM parent page at `data-privacy-office` workspace.

| DB | Short ID | Data Source ID env var | DB ID env var | Role |
|----|----------|----------------------|---------------|------|
| 📓 Notebooks | `eca18c6e` | `NOTION_NOTEBOOKS_DS_ID` | `NOTION_NOTEBOOKS_DB_ID` | Notebook inventory (central hub) |
| 📄 Sources | `e632a9e6` | `NOTION_SOURCES_DS_ID` | `NOTION_SOURCES_DB_ID` | Every source in every notebook |
| 🎙️ Assets | `daa7359a` | `NOTION_ASSETS_DS_ID` | `NOTION_ASSETS_DB_ID` | Audio/video/slides/infographics |
| 🔬 Research Tasks | `df22a357` | `NOTION_RESEARCH_DS_ID` | `NOTION_RESEARCH_DB_ID` | Research intake (Notion-first) |
| 🔗 NLM Connector | `334edd57` | `NOTION_CONNECTOR_DS_ID` | `NOTION_CONNECTOR_DB_ID` | Automation hub |

All IDs + integration token live in `D:\NotebookLM\.env` (gitignored). Mirror the token in n8n credentials at https://n8n.dpo.ae/ for webhook flows.

**Integration:** `NotebookLM Claude Code + n8n Integration` — scoped access, not workspace-wide.

### DB_ID vs DS_ID — critical

Notion 2025-09-03 API split databases from data sources:
- **`pages.create(parent={database_id: DB_ID})`** — use the **DB_ID**
- **`notion.data_sources.query(data_source_id=DS_ID)`** — use the **DS_ID**

Confusing them gives a 404 "Could not find database". Both are stored in `.env`; always pick the right one.

**Notion client:** `notion-client==3.0` required (v2.x has no `data_sources` attribute). `NOTION_VERSION = "2026-03-11"` across all scripts (native markdown, `in_trash`, position object).

## Command Pattern (SOP framework)

Each row in any DB has three standard properties:
- **`Commands`** (multi-select hashtags, e.g., `#link_relations`) — what an AI agent should do
- **`Automation Trigger`** (date) — the fire signal for Notion automations / n8n webhooks
- **`Log`** (text) — append execution results, format: `[DD/MM/YYYY HH:mm] #command — summary`

The **NLM Connector** DB has mirror multi-selects (`Notebooks Commands`, `Sources Commands`, etc.) that act as defaults for newly created rows in each content DB.

SOPs live in the shared SOPs database — `#database_standards`, `#link_relations`, `#sync_connector_commands` — and fire when a row's `Commands` matches.

## Automatic Sync (PostToolUse Hook)

**Toggle:** `NOTION_SYNC=1` in `D:\NotebookLM\.env` (default: ON).

The hook at `D:\NotebookLM\.claude\hooks\post_tool_use.py` fires after:
- `mcp__notebooklm-mcp__download_artifact` → runs `python scripts/sync_notion_assets.py --sync`
- `mcp__notebooklm-mcp__source_add` → runs `python scripts/sync_notion_sources.py push --notebook <id>`

Defined in `D:\NotebookLM\.claude\settings.json`:

```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "mcp__notebooklm-mcp__download_artifact|mcp__NotebookLM_MCP_Server__download_artifact",
        "hooks": [{"type": "command", "command": "python D:/NotebookLM/.claude/hooks/post_tool_use.py", "timeout": 180}]
      },
      {
        "matcher": "mcp__notebooklm-mcp__source_add|mcp__NotebookLM_MCP_Server__source_add",
        "hooks": [{"type": "command", "command": "python D:/NotebookLM/.claude/hooks/post_tool_use.py", "timeout": 180}]
      }
    ]
  }
}
```

To pause without removing the hook: set `NOTION_SYNC=0` in `.env`. The hook script reads `.env` on every invocation and exits early if disabled.

**Hook does NOT fire for:**
- CLI `nlm download <type>` (Bash commands)
- CLI `nlm source add` (Bash commands)
- Manual `python scripts/sync_notion_*.py` calls

For those paths, run the sync manually afterward.

## Sync Scripts

### Notebook inventory — `sync_notion_notebooks.py`

```bash
# Push CLI → Notion (creates missing, updates mutable fields)
python scripts/sync_notion_notebooks.py --push

# Pull Notion → notebooks.md (regenerates local mirror)
python scripts/sync_notion_notebooks.py --pull

# Both
python scripts/sync_notion_notebooks.py --sync
```

**Push rules:**
- Creates rows for notebooks missing from Notion
- Updates `Source Count`, `Last Modified`, `Status` on existing
- **Never touches** `Category`, `Tags`, `Notes` (Notion owns these)
- Missing from CLI output → `Status = Archived` (not deleted)
- Backfills `Slug` if the row has empty slug (auto-derived from Name)

**Status derivation:**
| Source Count | Status |
|-------------:|--------|
| 0 | Empty |
| 1–19 | Stub |
| 20–269 | Active |
| ≥270 | Near Capacity |
| (missing from CLI) | Archived |

**Bulk create:** first run creates 200+ notebooks at ~3 req/sec (~2–3 min).

### Asset sync — `sync_notion_assets.py`

**Lifecycle:** `Generating → Ready → Downloaded → Uploaded → Failed`

Subcommands:
```bash
# Create "Generating" row (inline after studio_create)
python scripts/sync_notion_assets.py create \
    --notebook-short-id eca18c6e --asset-type Audio

# Attach file after download (transitions Downloaded → Uploaded)
python scripts/sync_notion_assets.py attach \
    --page-id <notion-page-id> \
    --file-path "D:/NotebookLM/audio/{slug}/overview.mp3"

# Walk local folders + reconcile rows
python scripts/sync_notion_assets.py scan

# Transition stuck "Generating" rows whose file now exists
python scripts/sync_notion_assets.py catchup

# Both
python scripts/sync_notion_assets.py --sync

# Discover artifacts in NotebookLM + download + sync (see asset-pipeline.md)
python scripts/sync_notion_assets.py pull-existing [--notebook <slug> | --active-only | --category X | --tag Y]

# One-shot generate + upload (see asset-pipeline.md)
python scripts/sync_notion_assets.py generate --notebook <slug> --type audio --focus "..."

# Batch generate (dry-run default)
python scripts/sync_notion_assets.py generate-batch --type audio --active-only --focus "..." --confirm
```

**Pagination:** `_load_notebooks()` paginates correctly (while-True + has_more/next_cursor), returns all 200+. **Never** use ad-hoc `notion-query-database-view` MCP calls for bulk sweeps — those cap at 100 results per page.

**Canonical path helper:** `_stored_path(Path) -> str` returns ROOT-relative path with forward slashes. All reads/writes use it. Don't hand-write `str(path)`.

### Source sync — `sync_notion_sources.py`

Direction: NotebookLM CLI → Notion Sources DB (one-way).

```bash
# Push sources for one notebook (fast)
python scripts/sync_notion_sources.py push --notebook <short-id>

# Touch — mandatory after any source op (see source-ops.md)
python scripts/sync_notion_sources.py touch --notebook <short-id>

# Push across all notebooks
python scripts/sync_notion_sources.py push

# Scoping flags (apply to push, dedupe, sync)
--notebook <slug-or-short-id>     # one notebook
--active-only                      # Status=Active or Near Capacity only
--source-limit-min N               # only notebooks with ≥N sources (default 1)

# Dedupe duplicates by normalized URL
python scripts/sync_notion_sources.py dedupe --notebook <short-id>           # dry-run
python scripts/sync_notion_sources.py dedupe --notebook <short-id> --confirm-dedupe  # destructive

# Enrich (AI Summary + Keywords + Char Count + page body)
python scripts/sync_notion_sources.py enrich --notebook <short-id>

# sync = dedupe (dry) + push
python scripts/sync_notion_sources.py sync
```

Auth auto-recovery is built in — on `Authentication expired` detection, it runs `nlm login` once and retries.

### Research sync — `sync_notion_research.py`

Bidirectional between 🔬 Research Tasks DB and `research-queue.md`.

```bash
python scripts/sync_notion_research.py --pull    # Notion → local
python scripts/sync_notion_research.py --push    # local → Notion
python scripts/sync_notion_research.py --sync    # both
```

Status flow (see [research-workflow.md](research-workflow.md) for full lifecycle):
```
Notion: Requested → Queued — Local → Running → Importing → Done
                                        ↓
                                     Failed / Cancelled
```

Matching: by `Task ID` when present, otherwise by `Query` text + `Notebook` name.

## Notion File Upload (Cloudflare Bypass)

The upload helper in `scripts/notion_files.py` handles Notion's file upload API:

- **≤ 20 MiB** → single-part (POST `/v1/file_uploads` → upload multipart form → auto-completed)
- **> 20 MiB** → multi-part (POST create with `mode=multi_part` + `number_of_parts` → send 10 MiB chunks with `part_number` → POST `/v1/file_uploads/{id}/complete`)

**Why `curl_cffi`:** the `/v1/file_uploads/{id}/send` endpoint is Cloudflare-JA3-protected. Standard `requests` gets 403. `curl_cffi` with `impersonate="chrome"` passes the JA3 fingerprint check.

Alternative: `import_external_url()` — Notion fetches the file from a public URL server-side. Zero local bandwidth, works for `lh3.googleusercontent.com/notebooklm/...` URLs (audio, infographic) but not for `contribution.usercontent.google.com/...` (slides — auth-required).

Upload-then-attach pattern:
```python
{"File": {"files": [{"type": "file_upload", "file_upload": {"id": "<uuid>"}, "name": "..."}]}}
```
