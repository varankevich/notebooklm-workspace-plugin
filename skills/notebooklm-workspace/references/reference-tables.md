# Reference Tables — Autonomy, Timeouts, Subagent Waits, Errors

Quick-lookup tables that codify how this skill behaves around confirmation, long-running operations, parallelism, and error recovery. Load when you need a decision quickly without reading a long workflow page.

Patterns in this file are adapted from `teng-lin/notebooklm-py`'s SKILL.md (MIT) and combined with our workspace's observed behavior.

---

## Table 1 — Autonomy Rules

Two tiers: operations you run without asking the user, and operations that always require explicit confirmation.

### Auto-run (no confirmation needed)

Read-only or status-only operations. Safe to call freely.

| Area | Tools / commands |
|------|------------------|
| Listing | `notebook_list`, `nlm notebook list`, `source list`, `artifact list` (MCP/CLI) |
| Describe | `notebook_describe`, `source_describe`, `server_info` |
| Read content | `source_get_content`, `nlm source content` |
| Status polling | `research_status`, `studio_status`, `notebook_query_status` |
| Query | `notebook_query`, `cross_notebook_query` (non-destructive Q&A) |
| Auth | `nlm login profile list`, `nlm auth check`, `refresh_auth()` |
| Workspace | `sync_notion_*.py --pull` (read), `source_doctor --dry-run` |
| Health | `nlm doctor` (if available) |

### Ask first (explicit user confirmation required)

Destructive, generative, or filesystem-writing operations. Always confirm scope and intent before running.

| Area | Tools / commands | Why |
|------|------------------|-----|
| Delete | `notebook_delete`, `source_delete`, `studio_delete`, `note_delete` | Irreversible |
| Generate artifacts | `studio_create(confirm=True)`, `nlm audio/video/slides/infographic create --confirm` | Long-running, may fail, counts toward quotas |
| Download | `download_artifact`, `nlm download *` | Writes to filesystem |
| Rename | `notebook_rename`, `source_rename` | Changes identifiers used elsewhere |
| Research import | `research_import` | Adds sources to corpus (affects budget) |
| Research force-start | `research_start(force=True)` | Abandons prior pending task |
| Notes (write) | `note_create`, `note_update`, `--save-as-note` flags | Persists content |
| Sharing | `notebook_share_*` | Exposes content externally |
| Notion push | `sync_notion_*.py --push`, `--sync`, `--confirm-dedupe` | Mutates Notion DB |
| Corpus cleanup | `sync_notion_sources.py dedupe --confirm-dedupe` | Deletes rows |
| Destructive recovery | `source_doctor.py` without `--dry-run` | Deletes failed stubs (pre-authorized by standing rule but still surface what will happen) |

**Standing pre-authorizations** (exceptions to "ask first"):
- `source_doctor.py` (full run, not dry-run) — pre-authorized by `feedback_failed_source_recovery_delete.md` memory.
- Mandatory `touch` after any source op — pre-authorized by `feedback_source_touch.md`.

---

## Table 2 — Processing Times + Suggested Timeouts

Use these numbers to size `timeout` parameters, pick subagent wake intervals, and explain waits to the user.

| Operation | Typical duration | Suggested timeout | Notes |
|-----------|------------------|-------------------|-------|
| Source processing (URL/file → ingested) | 30s – 10min | 600s | Watch `status_code`; stubs appear if ingest fails |
| Research — `mode=fast` | 30s – 2min | 180s | ~10 sources per task |
| Research — `mode=deep` | 15 – 30min+ | 1800s | ~40–90 sources; never use for parallel batches |
| Mind-map generation | Instant (sync) | n/a | Returns JSON immediately |
| Data-table generation | 5 – 15min | 900s | CSV export |
| Report generation | 5 – 15min | 900s | `briefing-doc`, `study-guide`, `blog-post`, `custom` |
| Quiz generation | 5 – 15min | 900s | JSON/MD/HTML export |
| Flashcards generation | 5 – 15min | 900s | JSON/MD/HTML export |
| Slides generation | 5 – 15min | 900s | PDF default, `-f pptx` for editable |
| Slide revision (individual) | 2 – 5min | 600s | Re-downloads parent deck |
| Infographic generation | 3 – 10min | 600s | PNG |
| Audio (deep-dive) | 10 – 20min | 1200s | MP3 |
| Audio (brief/critique/debate) | 5 – 15min | 900s | MP3 |
| Video (explainer) | 15 – 45min | 2700s | MP4 — longest artifact type |
| Video (brief) | 10 – 30min | 1800s | MP4 |
| Notion sync (single notebook) | 5 – 30s | 60s | Run synchronously |
| Notion sync (all 200+ notebooks) | 2 – 5min | 600s | Paginated |
| Source Doctor (per notebook) | 1 – 20min | depends on stub count | Each tier escalation adds 5–30s; quarantine is cheap |

**Audio download gotcha**: audio `status_code == 2` (CDN partial) returns **HTTP 404** on download. Always poll until `status_code == 3`. Slides at `status_code 2` sometimes download but may hit intermittent 5xx on `contribution.usercontent.google.com` — retry 3× with exponential backoff.

---

## Table 3 — Background Subagent Wait Pattern

When you kick off a long-running artifact generation and want the main conversation to continue (answering follow-ups, doing other work), spawn a background `Agent` to do the wait + download.

