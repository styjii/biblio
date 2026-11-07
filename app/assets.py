"""Chargement des fichiers front-end (CSS, JS, gabarits HTML) et du bundle de l'éditeur.

Convention : un chemin qui désigne un dossier regroupe des fichiers `NN-nom` concaténés dans l'ordre
alphabétique (un script découpé par sections, une feuille de style découpée par thèmes). Chaque bloc est
précédé d'un saut de ligne, puis inséré tel quel dans la page (<style> / <script>) : aucune requête de
plus pour le navigateur. Pour un dossier de scripts (`wrap=True`), le serveur enveloppe l'ensemble dans une
fonction anonyme auto-appelée : les fichiers partagent une même portée sans rien exposer à la page, et chacun
reste un fichier JavaScript valide pris isolément (éditeur, linter).
"""

import gzip
import hashlib

from app import config

FRONTEND_DIR = config.HERE / "frontend"


def asset(rel, wrap=False):
    """Contenu d'un fichier de frontend/ (ou des fichiers d'un dossier, dans l'ordre alphabétique).

    `wrap=True` (scripts d'un dossier) : l'ensemble est placé dans une fonction anonyme auto-appelée.
    Seuls les fichiers .js et .css sont lus (un dossier peut contenir un jsconfig.json pour l'éditeur).
    """
    path = FRONTEND_DIR / rel
    files = sorted(p for p in path.iterdir() if p.is_file() and p.suffix in (".js", ".css")) if path.is_dir() else [path]
    body = "".join(p.read_text(encoding="utf-8") for p in files)
    return f"\n(() => {{\n{body}}})();\n" if wrap else "\n" + body


# Gabarits et scripts communs
THEME_INIT = asset("templates/partials/theme_init.html")
ERROR_BACK_JS = asset("js/error-page.js")
THEME_JS = asset("js/theme.js")
DECORATE_JS = asset("js/decorate.js")
LOCK_JS = asset("js/lock.js")

# Feuille de style commune
CSS = asset("css/main")

# Envois de fichiers : le moteur (aussi servi seul, en repli), le SharedWorker (moteur + glue) et le panneau commun
TRANSFER_ENGINE_JS = asset("js/transfers/engine.js")
TRANSFER_WORKER_JS = TRANSFER_ENGINE_JS + asset("js/transfers/worker.js")
TRANSFER_UI_JS = asset("js/transfers/ui.js")
TRANSFER_VERSION = hashlib.sha1(TRANSFER_WORKER_JS.encode("utf-8")).hexdigest()[:10]   # change avec le code : un worker périmé n'est pas réutilisé

# Mémoire de la position de lecture (serveur, par appareil), partagée par les lecteurs audio et vidéo
PROGRESS_JS = asset("js/progress.js")

# Pages
BROWSE_JS = asset("js/browse", wrap=True)
VIEWER_JS = asset("js/viewer.js")
PREVIEW_JS = asset("js/preview.js")
WATCH_JS = asset("js/watch", wrap=True)
MD_CSS = asset("css/markdown.css")
MD_JS = asset("js/markdown", wrap=True)
DASH_CSS = asset("css/dashboard.css")
DASH_JS = asset("js/dashboard", wrap=True)
LISTEN_CSS = asset("css/listen.css")
LISTEN_JS = asset("js/listen", wrap=True)


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
