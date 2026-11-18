"""Lecteur vidéo : le même composant (gabarit, icônes, script) sert la page de lecture et le lecteur local de l'accueil."""

from app.icons import icon
from app.templating import render

# Icônes dessinées par le script du lecteur (window.WICO)
PLAYER_ICONS = ("repeat", "repeat1", "volume", "mute", "play", "pause", "replay", "expand", "shrink", "chevron_left", "check",
                "queue", "shuffle", "gauge", "captions", "download", "orientation", "lock", "unlock")


def player_icons(*extra):
    """Icônes du script du lecteur ; `extra` : icônes supplémentaires (la liste d'attente de l'accueil en a besoin)."""
    return {n: icon(n, 24) for n in PLAYER_ICONS + extra}


def video_box(src_attr, tracks, title):
    """Zone du lecteur (image, commandes, menu des paramètres, verrouillage). `src_attr` : « src='…' », ou vide."""
    return render("player/video_box", src_attr=src_attr, tracks=tracks, title=title)


def shortcuts_hint():
    return render("player/hint")
