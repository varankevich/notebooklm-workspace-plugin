# Visual Refinement Prompt Templates

Tested prompts for Nano Banana Pro (Gemini image model) slide generation. Replace `[bracketed]` values with your specifics.

## General Rules

- Always specify `--resolution 2K --aspect-ratio 16:9` for presentation slides
- Include your brand colors as hex values in every prompt
- Mention "flat matte style, no glow effects" to avoid common AI image artifacts
- Reference "editorial" and "Swiss grid" for clean, professional results
- Be specific about typography: font style, weight, size relationships

---

## Title Slide

```
Executive presentation title slide. Dark [background color] background.
Large serif headline '[Your Title].' in [headline color] with elegant
[font name] style typography. Period at the end.
Subtitle below in lighter sans-serif: '[subtitle text]'.
[Accent treatment — e.g., "Small amber hand-drawn underline beneath
the word '[keyword]'."]
Corner registration marks in thin gray lines.
Bottom left: '[attribution]'.
Clean Swiss grid layout, editorial magazine quality.
Flat matte style, no glow effects, no gradients. 16:9 presentation slide.
```

## Section Divider

```
Executive presentation section divider slide. [Background color] background.
Top-left small label: '[section number] [SECTION NAME]' in small caps,
muted gray.
Center: a minimal [icon description] icon in [accent color], line art,
[size]px.
Large centered serif headline: '[Section Title].' with '[keyword]' in
italic serif.
Subtitle centered below: '[subtitle]' in muted gray sans-serif.
Generous whitespace. Corner registration marks.
Flat matte, editorial, Swiss grid. No glow. 16:9 presentation slide.
```

## Data / Statistic Slide

```
Executive presentation data slide. [Background color] background.
Title top left: '[Title].' in [headline font] serif.
Large hero statistic centered: '[number]%' in [accent color],
[size estimate] scale, bold.
Supporting text below the number: '[context for the stat]' in
[text color] sans-serif.
[Optional: thin horizontal rule in accent color separating title
from content.]
Clean, minimal, lots of negative space. The number is the star.
Flat matte, editorial, no glow. 16:9 presentation slide.
```

## Comparison / Before-After Slide

```
Executive presentation comparison slide. [Background color] background.
Title top left: '[Title].' in serif.
Two horizontal stacked bars:
Top bar labeled '[Label A]': [description of fill, color, and text content].
Bottom bar labeled '[Label B]': [description of fill, color, and text content].
[Accent treatment — e.g., "Hand-drawn [accent color] circle around
'[key element]' to highlight the insight."]
Clean infographic style, flat fills only (no patterns unless specified),
high contrast. Swiss grid alignment.
No glow, no gradients. 16:9 presentation slide.
```

## Diagram / Architecture Slide

```
Executive presentation diagram slide. [Background color] background.
Title at top left: '[Title].' in serif.
[Number] columns/sections showing [concept]:
- '[Column 1 name]' with [icon description] icon
- '[Column 2 name]' with [icon description] icon
- '[Column 3 name]' with [icon description] icon
Each column has a short description beneath the heading.
Icons are minimal line art in [accent color or neutral tone].
[Optional: thin horizontal rule or accent mark separating title
from content.]
Swiss grid, editorial. Consistent spacing between columns.
Flat matte, no glow. 16:9 presentation slide.
```

## Process / Pipeline Flow Slide

```
Executive presentation process slide. [Background color] background.
Title top left: '[Title].' in serif.
Horizontal flow diagram with [number] steps:
[Step 1 label] → [Step 2 label] → [Step 3 label]
Each step is a clean geometric box with [accent color] connecting
arrows or lines. Step labels inside boxes in [text color].
Short description below each box in muted gray.
Left to right reading flow. Generous spacing between steps.
Flat matte, editorial, Swiss grid. No glow. 16:9 presentation slide.
```

## Closing / Manifesto Slide

```
Executive presentation closing slide. [Background color] background.
Large centered serif headline: '[Closing statement].' with '[keyword]'
emphasized with a [accent treatment — e.g., "hand-drawn amber underline"].
Below in smaller muted gray sans-serif: '[supporting statement]'.
Generous whitespace — this slide should feel contemplative and spacious.
Corner registration marks.
Minimal, editorial quality. Flat matte, no glow.
16:9 presentation slide.
```

---

## Editing Existing Slides

When refining a NotebookLM slide (using `-i` flag to pass the original):

```
Refine this presentation slide to match [brand name] brand system:
- Background: [exact hex]
- Headlines: [font style] serif, [color]
- Body text: [font style] sans-serif, [color]
- Accent: [accent color] used for [specific treatments]
- Layout: Swiss grid, [margin]px margins
- Keep the same content and structure but apply the brand typography,
  colors, and spacing.
- Remove any [unwanted elements — gradients, glow, stock imagery, etc.]
- Add [brand elements — corner marks, accent marks, etc.]
Flat matte editorial style. 16:9.
```

## Tips

1. **Be redundant about style.** Say "flat matte, no glow" in every prompt. AI models forget.
2. **Specify what NOT to do.** "No gradients, no stock photos, no 3D effects" prevents common issues.
3. **Use the edit flag for refinement.** Passing the original slide via `-i` preserves layout structure.
4. **Include exact hex values.** Don't say "dark blue" — say "#0A0A0A".
5. **Describe typography relationships.** "Headline 3x larger than body" is more useful than absolute sizes.
