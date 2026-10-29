"""Lecture et édition de texte, aperçus web et Markdown."""

from html import escape
from urllib.parse import quote

from app import config
from app.assets import MD_CSS, MD_JS, PREVIEW_JS, THEME_JS, VIEWER_JS, editor_bundle
from app.config import MAX_TEXT
from app.filesystem import kind_of, load_text, rel_of
from app.filetypes import AUDIO_EXT, BINARY_EXT, IMAGE_EXT, MD_EXT, VIDEO_EXT, WEB_EXT
from app.icons import icon
from app.templating import render
from app.utils import fmt_size, js_json
from app.views.layout import (doc_close, doc_open, edit_pill, folder_label_of, folder_url, locked_page, message_page,
                              pill_link, theme_button)
from app.routes.base import BaseHandler


def unreadable_page(p, err, q, back):
    """Page d'information quand un fichier ne peut pas être affiché comme texte."""
    msg = {"big": f"Ce fichier dépasse {fmt_size(MAX_TEXT)}, trop lourd pour être affiché ici.",
           "binary": "Ce fichier semble binaire : il ne peut pas être lu comme du texte.",
           "io": "Impossible de lire ce fichier."}[err]
    actions = render("components/pill_back", href=back) + render("components/pill_download", q=q)
    return message_page(p.name, msg, actions)


