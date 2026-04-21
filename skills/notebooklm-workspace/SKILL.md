---
name: notebooklm-workspace
description: "Workspace procedures and automation for D:\\NotebookLM, invokable from any project on this device. Invoke for: Notion sync (notebooks/sources/assets), inbox file processing, artifact generation/upload (audio/video/slides/infographics), deep research + source import, post-operation workflows (what to run after adding/deleting sources), automation troubleshooting (why didn't sync run). Handles 206+ notebooks ↔ Notion 5-DB tracker, mandatory sync steps, folder conventions, research curation, scripts, hooks. Complements nlm-skill (CLI/MCP syntax)."
---

# NotebookLM Workspace Skill

Extends `nlm-skill`. Load that skill first for NotebookLM CLI/MCP syntax. This skill covers **project-specific conventions** for `D:\NotebookLM\` — paths, Notion DB IDs, mandatory workflow rules, and the automation layer.

## Why this skill exists

The NotebookLM workspace has a lot of invariants that don't belong in the shared `nlm-skill`: which Notion DBs mirror what, which folders host which asset type, which scripts to run after a source op, how the inbox matches files to notebooks, how to handle auth expiry silently. Inlining all of that every turn wastes context and hides the invariants. This file is the lean entry point — details live in `references/` and load only when a workflow is active.

## Mandatory Rules

These are non-negotiable because they prevent data loss, duplicate rows, or blown source budgets. Always follow them without asking the user.

1. **After any source op** (add, delete, rename, ingest, recover), run the touch command — platform-aware:
   ```bash
   # Windows
   python D:/NotebookLM/scripts/sync_notion_sources.py touch --notebook <short-id>
   # WSL on this machine (canonical) / standalone Linux if cloned here
   python3 /mnt/d/NotebookLM/scripts/sync_notion_sources.py touch --notebook <short-id>
   ```
   This keeps the Notion Sources DB mirror in sync. If you skip it, downstream automations read stale data. Use the absolute path — this skill runs from any project, so `scripts/` alone won't resolve correctly. Scripts self-anchor via `__file__`, so the only real choice is which interpreter + workspace path reaches the deps.

   **Env-incomplete soft-skip.** If the command fails with `python not found`, `python3: command not found`, or `ModuleNotFoundError: notion_client / requests / curl_cffi` (typical on a fresh WSL/VPS host where the workspace deps were never installed), do **not** treat it as a NotebookLM failure. The notebook op itself already succeeded. Report to the user: *"Notebook updated; Notion sync skipped — workspace env incomplete on this host."* The one-line fix:
   ```bash
   pip install notion-client==3.0 requests curl_cffi
   ```
   `uv run` will not rescue you unless the deps are pre-installed in the resolved env. Known WSL gotcha — surfaced 2026-04-17.

2. **Between `research_status` and `research_import` on any task returning >5 sources**: spawn a Haiku curation sub-agent (via the Agent tool with `model: "haiku"`). Research returns 10–90 sources; typically 30–50% are low-value. Import only the approved indices. For multi-task batches (parallel fast-mode discovery), curate all tasks in a single Haiku call with cross-task deduplication. See [references/research-workflow.md](references/research-workflow.md) for both single-task and multi-task curation prompts.
   - **Never** call `research_import` with no `source_indices` on any task with >5 sources.

3. **Auth expiry is silent — recover silently**: when any MCP tool returns an auth error, don't ask the user. Run `nlm login` via Bash, call `refresh_auth()`, retry. Full recipe in [references/workspace.md](references/workspace.md#auth-recovery). Sessions expire in ~20 min.

4. **Never use ad-hoc Notion MCP queries for bulk sweeps**: `notion-query-database-view` caps at 100 results per page and requires manual cursor chaining. For notebook-wide operations, always use the paginated helpers in `scripts/sync_notion_assets.py` (`_load_notebooks()` does while-True + has_more/next_cursor correctly, covers all 200+).

5. **Automatic Notion sync is ON by default** (`NOTION_SYNC=1` in `.env`). PostToolUse hooks fire after `download_artifact` and `source_add` calls and run the appropriate sync script. To pause: set `NOTION_SYNC=0`. See [references/notion-sync.md](references/notion-sync.md#automatic-sync).

6. **Run `source_doctor.py` after every `research_import`** that imports any URL sources (and any time you suspect failed-ingest stubs). It detects stubs, walks Firecrawl → curl_cffi → quarantine, uploads recovered content, deletes stubs (per the standing pre-authorization), and runs `touch`. Platform-aware:
   ```bash
   # Windows
   python D:/NotebookLM/scripts/source_doctor.py --notebook <slug-or-short-id>
   # WSL on this machine
   python3 /mnt/d/NotebookLM/scripts/source_doctor.py --notebook <slug-or-short-id>
   ```
   Use `--dry-run` to detect without changing anything. Same env-incomplete soft-skip as Rule 1 applies — if deps are missing, report and offer the install command rather than failing the workflow. Full ladder + stub-detection logic in [references/source-ops.md](references/source-ops.md#recovering-failed-urls-scraping-fallback). Do **not** hand-roll Firecrawl `curl` calls when a notebook just had stubs land — the script does it deterministically and keeps Notion in sync.
   - **Fresh-notebook prereq:** if the notebook was created via `mcp__...__notebook_create` earlier in the same session, run `python D:/NotebookLM/scripts/sync_notion_notebooks.py --sync` before invoking source_doctor. Otherwise source_doctor exits with `ERROR: No notebook in Notion DB with slug or short_id == '<id>'` — the short-id → full-UUID lookup happens against the Notion mirror, and a just-created notebook isn't there yet. This was observed 2026-04-17 on the Firecrawl-Alternatives pilot.

7. **Scope exclusions are session-scoped filters, not one-off edits**: when the user says "topic X was resolved in another notebook, exclude it from this one" (or sets this at notebook creation), record the exclusion for the whole session. Apply it to every subsequent curation prompt as a rejection rule, and issue a batch `source_delete` for any already-imported sources whose main topic is X. Don't leave them in — their presence pollutes notebook_query answers and future gap analysis.

8. **For final-deliverable queries after corpus completion, split by the deliverable's outline, not by "ask everything at once":** NotebookLM's tool-result size is dominated by the citations/references payload (each cited source appears with `cited_text`, sometimes including full `cited_table` rows). A single comprehensive query against a 90+-source notebook typically exceeds the output cap even when the answer text is small. Derive the deliverable's outline from the user's original request first — the shape differs by task type (tool evaluation, literature review, investigation, how-to guide, concept primer, comparison, market analysis, biography, policy/legal question, medical/scientific question, etc.) — then issue 6–10 sub-queries, one per outline heading, each with compact formatting rules (table-only cells or explicit word budget, bracketed citations only, scope exclusions inherited, shared `conversation_id`). Always end with a gap-query sub-query ("what is NOT well-covered by the current sources?"). Assemble inline in outline order. Full pattern in [references/research-workflow.md](references/research-workflow.md#answering-the-original-request-after-the-corpus-is-complete).

## Workspace Invariants

| Key | Value |
|-----|-------|
| Root | `D:\NotebookLM\` (Windows, canonical); `/mnt/d/NotebookLM/` (WSL on this machine — same workspace via drive mount, single `.env`); `~/NotebookLM/` (standalone Ubuntu / VPS). Scripts auto-detect via `Path(__file__).resolve().parent.parent` |
| CLI discovery | `NLM_CLI` env var → `shutil.which("nlm")` → platform default. Implementation: `scripts/_cli_paths.py`. Portability details in `CLAUDE.md` § Cross-Platform Installation |
| Skill location | **Global** — `~/.claude/skills/notebooklm-workspace/` on all platforms (portable copy tracked in-repo at `.claude/skills/notebooklm-workspace/`) |
| Hooks location | **Global** — `~/.claude/settings.json` PostToolUse (fires from any project; hook script path differs per host) |
| Invocation context | Any cwd — scripts and hooks self-anchor to the workspace root via `Path(__file__).resolve()`, so absolute paths in commands are mandatory |
| Active account | `dataprivacyoffice@gmail.com` (profile: `default`) |
| Plan | **Pro** — 300 sources/notebook, 500K words/source, 200 MB/file |
| Notebook count | ~206 (see `notebooks.md`) |
| Folder pattern | `D:\NotebookLM\{audio\|video\|slides\|infographics}\{slug}\{filename}` |
| `{slug}` source of truth | `Slug` property on Notion Notebooks DB (auto-derived from Name; customizable) |
| Scripts directory | `D:\NotebookLM\scripts\` (always invoke with full path, not `./scripts/`) |
| Python | System `python` (has `notion-client==3.0`, `curl_cffi`, `requests`) |

## Quick Reference — Most-Used Commands

All script paths are absolute because this skill runs from any project — `./scripts/` would resolve to the wrong cwd. Scripts self-anchor to `D:\NotebookLM\` via `__file__`, so they write output to the correct workspace regardless of where you invoke them.

> **Platform note.** Commands below use the Windows path. On WSL on this machine, replace `python D:/NotebookLM/...` with `python3 /mnt/d/NotebookLM/...` — the `D:` drive is mounted there and the workspace is shared (same `.env`, same assets). On standalone Ubuntu / VPS, use whatever path you cloned to (typically `~/NotebookLM/`) with `python3`. If the interpreter or deps are missing, apply the env-incomplete soft-skip from Rule 1.

| Task | Command |
|------|---------|
| Sync notebook inventory | `python D:/NotebookLM/scripts/sync_notion_notebooks.py --sync` |
| Scan + upload all assets | `python D:/NotebookLM/scripts/sync_notion_assets.py --sync` |
| Push sources after source op | `python D:/NotebookLM/scripts/sync_notion_sources.py push --notebook <short-id>` |
| Touch (mandatory after source op) | `python D:/NotebookLM/scripts/sync_notion_sources.py touch --notebook <short-id>` |
| Recover failed-ingest URL stubs | `python D:/NotebookLM/scripts/source_doctor.py --notebook <short-id>` |
| Process inbox | `python D:/NotebookLM/scripts/ingest.py` |
| Start inbox watcher | `python D:/NotebookLM/scripts/watch_inbox.py --daemon` |
| One-shot asset generation + upload | `python D:/NotebookLM/scripts/sync_notion_assets.py generate --notebook <slug> --type audio --focus "..."` |

## Decision Tree — Where to Look

Load only what the task needs. Each reference is focused on one coherent topic.

| If the task is… | Load | Why |
|-----------------|------|-----|
| Adding/recovering sources, Firecrawl fallback, dedup | [references/source-ops.md](references/source-ops.md) | Scraping protocol + touch mandate |
| Post-multi-pass corpus dedup, landing/PDF pair policy | [references/source-ops.md](references/source-ops.md#corpus-cleanup--dedup-pass) | Mandatory closing step after >2-cycle series |
| Starting deep research, curating, importing | [references/research-workflow.md](references/research-workflow.md) | Platform targeting + full haiku curation prompt |
| Generating/downloading audio/video/slides/infographics | [references/asset-pipeline.md](references/asset-pipeline.md) | Artifact types → folders, URL-first upload, `generate` flow |
| **Building a deck from scratch (narrative-first)** | [references/slide-pipeline.md](references/slide-pipeline.md) | Narrative → NotebookLM slides → Gemini refinement → CD review → Notion |
| **Autonomy / timeouts / subagent-wait / error-action lookup** | [references/reference-tables.md](references/reference-tables.md) | Four quick-reference tables for fast decisions |
| Notion DB schemas, sync scripts, hooks, command-pattern SOPs | [references/notion-sync.md](references/notion-sync.md) | 5-DB architecture + automatic sync |
| Auth recovery, account switching, folder structure | [references/workspace.md](references/workspace.md) | Workspace primitives |
| Dropping files into the inbox, matching, confirmation UI | [references/inbox.md](references/inbox.md) | Inbox watcher + ingest.py |
| Historical decisions, "why is it like this?" | [references/changelog.md](references/changelog.md) | Full history of workspace evolution |

## Workflow Entry Points

### Source ingestion (URL, text, Drive, file)
See [references/source-ops.md](references/source-ops.md). Key invariant: any source op triggers the mandatory `touch` step.

### Research → curated import (single or multi-aspect)
See [references/research-workflow.md](references/research-workflow.md). Key invariants: always `mode="fast"` for multi-query batches; curate before import; platform names and source type scoping go in the query text; multi-task curation runs in one Haiku call with cross-task dedup. For building a notebook on a topic with multiple dimensions, use the **Multi-Aspect Discovery Pattern** in that file.

### Artifact generation → download → Notion upload
See [references/asset-pipeline.md](references/asset-pipeline.md). Key invariant: artifact type + parent folder determines Notion asset-type select value; URL-first upload for audio/infographic, binary fallback for slides.

### Notion sync
See [references/notion-sync.md](references/notion-sync.md). Key invariants:
- Notion owns Category, Tags, Notes (never overwrite from CLI).
- `sync_notion_*.py` scripts are the canonical sync path — don't write custom Notion calls.
- PostToolUse hooks fire automatically when `NOTION_SYNC=1`.

### Inbox ingestion (files dropped into `inbox/`)
See [references/inbox.md](references/inbox.md). Key invariant: present matched notebooks as a numbered index table; only include score > 0 notebooks, sorted by score desc.

### Narrative-first slide deck (`/build-deck`)
See [references/slide-pipeline.md](references/slide-pipeline.md). Key invariants: prose narrative first (spawn `narrative-crafter` sub-agent), NotebookLM generates slides from the narrative, optional Gemini refinement gated on `GEMINI_API_KEY`, Creative Director sub-agent review against brand guide, 3-iteration cap. User entry point: `/build-deck "<topic>"`.

### Autonomy decisions + operation sizing
See [references/reference-tables.md](references/reference-tables.md). Four tables for quick lookup:
1. **Autonomy rules** — auto-run vs. ask-first by command.
2. **Processing times + timeouts** — per artifact type, for sizing subagent timeouts.
3. **Background subagent wait pattern** — spawn-template for long-running artifact waits.
4. **Error → action** — error signature to recovery step mapping.

Also codifies: always pass `--json` to `nlm` calls in subagent/scripted contexts (stable schema), and observe exit codes (0/1/2).

## Common Anti-Patterns

These come up often enough to flag at the top level:

- **Manually crafting YouTube/Reddit URLs as sources.** These fail — NotebookLM rejects dynamic search/listing pages. Always embed the platform name in a research query instead. See [research-workflow.md](references/research-workflow.md#platform-targeting).
- **Using `mode="deep"` for parallel multi-query batches.** Deep mode merges concurrent queries server-side into ~4 bulk backend jobs — you lose the task_id → query mapping and can't attribute sources back to their discovery dimension. Always use `mode="fast"` for multi-query discovery.
- **Running one broad discovery per source type without aspect analysis.** Narrow aspects (pricing, handover topics) don't yield meaningfully different signal from Reddit vs. YouTube vs. official docs — they produce thin, overlapping results. Analyse aspect breadth first; combine narrow aspects into one universal query.
- **Calling `notion.pages.create(parent={database_id: DS_ID})`.** `data_sources.query` uses the DS_ID; `pages.create` uses the DB_ID. They're different — `NOTION_*_DB_ID` and `NOTION_*_DS_ID` both live in `.env`.
- **Using `str(Path)` to store or compare Notion `Local File Path` values.** That yields absolute Windows paths with backslashes; stored paths are ROOT-relative with forward slashes. Use `_stored_path()` helper in `sync_notion_assets.py`.
- **Passing `notebook_id` to `notion-query-database-view` for bulk scans.** 100-result cap — use the script's paginated `_load_notebooks()` instead.
- **Importing `sync_notion_assets.py scan` results before files finish downloading.** The scan walks the filesystem; if download is mid-flight it sees partial files. Wait for download completion (or use the PostToolUse hook path).
- **Running `nlm research start` on a notebook with a prior completed-but-not-imported task.** The call aborts with a pending-task error. For iterative multi-pass discovery this is almost always the state — you import in batches, not task-by-task. Pass `--force` (CLI) / `force=True` (MCP). Don't "clean up" by deleting the pending task — its sources may still be curatable in the next cycle. See [research-workflow.md](references/research-workflow.md#prior-completed-but-not-imported-tasks-block-new-starts).
- **Assuming `python` resolves everywhere.** On WSL/Ubuntu, only `python3` is present. On fresh hosts without the workspace pip install, even `python3` won't have `notion_client` / `requests` / `curl_cffi` — and `uv run` won't rescue you unless the deps were pre-installed. Soft-skip Notion sync (report "sync skipped — env incomplete") rather than failing the whole workflow. Full recipe in Rule 1.

## When Extending This Skill

This skill is **trigger-driven**:
- Add a rule when a workflow is missing and you had to improvise — codify it next time
- Add a clarifying answer when the same question surfaces twice
- Promote a pattern from `knowledge/concepts/` when it recurs across sessions
- Do **not** add NotebookLM CLI/MCP syntax here — that belongs in `nlm-skill`
- Do add workspace paths, Notion targets, sync scripts, inbox/research conventions

Changelog entries go in [references/changelog.md](references/changelog.md) — out of the hot path but preserved.

---

**Pairing:** Always used alongside `nlm-skill` (global). This skill answers "where/how in this workspace?"; nlm-skill answers "what's the CLI/MCP call?".
