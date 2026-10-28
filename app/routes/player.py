"""Lecteurs vidéo et audio, miniatures, pochettes, métadonnées et sous-titres."""

from html import escape
from urllib.parse import quote

from app import config
from app.assets import DECORATE_JS, LISTEN_CSS, LISTEN_JS, THEME_JS, WATCH_JS
from app.filesystem import guess_mime, kind_of, list_dir, rel_of, resolve_inside
from app.icons import icon
from app.media import (LANGS, SUB_TYPES, audio_info, cover_for, duration_of, ffmpeg_semaphore, find_subtitles,
                       has_cover, srt_to_vtt, thumb_for)
from app.templating import render
from app.utils import fmt_size, js_json
from app.views.cards import video_row
from app.views.layout import EDIT_LOCKED_HINT, doc_close, doc_open, folder_url, topbar


class PlayerRoutes:
    def page_watch(self, rel):
        p = resolve_inside(rel)
        if p is None or not p.is_file() or kind_of(p) != "video":
            self.send_error(404, "Vidéo introuvable")
            return
        _, files = list_dir(p.parent)
        siblings = [f for f in (files or []) if kind_of(f) == "video"] or [p]
        try:
            idx = siblings.index(p)
        except ValueError:
            idx = -1
        prev_p = siblings[idx - 1] if idx > 0 else None
        next_p = siblings[idx + 1] if 0 <= idx < len(siblings) - 1 else None

        def watch_url(x):
            return "/watch?f=" + quote(rel_of(x), safe="")

        q = quote(rel_of(p), safe="")
        try:
            size = fmt_size(p.stat().st_size)
        except OSError:
            size = ""
        folder_rel = p.parent.relative_to(config.ROOT)
        folder_name = folder_rel.name if folder_rel.parts else (config.ROOT.name or "Accueil")

        tracks, sub_chips = "", ""
        for f, tag in find_subtitles(p):
            code = tag.lower()
            label = LANGS.get(code, tag or "Sous-titres")
            lang = code if code.isalpha() and 2 <= len(code) <= 3 else "fr"
            fq = quote(rel_of(f), safe="")
            tracks += render("player/track", q=fq, lang=lang, label=escape(label, quote=True))
            if not config.READONLY:
                if self.files_locked():
                    sub_chips += render("player/subtitle_chip_locked", label=escape(label),
                                        hint=escape(EDIT_LOCKED_HINT, quote=True))
                else:
                    sub_chips += render("player/subtitle_chip", q=fq, label=escape(label))

        def nav_btn(target, kind, text):
            if target is None:
                return render("player/nav_button_disabled", icon_svg=icon(kind, 16), text=text)
            return render("player/nav_button", href=watch_url(target), icon_svg=icon(kind, 16), text=text)

        page = render("player/watch", q=q, tracks=tracks, title=escape(p.stem),
                      folder_href=folder_url(p.parent), folder_name=escape(folder_name),
                      size=size, ext=p.suffix[1:].upper(),
                      prev_button=nav_btn(prev_p, "prev", "Précédente"),
                      next_button=nav_btn(next_p, "next", "Suivante"),
                      sub_chips=sub_chips, rows="".join(video_row(v, p) for v in siblings))
        cfg = {"key": f"{config.ROOT_ID}:{rel_of(p)}", "next": watch_url(next_p) if next_p else None}
        self.send_html(doc_open(f"{p.stem} — Ma bibliothèque") + topbar(False) + page
                       + doc_close(f"window.WCFG = {js_json(cfg)}; {THEME_JS}{DECORATE_JS}{WATCH_JS}"))

    def page_listen(self, rel):
        p = resolve_inside(rel)
        if p is None or not p.is_file() or kind_of(p) != "audio":
            self.send_error(404, "Fichier audio introuvable")
            return
        _, files = list_dir(p.parent)
        siblings = [f for f in (files or []) if kind_of(f) == "audio"] or [p]
        try:
            start = siblings.index(p)
        except ValueError:
            siblings.insert(0, p)
            start = 0
        folder_rel = p.parent.relative_to(config.ROOT)
        folder_name = folder_rel.name if folder_rel.parts else (config.ROOT.name or "Accueil")
        tracks = [{"f": rel_of(f), "q": quote(rel_of(f), safe=""), "n": f.stem, "e": f.suffix[1:].upper()}
                  for f in siblings]
        cfg = {"tracks": tracks, "start": start, "folder": folder_name,
               "back": folder_url(p.parent), "key": config.ROOT_ID}

        lico = {n: icon(n, 24) for n in ("play", "pause", "repeat", "repeat1", "volume", "mute",
                                         "music", "loader", "eq")}
        self.send_html(
            doc_open(f"{p.stem} — Lecteur audio", "", LISTEN_CSS) + topbar(False)
            + render("player/listen", folder_href=folder_url(p.parent), folder_name=escape(folder_name))
            + doc_close(f"window.LCFG = {js_json(cfg)}; window.LICO = {js_json(lico)}; {THEME_JS}{LISTEN_JS}"))

    def serve_thumb(self, rel):
        p = resolve_inside(rel)
        t = thumb_for(p) if p and p.is_file() and kind_of(p) == "video" else None
        if t is None:
            self.send_error(404)
            return
        self.send_bytes(t.read_bytes(), "image/jpeg", 200, {"Cache-Control": "private, max-age=86400"})

    def serve_meta(self, rel):
        p = resolve_inside(rel)
        kind = kind_of(p) if p is not None and p.is_file() else None
        if kind not in ("video", "audio"):
            self.send_error(404)
            return
        if kind == "audio":
            with ffmpeg_semaphore:
                info = audio_info(p)
            self.send_json({"duration": info["duration"], "title": info["title"], "artist": info["artist"],
                            "album": info["album"], "cover": has_cover(p, info)})
            return
        with ffmpeg_semaphore:
            dur = duration_of(p)
        self.send_json({"duration": dur})

    def serve_cover(self, rel):
        p = resolve_inside(rel)
        c = cover_for(p) if p is not None and p.is_file() and kind_of(p) == "audio" else None
        if c is None:
            self.send_error(404)
            return
        ctype = "image/jpeg" if c.suffix.lower() in (".jpg", ".jpeg") else guess_mime(c)
        self.send_file(c, ctype, None, {"Cache-Control": "private, max-age=86400"})

    def serve_sub(self, rel):
        p = resolve_inside(rel)
        if not p or not p.is_file() or p.suffix.lower() not in SUB_TYPES:
            self.send_error(404)
            return
        raw = p.read_bytes()
        try:
            text = raw.decode("utf-8-sig")
        except UnicodeDecodeError:
            text = raw.decode("latin-1")
        self.send_bytes(srt_to_vtt(text).encode("utf-8"), "text/vtt; charset=utf-8")
