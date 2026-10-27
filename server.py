import argparse
import errno
import gzip
import hashlib
import hmac
import ipaddress
import json
import mimetypes
import os
import re
import secrets
import shutil
import signal
import socket
import stat
import subprocess
import threading
import time
from collections import deque
from html import escape
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, quote, unquote, urlencode, urlsplit

# Dossier servi : celui passé en argument, sinon le dossier courant.
ROOT = Path(os.environ.get("BIBLIO_DOCS", Path.cwd())).resolve()
PORT = int(os.environ.get("BIBLIO_PORT", "8088"))
READONLY = False
TOKEN = ""
PASSWORD = ""      # BIBLIO_PASSWORD (.env) : vide = suppression, renommage et envoi désactivés (aucun déverrouillage possible)
DASH_PASSWORD = ""   # BIBLIO_DASHBOARD_PASSWORD (.env), à défaut BIBLIO_PASSWORD : vide = tableau de bord désactivé
ENV_PATH = None    # fichier .env (jeton, mot de passe)
ENV = {}           # valeurs lues dans le .env
MAX_UPLOAD = 4096 * 1024 * 1024   # taille max d'un fichier envoyé (BIBLIO_MAX_UPLOAD_MB, 0 = illimité)
UPLOAD_CHUNK = 1024 * 1024
UPLOAD_MIN_FREE = 64 * 1024 * 1024    # espace disque à toujours laisser libre
DRAIN_MAX = 512 * 1024 * 1024         # corps d'une requête refusée que l'on accepte de lire et jeter
HERE = Path(__file__).resolve().parent
BUNDLE = HERE / "editor.bundle.js"
ROOT_ID = ""
FFMPEG = shutil.which("ffmpeg")
FFPROBE = shutil.which("ffprobe")
CACHE = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / "biblio"
PDFJS_DIR = None
SUB_TYPES = {".srt", ".vtt"}
LANGS = {"fr": "Français", "en": "English", "ar": "Arabe",
         "es": "Español", "de": "Deutsch", "it": "Italiano"}
_sem = threading.Semaphore(2)
_durations = {}
_ainfo = {}
_failed = set()
COVER_NAMES = {"cover", "folder", "front", "album", "albumart", "artwork"}
COVER_EXT = {".jpg", ".jpeg", ".png", ".webp"}

MAX_TEXT = 2 * 1024 * 1024      # lecture / édition
MAX_SAVE = 5 * 1024 * 1024      # enregistrement

WEB_EXT = {".html", ".htm", ".xhtml", ".svg"}
IMAGE_EXT = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".ico", ".avif"}
VIDEO_EXT = {".mp4", ".webm", ".mkv", ".mov", ".m4v", ".avi", ".ogv"}
AUDIO_EXT = {".mp3", ".wav", ".ogg", ".m4a", ".flac", ".opus", ".aac"}
BINARY_EXT = {
    ".zip", ".tar", ".gz", ".tgz", ".bz2", ".xz", ".7z", ".rar", ".iso", ".exe", ".dll",
    ".so", ".bin", ".o", ".pyc", ".class", ".jar", ".apk", ".deb", ".sqlite", ".sqlite3",
    ".db", ".xlsx", ".xls", ".docx", ".doc", ".pptx", ".odt", ".ods", ".ttf", ".otf",
    ".woff", ".woff2",
}
TEXT_EXT = {
    ".txt", ".srt", ".vtt", ".csv", ".tsv", ".log", ".ini", ".cfg", ".conf", ".env", ".lock",
    ".gitignore", ".rst", ".tex", ".bib", ".diff", ".patch", ".properties", ".service",
}
CODE_EXT = {
    ".py", ".js", ".mjs", ".cjs", ".ts", ".tsx", ".jsx", ".java", ".c", ".h", ".cpp", ".hpp",
    ".cc", ".rs", ".go", ".php", ".rb", ".sh", ".bash", ".zsh", ".sql", ".css", ".scss",
    ".json", ".yml", ".yaml", ".toml", ".xml", ".lua", ".md", ".ipynb",
}
MD_EXT = {".md", ".markdown", ".mdown", ".mkd"}   # fichiers Markdown : aperçu rendu (/preview)
CODE_EXT |= MD_EXT

EXTRA_MIME = {
    ".js": "text/javascript", ".mjs": "text/javascript", ".css": "text/css",
    ".html": "text/html", ".htm": "text/html", ".svg": "image/svg+xml",
    ".json": "application/json", ".webp": "image/webp", ".avif": "image/avif",
    ".mkv": "video/x-matroska", ".m4a": "audio/mp4", ".woff2": "font/woff2",
    ".mjs": "text/javascript", ".wasm": "application/wasm", ".ftl": "text/plain", ".map": "application/json",
    ".mp3": "audio/mpeg", ".wav": "audio/wav", ".ogg": "audio/ogg", ".opus": "audio/ogg",
    ".flac": "audio/flac", ".aac": "audio/aac",
}


# --------------------------------------------------------------------------
# Icônes SVG (style Lucide, intégrées : aucune dépendance externe)
# --------------------------------------------------------------------------
ICONS = {
    "logo": '<polyline points="16 18 22 12 16 6"/><polyline points="8 6 2 12 8 18"/>',
    "folder": '<path d="M20 20a2 2 0 0 0 2-2V8a2 2 0 0 0-2-2h-7.9a2 2 0 0 1-1.69-.9L9.6 3.9A2 2 0 0 0 7.93 3H4a2 2 0 0 0-2 2v13a2 2 0 0 0 2 2Z"/>',
    "file": '<path d="M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7Z"/>'
            '<path d="M14 2v4a2 2 0 0 0 2 2h4"/><path d="M10 9H8"/><path d="M16 13H8"/><path d="M16 17H8"/>',
    "code": '<path d="M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7Z"/>'
            '<path d="M14 2v4a2 2 0 0 0 2 2h4"/><path d="m10 13-2 2 2 2"/><path d="m14 13 2 2-2 2"/>',
    "globe": '<circle cx="12" cy="12" r="10"/><path d="M12 2a14.5 14.5 0 0 0 0 20 14.5 14.5 0 0 0 0-20"/><path d="M2 12h20"/>',
    "image": '<rect width="18" height="18" x="3" y="3" rx="2"/><circle cx="9" cy="9" r="2"/>'
             '<path d="m21 15-3.09-3.09a2 2 0 0 0-2.82 0L6 21"/>',
    "film": '<rect width="18" height="18" x="3" y="3" rx="2"/><path d="M7 3v18"/><path d="M3 7.5h4"/>'
            '<path d="M3 12h18"/><path d="M3 16.5h4"/><path d="M17 3v18"/><path d="M17 7.5h4"/><path d="M17 16.5h4"/>',
    "music": '<path d="M9 18V5l12-2v13"/><circle cx="6" cy="18" r="3"/><circle cx="18" cy="16" r="3"/>',
    "box": '<path d="M21 8 12 3 3 8v8l9 5 9-5z"/><path d="m3 8 9 5 9-5"/><path d="M12 13v8"/>',
    "back": '<path d="m12 19-7-7 7-7"/><path d="M19 12H5"/>',
    "chevron": '<path d="m9 18 6-6-6-6"/>',
    "home": '<path d="m3 9 9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/><path d="M9 22V12h6v10"/>',
    "sun": '<circle cx="12" cy="12" r="4"/><path d="M12 2v2"/><path d="M12 20v2"/>'
           '<path d="m4.93 4.93 1.41 1.41"/><path d="m17.66 17.66 1.41 1.41"/>'
           '<path d="M2 12h2"/><path d="M20 12h2"/><path d="m6.34 17.66-1.41 1.41"/><path d="m19.07 4.93-1.41 1.41"/>',
    "moon": '<path d="M12 3a6 6 0 0 0 9 9 9 9 0 1 1-9-9Z"/>',
    "search": '<circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/>',
    "eye": '<path d="M2 12s3-7 10-7 10 7 10 7-3 7-10 7-10-7-10-7Z"/><circle cx="12" cy="12" r="3"/>',
    "edit": '<path d="M12 20h9"/><path d="M16.5 3.5a2.12 2.12 0 0 1 3 3L7 19l-4 1 1-4Z"/>',
    "download": '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/>'
                '<line x1="12" x2="12" y1="15" y2="3"/>',
    "external": '<path d="M15 3h6v6"/><path d="M10 14 21 3"/>'
                '<path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/>',
    "plus": '<path d="M5 12h14"/><path d="M12 5v14"/>',
    "minus": '<path d="M5 12h14"/>',
    "close": '<path d="M18 6 6 18"/><path d="m6 6 12 12"/>',
    "save": '<path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z"/>'
            '<polyline points="17 21 17 13 7 13 7 21"/><polyline points="7 3 7 8 15 8"/>',
    "keyboard": '<rect width="20" height="16" x="2" y="4" rx="2"/><path d="M6 8h.01"/><path d="M10 8h.01"/>'
                '<path d="M14 8h.01"/><path d="M18 8h.01"/><path d="M8 12h.01"/><path d="M12 12h.01"/>'
                '<path d="M16 12h.01"/><path d="M7 16h10"/>',
    "refresh": '<path d="M3 12a9 9 0 0 1 9-9 9.75 9.75 0 0 1 6.74 2.74L21 8"/><path d="M21 3v5h-5"/>'
               '<path d="M21 12a9 9 0 0 1-9 9 9.75 9.75 0 0 1-6.74-2.74L3 16"/><path d="M8 16H3v5"/>',
}


ICONS.update({
    "library": '<path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z"/><path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z"/>',
    "upload": '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/>'
              '<line x1="12" x2="12" y1="3" y2="15"/>',
    "trash": '<path d="M3 6h18"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6"/>'
             '<path d="M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/><line x1="10" x2="10" y1="11" y2="17"/>'
             '<line x1="14" x2="14" y1="11" y2="17"/>',
    "play": '<polygon points="6 3 20 12 6 21 6 3"/>',
    "next": '<polygon points="5 4 15 12 5 20 5 4"/><line x1="19" x2="19" y1="5" y2="19"/>',
    "prev": '<polygon points="19 20 9 12 19 4 19 20"/><line x1="5" x2="5" y1="19" y2="5"/>',
    "more": '<circle cx="12" cy="12" r="1"/><circle cx="19" cy="12" r="1"/><circle cx="5" cy="12" r="1"/>',
    "dashboard": '<rect width="7" height="9" x="3" y="3" rx="1"/><rect width="7" height="5" x="14" y="3" rx="1"/>'
                 '<rect width="7" height="9" x="14" y="12" rx="1"/><rect width="7" height="5" x="3" y="16" rx="1"/>',
    "monitor": '<rect width="20" height="14" x="2" y="3" rx="2"/><path d="M8 21h8"/><path d="M12 17v4"/>',
    "ban": '<circle cx="12" cy="12" r="10"/><path d="m4.9 4.9 14.2 14.2"/>',
    "lock": '<rect width="18" height="11" x="3" y="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/>',
    "pause": '<rect x="14" y="4" width="4" height="16" rx="1"/><rect x="6" y="4" width="4" height="16" rx="1"/>',
    "shuffle": '<path d="m18 14 4 4-4 4"/><path d="m18 2 4 4-4 4"/><path d="M2 18h1.973a4 4 0 0 0 3.3-1.7l5.454-8.6a4 4 0 0 1 3.3-1.7H22"/>'
               '<path d="M2 6h1.972a4 4 0 0 1 3.6 2.2"/><path d="M22 18h-6.041a4 4 0 0 1-3.3-1.8l-.359-.45"/>',
    "repeat": '<path d="m17 2 4 4-4 4"/><path d="M3 11v-1a4 4 0 0 1 4-4h14"/><path d="m7 22-4-4 4-4"/><path d="M21 13v1a4 4 0 0 1-4 4H3"/>',
    "repeat1": '<path d="m17 2 4 4-4 4"/><path d="M3 11v-1a4 4 0 0 1 4-4h14"/><path d="m7 22-4-4 4-4"/><path d="M21 13v1a4 4 0 0 1-4 4H3"/>' + '<path d="M11 10h1v4"/>',
    "volume": '<path d="M11 4.702a.705.705 0 0 0-1.203-.498L6.413 7.587A1.4 1.4 0 0 1 5.416 8H3a1 1 0 0 0-1 1v6a1 1 0 0 0 1 1h2.416a1.4 1.4 0 0 1 .997.413l3.383 3.384A.705.705 0 0 0 11 19.298z"/>' + '<path d="M16 9a5 5 0 0 1 0 6"/><path d="M19.364 18.364a9 9 0 0 0 0-12.728"/>',
    "mute": '<path d="M11 4.702a.705.705 0 0 0-1.203-.498L6.413 7.587A1.4 1.4 0 0 1 5.416 8H3a1 1 0 0 0-1 1v6a1 1 0 0 0 1 1h2.416a1.4 1.4 0 0 1 .997.413l3.383 3.384A.705.705 0 0 0 11 19.298z"/>' + '<line x1="22" x2="16" y1="9" y2="15"/><line x1="16" x2="22" y1="9" y2="15"/>',
    "queue": '<path d="M3 12h.01"/><path d="M3 18h.01"/><path d="M3 6h.01"/><path d="M8 12h13"/><path d="M8 18h13"/><path d="M8 6h13"/>',
})

ICONS.update({
    "check": '<path d="M20 6 9 17l-5-5"/>',
    "arrow_left": '<path d="m12 19-7-7 7-7"/><path d="M19 12H5"/>',
    "arrow_right": '<path d="M5 12h14"/><path d="m12 5 7 7-7 7"/>',
    "arrow_up": '<path d="m5 12 7-7 7 7"/><path d="M12 19V5"/>',
    "arrow_down": '<path d="M12 5v14"/><path d="m19 12-7 7-7-7"/>',
    # retour / avance de 10 s : flèche circulaire + « 10 » (texte SVG, pas un emoji)
    "back10": '<path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"/><path d="M3 3v5h5"/>'
              '<text x="12" y="15.4" text-anchor="middle" font-size="7.5" font-weight="700" '
              'font-family="system-ui,sans-serif" stroke="none" fill="currentColor">10</text>',
    "fwd10": '<path d="M21 12a9 9 0 1 1-9-9c2.52 0 4.93 1 6.74 2.74L21 8"/><path d="M21 3v5h-5"/>'
             '<text x="12" y="15.4" text-anchor="middle" font-size="7.5" font-weight="700" '
             'font-family="system-ui,sans-serif" stroke="none" fill="currentColor">10</text>',
    "loader": '<path d="M21 12a9 9 0 1 1-6.219-8.56"/>',
    # indicateur « en cours de lecture » (3 barres animées en CSS)
    "eq": '<path class="b1" d="M6 20V11"/><path class="b2" d="M12 20V4"/><path class="b3" d="M18 20V14"/>',
    # aperçu Markdown
    "rename": '<path d="M5 4h1a3 3 0 0 1 3 3 3 3 0 0 1 3-3h1"/><path d="M13 20h-1a3 3 0 0 1-3-3 3 3 0 0 1-3 3H5"/>'
              '<path d="M5 16H4a2 2 0 0 1-2-2v-4a2 2 0 0 1 2-2h1"/><path d="M13 8h7a2 2 0 0 1 2 2v4a2 2 0 0 1-2 2h-7"/><path d="M9 7v10"/>',
    "unlock": '<rect width="18" height="11" x="3" y="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0 1 9.9-1"/>',
    "book": '<path d="M12 7v14"/><path d="M3 18a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1h5a4 4 0 0 1 4 4 4 4 0 0 1 4-4h5a1 1 0 0 1 1 1v13a1 1 0 0 1-1 1h-6a3 3 0 0 0-3 3 3 3 0 0 0-3-3z"/>',
    "list": '<path d="M3 12h.01"/><path d="M3 18h.01"/><path d="M3 6h.01"/><path d="M8 12h13"/><path d="M8 18h13"/><path d="M8 6h13"/>',
    "printer": '<path d="M6 18H4a2 2 0 0 1-2-2v-5a2 2 0 0 1 2-2h16a2 2 0 0 1 2 2v5a2 2 0 0 1-2 2h-2"/>'
               '<path d="M6 9V3a1 1 0 0 1 1-1h10a1 1 0 0 1 1 1v6"/><rect x="6" y="14" width="12" height="8" rx="1"/>',
    "info": '<circle cx="12" cy="12" r="10"/><path d="M12 16v-4"/><path d="M12 8h.01"/>',
    "bulb": '<path d="M15 14c.2-1 .7-1.7 1.5-2.5 1-.9 1.5-2.2 1.5-3.5A6 6 0 0 0 6 8c0 1 .2 2.2 1.5 3.5.7.7 1.3 1.5 1.5 2.5"/>'
            '<path d="M9 18h6"/><path d="M10 22h4"/>',
    "msg_alert": '<path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/><path d="M12 7v2"/><path d="M12 13h.01"/>',
    "alert": '<path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3"/><path d="M12 9v4"/><path d="M12 17h.01"/>',
    "octagon": '<polygon points="7.86 2 16.14 2 22 7.86 22 16.14 16.14 22 7.86 22 2 16.14 2 7.86 7.86 2"/>'
               '<line x1="12" x2="12" y1="8" y2="12"/><line x1="12" x2="12.01" y1="16" y2="16"/>',
})


def icon(name, size=20, cls="i"):
    return (
        f"<svg class='{cls}' width='{size}' height='{size}' viewBox='0 0 24 24' "
        "fill='none' stroke='currentColor' stroke-width='2' "
        "stroke-linecap='round' stroke-linejoin='round' aria-hidden='true'>"
        f"{ICONS[name]}</svg>"
    )


FAVICON = (
    "<link rel='icon' href=\"data:image/svg+xml," + quote(
        "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'><rect width='32' height='32' rx='8' fill='#4f5bd5'/>"
        "<g transform='translate(4 4)' fill='none' stroke='#fff' stroke-width='2' stroke-linecap='round' "
        "stroke-linejoin='round'>" + ICONS["library"] + "</g></svg>") + "\">"
)


# --------------------------------------------------------------------------
# Thème et scripts communs
# --------------------------------------------------------------------------
THEME_INIT = """
<script>
(function(){
  var t = null;
  try { t = localStorage.getItem('theme'); } catch(e) {}
  if (t !== 'light' && t !== 'dark') {
    t = matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
  }
  document.documentElement.dataset.theme = t;
})();
</script>
"""

THEME_JS = """
(function(){
  var root = document.documentElement;
  var btn = document.getElementById('theme-toggle');
  if (!btn) return;
  btn.addEventListener('click', function(){
    var next = root.dataset.theme === 'dark' ? 'light' : 'dark';
    root.dataset.theme = next;
    try { localStorage.setItem('theme', next); } catch(e) {}
  });
})();
"""

DECORATE_JS = """
(function(){
  function fmt(s){
    s = Math.floor(s);
    var h = Math.floor(s / 3600), m = Math.floor(s % 3600 / 60), x = s % 60;
    var mm = h ? ('0' + m).slice(-2) : String(m);
    return (h ? h + ':' : '') + mm + ':' + ('0' + x).slice(-2);
  }
  function load(key){
    try { return JSON.parse(localStorage.getItem('vl:pos:' + key)); }
    catch(e) { return null; }
  }
  function bar(el, t, d){
    var b = el.querySelector('.bar');
    if (!b || !d || !t) return;
    b.hidden = false;
    b.firstElementChild.style.width = Math.min(100, t / d * 100) + '%';
  }
  var items = document.querySelectorAll('[data-key]');
  var io = 'IntersectionObserver' in window ? new IntersectionObserver(function(es){
    es.forEach(function(e){
      if (!e.isIntersecting) return;
      io.unobserve(e.target);
      var el = e.target;
      fetch('/meta?f=' + el.dataset.f)
        .then(function(r){ return r.json(); })
        .then(function(j){
          if (!j.duration) return;
          var d = el.querySelector('.dur');
          if (d) { d.textContent = fmt(j.duration); d.hidden = false; }
          var s = load(el.dataset.key);
          if (s) bar(el, s.t, s.d || j.duration);
        }).catch(function(){});
    });
  }, {rootMargin: '200px'}) : null;
  items.forEach(function(el){
    var s = load(el.dataset.key);
    if (s && s.d) bar(el, s.t, s.d);
    if (io) io.observe(el);
  });
})();
"""

BROWSE_JS = """
(function(){
  var cfg = window.FLCFG, ICO = window.ICO;
  var body = document.body;
  var active = 'all';
  try { if (localStorage.getItem('fl:hidden') === '1') body.classList.add('show-hidden'); } catch(e) {}

  function visible(el){
    return !el.hidden && (!el.classList.contains('dot') || body.classList.contains('show-hidden'));
  }
  function refresh(){
    var shown = 0, per = {};
    document.querySelectorAll('.section').forEach(function(s){
      var g = s.dataset.group, n = 0;
      s.querySelectorAll('[data-name]').forEach(function(el){ if (visible(el)) n++; });
      s.querySelector('.count').textContent = n;
      var off = g !== 'folders' && active !== 'all' && g !== active;
      s.classList.toggle('off', off);
      s.hidden = n === 0;
      if (g !== 'folders') per[g] = n;
      if (!off) shown += n;
    });
    document.querySelectorAll('.fchip').forEach(function(c){
      var g = c.dataset.g, n = 0;
      if (g === 'all') { Object.keys(per).forEach(function(k){ n += per[k]; }); }
      else { n = per[g] || 0; }
      c.querySelector('b').textContent = n;
      c.classList.toggle('on', g === active);
    });
    var none = document.getElementById('no-result');
    if (none) none.hidden = shown !== 0;
  }

  document.querySelectorAll('.fchip').forEach(function(c){
    c.addEventListener('click', function(){ active = c.dataset.g; refresh(); });
  });

  var hid = document.getElementById('toggle-hidden');
  if (hid) {
    hid.checked = body.classList.contains('show-hidden');
    hid.addEventListener('change', function(){
      body.classList.toggle('show-hidden', hid.checked);
      try { localStorage.setItem('fl:hidden', hid.checked ? '1' : '0'); } catch(e) {}
      refresh();
    });
  }

  var search = document.getElementById('search');
  if (search) {
    search.addEventListener('input', function(){
      var q = search.value.trim().toLowerCase();
      document.querySelectorAll('[data-name]').forEach(function(el){
        el.hidden = el.dataset.name.indexOf(q) === -1;
      });
      refresh();
    });
  }
  refresh();

  // ----- menu d'actions
  var OPTS = {
    watch:    {ic:'play',     t:'Regarder',           d:'Lire la vidéo',                        u:function(f){return '/watch?f='+f;}},
    pdf:      {ic:'file',     t:'Lire le PDF',        d:'Ouvrir dans le lecteur PDF',           u:function(f){return '/pdf?f='+f;}},
    view:     {ic:'eye',      t:'Lire',               d:'Affichage avec coloration syntaxique', u:function(f){return '/view?f='+f;}},
    edit:     {ic:'edit',     t:'Éditer',             d:'Éditeur de type Vim',                  u:function(f){return '/edit?f='+f;}, prot:true},
    preview:  {ic:'globe',    t:'Aperçu de la page',  d:'Afficher la page web rendue',          u:function(f){return '/preview?f='+f;}},
    mdview:   {ic:'book',     t:'Aperçu',             d:'Rendu Markdown, mis en page pour la lecture', u:function(f){return '/preview?f='+f;}},
    mdsrc:    {ic:'code',     t:'Source',             d:'Texte brut avec coloration syntaxique', u:function(f){return '/view?f='+f;}},
    listen:   {ic:'music',    t:'Écouter',            d:'Lecteur audio (aléatoire, répétition…)', u:function(f){return '/listen?f='+f;}},
    open:     {ic:'external', t:'Ouvrir',             d:'Afficher dans le navigateur',          u:function(f){return '/raw?f='+f;}},
    download: {ic:'download', t:'Télécharger',        d:'Enregistrer une copie',                u:function(f){return '/raw?dl=1&f='+f;}},
    rename:   {ic:'rename',   t:'Renommer',           d:'Changer le nom du fichier',            u:null, prot:true},
    del:      {ic:'trash',    t:'Supprimer',          d:'Supprimer définitivement',             u:null, danger:true, prot:true}
  };
  var BY = {
    video:['watch','open','download'], pdf:['pdf','open','download'], text:['view','edit','download'],
    web:['preview','view','edit','download'], image:['open','download'], audio:['listen','open','download'],
    binary:['download'], md:['mdview','mdsrc','edit','download']
  };
  var wrap = document.getElementById('sheet');
  var bodyEl = document.getElementById('sh-body');

  var upRunning = false, upDirty = false;
  function closeSheet(){
    if (upRunning) return;
    var reload = upDirty;
    wrap.hidden = true; document.getElementById('newdlg').hidden = true; document.getElementById('deldlg').hidden = true;
    document.getElementById('rendlg').hidden = true; document.getElementById('edtdlg').hidden = true;
    document.getElementById('updlg').hidden = true; bodyEl.innerHTML = '';
    if (reload) location.reload();
  }
  function esc(s){ return s.replace(/[&<>"']/g, function(c){ return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]; }); }

  function openMenu(a){
    var kind = a.dataset.kind, f = a.dataset.f;
    var list = (a.dataset.md === '1' ? BY.md : (BY[kind] || ['view','edit','download'])).filter(function(k){
      return !(cfg.readonly && k === 'edit');
    });
    if (cfg.canDelete) list.push('rename', 'del');
    document.getElementById('sh-title').textContent = a.dataset.title;
    document.getElementById('sh-sub').textContent = a.dataset.size;
    var ic = document.getElementById('sh-ico');
    ic.innerHTML = ICO[a.dataset.ico] || '';
    ic.className = 'ico ' + (a.dataset.icls || '');
    bodyEl.innerHTML = list.map(function(k){
      var o = OPTS[k];
      var desc = (o.prot && cfg.protect && !cfg.unlocked) ? 'Accès verrouillé' : o.d;
      return '<a class="opt' + (o.danger ? ' danger" data-del="1' : (k === 'rename' ? '" data-ren="1' : (k === 'edit' ? '" data-edt="1' : ''))) + '" href="' + (o.u ? o.u(f) : '#') + '"><span class="ico back">' + ICO[o.ic] + '</span>' +
        '<span class="text"><span class="name">' + esc(o.t) + '</span><div class="sub">' + esc(desc) + '</div></span>' +
        '<span class="go">' + ICO.chevron + '</span></a>';
    }).join('');
    var dl = bodyEl.querySelector('[data-del]');
    if (dl) dl.addEventListener('click', function(e){ e.preventDefault(); askDelete(a); });
    var rn = bodyEl.querySelector('[data-ren]');
    if (rn) rn.addEventListener('click', function(e){ e.preventDefault(); askRename(a); });
    var ed = bodyEl.querySelector('[data-edt]');
    if (ed) ed.addEventListener('click', function(e){
      if (cfg.protect && !cfg.unlocked) { e.preventDefault(); askEdit(a); }
    });
    document.getElementById('rendlg').hidden = true;
    document.getElementById('newdlg').hidden = true;
    document.getElementById('deldlg').hidden = true;
    document.getElementById('edtdlg').hidden = true;
    document.getElementById('sheet-main').hidden = false;
    wrap.hidden = false;
  }

  // ----- suppression (déverrouillage requis ; aucun mot de passe n'est demandé ici)
  var delTarget = null;
  function delPaint(){
    var locked = !cfg.unlocked;
    document.getElementById('del-locked').hidden = !locked;
    document.getElementById('delok').hidden = locked;
  }
  function askDelete(a){
    delTarget = a;
    document.getElementById('del-name').textContent = a.dataset.title;
    document.getElementById('delerr').textContent = '';
    delPaint();
    document.getElementById('sheet-main').hidden = true;
    document.getElementById('deldlg').hidden = false;
  }
  document.getElementById('delcancel').addEventListener('click', closeSheet);
  document.getElementById('delform').addEventListener('submit', function(e){
    e.preventDefault();
    var err = document.getElementById('delerr'), btn = document.getElementById('delok');
    if (!delTarget || !cfg.canDelete || !cfg.unlocked) return;
    btn.disabled = true; err.textContent = '';
    fetch('/delete?f=' + delTarget.dataset.f, {method: 'POST', headers: {'X-Requested-With': 'biblio'}})
      .then(function(r){ return r.json().then(function(j){ return {s: r.status, j: j}; }); })
      .then(function(x){
        btn.disabled = false;
        if (!x.j.ok) {
          if (x.j.locked) { cfg.unlocked = false; delPaint(); return; }
          err.textContent = x.j.error || ('Erreur ' + x.s);
          return;
        }
        location.reload();
      })
      .catch(function(){ btn.disabled = false; err.textContent = 'Échec réseau, rien n’a été supprimé.'; });
  });

  // ----- renommage (déverrouillage requis ; aucun mot de passe n'est demandé ici)
  var renTarget = null;
  function renPaint(){
    var locked = !cfg.unlocked;
    document.getElementById('ren-locked').hidden = !locked;
    document.getElementById('rennew').hidden = locked;
    document.getElementById('renok').hidden = locked;
  }
  function askRename(a){
    renTarget = a;
    var inp = document.getElementById('rennew');
    document.getElementById('ren-name').textContent = a.dataset.title;
    document.getElementById('renerr').textContent = '';
    inp.value = a.dataset.title;
    renPaint();
    document.getElementById('sheet-main').hidden = true;
    document.getElementById('rendlg').hidden = false;
    if (cfg.unlocked) setTimeout(function(){
      inp.focus();
      var dot = inp.value.lastIndexOf('.');
      inp.setSelectionRange(0, dot > 0 ? dot : inp.value.length);
    }, 30);
  }
  document.getElementById('rencancel').addEventListener('click', closeSheet);
  document.getElementById('renform').addEventListener('submit', function(e){
    e.preventDefault();
    var err = document.getElementById('renerr'), btn = document.getElementById('renok');
    var name = document.getElementById('rennew').value.trim();
    if (!renTarget || !cfg.canDelete || !cfg.unlocked) return;
    if (!name) { err.textContent = 'Saisis un nom.'; return; }
    if (name === renTarget.dataset.title) { closeSheet(); return; }
    btn.disabled = true; err.textContent = '';
    fetch('/rename?f=' + renTarget.dataset.f + '&to=' + encodeURIComponent(name), {method: 'POST', headers: {'X-Requested-With': 'biblio'}})
      .then(function(r){ return r.json().then(function(j){ return {s: r.status, j: j}; }); })
      .then(function(x){
        btn.disabled = false;
        if (!x.j.ok) {
          if (x.j.locked) { cfg.unlocked = false; renPaint(); return; }
          err.textContent = x.j.error || ('Erreur ' + x.s);
          return;
        }
        location.reload();
      })
      .catch(function(){ btn.disabled = false; err.textContent = 'Échec réseau, le fichier n’a pas été renommé.'; });
  });

  // ----- édition (déverrouillage requis ; aucun mot de passe n'est demandé ici : on indique seulement que c'est verrouillé)
  function askEdit(a){
    document.getElementById('edt-name').textContent = a.dataset.title;
    document.getElementById('sheet-main').hidden = true;
    document.getElementById('edtdlg').hidden = false;
  }
  document.getElementById('edtcancel').addEventListener('click', closeSheet);

  document.querySelectorAll('.fcard').forEach(function(a){
    a.addEventListener('click', function(e){
      var more = e.target.closest('.more');
      if (!more) {
        if (e.ctrlKey || e.metaKey || e.shiftKey || e.button) return;
        if (a.dataset.direct === '1') return;
      }
      e.preventDefault();
      openMenu(a);
    });
  });

  wrap.querySelectorAll('[data-close]').forEach(function(el){ el.addEventListener('click', closeSheet); });
  document.addEventListener('keydown', function(e){ if (e.key === 'Escape' && !wrap.hidden) closeSheet(); });

  // ----- envoi de fichiers, vidéos et dossiers (déverrouillage requis)
  var upBtn = document.getElementById('uploadbtn');
  if (upBtn) {
    var upTicket = null, upExpire = 0, upTtl = 0, upCancel = false, upXhr = null;
    var upEl = function(id){ return document.getElementById(id); };
    var upWarn = function(e){ e.preventDefault(); e.returnValue = ''; };
    var fmtB = function(n){
      var u = ['o', 'Ko', 'Mo', 'Go', 'To'], i = 0;
      while (n >= 1024 && i < u.length - 1) { n /= 1024; i++; }
      return (i ? n.toFixed(n < 10 ? 1 : 0).replace('.', ',') : n) + ' ' + u[i];
    };
    var upShow = function(step){
      ['upform', 'uppick', 'uprun'].forEach(function(id){ upEl(id).hidden = (id !== step); });
    };

    var upMsg = function(text){ upEl('uperr').textContent = text; upShow('upform'); };
    var upLocked = function(){
      cfg.unlocked = false; upTicket = null;
      upMsg('Accès verrouillé : déverrouille l’accès (cadenas en haut de la page) pour envoyer des fichiers.');
    };
    var upGetTicket = function(){
      upEl('uperr').textContent = '';
      fetch('/upload-auth', {method: 'POST', headers: {'X-Requested-With': 'biblio'}})
        .then(function(r){ return r.json().then(function(j){ return {s: r.status, j: j}; }); })
        .then(function(x){
          if (!x.j.ok) { if (x.j.locked) upLocked(); else upMsg(x.j.error || ('Erreur ' + x.s)); return; }
          upTicket = x.j.ticket; upTtl = x.j.ttl * 1000; upExpire = Date.now() + upTtl - 30000;
          upShow('uppick');
        })
        .catch(function(){ upMsg('Échec réseau.'); });
    };

    upBtn.addEventListener('click', function(){
      upEl('sheet-main').hidden = true; upEl('newdlg').hidden = true; upEl('deldlg').hidden = true; upEl('rendlg').hidden = true; upEl('edtdlg').hidden = true;
      upEl('updlg').hidden = false; wrap.hidden = false;
      upEl('up-dest').textContent = '/' + (cfg.folder || '');
      if (!cfg.unlocked) { upLocked(); return; }
      if (upTicket && Date.now() < upExpire) upShow('uppick'); else upGetTicket();
    });

    upEl('upcancel').addEventListener('click', closeSheet);
    upEl('up-pick-files').addEventListener('click', function(e){ e.preventDefault(); upEl('up-in-files').click(); });
    upEl('up-pick-dir').addEventListener('click', function(e){ e.preventDefault(); upEl('up-in-dir').click(); });
    ['up-in-files', 'up-in-dir'].forEach(function(id){
      upEl(id).addEventListener('change', function(){
        var files = Array.prototype.slice.call(this.files);
        this.value = '';
        if (files.length) upStart(files);
      });
    });

    upEl('up-cancel').addEventListener('click', function(){ upCancel = true; if (upXhr) upXhr.abort(); });
    upEl('up-done').addEventListener('click', function(){ upRunning = false; closeSheet(); });

    var upStart = function(files){
      var over = upEl('upover').checked, max = cfg.maxUpload || 0;
      var items = files.map(function(f){ return {f: f, rel: f.webkitRelativePath || f.name}; });
      var total = 0;
      var list = upEl('up-list');
      list.innerHTML = '';
      items.forEach(function(it){
        total += it.f.size;
        var row = document.createElement('div'); row.className = 'uprow';
        var n = document.createElement('span'); n.className = 'n'; n.textContent = it.rel;
        var s = document.createElement('span'); s.className = 's'; s.textContent = fmtB(it.f.size);
        row.appendChild(n); row.appendChild(s); list.appendChild(row);
        it.row = row; it.s = s;
      });
      upShow('uprun');
      upEl('up-done').hidden = true; upEl('up-cancel').hidden = false;
      upEl('up-bar').style.width = '0%';
      upRunning = true; upCancel = false;
      window.addEventListener('beforeunload', upWarn);

      var i = 0, sent = 0, ok = 0, skipped = 0, failed = 0;
      var setBar = function(bytes){
        var p = total ? Math.min(100, bytes / total * 100) : 100;
        upEl('up-bar').style.width = p + '%';
        upEl('up-sum').textContent = (ok + skipped + failed) + ' / ' + items.length + ' · ' + fmtB(Math.min(bytes, total)) + ' sur ' + fmtB(total);
      };
      var mark = function(it, cls, txt, ico){
        it.row.className = 'uprow ' + cls;
        it.s.textContent = '';
        if (ico && ICO[ico]) { var w = document.createElement('span'); w.className = 'sico'; w.innerHTML = ICO[ico]; it.s.appendChild(w); }
        it.s.appendChild(document.createTextNode(txt));
      };
      var finish = function(msg){
        upRunning = false;
        window.removeEventListener('beforeunload', upWarn);
        upEl('up-cancel').hidden = true; upEl('up-done').hidden = false;
        upEl('up-bar').style.width = (msg ? upEl('up-bar').style.width : '100%');
        upEl('up-sum').textContent = ok + ' envoyé(s)' + (skipped ? ' · ' + skipped + ' déjà présent(s)' : '') +
          (failed ? ' · ' + failed + ' en échec' : '') + (msg ? ' · ' + msg : '');
        if (ok) upDirty = true;
      };
      var next = function(){
        if (upCancel) return finish('arrêté');
        if (i >= items.length) return finish('');
        var it = items[i++];
        if (max && it.f.size > max) {
          failed++; sent += it.f.size; mark(it, 'bad', 'trop volumineux (max ' + fmtB(max) + ')');
          setBar(sent); return next();
        }
        mark(it, 'run', '0 %');
        var x = new XMLHttpRequest();
        upXhr = x;
        x.open('POST', '/upload?d=' + encodeURIComponent(cfg.folder || '') + '&n=' + encodeURIComponent(it.rel) + (over ? '&o=1' : ''));
        x.setRequestHeader('X-Requested-With', 'biblio');
        x.setRequestHeader('X-Upload-Ticket', upTicket);
        x.setRequestHeader('Content-Type', 'application/octet-stream');
        x.upload.onprogress = function(e){
          if (!e.lengthComputable) return;
          mark(it, 'run', Math.round(e.loaded / e.total * 100) + ' %');
          setBar(sent + e.loaded);
        };
        x.onload = function(){
          var j = {};
          try { j = JSON.parse(x.responseText); } catch(err) {}
          sent += it.f.size;
          if (x.status === 200 && j.ok) { ok++; mark(it, 'ok', fmtB(it.f.size), 'check'); upExpire = Date.now() + upTtl - 30000; }
          else if (x.status === 409) { skipped++; mark(it, 'skip', j.error || 'déjà présent'); }
          else if (j.code === 'locked') {
            failed++; upTicket = null; cfg.unlocked = false; mark(it, 'bad', 'accès verrouillé');
            return finish('accès verrouillé : déverrouille puis rouvre « Envoyer »');
          }
          else if (j.code === 'ticket') {
            failed++; upTicket = null; mark(it, 'bad', 'session expirée');
            return finish('session d’envoi expirée (rouvre « Envoyer »)');
          }
          else { failed++; mark(it, 'bad', j.error || ('erreur ' + x.status)); }
          setBar(sent); next();
        };
        x.onabort = function(){ mark(it, 'bad', 'arrêté'); next(); };
        x.onerror = function(){ failed++; mark(it, 'bad', 'échec réseau'); finish('connexion perdue'); };
        x.send(it.f);
      };
      next();
    };
  }

  // ----- nouveau fichier
  var nb = document.getElementById('newfile');
  if (nb) {
    nb.addEventListener('click', function(){
      document.getElementById('sheet-main').hidden = true;
      document.getElementById('deldlg').hidden = true;
      document.getElementById('newdlg').hidden = false;
      wrap.hidden = false;
      var inp = document.getElementById('newname'), nlock = !!cfg.protect && !cfg.unlocked;
      document.getElementById('rendlg').hidden = true; document.getElementById('edtdlg').hidden = true;
      document.getElementById('new-locked').hidden = !nlock;
      inp.hidden = nlock; document.getElementById('newok').hidden = nlock;
      inp.value = ''; document.getElementById('newerr').textContent = '';
      if (!nlock) setTimeout(function(){ inp.focus(); }, 50);
    });
    document.getElementById('newcancel').addEventListener('click', closeSheet);
    document.getElementById('newform').addEventListener('submit', function(e){
      e.preventDefault();
      if (cfg.protect && !cfg.unlocked) return;
      var name = document.getElementById('newname').value.trim();
      var err = document.getElementById('newerr');
      if (!name || name.indexOf('/') >= 0 || name.indexOf(String.fromCharCode(92)) >= 0 || name === '.' || name === '..') {
        err.textContent = 'Nom invalide (sans « / »).'; return;
      }
      var rel = cfg.folder ? cfg.folder + '/' + name : name;
      location.href = '/edit?new=1&f=' + encodeURIComponent(rel);
    });
  }
})();
"""