class ViewerRoutes(BaseHandler):
    def page_text(self, rel, edit, new=False):
        p = config.paths.resolve(rel)
        if p is None:
            self.send_error(403, "Fichier non autorisé")
            return
        if edit and config.READONLY:
            self.send_html(message_page("Mode lecture seule",
                                        "Le serveur a été lancé avec l'option lecture seule : l'édition est désactivée."), 403)
            return
        if edit and config.PASSWORD and "files" not in config.sessions.scopes(self.dash_session_id()):
            self.send_html(locked_page(f"Modifier « {p.name} »", "files", folder_url(p.parent)), 403)
            return

        is_new = False
        if not p.exists():
            if not (edit and new and p.parent.is_dir() and p.name):
                self.send_error(404, "Fichier introuvable")
                return
            is_new = True
            text, enc, crlf, err = "", "utf-8", False, None
        elif not p.is_file():
            self.send_error(404, "Fichier introuvable")
            return
        else:
            text, enc, crlf, err = load_text(p)

        q = quote(rel_of(p), safe="")
        back = folder_url(p.parent)
        if err:
            self.send_html(unreadable_page(p, err, q, back), 200)
            return

        mt = "new" if is_new else str(p.stat().st_mtime_ns)
        kind = kind_of(p)
        folder_label = folder_label_of(p)
        cfg = {
            "mode": "edit" if edit else "view", "name": p.name, "doc": text, "q": q, "mt": mt,
            "enc": enc, "crlf": crlf, "back": back, "readonly": config.READONLY,
            "readonlyView": not edit, "vim": True,
        }

        links = ""
        if edit:
            links += pill_link(f"/view?f={q}", "eye", "Lire")
            if p.suffix.lower() in MD_EXT:
                links += pill_link(f"/preview?f={q}", "book", "Aperçu")
            tools = render("viewer/tools_edit", links=links)
        else:
            if kind == "web":
                links += pill_link(f"/preview?f={q}", "globe", "Aperçu")
            elif p.suffix.lower() in MD_EXT:
                links += pill_link(f"/preview?f={q}", "book", "Aperçu")
            if not config.READONLY:
                links += edit_pill(q, self.files_locked())
            tools = render("viewer/tools_read", links=links)

        title = ("Édition · " if edit else "") + p.name
        html = [
            doc_open(f"{title} — Ma bibliothèque", "ed-page"),
            render("viewer/header", back=back, title=escape(p.name),
                   dirty=render("viewer/dirty_marker") if edit else "", small_attrs="",
                   subtitle=escape(folder_label) + (" · nouveau fichier" if is_new else ""),
                   save_button=render("viewer/save_button") if edit else "",
                   theme_button=theme_button(), tools=tools),
            render("viewer/editor_body", mode=render("viewer/mode_indicator") if edit else "",
                   encoding=escape(enc) + (" · CRLF" if crlf else "")),
        ]
        if edit:
            html.append(self.keys_bar())
        v = editor_bundle.get()["v"]
        html.append(doc_close(f"window.FLCFG = {js_json(cfg)}; {THEME_JS}{VIEWER_JS}",
                              before=render("layout/script_src", src=f"/static/editor.js?v={v}")))
        self.send_html("".join(html))

    @staticmethod
    def keys_bar():
        def k(label, what, cls=""):
            return render("viewer/key", cls=cls, what=escape(what, quote=True), label=label)

        sep = render("viewer/key_separator")
        items = [
            k("Esc", "esc", "vimonly"), k("Tab", "tab"),
            k(icon("arrow_left", 18), "left"), k(icon("arrow_down", 18), "down"),
            k(icon("arrow_up", 18), "up"), k(icon("arrow_right", 18), "right"),
            k(":", "ex", "vimonly"), k("/", "find"),
            k("undo", "undo"), k("redo", "redo"),
            sep,
        ]
        vim_keys = [("i", "k:i"), ("a", "k:a"), ("o", "k:o"), ("x", "k:x"), ("dd", "k:dd"), ("yy", "k:yy"),
                    ("p", "k:p"), ("gg", "k:gg"), ("G", "k:G"), ("0", "k:0"), ("$", "k:$"),
                    ("w", "k:w"), ("b", "k:b"), ("v", "k:v"), ("V", "k:V")]
        items += [k(label, what, "vimonly") for label, what in vim_keys]
        return render("viewer/keys_bar", keys="".join(items))

    def page_preview(self, rel):
        p = config.paths.resolve(rel)
        if p is None or not p.is_file():
            self.send_error(404, "Fichier introuvable")
            return
        if p.suffix.lower() in MD_EXT:
            self.page_markdown(p)
            return
        q = quote(rel_of(p), safe="")
        back = folder_url(p.parent)
        site = f"/s/{config.TOKEN}/{quote(rel_of(p), safe='/')}"
        folder_label = folder_label_of(p)
        links = (pill_link(site, "external", "Nouvel onglet", " target='_blank' rel='noopener'")
                 + pill_link(f"/view?f={q}", "eye", "Source"))
        if not config.READONLY:
            links += edit_pill(q, self.files_locked())
        self.send_html(
            doc_open(f"Aperçu · {p.name} — Ma bibliothèque", "ed-page")
            + render("viewer/header", back=back, title=escape(p.name), dirty="", small_attrs="",
                     subtitle=f"Aperçu · {escape(folder_label)}", save_button="", theme_button=theme_button(),
                     tools=render("viewer/tools_preview", links=links))
            + render("viewer/preview_frame", site=site)
            + doc_close(THEME_JS + PREVIEW_JS))

    def page_markdown(self, p):
        """Aperçu Markdown : rendu dans le navigateur (MD_JS, sans dépendance), mise en page de lecture."""
        text, enc, crlf, err = load_text(p)
        q = quote(rel_of(p), safe="")
        back = folder_url(p.parent)
        if err:
            self.send_html(unreadable_page(p, err, q, back), 200)
            return
        rel_dir = "" if p.parent == config.ROOT else rel_of(p.parent)
        folder_label = folder_label_of(p)
        exts = {name: sorted(e.lstrip(".") for e in group) for name, group in (
            ("md", MD_EXT), ("web", WEB_EXT), ("image", IMAGE_EXT), ("video", VIDEO_EXT),
            ("audio", AUDIO_EXT), ("binary", BINARY_EXT))}
        cfg = {
            "name": p.name, "doc": text, "q": q, "dir": rel_dir, "label": folder_label, "exts": exts,
            "site": f"/s/{config.TOKEN}/",
            "ico": {n: icon(n, 18) for n in ("info", "bulb", "msg_alert", "alert", "octagon")},
        }
        links = pill_link(f"/view?f={q}", "code", "Source")
        if not config.READONLY:
            links += edit_pill(q, self.files_locked())
        self.send_html(
            doc_open(f"{p.name} — Ma bibliothèque", "ed-page md-page", MD_CSS)
            + render("viewer/header", back=back, title=escape(p.name), dirty="", small_attrs=" id='md-meta'",
                     subtitle=f"Aperçu · {escape(folder_label)}", save_button="", theme_button=theme_button(),
                     tools=render("viewer/tools_markdown", links=links))
            + render("viewer/markdown_body")
            + doc_close(f"window.MDCFG = {js_json(cfg)}; {THEME_JS}{MD_JS}"))
