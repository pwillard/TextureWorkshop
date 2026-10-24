import configparser
import tempfile
import tkinter as tk
import unittest
from pathlib import Path

import dds_workshop as dw


class DDSWorkshopHelperTests(unittest.TestCase):
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

    def test_command_available_and_missing_support_files(self):
        self.assertFalse(dw.command_available(str(Path("definitely_missing_support_file.exe"))))
        root = tk.Tk()
        root.withdraw()
        try:
            app = dw.DDSWorkshopApp(root)
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
                app = dw.DDSWorkshopApp(root)
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
            finally:
                root.destroy()

    def test_content_below_header_is_scrollable(self):
        root = tk.Tk()
        root.geometry("820x420")
        try:
            app = dw.DDSWorkshopApp(root)
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
            dw.CONFIG_DIR = Path(td) / "DDSWorkshop"
            dw.CONFIG_FILE = dw.CONFIG_DIR / "settings.ini"
            try:
                root = tk.Tk()
                root.withdraw()
                app = dw.DDSWorkshopApp(root)
                app.theme_name.set("Dark")
                app.dds_compression.set("dxt5")
                app.dds_mipmaps.set("generate")
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
            finally:
                dw.CONFIG_DIR = original_config_dir
                dw.CONFIG_FILE = original_config_file


if __name__ == "__main__":
    unittest.main()
