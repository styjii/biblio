"""Les fichiers CSS / JS sont chargés et les scripts assemblés sont du JavaScript valide."""
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from app import assets

SCRIPTS = ["THEME_JS", "DECORATE_JS", "LOCK_JS", "BROWSE_JS", "VIEWER_JS", "PREVIEW_JS", "WATCH_JS", "MD_JS",
           "DASH_JS", "LISTEN_JS"]
STYLES = ["CSS", "MD_CSS", "DASH_CSS", "LISTEN_CSS"]


class AssetTests(unittest.TestCase):
    def test_tous_charges(self):
        for name in SCRIPTS + STYLES + ["THEME_INIT"]:
            with self.subTest(asset=name):
                value = getattr(assets, name)
                self.assertTrue(value.startswith("\n") and len(value) > 20)

    @unittest.skipUnless(shutil.which("node"), "node absent")
    def test_javascript_valide(self):
        for name in SCRIPTS:
            with self.subTest(script=name), tempfile.TemporaryDirectory() as d:
                f = Path(d) / (name + ".js")
                f.write_text(getattr(assets, name), encoding="utf-8")
                r = subprocess.run(["node", "--check", str(f)], capture_output=True, text=True)
                self.assertEqual(r.returncode, 0, r.stderr)

    def test_css_accolades_equilibrees(self):
        for name in STYLES:
            css = getattr(assets, name)
            self.assertEqual(css.count("{"), css.count("}"), name)


if __name__ == "__main__":
    unittest.main()
