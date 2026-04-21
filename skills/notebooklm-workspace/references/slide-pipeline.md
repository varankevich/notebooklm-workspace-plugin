# Narrative-First Slide Pipeline

Produces brand-aligned decks from a prose narrative (not bullet points). Adapted from `Jason-Cyr/openclaw-slide-pipeline` (MIT) to use our `nlm` CLI, Notion Tracker, and cross-platform workspace paths.

Load when the task is building a presentation or slide deck from scratch (not just regenerating slides on an existing notebook).

## Philosophy

- **Narrative first.** A 500–1500 word prose document is the source. NotebookLM generates dramatically better slides from narrative than from raw URLs or bullet lists.
- **Argument, not summary.** Every deck argues *for something*. The narrative identifies the claim, evidence, and turning point.
- **Brand as a constraint.** Pass slides through a Creative Director sub-agent loaded with a brand guide. Iterate until compliant.

## Pipeline

```
Idea → Narrative (sub-agent) → NotebookLM slides → [optional visual refinement] → CD review → Notion upload
```

## Workflow

### 1. Narrative — spawn `narrative-crafter` sub-agent

```
Agent(
    description="Craft presentation narrative",
    subagent_type="general-purpose",
    model="haiku",
    prompt="""
Load persona from:
~/.claude/plugins/notebooklm-workspace-plugin/agents/narrative-crafter.md

Run Discovery (3 questions) and Story Architecture (4 questions) phases.
Then draft 500-1500 words of prose narrative.

Topic: {user_topic}
Audience: {if known, else ask}
Desired outcome: {if known, else ask}

Save output to: D:/NotebookLM/slides/{slug}/narrative.md
Use output format specified in the persona (# title, ## type, ---, prose, ---, ## metadata).

When done, return: {path_to_narrative, metadata_block}.
"""
)
```

The sub-agent runs conversationally with the user through this session's Agent interface. Narrative lands at `D:/NotebookLM/slides/{slug}/narrative.md`.

### 2. Brand context

```bash
# Check for user's brand guide
ls D:/NotebookLM/brand-guides/
```

If `D:/NotebookLM/brand-guides/{brand}.md` exists, use it. Otherwise:
- Use bundled `~/.claude/plugins/notebooklm-workspace-plugin/brand-guides/example-brand.md` (Dark Editorial)
- Optionally: ask if user wants to customize it first — copy to `D:/NotebookLM/brand-guides/mine.md` and edit

### 3. NotebookLM slide generation

```bash
# Ensure target folder
mkdir -p "D:/NotebookLM/slides/{slug}"

# Create notebook if not already created
nlm notebook create "Deck: {name}" --json

# Add narrative as source
nlm source add <nb-id> --file "D:/NotebookLM/slides/{slug}/narrative.md" --title "Narrative" --json

# Wait for ingest (see reference-tables.md: Source processing 30s–10min)
# Poll source_list until status=READY

# Generate slides (both formats in parallel)
nlm slides create <nb-id> --confirm --json              # returns artifact_id for PDF
nlm slides create <nb-id> --format pptx --confirm --json  # editable PPTX

# Poll studio_status until complete (see reference-tables.md: Slides 5–15min)
# Download
nlm download slide-deck <nb-id> --output "D:/NotebookLM/slides/{slug}/deck.pdf"
nlm download slide-deck <nb-id> --format pptx --output "D:/NotebookLM/slides/{slug}/deck.pptx"
```

PostToolUse hook fires on `download_artifact` and auto-syncs Notion Assets rows (`Slides — PDF`, `Slides — PPTX`).

### 4. Visual refinement (OPTIONAL — requires `GEMINI_API_KEY`)

Skip entirely if `GEMINI_API_KEY` is unset. The pipeline still produces value with just NotebookLM slides + CD review.

If enabled:

