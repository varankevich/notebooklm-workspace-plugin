# Asset Pipeline

Generate → download → Notion upload flow. Load when the task involves creating or retrieving audio, video, slides, or infographics.

## Asset Type → Folder → Notion Mapping

Filename extension + parent folder determines the Notion `Asset Type` select value:

| Folder | Extensions | Asset Type select | CLI default |
|--------|-----------|-------------------|-------------|
| `audio/{slug}/` | `.mp3`, `.wav`, `.m4a` | **Audio** | `.m4a` |
| `video/{slug}/` | `.mp4`, `.webm`, `.mov` | **Video** | `.mp4` |
| `infographics/{slug}/` | `.png`, `.jpg`, `.jpeg` | **Infographic** | `.png` |
| `slides/{slug}/` | `.pdf` | **Slides — PDF** | `.pdf` |
| `slides/{slug}/` | `.pptx` | **Slides — PPTX** | (pass `-f pptx`) |

Before any download, ensure the folder exists: `mkdir -p "D:/NotebookLM/{type}/{slug}"`.

## Generating Artifacts

All generation commands require `--confirm` (CLI) or `confirm=True` (MCP). See `nlm-skill` for full syntax; listing here only the most-used project patterns.

### One-shot generate + upload (recommended)

For a single artifact, use the workspace's generate helper:

```bash
python scripts/sync_notion_assets.py generate \
    --notebook <slug> \
    --type audio \
    --focus "Target audience: DPOs. Focus: GDPR Article 6 implications. Length: medium."
```

Type choices: `audio` | `video` | `infographic` | `slides-pdf` | `slides-pptx`.

Flow inside `generate`:
1. Creates Notion row with `Status = Generating`
2. Calls `nlm <type> create --focus ...`
3. Polls `studio_status` every 15s (up to 20 min)
4. On completion, downloads via URL-first or binary upload (see below)
5. Sets `Status = Uploaded`

Flags:
- `--local-copy` — opt-in: keep local archive after successful URL upload (default: Notion pulls from Google CDN, no local bytes)
- `--binary-upload` — force binary path (skip URL-first)

### Batch generation (across notebooks)

```bash
python scripts/sync_notion_assets.py generate-batch \
    --type audio \
    --active-only \
    --focus "Quarterly summary, 10-minute brief"
    # --dry-run is default; add --confirm to execute
```

Filters: `--notebooks id1,id2`, `--active-only`, `--category <cat>`, `--tag <tag>`.

## Downloading Existing Artifacts

### CLI direct download

```bash
mkdir -p "D:/NotebookLM/audio/{slug}"
nlm download audio <nb-id> --output "D:/NotebookLM/audio/{slug}/overview.mp3"

nlm download video <nb-id> --output "D:/NotebookLM/video/{slug}/overview.mp4"

nlm download slide-deck <nb-id> --output "D:/NotebookLM/slides/{slug}/deck.pdf"
nlm download slide-deck <nb-id> --output "D:/NotebookLM/slides/{slug}/deck.pptx" --format pptx

nlm download report <nb-id> --output report.md
nlm download quiz <nb-id> --output quiz.json --format json
```

Infographic download is only available via MCP:
```
download_artifact(artifact_type="infographic", notebook_id="...", output_path="D:/NotebookLM/infographics/{slug}/overview.png")
```

With `NOTION_SYNC=1`, the PostToolUse hook fires after `download_artifact` and automatically runs `sync_notion_assets.py --sync` to reconcile rows.

### Audio status codes (important!)

Internal `status_code` from `client._list_raw()`:
- `1` = generating
- `2` = CDN not ready (partial) — **audio downloads return HTTP 404** at this stage
- `3` = fully downloadable

Always wait for `status_code == 3` before downloading audio. Slides can sometimes download at `status_code 2` via `nlm download slide-deck`, but expect intermittent HTTP errors on `contribution.usercontent.google.com` — retry with exponential backoff (3 tries).

### Bulk backfill — `pull-existing`

Discover artifacts already in NotebookLM (from prior sessions) and sync to Notion:

```bash
# One notebook
python scripts/sync_notion_assets.py pull-existing --notebook <slug>

# ALL notebooks (paginated, covers all 200+)
python scripts/sync_notion_assets.py pull-existing

# Only active notebooks
python scripts/sync_notion_assets.py pull-existing --active-only

# By category / tag (requires these set in Notion)
python scripts/sync_notion_assets.py pull-existing --category "Tech / Infrastructure"
python scripts/sync_notion_assets.py pull-existing --tag research

# Force re-download even if local file exists
python scripts/sync_notion_assets.py pull-existing --force-download
```

**Artifact type coverage:** `pull-existing` handles `audio`, `video`, `infographic`, `slide_deck`. Types `report`, `data_table`, `quiz` have no CLI download support and are skipped. `failed`-status artifacts are automatically skipped.

## URL-First vs Binary Upload (Notion)

For each artifact, the script tries `import_external_url` first (Notion pulls from Google CDN — zero local bandwidth), falling back to `curl_cffi` binary upload.

**URL compatibility:**
- Audio / infographic URLs are `lh3.googleusercontent.com/notebooklm/...` → public, works with Notion's fetch.
- Slide-deck URLs are `contribution.usercontent.google.com/download?...` → require Google auth, fail Notion's server-side fetch with 400.

`_extract_artifact_url()` returns `None` for slides, so slides go straight to binary upload. For audio/infographic, URL-first succeeds ~95% of the time.

### Binary upload (fallback)

`notion_files.py` uses `curl_cffi` with Chrome TLS impersonation (`impersonate="chrome"`) — required because Notion's `/v1/file_uploads/{id}/send` is Cloudflare-JA3-protected. Standard `requests` fails with 403.

- Files ≤ 20 MiB → single-part (one POST)
- Files > 20 MiB → multi-part (create with `mode=multi_part`, send 10 MiB chunks, complete)

Max file size on paid Notion workspaces: 5 GiB.

### Rate-limited direct CDN download

When downloading from `lh3.googleusercontent.com` (audio, infographic), `_download_direct()` uses chunked `urllib` with 3 retries + exponential backoff, optionally rate-capped by the `DOWNLOAD_RATE_LIMIT_KBPS` env var (0 or unset = full speed).

Slides remain CLI-only because their URL requires Google auth.

## Scan + Catchup

For reconciling local files and Notion rows:

```bash
# Walk audio/video/slides/infographics folders, create/upload rows for every file
python scripts/sync_notion_assets.py scan

# Transition "Generating" rows whose local file now exists
python scripts/sync_notion_assets.py catchup

# Both in one pass
python scripts/sync_notion_assets.py --sync
```

`scan` respects the `Slug` property — if a folder has no matching notebook slug in Notion, the scan prints `[scan] skip: no notebook with slug=X` and moves on. First create the Notebooks row (with the correct `Slug`), then rerun scan.

## Common Pitfalls

- **Duplicate rows from scan** — fixed by `_stored_path()` helper; all reads/writes go through one canonical form (ROOT-relative, forward slashes). Don't hand-write `str(path)` — use the helper.
- **Notion file upload fails with 403 Cloudflare** — you're using stock `requests`. Switch to `curl_cffi` with `impersonate="chrome"`.
- **URL-first upload fails 400 on slides** — expected; falls through to binary. Don't add retries at the URL layer.
- **Windows rename race** on re-download — `os.remove(path)` before calling `client.download_*()` if file already exists (NotebookLM client errors on existing file).
