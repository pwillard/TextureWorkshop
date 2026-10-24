import configparser
import struct
import tempfile
import zlib
import tkinter as tk
import unittest
from pathlib import Path

import texture_workshop as dw


def write_png(path: Path, width: int, height: int, rgba: bool) -> None:
    """Write a small solid-colour PNG without needing Pillow."""
    channels = 4 if rgba else 3
    pixel = bytes([200, 40, 40, 128][:channels])
    raw = b"".join(b"\x00" + pixel * width for _ in range(height))

    def chunk(kind: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)

    header = struct.pack(">IIBBBBB", width, height, 8, 6 if rgba else 2, 0, 0, 0)
    path.write_bytes(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", header) + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b""))


class TextureWorkshopHelperTests(unittest.TestCase):
    def test_collect_sources_filters_by_mode(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            for name in ["a.ace", "b.png", "c.tga", "d.bmp", "e.txt"]:
                (root / name).write_text("x")
            (root / "sub").mkdir()
            (root / "sub" / "z.ace").write_text("x")
            self.assertEqual([p.name for p in dw.collect_sources(root, "ace_png", False)], ["a.ace"])
            self.assertEqual([p.name for p in dw.collect_sources(root, "image_dds", False)], ["b.png", "c.tga", "d.bmp"])
            self.assertEqual([p.name for p in dw.collect_sources(root, "ace_dds", True)], ["a.ace", "z.ace"])
            (root / "f.targa").write_text("x")
            self.assertEqual([p.name for p in dw.collect_sources(root, "image_ace", False)], ["b.png", "c.tga", "d.bmp", "f.targa"])

    def test_output_paths_source_folder_and_preserved_tree(self):
        root = Path("C:/route/textures")
        source = root / "cars" / "box.ace"
        self.assertEqual(dw.output_path_for(source, root, Path("C:/out"), ".dds"), Path("C:/out/cars/box.dds"))
        self.assertEqual(dw.output_path_for(source, None, None, ".png"), Path("C:/route/textures/cars/box.png"))

    def test_overwrite_policy_skip_and_backup(self):
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "x.dds"
            out.write_text("old")
            should, note = dw.ensure_overwrite_policy(out, "skip")
            self.assertFalse(should)
            self.assertIn("SKIP", note)
            should, note = dw.ensure_overwrite_policy(out, "backup")
            self.assertTrue(should)
            self.assertIn("Backed up", note)
            self.assertFalse(out.exists())
            backups = list(Path(td).glob("x.dds.*.bak"))
            self.assertEqual(len(backups), 1)
            self.assertEqual(backups[0].read_text(), "old")

    def test_resolve_tool_finds_local_exe(self):
        self.assertTrue(Path(dw.resolve_tool("", ("ace2png.exe",))).name.lower().startswith("ace2png"))
        self.assertTrue(Path(dw.resolve_tool("", ("png2dds.exe",))).name.lower().startswith("png2dds"))
        self.assertTrue(Path(dw.resolve_magick("")).name.lower().startswith("magick"))
        with tempfile.TemporaryDirectory() as td:
            stale = Path(td) / "png2dds.exe"
            stale.write_text("stale")
            self.assertEqual(Path(dw.resolve_tool(str(stale), ("png2dds.exe",))).resolve(), (Path(dw.app_dir()) / "png2dds.exe").resolve())

    def test_tool_environment_prepends_magick_folder(self):
        with tempfile.TemporaryDirectory() as td:
            magick = Path(td) / "magick.exe"
            magick.write_text("fake")
            env = dw.tool_environment(str(magick))
            self.assertEqual(env["PATH"].split(dw.os.pathsep)[0], str(Path(td)))
            self.assertEqual(env["MAGICK_HOME"], str(Path(td)))

    def test_png2dds_command_includes_compression(self):
        cmd = dw.png2dds_command("png2dds.exe", Path("input.png"), Path("output.dds"), "dxt5", "generate")
        self.assertEqual(cmd, ["png2dds.exe", "input.png", "--destination", "output.dds", "--compression", "dxt5", "--mipmaps", "generate"])

    def test_png2ace_command_format_and_mipmaps(self):
        cmd = dw.png2ace_command("png2ace.exe", Path("input.png"), Path("output.ace"), "dxt1", "none")
        self.assertEqual(cmd, ["png2ace.exe", "input.png", "output.ace", "--format", "dxt1"])
        cmd = dw.png2ace_command("png2ace.exe", Path("input.png"), Path("output.ace"), "structured", "generate")
        self.assertEqual(cmd, ["png2ace.exe", "input.png", "output.ace", "--format", "structured", "--mipmaps"])

    def test_png2ace_missing_support_file_reported(self):
        root = tk.Tk()
        root.withdraw()
        try:
            app = dw.TextureWorkshopApp(root)
            app.mode.set("image_ace")
            app.png2ace_cmd.set(str(Path("missing_png2ace.exe")))
            missing = app.missing_support_files()
            self.assertTrue(any("png2ace.exe" in item for item in missing))
            self.assertFalse(any("png2dds" in item or "ImageMagick" in item for item in missing))
        finally:
            root.destroy()

    def test_image_to_ace_with_bundled_png2ace(self):
        png2ace = dw.app_dir() / "png2ace.exe"
        if not png2ace.exists():
            self.skipTest("png2ace.exe not present")
        with tempfile.TemporaryDirectory() as td:
            src = Path(td) / "src"
            out = Path(td) / "out"
            src.mkdir()
            write_png(src / "opaque.png", 32, 32, rgba=False)
            write_png(src / "alpha.png", 16, 16, rgba=True)
            root = tk.Tk()
            root.withdraw()
            try:
                app = dw.TextureWorkshopApp(root)
                app.png2ace_cmd.set(str(png2ace))
                app.mode.set("image_ace")
                app.thread_log = lambda _text: None
                app.overwrite_policy.set("backup")

                app.ace_format.set("structured")
                app.ace_mipmaps.set("generate")
                self.assertTrue(app.process_one(src / "opaque.png", src, out))
                ace = out / "opaque.ace"
                self.assertTrue(ace.read_bytes().startswith(b"SIMISA@@"))

                # DXT5 on a no-alpha source is skipped by png2ace: the existing ACE must survive untouched.
                before = ace.read_bytes()
                app.ace_format.set("dxt5")
                app.ace_mipmaps.set("none")
                self.assertIsNone(app.process_one(src / "opaque.png", src, out))
                self.assertEqual(ace.read_bytes(), before)
                self.assertEqual(list(out.glob("*.bak")), [])
                self.assertEqual([p.name for p in out.iterdir()], ["opaque.ace"])

                # A real re-conversion backs up the previous ACE.
                app.ace_format.set("dxt1")
                self.assertTrue(app.process_one(src / "opaque.png", src, out))
                self.assertEqual(len(list(out.glob("opaque.ace.*.bak"))), 1)

                app.ace_format.set("dxt5")
                self.assertTrue(app.process_one(src / "alpha.png", src, out))
                self.assertTrue((out / "alpha.ace").exists())

                # Mipmaps on a non-square image fail cleanly.
                write_png(src / "wide.png", 30, 20, rgba=False)
                app.ace_format.set("structured")
                app.ace_mipmaps.set("generate")
                self.assertFalse(app.process_one(src / "wide.png", src, out))
                self.assertFalse((out / "wide.ace").exists())

                app.overwrite_policy.set("skip")
                self.assertIsNone(app.process_one(src / "alpha.png", src, out))
            finally:
                root.destroy()

    def test_output_clashes_found_case_insensitively(self):
        root = Path("C:/tex")
        files = [root / "box.png", root / "box.tga", root / "car.png", root / "sub" / "box.bmp"]
        plan = dw.plan_outputs(files, "image_ace", root, None)
        clashes = dw.find_output_clashes(plan)
        self.assertEqual(len(clashes), 1)
        out, sources = clashes[0]
        self.assertEqual(out, root / "box.ace")
        self.assertEqual(sources, [root / "box.png", root / "box.tga"])
        # Flattened output (single-file style, no source root) makes the subfolder copy clash too.
        flat = dw.find_output_clashes(dw.plan_outputs(files, "image_ace", None, Path("C:/out")))
        self.assertEqual([len(s) for _o, s in flat], [3])
        if dw.os.name == "nt":
            upper = dw.find_output_clashes([(root / "A.png", [root / "A.ace"]), (root / "a.tga", [root / "a.ace"])])
            self.assertEqual(len(upper), 1)

    def test_apply_clash_choices_keeps_only_chosen_source(self):
        root = Path("C:/tex")
        files = [root / "box.png", root / "box.tga", root / "car.png", root / "car.bmp", root / "solo.png"]
        clashes = dw.find_output_clashes(dw.plan_outputs(files, "image_dds", root, None))
        choices = {dw.output_key(root / "box.dds"): root / "box.tga", dw.output_key(root / "car.dds"): None}
        self.assertEqual(dw.apply_clash_choices(files, clashes, choices), [root / "box.tga", root / "solo.png"])

    def test_keep_intermediate_png_counts_as_existing_output(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "a.ace").write_text("x")
            (root / "a.png").write_text("old intermediate")
            plan = dw.plan_outputs([root / "a.ace"], "ace_dds", root, None, keep_intermediate=True)
            self.assertEqual(dw.existing_outputs(plan), [root / "a.png"])
            plan = dw.plan_outputs([root / "a.ace"], "ace_dds", root, None, keep_intermediate=False)
            self.assertEqual(dw.existing_outputs(plan), [])

    def test_prepare_run_asks_about_clashes_and_existing_files(self):
        with tempfile.TemporaryDirectory() as td:
            src = Path(td)
            for name in ["box.png", "box.tga", "car.png", "old.png"]:
                (src / name).write_text("x")
            (src / "old.ace").write_text("existing")
            root = tk.Tk()
            root.withdraw()
            try:
                app = dw.TextureWorkshopApp(root)
                app.source_path.set(str(src))
                app.use_source_output.set(True)
                app.recursive.set(False)
                app.mode.set("image_ace")
                app.overwrite_policy.set("ask")
                asked = {}

                def clash_answer(clashes):
                    asked["clashes"] = clashes
                    return {dw.output_key(clashes[0][0]): clashes[0][1][1]}

                def existing_answer(existing):
                    asked["existing"] = existing
                    return "backup"

                app.ask_clash_choices = clash_answer
                app.ask_existing_policy = existing_answer
                files, policy, notes, preskipped = app.prepare_run()
                self.assertEqual(preskipped, 1)
                self.assertEqual([p.name for p in files], ["box.tga", "car.png", "old.png"])
                self.assertEqual(policy, "backup")
                self.assertEqual([o.name for o, _s in asked["clashes"]], ["box.ace"])
                self.assertEqual([p.name for p in asked["existing"]], ["old.ace"])
                self.assertTrue(any("using box.tga" in n for n in notes))

                # Cancelling either dialog cancels the run.
                app.ask_existing_policy = lambda existing: None
                self.assertIsNone(app.prepare_run())
                app.ask_clash_choices = lambda clashes: None
                self.assertIsNone(app.prepare_run())

                # A fixed policy never shows the existing-files dialog.
                app.ask_clash_choices = lambda clashes: {dw.output_key(clashes[0][0]): None}
                app.ask_existing_policy = lambda existing: self.fail("should not ask")
                app.overwrite_policy.set("overwrite")
                files, policy, _notes, preskipped = app.prepare_run()
                self.assertEqual(preskipped, 2)
                self.assertEqual([p.name for p in files], ["car.png", "old.png"])
                self.assertEqual(policy, "overwrite")

                # Unresolved "ask" is never applied blindly.
                app.overwrite_policy.set("ask")
                app.run_policy = None
                self.assertEqual(app.active_policy(), "skip")
            finally:
                root.destroy()

    def test_default_overwrite_policy_is_ask(self):
        originals = (dw.CONFIG_DIR, dw.CONFIG_FILE, dw.LEGACY_CONFIG_FILE)
        with tempfile.TemporaryDirectory() as td:
            dw.CONFIG_DIR = Path(td) / "TextureWorkshop"
            dw.CONFIG_FILE = dw.CONFIG_DIR / "settings.ini"
            dw.LEGACY_CONFIG_FILE = Path(td) / "none" / "settings.ini"
            try:
                root = tk.Tk()
                root.withdraw()
                try:
                    self.assertEqual(dw.TextureWorkshopApp(root).overwrite_policy.get(), "ask")
                finally:
                    root.destroy()
            finally:
                dw.CONFIG_DIR, dw.CONFIG_FILE, dw.LEGACY_CONFIG_FILE = originals

    def test_command_available_and_missing_support_files(self):
        self.assertFalse(dw.command_available(str(Path("definitely_missing_support_file.exe"))))
        root = tk.Tk()
        root.withdraw()
        try:
            app = dw.TextureWorkshopApp(root)
            app.mode.set("ace_dds")
            app.ace2png_cmd.set(str(Path("missing_ace2png.exe")))
            app.png2dds_cmd.set(str(Path("missing_png2dds.exe")))
            app.magick_cmd.set(str(Path("missing_magick.exe")))
            missing = app.missing_support_files()
            self.assertGreaterEqual(len(missing), 3)
            self.assertTrue(any("ace2png.exe" in item for item in missing))
            self.assertTrue(any("png2dds.exe" in item for item in missing))
            self.assertTrue(any("ImageMagick" in item for item in missing))
        finally:
            root.destroy()

    def test_subprocess_window_options_hide_windows_console(self):
        opts = dw.subprocess_window_options()
        if dw.os.name == "nt":
            self.assertIn("creationflags", opts)
            self.assertEqual(opts["creationflags"], dw.subprocess.CREATE_NO_WINDOW)
            self.assertIn("startupinfo", opts)
        else:
            self.assertEqual(opts, {})

    def test_asset_paths_exist(self):
        self.assertTrue(dw.app_icon_path().exists())
        self.assertTrue(dw.banner_image_path().exists())

    def test_display_folder_labels_are_not_blank(self):
        root = Path("C:/route/textures")
        self.assertEqual(dw.display_folder_for_source(root / "a.ace", root), "textures")
        self.assertEqual(dw.display_folder_for_source(root / "cars" / "b.ace", root), str(Path("textures") / "cars"))

    def test_source_tree_updates_when_mode_and_recursive_change(self):
        with tempfile.TemporaryDirectory() as td:
            root_path = Path(td)
            for name in ["a.ace", "b.png", "c.tga", "d.bmp", "e.txt"]:
                (root_path / name).write_text("x")
            (root_path / "sub").mkdir()
            (root_path / "sub" / "z.ace").write_text("x")

            root = tk.Tk()
            root.withdraw()
            try:
                app = dw.TextureWorkshopApp(root)
                app.source_path.set(str(root_path))
                app.mode.set("ace_png")
                app.recursive.set(False)
                app.refresh_source_list()
                items = app.source_tree.get_children()
                self.assertEqual(len(items), 1)
                self.assertEqual(app.source_tree.item(items[0], "values")[0], "a.ace")

                app.mode.set("image_dds")
                app.refresh_source_list()
                names = [app.source_tree.item(item, "values")[0] for item in app.source_tree.get_children()]
                self.assertEqual(names, ["b.png", "c.tga", "d.bmp"])

                app.mode.set("ace_dds")
                app.recursive.set(True)
                app.refresh_source_list()
                names = [app.source_tree.item(item, "values")[0] for item in app.source_tree.get_children()]
                folders = [app.source_tree.item(item, "values")[1] for item in app.source_tree.get_children()]
                self.assertEqual(names, ["a.ace", "z.ace"])
                self.assertEqual(folders, [root_path.name, str(Path(root_path.name) / "sub")])

                app.mode.set("image_ace")
                app.recursive.set(False)
                app.update_mode_state()
                names = [app.source_tree.item(item, "values")[0] for item in app.source_tree.get_children()]
                self.assertEqual(names, ["b.png", "c.tga", "d.bmp"])
                self.assertTrue(all(str(w.cget("state")) == "normal" for w in app.ace_option_widgets))
                self.assertTrue(all(str(w.cget("state")) == "disabled" for w in app.dds_option_widgets))
                app.mode.set("image_dds")
                app.update_mode_state()
                self.assertTrue(all(str(w.cget("state")) == "disabled" for w in app.ace_option_widgets))
                self.assertTrue(all(str(w.cget("state")) == "normal" for w in app.dds_option_widgets))
            finally:
                root.destroy()

    def test_content_below_header_is_scrollable(self):
        root = tk.Tk()
        root.geometry("820x420")
        try:
            app = dw.TextureWorkshopApp(root)
            root.geometry("820x420")
            root.update()
            self.assertTrue(hasattr(app, "content_canvas"))
            self.assertTrue(hasattr(app, "content_scrollbar"))
            self.assertTrue(app.content_scrollbar.winfo_ismapped())
            self.assertTrue(app.content_canvas.cget("yscrollcommand"))
            self.assertTrue(app.content_scrollbar.cget("command"))
            scrollregion = app.content_canvas.cget("scrollregion")
            self.assertTrue(scrollregion)
            self.assertGreater(app.content.winfo_height(), app.content_canvas.winfo_height())
        finally:
            root.destroy()

    def test_theme_switch_and_persistence(self):
        original_config_dir = dw.CONFIG_DIR
        original_config_file = dw.CONFIG_FILE
        with tempfile.TemporaryDirectory() as td:
            dw.CONFIG_DIR = Path(td) / "TextureWorkshop"
            dw.CONFIG_FILE = dw.CONFIG_DIR / "settings.ini"
            try:
                root = tk.Tk()
                root.withdraw()
                app = dw.TextureWorkshopApp(root)
                app.theme_name.set("Dark")
                app.dds_compression.set("dxt5")
                app.dds_mipmaps.set("generate")
                app.ace_format.set("auto-dxt")
                app.ace_mipmaps.set("generate")
                app.apply_theme_from_settings()
                root.update()
                self.assertEqual(root.cget("bg"), dw.THEMES["Dark"].app_bg)
                self.assertEqual(app.content_canvas.cget("bg"), dw.THEMES["Dark"].app_bg)
                self.assertEqual(app.log.cget("bg"), dw.THEMES["Dark"].log_bg)
                root.destroy()

                cfg = configparser.ConfigParser()
                cfg.read(dw.CONFIG_FILE)
                saved = cfg.get("settings", "theme")
                self.assertEqual(saved, "Dark")
                self.assertEqual(cfg.get("settings", "dds_compression"), "dxt5")
                self.assertEqual(cfg.get("settings", "dds_mipmaps"), "generate")
                self.assertEqual(cfg.get("settings", "ace_format"), "auto-dxt")
                self.assertEqual(cfg.get("settings", "ace_mipmaps"), "generate")
            finally:
                dw.CONFIG_DIR = original_config_dir
                dw.CONFIG_FILE = original_config_file

    def test_legacy_dds_workshop_settings_are_imported(self):
        originals = (dw.CONFIG_DIR, dw.CONFIG_FILE, dw.LEGACY_CONFIG_FILE)
        with tempfile.TemporaryDirectory() as td:
            dw.CONFIG_DIR = Path(td) / "TextureWorkshop"
            dw.CONFIG_FILE = dw.CONFIG_DIR / "settings.ini"
            dw.LEGACY_CONFIG_FILE = Path(td) / "DDSWorkshop" / "settings.ini"
            dw.LEGACY_CONFIG_FILE.parent.mkdir(parents=True)
            dw.LEGACY_CONFIG_FILE.write_text("[settings]\ntheme = Dark\ndds_compression = dxt1\n", encoding="utf-8")
            try:
                root = tk.Tk()
                root.withdraw()
                try:
                    app = dw.TextureWorkshopApp(root)
                    self.assertEqual(app.theme_name.get(), "Dark")
                    self.assertEqual(app.dds_compression.get(), "dxt1")
                finally:
                    root.destroy()
                # New settings file takes priority once it exists.
                dw.CONFIG_DIR.mkdir(parents=True)
                dw.CONFIG_FILE.write_text("[settings]\ntheme = Light\n", encoding="utf-8")
                root = tk.Tk()
                root.withdraw()
                try:
                    self.assertEqual(dw.TextureWorkshopApp(root).theme_name.get(), "Light")
                finally:
                    root.destroy()
            finally:
                dw.CONFIG_DIR, dw.CONFIG_FILE, dw.LEGACY_CONFIG_FILE = originals


if __name__ == "__main__":
    unittest.main()
