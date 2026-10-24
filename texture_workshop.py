#!/usr/bin/env python
"""Texture Workshop (formerly DDS Workshop) - ORZIP-style GUI frontend for ACE/PNG/DDS texture conversion tools."""
from __future__ import annotations

import configparser
import os
import queue
import shutil
import subprocess
import sys
import tempfile
import threading
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from tkinter import BOTH, END, LEFT, RIGHT, VERTICAL, X, Y, BooleanVar, StringVar, Tk, Toplevel, filedialog, messagebox, ttk
import tkinter as tk
import tkinter.font as tkfont
from tkinter.scrolledtext import ScrolledText

APP_NAME = "Texture Workshop"
APP_VERSION = "0.3.0"
APP_SUBTITLE = "ACE / PNG / DDS TEXTURE CONVERSION"
CONFIG_DIR = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming")) / "TextureWorkshop"
CONFIG_FILE = CONFIG_DIR / "settings.ini"
# Settings from the previous name (DDS Workshop); read once if no Texture Workshop settings exist yet.
LEGACY_CONFIG_FILE = CONFIG_DIR.parent / "DDSWorkshop" / "settings.ini"
IMAGE_EXTS = {".png", ".tga", ".bmp"}
ACE_SOURCE_EXTS = {".png", ".tga", ".targa", ".bmp"}
ACE_EXTS = {".ace"}
MODES = ("ace_png", "ace_dds", "image_dds", "image_ace")
ACE_INPUT_MODES = {"ace_png", "ace_dds"}
DDS_OUTPUT_MODES = {"image_dds", "ace_dds"}
SOURCE_COLUMNS = (("name", "File", 260), ("folder", "Folder", 360), ("type", "Type", 70), ("size", "Size", 90))
DDS_COMPRESSION_OPTIONS = (("Auto", "auto"), ("Force DXT1", "dxt1"), ("Force DXT5", "dxt5"))
DDS_MIPMAP_OPTIONS = (("No mipmaps", "none"), ("Generate mipmaps", "generate"))
ACE_FORMAT_OPTIONS = (("Structured (safest)", "structured"), ("DXT1", "dxt1"), ("DXT3", "dxt3"), ("DXT5", "dxt5"), ("Auto DXT", "auto-dxt"))
ACE_MIPMAP_OPTIONS = (("No mipmaps", "none"), ("Generate mipmaps (square power-of-two only)", "generate"))


@dataclass(frozen=True)
class ThemePalette:
    app_bg: str
    header_bg: str
    panel_bg: str
    input_bg: str
    log_bg: str
    log_fg: str
    text_fg: str
    help_fg: str
    accent_fg: str
    border: str
    button_bg: str
    primary_button_bg: str
    ready_bg: str
    busy_bg: str
    tree_selected_bg: str
    tree_selected_fg: str


THEMES: dict[str, ThemePalette] = {
    "Light": ThemePalette(
        app_bg="#f4f2ed",
        header_bg="#eee9e1",
        panel_bg="#f8f7f3",
        input_bg="#ffffff",
        log_bg="#202020",
        log_fg="#f4f4f4",
        text_fg="#2e2e2e",
        help_fg="#555555",
        accent_fg="#7a4634",
        border="#8b6f5b",
        button_bg="#dcefe2",
        primary_button_bg="#cfe3d6",
        ready_bg="#fff0c7",
        busy_bg="#d9edf7",
        tree_selected_bg="#cfe3d6",
        tree_selected_fg="#000000",
    ),
    "Dark": ThemePalette(
        app_bg="#2D2D2D",
        header_bg="#262626",
        panel_bg="#222222",
        input_bg="#303030",
        log_bg="#181818",
        log_fg="#F0F0F0",
        text_fg="#F0F0F0",
        help_fg="#CDCDCD",
        accent_fg="#E2B27E",
        border="#5C5C5C",
        button_bg="#343434",
        primary_button_bg="#3A3A3A",
        ready_bg="#EBAA51",
        busy_bg="#3A3A3A",
        tree_selected_bg="#CD8434",
        tree_selected_fg="#181818",
    ),
}


def app_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def bundled_dir() -> Path:
    return Path(getattr(sys, "_MEIPASS", app_dir())).resolve()


def app_icon_path() -> Path:
    for base in (bundled_dir(), app_dir()):
        candidate = base / "assets" / "TextureWorkshop_RSS.ico"
        if candidate.exists():
            return candidate
    return app_dir() / "assets" / "TextureWorkshop_RSS.ico"


def banner_image_path() -> Path:
    for base in (bundled_dir(), app_dir()):
        candidate = base / "assets" / "TextureWorkshop_RSS.png"
        if candidate.exists():
            return candidate
    return app_dir() / "assets" / "TextureWorkshop_RSS.png"


def resolve_tool(saved: str, names: tuple[str, ...]) -> str:
    for base in (app_dir(),):
        for name in names:
            candidate = base / name
            if candidate.exists():
                return str(candidate)
    if saved and Path(saved).exists():
        return saved
    for base in (Path.cwd(),):
        for name in names:
            candidate = base / name
            if candidate.exists():
                return str(candidate)
    for name in names:
        found = shutil.which(name)
        if found:
            return found
    return str(app_dir() / names[0])


def resolve_magick(saved: str) -> str:
    for base in (app_dir(),):
        for relative in (Path("ImageMagick") / "magick.exe", Path("magick.exe"), Path("magick")):
            candidate = base / relative
            if candidate.exists():
                return str(candidate)
    if saved and Path(saved).exists():
        return saved
    for base in (bundled_dir(), Path.cwd()):
        for relative in (Path("ImageMagick") / "magick.exe", Path("magick.exe"), Path("magick")):
            candidate = base / relative
            if candidate.exists():
                return str(candidate)
    return shutil.which("magick.exe") or shutil.which("magick") or str(app_dir() / "ImageMagick" / "magick.exe")


