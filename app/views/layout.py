"""Briques HTML communes : en-tête de page, barre du haut, pages d'information et de verrouillage."""

from html import escape
from urllib.parse import quote

from app import config
from app.assets import CSS, LOCK_JS, THEME_INIT, THEME_JS, TRANSFER_UI_JS, TRANSFER_VERSION
from app.icons import FAVICON, icon
from app.templating import render
from app.utils import js_json


def theme_button(extra=""):
    return render("layout/theme_button", extra=extra)


def doc_open(title, body_class="", extra_css=""):
    """Début de page : <head> complet puis <body>."""
    return render("layout/document_start", title=escape(title), favicon=FAVICON, theme_init=THEME_INIT,
                  css=CSS, extra_css=extra_css, body_class=body_class)


def transfer_script():
    """Panneau des envois (SharedWorker) : chargé sur toutes les pages tant que l'envoi de fichiers n'est pas désactivé."""
    if config.READONLY:
        return ""
    ico = {name: icon(name, size) for name, size in (("upload", 16), ("minus", 16), ("check", 14))}
    return f"window.TCFG = {js_json({'v': TRANSFER_VERSION, 'ico': ico})};{TRANSFER_UI_JS}\n"


def doc_close(script, before="", after=""):
    """Fin de page : script en ligne (+ balises avant / après) puis fermeture de <body>."""
    return render("layout/document_end", script=transfer_script() + script, before=before, after=after)


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


# code HTTP -> (icône, ton, titre, explication)
ERROR_PAGES = {
    400: ("close", "warn", "Requête invalide", "Cette requête n'a pas pu être comprise. Vérifie l'adresse et réessaie."),
    401: ("lock", "warn", "Accès protégé", "Ouvre le lien complet affiché dans le terminal au démarrage de biblio."),
    403: ("ban", "danger", "Accès refusé", "Tu n'as pas l'autorisation d'ouvrir cette page ou ce fichier."),
    404: ("search", "", "Page introuvable", "La page ou le fichier demandé n'existe pas, a été déplacé ou a été renommé."),
    405: ("ban", "warn", "Action non autorisée", "Cette action n'est pas disponible sur cette page."),
    413: ("upload", "warn", "Fichier trop volumineux", "Le fichier dépasse la taille maximale autorisée."),
    416: ("close", "warn", "Plage invalide", "La partie demandée du fichier n'existe pas."),
    500: ("refresh", "danger", "Erreur interne", "Quelque chose s'est mal passé côté serveur. Réessaie dans un instant."),
}
ERROR_BACK_JS = ("var b=document.getElementById('err-back');"
                 "if(b){if(history.length<2){b.hidden=true}"
                 "else{b.addEventListener('click',function(){history.back()})}}")


def error_page(code, detail="", where=""):
    """Page d'erreur HTTP : code, titre, explication, adresse demandée et boutons de sortie.
    `detail` : message précis de l'application (« Fichier introuvable »…) ; `where` : chemin demandé."""
    ic, tone, title, text = ERROR_PAGES.get(code, ("close", "danger" if code >= 500 else "warn", f"Erreur {code}",
                                                  "Une erreur est survenue."))
    detail_html = (render("pages/error_detail", detail=escape(detail))
                   if detail and detail.strip().casefold() != title.casefold() else "")
    where_html = render("pages/error_where", icon_svg=icon("globe", 14),
                        where=escape(where)) if where else ""
    actions = (render("components/pill_home")
               + render("components/pill_history_back"))
    return (doc_open(f"{title} — Ma bibliothèque") + topbar(False)
            + render("pages/error", code=code, tone=tone, title=escape(title), text=escape(text),
                     icon_svg=icon(ic, 30), detail=detail_html, where=where_html, actions=actions)
            + doc_close(THEME_JS + ERROR_BACK_JS))


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