WATCH_JS = """
(function(){
  var cfg = window.WCFG;
  var v = document.getElementById('player');
  var auto = document.getElementById('autonext');
  var posKey = 'vl:pos:' + cfg.key;

  try { auto.checked = localStorage.getItem('vl:autonext') !== '0'; } catch(e) {}
  auto.addEventListener('change', function(){
    try { localStorage.setItem('vl:autonext', auto.checked ? '1' : '0'); } catch(e) {}
  });

  var saved = null;
  try { saved = JSON.parse(localStorage.getItem(posKey)); } catch(e) {}
  v.addEventListener('loadedmetadata', function(){
    if (saved && saved.t > 3 && saved.t < v.duration - 8) v.currentTime = saved.t;
  });

  var last = 0;
  function save(){
    if (!v.duration || v.ended) return;
    try { localStorage.setItem(posKey, JSON.stringify({t: v.currentTime, d: v.duration})); }
    catch(e) {}
  }
  v.addEventListener('timeupdate', function(){
    var now = Date.now();
    if (now - last > 2500) { last = now; save(); }
  });
  v.addEventListener('pause', save);
  window.addEventListener('pagehide', save);

  v.addEventListener('ended', function(){
    try { localStorage.removeItem(posKey); } catch(e) {}
    if (auto.checked && cfg.next) location.href = cfg.next;
  });

  var cur = document.querySelector('.row.cur');
  if (cur && cur.scrollIntoView && innerWidth >= 1000) {
    cur.scrollIntoView({block: 'nearest'});
  }

  document.addEventListener('keydown', function(e){
    var tag = (e.target.tagName || '').toLowerCase();
    if (tag === 'input' || tag === 'textarea' || e.ctrlKey || e.metaKey || e.altKey) return;
    var onPlayer = e.target === v;
    var k = e.key.toLowerCase();
    var handled = true;
    if (k === 'k' || (k === ' ' && !onPlayer)) { v.paused ? v.play() : v.pause(); }
    else if (k === 'j') { v.currentTime = Math.max(0, v.currentTime - 10); }
    else if (k === 'l') { v.currentTime = Math.min(v.duration || 1e9, v.currentTime + 10); }
    else if (k === 'arrowleft' && !onPlayer) { v.currentTime = Math.max(0, v.currentTime - 5); }
    else if (k === 'arrowright' && !onPlayer) { v.currentTime = Math.min(v.duration || 1e9, v.currentTime + 5); }
    else if (k === 'm') { v.muted = !v.muted; }
    else if (k === 'f') {
      if (document.fullscreenElement) document.exitFullscreen();
      else if (v.requestFullscreen) v.requestFullscreen();
    }
    else { handled = false; }
    if (handled) e.preventDefault();
  });
})();
"""

VIEWER_JS = """
(function(){
  var C = window.FLCFG;
  function el(id){ return document.getElementById(id); }
  function ls(k, v){ try { if (v === undefined) return localStorage.getItem(k); localStorage.setItem(k, v); } catch(e) {} return null; }

  var fs = parseInt(ls('fl:fs'), 10) || 15;
  function applyFs(){ el('editor').style.setProperty('--fs', fs + 'px'); ls('fl:fs', String(fs)); }
  applyFs();
  el('fs-down').addEventListener('click', function(){ fs = Math.max(10, fs - 1); applyFs(); });
  el('fs-up').addEventListener('click', function(){ fs = Math.min(26, fs + 1); applyFs(); });

  var wrapOn = ls('fl:wrap') !== '0';
  var numOn = ls('fl:num') !== '0';
  var ctrl = FL.create({
    parent: el('editor'), name: C.name, doc: C.doc, readOnly: C.readonlyView,
    vim: C.vim !== false, wrap: wrapOn, numbers: numOn,
    onChange: function(i){ el('st-pos').textContent = i.line + ':' + i.col; el('st-lines').textContent = i.lines + ' lignes'; },
    onMode: function(m){ },
    onSave: function(cb){ save(cb); },
    onQuit: function(force){ quit(force); },
    onMessage: function(t){ flash(t); }
  });
  el('st-lang').textContent = ctrl.label;

  var msgTimer = null;
  function flash(t){
    var m = el('st-msg'); m.textContent = t;
    clearTimeout(msgTimer); msgTimer = setTimeout(function(){ m.textContent = ''; }, 3500);
  }

  if (C.mode === 'view') {
    el('wrap-btn').classList.toggle('on', wrapOn);
    el('wrap-btn').addEventListener('click', function(){
      wrapOn = !wrapOn; ctrl.setWrap(wrapOn); ls('fl:wrap', wrapOn ? '1' : '0');
      el('wrap-btn').classList.toggle('on', wrapOn);
    });
    el('find-btn').addEventListener('click', function(){ ctrl.search(); });
    return;
  }

  // ------------------------------------------------ mode édition
  var dirty = false, leaving = false;
  var vimOn = ls('fl:vim') !== '0';
  var keysOn = ls('fl:keys') === null ? matchMedia('(pointer:coarse)').matches : ls('fl:keys') === '1';
  var keys = el('keys');

  function setModeLabel(m, sub){
    var b = el('st-mode');
    var map = {normal:'NORMAL', insert:'INSERT', visual:'VISUAL', replace:'REMPLACER'};
    var txt = map[m] || m.toUpperCase();
    if (m === 'visual' && sub === 'linewise') txt = 'V-LIGNE';
    if (m === 'visual' && sub === 'blockwise') txt = 'V-BLOC';
    if (m === 'off') txt = 'TEXTE';
    b.textContent = txt; b.dataset.m = m;
  }
  function syncVimUi(){
    el('btn-vim').classList.toggle('on', vimOn);
    keys.classList.toggle('novim', !vimOn);
    if (!vimOn) setModeLabel('off');
  }

  ctrl.opts.onChange = function(i){
    dirty = i.dirty;
    el('dirty').hidden = !i.dirty;
    el('st-pos').textContent = i.line + ':' + i.col;
    el('st-lines').textContent = i.lines + ' lignes';
  };
  ctrl.opts.onMode = setModeLabel;
  if (!vimOn) ctrl.setVim(false);
  syncVimUi();
  keys.hidden = !keysOn; el('btn-keys').classList.toggle('on', keysOn);

  el('btn-vim').addEventListener('click', function(){
    vimOn = !vimOn; ls('fl:vim', vimOn ? '1' : '0'); ctrl.setVim(vimOn); syncVimUi(); ctrl.focus();
  });
  el('btn-keys').addEventListener('click', function(){
    keysOn = !keysOn; ls('fl:keys', keysOn ? '1' : '0'); keys.hidden = !keysOn;
    el('btn-keys').classList.toggle('on', keysOn);
  });
  el('wrap-btn').classList.toggle('on', wrapOn);
  el('wrap-btn').addEventListener('click', function(){
    wrapOn = !wrapOn; ctrl.setWrap(wrapOn); ls('fl:wrap', wrapOn ? '1' : '0');
    el('wrap-btn').classList.toggle('on', wrapOn);
  });
  el('num-btn').classList.toggle('on', numOn);
  el('num-btn').addEventListener('click', function(){
    numOn = !numOn; ctrl.setNumbers(numOn); ls('fl:num', numOn ? '1' : '0');
    el('num-btn').classList.toggle('on', numOn);
  });

  keys.addEventListener('pointerdown', function(e){ e.preventDefault(); });
  keys.addEventListener('click', function(e){
    var b = e.target.closest('[data-k]');
    if (b) ctrl.send(b.dataset.k);
  });

  function save(cb, force){
    if (C.readonly) { flash('Mode lecture seule'); return; }
    var url = '/save?f=' + C.q + '&mt=' + encodeURIComponent(C.mt) + '&enc=' + encodeURIComponent(C.enc) +
      '&crlf=' + (C.crlf ? 1 : 0) + (force ? '&force=1' : '');
    fetch(url, {
      method: 'POST',
      headers: {'X-Requested-With': 'biblio', 'Content-Type': 'text/plain; charset=utf-8'},
      body: ctrl.getText()
    }).then(function(r){ return r.json().then(function(j){ return {s: r.status, j: j}; }); })
      .then(function(x){
        if (x.s === 409 && !force) {
          if (confirm('Le fichier a changé sur le disque depuis son ouverture. Écraser quand même ?')) save(cb, true);
          else flash('Enregistrement annulé');
          return;
        }
        if (!x.j.ok) { flash('Erreur : ' + (x.j.error || x.s)); return; }
        C.mt = x.j.mtime; if (x.j.enc) C.enc = x.j.enc;
        ctrl.markSaved(); flash('Enregistré · ' + x.j.lines + ' lignes');
        if (cb) cb();
      }).catch(function(){ flash('Échec réseau, rien n\\u2019a été enregistré'); });
  }
  function quit(force){
    if (!force && ctrl.isDirty()) { flash('Modifications non enregistrées (:q! pour quitter quand même)'); return; }
    leaving = true; location.href = C.back;
  }
  window.addEventListener('beforeunload', function(e){
    if (!leaving && ctrl.isDirty()) { e.preventDefault(); e.returnValue = ''; }
  });
  el('btn-save').addEventListener('click', function(){ save(); });
  document.addEventListener('keydown', function(e){
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 's') { e.preventDefault(); save(); }
  });
  ctrl.focus();
})();
"""

CSS = """
:root{
  --bg:#f5f6fa; --bg-2:#e6e9f3;
  --surface:#ffffff; --text:#161b2e; --muted:#6b7490; --border:#e3e6f0;
  --accent:#4f5bd5; --accent-soft:#eceeff; --on-accent:#ffffff;
  --folder:#e0961a; --folder-soft:#fff3dc;
  --teal:#0f9d9a; --teal-soft:#dcf5f4;
  --pink:#d6409f; --pink-soft:#fde4f3;
  --gray-soft:#eceef4; --green:#2e9d5b; --orange:#d9822b;
  --red:#e5484d; --red-soft:#ffe9ea;
  --shadow:0 1px 2px rgba(22,27,46,.05),0 4px 14px rgba(22,27,46,.05);
  --shadow-hover:0 2px 4px rgba(22,27,46,.06),0 12px 28px rgba(79,91,213,.18);
  --topbar:rgba(255,255,255,.9); --tb:64px;
  --sel:rgba(79,91,213,.22);
  --syn-keyword:#a626a4; --syn-string:#3f8f3a; --syn-number:#b35c00; --syn-comment:#8a93a6;
  --syn-function:#3857d6; --syn-type:#b07d00; --syn-prop:#0b7285; --syn-var:#c0392b; --syn-op:#0184bc;
  color-scheme:light;
}
:root[data-theme='dark']{
  --bg:#0e1118; --bg-2:#1b2132;
  --surface:#181d2b; --text:#e8ebf5; --muted:#8a93ad; --border:#262d41;
  --accent:#8b95ff; --accent-soft:#22274a; --on-accent:#0e1118;
  --folder:#f2b24a; --folder-soft:#34291a;
  --teal:#4fd1c5; --teal-soft:#16302f;
  --pink:#f472b6; --pink-soft:#3a1c2e;
  --gray-soft:#232a3c; --green:#5fd08d; --orange:#f0a050;
  --red:#ff6b70; --red-soft:#3a1f24;
  --shadow:0 1px 2px rgba(0,0,0,.35),0 4px 14px rgba(0,0,0,.25);
  --shadow-hover:0 2px 4px rgba(0,0,0,.4),0 12px 28px rgba(0,0,0,.5);
  --topbar:rgba(14,17,24,.9); --sel:rgba(139,149,255,.3);
  --syn-keyword:#c678dd; --syn-string:#98c379; --syn-number:#d19a66; --syn-comment:#6b7490;
  --syn-function:#61afef; --syn-type:#e5c07b; --syn-prop:#56b6c2; --syn-var:#e06c75; --syn-op:#56b6c2;
  color-scheme:dark;
}
*{box-sizing:border-box}
[hidden]{display:none!important}
body{
  margin:0; min-height:100vh; background:var(--bg); color:var(--text);
  font:16px/1.5 Inter,system-ui,-apple-system,'Segoe UI',Roboto,sans-serif;
  -webkit-font-smoothing:antialiased; transition:background .25s,color .25s;
}
a{color:inherit;text-decoration:none}
button{font:inherit}
.i{flex-shrink:0;display:block}

/* ---------- Barre du haut ---------- */
.topbar{
  position:sticky; top:0; z-index:20; min-height:var(--tb);
  display:flex; align-items:center; flex-wrap:wrap; gap:10px 14px; padding:10px 16px;
  background:var(--topbar); border-bottom:1px solid var(--border);
  backdrop-filter:blur(12px); -webkit-backdrop-filter:blur(12px);
}
.brand{display:flex; align-items:center; gap:10px; font-weight:700; font-size:18px; letter-spacing:-.01em}
.brand .logo{
  width:38px; height:38px; border-radius:11px; flex-shrink:0; display:grid; place-items:center;
  color:#fff; background:linear-gradient(135deg,#4f5bd5,#7a4fd5);
}
.search{position:relative; display:flex; align-items:center; flex:1 1 320px; max-width:560px; margin:0 auto}
.search .i{position:absolute; left:14px; color:var(--muted); pointer-events:none}
.search input{
  width:100%; padding:10px 16px 10px 42px; font:inherit; font-size:15px; color:var(--text);
  background:var(--bg); border:1px solid var(--border); border-radius:99px; outline:none;
}
.search input::placeholder{color:var(--muted)}
.search input:focus{border-color:var(--accent); box-shadow:0 0 0 3px var(--accent-soft)}
.ibtn{
  width:40px; height:40px; border-radius:12px; flex-shrink:0; display:grid; place-items:center; cursor:pointer;
  color:var(--text); background:var(--bg-2); border:1px solid var(--border);
  transition:background .2s,color .2s,transform .2s;
}
.ibtn:hover{background:var(--accent-soft); color:var(--accent)}
.ibtn:active{transform:scale(.93)}
.ibtn:focus-visible,.pill:focus-visible,.key:focus-visible{outline:2px solid var(--accent); outline-offset:2px}
.theme-btn{margin-left:auto; border-radius:50%; width:42px; height:42px}
.theme-btn .moon{display:none}
:root[data-theme='dark'] .theme-btn .sun{display:none}
:root[data-theme='dark'] .theme-btn .moon{display:block}

/* ---------- Navigation ---------- */
main{max-width:1180px; margin:0 auto; padding:20px 16px 56px}
.crumb{display:flex; flex-wrap:wrap; align-items:center; gap:4px; font-size:14px; color:var(--muted)}
.crumb a{display:inline-flex; align-items:center; gap:6px; padding:6px 12px; border-radius:99px; color:var(--muted); transition:background .15s,color .15s}
.crumb a:hover{background:var(--accent-soft); color:var(--accent)}
.crumb a.current{color:var(--text); font-weight:600; background:var(--bg-2)}
.crumb .sep{opacity:.5; display:inline-flex}
.toolrow{display:flex; flex-wrap:wrap; align-items:center; gap:12px; margin-top:14px}
.pill{
  display:inline-flex; align-items:center; gap:7px; padding:8px 14px; border-radius:99px; cursor:pointer;
  font-size:14px; font-weight:600; color:var(--text); background:var(--surface); border:1px solid var(--border);
  white-space:nowrap; flex-shrink:0; transition:background .15s,border-color .15s,color .15s;
}
.pill:hover{border-color:var(--accent); color:var(--accent)}
.pill.on{background:var(--accent-soft); border-color:var(--accent); color:var(--accent)}
.pill.primary{background:var(--accent); border-color:var(--accent); color:var(--on-accent)}
.pill.primary:hover{filter:brightness(1.08); color:var(--on-accent)}
.switch{display:inline-flex; align-items:center; gap:10px; cursor:pointer; font-size:14px; user-select:none; color:var(--muted)}
.switch input{position:absolute; opacity:0; pointer-events:none}
.switch .track{width:38px; height:22px; border-radius:99px; background:var(--bg-2); border:1px solid var(--border); position:relative; transition:background .2s,border-color .2s}
.switch .track::after{content:''; position:absolute; left:2px; top:2px; width:16px; height:16px; border-radius:50%; background:var(--muted); transition:transform .2s,background .2s}
.switch input:checked + .track{background:var(--accent-soft); border-color:var(--accent)}
.switch input:checked + .track::after{transform:translateX(16px); background:var(--accent)}
.switch input:focus-visible + .track{outline:2px solid var(--accent); outline-offset:2px}

.section{margin-top:26px}
.section h2{display:flex; align-items:center; gap:10px; margin:0 0 14px; font-size:13px; font-weight:700; text-transform:uppercase; letter-spacing:.08em; color:var(--muted)}
.count{font-size:12px; letter-spacing:0; text-transform:none; padding:1px 9px; border-radius:99px; background:var(--accent-soft); color:var(--accent)}
.grid{display:grid; gap:12px; grid-template-columns:repeat(auto-fill,minmax(270px,1fr))}
.item,.opt{
  display:flex; align-items:center; gap:14px; padding:12px 14px; border-radius:14px;
  background:var(--surface); border:1px solid var(--border); box-shadow:var(--shadow); overflow-wrap:anywhere;
  transition:transform .18s,box-shadow .18s,border-color .18s;
}
.item:hover,.opt:hover{transform:translateY(-2px); box-shadow:var(--shadow-hover); border-color:var(--accent)}
.item:focus-visible,.opt:focus-visible{outline:2px solid var(--accent); outline-offset:2px}
body:not(.show-hidden) .dot{display:none}
.ico{width:44px; height:44px; border-radius:12px; flex-shrink:0; display:grid; place-items:center}
.ico.folder{background:var(--folder-soft); color:var(--folder)}
.ico.code,.ico.back{background:var(--accent-soft); color:var(--accent)}
.ico.web{background:var(--teal-soft); color:var(--teal)}
.ico.media{background:var(--pink-soft); color:var(--pink)}
.ico.text,.ico.binary{background:var(--gray-soft); color:var(--muted)}
.text{flex:1; min-width:0}
.name{font-weight:600; font-size:15px; line-height:1.35; display:-webkit-box; -webkit-line-clamp:2; -webkit-box-orient:vertical; overflow:hidden}
.sub{font-size:12.5px; color:var(--muted); margin-top:2px}
.go{color:var(--muted); opacity:.6; transition:transform .18s,opacity .18s,color .18s}
.item:hover .go,.opt:hover .go{transform:translateX(3px); opacity:1; color:var(--accent)}
.back-link{margin-top:16px; display:flex}
@media(min-width:600px){.back-link .item{min-width:270px}}
.empty,.msgcard{
  margin:28px auto 0; padding:36px 20px; text-align:center; color:var(--muted);
  background:var(--surface); border:1px dashed var(--border); border-radius:16px; max-width:640px;
}
.msgcard{border-style:solid}
.msgcard h1{margin:0 0 8px; font-size:20px; color:var(--text)}
.msgcard .pill{margin:14px 6px 0}
.empty .ico{margin:0 auto 12px; width:56px; height:56px; border-radius:16px}

/* ---------- Menu (feuille) ---------- */
.backdrop{position:fixed; inset:0; z-index:50; background:rgba(8,10,18,.55); animation:fade .15s}
.sheet{
  position:fixed; z-index:51; left:0; right:0; bottom:0; max-width:520px; margin:0 auto;
  background:var(--bg); border:1px solid var(--border); border-radius:22px 22px 0 0;
  padding:16px 14px calc(18px + env(safe-area-inset-bottom,0px)); box-shadow:0 -10px 40px rgba(0,0,0,.35);
  animation:up .2s ease-out;
}
.sheet-head{display:flex; align-items:center; gap:14px; padding:2px 4px 14px}
.sheet-head .name{font-size:16px}
#sh-body,.sheet form{display:flex; flex-direction:column; gap:10px}
.opt .ico{width:40px; height:40px}
.sheet input[type=text],.sheet input[type=password]{
  width:100%; padding:12px 14px; font:inherit; color:var(--text); background:var(--surface);
  border:1px solid var(--border); border-radius:12px; outline:none;
}
.sheet input[type=text]:focus,.sheet input[type=password]:focus{border-color:var(--accent); box-shadow:0 0 0 3px var(--accent-soft)}
.err{color:var(--syn-var); font-size:13px; min-height:1.2em}
.err:empty{display:none}
.sheet .ico.danger,.sheet .opt.danger .ico{background:var(--red-soft); color:var(--red)}
.opt.danger:hover{border-color:var(--red)}
.opt.danger:hover .go{color:var(--red)}
.pill.danger{background:var(--red); border-color:var(--red); color:#fff}
.pill.danger:hover{filter:brightness(1.08); color:#fff}
.pill:disabled{opacity:.6; pointer-events:none}
#uppick,#uprun{display:flex; flex-direction:column; gap:10px}
.upbar{height:8px; border-radius:99px; background:var(--surface); border:1px solid var(--border); overflow:hidden}
.upbar i{display:block; height:100%; width:0; background:var(--accent); transition:width .15s}
.uplist{max-height:34vh; overflow:auto; display:flex; flex-direction:column; gap:4px; font-size:13px}
.uprow{display:flex; justify-content:space-between; gap:12px; padding:2px 4px}
.uprow .n{overflow:hidden; text-overflow:ellipsis; white-space:nowrap; min-width:0}
.uprow .s{flex:none; color:var(--muted); display:inline-flex; align-items:center; gap:4px}
.uprow .sico{display:inline-grid} .uprow .sico svg{width:14px; height:14px}
.uprow.run .s{color:var(--accent)}
.uprow.ok .s{color:var(--green)}
.uprow.skip .s{color:var(--orange)}
.uprow.bad .s{color:var(--red)}
@media(min-width:700px){
  .sheet{bottom:auto; top:50%; transform:translateY(-50%); border-radius:22px; animation:fade .15s}
}
@keyframes up{from{transform:translateY(30px); opacity:0}to{transform:none; opacity:1}}
@keyframes fade{from{opacity:0}to{opacity:1}}

/* ---------- Pages lecture / édition / aperçu ---------- */
body.ed-page{height:100vh; height:100dvh; display:flex; flex-direction:column; overflow:hidden}
.edbar{
  display:flex; align-items:center; gap:10px; padding:8px 10px;
  background:var(--topbar); border-bottom:1px solid var(--border);
}
.edtitle{flex:1; min-width:0}
.edtitle b{display:block; font-size:15px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis}
.edtitle small{display:block; color:var(--muted); font-size:12px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis}
.dirty{display:inline-block; width:9px; height:9px; margin-left:8px; border-radius:50%; background:var(--orange)}
.edbar .theme-btn{margin-left:0; width:40px; height:40px}
.edtools{display:flex; gap:8px; padding:8px 10px; overflow-x:auto; background:var(--bg); border-bottom:1px solid var(--border); scrollbar-width:none}
.edtools::-webkit-scrollbar{display:none}
.ed{flex:1; min-height:0; position:relative; background:var(--surface)}
.ed .cm-editor{height:100%}
.pv{flex:1; width:100%; border:0; background:#fff}
.statusline{
  display:flex; align-items:center; gap:12px; padding:4px 10px; flex-shrink:0;
  font:12px ui-monospace,SFMono-Regular,Menlo,Consolas,monospace; color:var(--muted);
  background:var(--bg-2); border-top:1px solid var(--border);
}
.statusline .sp{flex:1; min-width:0; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; color:var(--text)}
.mode{font-weight:700; padding:1px 8px; border-radius:6px; color:var(--on-accent); background:var(--accent)}
.mode[data-m=insert]{background:var(--green)}
.mode[data-m=visual]{background:var(--orange)}
.mode[data-m=replace]{background:var(--syn-var)}
.mode[data-m=off]{background:var(--muted)}
.keys{display:flex; gap:6px; padding:6px 8px calc(6px + env(safe-area-inset-bottom,0px)); overflow-x:auto; flex-shrink:0; background:var(--bg-2); border-top:1px solid var(--border); scrollbar-width:none}
.keys::-webkit-scrollbar{display:none}
.key{
  flex:0 0 auto; min-width:42px; height:40px; padding:0 10px; border-radius:10px; cursor:pointer;
  color:var(--text); background:var(--surface); border:1px solid var(--border);
  font:600 14px ui-monospace,SFMono-Regular,Menlo,Consolas,monospace; display:grid; place-items:center;
}
.key:active{background:var(--accent-soft); border-color:var(--accent)}
.key.sepk{min-width:6px; width:6px; padding:0; border:none; background:none; pointer-events:none}
.keys.novim .vimonly{display:none}
@media(prefers-reduced-motion:reduce){*{transition:none!important; animation:none!important}}
@media(max-width:640px){.search{order:4; flex-basis:100%; max-width:none}.grid{grid-template-columns:1fr}}

.ico.pdf{background:var(--red-soft); color:var(--red)}

/* ---------- Filtres et actions ---------- */
.filters{display:flex; gap:8px; overflow-x:auto; padding:2px 0; margin-top:14px; scrollbar-width:none}
.filters::-webkit-scrollbar{display:none}
.fchip{
  display:inline-flex; align-items:center; gap:8px; padding:7px 14px; border-radius:99px; cursor:pointer; flex-shrink:0;
  font-size:14px; font-weight:600; color:var(--muted); background:var(--surface); border:1px solid var(--border);
  transition:background .15s,border-color .15s,color .15s;
}
.fchip b{font-size:12px; font-weight:600; padding:0 7px; border-radius:99px; background:var(--bg-2)}
.fchip:hover{color:var(--accent); border-color:var(--accent)}
.fchip.on{color:var(--on-accent); background:var(--accent); border-color:var(--accent)}
.fchip.on b{background:rgba(255,255,255,.25); color:inherit}
.off{display:none!important}
.more{
  width:36px; height:36px; border-radius:10px; flex-shrink:0; display:grid; place-items:center; cursor:pointer;
  color:var(--muted); background:transparent; border:0;
}
.more:hover{background:var(--accent-soft); color:var(--accent)}
.vcard .more{position:absolute; top:8px; right:8px; z-index:2; color:#fff; background:rgba(0,0,0,.55); backdrop-filter:blur(4px)}
.vcard .more:hover{background:rgba(0,0,0,.78); color:#fff}

/* ---------- Vidéos : cartes avec miniature ---------- */
.videos{display:grid; gap:18px; grid-template-columns:repeat(auto-fill,minmax(290px,1fr))}
.vcard{
  display:block; border-radius:14px; overflow:hidden; background:var(--surface);
  border:1px solid var(--border); box-shadow:var(--shadow);
  transition:transform .18s,box-shadow .18s,border-color .18s;
}
.vcard:hover{transform:translateY(-3px); box-shadow:var(--shadow-hover); border-color:var(--accent)}
.vcard:focus-visible,.row:focus-visible{outline:2px solid var(--accent); outline-offset:2px}
.thumb,.rthumb{position:relative; aspect-ratio:16/9; background:var(--bg-2); overflow:hidden}
.thumb img,.rthumb img{position:absolute; inset:0; width:100%; height:100%; object-fit:cover; transition:transform .35s}
.vcard:hover .thumb img{transform:scale(1.05)}
.ph{position:absolute; inset:0; display:grid; place-items:center; color:var(--muted); opacity:.6}
.play{
  position:absolute; left:50%; top:50%; width:54px; height:54px; margin:-27px 0 0 -27px;
  border-radius:50%; display:grid; place-items:center; color:#fff;
  background:rgba(0,0,0,.55); backdrop-filter:blur(4px);
  opacity:0; transform:scale(.85); transition:opacity .18s,transform .18s; pointer-events:none;
}
.play .i{margin-left:3px}
.vcard:hover .play{opacity:1; transform:scale(1)}
.dur{
  position:absolute; right:8px; bottom:10px; padding:1px 7px; border-radius:6px;
  font-size:12px; font-weight:600; color:#fff; background:rgba(0,0,0,.78); font-variant-numeric:tabular-nums;
}
.bar{position:absolute; left:0; right:0; bottom:0; height:4px; background:rgba(255,255,255,.35)}
.bar i{display:block; height:100%; width:0; background:var(--red)}
.vinfo{padding:12px 14px 14px}
.vname{font-weight:600; font-size:15px; line-height:1.35; display:-webkit-box; -webkit-line-clamp:2; -webkit-box-orient:vertical; overflow:hidden; overflow-wrap:anywhere}
.vsub{font-size:12.5px; color:var(--muted); margin-top:4px}

/* ---------- Page de lecture vidéo ---------- */
.watch{
  max-width:1560px; margin:0 auto; padding:16px 16px 56px;
  display:grid; gap:16px 24px; grid-template-columns:minmax(0,1fr);
  grid-template-areas:"player" "info" "next";
}
.player{
  grid-area:player; aspect-ratio:16/9; background:#000; border-radius:16px; overflow:hidden;
  box-shadow:var(--shadow-hover); max-height:calc(100vh - 110px); width:100%;
}
.player video{width:100%; height:100%; display:block; background:#000; object-fit:contain}
.info{grid-area:info; min-width:0}
.vtitle{margin:0; font-size:21px; line-height:1.3; font-weight:700; letter-spacing:-.01em; overflow-wrap:anywhere}
.chips{display:flex; flex-wrap:wrap; align-items:center; gap:10px; margin-top:14px}
.chip,.btn{
  display:inline-flex; align-items:center; gap:8px; padding:8px 14px; border-radius:99px; font-size:14px; font-weight:500;
  background:var(--surface); border:1px solid var(--border); color:var(--text);
  transition:background .15s,border-color .15s,color .15s;
}
a.chip:hover,a.btn:hover{background:var(--accent-soft); border-color:var(--accent); color:var(--accent)}
.chip.muted{color:var(--muted)}
.btn.disabled{opacity:.4; pointer-events:none}
.hint{margin-top:14px; font-size:13px; color:var(--muted)}
.hint kbd{font:inherit; font-size:12px; padding:1px 6px; border-radius:6px; background:var(--bg-2); border:1px solid var(--border)}
.next{grid-area:next; min-width:0}
.next h2{margin:0 0 12px; font-size:13px; font-weight:700; text-transform:uppercase; letter-spacing:.08em; color:var(--muted)}
.list{display:flex; flex-direction:column; gap:8px}
.row{display:flex; gap:12px; padding:6px; border-radius:12px; border:1px solid transparent; transition:background .15s,border-color .15s}
.row:hover{background:var(--surface); border-color:var(--border)}
.row.cur{background:var(--accent-soft); border-color:var(--accent)}
.rthumb{width:150px; flex-shrink:0; border-radius:9px}
.rthumb .dur{right:5px; bottom:8px; font-size:11px; padding:0 5px}
.rinfo{min-width:0; flex:1; padding:2px 0}
.rname{font-weight:600; font-size:14px; line-height:1.35; display:-webkit-box; -webkit-line-clamp:2; -webkit-box-orient:vertical; overflow:hidden; overflow-wrap:anywhere}
.rsub{font-size:12.5px; color:var(--muted); margin-top:3px}
.row.cur .rsub{color:var(--accent); font-weight:600}
@media(min-width:1000px){
  .watch{grid-template-columns:minmax(0,1fr) 390px; grid-template-areas:"player next" "info next"; grid-template-rows:auto 1fr}
  .next{align-self:start; position:sticky; top:calc(var(--tb) + 16px); max-height:calc(100vh - var(--tb) - 32px); overflow-y:auto; padding-right:4px}
}
@media(max-width:999px){
  .watch{padding-top:0}
  .player{margin:0 -16px; width:calc(100% + 32px); border-radius:0; position:sticky; top:var(--tb); z-index:10; max-height:none; box-shadow:none}
  .hint{display:none}
}
@media(max-width:640px){.videos{grid-template-columns:1fr}.rthumb{width:132px}}
"""


