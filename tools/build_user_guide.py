"""Build the Texture Workshop user guide PDF from DocSource with Asciidoctor PDF.

Usage:
    python tools/build_user_guide.py

Needs Ruby with the asciidoctor-pdf gem (gem install asciidoctor-pdf rouge).
The PDF is built to a temporary file first and then copied to
Documentation/TextureWorkshop_User_Guide.pdf, so an open PDF viewer cannot
leave you without a fresh build: if the copy fails, the temporary PDF is kept
and its path is printed.
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOC_SOURCE = ROOT / "DocSource"
SOURCE = DOC_SOURCE / "TextureWorkshop_User_Guide.adoc"
OUTPUT = ROOT / "Documentation" / "TextureWorkshop_User_Guide.pdf"


def find_asciidoctor_pdf() -> list[str]:
    for name in ("asciidoctor-pdf.bat", "asciidoctor-pdf.cmd", "asciidoctor-pdf"):
        found = shutil.which(name)
        if found:
            return [found]
    ruby = shutil.which("ruby")
    if ruby:
        return [ruby, "-S", "asciidoctor-pdf"]
    raise SystemExit("asciidoctor-pdf not found. Install Ruby, then: gem install asciidoctor-pdf rouge")


def check_versions() -> None:
    """Warn when the guide's :appversion: does not match APP_VERSION in texture_workshop.py."""
    app = re.search(r'^APP_VERSION = "([^"]+)"', (ROOT / "texture_workshop.py").read_text(encoding="utf-8"), re.M)
    doc = re.search(r"^:appversion: (.+)$", SOURCE.read_text(encoding="utf-8"), re.M)
    if app and doc and app.group(1) != doc.group(1).strip():
        print(f"WARNING: guide :appversion: {doc.group(1).strip()} does not match APP_VERSION {app.group(1)}")


def main() -> int:
    check_versions()
    fd, tmp_name = tempfile.mkstemp(prefix="TextureWorkshop_User_Guide-", suffix=".pdf")
    os.close(fd)
    tmp = Path(tmp_name)
    cmd = find_asciidoctor_pdf() + ["--failure-level", "WARN", "-o", str(tmp), SOURCE.name]
    print("$", " ".join(cmd))
    result = subprocess.run(cmd, cwd=DOC_SOURCE)
    if result.returncode != 0 or tmp.stat().st_size == 0:
        tmp.unlink(missing_ok=True)
        print("Build failed; see the messages above.")
        return result.returncode or 1
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    try:
        shutil.copyfile(tmp, OUTPUT)
    except OSError as exc:
        print(f"WARNING: could not replace {OUTPUT} ({exc}). Is it open in a PDF viewer?")
        print(f"The new PDF was kept at: {tmp}")
        return 2
    tmp.unlink(missing_ok=True)
    print(f"User guide: {OUTPUT} ({OUTPUT.stat().st_size:,} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
