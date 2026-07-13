#!/usr/bin/env python3
"""Preview a candidate cover as the newest tile in a social-media grid.

With an Instagram screenshot, the candidate replaces the first visible post
using either an explicit --tile-box or a conservative automatic estimate. If a
browser screenshot is unavailable, a local renderer contact sheet is converted
into a neutral 3-column feed and the candidate is inserted first.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageOps


INK = "#10141A"
CLOUD = "#F3F7FF"
ACCENT = "#FF5C35"


def parse_box(value: str) -> tuple[int, int, int, int]:
    try:
        values = tuple(int(part.strip()) for part in value.split(","))
    except ValueError as exc:
        raise argparse.ArgumentTypeError("tile box must be x,y,width,height") from exc
    if len(values) != 4 or values[2] <= 0 or values[3] <= 0:
        raise argparse.ArgumentTypeError("tile box must be x,y,width,height with positive size")
    return values  # type: ignore[return-value]


def cover_tile(path: Path, size: tuple[int, int]) -> Image.Image:
    image = Image.open(path).convert("RGB")
    return ImageOps.fit(image, size, Image.Resampling.LANCZOS, centering=(0.5, 0.5))


def auto_tile_box(image: Image.Image) -> tuple[int, int, int, int]:
    """Estimate the first visible grid tile in a desktop/mobile screenshot.

    Browser capture varies by viewport, so production runs should pass the
    browser-observed bounds via --tile-box whenever possible.
    """
    width, height = image.size
    if height > width * 1.25:  # mobile profile: 3 square columns below header
        tile_w = width // 3
        y = int(height * 0.31)
        return 0, y, tile_w, tile_w
    # Desktop/cropped grid views generally expose 4-5 portrait tiles.
    tile_w = min(int(width * 0.18), int(height * 0.44 * 4 / 5))
    x = max(0, int(width * 0.017))
    y = max(0, int(height * 0.035))
    return x, y, tile_w, int(tile_w * 5 / 4)


def screenshot_preview(candidate: Path, screenshot: Path, box: tuple[int, int, int, int] | None, out: Path) -> None:
    canvas = Image.open(screenshot).convert("RGB")
    x, y, width, height = box or auto_tile_box(canvas)
    x = max(0, min(x, canvas.width - 1))
    y = max(0, min(y, canvas.height - 1))
    width = min(width, canvas.width - x)
    height = min(height, canvas.height - y)
    if width < 80 or height < 80:
        raise ValueError("computed tile box is too small; pass --tile-box x,y,width,height")
    tile = cover_tile(candidate, (width, height))
    canvas.paste(tile, (x, y))
    out.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(out, optimize=True)


def contact_sheet_cells(path: Path, columns: int, rows: int) -> list[Image.Image]:
    sheet = Image.open(path).convert("RGB")
    cell_w, cell_h = sheet.width // columns, sheet.height // rows
    cells: list[Image.Image] = []
    for row in range(rows):
        for col in range(columns):
            left, top = col * cell_w, row * cell_h
            crop = sheet.crop((left, top, min(sheet.width, left + cell_w), min(sheet.height, top + cell_h)))
            # Contact sheets often include a bottom label. A centered 4:5 crop
            # discards it while retaining the rendered slide.
            cells.append(ImageOps.fit(crop, (270, 338), Image.Resampling.LANCZOS, centering=(0.5, 0.42)))
    return cells


def fallback_preview(candidate: Path, contact_sheet: Path, columns: int, rows: int, out: Path) -> None:
    recent = contact_sheet_cells(contact_sheet, columns, rows)
    tile_w, tile_h, gap = 270, 338, 5
    grid_cols, grid_rows = 3, 3
    margin, header = 28, 92
    canvas_w = margin * 2 + grid_cols * tile_w + (grid_cols - 1) * gap
    canvas_h = header + margin + grid_rows * tile_h + (grid_rows - 1) * gap + margin
    canvas = Image.new("RGB", (canvas_w, canvas_h), INK)
    draw = ImageDraw.Draw(canvas)
    draw.text((margin, 28), "GRID FIT PREVIEW  ·  NEWEST POST FIRST", fill=CLOUD)
    draw.rounded_rectangle((canvas_w - 118, 25, canvas_w - 28, 57), radius=16, fill=ACCENT)
    draw.text((canvas_w - 99, 35), "LOCAL", fill=INK)

    tiles = [cover_tile(candidate, (tile_w, tile_h))] + recent[:8]
    while len(tiles) < 9:
        tiles.append(Image.new("RGB", (tile_w, tile_h), "#252C33"))
    for index, tile in enumerate(tiles):
        x = margin + (index % grid_cols) * (tile_w + gap)
        y = header + (index // grid_cols) * (tile_h + gap)
        canvas.paste(tile, (x, y))
    out.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(out, optimize=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", type=Path, required=True, help="Candidate final cover PNG")
    parser.add_argument("--screenshot", type=Path, help="Instagram profile/grid screenshot")
    parser.add_argument("--fallback-contact-sheet", type=Path, help="Local contact sheet used when screenshot is unavailable")
    parser.add_argument("--tile-box", type=parse_box, help="First tile bounds: x,y,width,height")
    parser.add_argument("--sheet-columns", type=int, default=4)
    parser.add_argument("--sheet-rows", type=int, default=2)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    if not args.candidate.exists():
        raise FileNotFoundError(args.candidate)
    if args.screenshot and args.screenshot.exists():
        screenshot_preview(args.candidate, args.screenshot, args.tile_box, args.out)
        mode = "instagram-screenshot"
    elif args.fallback_contact_sheet and args.fallback_contact_sheet.exists():
        fallback_preview(args.candidate, args.fallback_contact_sheet, args.sheet_columns, args.sheet_rows, args.out)
        mode = "local-contact-sheet"
    else:
        raise ValueError("provide an existing --screenshot or --fallback-contact-sheet")
    print(f"{args.out.resolve()}\nmode={mode}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"grid_preview: {exc}", file=sys.stderr)
        raise SystemExit(1)