```bash
# Extract each slide as PNG from the PDF (use pdftoppm or similar)
pdftoppm -png -r 300 "D:/NotebookLM/slides/{slug}/deck.pdf" "D:/NotebookLM/slides/{slug}/raw/slide"

# For each slide, call generate_image.py with an edit prompt derived from
# visual-refinement-templates.md + brand guide
python ~/.claude/plugins/notebooklm-workspace-plugin/assets/generate_image.py \
  --prompt "<edit-prompt>" \
  -i "D:/NotebookLM/slides/{slug}/raw/slide-01.png" \
  --filename "D:/NotebookLM/slides/{slug}/refined/slide-01.png" \
  --resolution 2K --aspect-ratio 16:9
```

Prompt construction: load `~/.claude/plugins/notebooklm-workspace-plugin/prompts/visual-refinement-templates.md`; pick the template matching the slide role (title/section/data/etc.); fill in brand-guide values.

### 5. Creative Director review — spawn sub-agent

```
Agent(
    description="CD brand review of slide deck",
    subagent_type="general-purpose",
    prompt="""
Load persona from:
~/.claude/plugins/notebooklm-workspace-plugin/agents/creative-director.md

Load brand guide from:
{brand_guide_path}

Load review prompt template from:
~/.claude/plugins/notebooklm-workspace-plugin/prompts/cd-review-prompt.md
Use the 'Standard Review Prompt' variant.

Slides to review: {list of PNG paths, either raw/ or refined/}

Return structured review:
- Per-slide: What's Working / What Needs Attention / Direction for Next Iteration
- Cross-slide consistency notes
- Top 3 prioritized issues
- Pass/fail verdict
"""
)
```

Save review to `D:/NotebookLM/slides/{slug}/cd-review.md`.

### 6. Iteration (if fail)

For each flagged slide, re-run refinement (step 4) with the CD's specific direction as the prompt. Usually 1 iteration resolves things. Cap at 3 iterations; if still failing, surface to user.

Use "Quick Check Prompt" from `cd-review-prompt.md` for iteration rounds (faster than full review).

### 7. Final delivery — upload to Notion

```bash
# Re-run scan/catchup to ensure all new files are uploaded as Assets rows
python D:/NotebookLM/scripts/sync_notion_assets.py --sync
```

If refined slides exist, they go into `D:/NotebookLM/slides/{slug}/refined/` and get uploaded as additional Asset rows (type `Slides — PDF` or `Infographic` depending on how you package them — PDF-assemble the refined PNGs first for a single-row upload).

Final artifacts in `D:/NotebookLM/slides/{slug}/`:
- `narrative.md` — the story
- `deck.pdf` / `deck.pptx` — NotebookLM output
- `raw/slide-NN.png` — extracted raw slides (if refinement enabled)
- `refined/slide-NN.png` — refined slides (if refinement enabled)
- `cd-review.md` — Creative Director verdict

## Sub-Skill Entry Points

- Slash command: `/build-deck "<topic>" [--brand <name>] [--skip-refinement]`
- Intent trigger: "build a deck about…", "make slides about…", "create a presentation on…"
- Manual: invoke the `slide-pipeline` skill directly

## Common Pitfalls

- **Starting with bullet points instead of narrative.** Slides will look like bullet points. Always run narrative-crafter first unless the user already has 500+ words of prose.
- **Using a brand guide that's all vibes.** The CD agent needs concrete hex codes, fonts, and measurements. If the user's brand guide is vague, offer to use `example-brand.md` as a structural template.
- **Running visual refinement without `GEMINI_API_KEY`.** `generate_image.py` will fail loudly. Check env first; skip step 4 if unset.
- **Iterating CD review more than 3 times.** If the deck still fails on round 3, the problem is usually either the narrative (unclear argument) or the brand guide (self-contradictory) — not the slides. Surface to user.
- **Forgetting Notion upload.** The PostToolUse hook fires on `download_artifact`, which covers the initial PDF/PPTX. Refined slides assembled into new files still need `sync_notion_assets.py --sync` explicitly.
