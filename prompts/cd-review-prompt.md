# Creative Director Review Prompt

Use this prompt (or a variation) when asking the creative director agent to review slides.

## Standard Review Prompt

```
Review these [N] slides against the [Brand Name] brand system.

Brand system reference: [path to brand guide or inline summary]

For each slide:
1. What's working — specific elements that are strong
2. What needs attention — core issues, be direct
3. Direction for next iteration — actionable, with specific values
   (hex colors, px measurements, font weights)

Then provide cross-slide consistency notes:
- Are headlines consistent across slides?
- Are margins and grid alignment consistent?
- Are accent treatments applied uniformly?
- Does the deck tell a cohesive visual story?

Prioritize the 3 most impactful issues per slide.
```

## Quick Check Prompt (for iterations)

```
Quick review of the updated slides against [Brand Name] brand system.
Focus on:
1. Were the previous round's issues addressed?
2. Any new issues introduced?
3. Pass/fail — ready to ship or needs another round?
```

## Final Sign-Off Prompt

```
Final creative review of the complete deck against [Brand Name] brand system.
This is the ship/no-ship decision.

Check:
- [ ] Typography consistent across all slides
- [ ] Color palette compliance — no off-brand colors
- [ ] Layout grid consistent — margins, alignment, spacing
- [ ] Accent treatments uniform — same weight, color, placement
- [ ] Readability — works projected, on screen, and at thumbnail size
- [ ] Brand compliance — would this pass a brand team review?

Verdict: Ship / Ship with notes / Needs another round
```
