---
name: carousel-os
description: Create complete, posting-ready Instagram or LinkedIn carousels from a user-provided topic, source material, or brief, or by proposing an original topic when none is supplied. Use when a user asks to make, write, design, render, package, or revise a social-media carousel or slide post.
---

# Carousel OS

Create a complete carousel that is useful, visually distinct, fact-checked when necessary, and ready to post. Accept the user's supplied topic, source material, brand guidance, copy, or assets. If no topic is supplied, propose and select one original, audience-appropriate topic; never depend on a private idea library.

## Load the production context

Read these references before producing a carousel:

- `references/design-system.md` — default visual language and customization rules
- `references/editorial-system.md` — story, copy, research, and caption rules
- `references/qa-system.md` — production gates and delivery checklist
- `references/runbook.md` — production sequence, recovery, and packaging
- `config/tokens.json` — canvas and default visual tokens

Use `templates/carousel.json` as the editable slide-spec starting point. Use the renderer and packaging scripts instead of creating a redundant renderer.

## Input and ownership

Treat a request to make a carousel as permission to produce the full in-scope package once. Prefer the user's topic, supplied copy, sources, visual references, and brand system over this skill's defaults. Ask only when a missing choice materially changes the intended message or violates a stated brand rule.

When no topic is provided, choose an original, useful topic from the user's stated audience or niche. Do not scan, reserve, modify, or rely on any external content ledger, inspiration folder, social account, or previous-post archive unless the user explicitly provides it.

## Production contract

Deliver 5–9 slides at 1080×1350, normally seven:

- a text-led cover with a clear promise and no CTA chip;
- a standalone second-slide hook that makes sense when seen independently;
- focused teaching slides with one clear job each;
- one saveable framework, checklist, or recap where suitable;
- a final CTA slide only;
- a caption, sources/claim ledger where facts are used, contact sheet, QA report, package note, and ZIP.

Keep the language, captions, and CTA in the user's requested language and voice. Do not impose a regional dialect or code-switching pattern.

## Images and rendering

For generated or edited images, first identify the host agent:

- **Codex:** use the built-in native image-generation capability. No API key setup is needed.
- **Any other agent:** before generating or editing an image, tell the user that this workflow requires an OpenAI API key available to the agent as `OPENAI_API_KEY` in order to call **GPT Image 2** (`gpt-image-2`). Check only whether the key is available; never print, request in chat, or expose its value. If it is unavailable, pause image generation and provide the exact setup requirement. Continue with copy, layout, and non-image work where possible.

Generate cover art without text, then add the exact final title with `scripts/overlay_title.py`. Do not use image-generated typography as final copy.

Use generated imagery only when it communicates the lesson better than type, cards, screenshots, or a diagram. Keep the image subordinate to a readable headline and inspect every final slide at full size and thumbnail size.

Render with:

```bash
python3 scripts/render_carousel.py templates/carousel.json --out output/my-carousel
```

## Workflow

1. Define the audience, one promise, desired action, and source material. Build a claim ledger before writing factual claims.
2. Create the story arc: cover, independent hook, teaching sequence, saveable synthesis, and final CTA.
3. Art-direct a text-free cover base using the default design system or the user's brand system. Generate multiple distinct concepts when imagery is needed.
4. Choose the strongest concept, add the exact title overlay, and create the slide spec.
5. Render the slides and contact sheet. Inspect legibility, hierarchy, crop, factual support, and CTA placement.
6. Fix and rerender until every gate in `references/qa-system.md` passes.
7. Add `caption.md`, `package.md`, `qa-report.json`, and optional `sources.md` to the run folder, then package it with `scripts/package_run.py`.

## Non-negotiables

- Do not invent facts, statistics, testimonials, or source citations. Browse for time-sensitive claims and soften or remove unsupported claims.
- Do not place a CTA on the cover or teaching slides; reserve it for the final slide and caption.
- Do not make slide 2 ordinary setup copy. Give it independent context, a different hook mechanism, and an open loop into slide 3.
- Do not copy a reference creator's visual identity. Use references for direction, then make a distinct composition and metaphor.
- Do not claim completion based only on file existence. Inspect pixels, copy, source support, and package integrity.

## Final response

Lead with the completed carousel. Show the contact sheet and link the output folder and ZIP. State the topic, audience, CTA/keyword, and only material limitations or assumptions.
