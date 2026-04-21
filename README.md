# notebooklm-workspace

A Claude Code plugin that bundles everything needed to run a NotebookLM-centric workspace: project conventions, Notion Tracker sync, research curation, narrative-first slide decks, and automation hooks.

## What's in the box

| Component | Purpose |
|-----------|---------|
| `skills/notebooklm-workspace` | Core workspace skill — paths, Notion DB IDs, mandatory rules, automation layer. Extends `nlm-skill`. |
| `skills/slide-pipeline` | Narrative-first slide deck pipeline. User-invocable via `/build-deck`. |
| `agents/narrative-crafter.md` | Sub-agent persona — interviews the user and drafts prose narrative for decks. |
| `agents/creative-director.md` | Sub-agent persona — reviews slides against brand guide, emits actionable creative direction. |
| `agents/source-curator.md` | Sub-agent persona — filters NotebookLM research sources before import. |
| `commands/build-deck.md` | `/build-deck` slash command. |
| `brand-guides/example-brand.md` | Default brand guide (Dark Editorial). Customize or replace. |
| `prompts/visual-refinement-templates.md` | Gemini image prompts keyed by slide role. |
| `prompts/cd-review-prompt.md` | CD review prompt variants (standard / quick / final). |
| `assets/generate_image.py` | Thin Gemini wrapper for optional visual refinement. |
| `.claude/settings.json` | PostToolUse hooks for Notion auto-sync (fires on `source_add` and `download_artifact`). |

## Prerequisites

- **NotebookLM CLI (`nlm`)** — install via `uv tool install notebooklm-mcp-cli`. Provides both the CLI and the MCP server.
- **Notion integration** — set `NOTION_TOKEN` and DB IDs in `D:/NotebookLM/.env` (or your workspace equivalent). Token belongs to a Notion integration scoped to the 5 NotebookLM Tracker DBs.
- **Python deps for sync scripts** — `pip install notion-client==3.0 curl_cffi requests beautifulsoup4 markdownify`.
- **Firecrawl API key** — for `source_doctor.py` tier-1 recovery (optional if you never hit failed-URL stubs).
- **Workspace directory** — `D:\NotebookLM\` (Windows canonical), `/mnt/d/NotebookLM/` (WSL), or `~/NotebookLM/` (standalone Ubuntu/VPS).
- **Optional: `GEMINI_API_KEY`** — for visual refinement step in `/build-deck`. Pipeline skips this step cleanly when unset.

## Install

```bash
# Recommended — from GitHub
claude plugin install varankevich/notebooklm-workspace

# Or, during development, point at a local checkout
claude plugin install file:///d:/NotebookLM/plugin/notebooklm-workspace-plugin
```

After install, verify:

```bash
# In a Claude Code session
/skills
# Expect: notebooklm-workspace, slide-pipeline (or plugin-namespaced equivalents)

# Test the slash command
/build-deck "Your topic here"
```

## First-time setup

1. **Install `nlm`** and run `nlm login` to authenticate with Google.
2. **Create the NotebookLM Tracker** in Notion — 5 databases (Notebooks, Sources, Assets, Research Tasks, NLM Connector). See `skills/notebooklm-workspace/references/notion-sync.md` for schema.
3. **Populate `D:/NotebookLM/.env`** with `NOTION_TOKEN`, DB IDs, `NOTION_SYNC=1`, optional `GEMINI_API_KEY`.
4. **Seed the workspace folder structure** — the skill auto-creates `{audio,video,slides,infographics,sources,exports}/{slug}/` on first use, but you can pre-create if you like.
5. **Trigger a sync** to prove the plumbing:
   ```bash
   python D:/NotebookLM/scripts/sync_notion_notebooks.py --sync
   ```

## Cross-platform notes

| Platform | Workspace path | Interpreter |
|----------|----------------|-------------|
| Windows (canonical) | `D:\NotebookLM\` | `python` (system) |
| WSL (same machine) | `/mnt/d/NotebookLM/` | `python3` |
| Standalone Ubuntu / VPS | `~/NotebookLM/` (cloned separately) | `python3` |

Scripts self-anchor via `Path(__file__).resolve().parent.parent`, so they always write to the workspace of the invoked script, regardless of your `cwd`. Always use absolute paths in commands.

On a host missing the Python deps, the skill applies an **env-incomplete soft-skip**: the NotebookLM op still succeeds, but the Notion sync step is skipped with a clear message and a one-line install fix.

## Architecture

```
┌────────────────────────┐
│ Claude Code session    │
│  (any project cwd)     │
└──────────┬─────────────┘
           │ mcp__notebooklm-mcp__*
           ▼
┌────────────────────────┐      ┌─────────────────────┐
│ nlm CLI + MCP server   ├─────►│ Google NotebookLM   │
└──────────┬─────────────┘      └─────────────────────┘
           │ PostToolUse hooks
           ▼
┌────────────────────────┐      ┌─────────────────────┐
│ sync_notion_*.py       ├─────►│ Notion Tracker (5   │
│ source_doctor.py       │      │ databases)          │
│ (at D:/NotebookLM/     │      └─────────────────────┘
│  scripts/, self-       │
│  anchored)             │
└────────────────────────┘
```

Scripts stay at `D:/NotebookLM/scripts/` (data-adjacent). The plugin references them by absolute path — it doesn't bundle them, because they manage workspace data and need to live with the data.

## Usage examples

### Standard asset generation

```
# In Claude Code, with the plugin installed — just ask
"Generate an audio overview for my Claude-Code-Pricing notebook, focusing on enterprise tiers"
```

The skill handles: notebook lookup → `studio_create` → polling → download → Notion row update.

### Research with curation

```
"Start a deep research task on federated-learning frameworks in the Federated-Learning notebook"
```

Skill runs: `research_start` → poll → **mandatory Haiku curation via `source-curator` agent** → `research_import(indices=...)` → `source_doctor` for stub recovery → `touch`.

### Narrative-first slide deck

```
/build-deck "GDPR Article 6 primer for DPOs"
```

Pipeline: narrative-crafter interviews you → drafts prose → NotebookLM generates slides → optional Gemini refinement → CD review → Notion upload.

## Attribution

This plugin is MIT-licensed and stands on the shoulders of:

- **[Jason-Cyr/openclaw-slide-pipeline](https://github.com/Jason-Cyr/openclaw-slide-pipeline)** (MIT) — narrative-crafter and creative-director agent personas, visual refinement templates, CD review prompts, Dark Editorial example brand guide. Ported from OpenClaw to Claude Code.
- **[teng-lin/notebooklm-py](https://github.com/teng-lin/notebooklm-py)** (MIT) — SKILL.md ergonomics patterns: autonomy rule tables, processing-time tables, background subagent-wait pattern, error/action tables, `--json` discipline.
- **notebooklm-mcp-cli** (the `nlm` binary + MCP server) — the underlying CLI and MCP server. Not bundled; installed separately via `uv tool install notebooklm-mcp-cli`.
- **[Google NotebookLM](https://notebooklm.google.com/)** — the platform this plugin automates against.

## License

MIT. See [LICENSE](LICENSE).
