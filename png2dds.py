#!/usr/bin/env python3
"""Convert PNG/TGA/BMP images to DDS using ImageMagick.

The ImageMagick DDS coder interprets dds:mipmaps as the number of levels
below the base image.  Texture Workshop deliberately caps that value at 10:
this supplies the requested long mip chain without asking the coder to create
unbounded levels for unusually large images.
"""
from __future__ import annotations

import argparse
import math
import os
import shutil
import subprocess
import sys
from pathlib import Path

MAX_MIPMAP_LEVELS = 10
IMAGE_EXTENSIONS = {".png", ".tga", ".targa", ".bmp"}


def find_magick() -> str | None:
    configured = os.environ.get("MAGICK")
    if configured and Path(configured).exists():
        return configured
    application_dir = Path(sys.executable if getattr(sys, "frozen", False) else __file__).resolve().parent
    bundled = application_dir / "ImageMagick" / "magick.exe"
    if bundled.exists():
        return str(bundled)
    return shutil.which("magick.exe") or shutil.which("magick")


def image_info(magick: str, source: Path) -> tuple[int, int, bool]:
    proc = subprocess.run(
        [magick, "identify", "-format", "%w %h %[opaque]", str(source)],
        capture_output=True,
        text=True,
        errors="replace",
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or f"cannot read image: {source}")
    fields = proc.stdout.strip().split()
    if len(fields) != 3:
        raise RuntimeError(f"unexpected ImageMagick identify output for {source}")
    try:
        width, height = int(fields[0]), int(fields[1])
    except ValueError as exc:
        raise RuntimeError(f"invalid image dimensions for {source}") from exc
    return width, height, fields[2].lower() == "true"


def mipmap_levels(width: int, height: int, enabled: bool) -> int:
    if not enabled:
        return 0
    return min(MAX_MIPMAP_LEVELS, max(0, int(math.log2(max(width, height)))))


def convert(magick: str, source: Path, destination: Path, compression: str, mipmaps: str) -> None:
    width, height, opaque = image_info(magick, source)
    if compression == "auto":
        compression = "dxt1" if opaque else "dxt5"
    mip_count = mipmap_levels(width, height, mipmaps == "generate")
    destination.parent.mkdir(parents=True, exist_ok=True)
    command = [
        magick,
        str(source),
        "-define",
        f"dds:compression={compression}",
        "-define",
        f"dds:mipmaps={mip_count}",
        str(destination),
    ]
    proc = subprocess.run(command, capture_output=True, text=True, errors="replace")
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or f"ImageMagick failed for {source}")
    if not destination.exists():
        raise RuntimeError(f"ImageMagick did not create {destination}")
    print(f"{source} -> {destination} ({width}x{height}, {compression}, {mip_count} mipmaps)")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Convert PNG textures to DDS using ImageMagick.")
    parser.add_argument("source_arg", nargs="?", help="PNG/TGA/BMP file or folder")
    parser.add_argument("-s", "--source", dest="source_opt", help="PNG/TGA/BMP file or folder")
    parser.add_argument("-d", "--destination", "-o", "--out", default="dds", help="DDS output file or folder")
    parser.add_argument("-r", "--recursive", action="store_true", help="Process image files below a source folder recursively")
    parser.add_argument("--compression", choices=("auto", "dxt1", "dxt5"), default="auto")
    parser.add_argument("--mipmaps", choices=("none", "generate"), default="none")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    source_name = args.source_opt or args.source_arg
    if not source_name:
        print("ERROR: source image is required", file=sys.stderr)
        return 2
    source = Path(source_name)
    destination = Path(args.destination)
    magick = find_magick()
    if not source.exists():
        print(f"ERROR: source image or folder not found: {source}", file=sys.stderr)
        return 2
    if not magick:
        print("ERROR: ImageMagick not found in PATH. Install ImageMagick 7.x and ensure magick.exe is available.")
        return 1
    try:
        if source.is_file():
            convert(magick, source, destination, args.compression, args.mipmaps)
        elif source.is_dir():
            pattern = "**/*" if args.recursive else "*"
            images = sorted(p for p in source.glob(pattern) if p.is_file() and p.suffix.lower() in IMAGE_EXTENSIONS)
            if not images:
                print(f"No supported images found in {source}")
                return 0
            for image in images:
                relative = image.relative_to(source).with_suffix(".dds")
                convert(magick, image, destination / relative, args.compression, args.mipmaps)
        else:
            print(f"ERROR: source is neither a file nor a folder: {source}")
            return 2
    except RuntimeError as exc:
        print(f"ERROR: {exc}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
