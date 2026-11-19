"""Visionneuse d'images : /image?f=… (retour à la liste, précédente / suivante, zoom)."""

from html import escape
from urllib.parse import quote

from app import config
from app.assets import IMAGE_CSS, IMAGE_JS, THEME_JS
from app.filesystem import kind_of, list_dir, rel_of
from app.icons import icon
from app.routes.base import BaseHandler
from app.templating import render
from app.utils import js_json
from app.views.cards import stat_of
from app.views.layout import doc_close, doc_open, folder_url, topbar


class GalleryRoutes(BaseHandler):
    def page_image(self, rel):
        p = config.paths.resolve(rel)
        if p is None or not p.is_file() or kind_of(p) != "image":
            self.send_error(404, "Image introuvable")
            return
        _, files = list_dir(p.parent)
        siblings = [f for f in (files or []) if kind_of(f) == "image"]
        if p not in siblings:
            siblings.append(p)
        # `o` : rang par nom (ordre naturel du serveur) ; octets, date et extension servent au tri choisi dans la liste
        items = []
        for order, f in enumerate(siblings):
            nbytes, mtime = stat_of(f)
            items.append({"f": rel_of(f), "n": f.name, "o": order, "b": nbytes, "m": mtime, "e": f.suffix[1:].casefold()})
        current = rel_of(p)
        cfg = {"items": items, "current": current, "back": folder_url(p.parent), "key": config.library.root_id}
        icons = {n: icon(n, 20) for n in ("expand", "shrink")}
        index = next(i for i, item in enumerate(items) if item["f"] == current)
        page = render("viewer/image", folder_href=folder_url(p.parent), name=escape(p.name), pos=f"{index + 1} / {len(items)}")
        self.send_html(doc_open(f"{p.name} — Ma bibliothèque", "", IMAGE_CSS) + topbar(False) + page
                       + doc_close(f"window.ICFG = {js_json(cfg)}; window.IICO = {js_json(icons)}; {THEME_JS}{IMAGE_JS}"))