def command_available(command: str) -> bool:
    if not command:
        return False
    path = Path(command)
    if path.exists():
        return True
    return shutil.which(command) is not None


def tool_environment(magick_cmd: str) -> dict[str, str]:
    env = os.environ.copy()
    magick_path = Path(magick_cmd)
    if magick_path.exists():
        current_path = env.get("PATH", "")
        env["PATH"] = str(magick_path.parent) + os.pathsep + current_path
        env.setdefault("MAGICK_HOME", str(magick_path.parent))
    return env


def output_path_for(source: Path, source_root: Path | None, output_root: Path | None, suffix: str) -> Path:
    if output_root is None:
        return source.with_suffix(suffix)
    if source_root is not None:
        try:
            rel = source.relative_to(source_root)
        except ValueError:
            rel = Path(source.name)
        return (output_root / rel).with_suffix(suffix)
    return output_root / source.with_suffix(suffix).name


def collect_sources(source: Path, mode: str, recursive: bool) -> list[Path]:
    if source.is_file():
        candidates = [source]
    elif source.is_dir():
        pattern = "**/*" if recursive else "*"
        candidates = [p for p in source.glob(pattern) if p.is_file()]
    else:
        return []
    if mode in ACE_INPUT_MODES:
        allowed = ACE_EXTS
    elif mode == "image_ace":
        allowed = ACE_SOURCE_EXTS
    else:
        allowed = IMAGE_EXTS
    return sorted(p for p in candidates if p.suffix.lower() in allowed)


def format_size(size: int) -> str:
    if size < 1024:
        return f"{size} B"
    if size < 1024 * 1024:
        return f"{size / 1024:.1f} KB"
    return f"{size / (1024 * 1024):.1f} MB"


def display_folder_for_source(path: Path, source_root: Path | None) -> str:
    """Return a non-blank folder label for the source file list."""
    if source_root is None:
        return str(path.parent)
    try:
        rel_parent = path.parent.relative_to(source_root)
    except ValueError:
        return str(path.parent)
    if str(rel_parent) == ".":
        return source_root.name or str(source_root)
    return str(Path(source_root.name) / rel_parent)


def backup_existing(path: Path) -> Path:
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup = path.with_name(f"{path.name}.{stamp}.bak")
    index = 1
    while backup.exists():
        backup = path.with_name(f"{path.name}.{stamp}-{index}.bak")
        index += 1
    shutil.copy2(path, backup)
    return backup


def ensure_overwrite_policy(path: Path, policy: str) -> tuple[bool, str]:
    if not path.exists():
        return True, ""
    if policy == "skip":
        return False, f"SKIP existing output: {path}"
    if policy == "backup":
        backup = backup_existing(path)
        path.unlink()
        return True, f"Backed up existing output: {backup}"
    if policy == "overwrite":
        path.unlink()
        return True, f"Overwrite existing output: {path}"
    return False, f"SKIP unknown overwrite policy for: {path}"


def subprocess_window_options() -> dict[str, object]:
    if os.name != "nt":
        return {}
    startupinfo = subprocess.STARTUPINFO()
    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startupinfo.wShowWindow = subprocess.SW_HIDE
    return {"startupinfo": startupinfo, "creationflags": subprocess.CREATE_NO_WINDOW}


def run_command(cmd: list[str], cwd: Path, log, env: dict[str, str] | None = None) -> int:
    log("$ " + " ".join(f'"{x}"' if " " in x else x for x in cmd))
    try:
        proc = subprocess.Popen(
            cmd,
            cwd=str(cwd),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            errors="replace",
            **subprocess_window_options(),
        )
    except FileNotFoundError as exc:
        raise RuntimeError(f"Required external program not found: {cmd[0]}") from exc
    assert proc.stdout is not None
    for line in proc.stdout:
        log(line.rstrip())
    return proc.wait()


def png2dds_command(png2dds: str, source: Path, destination: Path, compression: str, mipmaps: str) -> list[str]:
    return [png2dds, str(source), "--destination", str(destination), "--compression", compression, "--mipmaps", mipmaps]


def png2ace_command(png2ace: str, source: Path, destination: Path, ace_format: str, mipmaps: str) -> list[str]:
    cmd = [png2ace, str(source), str(destination), "--format", ace_format]
    if mipmaps == "generate":
        cmd.append("--mipmaps")
    return cmd


