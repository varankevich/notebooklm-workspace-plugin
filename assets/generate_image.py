#!/usr/bin/env python3
"""
Gemini image generation wrapper for the slide-pipeline skill.

Thin wrapper over google-generativeai — used for visual refinement of
NotebookLM slides. Contract matches the openclaw deck-designer SKILL.md
template so the same prompts port 1:1.

Env:
    GEMINI_API_KEY  (required)

Usage:
    python generate_image.py \
        --prompt "Executive title slide, dark #0A0A0A background, ..." \
        --filename output/title.png \
        --resolution 2K --aspect-ratio 16:9

    # Edit mode (refine existing slide):
    python generate_image.py \
        --prompt "Refine to match brand: ..." \
        -i input-slide.png \
        --filename output/title-refined.png \
        --resolution 2K

Exit codes:
    0 = success, image written to --filename
    1 = error (auth, API, write)
    2 = usage / arg error
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

try:
    from google import genai
    from google.genai import types as genai_types
except ImportError:
    sys.stderr.write(
        "error: google-generativeai not installed.\n"
        "install: pip install -r "
        f"{Path(__file__).parent}/requirements.txt\n"
    )
    sys.exit(1)


MODEL = "gemini-2.5-flash-image"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Generate or refine presentation slide images with Gemini.",
    )
    p.add_argument("--prompt", required=True, help="Image generation prompt")
    p.add_argument("--filename", required=True, help="Output PNG path")
    p.add_argument("--resolution", default="2K", choices=["1K", "2K", "4K"])
    p.add_argument("--aspect-ratio", default="16:9",
                   choices=["16:9", "4:3", "1:1", "9:16", "3:4"])
    p.add_argument("-i", "--input", default=None,
                   help="Input image for edit mode (optional)")
    return p.parse_args()


def get_client() -> genai.Client:
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        sys.stderr.write("error: GEMINI_API_KEY not set in environment\n")
        sys.exit(1)
    return genai.Client(api_key=api_key)


def generate(args: argparse.Namespace) -> None:
    client = get_client()

    contents: list = [args.prompt]

    if args.input:
        input_path = Path(args.input)
        if not input_path.exists():
            sys.stderr.write(f"error: input image not found: {input_path}\n")
            sys.exit(1)
        image_bytes = input_path.read_bytes()
        mime = "image/png" if input_path.suffix.lower() == ".png" else "image/jpeg"
        contents.append(
            genai_types.Part.from_bytes(data=image_bytes, mime_type=mime)
        )

    config = genai_types.GenerateContentConfig(
        response_modalities=["IMAGE"],
        image_config=genai_types.ImageConfig(
            aspect_ratio=args.aspect_ratio,
            image_size=args.resolution,
        ),
    )

    try:
        response = client.models.generate_content(
            model=MODEL,
            contents=contents,
            config=config,
        )
    except Exception as exc:
        sys.stderr.write(f"error: Gemini API call failed: {exc}\n")
        sys.exit(1)

    image_bytes_out = None
    for candidate in response.candidates or []:
        for part in candidate.content.parts or []:
            if getattr(part, "inline_data", None) and part.inline_data.data:
                image_bytes_out = part.inline_data.data
                break
        if image_bytes_out:
            break

    if not image_bytes_out:
        sys.stderr.write("error: no image returned in response\n")
        sys.exit(1)

    out_path = Path(args.filename)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(image_bytes_out)
    print(f"wrote {out_path} ({len(image_bytes_out):,} bytes)")


def main() -> None:
    args = parse_args()
    generate(args)


if __name__ == "__main__":
    main()
