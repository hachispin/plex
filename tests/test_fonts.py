"""Verify the installed desktop defaults with HarfBuzz and the shipped TTFs."""

import hashlib
import json
from pathlib import Path
import runpy
import shutil
import subprocess
import tempfile
import unittest

from fontTools.ttLib import TTFont


ROOT = Path(__file__).resolve().parents[1]
FONT_PATHS = sorted((ROOT / "packages").glob("plex-*/fonts/complete/ttf/*.ttf"))
TARGET_FAMILIES = {"plex-sans", "plex-serif"}


def shape(path, text, features=None):
    command = ["hb-shape", str(path), text, "--output-format=json"]

    if features:
        command.append(f"--features={features}")

    return json.loads(subprocess.check_output(command))


class FontDefaultsTests(unittest.TestCase):
    def test_customization_is_repeatable(self):
        customize = runpy.run_path(str(ROOT / "scripts/customize-fonts.py"))["customize_font"]

        with tempfile.TemporaryDirectory() as directory:
            for path in FONT_PATHS:
                with self.subTest(font=path.name):
                    target = Path(directory) / path.parts[-5] / "fonts/complete/ttf" / path.name
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(path, target)
                    before = hashlib.sha256(target.read_bytes()).digest()

                    self.assertFalse(customize(target))
                    self.assertEqual(hashlib.sha256(target.read_bytes()).digest(), before)

    def test_existing_defaults(self):
        for path in FONT_PATHS:
            with self.subTest(font=path.name), TTFont(path, checkChecksums=2) as font:
                for tag in font.reader.keys():
                    font.reader[tag]

                for feature in font["GSUB"].table.FeatureList.FeatureRecord:
                    if feature.FeatureTag == "liga":
                        self.assertEqual(feature.Feature.LookupListIndex, [])

                if font["OS/2"].fsSelection & 1:
                    self.assertEqual(font.getBestCmap()[ord("g")], "g.alt01")

    @unittest.skipUnless(shutil.which("hb-shape"), "Requires the HarfBuzz hb-shape command")
    def test_numeric_colons(self):
        numeric_text = " ".join(f"{left}:{right}" for left in range(10) for right in range(10))
        numeric_text += " 12:34 1:2:3 00:00:00 a1:1b (123:456)"

        for path in FONT_PATHS:
            with self.subTest(font=path.name):
                original = shape(path, numeric_text, "calt=0")

                if path.parts[-5] in TARGET_FAMILIES:
                    expected = shape(path, numeric_text.replace(":", "∶"), "calt=0")
                    self.assertNotEqual(expected, original)
                else:
                    expected = original

                self.assertEqual(shape(path, numeric_text), expected)
                self.assertEqual(shape(path, numeric_text, "calt=1"), expected)

    @unittest.skipUnless(shutil.which("hb-shape"), "Requires the HarfBuzz hb-shape command")
    def test_non_numeric_colons(self):
        text = ": a:b foo:bar :1 1: a:1 1:a 1 : 1 1: 1 1 :1 1::1 1:∶:1"

        for path in FONT_PATHS:
            with self.subTest(font=path.name):
                self.assertEqual(shape(path, text), shape(path, text, "calt=0"))

    @unittest.skipUnless(shutil.which("hb-shape"), "Requires the HarfBuzz hb-shape command")
    def test_alternate_digits(self):
        for path in FONT_PATHS:
            if path.parts[-5] not in TARGET_FAMILIES:
                continue

            for features in ("onum=1", "zero=1", "ss01=1", "sups=1", "sinf=1"):
                with self.subTest(font=path.name, features=features):
                    expected = shape(path, "00∶12 34∶56 78∶90", f"{features},calt=0")
                    self.assertEqual(shape(path, "00:12 34:56 78:90", features), expected)


if __name__ == "__main__":
    unittest.main()
