"""Page de liste des dossiers et fichiers."""

from html import escape
from urllib.parse import quote

from app import config
from app.assets import BROWSE_JS, DECORATE_JS, THEME_JS
from app.filesystem import card_kind, list_dir, rel_of, resolve_inside
from app.icons import ICONS, icon
from app.security import unlock_scopes
from app.templating import render
from app.utils import js_json
from app.views.cards import GROUPS, file_card, group_of, video_card
from app.views.layout import doc_close, doc_open, lock_script, topbar


class BrowseRoutes:
    def page_browse(self, folder):
        current = resolve_inside(folder)
        if current is None:
            self.send_error(403, "Dossier non autorisé")
            return
        if not current.is_dir():
            self.send_error(404, "Dossier introuvable")
            return
        folders, files = list_dir(current)
        if folders is None:
            self.send_error(403, "Accès refusé")
            return

        relative = current.relative_to(config.ROOT)
        title = relative.name if relative.parts else (config.ROOT.name or "Bibliothèque")
        grouped = {}
        for f in files:
            kind = card_kind(f)
            grouped.setdefault(group_of(kind), []).append((f, kind))
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
                            upload_button=render("browse/upload_button")
                            if config.PASSWORD and not config.READONLY else ""))

        if files:
            chips = "".join(render("browse/filter_chip", key=key, label=label, count=len(grouped[key]))
                            for key, label in GROUPS if key in grouped)
            parts.append(render("browse/filters", total=len(files), chips=chips))

        if relative.parts:
            parent = quote(relative.parent.as_posix(), safe="")
            if parent == ".":
                parent = ""
            parts.append(render("browse/back_link", parent=parent))

        if folders:
            items = "".join(render("browse/folder_item", dot=" dot" if d.name.startswith(".") else "",
                                   target=quote(rel_of(d), safe=""),
                                   name_key=escape(d.name.casefold(), quote=True), name=escape(d.name))
                            for d in folders)
            parts.append(render("browse/section", key="folders", label="Dossiers", count=len(folders),
                                layout="grid", content=items))

        for key, label in GROUPS:
            items = grouped.get(key)
            if not items:
                continue
            if key == "video":
                layout, content = "videos", "".join(video_card(f) for f, _ in items)
            else:
                layout, content = "grid", "".join(file_card(f, k) for f, k in items)
            parts.append(render("browse/section", key=key, label=label, count=len(items),
                                layout=layout, content=content))

        parts.append(render("browse/no_result") if has_content else render("browse/empty_folder"))
        page = (doc_open(f"{title} — Ma bibliothèque") + topbar(has_content, True)
                + render("browse/main", content="".join(parts)))
        parts = [page, render("browse/sheet")]

        cfg = {"readonly": config.READONLY, "canDelete": bool(config.PASSWORD) and not config.READONLY,
               "unlocked": "files" in unlock_scopes(self.dash_session_id()), "protect": bool(config.PASSWORD),
               "maxUpload": config.MAX_UPLOAD, "folder": relative.as_posix() if relative.parts else ""}
        icons_js = {n: icon(n, 22) for n in ICONS}
        parts.append(doc_close(f"window.FLCFG = {js_json(cfg)}; window.ICO = {js_json(icons_js)};"
                               f"{THEME_JS}{DECORATE_JS}{BROWSE_JS}", after=lock_script()))
        self.send_html("".join(parts))
