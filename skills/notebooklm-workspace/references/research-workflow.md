# Research Workflow

Source discovery, platform targeting, the mandatory curation sub-agent, import. Load when starting a research task or importing discovered sources.

## Workflow Overview

Multi-cycle discovery is the **default**, not an advanced pattern. One cycle of fast-mode queries always leaves gaps — narrow aspects not targeted, tools that only appear in comparison articles never directly queried, pricing pages not surfaced, setup guides for specific combos missing. Run a gap-analysis pass after the first import and, if the notebook's own answer surfaces material gaps, fire a second parallel fast-mode cycle targeting them. Continue until the stop conditions below are met.

### Single discovery
```
1. research_start(mode="fast")   → task_id (capture it)
2. research_status                → poll until status=completed
3. CURATE                         → haiku sub-agent filters sources (MANDATORY for >5 sources)
4. research_import                → only approved indices
5. SOURCE DOCTOR                  → python D:/NotebookLM/scripts/source_doctor.py --notebook <short-id>
6. GAP ANALYSIS (mandatory)       → notebook_query: "What important aspects of <topic> are NOT
                                     well covered by the current sources? List specific tools,
                                     pricing tiers, setup scenarios, or comparisons that are absent."
                                    → If material gaps: launch cycle 2 (parallel fast-mode on the
                                      gap angles, same pattern as cycle 1 — curate, import, source_doctor).
                                    → Loop until a stop condition below is met.
7. touch                          → ONLY if step 5 was skipped (e.g. no URL sources imported)
8. Update research-queue.md       → status: running → done
```

### Multi-aspect discovery (parallel)
```
1. Analyze aspects → classify broad vs narrow (see below)
2. research_start × N (all parallel, mode="fast")  → N task_ids
3. Poll all task_ids in parallel (max_wait=0 snapshots, ~30–60s cycles)
4. CURATE all tasks in one Haiku call (cross-task dedup)
5. research_import × N (all parallel, approved indices per task)
6. SOURCE DOCTOR → python D:/NotebookLM/scripts/source_doctor.py --notebook <short-id>
7. GAP ANALYSIS (mandatory, run concurrently with cycle-2 planning)
   → notebook_query asking what's under-covered. Fire the follow-up queries for gap angles in
     parallel (fast mode, same multi-aspect pattern), not sequentially. Curate, import, source_doctor.
   → Loop until a stop condition below is met.
```

### Stop conditions (apply to all research tasks)