# --------------------------------------------------------------------------
# Utilitaires
# --------------------------------------------------------------------------
CSS += """

/* ---------- Verrouillage de l'accès ---------- */
.ibtn.unlocked{color:var(--green); border-color:var(--green)}
.pill.locked,.chip.locked{opacity:.6; cursor:not-allowed}
.pill.locked:hover{border-color:var(--border); color:var(--text)}
.lkveil{position:fixed; inset:0; z-index:90; display:grid; place-items:center; padding:16px; background:rgba(8,10,16,.55)}
.lkbox{width:min(100%,380px); display:flex; flex-direction:column; gap:12px; padding:22px; border-radius:20px; background:var(--surface); border:1px solid var(--border); box-shadow:var(--shadow-hover)}
.lkbox h2{margin:0; font-size:18px}
.lkbox p{margin:0; color:var(--muted); font-size:14px}
.lkbox input{padding:12px 14px; font:inherit; color:var(--text); background:var(--bg); border:1px solid var(--border); border-radius:12px; outline:none}
.lkbox input:focus{border-color:var(--accent); box-shadow:0 0 0 3px var(--accent-soft)}
.lkbox .lkerr{color:var(--red); min-height:1.3em}
.lkbox .row{display:flex; gap:8px; justify-content:flex-end}
"""

LOCK_JS = r"""
(function(){
  var ICO = window.LKICO || {}, H = {'X-Requested-With': 'biblio'};
  var btn = document.getElementById('lock-toggle');
  var st = {enabled: false, unlocked: false};
  function paint(){
    if (!btn) return;
    btn.hidden = !st.enabled;
    btn.innerHTML = st.unlocked ? ICO.unlock : ICO.lock;
    btn.classList.toggle('unlocked', st.unlocked);
    var t = st.unlocked ? 'Accès déverrouillé : cliquer pour verrouiller' : 'Accès verrouillé : cliquer pour déverrouiller';
    btn.title = t; btn.setAttribute('aria-label', t);
  }
  function post(url, body){
    return fetch(url, {method: 'POST', credentials: 'same-origin', headers: H, body: body}).then(function(r){ return r.json(); });
  }
  function dialog(){
    if (document.querySelector('.lkveil')) return;
    var veil = document.createElement('div');
    veil.className = 'lkveil';
    veil.innerHTML = '<form class="lkbox" autocomplete="off"><h2>Déverrouiller l’accès</h2>' +
      '<p>Le mot de passe n’est demandé qu’ici. Ensuite, la modification, le renommage, la suppression, l’envoi de fichiers et le tableau de bord ne le redemandent plus, jusqu’au prochain verrouillage.</p>' +
      '<input type="password" placeholder="Mot de passe" autocomplete="current-password" required>' +
      '<p class="lkerr" role="alert"></p><div class="row"><button type="button" class="pill" data-x>Annuler</button>' +
      '<button type="submit" class="pill primary">Déverrouiller</button></div></form>';
    document.body.appendChild(veil);
    var f = veil.firstChild, pw = f.querySelector('input'), err = f.querySelector('.lkerr'), go = f.querySelector('[type=submit]');
    function close(){ veil.remove(); document.removeEventListener('keydown', onKey); }
    function onKey(e){ if (e.key === 'Escape') close(); }
    document.addEventListener('keydown', onKey);
    veil.addEventListener('click', function(e){ if (e.target === veil) close(); });
    f.querySelector('[data-x]').addEventListener('click', close);
    f.addEventListener('submit', function(e){
      e.preventDefault(); go.disabled = true; err.textContent = '';
      post('/unlock', pw.value).then(function(j){
        if (j.ok) { location.reload(); return; }
        go.disabled = false; err.textContent = j.error || 'Erreur'; pw.value = ''; pw.focus();
      }).catch(function(){ go.disabled = false; err.textContent = 'Connexion impossible.'; });
    });
    setTimeout(function(){ pw.focus(); }, 30);
  }
  if (btn) btn.addEventListener('click', function(){
    if (!st.unlocked) { dialog(); return; }
    post('/lock').then(function(){ location.reload(); });
  });
  document.addEventListener('click', function(e){
    var t = e.target.closest ? e.target.closest('[data-unlock]') : null;
    if (t) { e.preventDefault(); dialog(); }
  });
  var first = null;
  function refresh(){
    fetch('/lock-state', {credentials: 'same-origin'}).then(function(r){ return r.json(); }).then(function(x){
      st = x; paint();
      if (window.FLCFG) window.FLCFG.unlocked = !!x.files;
      if (first === null) first = x;
      else if (window.LKRELOAD && !!x[window.LKRELOAD] !== !!first[window.LKRELOAD]) location.reload();
    }).catch(function(){});
  }
  refresh();
  document.addEventListener('visibilitychange', function(){ if (!document.hidden) refresh(); });
  window.addEventListener('focus', refresh);
})();
"""


def lock_script(reload=None):
    """Bouton cadenas + dialogue de déverrouillage ; `reload` : partie ("files"/"dash") dont le changement recharge la page."""
    ico = {n: icon(n, 20) for n in ("lock", "unlock")}
    return f"<script>window.LKICO = {js_json(ico)}; window.LKRELOAD = {js_json(reload)}; {LOCK_JS}</script>"


EDIT_LOCKED_HINT = "Accès verrouillé : déverrouille l'accès (cadenas de la liste des fichiers) pour modifier ce fichier."


def edit_pill(q, locked):
    """Bouton « Éditer » : lien normal, ou simple indication « verrouillé » (aucune invite de mot de passe)."""
    if locked:
        return (f"<span class='pill locked' role='button' aria-disabled='true' "
                f"title='{escape(EDIT_LOCKED_HINT, quote=True)}'>{icon('lock', 16)}Éditer · verrouillé</span>")
    return f"<a class='pill primary' href='/edit?f={q}'>{icon('edit', 16)}Éditer</a>"


def locked_page(what, scope, back=None, title="Accès verrouillé — Ma bibliothèque", css="", lock=False):
    """Page « accès verrouillé » commune : aucun champ de mot de passe, seulement un bouton pour déverrouiller."""
    actions = (f"<a class='pill' href='{back}'>{icon('back', 16)}Retour</a>" if back else "")
    actions += f"<button class='pill primary' type='button' data-unlock>{icon('unlock', 16)}Déverrouiller</button>"
    return (doc_open(title, "", css) + topbar(False, lock)
            + f"<main><div class='msgcard'><h1>Accès verrouillé</h1><p>{escape(what)} demande de déverrouiller l'accès.</p>{actions}</div></main>"
            + f"<script>{THEME_JS}</script>{lock_script(scope)}</body></html>")


def natural_key(p):
    return [int(t) if t.isdigit() else t.casefold() for t in re.split(r"(\d+)", p.name)]


def fmt_size(n):
    for unit, div in (("Go", 1024 ** 3), ("Mo", 1024 ** 2), ("Ko", 1024)):
        if n >= div:
            v = n / div
            return (f"{v:.1f}" if v < 10 else f"{v:.0f}").replace(".", ",") + " " + unit
    return f"{n} o"


