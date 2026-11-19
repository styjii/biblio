"""Page d'accueil : dossiers d'entrée, fichiers fréquents de l'appareil, lecteur multimédia local."""

from html import escape
from urllib.parse import quote

from app import config
from app.assets import HOME_CSS, HOME_JS, PROGRESS_JS, THEME_JS, WATCH_JS
from app.devices import monitor
from app.icons import icon
from app.templating import render
from app.utils import js_json
from app.views.layout import doc_close, doc_open, lock_script, topbar
from app.views.player import player_icons, shortcuts_hint, video_box

FREQUENT_LIMIT = 5

# catégorie d'historique -> (page qui ouvre le fichier, icône, couleur d'icône)
FREQUENT_OPEN = {
    "video": ("/watch", "film", "media"),
    "audio": ("/listen", "music", "media"),
    "pdf": ("/pdf", "file", "pdf"),
    "text": ("/view", "file", "text"),
    "web": ("/view", "globe", "web"),
    "image": ("/image", "image", "media"),
}


def open_url(mount_id, target):
    """Lien qui active un dossier d'entrée (cookie) puis redirige vers `target` (chemin local du serveur)."""
    return f"/open?root={quote(mount_id, safe='')}&to={quote(target, safe='')}"


def _roots():
    active = config.library.current
    items = []
    for m in config.library.mounts:
        tags = ""
        if m.launch:
            tags += "<span class='rtag cur'>Dossier courant</span>"
        if m.id == active.id and m.available:
            tags += "<span class='rtag on'>Actif</span>"
        name, path = escape(m.name), escape(m.shown, quote=True)
        if m.available:
            items.append(render("home/root_item", id=quote(m.id, safe=""), cls=" active" if m.id == active.id else "",
                                name=name, path=path, tags=tags))
        else:
            items.append(render("home/root_item_off", name=name, path=path, tags=tags))
    return "".join(items), len(items)


def _frequent(ip):
    """Les fichiers les plus consultés par cet appareil qui existent encore, avec leur dossier d'entrée."""
    cards = []
    legacy = config.library.default.id
    for entry in monitor.history.frequent(ip, limit=40, legacy_root=legacy):
        mount = config.library.get(entry["root"])
        if mount is None or not mount.available:
            continue
        p = config.paths.resolve(entry["file"], mount)
        if p is None or not p.is_file():
            continue
        page, ic, cls = FREQUENT_OPEN[entry["cat"]]
        parent = entry["file"].rpartition("/")[0]
        n = entry["n"]
        cards.append(render("home/frequent_item", href=escape(open_url(mount.id, f"{page}?f={quote(entry['file'], safe='')}"), quote=True),
                            title=escape(entry["file"], quote=True), cls=cls, icon_svg=icon(ic, 22), name=escape(p.name),
                            where=escape(f"{mount.name}/{parent}" if parent else mount.name),
                            count=f"{n} consultation{'s' if n > 1 else ''}"))
        if len(cards) == FREQUENT_LIMIT:
            break
    if not cards:
        return render("home/frequent_empty"), 0
    return render("home/frequent_list", items="".join(cards)), len(cards)


def home_page(ip):
    roots, roots_count = _roots()
    frequent, frequent_count = _frequent(ip)
    player = render("home/player", box=video_box("", "", ""), hint=shortcuts_hint())
    body = render("home/body", roots=roots, roots_count=roots_count, frequent=frequent, frequent_count=frequent_count,
                  player=player)
    # Même script que la page de lecture vidéo, en mode « local » : la liste est celle des fichiers choisis sur l'appareil
    cfg = {"local": True, "folder": "local", "key": "local", "index": 0, "download": "", "items": []}
    wico = player_icons("film", "music", "close")
    return (doc_open("Accueil — Ma bibliothèque", "", HOME_CSS) + topbar(False, True) + body
            + doc_close(f"window.WCFG = {js_json(cfg)}; window.WICO = {js_json(wico)}; {THEME_JS}{PROGRESS_JS}{WATCH_JS}{HOME_JS}",
                        after=lock_script()))
