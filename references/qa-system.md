# QA gates

Pass every gate before packaging.

## Editorial

- The audience, promise, and CTA are clear.
- Slide 2 works without slide 1 and pulls into slide 3.
- Every factual claim is supported, qualified, or removed.
- The final CTA is unique to the last slide.

## Visual

- Every slide is 1080×1350 PNG and remains readable at 320×400.
- The cover headline dominates and has no CTA chip.
- Text is intentional, correctly spelled, and not clipped.
- Images are high quality, correctly cropped, and useful to the lesson.
- The slides feel like one system without becoming repetitive.

## Delivery

- Inspect final pixels and the contact sheet.
- Include `caption.md`, `package.md`, and `qa-report.json` with `{"passed": true}` only after the checks pass.
- Package with `scripts/package_run.py`, then validate the resulting ZIP.
