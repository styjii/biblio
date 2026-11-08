"""Page de liste des dossiers et fichiers."""

from html import escape
from urllib.parse import quote

from app import config
from app.assets import BROWSE_JS, DECORATE_JS, HOVER_PREVIEW_JS, THEME_JS
from app.filesystem import card_kind, list_dir, rel_of
from app.icons import ICONS, icon
from app.templating import render
from app.utils import js_json
from app.media import media
from app.views.cards import GROUPS, file_card, group_of, sort_attrs, video_card
from app.views.layout import doc_close, doc_open, lock_script, topbar
from app.routes.base import BaseHandler


class BrowseRoutes(BaseHandler):
    def page_browse(self, folder):
        current = config.paths.resolve(folder)
        if current is None:
            self.send_error(403, "Dossier non autorisé")
            return
        if not current.is_dir():
            self.send_error(404, "Dossier introuvable")
            return
        folders, files = list_dir(current)
        if folders is None or files is None:
            self.send_error(403, "Accès refusé")
            return
        attached = media.attached_subtitles(files)             # sous-titres d'une vidéo du dossier : ouverts depuis le lecteur, pas listés
        files = [f for f in files if f not in attached]

        relative = current.relative_to(config.ROOT)
        title = relative.name if relative.parts else (config.ROOT.name or "Bibliothèque")
        cards = [(f, card_kind(f)) for f in files]            # dans l'ordre du serveur (nom, ordre naturel) : c'est le tri par défaut
        counts = {}
        for _, kind in cards:
            counts[group_of(kind)] = counts.get(group_of(kind), 0) + 1
        has_content = bool(folders or files)
        parts = []

        crumbs = [render("browse/crumb_home", cls="" if relative.parts else "current",
                         name=escape(config.ROOT.name or "Accueil"))]
        acc = []
        for i, comp in enumerate(relative.parts):
            acc.append(comp)
            crumbs.append(render("browse/crumb_item", cls="current" if i == len(relative.parts) - 1 else "",
                                 target=quote("/".join(acc), safe=""), name=escape(comp)))
        parts.append(render("browse/breadcrumb", items="".join(crumbs)))

        parts.append(render("browse/toolbar",
                            new_button="" if config.READONLY else render("browse/new_button"),
                            mkdir_button="" if config.READONLY else render("browse/mkdir_button"),
                            upload_button=render("browse/upload_button")
                            if config.PASSWORD and not config.READONLY else ""))

        if files or len(folders) > 1:                          # filtres par catégorie (s'il y a des fichiers) et tri
            filters = ""
            if files:
                chips = "".join(render("browse/filter_chip", key=key, label=label, count=counts[key])
                                for key, label in GROUPS if key in counts)
                filters = render("browse/filters", total=len(files), chips=chips)
            parts.append(render("browse/listbar", filters=filters))

        if relative.parts:
            parent = quote(relative.parent.as_posix(), safe="")
            if parent == ".":
                parent = ""
            parts.append(render("browse/back_link", parent=parent))

        if folders:
            items = "".join(render("browse/folder_item", dot=" dot" if d.name.startswith(".") else "",
                                   target=quote(rel_of(d), safe=""), title=escape(d.name, quote=True),
                                   more_button=render("components/more_button"),
                                   name_key=escape(d.name.casefold(), quote=True), name=escape(d.name),
                                   sort=sort_attrs(d, i))
                            for i, d in enumerate(folders))
            parts.append(render("browse/section", key="folders", label="Dossiers", count=len(folders),
                                layout="grid", content=items))

        if cards:                                              # une seule liste, tous types mélangés ; les filtres masquent par catégorie
            content = "".join(video_card(f, i) if k == "video" else file_card(f, k, i) for i, (f, k) in enumerate(cards))
            parts.append(render("browse/section", key="files", label="Fichiers", count=len(cards),
                                layout="files", content=content))

        parts.append(render("browse/no_result") if has_content else render("browse/empty_folder"))
        page = (doc_open(f"{title} — Ma bibliothèque") + topbar(has_content, True)
                + render("browse/main", content="".join(parts)))
        parts = [page, render("browse/sheet")]

        cfg = {"readonly": config.READONLY, "canDelete": bool(config.PASSWORD) and not config.READONLY,
               "unlocked": "files" in config.sessions.scopes(self.dash_session_id()), "protect": bool(config.PASSWORD),
               "maxUpload": config.MAX_UPLOAD, "folder": relative.as_posix() if relative.parts else ""}
        icons_js = {n: icon(n, 22) for n in ICONS}
        parts.append(doc_close(f"window.FLCFG = {js_json(cfg)}; window.ICO = {js_json(icons_js)};"
                               f"{THEME_JS}{DECORATE_JS}{HOVER_PREVIEW_JS}{BROWSE_JS}", after=lock_script()))
        self.send_html("".join(parts))
