"""JavaScript du front-end : syntaxe valide (telle que servie, fichiers concaténés) et syntaxe moderne uniquement."""
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from app import assets
from app.config import HERE

JS_DIR = HERE / "frontend" / "js"


class FrontendJsTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which("node"), "Node.js n'est pas installé")
    def test_chaque_script_servi_est_syntaxiquement_valide(self):
        scripts = {
            "worker d'envoi": assets.TRANSFER_WORKER_JS, "moteur d'envoi": assets.TRANSFER_ENGINE_JS,
            "panneau d'envoi": assets.TRANSFER_UI_JS, "progression": assets.PROGRESS_JS, "thème": assets.THEME_JS,
            "cadenas": assets.LOCK_JS, "décoration": assets.DECORATE_JS, "aperçu au survol": assets.HOVER_PREVIEW_JS, "lecteur vidéo": assets.WATCH_JS,
            "lecteur audio": assets.LISTEN_JS, "navigation": assets.BROWSE_JS, "tableau de bord": assets.DASH_JS,
            "markdown": assets.MD_JS, "visionneuse": assets.VIEWER_JS, "aperçu": assets.PREVIEW_JS,
            "page d'erreur": assets.ERROR_BACK_JS,
        }
        with tempfile.TemporaryDirectory() as tmp:
            for name, source in scripts.items():
                path = Path(tmp) / "script.js"
                path.write_text(source, encoding="utf-8")
                result = subprocess.run(["node", "--check", str(path)], capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, f"{name} : {result.stderr[:400]}")

    @unittest.skipUnless(shutil.which("node"), "Node.js n'est pas installé")
    def test_chaque_fichier_est_valide_isolement(self):
        """Éditeur et linter ouvrent les fichiers un par un : chacun doit être un JavaScript valide à lui seul."""
        failures = []
        for path in sorted(JS_DIR.rglob("*.js")):
            result = subprocess.run(["node", "--check", str(path)], capture_output=True, text=True)
            if result.returncode != 0:
                failures.append(f"{path.relative_to(HERE)} : {result.stderr.strip().splitlines()[0] if result.stderr.strip() else '?'}")
        self.assertEqual(failures, [], "fichiers invalides isolément :\n" + "\n".join(failures[:20]))

    def test_aucune_syntaxe_ancienne(self):
        old_style = {
            "var": re.compile(r"^\s*var\s", re.M),
            "function anonyme": re.compile(r"\bfunction\s*\("),
            "chaîne de .then": re.compile(r"\)\s*\.then\("),
            "concaténation de texte": re.compile(r"['\"]\s*\+\s*[A-Za-z_$(]"),
        }
        problems = []
        for path in sorted(JS_DIR.rglob("*.js")):
            text = path.read_text(encoding="utf-8")
            for label, pattern in old_style.items():
                for match in pattern.finditer(text):
                    line = text.count("\n", 0, match.start()) + 1
                    problems.append(f"{path.relative_to(HERE)}:{line} {label}")
        self.assertEqual(problems, [], "syntaxe ancienne trouvée :\n" + "\n".join(problems[:20]))


if __name__ == "__main__":
    unittest.main()
