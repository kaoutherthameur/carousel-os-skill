#!/usr/bin/env python3
"""Validate a completed Carousel OS delivery folder.

The validator intentionally uses only the Python standard library. It validates
the parts of ``schemas/run.schema.json`` that are important at the delivery
boundary, checks PNG dimensions without Pillow, and tests the final ZIP.
"""

from __future__ import annotations

import argparse
import json
import struct
import sys
import zipfile
from pathlib import Path
from typing import Any


SLIDE_SIZE = (1080, 1350)
REQUIRED_ARTIFACTS = (
    "cover",
    "final_slide",
    "contact_sheet",
    "archive",
    "package",
    "caption",
    "qa_report",
)


class ValidationError(Exception):
    """Raised when a run cannot cross the delivery gate."""


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValidationError(f"missing file: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ValidationError(f"invalid JSON in {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ValidationError(f"expected a JSON object in {path}")
    return value


def _inside(run_dir: Path, value: object, label: str) -> Path:
    if not isinstance(value, str) or not value.strip():
        raise ValidationError(f"{label} must be a non-empty relative path")
    candidate = (run_dir / value).resolve()
    try:
        candidate.relative_to(run_dir)
    except ValueError as exc:
        raise ValidationError(f"{label} escapes the run folder: {value}") from exc
    if not candidate.is_file():
        raise ValidationError(f"{label} is missing: {value}")
    return candidate


def png_size(path: Path) -> tuple[int, int]:
    with path.open("rb") as handle:
        header = handle.read(24)
    if len(header) < 24 or header[:8] != b"\x89PNG\r\n\x1a\n" or header[12:16] != b"IHDR":
        raise ValidationError(f"not a valid PNG: {path.name}")
    return struct.unpack(">II", header[16:24])


def validate_run(run_dir: Path, *, require_delivered: bool = True) -> dict[str, Any]:
    run_dir = run_dir.expanduser().resolve()
    if not run_dir.is_dir():
        raise ValidationError(f"run folder does not exist: {run_dir}")

    manifest_path = run_dir / "run.json"
    manifest = _read_json(manifest_path)
    errors: list[str] = []

    def check(condition: bool, message: str) -> None:
        if not condition:
            errors.append(message)

    check(manifest.get("schema_version") == 1, "schema_version must be 1")
    check(isinstance(manifest.get("run_id"), str) and bool(manifest.get("run_id")), "run_id is required")
    status = manifest.get("status")
    check(status in {"draft", "rendered", "validated", "delivered"}, "invalid run status")
    if require_delivered:
        check(status == "delivered", "run status must be delivered before the topic can be completed")
        delivery = manifest.get("delivery")
        check(isinstance(delivery, dict) and bool(delivery.get("delivered_at")), "delivery.delivered_at is required")

    topic = manifest.get("topic")
    check(isinstance(topic, dict), "topic object is required")
    if isinstance(topic, dict):
        for key in ("id", "source_file", "title"):
            check(isinstance(topic.get(key), str) and bool(topic.get(key)), f"topic.{key} is required")

    artifacts = manifest.get("artifacts")
    check(isinstance(artifacts, dict), "artifacts object is required")
    artifact_paths: dict[str, Path] = {}
    if isinstance(artifacts, dict):
        for key in REQUIRED_ARTIFACTS:
            try:
                artifact_paths[key] = _inside(run_dir, artifacts.get(key), f"artifacts.{key}")
            except ValidationError as exc:
                errors.append(str(exc))

    slides = manifest.get("slides")
    check(isinstance(slides, list) and 5 <= len(slides) <= 9, "slides must contain 5 to 9 entries")
    slide_paths: list[Path] = []
    if isinstance(slides, list):
        numbers = [slide.get("number") for slide in slides if isinstance(slide, dict)]
        check(numbers == list(range(1, len(slides) + 1)), "slide numbers must be sequential and ordered from 1")
        roles = [slide.get("role") for slide in slides if isinstance(slide, dict)]
        check(roles.count("cover") == 1 and roles[:1] == ["cover"], "the first slide must be the only cover")
        check(roles.count("cta") == 1 and roles[-1:] == ["cta"], "the final slide must be the only CTA")
        for index, slide in enumerate(slides, start=1):
            if not isinstance(slide, dict):
                errors.append(f"slide {index} must be an object")
                continue
            check(slide.get("width") == 1080 and slide.get("height") == 1350, f"slide {index} manifest size must be 1080x1350")
            try:
                path = _inside(run_dir, slide.get("file"), f"slide {index}")
                slide_paths.append(path)
                check(png_size(path) == SLIDE_SIZE, f"{path.name} must be 1080x1350")
            except ValidationError as exc:
                errors.append(str(exc))

    if slide_paths and artifact_paths:
        check(artifact_paths.get("cover") == slide_paths[0], "artifacts.cover must point to the first slide")
        check(artifact_paths.get("final_slide") == slide_paths[-1], "artifacts.final_slide must point to the final CTA slide")

    contact = artifact_paths.get("contact_sheet")
    if contact:
        try:
            width, height = png_size(contact)
            check(width > 0 and height > 0, "contact sheet has invalid dimensions")
        except ValidationError as exc:
            errors.append(str(exc))

    for key in ("package", "caption"):
        path = artifact_paths.get(key)
        if path:
            check(bool(path.read_text(encoding="utf-8").strip()), f"{key} must not be empty")

    qa_path = artifact_paths.get("qa_report")
    if qa_path:
        try:
            qa_report = _read_json(qa_path)
            check(qa_report.get("passed") is True, "QA report must contain passed: true")
            qa = manifest.get("qa")
            check(isinstance(qa, dict) and qa.get("passed") is True, "manifest qa.passed must be true")
            check(isinstance(qa, dict) and qa.get("report") == artifacts.get("qa_report"), "qa.report must match artifacts.qa_report")
        except ValidationError as exc:
            errors.append(str(exc))

    archive = artifact_paths.get("archive")
    if archive:
        try:
            with zipfile.ZipFile(archive) as bundle:
                bad = bundle.testzip()
                check(bad is None, f"archive contains a corrupt member: {bad}")
                names = {Path(name).name for name in bundle.namelist() if not name.endswith("/")}
                required_names = {path.name for path in slide_paths}
                required_names.update(
                    path.name for key, path in artifact_paths.items() if key in {"package", "caption", "qa_report"}
                )
                missing = sorted(required_names - names)
                check(not missing, f"archive is missing: {', '.join(missing)}")
        except (zipfile.BadZipFile, OSError) as exc:
            errors.append(f"invalid archive {archive.name}: {exc}")

    if errors:
        raise ValidationError("\n".join(f"- {message}" for message in errors))

    return {
        "valid": True,
        "run_id": manifest["run_id"],
        "status": status,
        "slide_count": len(slide_paths),
        "run_dir": str(run_dir),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate a carousel delivery run")
    parser.add_argument("run_dir", type=Path, help="folder containing run.json and delivery artifacts")
    parser.add_argument(
        "--allow-undelivered",
        action="store_true",
        help="validate production artifacts before delivery (never use this for ledger completion)",
    )
    parser.add_argument("--json", action="store_true", help="print machine-readable output")
    args = parser.parse_args(argv)
    try:
        result = validate_run(args.run_dir, require_delivered=not args.allow_undelivered)
    except ValidationError as exc:
        if args.json:
            print(json.dumps({"valid": False, "errors": str(exc).splitlines()}, ensure_ascii=False))
        else:
            print(f"Run validation failed:\n{exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2) if args.json else f"Valid delivery: {result['slide_count']} slides ({result['run_id']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