Stop adding cycles when any of these hold:
- Two consecutive gap queries return essentially the same answer — the notebook's own understanding has stabilized.
- Pro source budget > 240/300 (80% of the per-notebook limit) — stop and, if synthesis is needed, run one `mode="deep"` task for a deep_report only.
- All per-request approval rates from the latest cycle are below 50% — nothing still warm to refine (see [Iterative Fast-Mode Discovery](#iterative-fast-mode-discovery-edge-cases-and-tracking) for per-query exhaustion tracking).

## Starting Research

**`mode="fast"` is the default for all source discovery.** Use `mode="deep"` only for a single standalone discovery where maximum source volume matters and per-query traceability doesn't. Never use `mode="deep"` for parallel multi-query batches — the backend merges concurrent deep jobs into ~4 bulk tasks, destroying the task_id → query mapping and losing per-dimension traceability.

```bash
nlm research start "query" --notebook-id <id> --mode fast
# Modes: fast (~30s, ~10 sources), deep (~5min, ~40–90 sources, web only)
# --source drive : search Drive instead of web
```

```
# MCP:
research_start(query="...", notebook_id="...", mode="fast", source="web")
```

When starting research:
1. Add a row to `research-queue.md` Active table with `task_id = <from response>, status = running`
2. Log a `- [ ]` action item in the current session (memory compiler captures it)

### Prior completed-but-not-imported tasks block new starts

If `research_start` aborts with a pending-task error on a notebook, it's because a previous research task on that notebook reached `completed` status without ever being imported. During iterative multi-pass discovery this is almost always the state — you import in curated batches across multiple tasks, not one-at-a-time as they complete. Re-issue with `--force`:

```bash
nlm research start "query" --notebook-id <id> --mode fast --force
```

MCP equivalent: pass `force=True` to `research_start`.

**Do not "clean up" by deleting the pending task.** Its sources are still curatable in the next cycle, and deleting them throws away any Haiku curation work you already did. The `--force` flag is the correct handling, not a workaround.

## Platform Targeting — Critical

When the user asks for sources from a specific platform (YouTube, Reddit, GitHub, Hacker News, etc.), **embed the platform name in the query text**. Never manually look up or paste URLs from those platforms.

**Correct:**
```bash
research_start(
    query="Claude Code tutorial YouTube Reddit community tips 2026",
    mode="deep"
)
```

NotebookLM's engine uses the query to rank results and will prioritize pages from named platforms. Confirmed by 2026-04-15 session: YouTube-targeted query returned YouTube tutorials + creator channel pages in the result set.

**Wrong:**
- Calling `source_add(source_type="url", url="https://youtube.com/watch?v=<guessed-id>")`
- Adding Reddit search pages or subreddit listing pages as URL sources (these fail — dynamic pages)

**Rule:** The platform name in the query is the signal. The research engine does the URL discovery. This is also the mechanism for **source type scoping** in multi-aspect discovery — there is no native filter; the constraint lives entirely in the query string.

## Multi-Aspect Discovery Pattern

Use when building a notebook on a topic with multiple facets (e.g., a product feature with pricing, setup, use cases, community discussion). The goal is granular, per-dimension sources that stay attributable back to their query.

### Step 1 — Classify aspects: broad vs narrow

Before writing queries, decide which aspects warrant separate per-source-type coverage and which are too thin.

| Broad → 1 discovery per source type | Narrow → combine or run universal |
|--------------------------------------|-----------------------------------|
| Setup / getting started | Pricing + Models (factual, official-only) |
| Use cases & real workflows | Very niche features (e.g. agent handover) |
| Feature-rich topics (e.g. autofill) | Conditions + Triggers (combine into one) |
| Conditions + triggers (if substantial) | |

**Rule:** an aspect is broad if official docs, Reddit, and YouTube each add meaningfully different signal. Narrow aspects produce thin, overlapping results per source type — combine them into one query or make them universal (no site: scope).

### Step 2 — Build the query matrix

For each broad aspect × source type, embed the platform name in the query:

```
"Notion Custom Agent setup site:notion.so"
"Notion Custom Agent setup site:reddit.com"
"Notion Custom Agent setup tutorial site:youtube.com 2024 2025"
```

For narrow/combined aspects, one universal query without a site: constraint:

```
"Notion Custom Agent pricing AI models plans 2025"
"Notion Custom Agent handover multi-agent coordination"
```

Always `mode="fast"`. Expect ~10 sources per query, each with its own distinct task_id.

### Step 3 — Launch all in parallel

Fire all `research_start` calls in a single tool-call batch. Capture every task_id from the responses.

### Step 4 — Poll all task_ids in parallel

Use `max_wait=0` (single snapshot, non-blocking) and poll all task_ids simultaneously. Fast tasks complete in ~30s. Schedule wakeup at 60–90s intervals — typically all done within 2 cycles.

### Step 5 — Multi-task curation with Haiku

Spawn **one** Haiku agent with ALL task source lists compiled. Key rules:

- **Skip deep_report entries** (index 0, `result_type_name = "deep_report"`) — only appear in deep-mode tasks; these are AI-synthesized, not original sources
- **Deduplicate across tasks** — if a URL appears in multiple tasks, approve it only in the first task where it appears
- **Pass compact metadata only**: `{index, url, title, description}` — strip the `report` field entirely. Deep reports can be 5K+ tokens each; omitting them keeps Haiku context under ~15K tokens for a 14-task batch
- **Output**: approved indices keyed per task_id

Example Haiku prompt structure for multi-task curation:

```
You are curating research sources for a NotebookLM notebook on: <TOPIC>.
There are <N> completed research tasks. Select the best indices to import
from each task, avoiding duplicates across tasks and filtering noise.

Rules:
- Skip index 0 in any task where result_type_name = "deep_report"
- If a URL appears in multiple tasks, approve it only in the FIRST task listing it
- Skip: non-English pages, empty/blank descriptions, academic papers unrelated to topic,
  generic listicles, promotional content, localized duplicate pages
- Prefer: official vendor docs, community discussions on the exact topic,
  recent tutorials (2024–2026), platform-specific content matching the query's site: scope

No per-source-type quotas. Evaluate every source — YouTube videos, Reddit threads, GitHub
repos, vendor blogs, official docs, PDFs, conference talks — on the same authority /
relevance / dedup criteria. Do NOT impose numeric caps by platform (e.g. "max 2 YouTube
videos", "at most 3 Reddit posts") unless the user explicitly supplied them in THIS prompt.
The query already encoded platform intent by naming the platform in the query text; curation
must not re-filter the platform mix. A YouTube tutorial that directly answers the query is
as keepable as a vendor doc; a vendor blog full of promotional fluff is as rejectable as a
low-effort Reddit post.

Tasks and sources:
## Task <task_id_1> (<N> sources, query: "<query>"):
<index>: <url> — <title> — <description>
...

## Task <task_id_2> ...

Output ONLY this format, one line per task:
<task_id_1>: 1,2,4,7,9
<task_id_2>: 0,3,5,6
...
```

### Step 6 — Import all in parallel

Fire all `research_import` calls simultaneously — no need to sequence them.

```
# MCP (all in one tool-call batch):
research_import(notebook_id="...", task_id="<task_id_1>", source_indices=[1,2,4,7,9])
research_import(notebook_id="...", task_id="<task_id_2>", source_indices=[0,3,5,6])
...
```

### Step 7 — Source doctor

```bash
python D:/NotebookLM/scripts/source_doctor.py --notebook <short-id>
```

Recovers any failed-ingest stubs across all imported sources and runs `touch` internally.

## Polling Status

```bash
nlm research status <nb-id>                    # blocks up to 5 min
nlm research status <nb-id> --max-wait 0       # single check
nlm research status <nb-id> --task-id <tid>    # specific task
nlm research status <nb-id> --full             # full source list
```

```
# MCP:
research_status(notebook_id="...", task_id="...", compact=False)
# compact=True truncates report + limits sources shown; compact=False gets everything
```

For deep tasks with >10 sources, call `compact=False` when ready to curate so you get the full source array.

## Curation — MANDATORY for Any Research Import

**Rule:** NEVER call `research_import` with no `source_indices` on any task returning >5 sources. Research returns 10–90 sources; typically 30–50% are low-value (promotional, tangential, near-duplicates, or descriptions that admit no relevance). Importing them pollutes the notebook and burns the Pro 300-source budget.

For multi-task batches, use the multi-aspect pattern above (single Haiku call, cross-task dedup). For single-task imports, use the prompt below.

### How to curate (single task)

Spawn a sub-agent via the `Agent` tool with `model: "haiku"`. Haiku handles this well because:
- Deterministic heuristic task, short context, no tool use beyond file I/O
- ~$0.02 per curation vs ~$0.30 for sonnet
- Finishes in ~10 seconds for a 40-source list

Write only the compact source array (`index, url, title, description` — no `report` field) to `/tmp/research_sources.json`, then hand the agent the path. Stripping the report field is important: deep reports are 3K–8K tokens each and add no curation signal.

### Sub-agent prompt template (single task)

```
You are a source-curation agent for a NotebookLM research workflow. The notebook is about: <ONE-SENTENCE TOPIC>.

Read the JSON at `/tmp/research_sources.json`. It contains a `sources` array with fields {index, url, title, description, result_type_name}.

# Keep a source if ALL of these hold:
- Directly relevant to at least one sub-question in the research query
- Authoritative for the topic (official docs > research papers > specific technical blogs > vendor docs for adjacent products)
- Not a near-duplicate of another kept source (prefer more authoritative / more specific)
- Description is non-empty OR title strongly suggests relevance

# Skip unconditionally:
- Index 0 if result_type_name = "deep_report" — this is an AI-synthesized report, not an original source

# Reject a source if ANY of these hold:
- Description explicitly says it has no relevant info ("Contains no information regarding X")
- Promotional / chatbot / lead-gen content with no technical depth
- Beginner overview when the query needs advanced info, AND we already have authoritative sources on that topic
- Generic "top N AI tools" listicles with no implementation detail
- Unrelated products tangentially mentioning the query topic
- NPM/package pages that don't address the specific question
- Near-duplicate of a higher-authority source already kept

# Tie-breakers: prefer official vendor docs, prefer issues/PRs on the exact error,
# prefer 2025-2026 content, prefer detailed long-form over brief.

# No per-source-type quotas. Evaluate YouTube videos, Reddit threads, GitHub repos, vendor
# blogs, official docs, PDFs, and conference talks on the same keep/reject criteria above.
# Do NOT impose numeric caps by platform (e.g. "max 2 YouTube videos", "at most 3 Reddit
# posts") unless the user explicitly supplied such a cap in THIS prompt. The research query
# already encoded platform intent by naming the platform in the query text; curation must
# not re-filter the platform mix. A YouTube tutorial that directly answers the query is as
# keepable as a vendor doc; a promotional vendor blog is as rejectable as a low-effort
# Reddit post. Judge each source on authority + relevance + non-duplication, never on
# "we have enough of that source type already."

Research query: """<ORIGINAL QUERY>"""

# Output — ONLY a single valid JSON object written to `/tmp/curation_result.json`, no prose, no markdown fences:
{
  "keep":   [<sorted integer indices to keep, must include 0 if present>],
  "reject": [<sorted integer indices to reject>],
  "summary": "<one-sentence overall — e.g. 'Kept 22 / rejected 22.'>"
}

Target: keep 30–60% of the sources. When in doubt on a borderline source, reject it — we can always add more manually. Write the JSON file, then print only a one-line summary.
```

### After curation

Read `/tmp/curation_result.json`:
```bash
cat /tmp/curation_result.json
```

Then import only the approved indices:
```bash
# MCP:
research_import(
    notebook_id="...",
    task_id="...",
    source_indices=[0, 1, 3, 5, 7, ...],  # from curation_result.keep
    timeout=600                             # increase for >50 sources
)

# CLI:
nlm research import <nb-id> <task-id> --indices 0,1,3,5,7,... --timeout 600
```

Then run `source_doctor` (mandatory closing step — recovers any failed-ingest URL stubs and runs `touch` internally):
```bash
python D:/NotebookLM/scripts/source_doctor.py --notebook <short-id>
```

If `source_doctor` was skipped (e.g. you only imported non-URL sources), run `touch` standalone:
```bash
python D:/NotebookLM/scripts/sync_notion_sources.py touch --notebook <short-id>
```

Update `research-queue.md`: status `running` → `done`, move to Completed.

## Answering the original request after the corpus is complete

Once the notebook has been built out (fast-mode cycles exhausted per-request, optional deep-research synthesis imported, artifacts generated if requested), the user typically wants a comprehensive answer to their **original** research question — incorporating any gap-query insights surfaced along the way. Don't issue one monolithic query: NotebookLM's tool-result size is dominated by the citations/references payload (each cited source appears with `cited_text`, sometimes including full `cited_table` rows). A single comprehensive query against a 90+-source notebook reliably exceeds the output cap even when the answer text itself is small.

### Partition the deliverable, not the question

Start by deriving the outline of what the final deliverable will look like — this depends entirely on what the user asked, not on a fixed template. **Let the shape of the answer drive the shape of the query batch, not the other way around.** Common task shapes and how they naturally partition:

| Task type | Typical outline → sub-query partition |
|---|---|
| Tool / solution evaluation | Candidates by category → recommendation → ops concerns → failure modes → gaps |
| Literature / state-of-the-art review | Major schools of thought → key works per school → consensus vs. contested → gaps |
| Comparison of N options | Each option in depth → head-to-head matrix → verdict by use case → gaps |
| Investigation / incident / post-mortem | Timeline → contributing factors → root cause → impact → mitigations → prevention |
| Market / competitive analysis | Segment overview → top players per segment → trends → threats/opportunities → outlook |
| How-to / procedural guide | Prerequisites → steps → variations by environment → gotchas → verification |
| Person / entity / institution | Background → major phases or roles → body of work → reception/impact → open questions |
| Concept primer | Definition + history → mechanisms → variations → applications → misconceptions → frontier |
| Policy / legal question | Jurisdictions → statutes/precedents → tests/factors → application → exceptions → reform debate |
| Medical / scientific condition | Pathophysiology → presentation → diagnostics → treatment → prognosis → research frontier |

If the task doesn't cleanly match one of these, compose the outline from first principles — headings of ~500–1000 words each.

Target 6–10 sub-queries, each producing one outline heading.

### Query-shape invariants (apply regardless of topic)

- Constrain output explicitly: "TABLE ONLY, one-line cells" when the section is a matrix; explicit word budget ("~600 words") otherwise.
- "Bracketed citation numbers only — do not quote source paragraphs." This is the single biggest lever for keeping the references payload tractable.
- Pass through any session-scoped scope exclusions established earlier in the session ("Do NOT include topic X — out of scope for this notebook"). See Rule 7.
- Reuse the same `conversation_id` across sub-queries so NotebookLM accumulates shared context and you don't re-establish grounding each time.

### Always include a final "gap" sub-query

Regardless of domain, end with:

> "What is NOT well-covered by the current sources? Enumerate 3–5 gaps where a shipping-before-action decision would need more research. Be specific about what's thick vs. thin in the corpus."

This catches risk items that a confident final answer would otherwise paper over, and it's equally valuable for a tool evaluation, a medical primer, or a market analysis.

### Assemble inline in outline order

After all sub-queries return, stitch their answers into a single Markdown deliverable ordered by the outline derived in step 1. Deduplicate claims that appear in multiple sections — keep each in its most natural home. The canonical order is whatever the outline produced, not a fixed template.

### Precedent

**2026-04-17 Firecrawl-Alternatives pilot.** A single monolithic query against a 94-source notebook covering 26 candidates × 12 criteria + archetypes + six operational sections returned 96,130 characters and exceeded the cap. A compact single-table retry with 13 cloud-API rows + two trailing paragraphs returned 85,004 characters and still exceeded. The final successful pattern was 8 sub-queries: three candidate tables by category (HTML-to-MD libs; cloud scraping APIs; self-hosted engines + PDF tools), one for archetypes + top-pick stack, three operational-concerns queries grouped thematically, one for failure modes + gaps. Each sub-answer fit under the cap; the assembled deliverable covered the full scope. The specific partitioning axes (candidates / archetypes / ops / failure-modes) were task-type-specific — a literature review or market analysis would partition along different axes drawn from its own outline.

## Iterative Fast-Mode Discovery — Edge Cases and Tracking

The multi-cycle loop itself is covered in the [Workflow Overview](#workflow-overview) — that's the default path for every research task: cycle → gap query → next cycle → stop condition. This section covers the advanced tracking and edge-case handling that becomes relevant once you're on cycle 3+. Precedent: 2026-04-17 Firecrawl-Alternatives pilot, 94 curated sources across 5 cycles + 1 synthesis deep task.

### Exhaustion is per-request, not per-cycle

Each `research_start` task has its own approval rate. A cycle is a bag of heterogeneous queries — its aggregate rate averages warm and cold topics together and hides the signal. **Track and decide per query.**

**Rule:** a query is *exhausted* when THAT query's Haiku-approval rate drops below 50%. When you launch the next cycle, drop only the exhausted queries; keep running the ones still at ≥50% with refined angles (see below).

**Pilot evidence (don't misread aggregates):**
- C1 aggregate 58%. Per-query: Jina 40% (exhausted), Crawl4AI-vs-Firecrawl 70%, Trafilatura 70%, Turndown-mailto 50%, PDF-Tika 60%. Five separate signals.
- C3 aggregate 30% looked like "stop everything" — but only because all five queries in that bundle happened to be the ones that exhausted. The *method* didn't fail; the batch composition did.
- C4 (refined angles on still-warm topics + gap queries): 77% aggregate, 50–90% per task. All 14 queries stayed warm.
- C5: 74/90 = 82% aggregate, 70–90% per task. All 9 warm.

### Gap-query cadence — after every cycle starting with C2

After each cycle's imports land, before launching the next cycle, run a `notebook_query` against the notebook itself asking what's under-covered. Use the answer to seed new queries for cycle N+1 alongside the per-request continuations. This surfaces shipping-blockers the original query matrix missed.

**Timing — run the gap query in parallel with cycle N's polling, not after it.** Notebook queries hit existing sources (already imported from C1…N-1); they don't depend on C(N)'s results. Fire `notebook_query` concurrently with the cycle-N `research_status` polls; by the time cycle N imports land, the gap analysis is ready to shape cycle N+1.

**Re-run the gap query every cycle, even with similar wording.** The notebook content changes between cycles, so the AI answer changes too. On the pilot, the post-C4 gap query (at 69 sources) surfaced six concrete shipping-blocker topics (K8s Playwright memory leaks, Notion image S3 hosting, DOM-drift observability, fallback router architecture, incremental content-hash dedup, AST list flattening) that the original 15-query matrix missed. Each of those yielded 70–90% approval in C5.

### Refined angles, not repeat keywords

When a topic is still warm (≥50%) and you want more from it in the next cycle, re-query with a **different slice**, not the same keywords. NotebookLM's web engine returns near-identical result sets for identical queries — you'll re-import what you already have. Change the angle.

| Cycle | Angle for "Crawl4AI" |
|-------|----------------------|
| C1 | `Crawl4AI vs Firecrawl markdown web scraping comparison self-hosted open source` |
| C4 | `Crawl4AI fit_markdown content filter PruningContentFilter BM25 production case study 2025` |
| C5 | `Crawl4AI production memory leak FastAPI docker OOM fix workaround browser context pool concurrent` |

Each angle is the same topic, different slice: architectural overview → configuration internals → operational failure mode. All three produced >80% approval, with ~90% novel URLs.

### Synthesis deep task after stop

Once a stop condition from the [Workflow Overview](#stop-conditions-apply-to-all-research-tasks) fires, launch one `mode="deep"` task with a comprehensive query to produce a synthesizing deep_report, curate it hard (dedupe against everything already imported; expect ~50% novel), import the novel fraction, and move to artifact generation.

### After the series stops — corpus cleanup

If the series ran **more than 2 cycles** (C3+), cross-cycle duplicates have almost certainly accumulated — the same URL re-imported under a different refined angle, or a landing page from C1 sitting alongside the canonical PDF that landed in C4. Per-import curation doesn't catch these; it only sees one task at a time.

Run the [**Corpus Cleanup** workflow](source-ops.md#corpus-cleanup--dedup-pass) in source-ops.md before moving to artifact generation or final `notebook_query` deliverables. It covers URL-normalized dedup, the landing-page-vs-PDF sweep (policy: PDF-primary), vendor-summary removal, and the closing `touch`.

For 1–2-cycle series, corpus cleanup is optional. Run it if `nlm source list` shows obvious dup density (e.g. multiple titles that read as variants of the same publication) or before a citation-sensitive final deliverable; otherwise the per-import curation was enough.

### Scope exclusions are session-scoped

When the user says "topic X was resolved in another notebook, exclude it from this one" (or establishes this at notebook creation), treat it as a session-scoped rejection filter, not a one-off edit:

1. Add a `scope_excludes:` list to the curation prompt for every subsequent Haiku call in this session. Haiku rejects any source whose primary topic matches.
2. Scan already-imported sources; batch `source_delete` any whose title/description indicates they're exclusively about topic X.
3. Re-run the gap query after deletion so future gap analysis doesn't re-surface X as a missing topic.

The pilot instance: mid-C5, user said Notion block/char-limit sources belonged in another notebook. 15 already-imported sources matched and needed deletion; three incoming C5 sources (indices 2/3/4 on the mdast task) were rejected by Haiku using the updated prompt.

### Task-ID aliasing caveat (platform-side bug)

When a fast-mode `research_start` is launched close in time to a running deep-mode task, the NotebookLM backend can alias the fast task_id to the deep task's source pool on `research_import`. Symptom: `research_status` for the fast task_id returns sources that match your query, but `research_import` with those indices ends up importing sources from the concurrent deep task.

**Mitigation:**
- If `research_import`'s `imported_sources` titles don't match your `research_status` snapshot for that task, retry once with the canonical `task_id` from the status response (deep mode often re-issues task_ids mid-flight).
- If the retry still mismatches, accept the orphan: re-launch that one query alone (not in a parallel batch) and import separately. The isolated call doesn't collide.

Observed 2026-04-17 on a Shadow-DOM fast task launched while the Firecrawl deep task was finalizing; the fast task's 10 Shadow-DOM sources never imported despite two attempts, and the emerging-tools content got double-imported instead.

## Precedent

- **2026-04-15**: 44-source Notion-upload deep task curated by haiku to 22 keeps in 10s (task `5393f811`). Rejected 15 generic Cloudflare-bypass blogs, promotional chatbot content, unrelated NPM packages, and one explicitly-empty source (`docs.readwise.io/llms.txt` — description "Contains no information regarding X").
- **2026-04-15 (later)**: 93-source AI-skill-design deep task curated to 55 keeps. Rejected paywalled articles with no descriptions, unrelated SaaS listicles, consumer chatbot tricks.

## Research Queue Integration

Local file `research-queue.md` is bidirectionally synced with the 🔬 Research Tasks Notion DB.

```bash
# Pull new Requested tasks from Notion
python scripts/sync_notion_research.py --pull

# Push local status to Notion
python scripts/sync_notion_research.py --push

# Both
python scripts/sync_notion_research.py --sync
```

**Status flow:**
```
Notion: Requested → Queued — Local → Running → Importing → Done
                                        ↓
                                     Failed / Cancelled
```

Matching logic: by `Task ID` when present, otherwise by `Query` text + `Notebook` name.

### Adding a task in Notion

1. Open 🔬 Research Tasks DB → Intake Queue view → `+ New`
2. Fill: Query (title), Notebook (relation), Mode (fast/deep), Priority (High/Med/Low)
3. Status auto-defaults to `Requested`
4. Next `--pull` syncs it to `research-queue.md`
