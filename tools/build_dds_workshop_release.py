from __future__ import annotations

import hashlib
import shutil
import subprocess
import sys
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP_VERSION = None
RELEASE_NAME = None
DIST = ROOT / "dist"
BUILD = ROOT / "build"
APP_EXE_NAME = "DDSWorkshop.exe"
IMAGEMAGICK_VERSION = "7.1.2-31"
IMAGEMAGICK_ARCHIVE = f"ImageMagick-{IMAGEMAGICK_VERSION}-portable-Q16-x64.7z"
IMAGEMAGICK_URL = f"https://github.com/ImageMagick/ImageMagick/releases/download/{IMAGEMAGICK_VERSION}/{IMAGEMAGICK_ARCHIVE}"
IMAGEMAGICK_SHA256 = "33d8b47bb404a6b30c672195795e64a8ce0c807f9bba084e359ff086d6c5d50d"
IMAGEMAGICK_DOWNLOAD = ROOT / "third_party" / "downloads" / IMAGEMAGICK_ARCHIVE
IMAGEMAGICK_DIR = ROOT / "ImageMagick"


def read_app_version() -> str:
    namespace: dict[str, object] = {}
    text = (ROOT / "dds_workshop.py").read_text(encoding="utf-8")
    for line in text.splitlines():
        if line.startswith("APP_VERSION"):
            exec(line, namespace)
            return str(namespace["APP_VERSION"])
    raise RuntimeError("APP_VERSION not found in dds_workshop.py")


def run(cmd: list[str]) -> None:
    print("$", " ".join(cmd))
    subprocess.run(cmd, cwd=ROOT, check=True)


def copytree_clean(src: Path, dst: Path) -> None:
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))


def copy_required(src: Path, dst: Path) -> None:
    if not src.exists():
        raise FileNotFoundError(src)
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def verify_sha256(path: Path, expected: str) -> None:
    actual = sha256(path)
    if actual.lower() != expected.lower():
        raise RuntimeError(f"SHA256 mismatch for {path}\nexpected: {expected}\nactual:   {actual}")


def download_file(url: str, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    tmp = dst.with_suffix(dst.suffix + ".tmp")
    if tmp.exists():
        tmp.unlink()
    print(f"Downloading {url}")
    with urllib.request.urlopen(url, timeout=120) as response, tmp.open("wb") as fh:
        shutil.copyfileobj(response, fh)
    tmp.replace(dst)


def extract_7z_with_7zip(archive: Path, dst: Path) -> None:
    seven_zip = shutil.which("7z.exe") or shutil.which("7z")
    if not seven_zip:
        raise RuntimeError(
            "7-Zip is required to extract the ImageMagick portable .7z archive. "
            "Install 7-Zip or run: choco install 7zip -y"
        )
    if dst.exists():
        shutil.rmtree(dst)
    dst.mkdir(parents=True, exist_ok=True)
    run([seven_zip, "x", "-y", str(archive), f"-o{dst}"])


def ensure_imagemagick() -> None:
    magick_exe = IMAGEMAGICK_DIR / "magick.exe"
    if magick_exe.exists():
        print(f"Using existing ImageMagick: {magick_exe}")
    else:
        if not IMAGEMAGICK_DOWNLOAD.exists():
            download_file(IMAGEMAGICK_URL, IMAGEMAGICK_DOWNLOAD)
        verify_sha256(IMAGEMAGICK_DOWNLOAD, IMAGEMAGICK_SHA256)
        extract_7z_with_7zip(IMAGEMAGICK_DOWNLOAD, IMAGEMAGICK_DIR)
    if not magick_exe.exists():
        raise FileNotFoundError(f"Expected ImageMagick executable after extraction: {magick_exe}")
    verify_sha256(IMAGEMAGICK_DOWNLOAD, IMAGEMAGICK_SHA256)
    copy_required(IMAGEMAGICK_DIR / "LICENSE.txt", ROOT / "THIRD_PARTY_LICENSES" / "ImageMagick-LICENSE.txt")
    copy_required(IMAGEMAGICK_DIR / "NOTICE.txt", ROOT / "THIRD_PARTY_LICENSES" / "ImageMagick-UPSTREAM-NOTICE.txt")


def zip_dir(src_dir: Path, zip_path: Path) -> None:
    if zip_path.exists():
        zip_path.unlink()
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for path in sorted(src_dir.rglob("*")):
            if path.is_file():
                zf.write(path, path.relative_to(src_dir.parent))


def main() -> int:
    version = read_app_version()
    release_name = f"DDSWorkshop-{version}"
    release_dir = DIST / release_name
    zip_path = DIST / f"{release_name}.zip"

    ensure_imagemagick()
    run([sys.executable, "-m", "py_compile", "dds_workshop.py", "test_dds_workshop.py", "tools/build_dds_workshop_assets.py"])
    run([sys.executable, "-m", "unittest", "-v", "test_dds_workshop.py"])

    run([
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--onefile",
        "--windowed",
        "--name",
        "DDSWorkshop",
        "--icon",
        str(ROOT / "assets" / "DDSWorkshop_RSS.ico"),
        "--add-data",
        f"{ROOT / 'assets'};assets",
        str(ROOT / "dds_workshop.py"),
    ])

    if release_dir.exists():
        shutil.rmtree(release_dir)
    release_dir.mkdir(parents=True)

    copy_required(DIST / APP_EXE_NAME, release_dir / APP_EXE_NAME)
    copy_required(ROOT / "ace2png.exe", release_dir / "ace2png.exe")
    copy_required(ROOT / "png2dds.exe", release_dir / "png2dds.exe")
    copy_required(ROOT / "README.md", release_dir / "README.md")
    copy_required(ROOT / "SHA256SUMS.txt", release_dir / "SHA256SUMS-backend.txt")
    if (ROOT / "Documentation").exists():
        copytree_clean(ROOT / "Documentation", release_dir / "Documentation")
    copytree_clean(ROOT / "ImageMagick", release_dir / "ImageMagick")
    copytree_clean(ROOT / "THIRD_PARTY_LICENSES", release_dir / "THIRD_PARTY_LICENSES")

    manifest_lines = [
        f"DDS Workshop {version}",
        "",
        "Included files for normal users:",
        "- DDSWorkshop.exe: graphical front end",
        "- ace2png.exe: ACE to PNG backend",
        "- png2dds.exe: PNG to DDS backend",
        "- ImageMagick/: official portable ImageMagick runtime",
        "",
        "Checksums:",
    ]
    for path in sorted(release_dir.rglob("*")):
        if path.is_file():
            manifest_lines.append(f"{sha256(path)}  {path.relative_to(release_dir).as_posix()}")
    (release_dir / "SHA256SUMS.txt").write_text("\n".join(manifest_lines) + "\n", encoding="utf-8")

    zip_dir(release_dir, zip_path)
    print(f"Release folder: {release_dir}")
    print(f"Release zip   : {zip_path}")
    print(f"Zip SHA256    : {sha256(zip_path)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