### When to use this pattern

- Generation time ≥ 5 minutes AND the user wants to keep working in the main thread.
- You'd otherwise need multiple `ScheduleWakeup` calls over a long window.
- You have other independent work queued that doesn't depend on the artifact.

### When NOT to use this pattern

- Pipeline mode (multi-round artifact generation) — use `ScheduleWakeup` self-pacing at 90s instead, because rounds must sequence.
- Single artifact with nothing else to do — just `ScheduleWakeup` inline.

### Spawn template

```python
Agent(
    description="Wait for audio artifact + download",
    subagent_type="general-purpose",
    run_in_background=True,
    prompt="""
Wait for NotebookLM artifact to complete and download it.

Context:
- notebook_id: {nb_id}
- artifact_id: {artifact_id}
- artifact_type: audio
- output_path: D:/NotebookLM/audio/{slug}/{focus}.mp3

Steps:
1. Poll via mcp__notebooklm-mcp__studio_status every 60s.
   - Expect completion in 10-20 min (audio deep-dive).
   - Fail after 1500s total.
2. Once status is 'ready' AND status_code == 3, call:
   mcp__notebooklm-mcp__download_artifact(
       artifact_type="audio",
       notebook_id="{nb_id}",
       artifact_id="{artifact_id}",
       output_path="D:/NotebookLM/audio/{slug}/{focus}.mp3"
   )
3. PostToolUse hook will auto-sync to Notion.
4. Report success + final file size + Notion row status.

Do NOT retry indefinitely. If generation fails (status=failed),
report the failure cause and exit.
"""
)
```

### Choosing `ScheduleWakeup` vs. background Agent

| Situation | Use |
|-----------|-----|
| One artifact, nothing else to do | `ScheduleWakeup` |
| One artifact, user wants to keep working | Background `Agent` |
| Pipeline (N rounds, sequential) | `ScheduleWakeup` self-pacing (90s cycle) |
| Multi-aspect fast research (parallel tasks) | `ScheduleWakeup` + parallel `research_status` polling |

---

## Table 4 — Error → Action

Map the error message to the right recovery step. These are the actual errors observed across the workspace's history.

| Error signature | Cause | Action |
|-----------------|-------|--------|
| `Authentication error` / `cookie expired` / 401 on MCP | Session expired (~20 min idle) | `nlm login` via Bash, then `refresh_auth()`, retry silently — do NOT ask the user |
| `No notebook context` / missing notebook | CLI context not set for single-agent mode | Pass `-n <id>` or `--notebook <id>` flag explicitly |
| `No result found for RPC ID` | Google-side rate limit | Wait 5–10 min, retry. Consider smaller batch |
| `GENERATION_FAILED` | Google rate-limit / throttle | Back off + retry 1×. If persists, surface to user |
| `pending task` on `research_start` | Prior task completed-but-not-imported | Re-issue with `--force` / `force=True`. Never delete the pending task |
| HTTP 404 on audio download | `status_code=2` (CDN partial) | Poll `studio_status` until `status_code=3`, then retry |
| HTTP 400 on Notion URL-first upload (slides) | `contribution.usercontent.google.com` requires Google auth | Already handled — binary upload fallback fires automatically |
| HTTP 403 Cloudflare on Notion file send | Using stock `requests` instead of `curl_cffi` | Switch to `curl_cffi` with `impersonate="chrome"` — already in `notion_files.py` |
| `ERROR: No notebook in Notion DB with slug or short_id == 'X'` | Fresh notebook not mirrored to Notion yet | Run `sync_notion_notebooks.py --sync` first, then retry source_doctor |
| `ModuleNotFoundError: notion_client / requests / curl_cffi` | Host env missing workspace deps (typical on fresh WSL/VPS) | Report "Notion sync skipped — env incomplete", offer `pip install notion-client==3.0 requests curl_cffi`. Do NOT fail the whole op |
| `python not found` / `python3: command not found` | Interpreter missing | Same soft-skip as above |
| Research task alias mismatch on import | Fast task aliased to concurrent deep task | Retry with canonical `task_id`; if still mismatched, relaunch isolated |
| `100-result cap hit` | Using `notion-query-database-view` for bulk scan | Switch to `sync_notion_assets.py _load_notebooks()` paginated helper |
| Duplicate rows after scan | `str(Path)` used instead of `_stored_path()` helper | Always go through `_stored_path()` — canonical form (ROOT-relative, forward slashes) |

---

## Pattern: Always Use `--json` in Subagent / Scripted Contexts

When a subagent needs to parse CLI output, pass `--json` to every `nlm` command. Text output can change across versions; JSON schema is stable.

```bash
# In subagent scripts — always --json
nlm notebook list --json | jq '.notebooks[].id'
nlm source list <nb-id> --json | jq '.sources[] | select(.status == "READY")'
nlm research status <nb-id> --task-id <tid> --json
```

In main conversation (human-readable output), omit `--json`.

---

## Pattern: Exit Codes

Observe exit codes when scripting `nlm` calls:

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | Error (not found, generation failed, auth error) |
| 2 | Timeout (wait commands only) |

Check `$?` or `subprocess` returncode in scripts to distinguish timeout (2) from hard failure (1) — timeout is often recoverable by re-polling; hard failure usually isn't.