def js_json(obj):
    return (json.dumps(obj).replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026"))


def resolve_inside(rel):
    """Chemin *logique* sous ROOT : les liens symboliques ne sont pas résolus, de sorte
    qu'un raccourci vers un dossier se comporte comme un vrai dossier (même hors de ROOT).
    Seuls les « .. » et les chemins absolus sont neutralisés, de façon purement lexicale."""
    if "\x00" in rel:
        return None
    p = Path(os.path.normpath(ROOT / rel))
    try:
        p.relative_to(ROOT)
    except ValueError:
        return None
    if is_env_file(p):
        return None
    return p


def is_env_file(p):
    """Vrai si p est le .env (ou un lien vers lui) : il contient le jeton et le mot de passe."""
    if ENV_PATH is None:
        return False
    try:
        return p.samefile(ENV_PATH)
    except OSError:
        return False


def rel_of(p):
    return p.relative_to(ROOT).as_posix()


def kind_of(p):
    ext = p.suffix.lower()
    if ext in WEB_EXT:
        return "web"
    if ext in IMAGE_EXT:
        return "image"
    if ext == ".pdf":
        return "pdf"
    if ext in VIDEO_EXT:
        return "video"
    if ext in AUDIO_EXT:
        return "audio"
    if ext in BINARY_EXT:
        return "binary"
    return "text"


def card_kind(p):
    """Type pour le menu : un fichier d'extension inconnue est testé (octets nuls)."""
    kind = kind_of(p)
    if kind == "text" and p.suffix.lower() not in CODE_EXT | TEXT_EXT and is_binary_file(p):
        return "binary"
    return kind


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


def list_dir(current):
    try:
        entries = sorted(current.iterdir(), key=natural_key)
    except (PermissionError, OSError):
        return None, None
    folders = [p for p in entries if p.is_dir()]  # is_dir() suit les liens symboliques
    files = [p for p in entries if p.is_file() and not is_env_file(p)]
    return folders, files


def load_text(p):
    """-> (texte, encodage, crlf, erreur) ; erreur : None | 'big' | 'binary'."""
    try:
        raw = p.read_bytes()
    except OSError:
        return None, "utf-8", False, "io"
    if len(raw) > MAX_TEXT:
        return None, "utf-8", False, "big"
    if b"\x00" in raw[:8192]:
        return None, "utf-8", False, "binary"
    try:
        text = raw.decode("utf-8-sig")
        enc = "utf-8-sig" if raw.startswith(b"\xef\xbb\xbf") else "utf-8"
    except UnicodeDecodeError:
        text, enc = raw.decode("latin-1"), "latin-1"
    crlf = "\r\n" in text
    if crlf:
        text = text.replace("\r\n", "\n")
    return text, enc, crlf, None


def is_binary_file(p):
    try:
        with open(p, "rb") as f:
            return b"\x00" in f.read(8192)
    except OSError:
        return True


def guess_mime(p):
    ext = p.suffix.lower()
    if ext in EXTRA_MIME:
        mime = EXTRA_MIME[ext]
    else:
        mime = mimetypes.guess_type(p.name)[0] or "application/octet-stream"
    if mime.startswith("text/") or mime in ("application/json", "application/javascript", "image/svg+xml"):
        if "charset" not in mime:
            mime += "; charset=utf-8" if mime.startswith("text/") or mime == "application/json" else ""
    return mime


def lan_ips():
    try:
        out = subprocess.run(["hostname", "-I"], capture_output=True, text=True, timeout=3).stdout.split()
        return [ip for ip in out if ":" not in ip]
    except (OSError, subprocess.SubprocessError):
        return []


def read_env(path):
    """Lit un fichier .env (CLE=valeur, # commentaires, guillemets facultatifs)."""
    values = {}
    try:
        text = path.read_text(encoding="utf-8-sig")
    except OSError:
        return values
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        if line.startswith("export "):
            line = line[7:].lstrip()
        key, _, val = line.partition("=")
        key, val = key.strip(), val.strip()
        if len(val) >= 2 and val[0] == val[-1] and val[0] in "\"'":
            val = val[1:-1]
        if key:
            values[key] = val
    return values


def write_env_value(path, key, value):
    """Ajoute ou remplace CLE=valeur dans le .env (écriture atomique, droits 0600)."""
    try:
        lines = path.read_text(encoding="utf-8-sig").splitlines()
    except OSError:
        lines = []
    new = f"{key}={value}"
    pattern = re.compile(rf"\s*(export\s+)?{re.escape(key)}\s*=")
    for i, line in enumerate(lines):
        if pattern.match(line):
            lines[i] = new
            break
    else:
        lines.append(new)
    tmp = path.with_name(path.name + ".tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    os.chmod(tmp, 0o600)
    os.replace(tmp, path)


def conf(key):
    """Variable d'environnement si définie, sinon valeur du .env."""
    return os.environ.get(key) or ENV.get(key) or ""


def load_token():
    """Jeton d'accès : BIBLIO_TOKEN (environnement ou .env). Absent, il est créé et écrit dans le .env."""
    value = conf("BIBLIO_TOKEN")
    if value:
        return value
    # Migration : ancien emplacement ~/.config/biblio/token
    try:
        legacy = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "biblio" / "token"
        value = legacy.read_text().strip()
    except (OSError, RuntimeError):
        value = ""
    value = value or secrets.token_urlsafe(12)
    try:
        write_env_value(ENV_PATH, "BIBLIO_TOKEN", value)
    except OSError as e:
        print(f"Attention : impossible d'écrire {ENV_PATH} ({e.strerror}) : le jeton ne sera pas conservé.")
    return value


MAX_FAILS = 5          # essais de mot de passe avant verrouillage
LOCK_SECONDS = 60
_auth_lock = threading.Lock()
_auth_fails = {}       # ip -> (essais, verrouillé jusqu'à)


def check_password(ip, given, expected=None):
    """Vérifie un mot de passe (par défaut celui de suppression), avec verrouillage par adresse IP.
    -> (ok, message)"""
    expected = PASSWORD if expected is None else expected
    candidates = [e for e in ([expected] if isinstance(expected, str) else expected) if e]
    now = time.monotonic()
    with _auth_lock:
        count, until = _auth_fails.get(ip, (0, 0.0))
        if until > now:
            return False, f"Trop d'essais, réessaie dans {int(until - now) + 1} s."
        if until:                       # verrou expiré : on repart de zéro
            count = 0
        count += 1                      # l'essai est compté avant la vérification (essais parallèles)
        _auth_fails[ip] = (count, now + LOCK_SECONDS if count >= MAX_FAILS else 0.0)
    ok = any([hmac.compare_digest(given.encode("utf-8", "replace"), e.encode("utf-8", "replace")) for e in candidates])
    if ok:
        with _auth_lock:
            _auth_fails.pop(ip, None)
        return True, ""
    time.sleep(0.5)                     # ralentit les essais successifs
    return False, "Mot de passe incorrect."


TICKET_TTL = 15 * 60       # durée de validité d'un jeton d'envoi (fenêtre glissante)
_tickets = {}              # jeton d'envoi -> expiration (monotonic)
_tickets_lock = threading.Lock()


def issue_ticket():
    """Jeton d'envoi à usage limité (obtenu avec le mot de passe, valable pour /upload uniquement)."""
    now = time.monotonic()
    with _tickets_lock:
        for t in [t for t, exp in _tickets.items() if exp < now]:
            del _tickets[t]
        while len(_tickets) >= 50:
            del _tickets[min(_tickets, key=_tickets.get)]
        ticket = secrets.token_urlsafe(24)
        _tickets[ticket] = now + TICKET_TTL
    return ticket


def use_ticket(ticket):
    """Vrai si le jeton est valide ; sa validité est alors prolongée."""
    now = time.monotonic()
    with _tickets_lock:
        exp = _tickets.get(ticket)
        if exp is None or exp < now:
            _tickets.pop(ticket, None)
            return False
        _tickets[ticket] = now + TICKET_TTL
    return True


def clean_upload_name(name):
    """Nom relatif envoyé par le navigateur (« dossier/sous/fichier.ext ») -> composants sûrs, ou None."""
    if not name or len(name) > 1024 or name.startswith("/"):
        return None
    parts = name.split("/")
    for c in parts:
        if c in ("", ".", "..") or "\\" in c or len(c.encode("utf-8", "replace")) > 200:
            return None
        if any(ord(ch) < 32 or ord(ch) == 127 for ch in c):
            return None
    return parts


# --------------------------------------------------------------------------
# Tableau de bord : mémoire, appareils connectés, blocage
# --------------------------------------------------------------------------
DEVICE_ACTIVE_SECONDS = 5 * 60     # un appareil est « connecté » s'il a fait une requête depuis moins de 5 min
MAX_DEVICES = 500                  # appareils gardés en mémoire (les plus anciens sont oubliés)
BLOCKLIST_PATH = (Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
                  / "biblio" / "blocked_devices.json")
LOCAL_IPS = {"127.0.0.1"}          # adresses de la machine qui héberge le serveur (remplie au démarrage)
_dev_lock = threading.Lock()
_devices = {}                      # ip -> {first, last, hits, ua, auth}
_blocked = {}                      # ip -> date du blocage (time.time())

_unlock_lock = threading.Lock()
_unlocked = {}                     # identifiant de session -> {"files", "dash"} ; en mémoire : tout est verrouillé au redémarrage


def unlock_scopes(sid):
    """Parties déverrouillées de cette session : "files" (suppression, envoi) et/ou "dash" (tableau de bord)."""
    if not sid:
        return set()
    with _unlock_lock:
        return set(_unlocked.get(sid, ()))


def grant_unlock(sid, scopes):
    with _unlock_lock:
        if sid not in _unlocked:
            while len(_unlocked) >= 50:
                del _unlocked[next(iter(_unlocked))]
            sid = secrets.token_urlsafe(24)
            _unlocked[sid] = set()
        _unlocked[sid] |= set(scopes)
    return sid


def use_dash_session(sid, touch=True):
    return "dash" in unlock_scopes(sid)


def drop_dash_session(sid):
    with _unlock_lock:
        _unlocked.pop(sid, None)


def short_ua(ua):
    """User-Agent -> libellé court (« Chrome · Android »)."""
    ua = ua or ""
    browser = next((name for key, name in (
        ("Edg/", "Edge"), ("OPR/", "Opera"), ("Firefox/", "Firefox"), ("FxiOS/", "Firefox"),
        ("SamsungBrowser/", "Samsung Internet"), ("CriOS/", "Chrome"), ("Chrome/", "Chrome"),
        ("Safari/", "Safari")) if key in ua), "")
    system = next((name for key, name in (
        ("Android", "Android"), ("iPhone", "iPhone"), ("iPad", "iPad"), ("Windows", "Windows"),
        ("Mac OS X", "macOS"), ("CrOS", "ChromeOS"), ("Linux", "Linux")) if key in ua), "")
    label = " · ".join(x for x in (browser, system) if x)
    return label or ua.split("/")[0][:30]


def track_device(ip, ua, authed, hit=True):
    """Enregistre le passage d'un appareil. authed : a présenté le jeton d'accès (cookie), mémorisé."""
    global _hist_dirty
    now = time.time()
    with _dev_lock:
        d = _devices.get(ip)
        if d is None:
            if len(_devices) >= MAX_DEVICES:
                del _devices[min(_devices, key=lambda k: _devices[k]["last"])]
            d = _devices[ip] = {"first": now, "hits": 0, "auth": False, "ua": ""}
        d["last"] = now
        d["ua"] = short_ua(ua) or d["ua"]
        d["auth"] = d["auth"] or bool(authed)
        if hit:
            d["hits"] += 1
            _hist_dirty = True


def is_blocked(ip):
    with _dev_lock:
        return ip in _blocked


def load_blocklist():
    try:
        data = json.loads(BLOCKLIST_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return
    if not isinstance(data, list):
        return
    with _dev_lock:
        for item in data:
            try:
                _blocked[str(ipaddress.ip_address(str(item["ip"])))] = float(item.get("since", 0))
            except (ValueError, KeyError, TypeError, AttributeError):
                continue


def save_blocklist():
    """Écrit la liste des appareils bloqués (atomique, droits 0600). À appeler avec _dev_lock tenu."""
    data = [{"ip": ip, "since": since} for ip, since in sorted(_blocked.items())]
    BLOCKLIST_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = BLOCKLIST_PATH.with_name(BLOCKLIST_PATH.name + ".tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(data, f)
    os.replace(tmp, BLOCKLIST_PATH)


def set_blocked(ip_text, block, requester):
    """Bloque ou débloque une adresse IP. -> (ok, erreur, avertissement)"""
    try:
        ip = str(ipaddress.ip_address(ip_text.strip()))
    except ValueError:
        return False, "Adresse IP invalide.", ""
    if block:
        if ip == requester:
            return False, "Tu ne peux pas bloquer l'appareil que tu utilises.", ""
        if ipaddress.ip_address(ip).is_loopback or ip in LOCAL_IPS or ip in lan_ips():
            return False, "Tu ne peux pas bloquer l'appareil qui héberge le serveur.", ""
    warning = ""
    with _dev_lock:
        if block:
            _blocked[ip] = time.time()
        else:
            _blocked.pop(ip, None)
        try:
            save_blocklist()
        except OSError as e:
            warning = (f"Appliqué, mais la liste n'a pas pu être enregistrée dans {BLOCKLIST_PATH} "
                       f"({e.strerror}) : elle sera perdue au redémarrage.")
    return True, "", warning


def arp_macs():
    """ip -> adresse MAC d'après la table ARP du système (Linux ; vide si illisible)."""
    macs = {}
    try:
        with open("/proc/net/arp", encoding="ascii", errors="replace") as f:
            next(f, None)
            for line in f:
                cols = line.split()
                if len(cols) >= 4 and cols[3] != "00:00:00:00:00:00":
                    macs[cols[0]] = cols[3]
    except OSError:
        pass
    return macs


def device_rows(me):
    """Appareils vus + appareils bloqués, prêts pour le JSON du tableau de bord."""
    now = time.time()
    macs = arp_macs()
    with _dev_lock:
        seen = {ip: dict(d) for ip, d in _devices.items()}
        blocked = set(_blocked)
    rows = []
    for ip in set(seen) | blocked:
        d = seen.get(ip)
        ago = max(0, int(now - d["last"])) if d else None
        try:
            loopback = ipaddress.ip_address(ip).is_loopback
        except ValueError:
            loopback = False
        rows.append({
            "ip": ip, "mac": macs.get(ip, ""), "ua": d["ua"] if d else "", "ago": ago,
            "hits": d["hits"] if d else 0, "auth": bool(d and d["auth"]),
            "active": ago is not None and ago <= DEVICE_ACTIVE_SECONDS and ip not in blocked,
            "blocked": ip in blocked, "me": ip == me, "local": loopback or ip in LOCAL_IPS,
        })
    rows.sort(key=lambda r: (r["blocked"], not r["active"], r["ago"] if r["ago"] is not None else 1 << 40, r["ip"]))
    return rows


def read_memory():
    """Mémoire de l'appareil (octets) ou None. « Libre » = mémoire disponible (MemAvailable : cache
    récupérable inclus), et non le seul MemFree, toujours très bas sous Linux."""
    total = avail = None
    try:
        info = {}
        with open("/proc/meminfo", encoding="ascii", errors="replace") as f:
            for line in f:
                key, _, rest = line.partition(":")
                parts = rest.split()
                if parts and parts[0].isdigit():
                    info[key] = int(parts[0]) * 1024      # valeurs en Kio
        total = info.get("MemTotal")
        avail = info.get("MemAvailable")
        if avail is None and total:                       # très vieux noyaux
            avail = info.get("MemFree", 0) + info.get("Buffers", 0) + info.get("Cached", 0)
    except OSError:
        pass
    if not total:
        try:
            page = os.sysconf("SC_PAGE_SIZE")
            total = page * os.sysconf("SC_PHYS_PAGES")
            avail = page * os.sysconf("SC_AVPHYS_PAGES")
        except (ValueError, OSError, AttributeError):
            return None
    if not total or avail is None:
        return None
    avail = max(0, min(avail, total))
    used = total - avail
    return {"total": total, "used": used, "free": avail, "percent": round(used * 100 / total, 1),
            "total_h": fmt_size(total), "used_h": fmt_size(used), "free_h": fmt_size(avail)}


# --- stockage ---------------------------------------------------------------------
DISKS = [("/mnt/ext0", "Disque externe"), ("/sdcard", "Stockage interne")]   # BIBLIO_DISKS=chemin=Nom;chemin=Nom


def parse_disks(text):
    disks = []
    for item in text.split(";"):
        path, _, label = item.partition("=")
        path = path.strip()
        if path:
            disks.append((path, label.strip() or path))
    return disks


def read_disks():
    """Capacité de chaque volume configuré (octets), ou un message d'erreur s'il est illisible."""
    out = []
    for path, label in DISKS:
        row = {"path": path, "label": label}
        try:
            u = shutil.disk_usage(path)
        except FileNotFoundError:
            row["error"] = "Introuvable (non monté ?)"
        except PermissionError:
            row["error"] = "Accès refusé"
        except OSError as e:
            row["error"] = e.strerror or "Illisible"
        else:
            row.update(total=u.total, used=u.used, free=u.free,
                       percent=round(u.used * 100 / u.total, 1) if u.total else 0.0,
                       total_h=fmt_size(u.total), used_h=fmt_size(u.used), free_h=fmt_size(u.free))
            try:   # même volume que « / » : le disque n'est probablement pas monté
                row["system"] = os.stat(path).st_dev == os.stat("/").st_dev and os.path.realpath(path) != "/"
            except OSError:
                row["system"] = False
        out.append(row)
    return out


# --- historique des actions par appareil ---------------------------------------------------
ACTIVITY_CATS = [   # (identifiant, libellé, couleur)
    ("video", "Vidéos", "var(--pink)"),
    ("audio", "Audio", "var(--teal)"),
    ("pdf", "PDF", "var(--accent)"),
    ("text", "Texte et code", "var(--folder)"),
    ("web", "Navigation web", "var(--green)"),
    ("image", "Images", "var(--orange)"),
    ("browse", "Dossiers", "var(--muted)"),
    ("download", "Téléchargements", "var(--red)"),
    ("edit", "Modifications", "#9b6bd6"),
]
KIND_CATS = {"video": "video", "audio": "audio", "pdf": "pdf", "image": "image", "web": "web",
             "text": "text", "binary": "download"}
ACTIVITY_GAP = {"video": 300, "audio": 300}   # secondes sans requête avant de compter une nouvelle action
DEFAULT_GAP = 90
HISTORY_DAYS = 30                  # durée de conservation
HISTORY_MAX = 3000                 # actions gardées par appareil
HISTORY_PATH = BLOCKLIST_PATH.with_name("history.json")
HISTORY_RANGES = {"24h": (24 * 3600, 900), "7d": (7 * 24 * 3600, 3600), "30d": (30 * 24 * 3600, 6 * 3600)}
_history = {}                      # ip -> deque de [début, fin, catégorie, fichier, octets, requêtes]
_hist_dirty = False


def classify(path, q):
    """Requête -> (catégorie, fichier) si c'est une action de l'utilisateur, sinon None
    (miniatures, sous-titres, ressources pdf.js, tableau de bord… ne comptent pas)."""
    def arg(name):
        return q.get(name, [""])[0]

    if path == "/":
        return None if arg("token") else ("browse", arg("folder") or "/")
    if path == "/view":
        return "text", arg("f")
    if path == "/edit":
        return "edit", arg("f")
    if path == "/watch":
        return "video", arg("f")
    if path == "/listen":
        return "audio", arg("f")
    if path == "/pdf":
        return "pdf", arg("f")
    if path == "/preview":
        pf = resolve_inside(arg("f"))
        return ("text" if pf is not None and pf.suffix.lower() in MD_EXT else "web"), arg("f")
    if path == "/raw":
        f = arg("f")
        if arg("dl") == "1":
            return "download", f
        p = resolve_inside(f)
        return KIND_CATS.get(kind_of(p) if p else "text", "text"), f
    if path.startswith("/docs/"):
        return "pdf", unquote(path[len("/docs/"):])
    if path.startswith("/s/"):
        parts = path.split("/", 3)    # le jeton (parts[2]) n'est jamais conservé
        return "web", unquote(parts[3]) if len(parts) > 3 else ""
    if path in ("/save", "/delete", "/rename"):
        return "edit", arg("f")
    if path == "/upload":
        return "edit", (arg("d") + "/" + arg("n")).strip("/")
    return None


def record_event(ip, cat, file):
    """Ajoute une action à l'historique ; les requêtes rapprochées sur un même fichier (flux vidéo
    découpé en plages, par exemple) sont fusionnées en une seule action. -> entrée modifiable."""
    global _hist_dirty
    now = time.time()
    gap = ACTIVITY_GAP.get(cat, DEFAULT_GAP)
    file = file[:300]
    with _dev_lock:
        h = _history.get(ip)
        if h is None:
            h = _history[ip] = deque(maxlen=HISTORY_MAX)
        for i, e in enumerate(reversed(h)):
            if i >= 8:
                break
            if e[2] == cat and e[3] == file and now - e[1] <= gap:
                e[1] = now
                e[5] += 1
                _hist_dirty = True
                return e
        e = [now, now, cat, file, 0, 1]
        h.append(e)
        _hist_dirty = True
        return e


def add_bytes(entry, n):
    if entry is not None and n:
        with _dev_lock:
            entry[4] += n


def save_history():
    """Écrit appareils + historique (atomique, droits 0600) après avoir purgé ce qui est trop ancien."""
    global _hist_dirty
    cutoff = time.time() - HISTORY_DAYS * 86400
    with _dev_lock:
        for ip in list(_history):
            h = _history[ip]
            while h and h[0][1] < cutoff:
                h.popleft()
            if not h:
                del _history[ip]
        for ip in [ip for ip, d in _devices.items() if d["last"] < cutoff and ip not in _blocked]:
            del _devices[ip]
        data = {"devices": {ip: dict(d) for ip, d in _devices.items()},
                "history": {ip: [list(e) for e in h] for ip, h in _history.items()}}
        _hist_dirty = False
    try:
        HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
        tmp = HISTORY_PATH.with_name(HISTORY_PATH.name + ".tmp")
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, separators=(",", ":"))
        os.replace(tmp, HISTORY_PATH)
    except OSError:
        _hist_dirty = True      # nouvel essai au prochain passage


def load_history():
    try:
        data = json.loads(HISTORY_PATH.read_text(encoding="utf-8"))
        devices, history = data.get("devices", {}), data.get("history", {})
    except (OSError, ValueError, AttributeError):
        return
    cats = {c[0] for c in ACTIVITY_CATS}
    with _dev_lock:
        for ip, d in devices.items():
            try:
                ipaddress.ip_address(ip)
                _devices[ip] = {"first": float(d["first"]), "last": float(d["last"]), "hits": int(d["hits"]),
                                "ua": str(d.get("ua", ""))[:60], "auth": bool(d.get("auth"))}
            except (ValueError, KeyError, TypeError, AttributeError):
                continue
        for ip, items in history.items():
            try:
                ipaddress.ip_address(ip)
            except ValueError:
                continue
            h = deque(maxlen=HISTORY_MAX)
            for e in items if isinstance(items, list) else []:
                try:
                    if e[2] in cats:
                        h.append([float(e[0]), float(e[1]), e[2], str(e[3])[:300], int(e[4]), int(e[5])])
                except (IndexError, ValueError, TypeError):
                    continue
            if h:
                _history[ip] = h


def _on_term(signum, frame):
    raise SystemExit(0)     # kill / arrêt du système : passe par le « finally » qui enregistre l'historique


def history_flusher():
    while True:
        time.sleep(120)
        if _hist_dirty:
            save_history()


def history_report(ip, rng):
    """Courbes, totaux, fichiers les plus consultés et liste récente pour un appareil (ou « all »)."""
    span, step = HISTORY_RANGES.get(rng, HISTORY_RANGES["24h"])
    n = span // step
    now = time.time()
    start = (int(now // step) + 1) * step - span
    series = {c[0]: {"actions": [0] * n, "bytes": [0] * n, "seconds": [0.0] * n} for c in ACTIVITY_CATS}
    totals = {c[0]: {"actions": 0, "bytes": 0, "seconds": 0.0} for c in ACTIVITY_CATS}
    with _dev_lock:
        sources = _history.items() if ip == "all" else [(ip, _history.get(ip, ()))]
        rows = [(dev, tuple(e)) for dev, h in sources for e in h if e[1] >= start]
    top = {}
    for dev, (s, e, cat, file, nbytes, reqs) in rows:
        if cat not in series:
            continue
        idx = int((s - start) // step)
        if 0 <= idx < n:
            series[cat]["actions"][idx] += 1
            series[cat]["bytes"][idx] += nbytes
            totals[cat]["actions"] += 1
            totals[cat]["bytes"] += nbytes
            if cat != "browse" and file:
                t = top.setdefault((cat, file), [0, 0.0, 0])
                t[0] += 1
                t[1] += e - s
                t[2] += nbytes
        a, b = max(s, start), min(e, start + span)
        if b > a:    # durée répartie sur les tranches recouvertes
            for i in range(int((a - start) // step), min(int((b - start) // step), n - 1) + 1):
                part = min(b, start + (i + 1) * step) - max(a, start + i * step)
                if part > 0:
                    series[cat]["seconds"][i] += part
                    totals[cat]["seconds"] += part
    for cat in list(series):
        series[cat]["seconds"] = [round(v) for v in series[cat]["seconds"]]
        totals[cat]["seconds"] = round(totals[cat]["seconds"])
        if not (totals[cat]["actions"] or totals[cat]["seconds"] or totals[cat]["bytes"]):
            del series[cat], totals[cat]
    top_rows = sorted(top.items(), key=lambda kv: (-kv[1][0], -kv[1][1]))[:8]
    recent = sorted(rows, key=lambda r: -r[1][1])[:100]
    return {
        "ok": True, "ip": ip, "range": rng if rng in HISTORY_RANGES else "24h", "start": start, "step": step, "n": n,
        "series": series, "totals": totals,
        "top": [{"cat": k[0], "file": k[1], "n": v[0], "seconds": round(v[1]), "bytes": v[2]} for k, v in top_rows],
        "recent": [{"ip": dev, "t": s, "end": e, "cat": cat, "file": file, "bytes": nb, "n": reqs}
                   for dev, (s, e, cat, file, nb, reqs) in recent],
    }


_bundle_cache = {}


MD_CSS = r"""
/* ---------- Aperçu Markdown ---------- */
.mdprog{height:3px; flex-shrink:0}
.mdprog i{display:block; height:100%; width:0; background:var(--accent); transition:width .1s linear}
.mdscroll{flex:1; min-height:0; overflow-y:auto; overflow-x:hidden; background:var(--surface); overscroll-behavior:contain; outline:none; -webkit-overflow-scrolling:touch}
.mdwrap{display:flex; justify-content:center; align-items:flex-start; gap:56px; max-width:1260px; margin:0 auto; padding:44px 28px 140px}
.mdart{
  --serif:Charter,'Bitstream Charter','Iowan Old Style','Palatino Linotype',Palatino,Georgia,'Noto Serif','Times New Roman',serif;
  --sans:Inter,system-ui,-apple-system,'Segoe UI',Roboto,'Helvetica Neue',sans-serif;
  --mono:ui-monospace,SFMono-Regular,Menlo,Consolas,'Liberation Mono',monospace;
  flex:1 1 auto; min-width:0; max-width:44rem;
  font-family:var(--serif); font-size:var(--mdfs,18px); line-height:1.78; color:var(--text);
  font-kerning:normal; text-rendering:optimizeLegibility; overflow-wrap:break-word; hanging-punctuation:first;
}
.mdart.sans{font-family:var(--sans); line-height:1.7}
.mdart>:first-child{margin-top:0}
.mdart p{margin:0 0 1.1em}
.mdart p.empty{color:var(--muted); text-align:center; margin-top:3em}
.mdart :is(h1,h2,h3,h4,h5,h6){font-family:var(--sans); color:var(--text); line-height:1.25; scroll-margin-top:18px; position:relative}
.mdart h1{font-size:2.15em; font-weight:780; letter-spacing:-.025em; margin:1.6em 0 .55em}
.mdart h2{font-size:1.52em; font-weight:740; letter-spacing:-.018em; margin:2.3em 0 .65em; padding-bottom:.32em; border-bottom:1px solid var(--border)}
.mdart h3{font-size:1.22em; font-weight:700; letter-spacing:-.01em; margin:1.9em 0 .5em}
.mdart h4{font-size:1.04em; font-weight:700; margin:1.6em 0 .4em}
.mdart :is(h5,h6){font-size:.9em; font-weight:700; margin:1.5em 0 .4em; color:var(--muted)}
.mdart h1:first-child{margin-top:0}
.mdart .anc{margin-left:.45em; font-weight:500; color:var(--muted); text-decoration:none; opacity:0; transition:opacity .15s}
.mdart :is(h1,h2,h3,h4,h5,h6):hover .anc,.mdart .anc:focus-visible{opacity:1}
@media(hover:none){.mdart .anc{display:none}}
.mdart a{color:var(--accent); text-decoration:underline; text-decoration-thickness:1px; text-underline-offset:.2em; text-decoration-color:var(--accent)}
.mdart a:hover{text-decoration-thickness:2px}
.mdart strong{font-weight:700}
.mdart :not(pre)>code{font-family:var(--mono); font-size:.85em; padding:.14em .42em; border-radius:6px; background:var(--gray-soft); overflow-wrap:anywhere}
.mdart mark{background:rgba(255,200,40,.4); color:inherit; padding:0 .18em; border-radius:3px}
.mdart kbd{font:600 .78em var(--mono); padding:.14em .52em; border:1px solid var(--border); border-bottom-width:2px; border-radius:6px; background:var(--bg)}
.mdart del{color:var(--muted)}
.mdart hr{border:0; height:1px; background:var(--border); margin:2.6em 0}
.mdart img{max-width:100%; height:auto; border-radius:10px; cursor:zoom-in}
.mdart a img{cursor:pointer}
.mdart p>img:only-child{display:block; margin:1.3em auto}
.mdart [align=center]{text-align:center}
.mdart [align=right]{text-align:right}
.mdart ul,.mdart ol{margin:0 0 1.1em; padding-left:1.55em}
.mdart li{margin:.32em 0}
.mdart li::marker{color:var(--muted)}
.mdart li>:is(ul,ol){margin:.3em 0 .1em}
.mdart li>p:last-child{margin-bottom:0}
.mdart ul.contains-task-list{padding-left:.15em; list-style:none}
.mdart li.task-item{list-style:none; position:relative; padding-left:1.75em}
.mdart li.task-item>input{position:absolute; left:0; top:.5em; margin:0; accent-color:var(--accent)}
.mdart li.task-item.done{color:var(--muted)}
.mdart blockquote{margin:1.4em 0; padding:.05em 0 .05em 1.15em; border-left:3px solid var(--accent); color:var(--muted)}
.mdart blockquote>:last-child{margin-bottom:0}
.mdart .alert{--c:var(--accent); margin:1.5em 0; padding:.85em 1.1em .35em; border-left:4px solid var(--c); border-radius:4px 12px 12px 4px; background:var(--bg-2)}
@supports (background:color-mix(in srgb,red 10%,transparent)){.mdart .alert{background:color-mix(in srgb,var(--c) 9%,transparent)}}
.mdart .alert-tip{--c:var(--green)}
.mdart .alert-important{--c:var(--pink)}
.mdart .alert-warning{--c:var(--orange)}
.mdart .alert-caution{--c:var(--red)}
.mdart .alert-t{display:flex; align-items:center; gap:8px; margin:0 0 .5em; font:700 .88em var(--sans); color:var(--c)}
.mdart .alert-t .i{width:18px; height:18px}
.mdart figure.code{margin:1.5em 0; border:1px solid var(--border); border-radius:12px; overflow:hidden; background:var(--bg)}
.mdart figure.code figcaption{display:flex; align-items:center; justify-content:space-between; gap:10px; padding:5px 6px 5px 14px; font:600 12px var(--sans); color:var(--muted); background:var(--bg-2); border-bottom:1px solid var(--border)}
.mdart .copy{font:600 12px var(--sans); padding:5px 11px; border-radius:8px; cursor:pointer; color:var(--muted); background:transparent; border:1px solid transparent}
.mdart .copy:hover,.mdart .copy:focus-visible{color:var(--accent); border-color:var(--border); background:var(--surface)}
.mdart figure.code pre{margin:0; padding:15px 18px; overflow-x:auto; font:.83em/1.68 var(--mono); tab-size:4; -moz-tab-size:4; color:var(--text)}
.mdart pre code{font:inherit; background:none; padding:0; border-radius:0}
.mdart pre i{font-style:normal}
.mdart pre i.c{color:var(--syn-comment); font-style:italic}
.mdart pre i.k{color:var(--syn-keyword)}
.mdart pre i.s{color:var(--syn-string)}
.mdart pre i.n{color:var(--syn-number)}
.mdart pre i.f{color:var(--syn-function)}
.mdart pre i.t{color:var(--syn-type)}
.mdart pre i.p{color:var(--syn-prop)}
.mdart pre i.da{color:var(--green)}
.mdart pre i.dd{color:var(--red)}
.mdart pre i.h{color:var(--syn-function)}
.mdart .tblwrap{margin:1.5em 0; overflow-x:auto; border:1px solid var(--border); border-radius:12px}
.mdart table{border-collapse:collapse; width:100%; font:.9em/1.5 var(--sans)}
.mdart th,.mdart td{padding:.62em .95em; text-align:left; vertical-align:top; border-bottom:1px solid var(--border)}
.mdart th{background:var(--bg-2); font-weight:700}
.mdart tbody tr:last-child td{border-bottom:0}
.mdart tbody tr:nth-child(even) td{background:var(--bg)}
.mdart details{margin:1.3em 0; padding:.15em 1.1em; border:1px solid var(--border); border-radius:12px}
.mdart details[open]{padding-bottom:.4em}
.mdart summary{cursor:pointer; padding:.5em 0; font:600 .92em var(--sans); color:var(--text)}
.mdart details.fm{font-size:.85em; color:var(--muted); margin:0 0 2em}
.mdart details.fm dl{display:grid; grid-template-columns:max-content 1fr; gap:.3em 1.2em; margin:.2em 0 .8em; font-family:var(--sans)}
.mdart details.fm dt{font-weight:600}
.mdart details.fm dd{margin:0}
.mdart .fnref{font-size:.75em; line-height:0}
.mdart .fnref a,.mdart a.fnback{text-decoration:none}
.mdart .footnotes{margin-top:3.2em; padding-top:1.1em; border-top:1px solid var(--border); font-size:.86em; color:var(--muted)}
.mdart .footnotes ol{padding-left:1.4em}
.mdart a.fnback{margin-left:.4em; font:600 .85em var(--sans)}
.mdtoc{flex:0 0 250px; width:250px; position:sticky; top:30px; align-self:flex-start; max-height:calc(100vh - 230px); max-height:calc(100dvh - 210px); overflow-y:auto; padding-left:18px; border-left:1px solid var(--border); font:13.5px/1.4 Inter,system-ui,-apple-system,'Segoe UI',Roboto,sans-serif; scrollbar-width:thin}
.mdtoc h2{margin:0 0 10px; font-size:12.5px; font-weight:700; color:var(--muted)}
.mdtoc a{display:block; margin-left:-20px; padding:4px 8px 4px calc(18px + var(--ind,0) * 13px); border-left:2px solid transparent; color:var(--muted); text-decoration:none}
.mdtoc a:hover{color:var(--text)}
.mdtoc a.on{color:var(--accent); border-left-color:var(--accent); font-weight:600}
.mdveil{position:fixed; inset:0; z-index:55; background:rgba(8,10,16,.5)}
.mdbox{position:fixed; inset:0; z-index:80; display:grid; place-items:center; padding:16px; background:rgba(8,10,16,.9); cursor:zoom-out}
.mdbox img{max-width:100%; max-height:100%; border-radius:8px; background:#fff}
@media(min-width:1000px){body.toc-off .mdtoc{display:none}}
@media(max-width:999px){
  .mdtoc{display:none}
  .mdtoc.open{display:block; position:fixed; z-index:60; top:0; right:0; bottom:0; width:min(86vw,330px); max-height:none; padding:72px 18px 28px 34px; border-left:1px solid var(--border); background:var(--surface); box-shadow:var(--shadow-hover)}
  .mdwrap{padding:26px 18px 110px}
  .mdart h1{font-size:1.85em}
}
@media print{
  body.md-page{height:auto; display:block; overflow:visible; background:#fff}
  .edbar,.edtools,.mdprog,.mdtoc,.mdveil,.mdart .copy,.mdart .anc{display:none!important}
  .mdscroll{overflow:visible; background:#fff}
  .mdwrap{display:block; padding:0}
  .mdart{max-width:none; font-size:11.5pt; color:#000}
  .mdart figure.code,.mdart .tblwrap,.mdart .alert,.mdart img{break-inside:avoid}
  .mdart figure.code pre{white-space:pre-wrap; overflow:visible}
  .mdart a{color:#000}
}
"""

MD_JS = r"""
(function(){
'use strict';
var cfg = window.MDCFG, EXT = cfg.exts, ICO = cfg.ico || {};
var src = String(cfg.doc || '').replace(/\r\n?/g, '\n');
function $(id){ return document.getElementById(id); }
function esc(s){
  return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}
function store(k, v){
  try { if (v === undefined) return localStorage.getItem(k); localStorage.setItem(k, v); } catch(e) {}
  return null;
}

/* ---------- URL : chemins relatifs, liens sûrs ---------- */
function extOf(p){ var m = /\.([A-Za-z0-9]+)$/.exec(p); return m ? m[1].toLowerCase() : ''; }
function has(list, e){ return !!e && list.indexOf(e) >= 0; }
function joinPath(base, rel){
  var parts = (base ? base.split('/') : []).concat(rel.split('/')), out = [];
  parts.forEach(function(s){
    if (s === '' || s === '.') return;
    if (s === '..') out.pop(); else out.push(s);
  });
  return out.join('/');
}
function safeUrl(u, isImg){
  u = String(u || '').trim();
  if (!u) return null;
  if (/^(?:https?:)?\/\//i.test(u)) return {href: u, ext: true};
  if (u.charAt(0) === '#') return isImg ? null : {href: u};
  if (/^(?:mailto|tel):/i.test(u)) return isImg ? null : {href: u};
  if (/^data:image\/(?:png|jpe?g|gif|webp|avif|svg\+xml)[;,]/i.test(u)) return isImg ? {href: u} : null;
  if (/^[a-z][a-z0-9+.-]*:/i.test(u)) return null;
  var m = /^([^?#]*)([?#][\s\S]*)?$/.exec(u), path = m[1], tail = m[2] || '';
  try { path = decodeURIComponent(path); } catch(e) {}
  var full = path.charAt(0) === '/' ? joinPath('', path) : joinPath(cfg.dir, path);
  var hi = tail.indexOf('#'), hash = hi >= 0 ? tail.slice(hi) : '';
  if (!full) return hash ? {href: hash} : null;
  var q = encodeURIComponent(full), e = extOf(full), href;
  if (isImg) href = e === 'svg' ? cfg.site + full.split('/').map(encodeURIComponent).join('/') : '/raw?f=' + q;
  else if (has(EXT.md, e) || has(EXT.web, e)) href = '/preview?f=' + q + hash;
  else if (e === 'pdf') href = '/pdf?f=' + q + hash;
  else if (has(EXT.video, e)) href = '/watch?f=' + q;
  else if (has(EXT.audio, e)) href = '/listen?f=' + q;
  else if (has(EXT.image, e)) href = '/raw?f=' + q;
  else if (has(EXT.binary, e)) href = '/raw?dl=1&f=' + q;
  else href = '/view?f=' + q + hash;
  return {href: href};
}
function linkTag(inner, u, t){
  u = String(u || '').replace(/^<|>$/g, '');
  var r = safeUrl(u, false);
  if (!r) return inner;
  return '<a href="' + esc(r.href) + '"' + (t ? ' title="' + esc(t) + '"' : '') +
    (r.ext ? ' target="_blank" rel="noopener noreferrer"' : '') + '>' + inner + '</a>';
}
function imgTag(alt, u, t){
  u = String(u || '').replace(/^<|>$/g, '');
  var r = safeUrl(u, true);
  if (!r) return esc(alt);
  return '<img src="' + esc(r.href) + '" alt="' + esc(alt) + '"' + (t ? ' title="' + esc(t) + '"' : '') + ' loading="lazy">';
}

/* ---------- Inline ---------- */
var refs = Object.create(null), fnDefs = Object.create(null), fnOrder = [], stash = [];
function keep(h){ stash.push(h); return '\u0001' + (stash.length - 1) + '\u0002'; }
function unstash(s){
  var guard = 0;
  while (/\u0001\d+\u0002/.test(s) && guard++ < 24) {
    s = s.replace(/\u0001(\d+)\u0002/g, function(m, n){ return stash[+n]; });
  }
  return s;
}
function inline(s){
  s = s.replace(/(?: {2,}|\\)\n/g, function(){ return keep('<br>') + '\n'; });
  s = s.replace(/(`+)([\s\S]*?[^`])\1(?!`)/g, function(m, a, c){
    c = c.replace(/\n/g, ' ');
    if (/^ [\s\S]* $/.test(c) && /\S/.test(c)) c = c.slice(1, -1);
    return keep('<code>' + esc(c) + '</code>');
  });
  s = s.replace(/\\([\\`*_{}\[\]()#+\-.!|~<>=$"'&])/g, function(m, c){ return keep(esc(c)); });
  s = s.replace(/!\[([^\]]*)\]\(\s*(<[^>]*>|[^)\s]+)(?:\s+"([^"]*)")?\s*\)/g, function(m, alt, u, t){
    return keep(imgTag(alt, u, t));
  });
  s = s.replace(/!\[([^\]]*)\]\[([^\]]*)\]/g, function(m, alt, id){
    var r = refs[(id || alt).toLowerCase()];
    return r ? keep(imgTag(alt, r.u, r.t)) : m;
  });
  s = s.replace(/\[\^([^\]\s]+)\]/g, function(m, id){
    if (!(id in fnDefs)) return m;
    var n = fnOrder.indexOf(id);
    if (n < 0) { fnOrder.push(id); n = fnOrder.length - 1; }
    return keep('<sup class="fnref"><a href="#fn-' + esc(id) + '" id="fnref-' + esc(id) + '">' + (n + 1) + '</a></sup>');
  });
  s = s.replace(/\[((?:[^\[\]]|\[[^\]]*\])*)\]\(\s*(<[^>]*>|[^)\s]*)(?:\s+"([^"]*)")?\s*\)/g, function(m, text, u, t){
    return keep(linkTag(inline(text), u, t));
  });
  s = s.replace(/\[((?:[^\[\]]|\[[^\]]*\])*)\]\[([^\]]*)\]/g, function(m, text, id){
    var r = refs[(id || text).toLowerCase()];
    return r ? keep(linkTag(inline(text), r.u, r.t)) : m;
  });
  s = s.replace(/\[([^\[\]]+)\](?!\()/g, function(m, id){
    var r = refs[id.toLowerCase()];
    return r ? keep(linkTag(esc(id), r.u, r.t)) : m;
  });
  s = s.replace(/<((?:https?:\/\/|mailto:)[^\s<>]+)>/gi, function(m, u){ return keep(linkTag(esc(u), u)); });
  s = s.replace(/<([^\s<>@]+@[^\s<>@]+\.[^\s<>@]+)>/g, function(m, u){ return keep(linkTag(esc(u), 'mailto:' + u)); });
  s = s.replace(/(^|[\s(>])(https?:\/\/[^\s<]*[^\s<.,;:!?'")\]])/g, function(m, pre, u){
    return pre + keep(linkTag(esc(u), u));
  });
  s = s.replace(/<!--[\s\S]*?-->/g, '');
  s = s.replace(/<br\s*\/?>/gi, function(){ return keep('<br>'); });
  s = s.replace(/<(\/?)(kbd|sub|sup|mark|b|i|u|em|strong|del|ins|small|s|abbr|cite|q)>/gi, function(m, sl, t){
    return keep('<' + sl + t.toLowerCase() + '>');
  });
  s = esc(s);
  s = s.replace(/\*\*\*(?=\S)([\s\S]*?\S)\*\*\*/g, '<strong><em>$1</em></strong>')
       .replace(/\*\*(?=\S)([\s\S]*?\S)\*\*/g, '<strong>$1</strong>')
       .replace(/(^|[^\w])__(?=\S)([\s\S]*?\S)__(?!\w)/g, '$1<strong>$2</strong>')
       .replace(/\*(?=[^\s*])([\s\S]*?[^\s*])\*/g, '<em>$1</em>')
       .replace(/(^|[^\w])_(?=[^\s_])([\s\S]*?[^\s_])_(?!\w)/g, '$1<em>$2</em>')
       .replace(/~~(?=\S)([\s\S]*?\S)~~/g, '<del>$1</del>')
       .replace(/==(?=\S)([\s\S]*?\S)==/g, '<mark>$1</mark>');
  return s;
}
function ih(s){ return unstash(inline(s)); }

/* ---------- HTML brut : assaini via DOMParser (inerte) ---------- */
var HT = {}, HA = {}, DROP = {};
'a abbr b blockquote br caption center cite code col colgroup dd del details div dl dt em figcaption figure h1 h2 h3 h4 h5 h6 hr i img ins kbd li mark ol p picture pre q s small span strong sub summary sup table tbody td tfoot th thead tr u ul'
  .split(' ').forEach(function(t){ HT[t] = 1; });
'href src alt title width height align colspan rowspan open start valign'.split(' ').forEach(function(a){ HA[a] = 1; });
'script style iframe object embed noscript template textarea svg math link meta form input button select audio video source'.split(' ')
  .forEach(function(t){ DROP[t] = 1; });
var VOID = {br: 1, hr: 1, img: 1, col: 1};
function cleanHtml(str){
  var doc = new DOMParser().parseFromString('<body>' + str + '</body>', 'text/html');
  function walk(node){
    var out = '';
    node.childNodes.forEach(function(c){
      if (c.nodeType === 3) { out += esc(c.nodeValue); return; }
      if (c.nodeType !== 1) return;
      var t = c.tagName.toLowerCase();
      if (DROP[t]) return;
      var inner = VOID[t] ? '' : walk(c);
      if (!HT[t]) { out += inner; return; }
      var attrs = '', ext = false;
      Array.prototype.forEach.call(c.attributes, function(a){
        var n = a.name.toLowerCase(), v = a.value;
        if (!HA[n]) return;
        if (n === 'href' || n === 'src') {
          var r = safeUrl(v, t === 'img');
          if (!r) return;
          if (r.ext && n === 'href') ext = true;
          v = r.href;
        } else if (n === 'align') {
          if (!/^(?:left|right|center|justify)$/i.test(v)) return;
        } else if (n === 'width' || n === 'height' || n === 'colspan' || n === 'rowspan' || n === 'start') {
          if (!/^\d+%?$/.test(v)) return;
        } else if (n === 'open') {
          v = '';
        }
        attrs += ' ' + n + '="' + esc(v) + '"';
      });
      if (t === 'a' && ext) attrs += ' target="_blank" rel="noopener noreferrer"';
      if (t === 'img') attrs += ' loading="lazy"';
      out += VOID[t] ? '<' + t + attrs + '>' : '<' + t + attrs + '>' + inner + '</' + t + '>';
    });
    return out;
  }
  return walk(doc.body);
}

/* ---------- Coloration syntaxique légère ---------- */
var KW = {};
function defKw(name, words){ var o = {}; words.split(' ').forEach(function(w){ o[w] = 1; }); KW[name] = o; }
defKw('js', 'async await break case catch class const continue debugger default delete do else export extends finally for from function if import in instanceof let new of return static super switch this throw try typeof var void while with yield true false null undefined interface type enum implements public private protected readonly abstract namespace declare as');
defKw('py', 'and as assert async await break class continue def del elif else except finally for from global if import in is lambda nonlocal not or pass raise return try while with yield True False None self');
defKw('sh', 'if then else elif fi for while do done case esac function in select until return export local echo cd exit set unset source alias sudo');
defKw('c', 'int char float double void long short unsigned signed struct union enum typedef static const extern return if else for while do switch case break continue goto sizeof class public private protected new delete this namespace using template typename virtual override final try catch throw throws import package interface implements extends abstract synchronized volatile bool true false null nil fn let mut impl trait pub use mod match loop where async await func go defer chan map range var type select fallthrough default echo function foreach as isset array string object');
defKw('sql', 'select from where insert into values update set delete create table alter drop join left right inner outer on group by order having limit offset and or not null is in as distinct union all primary key foreign references index unique default auto_increment varchar int text date timestamp boolean case when then else end like between exists view database use show describe');
defKw('json', 'true false null');
defKw('cfg', 'true false null yes no on off');
defKw('css', 'important');
var DQ = '"(?:\\\\.|[^"\\\\\\n])*"', SQ = "'(?:\\\\.|[^'\\\\\\n])*'";
var SPECS = {
  js: {c: '\\/\\*[\\s\\S]*?\\*\\/|\\/\\/[^\\n]*', s: DQ + '|' + SQ + '|`(?:\\\\[\\s\\S]|[^`\\\\])*`', k: KW.js},
  c: {c: '\\/\\*[\\s\\S]*?\\*\\/|\\/\\/[^\\n]*|#[^\\n]*', s: DQ + '|' + SQ, k: KW.c},
  py: {c: '#[^\\n]*', s: '"{3}[\\s\\S]*?"{3}|\'{3}[\\s\\S]*?\'{3}|[rRbBfFuU]{0,2}' + DQ + '|[rRbBfFuU]{0,2}' + SQ, k: KW.py},
  sh: {c: '#[^\\n]*', s: '"(?:\\\\[\\s\\S]|[^"\\\\])*"|\'[^\']*\'', k: KW.sh},
  sql: {c: '--[^\\n]*|\\/\\*[\\s\\S]*?\\*\\/', s: "'(?:''|\\\\.|[^'\\\\])*'|" + DQ + '|`[^`]*`', k: KW.sql, ci: true},
  json: {c: '\\/\\*[\\s\\S]*?\\*\\/|\\/\\/[^\\n]*', s: DQ, k: KW.json, json: true},
  cfg: {c: '#[^\\n]*|;[^\\n]*', s: DQ + '|' + SQ, k: KW.cfg, ci: true, id: '[A-Za-z_.][\\w.-]*', prop: true},
  css: {c: '\\/\\*[\\s\\S]*?\\*\\/', s: DQ + '|' + SQ, k: KW.css, id: '@?-{0,2}[A-Za-z_][\\w-]*',
        n: '#[0-9a-fA-F]{3,8}\\b|\\b\\d[\\d.]*(?:px|r?em|vh|vw|ms|deg|fr|s|%)?', prop: true, at: true}
};
var LANG = {
  js: 'js', javascript: 'js', mjs: 'js', cjs: 'js', jsx: 'js', ts: 'js', typescript: 'js', tsx: 'js',
  py: 'py', python: 'py', python3: 'py',
  sh: 'sh', bash: 'sh', zsh: 'sh', shell: 'sh', console: 'sh',
  c: 'c', h: 'c', cpp: 'c', 'c++': 'c', cc: 'c', hpp: 'c', java: 'c', cs: 'c', csharp: 'c', go: 'c', rust: 'c', rs: 'c',
  php: 'c', kotlin: 'c', swift: 'c', dart: 'c', scala: 'c',
  sql: 'sql', mysql: 'sql', postgres: 'sql', postgresql: 'sql', sqlite: 'sql',
  json: 'json', jsonc: 'json',
  yaml: 'cfg', yml: 'cfg', toml: 'cfg', ini: 'cfg', conf: 'cfg', env: 'cfg', dotenv: 'cfg', properties: 'cfg',
  css: 'css', scss: 'css', less: 'css',
  html: 'html', xml: 'html', svg: 'html', vue: 'html', xhtml: 'html',
  diff: 'diff', patch: 'diff'
};
function lex(code, spec){
  var num = spec.n || '\\b0[xX][0-9a-fA-F_]+\\b|\\b\\d[\\d_]*(?:\\.\\d+)?(?:[eE][+-]?\\d+)?\\b';
  var id = spec.id || '[A-Za-z_$@][\\w$]*';
  var re = new RegExp('(' + spec.c + ')|(' + spec.s + ')|(' + num + ')|(' + id + ')', 'g');
  var out = '', last = 0, m, rest, w;
  while ((m = re.exec(code))) {
    if (m[0] === '') { re.lastIndex++; continue; }
    out += esc(code.slice(last, m.index));
    last = re.lastIndex;
    rest = code.slice(last, last + 24);
    if (m[1] !== undefined) out += '<i class="c">' + esc(m[0]) + '</i>';
    else if (m[2] !== undefined) out += '<i class="' + (spec.json && /^\s*:/.test(rest) ? 'p' : 's') + '">' + esc(m[0]) + '</i>';
    else if (m[3] !== undefined) out += '<i class="n">' + esc(m[0]) + '</i>';
    else {
      w = m[4];
      var key = spec.ci ? w.toLowerCase() : w;
      if (spec.at && w.charAt(0) === '@') out += '<i class="k">' + esc(w) + '</i>';
      else if (spec.prop && /^[ \t]*[:=]/.test(rest)) out += '<i class="p">' + esc(w) + '</i>';
      else if (spec.k[key] === 1) out += '<i class="k">' + esc(w) + '</i>';
      else if (/^[ \t]*\(/.test(rest)) out += '<i class="f">' + esc(w) + '</i>';
      else if (/^[A-Z][a-z]/.test(w)) out += '<i class="t">' + esc(w) + '</i>';
      else out += esc(w);
    }
  }
  return out + esc(code.slice(last));
}
function hlHtml(code){
  var re = /(<!--[\s\S]*?-->|<![A-Za-z][^>]*>)|(<\/?)([A-Za-z][\w:-]*)((?:\s+[^\s=>\/]+(?:\s*=\s*(?:"[^"]*"|'[^']*'|[^\s>]+))?)*)(\s*\/?>)/g;
  var out = '', last = 0, m;
  while ((m = re.exec(code))) {
    out += esc(code.slice(last, m.index));
    last = re.lastIndex;
    if (m[1] !== undefined) { out += '<i class="c">' + esc(m[0]) + '</i>'; continue; }
    out += esc(m[2]) + '<i class="k">' + esc(m[3]) + '</i>';
    out += m[4].replace(/(\s+)([^\s=]+)(?:(\s*=\s*)("[^"]*"|'[^']*'|[^\s]+))?/g, function(x, sp, name, eq, val){
      return esc(sp) + '<i class="p">' + esc(name) + '</i>' + (eq ? esc(eq) + '<i class="s">' + esc(val) + '</i>' : '');
    });
    out += esc(m[5]);
  }
  return out + esc(code.slice(last));
}
function hlDiff(code){
  return code.split('\n').map(function(l){
    var c = /^(?:\+\+\+|---)/.test(l) ? 'h' : l.charAt(0) === '+' ? 'da' : l.charAt(0) === '-' ? 'dd' : /^@@/.test(l) ? 'h' : '';
    return c ? '<i class="' + c + '">' + esc(l) + '</i>' : esc(l);
  }).join('\n');
}
function highlight(code, lang){
  var l = LANG[lang];
  if (!l || code.length > 120000) return esc(code);
  try {
    if (l === 'html') return hlHtml(code);
    if (l === 'diff') return hlDiff(code);
    return lex(code, SPECS[l]);
  } catch(e) { return esc(code); }
}
function codeBlock(code, info){
  var lang = (info.split(/\s+/)[0] || '').replace(/^\{\.?|\}$/g, '').replace(/^\./, '').toLowerCase();
  return '<figure class="code"><figcaption><span class="lang">' + esc(lang || 'texte') +
    '</span><button type="button" class="copy">Copier</button></figcaption><pre><code>' +
    highlight(code, lang) + '</code></pre></figure>';
}

/* ---------- Titres ---------- */
var slugs = Object.create(null), heads = [];
function slugify(t){
  t = t.toLowerCase().trim();
  try { t = t.replace(/[^\p{L}\p{N}\p{M}_\- ]/gu, ''); } catch(e) { t = t.replace(/[^\w\- ]/g, ''); }
  return t.replace(/ /g, '-');
}
function plain(html){ return new DOMParser().parseFromString('<body>' + html + '</body>', 'text/html').body.textContent; }
function heading(level, text){
  var html = ih(text.trim()), pt = plain(html).trim();
  var base = slugify(pt) || 'section', id = base, k = 1;
  while (slugs[id]) id = base + '-' + (k++);
  slugs[id] = 1;
  heads.push({level: level, id: id, text: pt});
  return '<h' + level + ' id="' + esc(id) + '">' + html +
    '<a class="anc" href="#' + esc(id) + '" aria-label="Lien vers cette section">#</a></h' + level + '>';
}

/* ---------- Blocs ---------- */
var RE_ATX = /^ {0,3}(#{1,6})(?:[ \t]+(.*?))?(?:[ \t]+#+)?[ \t]*$/;
var RE_HR = /^ {0,3}([-*_])(?:[ \t]*\1){2,}[ \t]*$/;
var RE_LIST = /^( *)([-*+]|\d{1,9}[.)])( +|$)(.*)$/;
var RE_QUOTE = /^ {0,3}> ?/;
var RE_TBL_SEP = /^ *\|? *:?-+:? *(?:\| *:?-+:? *)*\|? *$/;
var RE_HTML_BLOCK = /^ {0,3}<(?:p|div|center|table|h[1-6]|ul|ol|hr|img|picture|figure|section|a|br|blockquote|dl|pre)(?:[\s>\/]|$)/i;
var RE_HTML_INT = /^ {0,3}<(?:details|table|div|p|center|h[1-6]|ul|ol|hr|picture|figure|section|blockquote|dl|pre)(?:[\s>\/]|$)|^ {0,3}<!--/i;
var ALERTS = {
  note: {i: 'info', l: 'Note'}, tip: {i: 'bulb', l: 'Astuce'}, important: {i: 'msg_alert', l: 'Important'},
  warning: {i: 'alert', l: 'Avertissement'}, caution: {i: 'octagon', l: 'Attention'}
};
function isBlank(l){ return /^\s*$/.test(l); }
function leadSp(l){ return /^ */.exec(l)[0].length; }
function startsBlock(l){
  return /^ {0,3}(?:`{3,}|~{3,})/.test(l) || RE_ATX.test(l) || RE_HR.test(l) || /^ {0,3}>/.test(l) ||
    /^ {0,3}(?:[-*+]|1[.)])(?: +\S)/.test(l) || RE_HTML_INT.test(l);
}
function splitRow(l){
  l = l.trim();
  if (l.charAt(0) === '|') l = l.slice(1);
  if (/(^|[^\\])\|$/.test(l)) l = l.slice(0, -1);
  var cells = [], cur = '', i, c;
  for (i = 0; i < l.length; i++) {
    c = l.charAt(i);
    if (c === '\\' && l.charAt(i + 1) === '|') { cur += '|'; i++; continue; }
    if (c === '|') { cells.push(cur.trim()); cur = ''; } else cur += c;
  }
  cells.push(cur.trim());
  return cells;
}
function isTableAt(lines, i){
  if (i + 1 >= lines.length || lines[i].indexOf('|') < 0) return false;
  var sep = lines[i + 1];
  if (!RE_TBL_SEP.test(sep) || (sep.indexOf('|') < 0 && sep.indexOf(':') < 0)) return false;
  return splitRow(lines[i]).length === splitRow(sep).length;
}
function table(lines, i){
  var n = lines.length, head = splitRow(lines[i]);
  var al = splitRow(lines[i + 1]).map(function(c){
    var l = c.charAt(0) === ':', r = c.slice(-1) === ':';
    return l && r ? 'center' : r ? 'right' : l ? 'left' : '';
  });
  function cell(tag, c, k){
    return '<' + tag + (al[k] ? ' style="text-align:' + al[k] + '"' : '') + '>' + ih(c) + '</' + tag + '>';
  }
  var h = '<div class="tblwrap"><table><thead><tr>' + head.map(function(c, k){ return cell('th', c, k); }).join('') + '</tr></thead><tbody>';
  i += 2;
  while (i < n && !isBlank(lines[i]) && !startsBlock(lines[i])) {
    var row = splitRow(lines[i]);
    while (row.length < head.length) row.push('');
    row.length = head.length;
    h += '<tr>' + row.map(function(c, k){ return cell('td', c, k); }).join('') + '</tr>';
    i++;
  }
  return {html: h + '</tbody></table></div>', next: i};
}
function quote(qb){
  var m = /^\s*\[!(NOTE|TIP|IMPORTANT|WARNING|CAUTION)\][ \t]*(.*)$/i.exec(qb[0] || '');
  if (m) {
    var t = m[1].toLowerCase(), rest = qb.slice(1), A = ALERTS[t];
    if (m[2]) rest.unshift(m[2]);
    return '<div class="alert alert-' + t + '"><p class="alert-t">' + (ICO[A.i] || '') + '<span>' + A.l + '</span></p>' + blocks(rest) + '</div>';
  }
  return '<blockquote>' + blocks(qb) + '</blockquote>';
}
function sameKind(m, ordered, ch){
  return !!m && /^\d/.test(m[2]) === ordered && (ordered ? m[2].slice(-1) : m[2]) === ch;
}
function parseList(lines, i){
  var n = lines.length, first = RE_LIST.exec(lines[i]);
  var ordered = /^\d/.test(first[2]), ch = ordered ? first[2].slice(-1) : first[2];
  var start = ordered ? parseInt(first[2], 10) : 1, items = [], loose = false;
  while (i < n) {
    var m = RE_LIST.exec(lines[i]);
    if (!sameKind(m, ordered, ch)) break;
    var pad = m[3].length, w = m[1].length + m[2].length + ((pad === 0 || pad > 4) ? 1 : pad);
    var item = [m[4]];
    i++;
    while (i < n) {
      var l = lines[i];
      if (isBlank(l)) {
        var j = i + 1;
        while (j < n && isBlank(lines[j])) j++;
        if (j < n && leadSp(lines[j]) >= w) { for (; i < j; i++) item.push(''); continue; }
        break;
      }
      if (leadSp(l) >= w) { item.push(l.slice(w)); i++; continue; }
      if (!isBlank(item[item.length - 1]) && !startsBlock(l) && !RE_LIST.test(l)) { item.push(l.replace(/^ +/, '')); i++; continue; }
      break;
    }
    items.push(item);
    if (i < n && isBlank(lines[i])) {
      var k = i;
      while (k < n && isBlank(lines[k])) k++;
      var m2 = k < n ? RE_LIST.exec(lines[k]) : null;
      if (sameKind(m2, ordered, ch) && leadSp(lines[k]) < 4) { loose = true; i = k; continue; }
      break;
    }
  }
  var rendered = items.map(function(item){
    var task = null, tm = /^\[([ xX])\](?:[ \t]+|$)/.exec(item[0]);
    if (tm) { task = tm[1] !== ' '; item = [item[0].slice(tm[0].length)].concat(item.slice(1)); }
    var info = {}, h = blocks(item, true, info);
    if (info.gap) loose = true;
    return {h: h, task: task};
  });
  var tag = ordered ? 'ol' : 'ul';
  var hasTask = rendered.some(function(r){ return r.task !== null; });
  var html = '<' + tag + (ordered && start !== 1 ? ' start="' + start + '"' : '') + (hasTask ? ' class="contains-task-list"' : '') + '>' +
    rendered.map(function(r){
      var h = r.h;
      if (r.task !== null) {
        var cb = '<input type="checkbox" disabled' + (r.task ? ' checked' : '') + '>';
        h = h.charAt(0) === '\u0003' ? '\u0003' + cb + h.slice(1) : cb + h;
      }
      h = loose ? h.replace(/\u0003/g, '<p>').replace(/\u0004/g, '</p>') : h.replace(/[\u0003\u0004]/g, '');
      return '<li' + (r.task !== null ? ' class="task-item' + (r.task ? ' done' : '') + '"' : '') + '>' + h + '</li>';
    }).join('') + '</' + tag + '>';
  return {html: html, next: i};
}
function blocks(lines, defer, info){
  var out = [], i = 0, n = lines.length, gap = false, pend = false, m;
  function emit(h){ if (pend && out.length) gap = true; pend = false; out.push(h); }
  while (i < n) {
    var line = lines[i];
    if (isBlank(line)) { pend = true; i++; continue; }
    // code clôturé
    if ((m = /^( {0,3})(`{3,}|~{3,})(.*)$/.exec(line)) && !(m[2].charAt(0) === '`' && m[3].indexOf('`') >= 0)) {
      var ind = m[1].length, fence = m[2], finfo = m[3].trim(), buf = [];
      var closeRe = new RegExp('^ {0,3}' + fence.charAt(0) + '{' + fence.length + ',}\\s*$');
      i++;
      while (i < n && !closeRe.test(lines[i])) {
        buf.push(ind ? lines[i].replace(new RegExp('^ {0,' + ind + '}'), '') : lines[i]);
        i++;
      }
      i++;
      emit(codeBlock(buf.join('\n'), finfo));
      continue;
    }
    // code indenté
    if (/^ {4}/.test(line)) {
      var cb = [];
      while (i < n && (/^ {4}/.test(lines[i]) || isBlank(lines[i]))) { cb.push(lines[i].replace(/^ {4}/, '')); i++; }
      while (cb.length && isBlank(cb[cb.length - 1])) cb.pop();
      emit(codeBlock(cb.join('\n'), ''));
      continue;
    }
    if ((m = RE_ATX.exec(line))) { emit(heading(m[1].length, m[2] || '')); i++; continue; }
    if (RE_HR.test(line)) { emit('<hr>'); i++; continue; }
    // commentaire HTML
    if (/^ {0,3}<!--/.test(line)) {
      while (i < n && lines[i].indexOf('-->') < 0) i++;
      i++;
      continue;
    }
    // <details> : le contenu est du Markdown
    if (/^ {0,3}<details(?:\s[^>]*)?>/i.test(line)) {
      var depth = 0, j = i, dbuf = [];
      for (; j < n; j++) {
        depth += (lines[j].match(/<details[\s>]/gi) || []).length - (lines[j].match(/<\/details\s*>/gi) || []).length;
        dbuf.push(lines[j]);
        if (depth <= 0) break;
      }
      i = j + 1;
      var raw = dbuf.join('\n'), dm = /^\s*<details((?:\s[^>]*)?)>/i.exec(raw);
      raw = raw.slice(dm[0].length).replace(/<\/details\s*>\s*$/i, '');
      var sm = /^\s*<summary[^>]*>([\s\S]*?)<\/summary>/i.exec(raw), sum = 'Détails';
      if (sm) { sum = ih(sm[1].replace(/\s+/g, ' ').trim()); raw = raw.slice(sm[0].length); }
      emit('<details' + (/\bopen\b/i.test(dm[1]) ? ' open' : '') + '><summary>' + sum + '</summary>' + blocks(raw.split('\n')) + '</details>');
      continue;
    }
    // autres blocs HTML
    if (RE_HTML_BLOCK.test(line)) {
      var tag = /^ {0,3}<([a-z0-9]+)/i.exec(line)[1].toLowerCase();
      var stopBlank = /^(?:p|h[1-6]|a|img|hr|br|picture|figure|center)$/.test(tag);
      var openRe = new RegExp('<' + tag + '[\\s>/]', 'gi'), clRe = new RegExp('</' + tag + '\\s*>', 'gi');
      var hd = 0, hb = [];
      while (i < n) {
        var hl = lines[i];
        hd += (hl.match(openRe) || []).length - (hl.match(clRe) || []).length;
        hb.push(hl);
        i++;
        if ((stopBlank || hd <= 0) && (i >= n || isBlank(lines[i]))) break;
      }
      emit(cleanHtml(hb.join('\n')));
      continue;
    }
    if (RE_QUOTE.test(line)) {
      var qb = [];
      while (i < n && (RE_QUOTE.test(lines[i]) ||
             (!isBlank(lines[i]) && qb.length && !isBlank(qb[qb.length - 1]) && !startsBlock(lines[i])))) {
        qb.push(lines[i].replace(RE_QUOTE, ''));
        i++;
      }
      emit(quote(qb));
      continue;
    }
    if (RE_LIST.test(line) && !RE_HR.test(line)) {
      var pl2 = parseList(lines, i);
      emit(pl2.html);
      i = pl2.next;
      continue;
    }
    if (isTableAt(lines, i)) { var tb = table(lines, i); emit(tb.html); i = tb.next; continue; }
    // paragraphe (ou titre souligné)
    var pl = [], setext = 0;
    while (i < n && !isBlank(lines[i])) {
      if (pl.length) {
        if (/^ {0,3}=+[ \t]*$/.test(lines[i])) { setext = 1; i++; break; }
        if (/^ {0,3}-+[ \t]*$/.test(lines[i])) { setext = 2; i++; break; }
        if (startsBlock(lines[i]) || isTableAt(lines, i)) break;
      }
      pl.push(lines[i].replace(/^ +/, ''));
      i++;
    }
    var text = pl.join('\n').replace(/\s+$/, '');
    if (setext) emit(heading(setext, text.replace(/\n/g, ' ')));
    else emit('\u0003' + ih(text) + '\u0004');
  }
  if (info) info.gap = gap;
  var html = out.join('\n');
  return defer ? html : html.replace(/\u0003/g, '<p>').replace(/\u0004/g, '</p>');
}

/* ---------- Document ---------- */
function prepare(text){
  var lines = [], fence = null, curFn = null, m, fm = '';
  var f = /^---[ \t]*\n([\s\S]*?)\n(?:---|\.\.\.)[ \t]*(?:\n|$)/.exec(text);
  if (f) {
    text = text.slice(f[0].length);
    var rows = '';
    f[1].split('\n').forEach(function(l){
      var kv = /^([\w.-]+):[ \t]*(.*)$/.exec(l);
      if (kv && kv[2]) rows += '<dt>' + esc(kv[1]) + '</dt><dd>' + esc(kv[2].replace(/^["']|["']$/g, '')) + '</dd>';
    });
    if (rows) fm = '<details class="fm"><summary>Métadonnées</summary><dl>' + rows + '</dl></details>';
  }
  text.split('\n').forEach(function(l){
    if (fence) {
      lines.push(l);
      if (new RegExp('^\\s*' + fence.charAt(0) + '{' + fence.length + ',}\\s*$').test(l)) fence = null;
      return;
    }
    if ((m = /^\s*(`{3,}|~{3,})(.*)$/.exec(l)) && !(m[1].charAt(0) === '`' && m[2].indexOf('`') >= 0)) {
      fence = m[1]; curFn = null; lines.push(l); return;
    }
    l = l.replace(/^\t+/, function(t){ return new Array(t.length + 1).join('    '); });
    if ((m = /^ {0,3}\[\^([^\]\s]+)\]:[ \t]?(.*)$/.exec(l))) { curFn = m[1]; fnDefs[curFn] = m[2]; return; }
    if (curFn && /^ {2,}\S/.test(l)) { fnDefs[curFn] += ' ' + l.trim(); return; }
    curFn = null;
    if ((m = /^ {0,3}\[([^\]^][^\]]*)\]:[ \t]*(<[^>]+>|\S+)(?:[ \t]+(?:"([^"]*)"|'([^']*)'|\(([^)]*)\)))?[ \t]*$/.exec(l))) {
      refs[m[1].toLowerCase()] = {u: m[2].replace(/^<|>$/g, ''), t: m[3] || m[4] || m[5] || ''};
      return;
    }
    lines.push(l);
  });
  return {lines: lines, fm: fm};
}
function footnotes(){
  if (!fnOrder.length) return '';
  return '<section class="footnotes"><ol>' + fnOrder.map(function(id){
    return '<li id="fn-' + esc(id) + '">' + ih(fnDefs[id]) + ' <a class="fnback" href="#fnref-' + esc(id) + '" aria-label="Retour au texte">retour</a></li>';
  }).join('') + '</ol></section>';
}

var art = $('md-art'), sc = $('md-scroll'), bar = $('md-bar'), tocNav = $('md-toc'), tocList = $('md-toc-list');
var prep = prepare(src), body = blocks(prep.lines);
art.innerHTML = (body.trim() || prep.fm) ? prep.fm + body + footnotes() : '<p class="empty">Ce fichier est vide.</p>';

/* ---------- Sommaire ---------- */
var tocHeads = heads.filter(function(h){ return h.level <= 4; });
var tocBtn = $('md-toc-btn'), veil = $('md-veil'), wide = window.matchMedia('(min-width:1000px)');
if (tocHeads.length < 2) {
  tocNav.hidden = true;
  tocBtn.hidden = true;
} else {
  var minL = Math.min.apply(null, tocHeads.map(function(h){ return h.level; }));
  tocList.innerHTML = tocHeads.map(function(h){
    return '<a href="#' + esc(h.id) + '" data-id="' + esc(h.id) + '" style="--ind:' + (h.level - minL) + '">' + esc(h.text) + '</a>';
  }).join('');
}
var tocLinks = Array.prototype.slice.call(tocList.querySelectorAll('a'));
var hEls = tocHeads.map(function(h){ return document.getElementById(h.id); });
function syncTocBtn(){
  var on = wide.matches ? !document.body.classList.contains('toc-off') : tocNav.classList.contains('open');
  tocBtn.classList.toggle('on', on);
}
function closeToc(){ tocNav.classList.remove('open'); veil.hidden = true; syncTocBtn(); }
if (store('md-toc') === 'off') document.body.classList.add('toc-off');
syncTocBtn();
tocBtn.addEventListener('click', function(){
  if (wide.matches) {
    var off = document.body.classList.toggle('toc-off');
    store('md-toc', off ? 'off' : 'on');
  } else {
    var open = tocNav.classList.toggle('open');
    veil.hidden = !open;
  }
  syncTocBtn();
});
veil.addEventListener('click', closeToc);
(wide.addEventListener ? wide.addEventListener.bind(wide, 'change') : wide.addListener.bind(wide))(function(){ closeToc(); });

/* ---------- Navigation interne ---------- */
function fold(s){
  return s.toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g, '').replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');
}
function findEl(id){
  try { id = decodeURIComponent(id); } catch(e) {}
  var el = document.getElementById(id);
  if (el && art.contains(el)) return el;
  var key = fold(id);
  for (var i = 0; i < heads.length; i++) if (fold(heads[i].id) === key) return document.getElementById(heads[i].id);
  return null;
}
var reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
function goTo(el, smooth){
  var top = sc.scrollTop + el.getBoundingClientRect().top - sc.getBoundingClientRect().top - 14;
  sc.scrollTo({top: Math.max(0, top), behavior: smooth && !reduce ? 'smooth' : 'auto'});
}
document.addEventListener('click', function(e){
  var a = e.target.closest ? e.target.closest('a[href^="#"]') : null;
  if (!a || e.ctrlKey || e.metaKey || e.shiftKey) return;
  var el = findEl(a.getAttribute('href').slice(1));
  if (!el) return;
  e.preventDefault();
  goTo(el, true);
  try { history.replaceState(null, '', '#' + encodeURIComponent(el.id)); } catch(err) {}
  if (!wide.matches) closeToc();
});

/* ---------- Progression, repère du sommaire, position de lecture ---------- */
var curIdx = -1, ticking = false, saveT = 0, posKey = 'md-pos:' + cfg.q;
function update(){
  ticking = false;
  var max = sc.scrollHeight - sc.clientHeight;
  bar.style.width = (max > 0 ? sc.scrollTop / max * 100 : 100) + '%';
  if (!hEls.length) return;
  var limit = sc.getBoundingClientRect().top + 40, cur = -1, i;
  for (i = 0; i < hEls.length; i++) {
    if (hEls[i].getBoundingClientRect().top <= limit) cur = i; else break;
  }
  if (cur !== curIdx) {
    curIdx = cur;
    tocLinks.forEach(function(a, k){ a.classList.toggle('on', k === cur); });
    var a = tocLinks[cur];
    if (a && tocNav.offsetParent !== null) {
      if (a.offsetTop < tocNav.scrollTop + 40 || a.offsetTop + a.offsetHeight > tocNav.scrollTop + tocNav.clientHeight - 20) {
        tocNav.scrollTop = Math.max(0, a.offsetTop - tocNav.clientHeight / 3);
      }
    }
  }
}
sc.addEventListener('scroll', function(){
  if (!ticking) { ticking = true; requestAnimationFrame(update); }
  clearTimeout(saveT);
  saveT = setTimeout(function(){
    var h = sc.scrollHeight;
    store(posKey, String(h > 0 ? (sc.scrollTop / h).toFixed(4) : 0));
  }, 400);
}, {passive: true});
window.addEventListener('resize', update);

/* ---------- Réglages de lecture ---------- */
var fs = parseInt(store('md-fs') || '18', 10);
if (!(fs >= 14 && fs <= 26)) fs = 18;
function applyFs(){ art.style.setProperty('--mdfs', fs + 'px'); store('md-fs', String(fs)); update(); }
applyFs();
$('md-fs-down').addEventListener('click', function(){ if (fs > 14) { fs--; applyFs(); } });
$('md-fs-up').addEventListener('click', function(){ if (fs < 26) { fs++; applyFs(); } });
var ff = $('md-ff'), sans = store('md-ff') === 'sans';
function applyFf(){ art.classList.toggle('sans', sans); ff.textContent = sans ? 'Sans' : 'Serif'; ff.classList.toggle('on', sans); }
applyFf();
ff.addEventListener('click', function(){ sans = !sans; store('md-ff', sans ? 'sans' : 'serif'); applyFf(); update(); });
$('md-print').addEventListener('click', function(){ window.print(); });

/* ---------- Copie du code, images ---------- */
function copyText(t, cb){
  function legacy(){
    var ta = document.createElement('textarea'), ok = false;
    ta.value = t; ta.setAttribute('readonly', '');
    ta.style.cssText = 'position:fixed;top:0;left:0;opacity:0';
    document.body.appendChild(ta); ta.select();
    try { ok = document.execCommand('copy'); } catch(e) {}
    document.body.removeChild(ta);
    cb(ok);
  }
  if (navigator.clipboard && window.isSecureContext) navigator.clipboard.writeText(t).then(function(){ cb(true); }, legacy);
  else legacy();
}
function lightbox(img){
  var box = document.createElement('div');
  box.className = 'mdbox';
  var big = document.createElement('img');
  big.src = img.src; big.alt = img.alt;
  box.appendChild(big);
  function close(){ box.remove(); document.removeEventListener('keydown', onKey); }
  function onKey(e){ if (e.key === 'Escape') close(); }
  box.addEventListener('click', close);
  document.addEventListener('keydown', onKey);
  document.body.appendChild(box);
}
art.addEventListener('click', function(e){
  var t = e.target, b = t.closest ? t.closest('button.copy') : null;
  if (b) {
    copyText(b.closest('figure').querySelector('code').textContent, function(ok){
      b.textContent = ok ? 'Copié' : 'Échec';
      setTimeout(function(){ b.textContent = 'Copier'; }, 1600);
    });
    return;
  }
  if (t.tagName === 'IMG' && !(t.closest && t.closest('a'))) lightbox(t);
});

/* ---------- Informations, clavier, position initiale ---------- */
(function(){
  var c = art.cloneNode(true), words = 0;
  Array.prototype.forEach.call(c.querySelectorAll('figure.code,.anc'), function(x){ x.remove(); });
  try { words = (c.textContent.match(/[\p{L}\p{N}]+(?:['\u2019-][\p{L}\p{N}]+)*/gu) || []).length; }
  catch(e) { words = (c.textContent.match(/\S+/g) || []).length; }
  var min = Math.max(1, Math.round(words / 220));
  $('md-meta').textContent = 'Aper\u00e7u \u00b7 ' + cfg.label + ' \u00b7 ' + min + ' min de lecture \u00b7 ' + words.toLocaleString('fr-FR') + ' mots';
})();
document.addEventListener('keydown', function(e){
  if (e.ctrlKey || e.metaKey || e.altKey) return;
  var t = e.target && e.target.tagName;
  if (t === 'INPUT' || t === 'TEXTAREA') return;
  if (e.key === 't' && !tocBtn.hidden) tocBtn.click();
  else if (e.key === 'Escape' && tocNav.classList.contains('open')) closeToc();
});
sc.tabIndex = 0;
var start = location.hash.length > 1 ? findEl(location.hash.slice(1)) : null;
if (start) goTo(start, false);
else {
  var saved = parseFloat(store(posKey) || '0');
  if (saved > 0 && saved < 1) sc.scrollTop = saved * sc.scrollHeight;
}
update();
try { sc.focus({preventScroll: true}); } catch(e) {}
})();
"""


def bundle_bytes():
    st = BUNDLE.stat()
    key = st.st_mtime_ns
    if _bundle_cache.get("key") != key:
        raw = BUNDLE.read_bytes()
        _bundle_cache.update(key=key, raw=raw, gz=gzip.compress(raw, 6), v=str(key))
    return _bundle_cache


# --------------------------------------------------------------------------
# Briques HTML
# --------------------------------------------------------------------------
def theme_button(extra=""):
    return (
        f"<button id='theme-toggle' class='ibtn theme-btn {extra}' type='button' "
        "title='Changer de thème' aria-label='Changer de thème'>"
        f"<span class='sun'>{icon('sun', 20)}</span><span class='moon'>{icon('moon', 20)}</span></button>"
    )


def doc_open(title, body_class="", extra_css=""):
    return (
        "<!doctype html><html lang='fr'><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width,initial-scale=1,viewport-fit=cover'>"
        "<meta name='color-scheme' content='light dark'>"
        f"<title>{escape(title)}</title>{FAVICON}{THEME_INIT}<style>{CSS}{extra_css}</style></head>"
        f"<body class='{body_class}'>"
    )


def topbar(with_search, lock=False):
    search = ""
    if with_search:
        search = (f"<label class='search'>{icon('search', 18)}"
                  "<input id='search' type='search' autocomplete='off' "
                  "placeholder='Rechercher dans ce dossier…'></label>")
    lockbtn = "<button id='lock-toggle' class='ibtn' type='button' hidden aria-label='Verrouillage'></button>" if lock else ""
    return (
        "<header class='topbar'><a class='brand' href='/'>"
        f"<span class='logo'>{icon('library', 22)}</span><span>Ma bibliothèque</span></a>"
        f"{search}{theme_button()}{lockbtn}"
        "<a class='ibtn' href='/dashboard' title='Tableau de bord' aria-label='Tableau de bord'>"
        f"{icon('dashboard', 20)}</a></header>"
    )


def folder_url(p_dir):
    rel = p_dir.relative_to(ROOT)
    return "/?folder=" + quote(rel.as_posix(), safe="") if rel.parts else "/"


GROUPS = [("video", "Vidéos"), ("pdf", "Documents PDF"), ("text", "Texte et code"),
          ("web", "Pages web"), ("media", "Images et audio"), ("other", "Autres fichiers")]


def group_of(kind):
    return {"video": "video", "pdf": "pdf", "text": "text", "web": "web",
            "image": "media", "audio": "media", "binary": "other"}[kind]


def media_key(p):
    return escape(f"{ROOT_ID}:{rel_of(p)}", quote=True)


def duration_of(path):
    """Durée en secondes (ffprobe), None si indisponible. Mise en cache."""
    if not FFPROBE:
        return None
    st = path.stat()
    key = (str(path), st.st_mtime_ns, st.st_size)
    if key in _durations:
        return _durations[key]
    value = None
    try:
        out = subprocess.run(
            [FFPROBE, "-v", "error", "-show_entries", "format=duration",
             "-of", "default=nw=1:nk=1", str(path)],
            capture_output=True, text=True, timeout=20)
        value = float(out.stdout.strip())
    except (ValueError, subprocess.SubprocessError, OSError):
        value = None
    _durations[key] = value
    return value


def thumb_for(path):
    """Miniature JPEG en cache (ffmpeg), None si impossible."""
    if not FFMPEG:
        return None
    st = path.stat()
    key = hashlib.sha1(f"{path}|{st.st_mtime_ns}|{st.st_size}".encode()).hexdigest()
    out = CACHE / f"{key}.jpg"
    if out.exists():
        return out
    if key in _failed:
        return None
    with _sem:
        if out.exists():
            return out
        CACHE.mkdir(parents=True, exist_ok=True)
        dur = duration_of(path)
        tries = ([max(dur * 0.1, 1.0)] if dur else []) + [0.0]
        tmp = CACHE / f"{key}.tmp.jpg"
        for ss in tries:
            try:
                subprocess.run(
                    [FFMPEG, "-v", "error", "-y", "-ss", f"{ss:.2f}", "-i", str(path),
                     "-frames:v", "1", "-vf", "scale=480:-2", "-q:v", "5", str(tmp)],
                    capture_output=True, timeout=40)
            except (subprocess.SubprocessError, OSError):
                continue
            if tmp.exists() and tmp.stat().st_size > 0:
                tmp.replace(out)
                return out
        _failed.add(key)
    return None


def _tag(tags, *names):
    low = {str(k).lower(): v for k, v in (tags or {}).items()}
    for n in names:
        v = low.get(n)
        if v is not None and str(v).strip():
            return str(v).strip()
    return ""


def audio_info(path):
    """Durée, titre, artiste, album d'un fichier audio (ffprobe), mis en cache.
    Sans ffprobe ou si le fichier est illisible : valeurs vides, le lecteur se rabat sur le nom du fichier."""
    empty = {"duration": None, "title": "", "artist": "", "album": "", "embedded": False}
    if not FFPROBE:
        return empty
    try:
        st = path.stat()
    except OSError:
        return empty
    key = (str(path), st.st_mtime_ns, st.st_size)
    if key in _ainfo:
        return _ainfo[key]
    info = dict(empty)
    try:
        out = subprocess.run(
            [FFPROBE, "-v", "error", "-print_format", "json", "-show_format", "-show_streams", str(path)],
            capture_output=True, text=True, timeout=20)
        j = json.loads(out.stdout or "{}")
    except (ValueError, subprocess.SubprocessError, OSError):
        j = {}
    fmt = j.get("format") or {}
    try:
        d = float(fmt.get("duration"))
        info["duration"] = d if d > 0 else None
    except (TypeError, ValueError):
        pass
    tags = dict(fmt.get("tags") or {})
    for stream in j.get("streams") or []:
        if stream.get("codec_type") == "audio":
            for k, v in (stream.get("tags") or {}).items():     # ogg / opus : tags portés par le flux
                tags.setdefault(k, v)
        elif stream.get("codec_type") == "video" and (stream.get("disposition") or {}).get("attached_pic"):
            info["embedded"] = True
    info["title"] = _tag(tags, "title")
    info["artist"] = _tag(tags, "artist", "album_artist", "albumartist")
    info["album"] = _tag(tags, "album")
    if len(_ainfo) > 5000:
        _ainfo.clear()
    _ainfo[key] = info
    return info


def folder_cover(directory):
    """cover.jpg, folder.png, front.webp… présent dans le dossier de la piste."""
    try:
        for f in sorted(directory.iterdir(), key=lambda x: x.name.lower()):
            if f.suffix.lower() in COVER_EXT and f.stem.lower() in COVER_NAMES and f.is_file():
                return f
    except OSError:
        pass
    return None


def has_cover(path, info):
    return bool((info["embedded"] and FFMPEG) or folder_cover(path.parent))


def cover_for(path):
    """Pochette d'une piste : image intégrée aux tags (ffmpeg, JPEG en cache), sinon image du dossier."""
    info = audio_info(path)
    if info["embedded"] and FFMPEG:
        st = path.stat()
        key = hashlib.sha1(f"cover|{path}|{st.st_mtime_ns}|{st.st_size}".encode()).hexdigest()
        out = CACHE / f"{key}.jpg"
        if out.exists():
            return out
        if key not in _failed:
            with _sem:
                if out.exists():
                    return out
                CACHE.mkdir(parents=True, exist_ok=True)
                tmp = CACHE / f"{key}.tmp.jpg"
                try:
                    subprocess.run(
                        [FFMPEG, "-v", "error", "-y", "-i", str(path), "-an", "-map", "0:v:0", "-frames:v", "1",
                         "-vf", "scale='min(640,iw)':-2", "-q:v", "4", str(tmp)],
                        capture_output=True, timeout=40)
                except (subprocess.SubprocessError, OSError):
                    pass
                if tmp.exists() and tmp.stat().st_size > 0:
                    tmp.replace(out)
                    return out
                _failed.add(key)
    return folder_cover(path.parent)


def find_subtitles(video):
    subs = []
    stem = video.stem.casefold() + "."
    try:
        for f in sorted(video.parent.iterdir(), key=natural_key):
            if f.suffix.lower() in SUB_TYPES and f.name.casefold().startswith(stem) and f.is_file():
                subs.append((f, f.stem[len(video.stem) + 1:]))
    except OSError:
        pass
    return subs


def srt_to_vtt(text):
    text = text.replace("\r\n", "\n").replace("\r", "\n").lstrip("\ufeff")
    if text.startswith("WEBVTT"):
        return text
    text = re.sub(r"(\d{2}:\d{2}:\d{2}),(\d{3})", r"\1.\2", text)
    return "WEBVTT\n\n" + text


def file_card(p, kind):
    ic, cls = icon_for(p, kind)
    if kind == "pdf":
        cls = "pdf"
    q = quote(rel_of(p), safe="")
    try:
        size = fmt_size(p.stat().st_size)
    except OSError:
        size = ""
    href = {"text": f"/view?f={q}", "web": f"/view?f={q}", "pdf": f"/pdf?f={q}",
            "image": f"/raw?f={q}", "audio": f"/listen?f={q}", "binary": f"/raw?dl=1&f={q}"}[kind]
    direct = kind in ("pdf", "image", "audio", "binary")
    dot = " dot" if p.name.startswith(".") else ""
    md = " data-md='1'" if p.suffix.lower() in MD_EXT else ""
    ext = p.suffix[1:].upper() if p.suffix else "FICHIER"
    if kind in ("pdf", "image", "audio"):
        right = f"<button class='more' type='button' aria-label='Plus d’actions'>{icon('more', 18)}</button>"
    else:
        right = f"<span class='go'>{icon('chevron', 18)}</span>"
    return (
        f"<a class='item fcard{dot}' href='{href}' data-f='{q}' data-kind='{kind}'{md} "
        f"data-direct='{1 if direct else 0}' data-ico='{ic}' data-icls='{cls}' "
        f"data-title='{escape(p.name, quote=True)}' data-size='{size} · {ext}' "
        f"data-name='{escape(p.name.casefold(), quote=True)}'>"
        f"<span class='ico {cls}'>{icon(ic, 22)}</span>"
        f"<span class='text'><span class='name'>{escape(p.name)}</span>"
        f"<div class='sub'>{size} · {ext}</div></span>{right}</a>"
    )


def video_card(p):
    q = quote(rel_of(p), safe="")
    try:
        size = fmt_size(p.stat().st_size)
    except OSError:
        size = ""
    dot = " dot" if p.name.startswith(".") else ""
    ext = p.suffix[1:].upper()
    return (
        f"<a class='vcard fcard{dot}' href='/watch?f={q}' data-f='{q}' data-key='{media_key(p)}' "
        f"data-kind='video' data-direct='1' data-ico='film' data-icls='media' "
        f"data-title='{escape(p.name, quote=True)}' data-size='{size} · {ext}' "
        f"data-name='{escape(p.name.casefold(), quote=True)}'>"
        f"<div class='thumb'><span class='ph'>{icon('film', 36)}</span>"
        f"<img loading='lazy' alt='' src='/thumb?f={q}' onerror='this.remove()'>"
        f"<span class='play'>{icon('play', 22)}</span>"
        "<span class='dur' hidden></span><span class='bar' hidden><i></i></span>"
        f"<button class='more' type='button' aria-label='Plus d’actions'>{icon('more', 18)}</button></div>"
        f"<div class='vinfo'><div class='vname'>{escape(p.stem)}</div>"
        f"<div class='vsub'>{size} · {ext}</div></div></a>"
    )


def video_row(p, current):
    q = quote(rel_of(p), safe="")
    try:
        size = fmt_size(p.stat().st_size)
    except OSError:
        size = ""
    cur = " cur" if p == current else ""
    sub = "En lecture" if p == current else size
    return (
        f"<a class='row{cur}' href='/watch?f={q}' data-f='{q}' data-key='{media_key(p)}'>"
        f"<div class='rthumb'><span class='ph'>{icon('film', 24)}</span>"
        f"<img loading='lazy' alt='' src='/thumb?f={q}' onerror='this.remove()'>"
        "<span class='dur' hidden></span><span class='bar' hidden><i></i></span></div>"
        f"<div class='rinfo'><div class='rname'>{escape(p.stem)}</div>"
        f"<div class='rsub'>{sub}</div></div></a>"
    )


def message_page(title, text, actions=""):
    return (
        doc_open(title) + topbar(False)
        + f"<main><div class='msgcard'><h1>{escape(title)}</h1><p>{escape(text)}</p>{actions}</div></main>"
        + f"<script>{THEME_JS}</script></body></html>"
    )


DASH_CSS = """
.dash-head{display:flex; align-items:center; justify-content:space-between; gap:12px; flex-wrap:wrap}
.dash-title{margin:0; font-size:24px; letter-spacing:-.01em}
.stats{display:grid; gap:12px; grid-template-columns:repeat(auto-fit,minmax(150px,1fr))}
.stats.disks{grid-template-columns:repeat(auto-fit,minmax(250px,1fr))}
.stat{padding:14px 16px; border-radius:14px; background:var(--surface); border:1px solid var(--border); box-shadow:var(--shadow)}
.stat .label{font-size:12.5px; font-weight:600; color:var(--muted)}
.stat .value{margin-top:4px; font-size:24px; font-weight:700; letter-spacing:-.01em}
.stat .meter{margin-top:10px}
.meter{height:10px; margin-top:14px; border-radius:99px; background:var(--bg-2); overflow:hidden}
.meter span{display:block; height:100%; width:0; border-radius:99px; background:var(--green); transition:width .4s,background .3s}
.meter span.warn{background:var(--orange)}
.meter span.crit{background:var(--red)}
.dev{display:flex; flex-wrap:wrap; align-items:center; gap:14px; padding:12px 14px; border-radius:14px; background:var(--surface); border:1px solid var(--border); box-shadow:var(--shadow)}
.dev.blocked{border-color:var(--red); background:var(--red-soft)}
.dev .text{flex:1; min-width:160px; overflow-wrap:anywhere}
.dev-actions{display:flex; flex-wrap:wrap; gap:8px}
.dev .ico.danger{background:var(--red-soft); color:var(--red)}
.dev-top{display:flex; flex-wrap:wrap; align-items:center; gap:8px}
.ip{font:600 15px ui-monospace,SFMono-Regular,Menlo,Consolas,monospace}
.tag{font-size:11.5px; font-weight:600; padding:1px 8px; border-radius:99px; background:var(--gray-soft); color:var(--muted)}
.tag.me{background:var(--accent-soft); color:var(--accent)}
.tag.bad{background:var(--red-soft); color:var(--red)}
.pill.danger{color:var(--red); border-color:var(--red)}
.pill.danger:hover{background:var(--red-soft); color:var(--red)}
.hbar{display:flex; flex-wrap:wrap; gap:10px; margin:12px 0 0}
.hbar select{max-width:100%; padding:7px 14px; font:inherit; font-size:14px; color:var(--text); background:var(--surface); border:1px solid var(--border); border-radius:99px}
.hcard{margin-top:12px; padding:14px 16px; border-radius:14px; background:var(--surface); border:1px solid var(--border); box-shadow:var(--shadow)}
.hcard h3{margin:0 0 10px; font-size:14px; font-weight:700}
.chart{display:block; width:100%; height:auto}
.chart .grid{stroke:var(--border); stroke-width:1}
.chart .axis{fill:var(--muted); font-size:10px}
.chart .area{fill-opacity:.88}
.chart .cursor{stroke:var(--text); stroke-width:1; stroke-dasharray:3 3; visibility:hidden}
.chart .hit{fill:transparent; touch-action:pan-y}
.h-read{min-height:20px; margin-top:6px}
.h-legend{display:flex; flex-wrap:wrap; gap:6px 14px; margin-top:10px; font-size:13px}
.sw{display:inline-block; width:10px; height:10px; margin-right:6px; border-radius:3px; vertical-align:-1px}
.h-grid{display:grid; gap:12px; grid-template-columns:repeat(auto-fit,minmax(260px,1fr))}
.h-grid .hcard{margin-top:12px}
.donut{display:block; width:150px; height:150px; margin:0 auto}
.donut .ring{fill:none; stroke:var(--bg-2); stroke-width:5}
.donut .seg{fill:none; stroke-width:5}
.donut .dtot{fill:var(--text); font-size:5px; font-weight:700}
.share{display:grid; gap:4px; margin-top:12px; font-size:13px}
.share div{display:flex; justify-content:space-between; gap:10px}
.top-row{margin:10px 0}
.top-row .name{font-weight:600; overflow-wrap:anywhere}
.top-row .bar{height:6px; margin-top:6px; border-radius:99px; background:var(--bg-2); overflow:hidden}
.top-row .bar span{display:block; height:100%; border-radius:99px}
.h-list{max-height:380px; overflow:auto}
.h-item{display:grid; grid-template-columns:auto 1fr; gap:2px 12px; padding:8px 0; border-top:1px solid var(--border); font-size:13px}
.h-item:first-child{border-top:0}
.h-item .when{color:var(--muted); white-space:nowrap}
.h-item .what{overflow-wrap:anywhere}
.h-item .meta{grid-column:2; color:var(--muted); font-size:12px}
.dash-login .ico{margin:0 auto 12px; width:56px; height:56px; border-radius:16px}
.dash-login form{display:flex; flex-wrap:wrap; justify-content:center; gap:10px; margin-top:16px}
.dash-login input{
  flex:1 1 220px; max-width:320px; padding:10px 16px; font:inherit; font-size:15px; color:var(--text);
  background:var(--bg); border:1px solid var(--border); border-radius:99px; outline:none;
}
.dash-login input:focus{border-color:var(--accent); box-shadow:0 0 0 3px var(--accent-soft)}
.dash-login .pill{margin:0}
.dash-err{margin:12px 0 0; color:var(--red)}
"""

DASH_JS = """
(function(){
  var H = {'X-Requested-With': 'biblio'};
  var I = window.DCFG || {};
  var $ = function(id){ return document.getElementById(id); };
  function el(tag, cls, text){
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text !== undefined && text !== null) e.textContent = text;
    return e;
  }
  function pct(p){ return String(p).replace('.', ','); }
  function ago(s){
    if (s === null) return 'pas vu depuis le démarrage';
    if (s < 5) return "à l'instant";
    if (s < 60) return 'il y a ' + s + ' s';
    if (s < 3600) return 'il y a ' + Math.floor(s / 60) + ' min';
    if (s < 86400) return 'il y a ' + Math.floor(s / 3600) + ' h';
    return 'il y a ' + Math.floor(s / 86400) + ' j';
  }
  function fmtBytes(n){
    var u = [['Go', 1073741824], ['Mo', 1048576], ['Ko', 1024]];
    for (var i = 0; i < u.length; i++) {
      if (n >= u[i][1]) {
        var v = n / u[i][1];
        return (v < 10 ? v.toFixed(1) : String(Math.round(v))).replace('.', ',') + ' ' + u[i][0];
      }
    }
    return Math.round(n) + ' o';
  }
  function fmtDur(s){
    s = Math.round(s);
    if (s < 60) return s + ' s';
    var m = Math.floor(s / 60);
    if (m < 60) return m + ' min';
    var h = Math.floor(m / 60);
    m = m % 60;
    return h + ' h' + (m ? ' ' + ('0' + m).slice(-2) : '');
  }
  function fmtMetric(v, metric){
    return metric === 'bytes' ? fmtBytes(v) : (metric === 'seconds' ? fmtDur(v) : String(Math.round(v)));
  }
  function niceFor(v, metric){
    if (!(v > 0)) return metric === 'actions' ? 4 : 1;
    if (metric === 'actions') return Math.max(4, Math.ceil(v / 4) * 4);
    var div = 1;
    if (metric === 'bytes') div = v >= 1073741824 ? 1073741824 : (v >= 1048576 ? 1048576 : (v >= 1024 ? 1024 : 1));
    else div = v >= 3600 ? 3600 : (v >= 60 ? 60 : 1);
    var x = v / div, p = Math.pow(10, Math.floor(Math.log(x) / Math.LN10)), m = x / p;
    return (m <= 1 ? 1 : (m <= 2 ? 2 : (m <= 5 ? 5 : 10))) * p * div;
  }
  function f1(x){ return x.toFixed(1); }

  /* ---------- appareils ---------- */
  function act(ip, block){
    if (block && !confirm('Bloquer ' + ip + ' ? Cet appareil n\\'aura plus accès à la bibliothèque.')) return;
    fetch('/dashboard/' + (block ? 'block' : 'unblock') + '?ip=' + encodeURIComponent(ip), {
      method: 'POST', headers: H, credentials: 'same-origin'
    })
      .then(function(r){ return r.json().then(function(j){ return {status: r.status, j: j}; }); })
      .then(function(x){
        if (x.status === 401) { location.reload(); return; }
        if (!x.j.ok) alert(x.j.error || 'Erreur');
        else if (x.j.warning) alert(x.j.warning);
        busy = false; load();
      })
      .catch(function(){ alert('Connexion impossible.'); });
  }
  function row(v){
    var r = el('div', 'dev' + (v.blocked ? ' blocked' : ''));
    var ic = el('div', 'ico ' + (v.blocked ? 'danger' : 'code'));
    ic.innerHTML = v.blocked ? I.ban : I.monitor;
    var t = el('div', 'text');
    var top = el('div', 'dev-top');
    top.appendChild(el('span', 'ip', v.ip));
    if (v.me) top.appendChild(el('span', 'tag me', 'Cet appareil'));
    else if (v.local) top.appendChild(el('span', 'tag me', 'Serveur'));
    if (v.blocked) top.appendChild(el('span', 'tag bad', 'Bloqué'));
    else if (v.ago !== null && !v.auth) {
      var w = el('span', 'tag bad', 'Sans jeton');
      w.title = "N'a jamais présenté le jeton d'accès";
      top.appendChild(w);
    }
    var bits = [];
    if (v.ua) bits.push(v.ua);
    if (v.mac) bits.push('MAC ' + v.mac);
    bits.push(ago(v.ago));
    if (v.hits) bits.push(v.hits + (v.hits > 1 ? ' requêtes' : ' requête'));
    t.appendChild(top);
    t.appendChild(el('div', 'sub', bits.join(' · ')));
    r.appendChild(ic);
    r.appendChild(t);
    var acts = el('div', 'dev-actions');
    var hb = el('button', 'pill', 'Historique');
    hb.type = 'button';
    hb.addEventListener('click', function(){ openHistory(v.ip); });
    acts.appendChild(hb);
    if (!v.me && !v.local) {
      var b = el('button', 'pill' + (v.blocked ? '' : ' danger'), v.blocked ? 'Débloquer' : 'Bloquer');
      b.type = 'button';
      b.addEventListener('click', function(){ act(v.ip, !v.blocked); });
      acts.appendChild(b);
    }
    r.appendChild(acts);
    return r;
  }

  /* ---------- mémoire et stockage ---------- */
  function meterClass(p){ return p >= 90 ? 'crit' : (p >= 70 ? 'warn' : ''); }
  function memory(m){
    $('mem').hidden = !m;
    $('mem-na').hidden = !!m;
    if (!m) return;
    $('m-used').textContent = m.used_h;
    $('m-free').textContent = m.free_h;
    $('m-total').textContent = m.total_h;
    var bar = $('meter-bar');
    bar.style.width = m.percent + '%';
    bar.className = meterClass(m.percent);
    $('m-pct').textContent = pct(m.percent) + ' % utilisée · libre = mémoire disponible (cache récupérable inclus)';
  }
  function disks(list){
    var box = $('disks');
    box.textContent = '';
    $('disks-sec').hidden = !list.length;
    list.forEach(function(k){
      var c = el('div', 'stat');
      var head = el('div', 'dev-top');
      head.appendChild(el('span', 'label', k.label));
      head.appendChild(el('span', 'tag', k.path));
      if (k.system) {
        var w = el('span', 'tag bad', 'Même volume que le système');
        w.title = 'Ce chemin ne semble pas être un disque monté séparément';
        head.appendChild(w);
      }
      c.appendChild(head);
      if (k.error) {
        c.appendChild(el('div', 'sub', k.error));
      } else {
        c.appendChild(el('div', 'value', k.free_h + ' libres'));
        var m = el('div', 'meter');
        var s = el('span', meterClass(k.percent));
        s.style.width = k.percent + '%';
        m.appendChild(s);
        c.appendChild(m);
        c.appendChild(el('div', 'sub', k.used_h + ' utilisés sur ' + k.total_h + ' (' + pct(k.percent) + ' %)'));
      }
      box.appendChild(c);
    });
  }

  /* ---------- historique et analyse ---------- */
  var hsel = $('h-dev'), hrange = $('h-range'), hmetric = $('h-metric');
  var hdata = null, hseq = 0, devKey = '';
  function catOf(id){
    for (var i = 0; i < I.cats.length; i++) if (I.cats[i].id === id) return I.cats[i];
    return {id: id, label: id, color: 'var(--muted)'};
  }
  function syncDevices(list){
    var key = list.map(function(v){ return v.ip; }).join(',');
    if (key === devKey) return;
    devKey = key;
    var cur = hsel.value;
    hsel.textContent = '';
    var o = el('option', null, 'Tous les appareils');
    o.value = 'all';
    hsel.appendChild(o);
    list.forEach(function(v){
      var op = el('option', null, v.ip + (v.ua ? ' · ' + v.ua : '') + (v.me ? ' (cet appareil)' : ''));
      op.value = v.ip;
      hsel.appendChild(op);
    });
    hsel.value = cur;
    if (!hsel.value) hsel.value = 'all';
  }
  function openHistory(ip){
    hsel.value = ip;
    if (!hsel.value) hsel.value = 'all';
    loadHistory();
    $('hist').scrollIntoView({behavior: 'smooth'});
  }
  function loadHistory(){
    var my = ++hseq;
    fetch('/dashboard/history?ip=' + encodeURIComponent(hsel.value || 'all') + '&range=' + hrange.value,
          {credentials: 'same-origin', cache: 'no-store'})
      .then(function(r){
        if (r.status === 401) { location.reload(); return null; }
        return r.json();
      })
      .then(function(d){ if (d && d.ok && my === hseq) { hdata = d; drawHistory(); } })
      .catch(function(){});
  }
  function timeLabel(t, long){
    var d = new Date(t * 1000);
    if (long) return d.toLocaleString('fr-FR', {weekday: 'short', day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit'});
    if (hdata && hdata.range === '24h') return d.toLocaleTimeString('fr-FR', {hour: '2-digit', minute: '2-digit'});
    return d.toLocaleDateString('fr-FR', {day: 'numeric', month: 'short'});
  }
  function curve(cats, d, metric){
    var n = d.n, W = 640, Hh = 220, L = 50, R = 8, T = 10, B = 24, pw = W - L - R, ph = Hh - T - B, i;
    var tot = [];
    for (i = 0; i < n; i++) tot.push(0);
    cats.forEach(function(c){ d.series[c.id][metric].forEach(function(v, k){ tot[k] += v; }); });
    var max = niceFor(Math.max.apply(null, tot), metric);
    var x = function(k){ return L + (n > 1 ? k * pw / (n - 1) : pw / 2); };
    var y = function(v){ return T + ph - v / max * ph; };
    var out = '<svg viewBox="0 0 ' + W + ' ' + Hh + '" class="chart" role="img" aria-label="Courbe d activité">';
    for (var g = 0; g <= 4; g++) {
      var gy = y(max * g / 4);
      out += '<line class="grid" x1="' + L + '" x2="' + (W - R) + '" y1="' + f1(gy) + '" y2="' + f1(gy) + '"/>'
           + '<text class="axis" x="' + (L - 6) + '" y="' + f1(gy + 3.5) + '" text-anchor="end">' + fmtMetric(max * g / 4, metric) + '</text>';
    }
    var base = [];
    for (i = 0; i < n; i++) base.push(0);
    cats.forEach(function(c){
      var vals = d.series[c.id][metric], up = [], p, k;
      for (k = 0; k < n; k++) up.push(base[k] + vals[k]);
      p = 'M' + f1(x(0)) + ' ' + f1(y(base[0]));
      for (k = 0; k < n; k++) p += ' L' + f1(x(k)) + ' ' + f1(y(up[k]));
      for (k = n - 1; k >= 0; k--) p += ' L' + f1(x(k)) + ' ' + f1(y(base[k]));
      out += '<path class="area" d="' + p + 'Z" style="fill:' + c.color + '"/>';
      base = up;
    });
    [0, 0.25, 0.5, 0.75, 1].forEach(function(f, k){
      var idx = Math.round(f * (n - 1));
      out += '<text class="axis" x="' + f1(x(idx)) + '" y="' + (Hh - 6) + '" text-anchor="'
           + (k === 0 ? 'start' : (k === 4 ? 'end' : 'middle')) + '">' + timeLabel(d.start + idx * d.step, false) + '</text>';
    });
    out += '<line class="cursor" x1="0" x2="0" y1="' + T + '" y2="' + (T + ph) + '"/>'
         + '<rect class="hit" x="' + L + '" y="' + T + '" width="' + pw + '" height="' + ph + '"/></svg>';
    var box = $('h-curve');
    box.innerHTML = out;
    var svg = box.firstChild, cur = svg.querySelector('.cursor'), hit = svg.querySelector('.hit');
    function at(ev){
      var r = svg.getBoundingClientRect();
      var px = (ev.clientX - r.left) / r.width * W;
      var k = Math.max(0, Math.min(n - 1, Math.round((px - L) / pw * (n - 1))));
      cur.setAttribute('x1', f1(x(k)));
      cur.setAttribute('x2', f1(x(k)));
      cur.style.visibility = 'visible';
      var parts = [];
      cats.forEach(function(c){
        var v = d.series[c.id][metric][k];
        if (v) parts.push(c.label + ' ' + fmtMetric(v, metric));
      });
      $('h-read').textContent = timeLabel(d.start + k * d.step, true) + ' : ' + (parts.length ? parts.join(' · ') : 'aucune activité');
    }
    hit.addEventListener('pointermove', at);
    hit.addEventListener('pointerdown', at);
    $('h-read').textContent = 'Touche ou survole la courbe pour le détail.';
    var lg = $('h-legend');
    lg.textContent = '';
    cats.forEach(function(c){
      var s = el('span', null, c.label + ' ');
      var sw = el('span', 'sw');
      sw.style.background = c.color;
      s.insertBefore(sw, s.firstChild);
      s.appendChild(el('b', null, fmtMetric(d.totals[c.id][metric], metric)));
      lg.appendChild(s);
    });
  }
  function donut(cats, d, metric){
    var tot = 0;
    cats.forEach(function(c){ tot += d.totals[c.id][metric]; });
    var out = '<svg viewBox="0 0 42 42" class="donut" role="img" aria-label="Répartition par catégorie">'
            + '<circle cx="21" cy="21" r="15.9155" class="ring"/>';
    var off = 25;
    var share = $('h-share');
    share.textContent = '';
    cats.forEach(function(c){
      var v = d.totals[c.id][metric];
      if (!v || !tot) return;
      var p = v / tot * 100;
      out += '<circle cx="21" cy="21" r="15.9155" class="seg" style="stroke:' + c.color + '" stroke-dasharray="'
           + p.toFixed(2) + ' ' + (100 - p).toFixed(2) + '" stroke-dashoffset="' + off.toFixed(2) + '"/>';
      off -= p;
      var line = el('div');
      var left = el('span', null, c.label);
      var sw = el('span', 'sw');
      sw.style.background = c.color;
      left.insertBefore(sw, left.firstChild);
      line.appendChild(left);
      line.appendChild(el('b', null, Math.round(p) + ' %'));
      share.appendChild(line);
    });
    out += '<text x="21" y="22.8" text-anchor="middle" class="dtot">' + fmtMetric(tot, metric) + '</text></svg>';
    $('h-donut').innerHTML = out;
  }
  function topFiles(d){
    var box = $('h-top');
    box.textContent = '';
    if (!d.top.length) { box.appendChild(el('div', 'sub', 'Aucun fichier consulté.')); return; }
    var max = d.top[0].n;
    d.top.forEach(function(t){
      var c = catOf(t.cat);
      var r = el('div', 'top-row');
      r.appendChild(el('div', 'name', t.file));
      var bits = [c.label, t.n + ' fois'];
      if (t.seconds >= 5) bits.push(fmtDur(t.seconds));
      if (t.bytes) bits.push(fmtBytes(t.bytes));
      r.appendChild(el('div', 'sub', bits.join(' · ')));
      var bar = el('div', 'bar');
      var s = el('span');
      s.style.width = Math.max(4, t.n / max * 100) + '%';
      s.style.background = c.color;
      bar.appendChild(s);
      r.appendChild(bar);
      box.appendChild(r);
    });
  }
  function recent(d){
    var box = $('h-list');
    box.textContent = '';
    d.recent.forEach(function(e){
      var c = catOf(e.cat);
      var r = el('div', 'h-item');
      r.appendChild(el('span', 'when', timeLabel(e.t, true)));
      var what = el('span', 'what');
      var sw = el('span', 'sw');
      sw.style.background = c.color;
      what.appendChild(sw);
      what.appendChild(document.createTextNode(c.label + ' · ' + (e.file || '/')));
      r.appendChild(what);
      var bits = [];
      if (e.end - e.t >= 5) bits.push(fmtDur(e.end - e.t));
      if (e.bytes) bits.push(fmtBytes(e.bytes));
      if (d.ip === 'all') bits.push(e.ip);
      if (bits.length) r.appendChild(el('span', 'meta', bits.join(' · ')));
      box.appendChild(r);
    });
  }
  function drawHistory(){
    var d = hdata, metric = hmetric.value;
    var cats = I.cats.filter(function(c){ return d.series[c.id]; });
    $('h-empty').hidden = cats.length > 0;
    $('h-body').hidden = cats.length === 0;
    if (!cats.length) return;
    curve(cats, d, metric);
    donut(cats, d, metric);
    topFiles(d);
    recent(d);
  }

  /* ---------- actualisation ---------- */
  function render(d){
    $('host').textContent = d.host;
    memory(d.memory);
    disks(d.disks || []);
    $('n-active').textContent = d.active;
    $('dev-sub').textContent = d.active + (d.active > 1 ? ' appareils connectés' : ' appareil connecté')
      + ' (activité depuis moins de ' + Math.round(d.window / 60) + ' min) · ' + d.blocked
      + (d.blocked > 1 ? ' bloqués' : ' bloqué');
    var list = $('devices');
    list.textContent = '';
    d.devices.forEach(function(v){ list.appendChild(row(v)); });
    if (!d.devices.length) list.appendChild(el('div', 'empty', 'Aucun appareil pour le moment.'));
    syncDevices(d.devices);
  }
  var busy = false;
  function load(){
    if (busy) return;
    busy = true;
    fetch('/dashboard/data', {credentials: 'same-origin', cache: 'no-store'})
      .then(function(r){
        if (r.status === 401) { location.reload(); return null; }
        return r.json();
      })
      .then(function(d){
        if (d && d.ok) {
          render(d);
          $('upd').textContent = 'mis à jour à ' + new Date().toLocaleTimeString('fr-FR');
        }
      })
      .catch(function(){ $('upd').textContent = 'connexion perdue, nouvel essai…'; })
      .then(function(){ busy = false; });
  }
  $('lock').addEventListener('click', function(){
    fetch('/lock', {method: 'POST', headers: H, credentials: 'same-origin'})
      .then(function(){ location.reload(); });
  });
  hsel.addEventListener('change', loadHistory);
  hrange.addEventListener('change', loadHistory);
  hmetric.addEventListener('change', function(){ if (hdata) drawHistory(); });
  document.addEventListener('visibilitychange', function(){ if (!document.hidden) { load(); loadHistory(); } });
  setInterval(function(){ if (!document.hidden) load(); }, 3000);
  setInterval(function(){ if (!document.hidden) loadHistory(); }, 15000);
  load();
  loadHistory();
})();
"""


def dashboard_page(unlocked):
    parts = [doc_open("Tableau de bord — Ma bibliothèque", "", DASH_CSS), topbar(False, True)]
    if not unlocked:
        return locked_page("Le tableau de bord", "dash", None, "Tableau de bord — Ma bibliothèque", DASH_CSS, True)
    cfg = {"monitor": icon("monitor", 22), "ban": icon("ban", 22),
           "cats": [{"id": i, "label": label, "color": color} for i, label, color in ACTIVITY_CATS]}
    parts.append(
        "<main class='dash'>"
        "<div class='dash-head'><div><h1 class='dash-title'>Tableau de bord</h1>"
        "<div class='sub'>Appareil : <strong id='host'>…</strong> · <span id='upd'>chargement…</span></div></div>"
        f"<button id='lock' class='pill' type='button'>{icon('lock', 16)}Verrouiller</button></div>"
        "<section class='section'><h2>Mémoire</h2>"
        "<div id='mem'><div class='stats'>"
        "<div class='stat'><div class='label'>Utilisée</div><div class='value' id='m-used'>–</div></div>"
        "<div class='stat'><div class='label'>Libre</div><div class='value' id='m-free'>–</div></div>"
        "<div class='stat'><div class='label'>Totale</div><div class='value' id='m-total'>–</div></div></div>"
        "<div class='meter'><span id='meter-bar'></span></div><div class='sub' id='m-pct'></div></div>"
        "<div class='empty' id='mem-na' hidden>Mémoire indisponible sur ce système.</div></section>"
        "<section class='section' id='disks-sec' hidden><h2>Stockage</h2><div class='stats disks' id='disks'></div></section>"
        "<section class='section'><h2>Appareils connectés <span class='count' id='n-active'>0</span></h2>"
        "<div class='sub' id='dev-sub'></div><div class='list' id='devices' style='margin-top:12px'></div></section>"
        "<section class='section' id='hist'><h2>Historique et analyse</h2>"
        "<div class='hbar'>"
        "<select id='h-dev' aria-label='Appareil'><option value='all'>Tous les appareils</option></select>"
        "<select id='h-range' aria-label='Période'><option value='24h'>24 heures</option>"
        "<option value='7d'>7 jours</option><option value='30d'>30 jours</option></select>"
        "<select id='h-metric' aria-label='Mesure'><option value='actions'>Actions</option>"
        "<option value='seconds'>Durée d'activité</option><option value='bytes'>Données transférées</option></select></div>"
        "<div class='empty' id='h-empty' hidden>Aucune activité enregistrée sur cette période.</div>"
        "<div id='h-body' hidden>"
        "<div class='hcard'><h3>Activité dans le temps</h3><div id='h-curve'></div>"
        "<div class='sub h-read' id='h-read'></div><div class='h-legend' id='h-legend'></div></div>"
        "<div class='h-grid'>"
        "<div class='hcard'><h3>Répartition</h3><div id='h-donut'></div><div class='share' id='h-share'></div></div>"
        "<div class='hcard'><h3>Fichiers les plus consultés</h3><div id='h-top'></div></div></div>"
        "<div class='hcard'><h3>Historique des actions</h3><div class='h-list' id='h-list'></div></div></div>"
        "</section></main>"
        f"<script>window.DCFG = {js_json(cfg)}; {THEME_JS}{DASH_JS}</script>{lock_script('dash')}</body></html>")
    return "".join(parts)


LISTEN_CSS = """
.listen{max-width:1100px; margin:0 auto; padding:16px 16px 56px; display:grid; gap:20px 28px; grid-template-columns:minmax(0,1fr); align-items:start}
@media(min-width:900px){
  .listen{grid-template-columns:minmax(0,420px) minmax(0,1fr)}
  .lplayer{position:sticky; top:calc(var(--tb) + 16px)}
}
.lplayer{padding:20px; border-radius:20px; background:var(--surface); border:1px solid var(--border); box-shadow:var(--shadow)}

/* pochette : image des tags / du dossier, sinon icône */
.cover{position:relative; overflow:hidden; display:grid; place-items:center; width:min(60vw,240px); aspect-ratio:1; margin:0 auto 18px; border-radius:24px; color:var(--pink); background:linear-gradient(145deg,var(--pink-soft,var(--accent-soft)),var(--accent-soft)); box-shadow:var(--shadow)}
.cover img{position:absolute; inset:0; width:100%; height:100%; object-fit:cover}
.cover.has-img .cover-ico{visibility:hidden}
.cover.playing:not(.has-img) .cover-ico svg{animation:lpulse 2.4s ease-in-out infinite}
@keyframes lpulse{50%{transform:scale(1.08)}}

.ltitle{text-align:center}
.ltitle h1{margin:0 0 4px; font-size:20px; line-height:1.3; overflow-wrap:anywhere}
.lartist{margin:0 0 10px; font-size:14px; color:var(--muted); overflow-wrap:anywhere}
.lmeta{display:flex; align-items:center; justify-content:center; flex-wrap:wrap; gap:8px; margin-top:8px}
.lmeta .sub{margin:0}

/* curseurs (position et volume) : remplissage de progression, plage déjà en mémoire tampon */
.seek{display:flex; align-items:center; gap:10px; margin-top:18px}
.seek input{flex:1; min-width:0}
.time{font-size:12.5px; color:var(--muted); font-variant-numeric:tabular-nums; min-width:42px; text-align:center}
.rng{-webkit-appearance:none; appearance:none; height:28px; margin:0; padding:0; background:transparent; cursor:pointer; --p:0%; --b:0%}
.rng:focus{outline:none}
.rng::-webkit-slider-runnable-track{height:6px; border-radius:99px; background:linear-gradient(to right,var(--accent) 0 var(--p),var(--sel) var(--p) var(--b),var(--bg-2) var(--b) 100%)}
.rng::-moz-range-track{height:6px; border-radius:99px; background:linear-gradient(to right,var(--accent) 0 var(--p),var(--sel) var(--p) var(--b),var(--bg-2) var(--b) 100%)}
.rng::-webkit-slider-thumb{-webkit-appearance:none; width:16px; height:16px; margin-top:-5px; border:0; border-radius:50%; background:var(--accent); box-shadow:0 0 0 3px var(--surface),var(--shadow); transition:transform .12s}
.rng::-moz-range-thumb{width:16px; height:16px; border:0; border-radius:50%; background:var(--accent); box-shadow:0 0 0 3px var(--surface),var(--shadow)}
.rng:hover::-webkit-slider-thumb,.rng:active::-webkit-slider-thumb{transform:scale(1.2)}
.rng:focus-visible::-webkit-slider-thumb{box-shadow:0 0 0 3px var(--surface),0 0 0 5px var(--accent)}
.rng:focus-visible::-moz-range-thumb{box-shadow:0 0 0 3px var(--surface),0 0 0 5px var(--accent)}

/* commandes */
.ctrls{display:flex; align-items:center; justify-content:center; gap:10px; margin-top:12px}
.modes{display:flex; align-items:center; justify-content:center; flex-wrap:wrap; gap:10px; margin-top:12px}
.vol{display:flex; align-items:center; justify-content:center; gap:8px; margin:8px auto 0; max-width:280px}
.vol input{flex:1; min-width:0}
.abtn{display:grid; place-items:center; width:44px; height:44px; border-radius:50%; border:1px solid transparent; background:transparent; color:var(--text); cursor:pointer; transition:background .15s,color .15s,transform .12s}
.abtn:hover{background:var(--bg-2)}
.abtn:active{transform:scale(.92)}
.abtn:focus-visible{outline:2px solid var(--accent); outline-offset:2px}
.abtn.on{background:var(--accent-soft); color:var(--accent)}
.abtn svg{width:22px; height:22px}
.abtn.big{width:64px; height:64px; background:var(--accent); color:var(--on-accent); box-shadow:var(--shadow)}
.abtn.big:hover{background:var(--accent); filter:brightness(1.08)}
.abtn.big svg{width:30px; height:30px}
.abtn.sm{width:36px; height:36px}
.abtn.sm svg{width:18px; height:18px}
#b-play svg,#b-prev svg,#b-next svg{fill:currentColor}
#b-play.loading svg{fill:none; animation:lspin .9s linear infinite}
@keyframes lspin{to{transform:rotate(360deg)}}
.pill.sm{padding:6px 12px; font-size:13px}
.pill.sm svg{width:16px; height:16px}
.lmsg{min-height:18px; margin-top:10px; text-align:center}

@media(prefers-reduced-motion:reduce){
  .cover.playing:not(.has-img) .cover-ico svg,#b-play.loading svg{animation:none}
  #b-play.loading svg{opacity:.7}
}

/* aide clavier (anciennement « .keys », classe déjà utilisée par la barre de touches de l'éditeur) */
.lkeys{margin-top:12px; font-size:13px; color:var(--muted)}
.lkeys summary{cursor:pointer; padding:4px 0}
.lkeys .hint{margin-top:8px; line-height:1.9}
.hint kbd svg{display:inline-block; vertical-align:-2px}

/* file de lecture */
.lqueue h2{display:flex; align-items:center; gap:8px; margin:0 0 10px; font-size:16px}
.lfilter{width:100%; padding:9px 14px; margin-bottom:10px; font:inherit; font-size:14px; color:var(--text); background:var(--surface); border:1px solid var(--border); border-radius:99px; outline:none}
.lfilter:focus{border-color:var(--accent); box-shadow:0 0 0 3px var(--accent-soft)}
.llist{position:relative; display:flex; flex-direction:column; gap:6px; max-height:70vh; overflow:auto}
.ltrack{display:flex; align-items:center; gap:12px; width:100%; padding:10px 12px; text-align:left; font:inherit; color:var(--text); background:var(--surface); border:1px solid var(--border); border-radius:12px; cursor:pointer}
.ltrack:hover{background:var(--bg-2)}
.ltrack:focus-visible{outline:2px solid var(--accent); outline-offset:2px}
.ltrack.cur{border-color:var(--accent); background:var(--accent-soft)}
.ltrack.bad{opacity:.5}
.ltrack .num{display:grid; place-items:center; flex:none; min-width:26px; height:20px; font-size:12.5px; color:var(--muted); font-variant-numeric:tabular-nums}
.ltrack.cur .num{color:var(--accent)}
.ltrack .eqi{display:none}
.ltrack.playing .n{display:none}
.ltrack.playing .eqi{display:grid}
.eqi svg{width:16px; height:16px}
.eqi .b1,.eqi .b2,.eqi .b3{transform-box:fill-box; transform-origin:50% 100%; animation:leq 1s ease-in-out infinite}
.eqi .b2{animation-delay:-.4s}
.eqi .b3{animation-delay:-.75s}
@keyframes leq{0%,100%{transform:scaleY(.35)}50%{transform:scaleY(1)}}
@media(prefers-reduced-motion:reduce){.eqi .b1,.eqi .b2,.eqi .b3{animation:none}}
.ltrack .tn{flex:1; min-width:0; overflow-wrap:anywhere}
.ltrack .td{flex:none; font-size:12px; color:var(--muted); font-variant-numeric:tabular-nums}
.ltrack .te{flex:none; font-size:11.5px; color:var(--muted); min-width:34px; text-align:right}
"""

LISTEN_JS = """
(function(){
  var cfg = window.LCFG, I = window.LICO || {};
  var T = cfg.tracks, n = T.length;
  var $ = function(id){ return document.getElementById(id); };
  var a = $('l-audio'), seek = $('l-seek'), vslider = $('l-vol'), cov = $('l-cover'), img = $('l-img');
  var idx = cfg.start, order = [], pos = 0, first = true, errRun = 0, errT = 0, msgT = 0;
  var shuffle = false, repeat = 'off', rates = [0.75, 1, 1.25, 1.5, 1.75, 2], rate = 1;
  var loading = false, seeking = false, lastSave = 0, rows = [], infos = {}, curRow = null;
  function load(k, d){ try { var v = localStorage.getItem('al:' + k); return v === null ? d : v; } catch(e) { return d; } }
  function store(k, v){ try { localStorage.setItem('al:' + k, v); } catch(e) {} }

  shuffle = load('shuffle', '0') === '1';
  repeat = ['off', 'all', 'one'].indexOf(load('repeat', 'off')) >= 0 ? load('repeat', 'off') : 'off';
  rate = parseFloat(load('rate', '1')); if (rates.indexOf(rate) < 0) rate = 1;
  var vol = parseFloat(load('vol', '1')); if (!(vol >= 0 && vol <= 1)) vol = 1;
  a.volume = vol; a.muted = load('muted', '0') === '1';

  function fmt(s){
    if (!isFinite(s) || s < 0) s = 0;
    s = Math.floor(s);
    var h = Math.floor(s / 3600), m = Math.floor(s % 3600 / 60), r = s % 60;
    return (h ? h + ':' + ('0' + m).slice(-2) : m) + ':' + ('0' + r).slice(-2);
  }
  // keep = true : le message reste (erreurs) ; sinon il s'efface seul
  function say(t, keep){
    clearTimeout(msgT);
    $('l-msg').textContent = t || '';
    if (t && !keep) msgT = setTimeout(function(){ $('l-msg').textContent = ''; }, 4000);
  }
  function setIcon(btn, name){ btn.innerHTML = I[name] || ''; }
  function play(){
    var pr = a.play();
    if (pr && pr.catch) pr.catch(function(e){
      if (e && e.name === 'AbortError') return;       // lecture interrompue par un changement de piste
      loading = false; renderPlay();
      if (e && e.name === 'NotAllowedError') say('Appuie sur lecture pour démarrer.', true);
    });
  }

  /* ----- ordre de lecture ----- */
  function rebuild(){
    var i, rest = [];
    if (shuffle) {
      for (i = 0; i < n; i++) if (i !== idx) rest.push(i);
      for (i = rest.length - 1; i > 0; i--) {
        var j = Math.floor(Math.random() * (i + 1)), t = rest[i];
        rest[i] = rest[j]; rest[j] = t;
      }
      order = [idx].concat(rest); pos = 0;
    } else {
      order = []; for (i = 0; i < n; i++) order.push(i);
      pos = idx;
    }
  }

  /* ----- informations des pistes (durée, tags) : chargées à la demande ----- */
  function getInfo(i){
    if (!infos[i]) {
      infos[i] = fetch('/meta?f=' + T[i].q)
        .then(function(r){ return r.ok ? r.json() : {}; })
        .catch(function(){ return {}; });
    }
    return infos[i];
  }
  function showDur(i, d){
    var el = rows[i] && rows[i].querySelector('.td');
    if (el && d) el.textContent = fmt(d);
  }

  /* ----- liste des pistes ----- */
  function buildList(){
    var box = $('l-list');
    box.textContent = '';
    var io = 'IntersectionObserver' in window ? new IntersectionObserver(function(es){
      es.forEach(function(e){
        if (!e.isIntersecting) return;
        io.unobserve(e.target);
        var i = +e.target.dataset.i;
        getInfo(i).then(function(j){ showDur(i, j && j.duration); });
      });
    }, {root: box, rootMargin: '120px'}) : null;
    T.forEach(function(t, i){
      var b = document.createElement('button');
      b.type = 'button'; b.className = 'ltrack'; b.dataset.i = i;
      var num = document.createElement('span'); num.className = 'num';
      var nn = document.createElement('span'); nn.className = 'n'; nn.textContent = i + 1;
      var eq = document.createElement('span'); eq.className = 'eqi'; eq.innerHTML = I.eq || '';
      num.appendChild(nn); num.appendChild(eq);
      var tn = document.createElement('span'); tn.className = 'tn'; tn.textContent = t.n;
      var td = document.createElement('span'); td.className = 'td';
      var te = document.createElement('span'); te.className = 'te'; te.textContent = t.e;
      b.appendChild(num); b.appendChild(tn); b.appendChild(td); b.appendChild(te);
      b.addEventListener('click', function(){ playIndex(i); });
      box.appendChild(b); rows.push(b);
      if (io) io.observe(b);
    });
  }
  function markCurrent(){
    if (curRow) { curRow.classList.remove('cur', 'playing'); curRow.removeAttribute('aria-current'); }
    curRow = rows[idx] || null;
    if (curRow) { curRow.classList.add('cur'); curRow.setAttribute('aria-current', 'true'); }
    renderPlayRow();
  }
  function renderPlayRow(){ if (curRow) curRow.classList.toggle('playing', !a.paused && !a.ended); }
  // fait défiler la liste elle-même (jamais la page) pour montrer la piste courante
  function reveal(){
    var box = $('l-list'), r = rows[idx];
    if (!box || !r) return;
    window.requestAnimationFrame(function(){
      box.scrollTop = Math.max(0, r.offsetTop - (box.clientHeight - r.offsetHeight) / 2);
    });
  }

  /* ----- affichage ----- */
  function renderPlay(){
    var playing = !a.paused, b = $('b-play');
    setIcon(b, loading ? 'loader' : (playing ? 'pause' : 'play'));
    b.classList.toggle('loading', loading);
    b.setAttribute('aria-busy', loading ? 'true' : 'false');
    b.setAttribute('aria-label', playing ? 'Pause' : 'Lecture');
    cov.classList.toggle('playing', playing && !loading);
    renderPlayRow();
  }
  function renderModes(){
    $('b-shuffle').classList.toggle('on', shuffle);
    $('b-shuffle').setAttribute('aria-pressed', shuffle ? 'true' : 'false');
    var rb = $('b-repeat');
    setIcon(rb, repeat === 'one' ? 'repeat1' : 'repeat');
    rb.classList.toggle('on', repeat !== 'off');
    rb.setAttribute('aria-pressed', repeat !== 'off' ? 'true' : 'false');
    rb.setAttribute('aria-label', 'Répétition : ' + (repeat === 'off' ? 'désactivée' : (repeat === 'all' ? 'toutes les pistes' : 'cette piste')));
    rb.title = 'Répétition (R) : ' + (repeat === 'off' ? 'aucune' : (repeat === 'all' ? 'tout' : 'une piste'));
  }
  function renderVol(){
    var muted = a.muted || a.volume === 0;
    setIcon($('b-mute'), muted ? 'mute' : 'volume');
    $('b-mute').setAttribute('aria-pressed', muted ? 'true' : 'false');
    var v = Math.round((a.muted ? 0 : a.volume) * 100);
    vslider.value = v;
    vslider.style.setProperty('--p', v + '%');
    vslider.setAttribute('aria-valuetext', v + ' %');
  }
  function renderRate(){ $('b-rate').textContent = String(rate).replace('.', ',') + '×'; }
  function renderSeek(){
    var d = a.duration, ok = isFinite(d) && d > 0;
    var p = ok ? a.currentTime / d * 100 : 0;
    if (!seeking) seek.value = Math.round(p * 10);
    var shown = seeking ? seek.value / 10 : p, buf = 0;
    if (ok) {
      for (var i = 0; i < a.buffered.length; i++) {
        if (a.buffered.start(i) <= a.currentTime + 0.25 && a.buffered.end(i) >= a.currentTime) buf = Math.max(buf, a.buffered.end(i));
      }
      buf = buf / d * 100;
    }
    seek.style.setProperty('--p', shown + '%');
    seek.style.setProperty('--b', Math.max(shown, buf) + '%');
    $('l-cur').textContent = fmt(seeking && ok ? seek.value / 1000 * d : a.currentTime);
    $('l-dur').textContent = fmt(ok ? d : 0);
    seek.setAttribute('aria-valuetext', fmt(a.currentTime) + ' sur ' + fmt(ok ? d : 0));
  }
  function ui(){ renderPlay(); renderModes(); renderVol(); renderRate(); renderSeek(); }

  /* ----- titre, pochette, écran de verrouillage ----- */
  function coverUrl(k){ return '/cover?f=' + T[k].q; }
  function session(title, info){
    if (!('mediaSession' in navigator) || !window.MediaMetadata) return;
    var art = [];
    if (info && info.cover) { try { art = [{src: new URL(coverUrl(idx), location.href).href, sizes: '640x640'}]; } catch(e) {} }
    try {
      navigator.mediaSession.metadata = new MediaMetadata({
        title: title, artist: (info && info.artist) || cfg.folder, album: (info && info.album) || cfg.folder, artwork: art
      });
    } catch(e) {}
  }
  function applyTitle(info){
    var title = (info && info.title) || T[idx].n;
    $('l-title').textContent = title;
    var sub = [info && info.artist, info && info.album].filter(Boolean).join(' · ');
    var el = $('l-artist'); el.textContent = sub; el.hidden = !sub;
    document.title = title + ' — Lecteur audio';
    session(title, info);
  }
  function setCover(info, k){
    cov.classList.remove('has-img'); img.hidden = true; img.removeAttribute('src');
    if (info && info.cover) img.src = coverUrl(k);
  }
  img.addEventListener('load', function(){ cov.classList.add('has-img'); img.hidden = false; });
  img.addEventListener('error', function(){ cov.classList.remove('has-img'); img.hidden = true; });

  /* ----- lecture ----- */
  function start(k, wantPlay){
    clearTimeout(errT);
    idx = k;
    var t = T[k];
    $('l-count').textContent = 'Piste ' + (k + 1) + ' sur ' + n;
    $('l-dl').href = '/raw?dl=1&f=' + t.q;
    try { history.replaceState(null, '', '/listen?f=' + t.q); } catch(e) {}
    applyTitle(null); setCover(null, k);
    getInfo(k).then(function(j){
      if (k !== idx) return;
      applyTitle(j); setCover(j, k); showDur(k, j && j.duration);
    });
    a.src = '/raw?f=' + t.q;
    a.defaultPlaybackRate = rate; a.playbackRate = rate;
    say('');
    markCurrent(); reveal();
    loading = !!wantPlay;
    if (wantPlay) play();
    renderSeek(); renderPlay();
  }
  function playIndex(k){
    idx = k; rebuild();
    start(k, true);
  }
  function wrap(){
    // fin de liste : on repart du début ; en aléatoire, nouvelle série dont la piste qui vient de finir passe en dernier
    rebuild();
    if (shuffle) order.push(order.shift());
    pos = 0;
    start(order[0], true);
  }
  function next(auto){
    if (pos + 1 < n) { pos++; start(order[pos], true); return; }
    if (repeat === 'all' || (!auto && n > 1)) { wrap(); return; }
    if (!auto) { a.currentTime = 0; play(); return; }       // une seule piste : « suivant » la relance
    a.pause(); a.currentTime = 0; renderPlay(); say('Fin de la liste.');
  }
  function prev(){
    if (a.currentTime > 3) { a.currentTime = 0; return; }
    if (pos > 0) { pos--; start(order[pos], true); return; }
    if (n > 1) { pos = n - 1; start(order[pos], true); return; }
    a.currentTime = 0;
  }
  function toggle(){ if (a.paused) play(); else a.pause(); }
  function seekBy(d){
    if (!isFinite(a.duration)) return;
    a.currentTime = Math.max(0, Math.min(a.duration, a.currentTime + d));
  }
  function setShuffle(v){
    shuffle = v; store('shuffle', v ? '1' : '0'); rebuild(); renderModes();
    say(v ? 'Lecture aléatoire activée.' : "Lecture dans l'ordre.");
  }
  function cycleRepeat(){
    repeat = repeat === 'off' ? 'all' : (repeat === 'all' ? 'one' : 'off');
    store('repeat', repeat); renderModes();
    say(repeat === 'off' ? 'Répétition désactivée.' : (repeat === 'all' ? 'Répétition de toutes les pistes.' : 'Répétition de la piste.'));
  }
  function setVol(v){
    v = Math.max(0, Math.min(1, v));
    a.volume = v; if (v > 0) a.muted = false;
    store('vol', v); store('muted', '0');
  }
  function toggleMute(){ a.muted = !a.muted; store('muted', a.muted ? '1' : '0'); }
  function setRate(r){
    rate = r; a.defaultPlaybackRate = r; a.playbackRate = r; store('rate', r); renderRate();
    say('Vitesse : ' + String(r).replace('.', ',') + '×');
  }
  function stepRate(d){
    var i = rates.indexOf(rate) + d;
    setRate(rates[Math.max(0, Math.min(rates.length - 1, i))]);
  }

  /* ----- événements du lecteur ----- */
  function posKey(){ return 'al:pos:' + cfg.key + ':' + T[idx].f; }
  function posState(){
    if ('mediaSession' in navigator && navigator.mediaSession.setPositionState && isFinite(a.duration)) {
      try { navigator.mediaSession.setPositionState({duration: a.duration, playbackRate: a.playbackRate, position: Math.min(a.currentTime, a.duration)}); } catch(e) {}
    }
  }
  a.addEventListener('loadedmetadata', function(){
    errRun = 0;
    showDur(idx, a.duration);
    if (first) {
      first = false;
      try {
        var s = JSON.parse(localStorage.getItem(posKey()));
        if (s && s.t > 3 && s.t < a.duration - 5) a.currentTime = s.t;
      } catch(e) {}
    }
    renderSeek(); posState();
  });
  a.addEventListener('durationchange', renderSeek);
  a.addEventListener('progress', renderSeek);
  a.addEventListener('timeupdate', function(){
    renderSeek();
    var now = Date.now();
    if (now - lastSave > 2500 && a.duration && !a.ended) {
      lastSave = now;
      try { localStorage.setItem(posKey(), JSON.stringify({t: a.currentTime})); } catch(e) {}
    }
  });
  a.addEventListener('waiting', function(){ if (!a.paused) { loading = true; renderPlay(); } });
  a.addEventListener('canplay', function(){ loading = false; renderPlay(); });
  a.addEventListener('playing', function(){ loading = false; renderPlay(); });
  a.addEventListener('play', function(){ renderPlay(); if ('mediaSession' in navigator) navigator.mediaSession.playbackState = 'playing'; });
  a.addEventListener('pause', function(){
    loading = false; renderPlay();
    if ('mediaSession' in navigator) navigator.mediaSession.playbackState = 'paused';
    try { if (a.duration && !a.ended) localStorage.setItem(posKey(), JSON.stringify({t: a.currentTime})); } catch(e) {}
  });
  a.addEventListener('ended', function(){
    try { localStorage.removeItem(posKey()); } catch(e) {}
    if (repeat === 'one') { a.currentTime = 0; play(); return; }
    next(true);
  });
  a.addEventListener('error', function(){
    loading = false;
    var c = a.error ? a.error.code : 0;
    var why = c === 2 ? 'Erreur réseau' : (c === 3 ? 'Fichier audio endommagé' : (c === 4 ? 'Format non pris en charge' : 'Lecture impossible'));
    if (rows[idx]) rows[idx].classList.add('bad');
    errRun++;
    var canSkip = n > 1 && errRun < n && (pos + 1 < n || repeat === 'all');
    say(why + ' : ' + T[idx].n + (canSkip ? ' — passage à la piste suivante…' : ''), true);
    renderPlay();
    if (canSkip) { clearTimeout(errT); errT = setTimeout(function(){ next(true); }, 1400); }
  });
  a.addEventListener('volumechange', renderVol);
  a.addEventListener('ratechange', posState);
  a.addEventListener('seeked', function(){ renderSeek(); posState(); });

  /* ----- commandes ----- */
  seek.addEventListener('input', function(){ seeking = true; renderSeek(); });
  seek.addEventListener('change', function(){
    if (isFinite(a.duration)) a.currentTime = seek.value / 1000 * a.duration;
    seeking = false; renderSeek(); seek.blur();
  });
  seek.addEventListener('pointercancel', function(){ seeking = false; renderSeek(); });
  vslider.addEventListener('input', function(e){ setVol(e.target.value / 100); });
  vslider.addEventListener('change', function(e){ e.target.blur(); });
  $('b-play').addEventListener('click', toggle);
  $('b-next').addEventListener('click', function(){ next(false); });
  $('b-prev').addEventListener('click', prev);
  $('b-back').addEventListener('click', function(){ seekBy(-10); });
  $('b-fwd').addEventListener('click', function(){ seekBy(10); });
  $('b-shuffle').addEventListener('click', function(){ setShuffle(!shuffle); });
  $('b-repeat').addEventListener('click', cycleRepeat);
  $('b-mute').addEventListener('click', toggleMute);
  $('b-rate').addEventListener('click', function(){ setRate(rates[(rates.indexOf(rate) + 1) % rates.length]); });
  function applyFilter(){
    var q = $('l-filter').value.trim().toLowerCase();
    rows.forEach(function(r, i){ r.hidden = !!q && T[i].n.toLowerCase().indexOf(q) < 0; });
  }
  $('l-filter').addEventListener('input', applyFilter);

  document.addEventListener('keydown', function(e){
    if (e.ctrlKey || e.metaKey || e.altKey) return;
    var tag = (e.target.tagName || '').toLowerCase(), type = (e.target.type || '').toLowerCase();
    var k = e.key, lk = k.toLowerCase();
    if (tag === 'textarea' || (tag === 'input' && type !== 'range' && type !== 'checkbox')) {
      if (k === 'Escape') { if (e.target.id === 'l-filter') { e.target.value = ''; applyFilter(); } e.target.blur(); }
      return;
    }
    if (tag === 'button' && (k === ' ' || k === 'Enter')) return;
    // le curseur de volume garde ses flèches natives ; sur le curseur de position, elles avancent de 5 s
    if (e.target.id === 'l-vol' && (k === 'ArrowLeft' || k === 'ArrowRight' || k === 'ArrowUp' || k === 'ArrowDown')) return;
    var handled = true;
    if (k === ' ' || lk === 'k') toggle();
    else if (lk === 'n') next(false);
    else if (lk === 'p') prev();
    else if (lk === 's') setShuffle(!shuffle);
    else if (lk === 'r') cycleRepeat();
    else if (lk === 'm') toggleMute();
    else if (k === 'ArrowLeft') seekBy(-5);
    else if (k === 'ArrowRight') seekBy(5);
    else if (lk === 'j') seekBy(-10);
    else if (lk === 'l') seekBy(10);
    else if (k === 'ArrowUp') setVol((a.muted ? 0 : a.volume) + 0.05);
    else if (k === 'ArrowDown') setVol((a.muted ? 0 : a.volume) - 0.05);
    else if (k === '<' || k === ',') stepRate(-1);
    else if (k === '>' || k === '.') stepRate(1);
    else if (/^[0-9]$/.test(k)) { if (isFinite(a.duration)) a.currentTime = a.duration * Number(k) / 10; }
    else if (k === '/') { $('l-filter').focus(); }
    else handled = false;
    if (handled) e.preventDefault();
  });

  if ('mediaSession' in navigator) {
    var H = {
      play: play, pause: function(){ a.pause(); },
      previoustrack: prev, nexttrack: function(){ next(false); },
      seekbackward: function(d){ seekBy(-((d && d.seekOffset) || 10)); },
      seekforward: function(d){ seekBy((d && d.seekOffset) || 10); },
      seekto: function(d){ if (d && isFinite(d.seekTime)) a.currentTime = d.seekTime; }
    };
    Object.keys(H).forEach(function(name){ try { navigator.mediaSession.setActionHandler(name, H[name]); } catch(e) {} });
  }
  window.addEventListener('pagehide', function(){
    try { if (a.duration && !a.ended && a.currentTime > 0) localStorage.setItem(posKey(), JSON.stringify({t: a.currentTime})); } catch(e) {}
  });

  buildList();
  rebuild();
  ui();
  start(idx, true);
})();
"""


# --------------------------------------------------------------------------
# Serveur
# --------------------------------------------------------------------------
DASH_POSTS = ("/dashboard/block", "/dashboard/unblock")


class FileHandler(BaseHTTPRequestHandler):
    server_version = "Biblio/1.0"
    _entry = None      # action d'historique de la requête en cours (voir parse_request)

    # ----- réponses
    def send_bytes(self, content, ctype, status=200, extra=None):
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(content)))
        self.send_header("X-Content-Type-Options", "nosniff")
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(content)
        add_bytes(self._entry, len(content))

    def send_html(self, html, status=200):
        self.send_bytes(html.encode("utf-8"), "text/html; charset=utf-8", status,
                        {"Cache-Control": "no-store"})

    def send_json(self, obj, status=200, extra=None):
        self.send_bytes(json.dumps(obj).encode(), "application/json", status,
                        {"Cache-Control": "no-store", **(extra or {})})

    def send_file(self, path, ctype, disposition=None, extra=None):
        try:
            size = path.stat().st_size
        except OSError:
            self.send_error(404)
            return
        start, end, status = 0, size - 1, 200
        header = self.headers.get("Range")
        if header:
            m = re.match(r"bytes=(\d*)-(\d*)$", header.strip())
            if m and (m.group(1) or m.group(2)):
                s, e = m.groups()
                if s == "":
                    start = max(size - int(e), 0)
                else:
                    start = int(s)
                    if e:
                        end = min(int(e), size - 1)
                if start > end or start >= size:
                    self.send_response(416)
                    self.send_header("Content-Range", f"bytes */{size}")
                    self.send_header("Content-Length", "0")
                    self.end_headers()
                    return
                status = 206
        length = max(end - start + 1, 0)
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Content-Length", str(length))
        self.send_header("X-Content-Type-Options", "nosniff")
        if status == 206:
            self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        if disposition:
            self.send_header("Content-Disposition", disposition)
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        try:
            with open(path, "rb") as f:
                f.seek(start)
                remaining = length
                while remaining > 0:
                    chunk = f.read(min(256 * 1024, remaining))
                    if not chunk:
                        break
                    self.wfile.write(chunk)
                    add_bytes(self._entry, len(chunk))
                    remaining -= len(chunk)
        except (BrokenPipeError, ConnectionResetError):
            pass

    # ----- blocage des appareils et suivi des connexions
    def parse_request(self):
        if not super().parse_request():
            return False
        ip = self.client_address[0]
        if is_blocked(ip):
            self.close_connection = True
            self.send_html(message_page("Accès bloqué", "Cet appareil a été bloqué par l'administrateur."), 403)
            return False
        req = urlsplit(self.path)
        authed = self.has_cookie()
        track_device(ip, self.headers.get("User-Agent", ""), authed, hit=not req.path.startswith("/dashboard/"))
        self._entry = None
        if not req.path.startswith("/dashboard"):
            if req.path.startswith("/s/"):     # les aperçus web s'authentifient par le jeton dans l'URL
                parts = req.path.split("/", 3)
                authed = authed or (len(parts) > 2 and hmac.compare_digest(
                    unquote(parts[2]).encode("utf-8", "replace"), TOKEN.encode()))
            if authed:
                action = classify(req.path, parse_qs(req.query))
                if action:
                    self._entry = record_event(ip, *action)
        return True

    # ----- authentification
    def has_cookie(self):
        c = SimpleCookie()
        try:
            c.load(self.headers.get("Cookie", ""))
        except Exception:
            return False
        m = c.get("fl_auth")
        return bool(m) and hmac.compare_digest(m.value.encode("utf-8", "replace"), TOKEN.encode())

    def page_locked(self):
        html = message_page(
            "Accès protégé",
            "Ouvre le lien complet affiché dans le terminal au démarrage de biblio "
            "(il se termine par ?token=…).")
        self.send_html(html, 401)

    def files_locked(self):
        """Vrai si un mot de passe est configuré et que cette session n'est pas déverrouillée."""
        return bool(PASSWORD) and "files" not in unlock_scopes(self.dash_session_id())

    def dash_session_id(self):
        c = SimpleCookie()
        try:
            c.load(self.headers.get("Cookie", ""))
        except Exception:
            return ""
        m = c.get("fl_unlock")
        return m.value if m else ""

    # ----- routage
    def do_GET(self):
        req = urlsplit(self.path)
        q = parse_qs(req.query)
        path = req.path

        def arg(name):
            return q.get(name, [""])[0]

        try:
            if path.startswith("/s/"):
                return self.route_site(path)

            tok = arg("token")
            if tok and hmac.compare_digest(tok.encode("utf-8", "replace"), TOKEN.encode()):
                rest = {k: v for k, v in q.items() if k != "token"}
                loc = "/" + path.lstrip("/") + ("?" + urlencode(rest, doseq=True) if rest else "")
                self.send_response(302)
                self.send_header("Location", loc)
                self.send_header("Set-Cookie",
                                 f"fl_auth={TOKEN}; Path=/; HttpOnly; SameSite=Strict; Max-Age=31536000")
                self.send_header("Content-Length", "0")
                self.end_headers()
                return
            if not self.has_cookie():
                return self.page_locked()

            if path == "/":
                self.page_browse(arg("folder"))
            elif path == "/view":
                self.page_text(arg("f"), edit=False)
            elif path == "/edit":
                self.page_text(arg("f"), edit=True, new=arg("new") == "1")
            elif path == "/preview":
                self.page_preview(arg("f"))
            elif path == "/raw":
                self.route_raw(arg("f"), arg("dl") == "1")
            elif path == "/static/editor.js":
                self.route_bundle()
            elif path == "/lock-state":
                self.route_lock_state()
            elif path == "/watch":
                self.page_watch(arg("f"))
            elif path == "/listen":
                self.page_listen(arg("f"))
            elif path == "/thumb":
                self.serve_thumb(arg("f"))
            elif path == "/meta":
                self.serve_meta(arg("f"))
            elif path == "/cover":
                self.serve_cover(arg("f"))
            elif path == "/sub":
                self.serve_sub(arg("f"))
            elif path == "/pdf":
                self.route_pdf(arg("f"))
            elif path == "/dashboard":
                self.page_dashboard()
            elif path == "/dashboard/data":
                self.route_dash_data()
            elif path == "/dashboard/history":
                self.route_dash_history(q)
            elif path.startswith("/docs/"):
                self.route_docs(path)
            elif path.startswith(("/legacy/", "/build/", "/web/")):
                self.route_pdfjs(path)
            else:
                self.send_error(404, "Page introuvable")
        except (BrokenPipeError, ConnectionResetError):
            pass

    def do_POST(self):
        req = urlsplit(self.path)
        q = parse_qs(req.query)
        try:
            if req.path not in ("/save", "/delete", "/rename", "/upload-auth", "/upload", "/unlock", "/lock") + DASH_POSTS:
                self.send_error(404)
                return
            if not self.has_cookie() or self.headers.get("X-Requested-With") != "biblio":
                self.send_json({"ok": False, "error": "Non autorisé"}, 403)
                return
            if req.path in DASH_POSTS:
                self.route_dash_post(req.path, q)
            elif req.path == "/unlock":
                self.route_unlock()
            elif req.path == "/lock":
                self.route_lock()
            elif req.path == "/delete":
                self.route_delete(q)
            elif req.path == "/rename":
                self.route_rename(q)
            elif req.path == "/upload-auth":
                self.route_upload_auth()
            elif req.path == "/upload":
                self.route_upload(q)
            else:
                self.route_save(q)
        except (BrokenPipeError, ConnectionResetError):
            pass

    # ----- navigation
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

        relative = current.relative_to(ROOT)
        title = relative.name if relative.parts else (ROOT.name or "Bibliothèque")
        grouped = {}
        for f in files:
            kind = card_kind(f)
            grouped.setdefault(group_of(kind), []).append((f, kind))
        has_content = bool(folders or files)
        parts = [doc_open(f"{title} — Ma bibliothèque"), topbar(has_content, True), "<main>"]

        parts.append("<nav class='crumb'>")
        parts.append(f"<a class='{'current' if not relative.parts else ''}' href='/'>"
                     f"{icon('home', 16)}{escape(ROOT.name or 'Accueil')}</a>")
        acc = []
        for i, comp in enumerate(relative.parts):
            acc.append(comp)
            target = quote("/".join(acc), safe="")
            cls = "current" if i == len(relative.parts) - 1 else ""
            parts.append(f"<span class='sep'>{icon('chevron', 14)}</span>"
                         f"<a class='{cls}' href='/?folder={target}'>{escape(comp)}</a>")
        parts.append("</nav>")

        parts.append("<div class='toolrow'>")
        if not READONLY:
            parts.append(f"<button id='newfile' class='pill primary' type='button'>{icon('plus', 16)}Nouveau fichier</button>")
        if PASSWORD and not READONLY:
            parts.append(f"<button id='uploadbtn' class='pill' type='button'>{icon('upload', 16)}Envoyer</button>")
        parts.append("<label class='switch'><input type='checkbox' id='toggle-hidden'>"
                     "<span class='track'></span>Fichiers cachés</label></div>")

        if files:
            parts.append("<div class='filters'><button class='fchip on' type='button' data-g='all'>"
                         f"Tout <b>{len(files)}</b></button>")
            for key, label in GROUPS:
                if key in grouped:
                    parts.append(f"<button class='fchip' type='button' data-g='{key}'>"
                                 f"{label} <b>{len(grouped[key])}</b></button>")
            parts.append("</div>")

        if relative.parts:
            parent = quote(relative.parent.as_posix(), safe="")
            if parent == ".":
                parent = ""
            parts.append("<div class='back-link'>"
                         f"<a class='item' href='/?folder={parent}'>"
                         f"<span class='ico back'>{icon('back', 22)}</span>"
                         "<span class='text'><span class='name'>Dossier précédent</span></span></a></div>")

        if folders:
            parts.append(f"<section class='section' data-group='folders'><h2>Dossiers <span class='count'>{len(folders)}</span></h2>"
                         "<div class='grid'>")
            for d in folders:
                target = quote(rel_of(d), safe="")
                dot = " dot" if d.name.startswith(".") else ""
                parts.append(
                    f"<a class='item{dot}' href='/?folder={target}' "
                    f"data-name='{escape(d.name.casefold(), quote=True)}'>"
                    f"<span class='ico folder'>{icon('folder', 22)}</span>"
                    f"<span class='text'><span class='name'>{escape(d.name)}</span>"
                    "<div class='sub'>Ouvrir le dossier</div></span>"
                    f"<span class='go'>{icon('chevron', 18)}</span></a>")
            parts.append("</div></section>")

        for key, label in GROUPS:
            items = grouped.get(key)
            if not items:
                continue
            parts.append(f"<section class='section' data-group='{key}'><h2>{label} "
                         f"<span class='count'>{len(items)}</span></h2>")
            if key == "video":
                parts.append("<div class='videos'>" + "".join(video_card(f) for f, _ in items) + "</div>")
            else:
                parts.append("<div class='grid'>" + "".join(file_card(f, k) for f, k in items) + "</div>")
            parts.append("</section>")

        if has_content:
            parts.append("<div id='no-result' class='empty' hidden>Aucun résultat à afficher.</div>")
        else:
            parts.append("<div class='empty'>"
                         f"<div class='ico folder'>{icon('folder', 28)}</div>Ce dossier est vide.</div>")
        parts.append("</main>")

        parts.append(
            "<div id='sheet' hidden><div class='backdrop' data-close></div>"
            "<div class='sheet' role='dialog' aria-modal='true'>"
            "<div id='sheet-main'><div class='sheet-head'><div id='sh-ico' class='ico'></div>"
            "<div class='text'><div class='name' id='sh-title'></div><div class='sub' id='sh-sub'></div></div>"
            f"<button class='ibtn' data-close type='button' aria-label='Fermer'>{icon('close', 18)}</button></div>"
            "<div id='sh-body'></div></div>"
            "<div id='newdlg' hidden><div class='sheet-head'><div class='ico back'>"
            f"{icon('plus', 22)}</div><div class='text'><div class='name'>Nouveau fichier</div>"
            "<div class='sub'>Il sera créé à l'enregistrement</div></div>"
            f"<button class='ibtn' data-close type='button' aria-label='Fermer'>{icon('close', 18)}</button></div>"
            "<form id='newform'><p id='new-locked' class='sub' role='status' hidden>Accès verrouillé : déverrouille l'accès "
            "(cadenas en haut de la page) pour créer un fichier.</p>"
            "<input id='newname' type='text' placeholder='nom.py, notes.txt, index.html…' "
            "autocomplete='off' autocapitalize='off' spellcheck='false'>"
            "<div id='newerr' class='err'></div>"
            f"<button id='newok' class='pill primary' type='submit' style='justify-content:center'>{icon('edit', 16)}Créer et éditer</button>"
            "<button id='newcancel' class='pill' type='button' style='justify-content:center'>Annuler</button>"
            "</form></div>"
            "<div id='edtdlg' hidden><div class='sheet-head'><div class='ico back'>"
            f"{icon('edit', 22)}</div><div class='text'><div class='name'>Éditer ce fichier</div>"
            "<div class='sub' id='edt-name'></div></div>"
            f"<button class='ibtn' data-close type='button' aria-label='Fermer'>{icon('close', 18)}</button></div>"
            "<form id='edtform'><p id='edt-locked' class='sub' role='status'>Accès verrouillé : déverrouille l'accès "
            "(cadenas en haut de la page) pour modifier ce fichier.</p>"
            "<button id='edtcancel' class='pill' type='button' style='justify-content:center'>Fermer</button>"
            "</form></div>"
            "<div id='rendlg' hidden><div class='sheet-head'><div class='ico back'>"
            f"{icon('rename', 22)}</div><div class='text'><div class='name'>Renommer ce fichier</div>"
            "<div class='sub' id='ren-name'></div></div>"
            f"<button class='ibtn' data-close type='button' aria-label='Fermer'>{icon('close', 18)}</button></div>"
            "<form id='renform'><p id='ren-locked' class='sub' role='status' hidden>Accès verrouillé : déverrouille l'accès "
            "(cadenas en haut de la page) pour renommer ce fichier.</p>"
            "<input id='rennew' type='text' autocomplete='off' autocapitalize='off' spellcheck='false' placeholder='Nouveau nom'>"
            "<div id='renerr' class='err'></div>"
            f"<button id='renok' class='pill primary' type='submit' style='justify-content:center'>{icon('check', 16)}Renommer</button>"
            "<button id='rencancel' class='pill' type='button' style='justify-content:center'>Annuler</button>"
            "</form></div>"
            "<div id='deldlg' hidden><div class='sheet-head'><div class='ico back danger'>"
            f"{icon('trash', 22)}</div><div class='text'><div class='name'>Supprimer ce fichier ?</div>"
            "<div class='sub' id='del-name'></div></div>"
            f"<button class='ibtn' data-close type='button' aria-label='Fermer'>{icon('close', 18)}</button></div>"
            "<form id='delform'><p id='del-locked' class='sub' role='status' hidden>Accès verrouillé : déverrouille l'accès "
            "(cadenas en haut de la page) pour supprimer ce fichier.</p>"
            "<div id='delerr' class='err'></div>"
            f"<button id='delok' class='pill danger' type='submit' style='justify-content:center'>{icon('trash', 16)}Supprimer définitivement</button>"
            "<button id='delcancel' class='pill' type='button' style='justify-content:center'>Annuler</button>"
            "</form></div>"
            "<div id='updlg' hidden><div class='sheet-head'><div class='ico back'>"
            f"{icon('upload', 22)}</div><div class='text'><div class='name'>Envoyer dans ce dossier</div>"
            "<div class='sub' id='up-dest'></div></div>"
            f"<button class='ibtn' data-close type='button' aria-label='Fermer'>{icon('close', 18)}</button></div>"
            "<div id='upform' hidden style='display:flex;flex-direction:column;gap:10px'><p id='uperr' class='sub' role='status'></p>"
            "<button id='upcancel' class='pill' type='button' style='justify-content:center'>Annuler</button></div>"
            "<div id='uppick' hidden>"
            "<label class='switch'><input type='checkbox' id='upover'><span class='track'></span>Remplacer les fichiers existants</label>"
            f"<a class='opt' href='#' id='up-pick-files'><span class='ico back'>{icon('file', 22)}</span>"
            "<span class='text'><span class='name'>Fichiers ou vidéos</span><div class='sub'>Un ou plusieurs fichiers</div></span>"
            f"<span class='go'>{icon('chevron', 18)}</span></a>"
            f"<a class='opt' href='#' id='up-pick-dir'><span class='ico back'>{icon('folder', 22)}</span>"
            "<span class='text'><span class='name'>Un dossier entier</span><div class='sub'>Avec ses sous-dossiers</div></span>"
            f"<span class='go'>{icon('chevron', 18)}</span></a>"
            "<input id='up-in-files' type='file' multiple hidden><input id='up-in-dir' type='file' webkitdirectory hidden></div>"
            "<div id='uprun' hidden><div class='upbar'><i id='up-bar'></i></div><div class='sub' id='up-sum'></div>"
            "<div id='up-list' class='uplist'></div>"
            "<button id='up-cancel' class='pill' type='button' style='justify-content:center'>Arrêter l'envoi</button>"
            "<button id='up-done' class='pill primary' type='button' style='justify-content:center' hidden>Terminer</button></div>"
            "</div></div></div>")

        cfg = {"readonly": READONLY, "canDelete": bool(PASSWORD) and not READONLY,
               "unlocked": "files" in unlock_scopes(self.dash_session_id()), "protect": bool(PASSWORD), "maxUpload": MAX_UPLOAD, "folder": relative.as_posix() if relative.parts else ""}
        icons_js = {n: icon(n, 22) for n in ICONS}
        parts.append(f"<script>window.FLCFG = {js_json(cfg)}; window.ICO = {js_json(icons_js)};"
                     f"{THEME_JS}{DECORATE_JS}{BROWSE_JS}</script>{lock_script()}</body></html>")
        self.send_html("".join(parts))

    # ----- lecture / édition
    def page_text(self, rel, edit, new=False):
        p = resolve_inside(rel)
        if p is None:
            self.send_error(403, "Fichier non autorisé")
            return
        if edit and READONLY:
            self.send_html(message_page("Mode lecture seule",
                                        "Le serveur a été lancé avec l'option lecture seule : l'édition est désactivée."), 403)
            return
        if edit and PASSWORD and "files" not in unlock_scopes(self.dash_session_id()):
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
            msg = {"big": f"Ce fichier dépasse {fmt_size(MAX_TEXT)}, trop lourd pour être affiché ici.",
                   "binary": "Ce fichier semble binaire : il ne peut pas être lu comme du texte.",
                   "io": "Impossible de lire ce fichier."}[err]
            actions = (f"<a class='pill' href='{back}'>{icon('back', 16)}Retour</a>"
                       f"<a class='pill primary' href='/raw?dl=1&f={q}'>{icon('download', 16)}Télécharger</a>")
            self.send_html(message_page(p.name, msg, actions), 200)
            return

        mt = "new" if is_new else str(p.stat().st_mtime_ns)
        kind = kind_of(p)
        folder_label = p.parent.relative_to(ROOT).as_posix() if p.parent != ROOT else (ROOT.name or "/")
        cfg = {
            "mode": "edit" if edit else "view", "name": p.name, "doc": text, "q": q, "mt": mt,
            "enc": enc, "crlf": crlf, "back": back, "readonly": READONLY,
            "readonlyView": not edit, "vim": True,
        }

        tools = []
        if edit:
            tools += [
                f"<button id='btn-vim' class='pill on' type='button'>Vim</button>",
                f"<button id='wrap-btn' class='pill' type='button'>Retour ligne</button>",
                f"<button id='num-btn' class='pill' type='button'>Numéros</button>",
                f"<button id='btn-keys' class='pill' type='button'>{icon('keyboard', 16)}Touches</button>",
            ]
        else:
            tools += [
                f"<button id='find-btn' class='pill' type='button'>{icon('search', 16)}Rechercher</button>",
                f"<button id='wrap-btn' class='pill on' type='button'>Retour ligne</button>",
            ]
        tools += [
            f"<button id='fs-down' class='pill' type='button' aria-label='Texte plus petit'>A{icon('minus', 12)}</button>",
            f"<button id='fs-up' class='pill' type='button' aria-label='Texte plus grand'>A{icon('plus', 12)}</button>",
        ]
        if not edit:
            if kind == "web":
                tools.append(f"<a class='pill' href='/preview?f={q}'>{icon('globe', 16)}Aperçu</a>")
            elif p.suffix.lower() in MD_EXT:
                tools.append(f"<a class='pill' href='/preview?f={q}'>{icon('book', 16)}Aperçu</a>")
            if not READONLY:
                tools.append(edit_pill(q, self.files_locked()))
        else:
            tools.append(f"<a class='pill' href='/view?f={q}'>{icon('eye', 16)}Lire</a>")
            if p.suffix.lower() in MD_EXT:
                tools.append(f"<a class='pill' href='/preview?f={q}'>{icon('book', 16)}Aperçu</a>")

        save_btn = ""
        if edit:
            save_btn = f"<button id='btn-save' class='pill primary' type='button'>{icon('save', 16)}Enregistrer</button>"

        dirty = "<span id='dirty' class='dirty' hidden title='Modifications non enregistrées'></span>" if edit else ""
        title = ("Édition · " if edit else "") + p.name
        html = [
            doc_open(f"{title} — Ma bibliothèque", "ed-page"),
            "<header class='edbar'>"
            f"<a class='ibtn' href='{back}' title='Retour' aria-label='Retour'>{icon('back', 20)}</a>"
            f"<div class='edtitle'><b>{escape(p.name)}{dirty}</b><small>{escape(folder_label)}"
            f"{' · nouveau fichier' if is_new else ''}</small></div>{save_btn}{theme_button()}</header>",
            f"<div class='edtools'>{''.join(tools)}</div>",
            "<div id='editor' class='ed'></div>",
            "<div class='statusline'>"
            + ("<span id='st-mode' class='mode' data-m='normal'>NORMAL</span>" if edit else "")
            + "<span id='st-msg' class='sp'></span><span id='st-lines'></span><span id='st-pos'>1:1</span>"
            f"<span id='st-lang'></span><span>{escape(enc)}{' · CRLF' if crlf else ''}</span></div>",
        ]
        if edit:
            html.append(self.keys_bar())
        v = bundle_bytes()["v"]
        html.append(f"<script src='/static/editor.js?v={v}'></script>"
                    f"<script>window.FLCFG = {js_json(cfg)}; {THEME_JS}{VIEWER_JS}</script></body></html>")
        self.send_html("".join(html))

    @staticmethod
    def keys_bar():
        def k(label, what, cls=""):
            return f"<button class='key {cls}' type='button' data-k='{escape(what, quote=True)}'>{label}</button>"

        sep = "<span class='key sepk'></span>"
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
        return "<div id='keys' class='keys' hidden>" + "".join(items) + "</div>"

    def page_preview(self, rel):
        p = resolve_inside(rel)
        if p is None or not p.is_file():
            self.send_error(404, "Fichier introuvable")
            return
        if p.suffix.lower() in MD_EXT:
            self.page_markdown(p)
            return
        q = quote(rel_of(p), safe="")
        back = folder_url(p.parent)
        site = f"/s/{TOKEN}/{quote(rel_of(p), safe='/')}"
        folder_label = p.parent.relative_to(ROOT).as_posix() if p.parent != ROOT else (ROOT.name or "/")
        tools = [
            f"<button id='reload' class='pill' type='button'>{icon('refresh', 16)}Actualiser</button>",
            f"<a class='pill' href='{site}' target='_blank' rel='noopener'>{icon('external', 16)}Nouvel onglet</a>",
            f"<a class='pill' href='/view?f={q}'>{icon('eye', 16)}Source</a>",
        ]
        if not READONLY:
            tools.append(edit_pill(q, self.files_locked()))
        html = (
            doc_open(f"Aperçu · {p.name} — Ma bibliothèque", "ed-page")
            + "<header class='edbar'>"
            f"<a class='ibtn' href='{back}' title='Retour' aria-label='Retour'>{icon('back', 20)}</a>"
            f"<div class='edtitle'><b>{escape(p.name)}</b><small>Aperçu · {escape(folder_label)}</small></div>"
            f"{theme_button()}</header><div class='edtools'>{''.join(tools)}</div>"
            f"<iframe id='pv' class='pv' src='{site}' "
            "sandbox='allow-scripts allow-forms allow-popups allow-modals'></iframe>"
            f"<script>{THEME_JS}"
            "document.getElementById('reload').addEventListener('click',function(){"
            "var f=document.getElementById('pv');f.src=f.src;});</script></body></html>"
        )
        self.send_html(html)

    def page_markdown(self, p):
        """Aperçu Markdown : rendu dans le navigateur (MD_JS, sans dépendance), mise en page de lecture."""
        text, enc, crlf, err = load_text(p)
        q = quote(rel_of(p), safe="")
        back = folder_url(p.parent)
        if err:
            msg = {"big": f"Ce fichier dépasse {fmt_size(MAX_TEXT)}, trop lourd pour être affiché ici.",
                   "binary": "Ce fichier semble binaire : il ne peut pas être lu comme du texte.",
                   "io": "Impossible de lire ce fichier."}[err]
            actions = (f"<a class='pill' href='{back}'>{icon('back', 16)}Retour</a>"
                       f"<a class='pill primary' href='/raw?dl=1&f={q}'>{icon('download', 16)}Télécharger</a>")
            self.send_html(message_page(p.name, msg, actions), 200)
            return
        rel_dir = "" if p.parent == ROOT else rel_of(p.parent)
        folder_label = p.parent.relative_to(ROOT).as_posix() if p.parent != ROOT else (ROOT.name or "/")
        exts = {name: sorted(e.lstrip(".") for e in group) for name, group in (
            ("md", MD_EXT), ("web", WEB_EXT), ("image", IMAGE_EXT), ("video", VIDEO_EXT),
            ("audio", AUDIO_EXT), ("binary", BINARY_EXT))}
        cfg = {
            "name": p.name, "doc": text, "q": q, "dir": rel_dir, "label": folder_label, "exts": exts,
            "site": f"/s/{TOKEN}/",
            "ico": {n: icon(n, 18) for n in ("info", "bulb", "msg_alert", "alert", "octagon")},
        }
        tools = [
            f"<button id='md-toc-btn' class='pill on' type='button'>{icon('list', 16)}Sommaire</button>",
            f"<button id='md-fs-down' class='pill' type='button' aria-label='Texte plus petit'>A{icon('minus', 12)}</button>",
            f"<button id='md-fs-up' class='pill' type='button' aria-label='Texte plus grand'>A{icon('plus', 12)}</button>",
            "<button id='md-ff' class='pill' type='button' title='Changer la police de lecture'>Serif</button>",
            f"<button id='md-print' class='pill' type='button'>{icon('printer', 16)}Imprimer</button>",
            f"<a class='pill' href='/view?f={q}'>{icon('code', 16)}Source</a>",
        ]
        if not READONLY:
            tools.append(edit_pill(q, self.files_locked()))
        html = (
            doc_open(f"{p.name} — Ma bibliothèque", "ed-page md-page", MD_CSS)
            + "<header class='edbar'>"
            f"<a class='ibtn' href='{back}' title='Retour' aria-label='Retour'>{icon('back', 20)}</a>"
            f"<div class='edtitle'><b>{escape(p.name)}</b><small id='md-meta'>Aperçu · {escape(folder_label)}</small></div>"
            f"{theme_button()}</header><div class='edtools'>{''.join(tools)}</div>"
            "<div class='mdprog'><i id='md-bar'></i></div>"
            "<div id='md-scroll' class='mdscroll'><div class='mdwrap'>"
            "<article id='md-art' class='mdart'></article>"
            "<nav id='md-toc' class='mdtoc' aria-label='Sommaire'><h2>Sommaire</h2><div id='md-toc-list'></div></nav>"
            "</div></div><div id='md-veil' class='mdveil' hidden></div>"
            f"<script>window.MDCFG = {js_json(cfg)}; {THEME_JS}{MD_JS}</script></body></html>"
        )
        self.send_html(html)

    # ----- fichiers bruts
    def route_raw(self, rel, download):
        p = resolve_inside(rel)
        if p is None or not p.is_file():
            self.send_error(404, "Fichier introuvable")
            return
        kind = kind_of(p)
        if download:
            disp = "attachment; filename*=UTF-8''" + quote(p.name)
            ctype = "application/octet-stream"
        else:
            disp = None
            ctype = guess_mime(p)
            if kind in ("text", "web"):
                ctype = "text/plain; charset=utf-8"
        extra = {"Content-Security-Policy": "sandbox"} if kind in ("text", "web") else None
        self.send_file(p, ctype, disp, extra)

    def route_site(self, path):
        """Aperçu des pages web : /s/<token>/<chemin> (isolé par CSP sandbox)."""
        parts = path.split("/", 3)  # ['', 's', token, rest]
        if len(parts) < 4 or not hmac.compare_digest(unquote(parts[2]).encode("utf-8", "replace"), TOKEN.encode()):
            self.send_error(403, "Accès refusé")
            return
        p = resolve_inside(unquote(parts[3]))
        if p is not None and p.is_dir():
            for name in ("index.html", "index.htm"):
                if (p / name).is_file():
                    p = p / name
                    break
        if p is None or not p.is_file():
            self.send_error(404, "Fichier introuvable")
            return
        self.send_file(p, guess_mime(p), None, {
            "Content-Security-Policy": "sandbox allow-scripts allow-forms allow-popups allow-modals",
            "Cache-Control": "no-store",
        })

    def route_bundle(self):
        if not BUNDLE.is_file():
            self.send_error(404, "editor.bundle.js introuvable à côté de server.py")
            return
        b = bundle_bytes()
        headers = {"Cache-Control": "public, max-age=86400", "Vary": "Accept-Encoding"}
        if "gzip" in self.headers.get("Accept-Encoding", ""):
            headers["Content-Encoding"] = "gzip"
            self.send_bytes(b["gz"], "text/javascript; charset=utf-8", 200, headers)
        else:
            self.send_bytes(b["raw"], "text/javascript; charset=utf-8", 200, headers)

    # ----- vidéos
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
        folder_rel = p.parent.relative_to(ROOT)
        folder_name = folder_rel.name if folder_rel.parts else (ROOT.name or "Accueil")

        tracks, sub_chips = "", ""
        for f, tag in find_subtitles(p):
            code = tag.lower()
            label = LANGS.get(code, tag or "Sous-titres")
            lang = code if code.isalpha() and 2 <= len(code) <= 3 else "fr"
            fq = quote(rel_of(f), safe="")
            tracks += (f"<track kind='subtitles' src='/sub?f={fq}' srclang='{lang}' "
                       f"label='{escape(label, quote=True)}'>")
            if not READONLY:
                if self.files_locked():
                    sub_chips += (f"<span class='chip locked' aria-disabled='true' "
                                  f"title='{escape(EDIT_LOCKED_HINT, quote=True)}'>"
                                  f"{icon('lock', 16)}{escape(label)}</span>")
                else:
                    sub_chips += (f"<a class='chip' href='/edit?f={fq}' title='Éditer les sous-titres'>"
                                  f"{icon('edit', 16)}{escape(label)}</a>")

        def nav_btn(target, kind, text):
            if target is None:
                return f"<span class='btn disabled'>{icon(kind, 16)}{text}</span>"
            return f"<a class='btn' href='{watch_url(target)}'>{icon(kind, 16)}{text}</a>"

        parts = [doc_open(f"{p.stem} — Ma bibliothèque"), topbar(False), "<main class='watch'>"]
        parts.append(
            "<div class='player'><video id='player' controls autoplay playsinline "
            f"preload='metadata' src='/raw?f={q}'>{tracks}</video></div>")
        parts.append(
            "<section class='info'>"
            f"<h1 class='vtitle'>{escape(p.stem)}</h1><div class='chips'>"
            f"<a class='chip' href='{folder_url(p.parent)}'>{icon('folder', 16)}{escape(folder_name)}</a>"
            f"<span class='chip muted'>{size} · {p.suffix[1:].upper()}</span>"
            f"{nav_btn(prev_p, 'prev', 'Précédente')}{nav_btn(next_p, 'next', 'Suivante')}"
            f"<a class='chip' href='/raw?dl=1&f={q}'>{icon('download', 16)}Télécharger</a>{sub_chips}"
            "<label class='switch'><input type='checkbox' id='autonext' checked>"
            "<span class='track'></span>Lecture automatique</label></div>"
            "<p class='hint'>Raccourcis : <kbd>K</kbd> lecture/pause · <kbd>J</kbd> -10 s · "
            "<kbd>L</kbd> +10 s · <kbd>F</kbd> plein écran · <kbd>M</kbd> muet</p>"
            "</section>")
        parts.append("<aside class='next'><h2>Dans ce dossier</h2><div class='list'>")
        parts.extend(video_row(v, p) for v in siblings)
        parts.append("</div></aside></main>")
        cfg = {"key": f"{ROOT_ID}:{rel_of(p)}", "next": watch_url(next_p) if next_p else None}
        parts.append(f"<script>window.WCFG = {js_json(cfg)}; {THEME_JS}{DECORATE_JS}{WATCH_JS}</script></body></html>")
        self.send_html("".join(parts))

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
        folder_rel = p.parent.relative_to(ROOT)
        folder_name = folder_rel.name if folder_rel.parts else (ROOT.name or "Accueil")
        tracks = [{"f": rel_of(f), "q": quote(rel_of(f), safe=""), "n": f.stem, "e": f.suffix[1:].upper()}
                  for f in siblings]
        cfg = {"tracks": tracks, "start": start, "folder": folder_name,
               "back": folder_url(p.parent), "key": ROOT_ID}

        def kbd_icon(name):
            return f"<kbd>{icon(name, 12, 'ik')}</kbd>"

        html = (
            doc_open(f"{p.stem} — Lecteur audio", "", LISTEN_CSS) + topbar(False)
            + "<main class='listen'>"
            "<section class='lplayer'>"
            f"<div class='cover' id='l-cover'><span class='cover-ico'>{icon('music', 72)}</span>"
            "<img id='l-img' alt='Pochette' hidden></div>"
            "<div class='ltitle'><h1 id='l-title'>…</h1><p class='lartist' id='l-artist' hidden></p>"
            f"<div class='lmeta'><a class='chip' href='{folder_url(p.parent)}'>{icon('folder', 16)}{escape(folder_name)}</a>"
            "<span class='sub' id='l-count'></span></div></div>"
            "<div class='seek'><span id='l-cur' class='time'>0:00</span>"
            "<input id='l-seek' class='rng' type='range' min='0' max='1000' value='0' step='1' aria-label='Position'>"
            "<span id='l-dur' class='time'>0:00</span></div>"
            "<div class='ctrls'>"
            f"<button id='b-prev' class='abtn' type='button' title='Piste précédente (P)' aria-label='Piste précédente'>{icon('prev', 24)}</button>"
            f"<button id='b-back' class='abtn' type='button' title='Reculer de 10 s (J)' aria-label='Reculer de 10 secondes'>{icon('back10', 24)}</button>"
            f"<button id='b-play' class='abtn big' type='button' title='Lecture / pause (espace)' aria-label='Lecture'>{icon('play', 24)}</button>"
            f"<button id='b-fwd' class='abtn' type='button' title='Avancer de 10 s (L)' aria-label='Avancer de 10 secondes'>{icon('fwd10', 24)}</button>"
            f"<button id='b-next' class='abtn' type='button' title='Piste suivante (N)' aria-label='Piste suivante'>{icon('next', 24)}</button>"
            "</div>"
            "<div class='modes'>"
            f"<button id='b-shuffle' class='abtn' type='button' title='Lecture aléatoire (S)' aria-label='Lecture aléatoire' aria-pressed='false'>{icon('shuffle', 24)}</button>"
            f"<button id='b-repeat' class='abtn' type='button' title='Répétition (R)' aria-label='Répétition : désactivée' aria-pressed='false'>{icon('repeat', 24)}</button>"
            "<button id='b-rate' class='pill sm' type='button' title='Vitesse de lecture (&lt; et &gt;)'>1×</button>"
            f"<a class='pill sm' id='l-dl' href='#' title='Télécharger'>{icon('download', 16)}Télécharger</a>"
            "</div>"
            "<div class='vol'>"
            f"<button id='b-mute' class='abtn sm' type='button' title='Muet (M)' aria-label='Muet' aria-pressed='false'>{icon('volume', 18)}</button>"
            "<input id='l-vol' class='rng' type='range' min='0' max='100' value='100' step='1' aria-label='Volume'>"
            "</div>"
            "<div id='l-msg' class='sub lmsg' role='status'></div>"
            "<details class='lkeys'><summary>Raccourcis clavier</summary><p class='hint'>"
            "<kbd>Espace</kbd> / <kbd>K</kbd> lecture-pause · <kbd>N</kbd> suivante · <kbd>P</kbd> précédente "
            "(ou début de la piste) · <kbd>S</kbd> aléatoire · <kbd>R</kbd> répétition (aucune, tout, une piste) · "
            f"{kbd_icon('arrow_left')} {kbd_icon('arrow_right')} ±5 s · <kbd>J</kbd> <kbd>L</kbd> ±10 s · "
            f"{kbd_icon('arrow_up')} {kbd_icon('arrow_down')} volume · "
            "<kbd>M</kbd> muet · <kbd>0</kbd>–<kbd>9</kbd> aller à 0–90 % · <kbd>&lt;</kbd> <kbd>&gt;</kbd> vitesse · "
            "<kbd>/</kbd> chercher dans la liste</p></details>"
            "</section>"
            "<aside class='lqueue'>"
            f"<h2>{icon('queue', 18)}Dans ce dossier</h2>"
            "<input id='l-filter' class='lfilter' type='search' placeholder='Filtrer les pistes' aria-label='Filtrer les pistes' autocomplete='off'>"
            "<div id='l-list' class='llist'></div></aside></main>"
            "<audio id='l-audio' preload='metadata'></audio>"
            f"<script>window.LCFG = {js_json(cfg)}; window.LICO = "
            + js_json({n: icon(n, 24) for n in ("play", "pause", "repeat", "repeat1", "volume", "mute",
                                                 "music", "loader", "eq")})
            + f"; {THEME_JS}{LISTEN_JS}</script></body></html>"
        )
        self.send_html(html)

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
            with _sem:
                info = audio_info(p)
            self.send_json({"duration": info["duration"], "title": info["title"], "artist": info["artist"],
                            "album": info["album"], "cover": has_cover(p, info)})
            return
        with _sem:
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

    # ----- PDF (lecteur pdf.js)
    def route_pdf(self, rel):
        p = resolve_inside(rel)
        if p is None or not p.is_file() or p.suffix.lower() != ".pdf":
            self.send_error(404, "PDF introuvable")
            return
        if PDFJS_DIR is not None:
            loc = "/legacy/web/viewer.html?file=" + quote("/docs/" + rel_of(p), safe="")
        else:
            loc = "/raw?f=" + quote(rel_of(p), safe="")
        self.send_response(302)
        self.send_header("Location", loc)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def route_docs(self, path):
        p = resolve_inside(unquote(path[len("/docs/"):]))
        if p is None or not p.is_file() or p.suffix.lower() != ".pdf":
            self.send_error(404, "PDF introuvable")
            return
        self.send_file(p, "application/pdf", None, {"Cache-Control": "no-cache"})

    def route_pdfjs(self, path):
        if PDFJS_DIR is None:
            self.send_error(404, "pdf.js non installé")
            return
        rel = unquote(path.lstrip("/"))
        try:
            # seuls legacy/, build/ et web/ sont servis ; rien ne doit en sortir
            base = (PDFJS_DIR / rel.split("/", 1)[0]).resolve()
            base.relative_to(PDFJS_DIR)
            target = (PDFJS_DIR / rel).resolve()
            target.relative_to(base)
        except (ValueError, OSError):
            self.send_error(403, "Accès refusé")
            return
        if not target.is_file():
            self.send_error(404, "Fichier introuvable")
            return
        self.send_file(target, guess_mime(target), None, {"Cache-Control": "public, max-age=86400"})

    # ----- enregistrement
    def route_save(self, q):
        def arg(name, default=""):
            return q.get(name, [default])[0]

        if READONLY:
            self.send_json({"ok": False, "error": "Mode lecture seule"}, 403)
            return
        if PASSWORD and "files" not in unlock_scopes(self.dash_session_id()):
            self.send_json({"ok": False, "error": "Accès verrouillé", "locked": True}, 403)
            return
        p = resolve_inside(arg("f"))
        if p is None or not p.name:
            self.send_json({"ok": False, "error": "Chemin non autorisé"}, 403)
            return
        if p.exists() and not p.is_file():
            self.send_json({"ok": False, "error": "Ce n'est pas un fichier"}, 400)
            return
        if not p.parent.is_dir():
            self.send_json({"ok": False, "error": "Dossier parent introuvable"}, 400)
            return

        exists = p.exists()
        force = arg("force") == "1"
        if exists and not force:
            if arg("mt") != str(p.stat().st_mtime_ns):
                self.send_json({"ok": False, "error": "Le fichier a changé sur le disque"}, 409)
                return
        if exists and is_binary_file(p):
            self.send_json({"ok": False, "error": "Fichier binaire : édition refusée"}, 415)
            return

        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            length = -1
        if length < 0 or length > MAX_SAVE:
            self.send_json({"ok": False, "error": f"Taille maximale : {fmt_size(MAX_SAVE)}"}, 413)
            return
        body = self.rfile.read(length)
        try:
            text = body.decode("utf-8")
        except UnicodeDecodeError:
            self.send_json({"ok": False, "error": "Contenu UTF-8 invalide"}, 400)
            return

        if arg("crlf") == "1":
            text = text.replace("\n", "\r\n")
        enc = arg("enc", "utf-8")
        if enc not in ("utf-8", "utf-8-sig", "latin-1"):
            enc = "utf-8"
        try:
            data = text.encode(enc)
        except UnicodeEncodeError:
            enc, data = "utf-8", text.encode("utf-8")

        # Si le fichier est lui-même un lien, on écrit dans sa cible (sans remplacer le lien).
        real = Path(os.path.realpath(p)) if p.is_symlink() else p
        tmp = real.with_name(f".{real.name}.fl-tmp")
        try:
            tmp.write_bytes(data)
            if exists:
                os.chmod(tmp, stat.S_IMODE(p.stat().st_mode))
            os.replace(tmp, real)
        except OSError as e:
            try:
                tmp.unlink()
            except OSError:
                pass
            self.send_json({"ok": False, "error": e.strerror or "Écriture impossible"}, 500)
            return
        self.send_json({"ok": True, "mtime": str(p.stat().st_mtime_ns), "enc": enc,
                        "lines": text.count("\n") + 1})

    def route_delete(self, q):
        """POST /delete?f=<chemin> ; l'accès doit être déverrouillé (cadenas), aucun mot de passe n'est lu ici."""
        if READONLY:
            self.send_json({"ok": False, "error": "Mode lecture seule"}, 403)
            return
        if not PASSWORD:
            self.send_json({"ok": False, "error": "Suppression désactivée : BIBLIO_PASSWORD absent du .env"}, 403)
            return
        if "files" not in unlock_scopes(self.dash_session_id()):
            self.send_json({"ok": False, "error": "Accès verrouillé", "locked": True}, 403)
            return

        p = resolve_inside(q.get("f", [""])[0])
        if p is None or p == ROOT:
            self.send_json({"ok": False, "error": "Chemin non autorisé"}, 403)
            return
        if not os.path.lexists(p):
            self.send_json({"ok": False, "error": "Fichier introuvable"}, 404)
            return
        if p.is_dir():                  # dossier réel ou raccourci vers un dossier
            self.send_json({"ok": False, "error": "Les dossiers ne peuvent pas être supprimés"}, 400)
            return
        try:
            os.unlink(p)                # sur un lien symbolique, supprime le lien et non sa cible
        except OSError as e:
            self.send_json({"ok": False, "error": e.strerror or "Suppression impossible"}, 500)
            return
        self.send_json({"ok": True})

    # ----- verrouillage : le mot de passe n'est demandé qu'ici, pour déverrouiller
    def route_lock_state(self):
        scopes = unlock_scopes(self.dash_session_id())
        self.send_json({"enabled": bool(PASSWORD or DASH_PASSWORD), "unlocked": bool(scopes),
                        "files": "files" in scopes, "dash": "dash" in scopes})

    def route_unlock(self):
        """POST /unlock ; corps : mot de passe (BIBLIO_PASSWORD ou BIBLIO_DASHBOARD_PASSWORD) -> session déverrouillée."""
        if not (PASSWORD or DASH_PASSWORD):
            self.send_json({"ok": False, "error": "Verrouillage désactivé : aucun mot de passe dans le .env"}, 403)
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            length = -1
        if length < 0 or length > 1024:
            self.send_json({"ok": False, "error": "Requête invalide"}, 400)
            return
        given = self.rfile.read(length).decode("utf-8", "replace")
        ok, msg = check_password(self.client_address[0], given, [PASSWORD, DASH_PASSWORD])
        if not ok:
            self.send_json({"ok": False, "error": msg}, 429 if msg.startswith("Trop") else 403)
            return
        raw = given.encode("utf-8", "replace")
        scopes = {scope for scope, pw in (("files", PASSWORD), ("dash", DASH_PASSWORD))
                  if pw and hmac.compare_digest(raw, pw.encode("utf-8", "replace"))}
        sid = grant_unlock(self.dash_session_id(), scopes)
        self.send_json({"ok": True, "files": "files" in scopes, "dash": "dash" in scopes},
                       extra={"Set-Cookie": f"fl_unlock={sid}; Path=/; HttpOnly; SameSite=Strict"})

    def route_lock(self):
        drop_dash_session(self.dash_session_id())
        self.send_json({"ok": True}, extra={"Set-Cookie": "fl_unlock=; Path=/; HttpOnly; SameSite=Strict; Max-Age=0"})

    # ----- tableau de bord (accès déverrouillé -> données, blocage)
    def page_dashboard(self):
        if not DASH_PASSWORD:
            self.send_html(message_page(
                "Tableau de bord désactivé",
                "Définis BIBLIO_DASHBOARD_PASSWORD (ou BIBLIO_PASSWORD) dans le .env, puis relance biblio.",
                f"<a class='pill' href='/'>{icon('home', 16)}Accueil</a>"), 403)
            return
        self.send_html(dashboard_page(use_dash_session(self.dash_session_id(), touch=False)))

    def route_dash_data(self):
        if not use_dash_session(self.dash_session_id(), touch=False):
            self.send_json({"ok": False, "error": "Accès verrouillé"}, 401)
            return
        rows = device_rows(self.client_address[0])
        self.send_json({
            "ok": True, "host": socket.gethostname(), "memory": read_memory(), "disks": read_disks(), "devices": rows,
            "active": sum(1 for r in rows if r["active"]), "blocked": sum(1 for r in rows if r["blocked"]),
            "window": DEVICE_ACTIVE_SECONDS,
        })

    def route_dash_history(self, q):
        if not use_dash_session(self.dash_session_id(), touch=False):
            self.send_json({"ok": False, "error": "Accès verrouillé"}, 401)
            return
        ip = q.get("ip", ["all"])[0]
        if ip != "all":
            try:
                ip = str(ipaddress.ip_address(ip))
            except ValueError:
                self.send_json({"ok": False, "error": "Adresse IP invalide."}, 400)
                return
        self.send_json(history_report(ip, q.get("range", ["24h"])[0]))

    def route_dash_post(self, path, q):
        """POST /dashboard/block?ip=…, /dashboard/unblock?ip=… (accès déverrouillé requis)."""
        if not use_dash_session(self.dash_session_id()):
            self.send_json({"ok": False, "error": "Accès verrouillé", "locked": True}, 401)
            return
        ok, err, warning = set_blocked(q.get("ip", [""])[0], path == "/dashboard/block", self.client_address[0])
        if not ok:
            self.send_json({"ok": False, "error": err}, 400)
            return
        self.send_json({"ok": True, "warning": warning})

    # ----- envoi de fichiers (mot de passe -> jeton d'envoi -> un POST par fichier)
    def drain(self, length):
        """Lit et jette le corps restant : sans cela le navigateur perd la réponse d'erreur."""
        if length < 0 or length > DRAIN_MAX:
            self.close_connection = True
            return
        left = length
        while left > 0:
            chunk = self.rfile.read(min(UPLOAD_CHUNK, left))
            if not chunk:
                break
            left -= len(chunk)

    def upload_error(self, length, msg, status, code=""):
        self.drain(length)
        self.send_json({"ok": False, "error": msg, "code": code}, status)

    def route_rename(self, q):
        """POST /rename?f=<chemin>&to=<nouveau nom> ; l'accès doit être déverrouillé (comme la suppression)."""
        if READONLY:
            self.send_json({"ok": False, "error": "Mode lecture seule"}, 403)
            return
        if not PASSWORD:
            self.send_json({"ok": False, "error": "Renommage désactivé : BIBLIO_PASSWORD absent du .env"}, 403)
            return
        if "files" not in unlock_scopes(self.dash_session_id()):
            self.send_json({"ok": False, "error": "Accès verrouillé", "locked": True}, 403)
            return
        p = resolve_inside(q.get("f", [""])[0])
        if p is None or p == ROOT:
            self.send_json({"ok": False, "error": "Chemin non autorisé"}, 403)
            return
        if not os.path.lexists(p):
            self.send_json({"ok": False, "error": "Fichier introuvable"}, 404)
            return
        if p.is_dir():
            self.send_json({"ok": False, "error": "Les dossiers ne peuvent pas être renommés"}, 400)
            return
        new = q.get("to", [""])[0].strip()
        if (not new or new in (".", "..") or "/" in new or "\\" in new or "\x00" in new
                or len(new.encode("utf-8")) > 255):
            self.send_json({"ok": False, "error": "Nom invalide"}, 400)
            return
        target = p.with_name(new)
        if ENV_PATH is not None and os.path.normcase(str(target)) == os.path.normcase(str(ENV_PATH)):
            self.send_json({"ok": False, "error": "Nom réservé"}, 403)
            return
        if new != p.name and os.path.lexists(target):
            try:
                same = new.lower() == p.name.lower() and target.samefile(p)
            except OSError:
                same = False
            if not same:
                self.send_json({"ok": False, "error": "Un fichier porte déjà ce nom"}, 409)
                return
        try:
            if new != p.name:
                os.rename(p, target)
        except OSError as e:
            self.send_json({"ok": False, "error": e.strerror or "Renommage impossible"}, 500)
            return
        self.send_json({"ok": True, "name": new})

    def route_upload_auth(self):
        """POST /upload-auth ; l'accès doit être déverrouillé -> jeton d'envoi."""
        if READONLY:
            self.send_json({"ok": False, "error": "Mode lecture seule"}, 403)
            return
        if not PASSWORD:
            self.send_json({"ok": False, "error": "Envoi désactivé : BIBLIO_PASSWORD absent du .env"}, 403)
            return
        if "files" not in unlock_scopes(self.dash_session_id()):
            self.send_json({"ok": False, "error": "Accès verrouillé", "locked": True}, 403)
            return
        self.send_json({"ok": True, "ticket": issue_ticket(), "ttl": TICKET_TTL})

    def route_upload(self, q):
        """POST /upload?d=<dossier>&n=<chemin relatif>[&o=1] ; corps : contenu du fichier (en flux)."""
        def arg(name):
            return q.get(name, [""])[0]

        try:
            length = int(self.headers.get("Content-Length", "-1"))
        except ValueError:
            length = -1
        if length < 0:
            self.close_connection = True
            self.send_json({"ok": False, "error": "Content-Length requis"}, 411)
            return
        if READONLY:
            return self.upload_error(length, "Mode lecture seule", 403)
        if not PASSWORD:
            return self.upload_error(length, "Envoi désactivé : BIBLIO_PASSWORD absent du .env", 403)
        if "files" not in unlock_scopes(self.dash_session_id()):
            return self.upload_error(length, "Accès verrouillé", 403, "locked")
        if not use_ticket(self.headers.get("X-Upload-Ticket", "")):
            return self.upload_error(length, "Session d'envoi expirée : rouvre « Envoyer »", 403, "ticket")
        if MAX_UPLOAD and length > MAX_UPLOAD:
            return self.upload_error(length, f"Fichier trop volumineux (maximum {fmt_size(MAX_UPLOAD)})", 413)

        parts = clean_upload_name(arg("n"))
        if parts is None:
            return self.upload_error(length, "Nom de fichier invalide", 400)
        folder = resolve_inside(arg("d"))
        if folder is None:
            return self.upload_error(length, "Dossier non autorisé", 403)
        if not folder.is_dir():
            return self.upload_error(length, "Dossier de destination introuvable", 404)
        final = Path(os.path.normpath(folder.joinpath(*parts)))
        try:
            final.relative_to(ROOT)
        except ValueError:
            return self.upload_error(length, "Chemin non autorisé", 403)
        if is_env_file(final):
            return self.upload_error(length, "Chemin non autorisé", 403)

        overwrite = arg("o") == "1"
        exists = os.path.lexists(final)
        if exists and final.is_dir():
            return self.upload_error(length, "Un dossier porte déjà ce nom", 409)
        if exists and not overwrite:
            return self.upload_error(length, "Déjà présent", 409)

        probe = final.parent
        while not probe.exists() and probe != probe.parent:
            probe = probe.parent
        try:
            free = shutil.disk_usage(probe).free
        except OSError:
            free = None
        if free is not None and length + UPLOAD_MIN_FREE > free:
            return self.upload_error(length, "Espace disque insuffisant", 507)
        try:
            os.makedirs(final.parent, exist_ok=True)
        except OSError as e:
            return self.upload_error(length, "Impossible de créer le dossier : " + (e.strerror or "erreur"), 409)

        dest = Path(os.path.realpath(final)) if final.is_symlink() else final   # écrire dans la cible d'un lien
        tmp = dest.with_name(f".up-{secrets.token_hex(6)}.fl-tmp")
        received = 0
        try:
            with open(tmp, "wb") as f:
                while received < length:
                    chunk = self.rfile.read(min(UPLOAD_CHUNK, length - received))
                    if not chunk:
                        break
                    f.write(chunk)
                    received += len(chunk)
            if received != length:               # envoi interrompu par le client
                self.close_connection = True
                return
            if exists:
                try:
                    os.chmod(tmp, stat.S_IMODE(dest.stat().st_mode))
                except OSError:
                    pass
                os.replace(tmp, dest)
            else:
                try:
                    os.link(tmp, dest)           # échoue si le fichier est apparu entre-temps
                except FileExistsError:
                    self.send_json({"ok": False, "error": "Déjà présent"}, 409)
                    return
                except OSError:                  # système de fichiers sans liens physiques
                    if os.path.lexists(dest):
                        self.send_json({"ok": False, "error": "Déjà présent"}, 409)
                        return
                    os.replace(tmp, dest)
            self.send_json({"ok": True, "name": "/".join(parts), "size": length})
        except OSError as e:
            full = e.errno == errno.ENOSPC
            self.drain(max(0, length - received))
            self.send_json({"ok": False, "error": "Espace disque insuffisant" if full else (e.strerror or "Écriture impossible")},
                           507 if full else 500)
        finally:
            try:
                os.unlink(tmp)                   # temporaire (ou second lien) : toujours nettoyé
            except OSError:
                pass


def find_pdfjs(cli):
    candidates = [cli] if cli else []
    if os.environ.get("BIBLIO_PDFJS"):
        candidates.append(os.environ["BIBLIO_PDFJS"])
    candidates += [str(HERE), "/opt/pdf-library"]
    for c in candidates:
        d = Path(c).expanduser().resolve()
        if (d / "legacy" / "web" / "viewer.html").is_file():
            return d
    return None


def main():
    global ROOT, PORT, READONLY, TOKEN, ROOT_ID, PDFJS_DIR, PASSWORD, DASH_PASSWORD, DISKS, ENV_PATH, MAX_UPLOAD

    parser = argparse.ArgumentParser(description="Bibliothèque : documents, vidéos, texte et code")
    parser.add_argument("dossier", nargs="?", default=str(ROOT),
                        help="dossier à servir (défaut : dossier courant)")
    parser.add_argument("-p", "--port", type=int, default=PORT)
    parser.add_argument("-r", "--readonly", action="store_true", help="désactive l'édition")
    parser.add_argument("-e", "--env", help="fichier .env : BIBLIO_TOKEN, BIBLIO_PASSWORD (défaut : .env à côté de server.py)")
    parser.add_argument("-j", "--pdfjs", help="dossier contenant legacy/web/viewer.html (pdf.js)")
    args = parser.parse_args()

    ROOT = Path(args.dossier).expanduser().resolve()
    PORT = args.port
    READONLY = args.readonly
    if not ROOT.is_dir():
        parser.error(f"dossier introuvable : {ROOT}")
    ENV_PATH = Path(args.env or os.environ.get("BIBLIO_ENV") or HERE / ".env").expanduser().resolve()
    ENV.update(read_env(ENV_PATH))
    PASSWORD = conf("BIBLIO_PASSWORD")
    DASH_PASSWORD = conf("BIBLIO_DASHBOARD_PASSWORD") or PASSWORD
    if conf("BIBLIO_DISKS"):
        DISKS = parse_disks(conf("BIBLIO_DISKS"))
    TOKEN = load_token()
    try:
        MAX_UPLOAD = max(0, int(conf("BIBLIO_MAX_UPLOAD_MB") or 4096)) * 1024 * 1024
    except ValueError:
        print("Attention : BIBLIO_MAX_UPLOAD_MB invalide, valeur par défaut (4096 Mo) utilisée.")
    ROOT_ID = hashlib.sha1(str(ROOT).encode()).hexdigest()[:8]
    LOCAL_IPS.update(lan_ips())
    load_blocklist()
    load_history()
    threading.Thread(target=history_flusher, daemon=True).start()
    signal.signal(signal.SIGTERM, _on_term)
    PDFJS_DIR = find_pdfjs(args.pdfjs)

    print(f"Bibliothèque : {ROOT}" + ("  (lecture seule)" if READONLY else ""))
    print(f"Configuration : {ENV_PATH}")
    if READONLY:
        pass
    elif PASSWORD:
        print("Suppression et envoi de fichiers : activés (mot de passe du .env).")
        print("Taille maximale par fichier envoyé : " + (fmt_size(MAX_UPLOAD) if MAX_UPLOAD else "illimitée") + ".")
    else:
        print("Suppression et envoi de fichiers : désactivés (définis BIBLIO_PASSWORD dans le .env).")
    if DASH_PASSWORD:
        print(f"Tableau de bord : activé (/dashboard), {len(_blocked)} appareil(s) bloqué(s).")
    else:
        print("Tableau de bord : désactivé (définis BIBLIO_DASHBOARD_PASSWORD ou BIBLIO_PASSWORD dans le .env).")
    try:
        if ENV_PATH.stat().st_mode & 0o077:
            print(f"Attention : {ENV_PATH.name} est lisible par d'autres utilisateurs (chmod 600 recommandé).")
    except OSError:
        pass
    if not BUNDLE.is_file():
        print(f"Attention : {BUNDLE.name} introuvable à côté de server.py, la lecture et l'édition de texte ne fonctionneront pas.")
    if not FFMPEG:
        print("ffmpeg introuvable : pas de miniatures ni de durées pour les vidéos (sudo apt install ffmpeg).")
    if PDFJS_DIR is None:
        print("pdf.js introuvable : les PDF s'ouvriront avec le lecteur du navigateur (voir l'option --pdfjs).")
    server = ThreadingHTTPServer(("0.0.0.0", PORT), FileHandler)
    print(f"Local   : http://localhost:{PORT}/?token={TOKEN}")
    for ip in lan_ips():
        print(f"Réseau  : http://{ip}:{PORT}/?token={TOKEN}")
    print("Garde ce lien privé : il donne accès aux fichiers" + ("." if READONLY else " et permet de les modifier."))
    print("Ctrl+C pour arrêter.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nArrêt.")
    finally:
        save_history()


if __name__ == "__main__":
    main()
