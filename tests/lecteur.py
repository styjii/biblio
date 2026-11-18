"""Textes du lecteur vidéo pour les tests qui vérifient son gabarit et son script : la page de lecture (gabarit « watch ») est
assemblée à partir de pièces partagées avec l'accueil (« video_box », « hint ») ; on les relit donc ensemble, dans l'ordre de la page."""
import re

from app import assets, config

_T = assets.FRONTEND_DIR / "templates/player"


def _read(path):
    return path.read_text(encoding="utf-8")


def watch_html():
    """Gabarit de la page de lecture, pièces partagées (zone du lecteur, raccourcis) remises à leur place."""
    page = _read(_T / "watch.html")
    page = page.replace("{{ box }}", _read(_T / "video_box.html")).replace("{{ hint }}", _read(_T / "hint.html"))
    return re.sub(r"\{\{ *(?:box|hint) *\}\}", "", page)


def player_py():
    """Code Python de la page de lecture et de ses briques partagées."""
    return _read(config.HERE / "app/routes/player.py") + "\n" + _read(config.HERE / "app/views/player.py")
