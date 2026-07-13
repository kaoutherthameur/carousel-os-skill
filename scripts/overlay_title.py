#!/usr/bin/env python3
"""Apply an exact mixed-language cover title without changing the image.

This is the primary title path. It preserves the base pixels and never adds a
CTA. Lines are supplied explicitly so the orchestrator owns spelling and line
breaks.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps


SCRIPT = Path(__file__).resolve()
ROOT = SCRIPT.parent.parent
VENDOR = SCRIPT.parent / "vendor"
if VENDOR.exists():
    sys.path.insert(0, str(VENDOR))

W, H = 1080, 1350
LATIN_FONTS = [
    Path("/System/Library/Fonts/Helvetica.ttc"),
    Path("/System/Library/Fonts/Supplemental/Arial.ttf"),
    Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
]
ARABIC_FONTS = [
    Path("/System/Library/Fonts/Supplemental/Arial Unicode.ttf"),
    Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
]
CLOUD = "#F3F7FF"
INK = "#071A36"
ACCENT = "#FF5C35"


def has_arabic(text: str) -> bool:
    return any("\u0600" <= char <= "\u06ff" or "\u0750" <= char <= "\u077f" for char in text)


def display(text: str) -> str:
    if not has_arabic(text):
        return text
    import arabic_reshaper
    from bidi.algorithm import get_display

    return get_display(arabic_reshaper.reshape(text))


def font_for(text: str, size: int) -> ImageFont.FreeTypeFont:
    paths = ARABIC_FONTS if has_arabic(text) else LATIN_FONTS
    for path in paths:
        if not path.exists():
            continue
        try:
            return ImageFont.truetype(str(path), size)
        except Exception:
            continue
    return ImageFont.load_default()


def measure(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont) -> tuple[int, int, int]:
    box = draw.textbbox((0, 0), display(text), font=font)
    return box[2] - box[0], box[3] - box[1], box[1]


def fit_font(draw: ImageDraw.ImageDraw, text: str, max_width: int, preferred: int) -> ImageFont.FreeTypeFont:
    size = preferred
    while size >= 54:
        font = font_for(text, size)
        if measure(draw, text, font)[0] <= max_width:
            return font
        size -= 4
    return font_for(text, 54)


def visual_runs(text: str) -> list[tuple[str, ImageFont.FreeTypeFont | None]]:
    """Return visual-order script runs; fonts are assigned later at one size."""
    # Keep a purely Arabic line as one bidi unit. Splitting it word-by-word and
    # then drawing those words from left to right reverses the sentence order.
    if has_arabic(text) and not re.search(r"[A-Za-z0-9]", text):
        return [(text, None)]
    parts = [part.strip() for part in re.split(r"([\u0600-\u06ff\u0750-\u077f]+)", text) if part.strip()]
    if has_arabic(text) and any(not has_arabic(part) and part.strip() for part in parts):
        parts.reverse()
    return [(part, None) for part in parts]


def line_metrics(draw: ImageDraw.ImageDraw, text: str, size: int) -> tuple[int, int, list[tuple[str, ImageFont.FreeTypeFont]]]:
    runs: list[tuple[str, ImageFont.FreeTypeFont]] = []
    width = 0
    height = 0
    for part, _ in visual_runs(text):
        if runs:
            width += max(10, size // 7)
        font = font_for(part, size)
        rendered = display(part) if has_arabic(part) else part
        box = draw.textbbox((0, 0), rendered, font=font)
        width += box[2] - box[0]
        height = max(height, box[3] - box[1])
        runs.append((part, font))
    return width, height, runs


def fit_line(draw: ImageDraw.ImageDraw, text: str, max_width: int, preferred: int) -> tuple[int, int, list[tuple[str, ImageFont.FreeTypeFont]]]:
    size = preferred
    hard_min = 104 if has_arabic(text) else 88
    while size >= hard_min:
        width, height, runs = line_metrics(draw, text, size)
        if width <= max_width:
            return width, height, runs
        size -= 4
    return line_metrics(draw, text, hard_min)


def draw_wordmark(draw: ImageDraw.ImageDraw, color: str) -> None:
    lines = [("CAROUSEL", 25, 52), ("OS", 34, 81)]
    for text, size, y in lines:
        font = font_for(text, size)
        width, height, top = measure(draw, text, font)
        draw.text(((W - width) / 2, y - top), text, font=font, fill=color)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--line", action="append", required=True, help="Exact title line; repeat for multiple lines")
    parser.add_argument("--zone", choices=["left", "right", "center"], default="left")
    parser.add_argument("--y", type=int, default=270)
    parser.add_argument("--max-width", type=int, default=650)
    parser.add_argument("--size", type=int, default=164)
    parser.add_argument("--line-gap", type=int, default=16)
    parser.add_argument("--color", default=CLOUD)
    parser.add_argument("--stroke", type=int, default=0)
    parser.add_argument("--stroke-color", default=INK)
    parser.add_argument("--underline", action="store_true")
    parser.add_argument("--wordmark", action="store_true")
    parser.add_argument("--wordmark-color", default=CLOUD)
    args = parser.parse_args()

    source = Image.open(args.image).convert("RGB")
    image = source.copy() if source.size == (W, H) else ImageOps.fit(source, (W, H), Image.Resampling.LANCZOS)
    draw = ImageDraw.Draw(image)
    if args.wordmark:
        draw_wordmark(draw, args.wordmark_color)

    y = args.y
    line_boxes: list[tuple[float, float, float, float]] = []
    for text in args.line:
        width, height, runs = fit_line(draw, text, args.max_width, args.size)
        if args.zone == "left":
            x = 72
        elif args.zone == "right":
            x = W - 72 - width
        else:
            x = (W - width) / 2
        cursor = x
        for part, font in runs:
            if cursor > x:
                cursor += max(10, font.size // 7)
            rendered = display(part) if has_arabic(part) else part
            box = draw.textbbox((0, 0), rendered, font=font)
            run_width = box[2] - box[0]
            draw.text(
                (cursor, y - box[1]),
                rendered,
                font=font,
                fill=args.color,
                stroke_width=args.stroke,
                stroke_fill=args.stroke_color,
            )
            cursor += run_width
        line_boxes.append((x, y, x + width, y + height))
        y += height + args.line_gap

    if args.underline and line_boxes:
        x1, _, x2, y2 = line_boxes[-1]
        width = min(150, x2 - x1)
        if args.zone == "right":
            x1 = x2 - width
        elif args.zone == "center":
            x1 = (x1 + x2 - width) / 2
        draw.rounded_rectangle((x1, y2 + 18, x1 + width, y2 + 26), radius=4, fill=ACCENT)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    image.save(args.out, format="PNG", optimize=True)
    print(args.out.resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
