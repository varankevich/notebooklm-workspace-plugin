---
name: slide-pipeline
description: Build brand-aligned slide decks using a narrative-first pipeline — idea → prose narrative → NotebookLM slides → optional Gemini visual refinement → Creative Director review. Activates on "build a deck", "make a presentation", "create slides about X", "/build-deck", "/slide-pipeline".
---

# Slide Pipeline (Narrative-First)

Turns an idea into a brand-aligned presentation by forcing a narrative-first flow: prose story before slide structure. Produces noticeably better decks than ad-hoc slide generation because NotebookLM structures its output around the argument in the narrative.

Uses our existing `nlm` CLI, Notion Tracker, and cross-platform workspace paths. No new CLI dependency.

## When to use this skill

- User wants to build a presentation/deck from scratch
- User has an idea but no narrative yet
- Intent phrases: "build a deck about…", "make slides on…", "create a presentation", "design a deck"
- Explicit: `/build-deck` or `/slide-pipeline`

**Don't use this skill for:**
- Regenerating slides on an existing notebook (use the standard asset-pipeline from `notebooklm-workspace` skill)
- Quick one-off slide revision (use `studio_revise`)
- Non-deck artifact generation (audio, video, infographic)

## Quick workflow

See [../notebooklm-workspace/references/slide-pipeline.md](../notebooklm-workspace/references/slide-pipeline.md) for the full procedure. Summary:

1. **Narrative** — spawn `narrative-crafter` sub-agent, produce `D:/NotebookLM/slides/{slug}/narrative.md`
2. **Brand** — use user's brand guide at `D:/NotebookLM/brand-guides/{name}.md` or the bundled `example-brand.md`
3. **NotebookLM** — `nlm slides create` + `nlm download slide-deck` (PDF and PPTX)
4. **Visual refinement** (optional, gated on `GEMINI_API_KEY`) — per-slide Gemini edits via `generate_image.py`
5. **CD review** — spawn `creative-director` sub-agent with brand guide + slides, iterate
6. **Upload** — PostToolUse hook auto-syncs to Notion Assets DB

## Rules

- **Always narrative first.** Never feed raw URLs directly to slide generation without a narrative pass. If user has only bullet points or a rough outline, route through `narrative-crafter` first.
- **Cap CD iterations at 3.** If slides still fail on round 3, the root cause is usually the narrative or the brand guide — not the slides. Surface to user.
- **Gate visual refinement.** Check `GEMINI_API_KEY` before step 4. Skip cleanly if unset; pipeline still delivers value without it.
- **Brand guide must be concrete.** Hex codes, fonts, measurements. If the user's brand guide is vague ("modern, clean, trustworthy"), offer `example-brand.md` as a structural template to fill in.
- **PDF-primary.** NotebookLM exports PDF by default and PPTX with `-f pptx`. Generate both when possible — PDF for delivery, PPTX for editing.

## Files in this plugin you'll reference

| Path | Purpose |
|------|---------|
| `agents/narrative-crafter.md` | Persona for sub-agent that interviews the user and drafts prose |
| `agents/creative-director.md` | Persona for sub-agent that reviews slides vs. brand |
| `prompts/visual-refinement-templates.md` | Gemini prompts per slide role (title/section/data/etc.) |
| `prompts/cd-review-prompt.md` | Standard / quick-check / final-signoff CD review prompts |
| `brand-guides/example-brand.md` | Default brand guide (Dark Editorial) |
| `assets/generate_image.py` | Gemini image wrapper (optional — requires `GEMINI_API_KEY`) |

## Entry points

- Slash command: `/build-deck "<topic>" [--brand <name>] [--skip-refinement]`
- See `commands/build-deck.md` for the command definition.

## Pairing

- Always used alongside `notebooklm-workspace` skill (for asset pipeline + Notion sync).
- Always used alongside `nlm-skill` (for CLI syntax).
