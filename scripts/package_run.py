#!/usr/bin/env python3
"""Package a passing carousel run and write the delivery manifest.

The command is intentionally strict: it requires an existing passed QA report,
sequential slides, package/caption files, and a contact sheet. It creates the
ZIP, writes run.json, and invokes validate_run before reporting success.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import zipfile
from pathlib import Path

from validate_run import png_size, validate_run


def now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def inside(run_dir: Path, path: Path) -> str:
    return path.resolve().relative_to(run_dir.resolve()).as_posix()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_dir", type=Path)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--topic-id", required=True)
    parser.add_argument("--topic-source", required=True)
    parser.add_argument("--topic-title", required=True)
    parser.add_argument("--channel", default="codex")
    parser.add_argument("--note", default="")
    args = parser.parse_args()

    run_dir = args.run_dir.expanduser().resolve()
    slides_dir = run_dir / "slides"
    slides = sorted(slides_dir.glob("slide-*.png"))
    if not 5 <= len(slides) <= 9:
        raise ValueError("slides/ must contain 5 to 9 sequential slide-*.png files")
    expected = [f"slide-{index:02d}.png" for index in range(1, len(slides) + 1)]
    if [path.name for path in slides] != expected:
        raise ValueError("slide files must be sequential from slide-01.png")
    for path in slides:
        if png_size(path) != (1080, 1350):
            raise ValueError(f"{path.name} must be 1080x1350")

    contact = run_dir / "contact-sheet.png"
    package = run_dir / "package.md"
    caption = run_dir / "caption.md"
    qa_report = run_dir / "qa-report.json"
    for path in (contact, package, caption, qa_report):
        if not path.is_file():
            raise FileNotFoundError(path)
    qa = json.loads(qa_report.read_text(encoding="utf-8"))
    if qa.get("passed") is not True:
        raise ValueError("qa-report.json must contain passed: true")

    archive = run_dir / f"{args.run_id}-carousel.zip"
    lead_magnet = run_dir / "lead-magnet.md"
    sources = run_dir / "sources.md"
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
        for path in slides:
            bundle.write(path, path.name)
        for path in (package, caption, qa_report):
            bundle.write(path, path.name)
        if lead_magnet.is_file():
            bundle.write(lead_magnet, lead_magnet.name)
        if sources.is_file():
            bundle.write(sources, sources.name)

    timestamp = now()
    slide_rows = []
    for index, path in enumerate(slides, 1):
        role = "cover" if index == 1 else "hook" if index == 2 else "cta" if index == len(slides) else "save" if index == len(slides) - 1 else "content"
        slide_rows.append({
            "number": index,
            "file": inside(run_dir, path),
            "role": role,
            "width": 1080,
            "height": 1350,
        })
    manifest = {
        "schema_version": 1,
        "run_id": args.run_id,
        "topic": {
            "id": args.topic_id,
            "source_file": args.topic_source,
            "title": args.topic_title,
        },
        "status": "delivered",
        "created_at": timestamp,
        "updated_at": timestamp,
        "slides": slide_rows,
        "artifacts": {
            "cover": slide_rows[0]["file"],
            "final_slide": slide_rows[-1]["file"],
            "contact_sheet": inside(run_dir, contact),
            "archive": inside(run_dir, archive),
            "package": inside(run_dir, package),
            "caption": inside(run_dir, caption),
            "qa_report": inside(run_dir, qa_report),
        },
        "qa": {"passed": True, "report": inside(run_dir, qa_report)},
        "delivery": {"delivered_at": timestamp, "channel": args.channel, "note": args.note},
    }
    (run_dir / "run.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    result = validate_run(run_dir, require_delivered=True)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
