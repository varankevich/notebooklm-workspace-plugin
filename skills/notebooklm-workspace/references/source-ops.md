# Source Operations

Adding sources, recovering failed URLs, deduplication, the mandatory `touch` step. Load when the task involves sources — adding, removing, renaming, scraping.

## The Touch Mandate

**After ANY source op — add, delete, rename, ingest, recover — run the touch command. Platform-aware:**

```bash
# Windows (canonical)
python D:/NotebookLM/scripts/sync_notion_sources.py touch --notebook <short-id>
# WSL on this machine (shared workspace via /mnt/d)
python3 /mnt/d/NotebookLM/scripts/sync_notion_sources.py touch --notebook <short-id>
# Standalone Ubuntu / VPS (clone path — typically ~/NotebookLM/)
python3 ~/NotebookLM/scripts/sync_notion_sources.py touch --notebook <short-id>
```

Why: the Notion Sources DB is a one-way mirror from NotebookLM. If you skip touch, downstream automations (n8n flows, Notion formulas using `Last Modified`) read stale data. The `--notebook` flag scopes the sync to just the one notebook, keeping it fast (~2–5s vs ~2 min for a full push).

### Env-incomplete soft-skip

On a fresh WSL or VPS host the command may fail with:
- `python: command not found` / `python3: command not found`
- `ModuleNotFoundError: No module named 'notion_client'` (or `requests`, `curl_cffi`)
- `uv run` doesn't rescue you unless the deps were pre-installed in the resolved env

**Do not treat this as a NotebookLM failure.** The notebook op itself already succeeded — only the Notion mirror step was skipped. Report to the user:

> Notebook updated; Notion sync skipped — workspace env incomplete on this host.

Then offer the one-line install:

```bash
pip install notion-client==3.0 requests curl_cffi
```

On subsequent source ops, retry the touch command once installed.

With the PostToolUse hook active (`NOTION_SYNC=1`), `mcp__notebooklm-mcp__source_add` calls trigger `sync_notion_sources.py push --notebook <id>` automatically. But the hook doesn't fire for CLI `nlm source add` — use touch manually in that case.

## Adding Sources

### URL (web, YouTube, social)

```bash
nlm source add <nb-id> --url "https://example.com/article"
nlm source add <nb-id> --url "https://youtube.com/watch?v=..."
# or MCP:
source_add(notebook_id="...", source_type="url", url="...")
```

