"""Chargement des fichiers front-end (CSS, JS, gabarits HTML) et du bundle de l'éditeur.

Convention : un chemin qui désigne un dossier regroupe des fichiers `NN-nom` concaténés dans l'ordre
alphabétique (un script découpé par sections, une feuille de style découpée par thèmes). Chaque bloc est
précédé d'un saut de ligne, puis inséré tel quel dans la page (<style> / <script>) : aucune requête de
plus pour le navigateur.
"""

import gzip

from app import config

FRONTEND_DIR = config.HERE / "frontend"


def asset(rel):
    """Contenu d'un fichier de frontend/ (ou des fichiers d'un dossier, dans l'ordre alphabétique)."""
    path = FRONTEND_DIR / rel
    files = sorted(p for p in path.iterdir() if p.is_file()) if path.is_dir() else [path]
    return "\n" + "".join(p.read_text(encoding="utf-8") for p in files)


# Gabarits et scripts communs
THEME_INIT = asset("templates/partials/theme_init.html")
THEME_JS = asset("js/theme.js")
DECORATE_JS = asset("js/decorate.js")
LOCK_JS = asset("js/lock.js")

# Feuille de style commune
CSS = asset("css/main")

# Pages
BROWSE_JS = asset("js/browse")
VIEWER_JS = asset("js/viewer.js")
PREVIEW_JS = asset("js/preview.js")
WATCH_JS = asset("js/watch")
MD_CSS = asset("css/markdown.css")
MD_JS = asset("js/markdown")
DASH_CSS = asset("css/dashboard.css")
DASH_JS = asset("js/dashboard")
LISTEN_CSS = asset("css/listen.css")
LISTEN_JS = asset("js/listen")


class EditorBundle:
    """Bundle JavaScript de l'éditeur (editor.bundle.js) : contenu, version gzip et version (mtime), rechargé si modifié."""

    def __init__(self, path):
        self.path = path
        self._key = None
        self._data = {}

    def get(self):
        key = self.path.stat().st_mtime_ns
        if self._key != key:
            raw = self.path.read_bytes()
            self._data = {"raw": raw, "gz": gzip.compress(raw, 6), "v": str(key)}
            self._key = key
        return self._data


editor_bundle = EditorBundle(config.BUNDLE)
