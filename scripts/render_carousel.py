#!/usr/bin/env python3
"""Render a schema-driven social-media carousel to 1080x1350 PNGs.

The cover is treated as a finished artifact: it is copied pixel-for-pixel when
already 1080x1350, otherwise it is cropped once to fit. No CTA, logo, gradient,
or other mark is added to it. The final CTA belongs on its own slide.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any, Iterable

from PIL import Image, ImageDraw, ImageFont, ImageOps


SCRIPT = Path(__file__).resolve()
OS_ROOT = SCRIPT.parent.parent
WORKSPACE = OS_ROOT.parent
VENDOR = SCRIPT.parent / "vendor"
if VENDOR.exists():
    sys.path.insert(0, str(VENDOR))
DEFAULT_SCHEMA = OS_ROOT / "schemas" / "carousel.schema.json"
W, H = 1080, 1350

DEFAULTS: dict[str, Any] = {
    "canvas": {"width": W, "height": H},
    "colors": {
        "porcelain": "#F3F7FF",
        "ink": "#071A36",
        "copper": "#FF5C35",
        "slate": "#60738D",
        "lime": "#48C6EF",
        "plum": "#101820",
        "cobalt": "#48C6EF",
        "white": "#FFFFFF",
        "soft": "#DCEBFA"
    },
    "brand": {"handle": "@yourhandle", "wordmark": ["CAROUSEL", "OS"]},
    "fonts": {}
}


def deep_merge(base: dict[str, Any], update: dict[str, Any]) -> dict[str, Any]:
    result = dict(base)
    for key, value in update.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def discover_tokens(explicit: Path | None) -> Path | None:
    candidates = [
        explicit,
        OS_ROOT / "config" / "tokens.json",
        OS_ROOT / "config" / "brand-tokens.json",
        OS_ROOT / "assets" / "tokens.json",
        OS_ROOT / "references" / "tokens.json",
    ]
    return next((p for p in candidates if p and p.exists()), None)


def load_tokens(path: Path | None) -> dict[str, Any]:
    tokens = DEFAULTS
    found = discover_tokens(path)
    if found:
        tokens = deep_merge(tokens, json.loads(found.read_text(encoding="utf-8")))
    # The OS config uses descriptive public names; rendering code keeps short
    # aliases for legibility. Accept both so the config remains the source of
    # truth without coupling it to Python implementation details.
    palette = tokens.get("colors", {})
    aliases = {
        "porcelain": "cloud_white",
        "ink": "midnight_navy",
        "copper": "coral_punch",
        "slate": "slate_blue",
        "lime": "sky_signal",
        "plum": "ink_black",
        "cobalt": "sky_signal",
    }
    for short, public in aliases.items():
        if public in palette:
            palette[short] = palette[public]
    palette.setdefault("white", "#FFFFFF")
    palette.setdefault("soft", "#E8E2D8")
    brand = tokens.setdefault("brand", {})
    if "account" in brand:
        brand["handle"] = brand["account"]
    if "wordmark_lines" in brand:
        brand["wordmark"] = brand["wordmark_lines"]
    canvas = tokens.get("canvas", {})
    if int(canvas.get("width", W)) != W or int(canvas.get("height", H)) != H:
        raise ValueError("Carousel canvas must remain 1080x1350")
    return tokens


def resolve_path(raw: str | Path, spec_dir: Path) -> Path:
    p = Path(raw).expanduser()
    return p if p.is_absolute() else (spec_dir / p).resolve()


def validate_document(doc: dict[str, Any], schema_path: Path) -> None:
    try:
        import jsonschema  # type: ignore
    except ImportError:
        if not isinstance(doc.get("metadata"), dict) or not doc["metadata"].get("topic"):
            raise ValueError("metadata.topic is required")
        slides = doc.get("slides")
        if not isinstance(slides, list) or not 5 <= len(slides) <= 9:
            raise ValueError("slides must contain 5 to 9 entries")
        allowed = {"cover", "hook", "list", "cards", "process", "before_after", "checklist", "cta"}
        for index, slide in enumerate(slides, 1):
            if not isinstance(slide, dict) or slide.get("type") not in allowed:
                raise ValueError(f"slide {index}: unsupported or missing type")
        return
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    jsonschema.validate(doc, schema)


def font_candidates(tokens: dict[str, Any], kind: str) -> list[Path]:
    configured = tokens.get("fonts", {}).get(kind)
    if isinstance(configured, str):
        configured = [configured]
    elif not isinstance(configured, list):
        # Config may describe a family/weight object rather than a file path.
        # The matching bundled font file below remains authoritative.
        configured = []
    paths: list[Path] = []
    for raw in configured or []:
        p = Path(raw).expanduser()
        paths.append(p if p.is_absolute() else OS_ROOT / p)
    local = OS_ROOT / "assets" / "fonts"
    names = {
        "latin_regular": ["SpaceGrotesk-Regular.otf"],
        "latin_bold": ["SpaceGrotesk-Bold.otf"],
        "arabic_regular": [],
        "arabic_bold": [],
    }[kind]
    paths.extend(local / name for name in names)
    paths.extend([
        Path("/System/Library/Fonts/Helvetica.ttc"),
        Path("/System/Library/Fonts/Supplemental/Arial Unicode.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
    ])
    return paths


def load_font(tokens: dict[str, Any], kind: str, size: int) -> ImageFont.FreeTypeFont:
    for path in font_candidates(tokens, kind):
        try:
            if path.exists():
                font = ImageFont.truetype(str(path), size)
                if "[wght]" in path.name:
                    try:
                        font.set_variation_by_axes([700 if kind.endswith("bold") else 400])
                    except Exception:
                        pass
                return font
        except Exception:
            continue
    return ImageFont.load_default()


def has_arabic(text: str) -> bool:
    return any("\u0600" <= char <= "\u06ff" or "\u0750" <= char <= "\u077f" for char in text)


def display(text: str) -> str:
    if not has_arabic(text):
        return text
    try:
        import arabic_reshaper  # type: ignore
        from bidi.algorithm import get_display  # type: ignore
    except ImportError as exc:
        raise RuntimeError(
            "Arabic slides require arabic-reshaper and python-bidi. "
            "Install them in the active Python runtime."
        ) from exc
    return get_display(arabic_reshaper.reshape(text), base_dir="R")


def font_for(tokens: dict[str, Any], text: str, size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    family = "arabic" if has_arabic(text) else "latin"
    return load_font(tokens, f"{family}_{'bold' if bold else 'regular'}", size)


def measure(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont) -> tuple[int, int]:
    box = draw.textbbox((0, 0), display(text), font=font)
    return box[2] - box[0], box[3] - box[1]


def wrap(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont, width: int) -> list[str]:
    lines: list[str] = []
    for paragraph in str(text).splitlines() or [""]:
        words = paragraph.split()
        if not words:
            lines.append("")
            continue
        current = words[0]
        for word in words[1:]:
            candidate = f"{current} {word}"
            if measure(draw, candidate, font)[0] <= width:
                current = candidate
            else:
                lines.append(current)
                current = word
        lines.append(current)
    return lines


def draw_text_block(
    draw: ImageDraw.ImageDraw,
    tokens: dict[str, Any],
    text: str,
    box: tuple[int, int, int, int],
    size: int,
    color: str,
    bold: bool = False,
    gap: int = 10,
    align: str = "auto",
    max_lines: int | None = None,
) -> int:
    x1, y1, x2, _ = box
    font = font_for(tokens, text, size, bold)
    lines = wrap(draw, text, font, x2 - x1)
    if max_lines:
        lines = lines[:max_lines]
    if align == "auto":
        align = "right" if has_arabic(text) else "left"
    y = y1
    for line in lines:
        w, h = measure(draw, line, font)
        x = x2 - w if align == "right" else (x1 + x2 - w) // 2 if align == "center" else x1
        draw.text((x, y), display(line), font=font, fill=color)
        y += h + gap
    return y


def fit_title_size(draw: ImageDraw.ImageDraw, tokens: dict[str, Any], text: str, width: int, start: int = 82) -> int:
    for size in range(start, 45, -2):
        font = font_for(tokens, text, size, True)
        if len(wrap(draw, text, font, width)) <= 2:
            return size
    return 46


def colors(tokens: dict[str, Any], theme: str) -> tuple[str, str, str, str]:
    c = tokens["colors"]
    if theme == "dark":
        return c["ink"], c["porcelain"], "#252C33", "#94A0AB"
    if theme == "ink":
        return c["plum"], c["porcelain"], "#3B2635", "#BCA8B5"
    return c["porcelain"], c["ink"], c["white"], c["slate"]


def draw_wordmark(draw: ImageDraw.ImageDraw, tokens: dict[str, Any], foreground: str) -> None:
    lines = tokens.get("brand", {}).get("wordmark", ["CAROUSEL", "OS"])
    sizes = [25, 34]
    ys = [48, 76]
    for text, size, y in zip(lines, sizes, ys):
        font = load_font(tokens, "latin_bold", size)
        w, _ = measure(draw, text, font)
        draw.text(((W - w) // 2, y), text, font=font, fill=foreground)


def draw_footer(draw: ImageDraw.ImageDraw, tokens: dict[str, Any], foreground: str, quiet: str, index: int, count: int, handle: str) -> None:
    font = load_font(tokens, "latin_bold", 21)
    draw.text((70, 1282), handle, font=font, fill=foreground)
    label = f"{index:02d}/{count:02d}"
    lw, _ = measure(draw, label, font)
    draw.text((1010 - lw, 1282), label, font=font, fill=quiet)


def base(tokens: dict[str, Any], slide: dict[str, Any], index: int, count: int, handle: str) -> tuple[Image.Image, ImageDraw.ImageDraw, str, str, str, str]:
    bg, fg, card, quiet = colors(tokens, slide.get("theme", "light"))
    image = Image.new("RGB", (W, H), bg)
    draw = ImageDraw.Draw(image)
    draw_wordmark(draw, tokens, fg)
    draw_footer(draw, tokens, fg, quiet, index, count, handle)
    eyebrow = str(slide.get("eyebrow", "")).upper()
    if eyebrow:
        font = load_font(tokens, "latin_bold", 20)
        draw.text((70, 178), eyebrow, font=font, fill=tokens["colors"]["lime"])
    title = str(slide.get("title", ""))
    if title:
        size = fit_title_size(draw, tokens, title, 940)
        draw_text_block(draw, tokens, title, (70, 218, 1010, 420), size, fg, True, gap=6, max_lines=2)
    subtitle = str(slide.get("subtitle", ""))
    if subtitle:
        draw_text_block(draw, tokens, subtitle, (70, 420, 1010, 520), 29, quiet, False, gap=6, max_lines=2)
    return image, draw, bg, fg, card, quiet


def normalized_items(items: Iterable[Any]) -> list[dict[str, Any]]:
    result = []
    for index, raw in enumerate(items, 1):
        if isinstance(raw, str):
            result.append({"title": raw, "body": "", "number": index})
        else:
            item = dict(raw)
            item.setdefault("title", item.get("label", ""))
            item.setdefault("body", "")
            item.setdefault("number", index)
            result.append(item)
    return result


def card_box(draw: ImageDraw.ImageDraw, xy: tuple[int, int, int, int], fill: str, outline: str, width: int = 2, radius: int = 24) -> None:
    draw.rounded_rectangle(xy, radius=radius, fill=fill, outline=outline, width=width)


def paste_image_panel(canvas: Image.Image, slide: dict[str, Any], box: tuple[int, int, int, int], outline: str, radius: int = 26) -> None:
    """Crop an optional teaching image into a clean rounded editorial panel."""
    raw = slide.get("_resolved_image") or slide.get("image")
    if not raw:
        return
    source = Image.open(Path(str(raw))).convert("RGB")
    x1, y1, x2, y2 = box
    size = (x2 - x1, y2 - y1)
    if slide.get("image_fit") == "contain":
        panel = Image.new("RGB", size, source.getpixel((0, 0)))
        contained = ImageOps.contain(source, size, Image.Resampling.LANCZOS)
        panel.paste(contained, ((size[0] - contained.width) // 2, (size[1] - contained.height) // 2))
    else:
        panel = ImageOps.fit(source, size, Image.Resampling.LANCZOS, centering=(0.5, 0.5))
    mask = Image.new("L", size, 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, size[0], size[1]), radius=radius, fill=255)
    canvas.paste(panel, (x1, y1), mask)
    ImageDraw.Draw(canvas).rounded_rectangle(box, radius=radius, outline=outline, width=2)


def draw_image_labels(canvas: Image.Image, slide: dict[str, Any], box: tuple[int, int, int, int], tokens: dict[str, Any]) -> None:
    labels = slide.get("image_labels") or []
    if not labels:
        return
    draw = ImageDraw.Draw(canvas)
    x1, y1, x2, _ = box
    positions = [x1 + 28, x2 - 238]
    for index, raw in enumerate(labels[:2]):
        label = str(raw).upper()
        x = positions[index]
        fill = tokens["colors"]["cobalt"] if index == 0 else tokens["colors"]["copper"]
        draw.rounded_rectangle((x, y1 + 20, x + 210, y1 + 66), radius=23, fill=fill)
        font = load_font(tokens, "latin_bold", 18)
        width, height = measure(draw, label, font)
        draw.text((x + 105 - width // 2, y1 + 43 - height // 2), label, font=font, fill=tokens["colors"]["porcelain"])


def render_hook(tokens: dict[str, Any], slide: dict[str, Any], index: int, count: int, handle: str) -> Image.Image:
    """Render slide 2 as an alternate front door with cover-like hierarchy."""
    bg, fg, card, quiet = colors(tokens, slide.get("theme", "dark"))
    image = Image.new("RGB", (W, H), bg)
    draw = ImageDraw.Draw(image)
    draw_wordmark(draw, tokens, fg)
    draw_footer(draw, tokens, fg, quiet, index, count, handle)

    eyebrow = str(slide.get("eyebrow", "")).upper()
    if eyebrow:
        ef = load_font(tokens, "latin_bold", 21)
        ew, _ = measure(draw, eyebrow, ef)
        draw.rounded_rectangle((W // 2 - ew // 2 - 22, 176, W // 2 + ew // 2 + 22, 222), radius=23, fill=tokens["colors"]["lime"])
        draw.text((W // 2 - ew // 2, 187), eyebrow, font=ef, fill=tokens["colors"]["ink"])

    title = str(slide.get("title", ""))
    has_image = bool(slide.get("image"))
    title_size = fit_title_size(draw, tokens, title, 900, 104 if has_image else 116)
    title_box = (90, 270, 990, 535) if has_image else (90, 300, 990, 665)
    draw_text_block(draw, tokens, title, title_box, title_size, fg, True, gap=10, align="center", max_lines=3)

    subtitle = str(slide.get("subtitle", ""))
    subtitle_box = (135, 540, 945, 670) if has_image else (135, 735, 945, 920)
    draw_text_block(draw, tokens, subtitle, subtitle_box, 34 if has_image else 38, quiet, False, gap=8, align="center", max_lines=3)

    if has_image:
        image_box = (135, 705, 945, 1135)
        paste_image_panel(image, slide, image_box, quiet, 28)
        draw_image_labels(image, slide, image_box, tokens)
        return image

    # Minimal open-loop device: a broken sequence that visually asks for completion.
    y = 1065
    draw.line((365, y, 490, y), fill=quiet, width=4)
    draw.line((590, y, 715, y), fill=quiet, width=4)
    draw.ellipse((330, y - 35, 400, y + 35), fill=tokens["colors"]["lime"])
    draw.ellipse((505, y - 35, 575, y + 35), outline=quiet, width=4)
    draw.ellipse((680, y - 35, 750, y + 35), outline=quiet, width=4)
    return image


def render_list(tokens: dict[str, Any], slide: dict[str, Any], index: int, count: int, handle: str) -> Image.Image:
    image, draw, _, fg, card, quiet = base(tokens, slide, index, count, handle)
    items = normalized_items(slide.get("items", []))[:6]
    if slide.get("image"):
        image_box = (70, 525, 1010, 845)
        paste_image_panel(image, slide, image_box, quiet, 28)
        draw_image_labels(image, slide, image_box, tokens)
        cols = 2
        rows = max(1, math.ceil(len(items) / cols))
        gap_x, gap_y = 24, 18
        x0, y0 = 70, 875
        card_w = (940 - gap_x) // cols
        card_h = (315 - gap_y * max(0, rows - 1)) // rows
        for i, item in enumerate(items):
            x = x0 + (i % cols) * (card_w + gap_x)
            y = y0 + (i // cols) * (card_h + gap_y)
            card_box(draw, (x, y, x + card_w, y + card_h), card, quiet, 2, 20)
            circle = tokens["colors"]["cobalt"]
            draw.ellipse((x + 20, y + 20, x + 64, y + 64), fill=circle)
            number = str(item.get("number", i + 1)).zfill(2)
            nf = load_font(tokens, "latin_bold", 17)
            nw, nh = measure(draw, number, nf)
            draw.text((x + 42 - nw // 2, y + 42 - nh // 2), number, font=nf, fill=tokens["colors"]["porcelain"])
            draw_text_block(draw, tokens, str(item["title"]), (x + 82, y + 18, x + card_w - 18, y + 60), 22, fg, True, gap=2, max_lines=1)
            draw_text_block(draw, tokens, str(item["body"]), (x + 20, y + 76, x + card_w - 18, y + card_h - 12), 21, fg, False, gap=3, max_lines=3)
        return image
    top, bottom = 545, 1208
    gap = 16
    row_h = min(138, (bottom - top - gap * max(0, len(items) - 1)) // max(1, len(items)))
    for i, item in enumerate(items):
        y = top + i * (row_h + gap)
        accent = bool(item.get("accent"))
        fill = fg if accent else card
        text_color = tokens["colors"]["porcelain"] if accent else fg
        card_box(draw, (70, y, 1010, y + row_h), fill, fg if accent else quiet, 2)
        circle = tokens["colors"]["lime"] if accent else tokens["colors"]["cobalt"]
        draw.ellipse((95, y + 27, 151, y + 83), fill=circle)
        number = str(item.get("number", i + 1)).zfill(2)
        nf = load_font(tokens, "latin_bold", 20)
        nw, nh = measure(draw, number, nf)
        draw.text((123 - nw // 2, y + 54 - nh // 2), number, font=nf, fill=tokens["colors"]["ink"])
        draw_text_block(draw, tokens, str(item["title"]), (180, y + 22, 475, y + row_h - 12), 29, text_color, True, gap=2, max_lines=2)
        draw_text_block(draw, tokens, str(item["body"]), (500, y + 24, 975, y + row_h - 12), 29, text_color, False, gap=3, max_lines=2)
    return image


def render_cards(tokens: dict[str, Any], slide: dict[str, Any], index: int, count: int, handle: str) -> Image.Image:
    image, draw, _, fg, card, quiet = base(tokens, slide, index, count, handle)
    items = normalized_items(slide.get("items", []))[:6]
    cols = 2
    rows = max(1, math.ceil(len(items) / cols))
    x0, y0, gap_x, gap_y = 70, 535, 24, 24
    cw = (940 - gap_x) // 2
    ch = min(260, (665 - gap_y * (rows - 1)) // rows)
    for i, item in enumerate(items):
        x = x0 + (i % cols) * (cw + gap_x)
        y = y0 + (i // cols) * (ch + gap_y)
        accent = bool(item.get("accent"))
        fill = fg if accent else card
        text_color = tokens["colors"]["porcelain"] if accent else fg
        card_box(draw, (x, y, x + cw, y + ch), fill, tokens["colors"]["lime"] if accent else quiet, 2)
        number = str(item.get("number", i + 1)).zfill(2)
        draw.text((x + 25, y + 22), number, font=load_font(tokens, "latin_bold", 21), fill=tokens["colors"]["lime"])
        draw_text_block(draw, tokens, str(item["title"]), (x + 25, y + 65, x + cw - 25, y + 130), 29, text_color, True, gap=3, max_lines=2)
        draw_text_block(draw, tokens, str(item["body"]), (x + 25, y + 137, x + cw - 25, y + ch - 20), 28, text_color, False, gap=4, max_lines=3)
    return image


def render_process(tokens: dict[str, Any], slide: dict[str, Any], index: int, count: int, handle: str) -> Image.Image:
    image, draw, _, fg, card, quiet = base(tokens, slide, index, count, handle)
    items = normalized_items(slide.get("items", []))[:5]
    n = max(1, len(items))
    left, right, y = 82, 998, 750
    step_gap = (right - left) / max(1, n - 1)
    draw.line((left, y, right, y), fill=quiet, width=5)
    for i, item in enumerate(items):
        x = int(left + i * step_gap) if n > 1 else W // 2
        draw.ellipse((x - 49, y - 49, x + 49, y + 49), fill=tokens["colors"]["lime"], outline=fg, width=3)
        number = str(item.get("number", i + 1)).zfill(2)
        f = load_font(tokens, "latin_bold", 25)
        nw, nh = measure(draw, number, f)
        draw.text((x - nw // 2, y - nh // 2 - 2), number, font=f, fill=tokens["colors"]["ink"])
        bx1, bx2 = max(45, x - 120), min(1035, x + 120)
        draw_text_block(draw, tokens, str(item["title"]), (bx1, y + 80, bx2, y + 165), 25, fg, True, gap=2, align="center", max_lines=2)
        draw_text_block(draw, tokens, str(item["body"]), (bx1, y + 180, bx2, y + 310), 28, quiet, False, gap=3, align="center", max_lines=3)
    note = str(slide.get("note", ""))
    if note:
        draw_text_block(draw, tokens, note, (70, 1095, 1010, 1180), 26, tokens["colors"]["lime"], True, align="center", max_lines=2)
    return image


def side_data(raw: Any, default_title: str) -> dict[str, Any]:
    if isinstance(raw, str):
        return {"title": default_title, "body": raw, "items": []}
    value = dict(raw or {})
    value.setdefault("title", default_title)
    value.setdefault("body", "")
    value.setdefault("items", [])
    return value


def render_before_after(tokens: dict[str, Any], slide: dict[str, Any], index: int, count: int, handle: str) -> Image.Image:
    image, draw, _, fg, card, quiet = base(tokens, slide, index, count, handle)
    panels = [side_data(slide.get("before"), "BEFORE"), side_data(slide.get("after"), "AFTER")]
    for i, panel in enumerate(panels):
        x1 = 70 if i == 0 else 552
        x2 = 528 if i == 0 else 1010
        y1, y2 = 540, 1195
        accent = tokens["colors"]["copper"] if i == 0 else tokens["colors"]["lime"]
        fill = card if i == 0 else fg
        pfg = fg if i == 0 else tokens["colors"]["porcelain"]
        card_box(draw, (x1, y1, x2, y2), fill, accent, 3, 28)
        label = str(panel["title"])
        draw.text((x1 + 30, y1 + 30), display(label), font=font_for(tokens, label, 25, True), fill=accent)
        end = draw_text_block(draw, tokens, str(panel["body"]), (x1 + 30, y1 + 105, x2 - 30, y1 + 300), 30, pfg, True, gap=7, max_lines=4)
        for j, item in enumerate(normalized_items(panel.get("items", []))[:4]):
            yy = end + 35 + j * 88
            draw.ellipse((x1 + 32, yy + 9, x1 + 50, yy + 27), fill=accent)
            draw_text_block(draw, tokens, str(item["title"]), (x1 + 70, yy, x2 - 25, yy + 75), 23, pfg, False, gap=2, max_lines=2)
    return image


def render_checklist(tokens: dict[str, Any], slide: dict[str, Any], index: int, count: int, handle: str) -> Image.Image:
    image, draw, _, fg, card, quiet = base(tokens, slide, index, count, handle)
    items = normalized_items(slide.get("items", []))[:6]
    if slide.get("image"):
        paste_image_panel(image, slide, (70, 520, 480, 1115), quiet, 28)
        top, bottom, gap = 520, 1115, 14
        row_h = (bottom - top - gap * max(0, len(items) - 1)) // max(1, len(items))
        for i, item in enumerate(items):
            y = top + i * (row_h + gap)
            card_box(draw, (510, y, 1010, y + row_h), card, quiet, 2, 20)
            draw.rounded_rectangle((530, y + 22, 576, y + 68), radius=11, fill=tokens["colors"]["lime"], outline=fg, width=2)
            draw.line((541, y + 45, 551, y + 55, 566, y + 36), fill=tokens["colors"]["ink"], width=4, joint="curve")
            draw_text_block(draw, tokens, str(item["title"]), (595, y + 18, 985, y + 56), 23, fg, True, gap=2, max_lines=1)
            draw_text_block(draw, tokens, str(item["body"]), (530, y + 70, 985, y + row_h - 12), 22, fg, False, gap=2, max_lines=3)
        note = str(slide.get("note", ""))
        if note:
            draw_text_block(draw, tokens, note, (70, 1150, 1010, 1250), 25, tokens["colors"]["lime"], True, align="center", max_lines=2)
        return image
    top, gap = 520, 14
    row_h = min(120, (690 - gap * max(0, len(items) - 1)) // max(1, len(items)))
    for i, item in enumerate(items):
        y = top + i * (row_h + gap)
        card_box(draw, (70, y, 1010, y + row_h), card, quiet, 2, 20)
        draw.rounded_rectangle((95, y + 29, 151, y + 85), radius=13, fill=tokens["colors"]["lime"], outline=fg, width=2)
        draw.line((109, y + 56, 121, y + 68, 139, y + 45), fill=tokens["colors"]["ink"], width=5, joint="curve")
        draw_text_block(draw, tokens, str(item["title"]), (185, y + 24, 470, y + row_h - 10), 27, fg, True, gap=2, max_lines=2)
        draw_text_block(draw, tokens, str(item["body"]), (500, y + 25, 975, y + row_h - 10), 28, fg, False, gap=2, max_lines=2)
    note = str(slide.get("note", ""))
    if note:
        draw_text_block(draw, tokens, note, (70, 1195, 1010, 1260), 28, tokens["colors"]["lime"], True, align="center", max_lines=1)
    return image


def render_cta(tokens: dict[str, Any], slide: dict[str, Any], index: int, count: int, handle: str) -> Image.Image:
    local = dict(slide)
    local.setdefault("theme", "dark")
    image, draw, _, fg, card, quiet = base(tokens, local, index, count, handle)
    keyword = str(slide.get("keyword", "")).upper()
    box = (105, 650, 975, 955)
    card_box(draw, box, tokens["colors"]["porcelain"], tokens["colors"]["lime"], 4, 32)
    key_size = fit_title_size(draw, tokens, keyword, 760, 118)
    draw_text_block(draw, tokens, keyword, (150, 710, 930, 830), key_size, tokens["colors"]["ink"], True, align="center", max_lines=1)
    cta = str(slide.get("cta") or f'COMMENT "{keyword}"')
    draw_text_block(draw, tokens, cta, (155, 850, 925, 915), 29, tokens["colors"]["slate"], True, align="center", max_lines=1)
    prompt = str(slide.get("button", "SEND IT →"))
    if prompt:
        pill = (260, 1055, 820, 1135)
        draw.rounded_rectangle(pill, radius=40, fill=tokens["colors"]["lime"])
        draw_text_block(draw, tokens, prompt, (285, 1077, 795, 1122), 27, tokens["colors"]["ink"], True, align="center", max_lines=1)
    return image


RENDERERS = {
    "hook": render_hook,
    "list": render_list,
    "cards": render_cards,
    "process": render_process,
    "before_after": render_before_after,
    "checklist": render_checklist,
    "cta": render_cta,
}


def render_cover(slide: dict[str, Any], spec_dir: Path) -> Image.Image:
    path = resolve_path(slide["image"], spec_dir)
    if not path.exists():
        raise FileNotFoundError(f"cover image not found: {path}")
    source = Image.open(path).convert("RGB")
    if source.size == (W, H):
        return source.copy()
    return ImageOps.fit(source, (W, H), Image.Resampling.LANCZOS, centering=(0.5, 0.5))


def make_contact_sheet(paths: list[Path], out: Path) -> None:
    thumb = (216, 270)
    cols = min(4, len(paths))
    rows = math.ceil(len(paths) / cols)
    sheet = Image.new("RGB", (cols * 240 + 24, rows * 310 + 24), DEFAULTS["colors"]["porcelain"])
    draw = ImageDraw.Draw(sheet)
    for i, path in enumerate(paths):
        image = Image.open(path).convert("RGB").resize(thumb, Image.Resampling.LANCZOS)
        x, y = 18 + (i % cols) * 240, 18 + (i // cols) * 310
        sheet.paste(image, (x, y))
        draw.text((x, y + 276), f"SLIDE {i + 1:02d}", fill=DEFAULTS["colors"]["ink"])
    sheet.save(out, optimize=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("spec", type=Path, help="Carousel JSON document")
    parser.add_argument("--out", type=Path, required=True, help="Output directory")
    parser.add_argument("--tokens", type=Path, help="Optional brand tokens JSON")
    parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA)
    parser.add_argument("--no-contact-sheet", action="store_true")
    args = parser.parse_args()

    spec = args.spec.resolve()
    doc = json.loads(spec.read_text(encoding="utf-8"))
    validate_document(doc, args.schema)
    tokens = load_tokens(args.tokens)
    slides = doc["slides"]
    if slides[0]["type"] != "cover":
        raise ValueError("The first slide must be type 'cover'")
    if slides[1]["type"] != "hook":
        raise ValueError("The second slide must be the dedicated type 'hook' second-chance slide")
    if slides[-1]["type"] != "cta":
        raise ValueError("The last slide must be a dedicated type 'cta' slide")

    args.out.mkdir(parents=True, exist_ok=True)
    handle = doc.get("metadata", {}).get("handle") or tokens.get("brand", {}).get("handle", "@yourhandle")
    paths: list[Path] = []
    for index, slide in enumerate(slides, 1):
        if slide["type"] == "cover":
            image = render_cover(slide, spec.parent)
        else:
            local_slide = dict(slide)
            if local_slide.get("image"):
                local_slide["_resolved_image"] = str(resolve_path(local_slide["image"], spec.parent))
            image = RENDERERS[slide["type"]](tokens, local_slide, index, len(slides), handle)
        path = args.out / f"slide-{index:02d}.png"
        image.save(path, format="PNG", optimize=True)
        paths.append(path)

    if not args.no_contact_sheet:
        make_contact_sheet(paths, args.out / "contact-sheet.png")
    manifest = {
        "topic": doc["metadata"]["topic"],
        "canvas": [W, H],
        "slides": [str(path.resolve()) for path in paths],
        "contact_sheet": None if args.no_contact_sheet else str((args.out / "contact-sheet.png").resolve()),
    }
    (args.out / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"render_carousel: {exc}", file=sys.stderr)
        raise SystemExit(1)
