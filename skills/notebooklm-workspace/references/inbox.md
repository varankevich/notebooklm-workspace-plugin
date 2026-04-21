# Inbox Ingestion Workflow

Drop files into `D:\NotebookLM\inbox\` → watcher detects → matches to notebooks → Claude confirms → upload. Load when the task is "process inbox" or when a file appears in the inbox.

## Overview

| Step | What happens |
|------|--------------|
| Drop file in `inbox/` | Watcher detects → adds to `queue.md` → runs matching |
| Session start | Hook injects "N files pending" alert if queue has items |
| User says "process inbox" | Run `ingest.py`, show plan, wait for user confirmation |
| User confirms | Upload to matched notebooks via `source_add(source_type="file")` |
| Post-ingestion | File → `inbox/processed/` + copy → `sources/{slug}/` per notebook |
| Mandatory | `sync_notion_sources.py touch --notebook <short-id>` per notebook touched |

## Folder Structure

```
inbox/
├── (drop files here — any PDF, TXT, MD, DOCX, MP3, MP4)
├── processed/          ← originals moved here after ingestion
├── queue.md            ← watcher log (pending → done)
├── pending-plan.json   ← ingest.py output, reviewed before execution
└── watcher.pid         ← PID of running watcher (when daemon mode)
```

## Matching Logic

`ingest.py` does NOT do token-scoring or keyword matching anymore. It just extracts text from the file:
- PDF: first 5 pages via `pypdf`
- TXT/MD: full text
- DOCX: full text via `python-docx`
- MP3/MP4: transcript via CLI, if available; else metadata + filename

Then prints a content preview. **Claude reads the preview in-context and performs semantic matching** against `notebooks.md`. No external API calls, no scoring algorithm — just Claude's understanding of the document's topic against the notebook inventory.

This means matching quality depends on:
- Having a complete, well-categorized `notebooks.md` (kept current by `sync_notion_notebooks.py --pull`)
- The preview actually capturing the document's topic (first 5 pages is usually enough)

## Manual Trigger

```bash
# Process all pending files in queue
python scripts/ingest.py

# Process a specific file (any location)
python scripts/ingest.py "path/to/file.pdf"

# Show queue without processing
python scripts/ingest.py --list
```

## Background Watcher

```bash
# Foreground (Ctrl+C to stop)
python scripts/watch_inbox.py

# Detached daemon (Windows)
python scripts/watch_inbox.py --daemon
# PID saved to inbox/watcher.pid
```

The watcher uses `watchdog` for filesystem events. On new file:
1. Adds row to `queue.md` (status: pending)
2. Runs `ingest.py` in-process to extract preview + write `pending-plan.json`
3. Sleeps until next file event

## Confirmation Flow (CRITICAL)

After `ingest.py` runs, present matched notebooks as a **numbered index table** for the user to select from.

### Rules

- **Only show notebooks with score > 0** — never add unscored "obviously relevant" notebooks to the list. If the user wants one, they can say so.
- **Sort strictly by score descending** — highest confidence first
- Include auto-matched notebooks AND manually added candidates that are clearly relevant but scored 0 (e.g., AI-topic notebooks for an AI paper)
- Format as a table with numbered rows for selection

### Format

```
FILE: gdpr-anonymization-techniques.pdf  (content-based matching used)

| # | Notebook | Score |
|---|----------|-------|
| 1 | GDPR Anonymization - Methods & Regulatory Standards | 0.42 |
| 2 | GDPR Pseudonymization - Techniques & Legal Framework | 0.31 |
| 3 | Privacy KB: Anonymizing Data with AI | 0.20 |
| 4 | Data Protection Impact Assessments (DPIAs) | 0.15 |

Reply with the numbers to add (e.g. "1, 3") — or "none".
You can also say "also add to <name>" for any notebook not in this list.
```

User replies with index numbers → upload only those notebooks.

## Execution

After user confirms, for each matched notebook:

```python
source_add(
    source_type="file",
    file_path="D:/NotebookLM/inbox/filename.pdf",
    title="filename.pdf",  # or a cleaner title if derivable
    notebook_id="<full-uuid>",  # not the short-id
)
```

**Short-id vs full UUID:**
- `notebooks.md` rows have the short ID (first 8 chars of UUID)
- `source_add` needs the full UUID
- Use `nlm notebook list --json` or `mcp__notebooklm-mcp__notebook_list()` to resolve

## Post-Ingestion

Automatically handled by `ingest.py`'s `stage_file()`:

```bash
# Move original
mv inbox/file.pdf inbox/processed/file.pdf

# Copy to each target notebook's sources folder
cp inbox/processed/file.pdf sources/{slug1}/file.pdf
cp inbox/processed/file.pdf sources/{slug2}/file.pdf
```

Update `queue.md` row status: `pending` → `done`.

Then **mandatory**: touch each notebook:
```bash
for slug in slug1 slug2; do
    python scripts/sync_notion_sources.py touch --notebook "${slug}"
done
```

With `NOTION_SYNC=1`, each `source_add` call also triggers the PostToolUse hook's `push --notebook <id>` — so touch may be redundant. But running touch anyway is fine (it's idempotent) and covers the case where the hook didn't fire (e.g., the file was added via a different tool).

## Common Pitfalls

- **User sees "files pending" alert at session start but file already processed** — the session-start hook reads `queue.md`; stale `pending` rows cause false alerts. Make sure `ingest.py` updates status to `done` after upload.
- **Matching returns no results** — check `notebooks.md` is up to date (`sync_notion_notebooks.py --pull`), check the file preview actually captures the topic (increase PDF page limit if needed).
- **Upload succeeds but file stuck in `inbox/`** — `stage_file()` ran but failed to move. Look for permission errors. Manual: `mv inbox/file.pdf inbox/processed/file.pdf`.
- **Same file matched to wrong notebook** — user's confirmation step is the check. If it happens repeatedly, the preview isn't capturing the topic — adjust `ingest.py`'s extraction logic for that file type.
