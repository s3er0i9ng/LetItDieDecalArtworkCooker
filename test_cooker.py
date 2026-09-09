from pathlib import Path
import json
import os
import tempfile
import tkinter as tk
import unittest
import zipfile

from cooker_core import cook_decal, normalize_identifier, output_filenames, read_png_dimensions
from decal_cooker_gui import CookerApp


HERE = Path(__file__).resolve().parent
GAME = Path(os.environ["LID_GAME_DIR"]) if os.environ.get("LID_GAME_DIR") else None
SAMPLE = Path(os.environ["LID_TEST_PNG"]) if os.environ.get("LID_TEST_PNG") else None


class CookerTests(unittest.TestCase):
    def test_identifier_normalization_and_names(self):
        self.assertEqual(normalize_identifier(" ui_skl_yippee-ki yay "), "YIPPEE_KI_YAY")
        self.assertEqual(
            output_filenames("test decal"),
            (
                "UI_SKL_TEST_DECAL_SF.upk",
                "UI_SKL_TEST_DECAL_M_SF.upk",
                "UI_SKL_TEST_DECAL_S_SF.upk",
            ),
        )
        for invalid in ("", "1BAD", "A", "BAD/ID", "NAME_SF"):
            with self.assertRaises(ValueError):
                normalize_identifier(invalid)

    def test_gui_constructs_and_previews_all_sizes(self):
        try:
            root = tk.Tk()
        except tk.TclError as error:
            self.skipTest(f"Tk is unavailable in this Python installation: {error}")
        root.withdraw()
        try:
            app = CookerApp(root)
            app.identifier_var.set("GUI_PREVIEW_TEST")
            app.update_preview()
            preview = app.filename_preview.cget("text")
            self.assertIn("UI_SKL_GUI_PREVIEW_TEST_SF.upk", preview)
            self.assertIn("UI_SKL_GUI_PREVIEW_TEST_M_SF.upk", preview)
            self.assertIn("UI_SKL_GUI_PREVIEW_TEST_S_SF.upk", preview)
        finally:
            root.destroy()

    @unittest.skipUnless(SAMPLE and SAMPLE.is_file(), "Set LID_TEST_PNG to test PNG parsing")
    def test_sample_png(self):
        width, height = read_png_dimensions(SAMPLE)
        self.assertEqual(width, height)
        self.assertGreaterEqual(width, 128)

    @unittest.skipUnless(
        SAMPLE and SAMPLE.is_file() and GAME and GAME.is_dir(),
        "Set LID_TEST_PNG and LID_GAME_DIR for the real-package integration test",
    )
    def test_real_three_size_cook(self):
        with tempfile.TemporaryDirectory(prefix="decal-cooker-test-") as temporary:
            result = cook_decal(SAMPLE, "COOKER_INTEGRATION_TEST", GAME, Path(temporary), lambda _: None)
            manifest = json.loads((result / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(len(manifest["files"]), 3)
            self.assertEqual(
                [row["dimensions"] for row in manifest["files"]],
                [[512, 512], [256, 256], [128, 128]],
            )
            self.assertTrue(all(row["native_lzo_validated"] for row in manifest["files"]))
            archive = result / "LET-IT-DIE-Decal-COOKER_INTEGRATION_TEST-Artwork.zip"
            with zipfile.ZipFile(archive) as bundle:
                self.assertIsNone(bundle.testzip())
                self.assertEqual(sum(name.endswith(".upk") for name in bundle.namelist()), 3)


if __name__ == "__main__":
    unittest.main()
