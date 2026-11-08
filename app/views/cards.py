"""Cartes et lignes des listes de fichiers / vidéos."""

from html import escape
from urllib.parse import quote

from app.filesystem import rel_of
from app.filetypes import CODE_EXT, MD_EXT
from app.icons import icon
from app.media import media
from app.templating import render
from app.utils import fmt_size


def icon_for(p, kind):
    """-> (nom d'icône, classe de couleur)"""
    if kind == "web":
        return "globe", "web"
    if kind == "image":
        return "image", "media"
    if kind == "video":
        return "film", "media"
    if kind == "audio":
        return "music", "media"
    if kind == "pdf":
        return "file", "media"
    if kind == "binary":
        return "box", "binary"
    if p.suffix.lower() in MD_EXT:
        return "book", "code"
    if p.suffix.lower() in CODE_EXT:
        return "code", "code"
    return "file", "text"


GROUPS = [("video", "Vidéos"), ("pdf", "Documents PDF"), ("text", "Texte et code"),
          ("web", "Pages web"), ("media", "Images et audio"), ("other", "Autres fichiers")]


def group_of(kind):
    return {"video": "video", "pdf": "pdf", "text": "text", "web": "web",
            "image": "media", "audio": "media", "binary": "other"}[kind]


def _stat(p):
    """-> (taille en octets, date de modification en secondes) ; (0, 0) si illisible."""
    try:
        st = p.stat()
        return st.st_size, int(st.st_mtime)
    except OSError:
        return 0, 0


def _size_of(p):
    try:
        return fmt_size(p.stat().st_size)
    except OSError:
        return ""


def sort_attrs(p, order):
    """Attributs data-* lus par le tri de la liste (frontend/js/browse/00-tri.js) : rang par nom (ordre naturel du serveur),
    octets, date, extension."""
    nbytes, mtime = _stat(p)
    return f"data-order='{order}' data-bytes='{nbytes}' data-mtime='{mtime}' data-ext='{escape(p.suffix[1:].casefold(), quote=True)}'"


def file_card(p, kind, order=0):
    ic, cls = icon_for(p, kind)
    if kind == "pdf":
        cls = "pdf"
    q = quote(rel_of(p), safe="")
    size = _size_of(p)
    href = {"text": f"/view?f={q}", "web": f"/view?f={q}", "pdf": f"/pdf?f={q}",
            "image": f"/raw?f={q}", "audio": f"/listen?f={q}", "binary": f"/raw?dl=1&f={q}"}[kind]
    direct = kind in ("pdf", "image", "audio")
    ext = p.suffix[1:].upper() if p.suffix else "FICHIER"
    has_menu = kind in ("pdf", "image", "audio", "binary")
    return render("components/file_card",
                  dot=" dot" if p.name.startswith(".") else "",
                  href=href, q=q, kind=kind,
                  md=" data-md='1'" if p.suffix.lower() in MD_EXT else "",
                  direct=1 if direct else 0, ic=ic, cls=cls, group=group_of(kind), sort=sort_attrs(p, order),
                  title=escape(p.name, quote=True), size=size, ext=ext,
                  name_key=escape(p.name.casefold(), quote=True),
                  icon_svg=icon(ic, 22), name=escape(p.name),
                  right=render("components/more_button" if has_menu else "components/go_chevron"))


def video_card(p, order=0):
    q = quote(rel_of(p), safe="")
    return render("components/video_card",
                  dot=" dot" if p.name.startswith(".") else "",
                  q=q, key=media.key(p), title=escape(p.name, quote=True), sort=sort_attrs(p, order),
                  size=_size_of(p), ext=p.suffix[1:].upper(),
                  name_key=escape(p.name.casefold(), quote=True),
                  more_button=render("components/more_button"), name=escape(p.stem))


def video_row(p, current):
    q = quote(rel_of(p), safe="")
    size = _size_of(p)
    return render("components/video_row",
                  cur=" cur" if p == current else "", q=q, key=media.key(p),
                  name=escape(p.stem), sub="En lecture" if p == current else size)
