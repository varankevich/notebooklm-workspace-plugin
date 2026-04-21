---
description: Build a brand-aligned slide deck using the narrative-first pipeline
argument-hint: [topic] [--brand <name>] [--skip-refinement]
allowed-tools:
  - Read
  - Write
  - Glob
  - Grep
  - Bash
  - Agent
  - ScheduleWakeup
  - mcp__notebooklm-mcp__notebook_create
  - mcp__notebooklm-mcp__source_add
  - mcp__notebooklm-mcp__studio_create
  - mcp__notebooklm-mcp__studio_status
  - mcp__notebooklm-mcp__download_artifact
  - mcp__notebooklm-mcp__source_describe
---

# /build-deck

Build a brand-aligned slide deck from an idea using the narrative-first pipeline. Invokes the `slide-pipeline` skill.

## Arguments

- **topic** (required) — the deck topic, e.g., "Claude Code for enterprise developers"
- `--brand <name>` (optional) — brand guide name. Looks up `D:/NotebookLM/brand-guides/<name>.md`. Defaults to the bundled `example-brand.md` (Dark Editorial).
- `--skip-refinement` (optional) — skip the Gemini visual refinement step (step 4). Useful when `GEMINI_API_KEY` is unset or when you want NotebookLM output as-is.

## What this command does

Orchestrates the full 7-step narrative-first pipeline from `slide-pipeline.md`:

1. **Narrative** — spawn `narrative-crafter` sub-agent (persona at `agents/narrative-crafter.md`). Runs conversational discovery with the user; produces 500–1500 word prose at `D:/NotebookLM/slides/{slug}/narrative.md`.
2. **Brand context** — load `D:/NotebookLM/brand-guides/{brand}.md` or fallback to `example-brand.md`.
3. **Slide generation** —
   - `notebook_create("Deck: {topic}")` → `nb_id`
   - `source_add(file=narrative.md)` → wait for READY
   - `studio_create(artifact_type=slide_deck, confirm=True)` → `artifact_id` (PDF)
   - `studio_create(artifact_type=slide_deck, format=pptx, confirm=True)` → `artifact_id_pptx`
   - Poll `studio_status` until complete (see `reference-tables.md` — 5–15 min)
   - `download_artifact` for both PDF and PPTX
4. **Visual refinement** (optional, gated on `GEMINI_API_KEY` + not `--skip-refinement`):
   - Extract raw slides as PNGs via `pdftoppm`
   - For each slide, call `assets/generate_image.py` with prompt derived from `prompts/visual-refinement-templates.md` + brand values
5. **CD review** — spawn `creative-director` sub-agent with brand guide + slide PNGs + `prompts/cd-review-prompt.md` (Standard Review variant). Save verdict to `cd-review.md`.
6. **Iteration** — if fail, re-refine flagged slides. Cap at 3 iterations; surface to user if still failing.
7. **Notion upload** — PostToolUse hook already fires on `download_artifact`; run `sync_notion_assets.py --sync` explicitly if refined slides were assembled into new files.

## Default behavior

- Slug derived from topic: lowercase, hyphens, strip non-alphanumerics.
- Output folder: `D:/NotebookLM/slides/{slug}/`
- If `GEMINI_API_KEY` is unset AND `--skip-refinement` is not passed: warn, then skip refinement.
- If no brand guide specified AND user's brand-guides/ folder is empty: prompt user to pick `example-brand.md` or customize first.

## Examples

```
/build-deck "Claude Code features for developers"
/build-deck "Q2 product roadmap" --brand acme-corp
/build-deck "GDPR Article 6 primer for DPOs" --skip-refinement
```

## See also

- Skill: [`slide-pipeline`](../skills/slide-pipeline/SKILL.md)
- Full procedure: [`slide-pipeline.md`](../skills/notebooklm-workspace/references/slide-pipeline.md)
- Timing + autonomy: [`reference-tables.md`](../skills/notebooklm-workspace/references/reference-tables.md)
