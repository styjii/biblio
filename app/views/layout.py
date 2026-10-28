"""Briques HTML communes : en-tête de page, barre du haut, pages d'information et de verrouillage."""

from html import escape
from urllib.parse import quote

from app import config
from app.assets import CSS, LOCK_JS, THEME_INIT, THEME_JS
from app.icons import FAVICON, icon
from app.templating import render
from app.utils import js_json


def theme_button(extra=""):
    return render("layout/theme_button", extra=extra)


def doc_open(title, body_class="", extra_css=""):
    """Début de page : <head> complet puis <body>."""
    return render("layout/document_start", title=escape(title), favicon=FAVICON, theme_init=THEME_INIT,
                  css=CSS, extra_css=extra_css, body_class=body_class)


def doc_close(script, before="", after=""):
    """Fin de page : script en ligne (+ balises avant / après) puis fermeture de <body>."""
    return render("layout/document_end", script=script, before=before, after=after)


def topbar(with_search, lock=False):
    return render("layout/topbar",
                  search=render("layout/search_box") if with_search else "",
                  theme_button=theme_button(),
                  lock_button=render("layout/lock_button") if lock else "")


def folder_label_of(p):
    """Libellé du dossier d'un fichier, relatif au dossier servi (« / » ou son nom pour la racine)."""
    parent = p.parent
    return parent.relative_to(config.ROOT).as_posix() if parent != config.ROOT else (config.ROOT.name or "/")


def pill_link(href, icon_name, label, extra=""):
    """Bouton-lien de la barre d'outils (icône + libellé) ; `extra` : attributs HTML supplémentaires."""
    return render("components/pill_link", href=href, extra=extra, icon_svg=icon(icon_name, 16), label=label)


def folder_url(p_dir):
    rel = p_dir.relative_to(config.ROOT)
    return "/?folder=" + quote(rel.as_posix(), safe="") if rel.parts else "/"


def lock_script(reload=None):
    """Bouton cadenas + dialogue de déverrouillage ; `reload` : partie ("files"/"dash") dont le changement recharge la page."""
    ico = {n: icon(n, 20) for n in ("lock", "unlock")}
    return render("layout/script", code=f"window.LKICO = {js_json(ico)}; window.LKRELOAD = {js_json(reload)}; {LOCK_JS}")


def message_page(title, text, actions=""):
    return (doc_open(title) + topbar(False)
            + render("pages/message", title=escape(title), text=escape(text), actions=actions)
            + doc_close(THEME_JS))


EDIT_LOCKED_HINT = "Accès verrouillé : déverrouille l'accès (cadenas de la liste des fichiers) pour modifier ce fichier."


def edit_pill(q, locked):
    """Bouton « Éditer » : lien normal, ou simple indication « verrouillé » (aucune invite de mot de passe)."""
    if locked:
        return render("components/edit_pill_locked", hint=escape(EDIT_LOCKED_HINT, quote=True))
    return render("components/edit_pill", q=q)


def locked_page(what, scope, back=None, title="Accès verrouillé — Ma bibliothèque", css="", lock=False):
    """Page « accès verrouillé » commune : aucun champ de mot de passe, seulement un bouton pour déverrouiller."""
    actions = (render("components/pill_back", href=back) if back else "") + render("components/pill_unlock")
    return (doc_open(title, "", css) + topbar(False, lock)
            + render("pages/locked", what=escape(what), actions=actions)
            + doc_close(THEME_JS, after=lock_script(scope)))