**Do not** manually paste YouTube search pages, Reddit subreddit pages, or Google search results as URL sources — NotebookLM rejects dynamic listing pages. For platform-targeted discovery, use research instead (see [research-workflow.md](research-workflow.md#platform-targeting)).

### Text (pasted / recovered)

```bash
nlm source add <nb-id> --text "$(cat sources/{slug}/file.md)" --title "Title"
# or MCP:
source_add(source_type="text", text="...", title="...", notebook_id="...")
```

Use for: content recovered from Firecrawl/WebFetch, notes, pasted articles.

### Google Drive

```bash
nlm source add <nb-id> --drive <doc-id>                   # auto-detect type
nlm source add <nb-id> --drive <doc-id> --type slides     # explicit
# types: doc, slides, sheets, pdf
```

For stale Drive sources:
```bash
nlm source stale <nb-id>               # list outdated
nlm source sync <nb-id> --confirm      # sync all
nlm source sync <nb-id> --source-ids <ids> --confirm
```

### Local file upload

```bash
# MCP only:
source_add(source_type="file", file_path="D:/path/to/file.pdf", notebook_id="...")
```

Used by the inbox ingestion workflow.

## Recovering Failed URLs (Scraping Fallback)

**Always prefer the automated path:** run `source_doctor.py` instead of doing recovery by hand. It detects stub sources, walks the recovery ladder, uploads the recovered content, deletes the stub (per the standing pre-authorization), and runs the mandatory `touch` — all in one command.

### Automated path (preferred)

```bash
# Windows
python D:/NotebookLM/scripts/source_doctor.py --notebook <slug-or-short-id>
python D:/NotebookLM/scripts/source_doctor.py --notebook <slug> --dry-run    # detect only
python D:/NotebookLM/scripts/source_doctor.py --notebook <slug> --grace 90   # wait for in-flight ingests

# WSL on this machine
python3 /mnt/d/NotebookLM/scripts/source_doctor.py --notebook <slug-or-short-id>
python3 /mnt/d/NotebookLM/scripts/source_doctor.py --notebook <slug> --dry-run
python3 /mnt/d/NotebookLM/scripts/source_doctor.py --notebook <slug> --grace 90
```

Env-incomplete soft-skip applies here too — if `python3` / deps are missing, report and offer the install command from the Touch Mandate section; don't fail the workflow.

**Fresh-notebook prereq:** if the notebook was created in the current session via `mcp__...__notebook_create` (i.e. it exists in NotebookLM but hasn't been synced to the Notion Notebooks DB yet), source_doctor fails with `ERROR: No notebook in Notion DB with slug or short_id == '<id>'`. The script's short-id → full-UUID lookup runs against the Notion mirror, not the live NotebookLM API. Run a sync first:

```bash
python D:/NotebookLM/scripts/sync_notion_notebooks.py --sync
python D:/NotebookLM/scripts/source_doctor.py --notebook <short-id>
```

Established notebooks (anything already in `notebooks.md`) don't need this — they're already mirrored. Only applies to notebooks created mid-session. Observed 2026-04-17 on the Firecrawl-Alternatives pilot.

**Stub detection:** `title == url` OR `title` is itself a URL string (NotebookLM often blanks `url` to `None` on failed ingest while keeping the original URL as the title), confirmed by `source content` returning `NOT_FOUND` or < 500 chars.

**Recovery ladder** (first tier ≥ `MIN_RECOVERED_CHARS=800` wins):

1. **Tier 1 — Firecrawl markdown** via `https://firecrawl-api.global-dpo.com/v1/scrape` (`formats: ["markdown"]`). Handles HTML and many `.docx`/`.pdf` URLs (Firecrawl extracts text from binaries server-side). Note: `formats: ["pdf"]` is **not** supported on this deployment — markdown only.
2. **Tier 2 — `curl_cffi` browser GET** with `impersonate="chrome"`, then `bs4` chrome-stripping → `markdownify`. Bypasses many JA3/Cloudflare/WAF gates that block Firecrawl. Cleans nav/footer/script/aside tags + class-based pruning *within* the chosen `<main>`/`<article>` (never at document level — wrapper classes like `mw-header` would nuke everything).
3. **Tier 3 — Playwright Chromium** reusing the `nlm` cookie jar (`C:/Users/user2/.notebooklm-mcp-cli/profiles/default/cookies.json`, converted to Playwright's `add_cookies()` schema). Headless, JS-rendered, supports both:
   - **PDF URLs** → downloaded via `context.request.get` → saved to `sources/{slug}/{url-slug}.pdf` → uploaded as a file source. HEAD-probe first; if HEAD lies (some servers return non-PDF content-type), late-detect on the actual GET response and switch to PDF-download mode.
   - **JS-rendered HTML** → real `page.goto(..., wait_until="domcontentloaded")` + `wait_for_load_state("networkidle", timeout=12s)`, then the same `bs4`/`markdownify` pipeline as tier 2.

   Serialized via `D:/NotebookLM/.locks/nlm_chromium.lock` to prevent collisions with in-flight `nlm login`. Lock format: `<pid>|<iso-utc>|source_doctor`. Stale locks (dead PID via OS portable check — `OpenProcess` on Windows, `os.kill(pid, 0)` on POSIX) are auto-cleared. Default wait: 120s.
4. **Tier 4 — Quarantine.** Append the URL + tier-failure trace to `sources/{slug}/_unrecoverable.md` (table format; auto-headered on first append).

On per-stub success the script: saves the markdown to `sources/{slug}/{url-slug}.md` with a provenance header, uploads via `nlm source add --file --title`, deletes the stub via `nlm source delete --confirm` (per [feedback memory](../../../projects/D--NotebookLM/memory/feedback_failed_source_recovery_delete.md)), and runs `sync_notion_sources.py touch` once at the end.

**Mandatory after every `research_import`** that imports any URL sources — adds `source_doctor.py` as the closing step of the deep-research workflow. (See [research-workflow.md](research-workflow.md).)

### Manual path (fallback)

If the script can't help (e.g. a one-off URL the notebook never tried to ingest, or an authenticated page where you have a session cookie), do it by hand:

```bash
# 1. Fetch via Firecrawl directly (or use WebFetch as a Claude-tool fallback)
curl -s -X POST https://firecrawl-api.global-dpo.com/v1/scrape \
  -H "Authorization: Bearer $FIRECRAWL_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"url":"<url>","formats":["markdown"]}' | jq -r '.data.markdown' \
  > sources/{slug}/{page-slug}.md

# 2. Upload as a file source (preserves UTF-8 + spares shell escaping)
nlm source add <notebook-id> --file sources/{slug}/{page-slug}.md --title "Recovered: {Title}"

# 3. Mandatory touch
python D:/NotebookLM/scripts/sync_notion_sources.py touch --notebook <short-id>
```

Use `--text` only for content too small to deserve a file on disk; otherwise `--file` is more reliable on Windows (no shell quoting headaches).

## Dedup by URL

Deep research sometimes imports near-duplicate URLs (same article, different domains). The sync script can flag these:

```bash
# Dry-run — lists duplicates without deleting
python scripts/sync_notion_sources.py dedupe --notebook <short-id>

# Destructive — actually delete via nlm source delete
python scripts/sync_notion_sources.py dedupe --notebook <short-id> --confirm-dedupe
```

Duplicates are identified by normalized URL within the same notebook. The script keeps the oldest (lowest source_id) and deletes the rest.

For single-source manual delete:
```bash
nlm source delete <source-id> --confirm
# Then touch:
python scripts/sync_notion_sources.py touch --notebook <short-id>
```

## Corpus Cleanup / Dedup Pass

Per-import curation (single-task or multi-task Haiku filtering before `research_import`) catches obvious duplicates *within* a single discovery cycle. It does not catch **cross-cycle** duplicates that accumulate when you run iterative multi-pass discovery — the same URL, or an equivalent landing-page-vs-PDF pair, can land in C1 and again in C4 under a different refined angle. Nor does it deduplicate vendor-summary blog posts against their canonical primary source.

This section covers the notebook-wide cleanup sweep.

### When to run

- **Mandatory** — closing step after any iterative discovery series that ran **more than 2 cycles** (C3+). By the time the third cycle lands, cross-cycle duplicate density is near-certain and materially pollutes citations in later `notebook_query` calls and the generated artifacts.
- **On-demand** — invoke when:
  - the user asks for a cleanup,
  - `nlm source list` shows obvious dup clusters (same title with different URLs, or page + PDF for the same official doc),
  - before a final artifact-generation pass and you want clean citations,
  - or a research-queue entry explicitly flags "dedup needed".
- **Skip** for 1–2-cycle series unless inspection shows dup density — per-import curation is usually sufficient.

### Steps

1. **URL-normalized dedup.** Run the built-in script first — it catches trivial same-URL duplicates:
   ```bash
   # Windows
   python D:/NotebookLM/scripts/sync_notion_sources.py dedupe --notebook <short-id>                      # dry-run
   python D:/NotebookLM/scripts/sync_notion_sources.py dedupe --notebook <short-id> --confirm-dedupe     # destructive
   # WSL
   python3 /mnt/d/NotebookLM/scripts/sync_notion_sources.py dedupe --notebook <short-id>
   python3 /mnt/d/NotebookLM/scripts/sync_notion_sources.py dedupe --notebook <short-id> --confirm-dedupe
   ```
   Keeps the oldest (lowest source_id) per normalized URL.

2. **Manual landing-page vs canonical-PDF sweep.** `nlm source list <nb-id> --full` and scan for pairs where one row is an HTML landing page and another is the canonical PDF of the same publication (EDPB, EC, GDPR regulator pages, vendor whitepapers, academic preprint-and-PDF pairs, etc.).

   **Default policy — PDF-primary.** For official regulator / vendor publications:
   - **Keep** the canonical PDF. It has the authoritative text, stable citation anchors, and is what reviewers expect to see cited.
   - **Drop** the landing page by default.
   - **Exception: keep the page too** only if it adds *distinct structured value* that isn't in the PDF:
     - updates/changelog surfaced on the page but not restated in the PDF,
     - translation switcher or official alternative-language pointers,
     - related-docs navigation (linked implementing acts, opinions, guidelines) that frames the PDF in context,
     - interactive tables / version matrices rendered on the page.
   - If the page is just a link-to-PDF chrome with the same abstract, drop it.

   How to check quickly: `source describe <source-id>` for both rows and diff the content sections — if the page's sections are a strict subset of the PDF's, drop the page.

3. **Vendor summaries vs primary sources.** If a vendor recap / blog explainer of an official doc is in the notebook and the official primary source is also in, drop the vendor summary unless it adds original analysis the curating agent deemed valuable. Judgment call, not a hard rule.

4. **Quarantine trace cleanup.** Grep `sources/{slug}/_unrecoverable.md` for any URLs that got re-added to the notebook via a different path (e.g., manual Firecrawl, user-supplied PDF). Delete the quarantine entry to keep the trace honest.

5. **Destructive delete sweep.** Fire a batched `source_delete` for every row identified in steps 2–4.

6. **Mandatory touch at the end** — single call scopes the Notion sync to this notebook:
   ```bash
   python D:/NotebookLM/scripts/sync_notion_sources.py touch --notebook <short-id>
   # or python3 /mnt/d/NotebookLM/... on WSL
   ```

### Heuristic for the landing/PDF pair decision (agent stable rule)

PDF wins by default. Page wins only if `source describe` output lists **at least one content section** that is not present in the PDF. Ties break to PDF. If you're genuinely unsure after inspecting both, keep the PDF and drop the page — you can always re-add the page later, but a polluted citation stream is harder to untangle mid-deliverable.

## Rename

```bash
nlm source rename <source-id> "New Title" --notebook <notebook-id>
# or MCP:
source_rename(notebook_id="...", source_id="...", new_title="...")
```

Followed by touch.

## Listing

```bash
nlm source list <nb-id>                # table
nlm source list <nb-id> --full         # full detail
nlm source list <nb-id> --json         # for parsing
nlm source list <nb-id> --drive        # Drive sources with freshness
nlm source list <nb-id> --drive -S     # skip freshness checks (faster)
```

## Enrichment (AI summary + keywords)

```bash
# Populate AI Summary, Keywords, Char Count, page-body markdown in Notion
python scripts/sync_notion_sources.py enrich --notebook <short-id>
```

This calls `nlm source describe` + `nlm source content` per source and writes structured output to the Notion Sources DB. Rate-limited to ~1 req/sec to respect NotebookLM's limits.