class TextureWorkshopApp:
    def __init__(self, root: Tk) -> None:
        self.root = root
        root.title(f"{APP_NAME} {APP_VERSION}")
        self.config = self.load_config()
        saved_theme = self.config.get("settings", "theme", fallback="Light")
        self.theme_name = StringVar(value=saved_theme if saved_theme in THEMES else "Light")
        root.configure(bg=self.palette().app_bg)
        try:
            root.iconbitmap(default=str(app_icon_path()))
        except Exception:
            pass
        self.banner_image = None
        self.header = None
        self.badge_label = None
        self.title_box = None
        self.title_label = None
        self.subtitle_label = None
        self.version_label = None
        self.queue: queue.Queue[str] = queue.Queue()
        self.worker: threading.Thread | None = None
        self.abort_requested = False
        self.log_after_id = None
        self._clam_theme_applied = False

        self.source_path = StringVar(value=self.config.get("settings", "source_path", fallback=os.getcwd()))
        self.use_source_output = BooleanVar(value=self.config.getboolean("settings", "use_source_output", fallback=True))
        self.output_path = StringVar(value=self.config.get("settings", "output_path", fallback=str(Path.cwd() / "converted")))
        saved_mode = self.config.get("settings", "mode", fallback="ace_png")
        self.mode = StringVar(value=saved_mode if saved_mode in MODES else "ace_png")
        self.recursive = BooleanVar(value=self.config.getboolean("settings", "recursive", fallback=False))
        self.keep_intermediate = BooleanVar(value=self.config.getboolean("settings", "keep_intermediate", fallback=False))
        self.overwrite_policy = StringVar(value=self.config.get("settings", "overwrite_policy", fallback="backup"))
        saved_compression = self.config.get("settings", "dds_compression", fallback="auto")
        self.dds_compression = StringVar(value=saved_compression if saved_compression in {value for _label, value in DDS_COMPRESSION_OPTIONS} else "auto")
        saved_mipmaps = self.config.get("settings", "dds_mipmaps", fallback="none")
        self.dds_mipmaps = StringVar(value=saved_mipmaps if saved_mipmaps in {value for _label, value in DDS_MIPMAP_OPTIONS} else "none")
        saved_ace_format = self.config.get("settings", "ace_format", fallback="structured")
        self.ace_format = StringVar(value=saved_ace_format if saved_ace_format in {value for _label, value in ACE_FORMAT_OPTIONS} else "structured")
        saved_ace_mipmaps = self.config.get("settings", "ace_mipmaps", fallback="none")
        self.ace_mipmaps = StringVar(value=saved_ace_mipmaps if saved_ace_mipmaps in {value for _label, value in ACE_MIPMAP_OPTIONS} else "none")
        self.ace2png_cmd = StringVar(value=resolve_tool(self.config.get("settings", "ace2png_cmd", fallback=""), ("ace2png.exe", "ace2png")))
        self.png2dds_cmd = StringVar(value=resolve_tool(self.config.get("settings", "png2dds_cmd", fallback=""), ("png2dds.exe", "png2dds")))
        self.png2ace_cmd = StringVar(value=resolve_tool(self.config.get("settings", "png2ace_cmd", fallback=""), ("png2ace.exe", "png2ace")))
        self.magick_cmd = StringVar(value=resolve_magick(self.config.get("settings", "magick_cmd", fallback="")))
        self.source_files: list[Path] = []
        self.source_item_paths: dict[str, Path] = {}

        self.configure_fonts()
        self.configure_style()
        self.build_ui()
        self.source_path.trace_add("write", lambda *_: self.refresh_source_list())
        self.mode.trace_add("write", lambda *_: self.refresh_source_list())
        root.geometry("940x760")
        root.minsize(820, 620)
        self.root.bind("<Destroy>", self.on_destroy, add="+")
        self.schedule_log_drain()

    def configure_fonts(self) -> None:
        for name in ("TkDefaultFont", "TkTextFont", "TkMenuFont", "TkCaptionFont", "TkIconFont"):
            try:
                tkfont.nametofont(name).configure(family="Segoe UI", size=9)
            except Exception:
                pass

    def palette(self) -> ThemePalette:
        return THEMES.get(self.theme_name.get(), THEMES["Light"])

    def configure_style(self) -> None:
        colors = self.palette()
        style = ttk.Style(self.root)
        if not self._clam_theme_applied:
            try:
                style.theme_use("clam")
            except Exception:
                pass
            self._clam_theme_applied = True
        style.configure("TFrame", background=colors.app_bg)
        style.configure("Panel.TFrame", background=colors.panel_bg)
        style.configure("TLabel", background=colors.app_bg, foreground=colors.text_fg)
        style.configure("Panel.TLabel", background=colors.panel_bg, foreground=colors.text_fg)
        style.configure("Help.TLabel", background=colors.panel_bg, foreground=colors.help_fg)
        style.configure("TLabelframe", background=colors.panel_bg, foreground=colors.text_fg, bordercolor=colors.border)
        style.configure("TLabelframe.Label", background=colors.app_bg, foreground=colors.accent_fg, font=("Segoe UI", 9, "bold"))
        style.configure("TButton", background=colors.button_bg, foreground=colors.text_fg, bordercolor=colors.border)
        style.configure("Primary.TButton", background=colors.primary_button_bg, foreground=colors.text_fg, font=("Segoe UI", 10, "bold"))
        style.configure("TEntry", fieldbackground=colors.input_bg, foreground=colors.text_fg, insertcolor=colors.text_fg, bordercolor=colors.border, lightcolor=colors.border, darkcolor=colors.border)
        style.configure("TCombobox", fieldbackground=colors.input_bg, foreground=colors.text_fg, background=colors.input_bg, insertcolor=colors.text_fg, bordercolor=colors.border)
        style.map("TCombobox", fieldbackground=[("readonly", colors.input_bg)], foreground=[("readonly", colors.text_fg)])
        style.configure("TRadiobutton", background=colors.panel_bg, foreground=colors.text_fg)
        style.configure("TCheckbutton", background=colors.panel_bg, foreground=colors.text_fg)
        style.configure("Treeview", background=colors.input_bg, fieldbackground=colors.input_bg, foreground=colors.text_fg, rowheight=22, bordercolor=colors.border)
        style.configure("Treeview.Heading", background=colors.header_bg, foreground=colors.text_fg, font=("Segoe UI", 9, "bold"))
        style.map("Treeview", background=[("selected", colors.tree_selected_bg)], foreground=[("selected", colors.tree_selected_fg)])

    def panel(self, parent, text: str):
        frame = ttk.LabelFrame(parent, text=text, padding=10)
        return frame

    def build_ui(self) -> None:
        self.build_menu()
        colors = self.palette()
        outer = ttk.Frame(self.root, padding=12)
        outer.pack(fill=BOTH, expand=True)

        self.header = tk.Frame(outer, bg=colors.header_bg, highlightbackground=colors.border, highlightthickness=1)
        self.header.pack(fill=X, pady=(0, 10))
        try:
            self.banner_image = tk.PhotoImage(file=str(banner_image_path())).subsample(4, 4)
            self.badge_label = tk.Label(self.header, image=self.banner_image, bg=colors.header_bg, padx=8, pady=6)
        except Exception:
            self.badge_label = tk.Label(self.header, text="DDS", bg=colors.accent_fg, fg="white", font=("Segoe UI", 15, "bold"), padx=14, pady=8)
        self.badge_label.pack(side=LEFT, padx=10, pady=10)
        self.title_box = tk.Frame(self.header, bg=colors.header_bg)
        self.title_box.pack(side=LEFT, fill=X, expand=True)
        self.title_label = tk.Label(self.title_box, text=APP_NAME, bg=colors.header_bg, fg=colors.text_fg, font=("Segoe UI", 18, "bold"))
        self.title_label.pack(anchor="w")
        self.subtitle_label = tk.Label(self.title_box, text=APP_SUBTITLE, bg=colors.header_bg, fg=colors.accent_fg, font=("Segoe UI", 8, "bold"))
        self.subtitle_label.pack(anchor="w")
        self.version_label = tk.Label(self.header, text=f"v{APP_VERSION}", bg=colors.ready_bg, fg=colors.text_fg, padx=10, pady=4)
        self.version_label.pack(side=RIGHT, padx=12)

        scroll_area = ttk.Frame(outer)
        scroll_area.pack(fill=BOTH, expand=True)
        self.content_canvas = tk.Canvas(scroll_area, bg=colors.app_bg, highlightthickness=0, borderwidth=0)
        self.content_scrollbar = ttk.Scrollbar(scroll_area, orient=VERTICAL, command=self.content_canvas.yview)
        self.content_canvas.configure(yscrollcommand=self.content_scrollbar.set)
        self.content_scrollbar.pack(side=RIGHT, fill=Y)
        self.content_canvas.pack(side=LEFT, fill=BOTH, expand=True)
        self.content = ttk.Frame(self.content_canvas)
        self.content_window = self.content_canvas.create_window((0, 0), window=self.content, anchor="nw")
        self.content.bind("<Configure>", lambda event: self.content_canvas.configure(scrollregion=self.content_canvas.bbox("all")))
        self.content_canvas.bind("<Configure>", lambda event: self.content_canvas.itemconfigure(self.content_window, width=event.width))
        self.content_canvas.bind_all("<MouseWheel>", self.on_mouse_wheel)

        setup = self.panel(self.content, "Run Setup")
        setup.pack(fill=X, pady=(0, 8))
        setup.columnconfigure(1, weight=1)
        ttk.Label(setup, text="Source", style="Panel.TLabel").grid(row=0, column=0, sticky="w", padx=(0, 6), pady=3)
        ttk.Entry(setup, textvariable=self.source_path).grid(row=0, column=1, sticky="ew", pady=3)
        ttk.Button(setup, text="File...", command=self.browse_source_file).grid(row=0, column=2, padx=(6, 0), pady=3)
        ttk.Button(setup, text="Folder...", command=self.browse_source_folder).grid(row=0, column=3, padx=(6, 0), pady=3)
        ttk.Label(setup, text="Output", style="Panel.TLabel").grid(row=1, column=0, sticky="w", padx=(0, 6), pady=3)
        ttk.Checkbutton(setup, text="Use source folder", variable=self.use_source_output, command=self.update_output_state).grid(row=1, column=1, sticky="w", pady=3)
        self.output_entry = ttk.Entry(setup, textvariable=self.output_path)
        self.output_entry.grid(row=2, column=1, sticky="ew", pady=3)
        ttk.Button(setup, text="Output Folder...", command=self.browse_output_folder).grid(row=2, column=2, columnspan=2, sticky="ew", padx=(6, 0), pady=3)

        self.source_count_label = ttk.Label(setup, text="No source files listed", style="Help.TLabel")
        self.source_count_label.grid(row=3, column=0, columnspan=4, sticky="w", pady=(8, 2))
        list_frame = ttk.Frame(setup, style="Panel.TFrame")
        list_frame.grid(row=4, column=0, columnspan=4, sticky="ew")
        list_frame.columnconfigure(0, weight=1)
        self.source_tree = ttk.Treeview(list_frame, columns=[col for col, _title, _width in SOURCE_COLUMNS], show="headings", height=7, selectmode="browse")
        for col, title, width in SOURCE_COLUMNS:
            self.source_tree.heading(col, text=title)
            self.source_tree.column(col, width=width, minwidth=max(50, width // 2), anchor="w")
        source_scroll = ttk.Scrollbar(list_frame, orient=VERTICAL, command=self.source_tree.yview)
        self.source_tree.configure(yscrollcommand=source_scroll.set)
        self.source_tree.grid(row=0, column=0, sticky="ew")
        source_scroll.grid(row=0, column=1, sticky="ns")

        mode_panel = self.panel(self.content, "Conversion Mode")
        mode_panel.pack(fill=X, pady=(0, 8))
        mode_buttons = (
            ("ACE to editable PNG", "ace_png", 0, 0),
            ("ACE directly to DDS", "ace_dds", 0, 1),
            ("PNG/TGA/BMP to DDS", "image_dds", 1, 0),
            ("PNG/TGA/BMP to ACE", "image_ace", 1, 1),
        )
        for text, value, row, column in mode_buttons:
            ttk.Radiobutton(mode_panel, text=text, variable=self.mode, value=value, command=self.update_mode_state).grid(row=row, column=column, sticky="w", padx=(0, 28), pady=2)

        opts = self.panel(self.content, "Batch and Existing File Options")
        opts.pack(fill=X, pady=(0, 8))
        ttk.Checkbutton(opts, text="Include subfolders", variable=self.recursive, command=self.refresh_source_list).grid(row=0, column=0, sticky="w", padx=(0, 18))
        self.keep_intermediate_check = ttk.Checkbutton(opts, text="Keep intermediate PNG files for ACE to DDS", variable=self.keep_intermediate)
        self.keep_intermediate_check.grid(row=0, column=1, sticky="w", padx=(0, 18))
        ttk.Label(opts, text="Existing outputs:", style="Panel.TLabel").grid(row=1, column=0, sticky="w", pady=(8, 0))
        for idx, (label, value) in enumerate((("Skip", "skip"), ("Overwrite", "overwrite"), ("Backup then overwrite", "backup"))):
            ttk.Radiobutton(opts, text=label, variable=self.overwrite_policy, value=value).grid(row=1, column=idx + 1, sticky="w", pady=(8, 0), padx=(0, 18))
        ttk.Label(opts, text="DDS compression:", style="Panel.TLabel").grid(row=2, column=0, sticky="w", pady=(8, 0))
        self.dds_option_widgets: list[ttk.Radiobutton] = []
        for idx, (label, value) in enumerate(DDS_COMPRESSION_OPTIONS):
            button = ttk.Radiobutton(opts, text=label, variable=self.dds_compression, value=value)
            button.grid(row=2, column=idx + 1, sticky="w", pady=(8, 0), padx=(0, 18))
            self.dds_option_widgets.append(button)
        ttk.Label(opts, text="DDS mipmaps:", style="Panel.TLabel").grid(row=3, column=0, sticky="w", pady=(8, 0))
        for idx, (label, value) in enumerate(DDS_MIPMAP_OPTIONS):
            button = ttk.Radiobutton(opts, text=label, variable=self.dds_mipmaps, value=value)
            button.grid(row=3, column=idx + 1, sticky="w", pady=(8, 0), padx=(0, 18))
            self.dds_option_widgets.append(button)

        ace_opts = self.panel(self.content, "ACE Output Options")
        ace_opts.pack(fill=X, pady=(0, 8))
        self.ace_option_widgets: list[ttk.Radiobutton] = []
        ttk.Label(ace_opts, text="ACE format:", style="Panel.TLabel").grid(row=0, column=0, sticky="w")
        for idx, (label, value) in enumerate(ACE_FORMAT_OPTIONS):
            button = ttk.Radiobutton(ace_opts, text=label, variable=self.ace_format, value=value)
            button.grid(row=0, column=idx + 1, sticky="w", padx=(0, 14))
            self.ace_option_widgets.append(button)
        ttk.Label(ace_opts, text="ACE mipmaps:", style="Panel.TLabel").grid(row=1, column=0, sticky="w", pady=(8, 0))
        for idx, (label, value) in enumerate(ACE_MIPMAP_OPTIONS):
            button = ttk.Radiobutton(ace_opts, text=label, variable=self.ace_mipmaps, value=value)
            button.grid(row=1, column=1 + idx, columnspan=1 if idx == 0 else 4, sticky="w", pady=(8, 0), padx=(0, 14))
            self.ace_option_widgets.append(button)
        ttk.Label(
            ace_opts,
            text="DXT3/DXT5 need a source with an alpha channel; images without alpha are skipped. Auto DXT picks DXT1 or DXT5.",
            style="Help.TLabel",
        ).grid(row=2, column=0, columnspan=6, sticky="w", pady=(8, 0))

        status = self.panel(self.content, "Status")
        status.pack(fill=X, pady=(0, 8))
        self.status_label = ttk.Label(status, text="READY", style="Panel.TLabel")
        self.status_label.pack(side=LEFT)
        self.run_button = ttk.Button(status, text="Run Conversion", style="Primary.TButton", command=self.start_run)
        self.run_button.pack(side=RIGHT, padx=(6, 0))
        self.abort_button = ttk.Button(status, text="Abort", command=self.abort, state="disabled")
        self.abort_button.pack(side=RIGHT, padx=(6, 0))

        log_panel = self.panel(self.content, "Output Log")
        log_panel.pack(fill=BOTH, expand=True)
        toolbar = ttk.Frame(log_panel, style="Panel.TFrame")
        toolbar.pack(fill=X)
        ttk.Button(toolbar, text="Clear Log", command=lambda: self.log.delete("1.0", END)).pack(side=RIGHT, padx=(6, 0))
        ttk.Button(toolbar, text="Copy Log", command=self.copy_log).pack(side=RIGHT)
        self.log = ScrolledText(log_panel, height=12, bg=colors.log_bg, fg=colors.log_fg, insertbackground=colors.log_fg, state="disabled")
        self.log.pack(fill=BOTH, expand=True, pady=(6, 0))
        self.update_output_state()
        self.update_mode_state()
        self.refresh_source_list()

    def on_mouse_wheel(self, event) -> None:
        if hasattr(self, "content_canvas"):
            self.content_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def build_menu(self) -> None:
        menu = tk.Menu(self.root)
        file_menu = tk.Menu(menu, tearoff=False)
        file_menu.add_command(label="Settings...", command=self.open_settings)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.root.destroy)
        menu.add_cascade(label="File", menu=file_menu)
        help_menu = tk.Menu(menu, tearoff=False)
        help_menu.add_command(label="About", command=lambda: messagebox.showinfo(APP_NAME, f"{APP_NAME} {APP_VERSION}\nFormerly DDS Workshop\nFrontend for ace2png.exe, png2dds.exe and png2ace.exe", parent=self.root))
        menu.add_cascade(label="Help", menu=help_menu)
        self.root.config(menu=menu)

    def browse_source_file(self) -> None:
        path = filedialog.askopenfilename(parent=self.root, filetypes=[("Supported textures", "*.ace *.png *.tga *.targa *.bmp"), ("All files", "*.*")])
        if path:
            self.source_path.set(path)

    def browse_source_folder(self) -> None:
        path = filedialog.askdirectory(parent=self.root)
        if path:
            self.source_path.set(path)

    def browse_output_folder(self) -> None:
        path = filedialog.askdirectory(parent=self.root)
        if path:
            self.output_path.set(path)
            self.use_source_output.set(False)
            self.update_output_state()

    def update_output_state(self) -> None:
        self.output_entry.configure(state="disabled" if self.use_source_output.get() else "normal")

    def update_mode_state(self) -> None:
        mode = self.mode.get()
        self.keep_intermediate_check.configure(state="normal" if mode == "ace_dds" else "disabled")
        for widget in getattr(self, "dds_option_widgets", []):
            widget.configure(state="normal" if mode in DDS_OUTPUT_MODES else "disabled")
        for widget in getattr(self, "ace_option_widgets", []):
            widget.configure(state="normal" if mode == "image_ace" else "disabled")
        self.refresh_source_list()

    def refresh_source_list(self) -> None:
        if not hasattr(self, "source_tree"):
            return
        source = Path(self.source_path.get())
        mode = self.mode.get()
        recursive = self.recursive.get()
        files = collect_sources(source, mode, recursive)
        self.source_files = files
        self.source_item_paths.clear()
        self.source_tree.delete(*self.source_tree.get_children())
        source_root = source if source.is_dir() else source.parent if source.is_file() else None
        for path in files:
            folder = display_folder_for_source(path, source_root)
            try:
                size = format_size(path.stat().st_size)
            except OSError:
                size = ""
            item = self.source_tree.insert("", END, values=(path.name, folder, path.suffix.lower(), size))
            self.source_item_paths[item] = path
        label = f"{len(files)} source file(s) listed"
        if source.is_dir() and recursive:
            label += " including subfolders"
        elif source.is_dir():
            label += " in selected folder"
        elif source.is_file():
            label += " from selected file"
        self.source_count_label.configure(text=label)

    def apply_theme(self) -> None:
        colors = self.palette()
        self.root.configure(bg=colors.app_bg)
        self.configure_style()
        if self.header is not None:
            self.header.configure(bg=colors.header_bg, highlightbackground=colors.border)
        if self.badge_label is not None:
            if self.banner_image is not None:
                self.badge_label.configure(bg=colors.header_bg)
            else:
                self.badge_label.configure(bg=colors.accent_fg, fg="white")
        if self.title_box is not None:
            self.title_box.configure(bg=colors.header_bg)
        if self.title_label is not None:
            self.title_label.configure(bg=colors.header_bg, fg=colors.text_fg)
        if self.subtitle_label is not None:
            self.subtitle_label.configure(bg=colors.header_bg, fg=colors.accent_fg)
        if self.version_label is not None:
            self.version_label.configure(bg=colors.ready_bg, fg=colors.text_fg)
        if hasattr(self, "content_canvas"):
            self.content_canvas.configure(bg=colors.app_bg)
        if hasattr(self, "log"):
            self.log.configure(bg=colors.log_bg, fg=colors.log_fg, insertbackground=colors.log_fg)

    def apply_theme_from_settings(self) -> None:
        self.apply_theme()
        self.save_config()

    def open_settings(self) -> None:
        win = Toplevel(self.root)
        win.title("Texture Workshop Settings")
        win.configure(bg=self.palette().app_bg)
        win.transient(self.root)
        win.grab_set()
        frame = ttk.Frame(win, padding=12)
        frame.pack(fill=BOTH, expand=True)
        frame.columnconfigure(1, weight=1)
        ttk.Label(frame, text="ace2png executable").grid(row=0, column=0, sticky="w", padx=(0, 8), pady=4)
        ttk.Entry(frame, textvariable=self.ace2png_cmd, width=60).grid(row=0, column=1, sticky="ew", pady=4)
        ttk.Button(frame, text="Browse...", command=lambda: self.browse_tool(self.ace2png_cmd, win)).grid(row=0, column=2, padx=(8, 0), pady=4)
        ttk.Label(frame, text="png2dds executable").grid(row=1, column=0, sticky="w", padx=(0, 8), pady=4)
        ttk.Entry(frame, textvariable=self.png2dds_cmd, width=60).grid(row=1, column=1, sticky="ew", pady=4)
        ttk.Button(frame, text="Browse...", command=lambda: self.browse_tool(self.png2dds_cmd, win)).grid(row=1, column=2, padx=(8, 0), pady=4)
        ttk.Label(frame, text="png2ace executable").grid(row=2, column=0, sticky="w", padx=(0, 8), pady=4)
        ttk.Entry(frame, textvariable=self.png2ace_cmd, width=60).grid(row=2, column=1, sticky="ew", pady=4)
        ttk.Button(frame, text="Browse...", command=lambda: self.browse_tool(self.png2ace_cmd, win)).grid(row=2, column=2, padx=(8, 0), pady=4)
        ttk.Label(frame, text="ImageMagick magick executable").grid(row=3, column=0, sticky="w", padx=(0, 8), pady=4)
        ttk.Entry(frame, textvariable=self.magick_cmd, width=60).grid(row=3, column=1, sticky="ew", pady=4)
        ttk.Button(frame, text="Browse...", command=lambda: self.browse_tool(self.magick_cmd, win)).grid(row=3, column=2, padx=(8, 0), pady=4)
        ttk.Label(frame, text="Theme").grid(row=4, column=0, sticky="w", padx=(0, 8), pady=4)
        theme_box = ttk.Combobox(frame, textvariable=self.theme_name, values=list(THEMES), state="readonly", width=18)
        theme_box.grid(row=4, column=1, sticky="w", pady=4)
        theme_box.bind("<<ComboboxSelected>>", lambda _event: self.apply_theme_from_settings())
        ttk.Button(frame, text="Save", style="Primary.TButton", command=lambda: (self.save_config(), win.destroy())).grid(row=5, column=2, sticky="e", pady=(12, 0))

    def browse_tool(self, var: StringVar, parent) -> None:
        path = filedialog.askopenfilename(parent=parent, filetypes=[("Executable", "*.exe"), ("All files", "*.*")])
        if path:
            var.set(path)

    def append_log(self, text: str) -> None:
        self.log.configure(state="normal")
        self.log.insert(END, text + "\n")
        self.log.see(END)
        self.log.configure(state="disabled")

    def thread_log(self, text: str) -> None:
        self.queue.put(text)

    def drain_log_queue(self) -> None:
        while True:
            try:
                msg = self.queue.get_nowait()
            except queue.Empty:
                break
            self.append_log(msg)
        self.schedule_log_drain()

    def schedule_log_drain(self) -> None:
        if self.root.winfo_exists():
            self.log_after_id = self.root.after(100, self.drain_log_queue)

    def on_destroy(self, event) -> None:
        if event.widget is self.root:
            try:
                for after_id in self.root.tk.call("after", "info"):
                    try:
                        self.root.after_cancel(after_id)
                    except Exception:
                        pass
            except Exception:
                pass
            self.log_after_id = None

    def copy_log(self) -> None:
        self.root.clipboard_clear()
        self.root.clipboard_append(self.log.get("1.0", END))

    def set_running(self, running: bool) -> None:
        self.run_button.configure(state="disabled" if running else "normal")
        self.abort_button.configure(state="normal" if running else "disabled")
        self.status_label.configure(text="RUNNING" if running else "READY")

    def missing_support_files(self) -> list[str]:
        mode = self.mode.get()
        required: list[tuple[str, str]] = []
        if mode in ACE_INPUT_MODES:
            required.append(("Bundled ace2png.exe", str(app_dir() / "ace2png.exe")))
            required.append(("ace2png.exe", self.ace2png_cmd.get()))
        if mode == "image_ace":
            required.append(("Bundled png2ace.exe", str(app_dir() / "png2ace.exe")))
            required.append(("png2ace.exe", self.png2ace_cmd.get()))
        if mode in DDS_OUTPUT_MODES:
            required.append(("Bundled png2dds.exe", str(app_dir() / "png2dds.exe")))
            required.append(("Bundled ImageMagick magick.exe", str(app_dir() / "ImageMagick" / "magick.exe")))
            required.append(("png2dds.exe", self.png2dds_cmd.get()))
            required.append(("ImageMagick magick.exe", self.magick_cmd.get()))
        missing = []
        seen: set[str] = set()
        for label, command in required:
            line = f"{label}: {command or '(not configured)'}"
            if line not in seen and not command_available(command):
                missing.append(line)
                seen.add(line)
        return missing

    def log_support_paths(self) -> None:
        mode = self.mode.get()
        self.thread_log("Support files:")
        if mode in ACE_INPUT_MODES:
            self.thread_log(f"  ace2png    : {self.ace2png_cmd.get()}")
        if mode == "image_ace":
            self.thread_log(f"  png2ace    : {self.png2ace_cmd.get()}")
            self.thread_log(f"  ACE format : {self.ace_format.get()}")
            self.thread_log(f"  ACE mipmaps: {self.ace_mipmaps.get()}")
        if mode in DDS_OUTPUT_MODES:
            self.thread_log(f"  png2dds    : {self.png2dds_cmd.get()}")
            self.thread_log(f"  ImageMagick: {self.magick_cmd.get()}")
            self.thread_log(f"  DDS compression: {self.dds_compression.get()}")
            self.thread_log(f"  DDS mipmaps: {self.dds_mipmaps.get()}")

    def start_run(self) -> None:
        if self.worker and self.worker.is_alive():
            return
        self.save_config()
        source = Path(self.source_path.get())
        if not source.exists():
            messagebox.showerror(APP_NAME, "Source file or folder does not exist.", parent=self.root)
            return
        missing = self.missing_support_files()
        if missing:
            message = "Texture Workshop cannot run because required support files are missing:\n\n" + "\n".join(missing) + "\n\nUse Settings to point Texture Workshop at the missing executable, or restore the files beside TextureWorkshop.exe."
            self.append_log(message)
            messagebox.showerror(APP_NAME, message, parent=self.root)
            return
        self.abort_requested = False
        self.set_running(True)
        self.worker = threading.Thread(target=self.run_batch, daemon=True)
        self.worker.start()

    def abort(self) -> None:
        self.abort_requested = True
        self.thread_log("Abort requested. The current file will finish first.")

    def run_batch(self) -> None:
        ok = 0
        failed = 0
        skipped = 0
        try:
            source = Path(self.source_path.get()).resolve()
            mode = self.mode.get()
            output_root = None if self.use_source_output.get() else Path(self.output_path.get()).resolve()
            if output_root:
                output_root.mkdir(parents=True, exist_ok=True)
            files = collect_sources(source, mode, self.recursive.get())
            self.thread_log(f"Texture Workshop {APP_VERSION}")
            self.log_support_paths()
            self.thread_log(f"Found {len(files)} file(s).")
            for index, file_path in enumerate(files, start=1):
                if self.abort_requested:
                    self.thread_log("Batch aborted.")
                    break
                self.thread_log(f"\n[{index}/{len(files)}] {file_path}")
                try:
                    changed = self.process_one(file_path, source if source.is_dir() else None, output_root)
                except Exception as exc:
                    failed += 1
                    self.thread_log(f"ERROR: {exc}")
                    continue
                if changed is None:
                    skipped += 1
                elif changed:
                    ok += 1
                else:
                    failed += 1
            self.thread_log("\nConversion complete")
            self.thread_log(f"Succeeded: {ok}")
            self.thread_log(f"Skipped  : {skipped}")
            self.thread_log(f"Failed   : {failed}")
        finally:
            self.root.after(0, lambda: self.set_running(False))

    def process_one(self, file_path: Path, source_root: Path | None, output_root: Path | None) -> bool | None:
        mode = self.mode.get()
        if mode == "ace_png":
            out = output_path_for(file_path, source_root, output_root, ".png")
            return self.run_ace_to_png(file_path, out)
        if mode == "image_dds":
            return self.run_image_to_dds(file_path, source_root, output_root)
        if mode == "ace_dds":
            dds_out = output_path_for(file_path, source_root, output_root, ".dds")
            return self.run_ace_to_dds(file_path, dds_out)
        if mode == "image_ace":
            ace_out = output_path_for(file_path, source_root, output_root, ".ace")
            return self.run_image_to_ace(file_path, ace_out)
        raise ValueError(f"Unknown mode: {mode}")

    def run_ace_to_png(self, ace: Path, png_out: Path) -> bool | None:
        should_run, note = ensure_overwrite_policy(png_out, self.overwrite_policy.get())
        if note:
            self.thread_log(note)
        if not should_run:
            return None
        png_out.parent.mkdir(parents=True, exist_ok=True)
        rc = run_command([self.ace2png_cmd.get(), str(ace), "-o", str(png_out)], app_dir(), self.thread_log, env=tool_environment(self.magick_cmd.get()))
        return rc == 0 and png_out.exists()

    def run_image_to_dds(self, image: Path, source_root: Path | None, output_root: Path | None) -> bool | None:
        dds_out = output_path_for(image, source_root, output_root, ".dds")
        should_run, note = ensure_overwrite_policy(dds_out, self.overwrite_policy.get())
        if note:
            self.thread_log(note)
        if not should_run:
            return None
        dds_out.parent.mkdir(parents=True, exist_ok=True)
        if image.suffix.lower() == ".png":
            source_for_png2dds = image
            cleanup_dir = None
        else:
            cleanup_dir = tempfile.TemporaryDirectory(prefix="textureworkshop-")
            source_for_png2dds = Path(cleanup_dir.name) / (image.stem + ".png")
            rc = run_command([self.magick_cmd.get(), str(image), str(source_for_png2dds)], app_dir(), self.thread_log, env=tool_environment(self.magick_cmd.get()))
            if rc != 0 or not source_for_png2dds.exists():
                cleanup_dir.cleanup()
                return False
        try:
            rc = run_command(png2dds_command(self.png2dds_cmd.get(), source_for_png2dds, dds_out, self.dds_compression.get(), self.dds_mipmaps.get()), app_dir(), self.thread_log, env=tool_environment(self.magick_cmd.get()))
            return rc == 0 and dds_out.exists()
        finally:
            if cleanup_dir is not None:
                cleanup_dir.cleanup()

    def run_ace_to_dds(self, ace: Path, dds_out: Path) -> bool | None:
        should_run, note = ensure_overwrite_policy(dds_out, self.overwrite_policy.get())
        if note:
            self.thread_log(note)
        if not should_run:
            return None
        dds_out.parent.mkdir(parents=True, exist_ok=True)
        if self.keep_intermediate.get():
            png_out = dds_out.with_suffix(".png")
            cleanup_dir = None
        else:
            cleanup_dir = tempfile.TemporaryDirectory(prefix="textureworkshop-")
            png_out = Path(cleanup_dir.name) / (ace.stem + ".png")
        try:
            if not self.run_ace_to_png(ace, png_out):
                return False
            rc = run_command(png2dds_command(self.png2dds_cmd.get(), png_out, dds_out, self.dds_compression.get(), self.dds_mipmaps.get()), app_dir(), self.thread_log, env=tool_environment(self.magick_cmd.get()))
            return rc == 0 and dds_out.exists()
        finally:
            if cleanup_dir is not None:
                cleanup_dir.cleanup()

    def run_image_to_ace(self, image: Path, ace_out: Path) -> bool | None:
        """Convert with png2ace into a temp file, then apply the overwrite policy.

        png2ace exits 0 without writing anything when it deliberately skips an image
        (DXT3/DXT5 requested for a source without alpha), so an existing ACE file is
        only touched once a new one has actually been produced.
        """
        policy = self.overwrite_policy.get()
        if ace_out.exists() and policy == "skip":
            self.thread_log(f"SKIP existing output: {ace_out}")
            return None
        ace_out.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="textureworkshop-", dir=ace_out.parent) as td:
            temp_out = Path(td) / ace_out.name
            rc = run_command(png2ace_command(self.png2ace_cmd.get(), image, temp_out, self.ace_format.get(), self.ace_mipmaps.get()), app_dir(), self.thread_log)
            if rc != 0:
                return False
            if not temp_out.exists():
                self.thread_log(f"SKIP: png2ace did not write an ACE file for {image.name}")
                return None
            should_run, note = ensure_overwrite_policy(ace_out, policy)
            if note:
                self.thread_log(note)
            if not should_run:
                return None
            shutil.move(str(temp_out), str(ace_out))
        return ace_out.exists()

    def load_config(self) -> configparser.ConfigParser:
        cfg = configparser.ConfigParser()
        if CONFIG_FILE.exists():
            cfg.read(CONFIG_FILE)
        elif LEGACY_CONFIG_FILE.exists():
            cfg.read(LEGACY_CONFIG_FILE)
        if not cfg.has_section("settings"):
            cfg.add_section("settings")
        return cfg

    def save_config(self) -> None:
        cfg = self.config
        if not cfg.has_section("settings"):
            cfg.add_section("settings")
        values = {
            "source_path": self.source_path.get(),
            "use_source_output": str(self.use_source_output.get()),
            "output_path": self.output_path.get(),
            "mode": self.mode.get(),
            "recursive": str(self.recursive.get()),
            "keep_intermediate": str(self.keep_intermediate.get()),
            "overwrite_policy": self.overwrite_policy.get(),
            "dds_compression": self.dds_compression.get(),
            "dds_mipmaps": self.dds_mipmaps.get(),
            "ace_format": self.ace_format.get(),
            "ace_mipmaps": self.ace_mipmaps.get(),
            "theme": self.theme_name.get(),
            "ace2png_cmd": self.ace2png_cmd.get(),
            "png2dds_cmd": self.png2dds_cmd.get(),
            "png2ace_cmd": self.png2ace_cmd.get(),
            "magick_cmd": self.magick_cmd.get(),
        }
        for key, value in values.items():
            cfg.set("settings", key, value)
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        with CONFIG_FILE.open("w", encoding="utf-8") as fh:
            cfg.write(fh)


def main() -> None:
    root = Tk()
    TextureWorkshopApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
