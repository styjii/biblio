"""Garde-fou : les attributs utilisés sur les modules / instances partagés existent bien (pyflakes ne le voit pas)."""
import ast
import unittest
from pathlib import Path

from app import config
from app.assets import editor_bundle
from app.devices import monitor
from app.media import media
from app.sysinfo import SystemInfo

APP = Path(__file__).resolve().parent.parent / "app"
from app.devices import ActivityHistory, DeviceTracker
from app.media import MediaLibrary

SHARED = {"ActivityHistory": ActivityHistory, "DeviceTracker": DeviceTracker, "MediaLibrary": MediaLibrary, "config": config, "monitor": monitor, "media": media, "editor_bundle": editor_bundle, "SystemInfo": SystemInfo}


class ReferenceTests(unittest.TestCase):
    def test_attributs_existants(self):
        missing = []
        for path in sorted(APP.rglob("*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                # config.x   /   monitor.history.y   /   config.sessions.z
                chain, cur = [], node
                while isinstance(cur, ast.Attribute):
                    chain.append(cur.attr)
                    cur = cur.value
                if not (isinstance(cur, ast.Name) and cur.id in SHARED and chain) or cur.id in ("media",) and False:
                    continue
                obj = SHARED[cur.id]
                for attr in reversed(chain):
                    if not hasattr(obj, attr):
                        missing.append(f"{path.relative_to(APP.parent)}:{getattr(node, 'lineno', '?')} {cur.id}.{'.'.join(reversed(chain))}")
                        break
                    obj = getattr(obj, attr)
        self.assertEqual(missing, [])

    def test_les_routes_heritent_du_socle_http(self):
        """Chaque famille de routes hérite de BaseHandler : l'éditeur (Pyright) connaît send_html, send_json, self.path…"""
        import importlib
        from app.routes.base import BaseHandler
        for module in ("auth", "browse", "dashboard", "edit", "player", "serve", "upload", "viewer"):
            mod = importlib.import_module(f"app.routes.{module}")
            classes = [c for n, c in vars(mod).items() if n.endswith("Routes") and isinstance(c, type)]
            self.assertTrue(classes, module)
            for cls in classes:
                self.assertTrue(issubclass(cls, BaseHandler), f"{module}.{cls.__name__}")


if __name__ == "__main__":
    unittest.main()
