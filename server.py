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
import socket
import stat
import subprocess
import threading
import time
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
PASSWORD = ""      # BIBLIO_PASSWORD (.env) : vide = suppression de fichiers désactivée
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
_failed = set()

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

EXTRA_MIME = {
    ".js": "text/javascript", ".mjs": "text/javascript", ".css": "text/css",
    ".html": "text/html", ".htm": "text/html", ".svg": "image/svg+xml",
    ".json": "application/json", ".webp": "image/webp", ".avif": "image/avif",
    ".mkv": "video/x-matroska", ".m4a": "audio/mp4", ".woff2": "font/woff2",
    ".mjs": "text/javascript", ".wasm": "application/wasm", ".ftl": "text/plain", ".map": "application/json",
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
})


def icon(name, size=20, cls="i"):
    return (
        f"<svg class='{cls}' width='{size}' height='{size}' viewBox='0 0 24 24' "
        "fill='none' stroke='currentColor' stroke-width='2' "
        "stroke-linecap='round' stroke-linejoin='round' aria-hidden='true'>"
        f"{ICONS[name]}</svg>"
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
    edit:     {ic:'edit',     t:'Éditer',             d:'Éditeur de type Vim',                  u:function(f){return '/edit?f='+f;}},
    preview:  {ic:'globe',    t:'Aperçu de la page',  d:'Afficher la page web rendue',          u:function(f){return '/preview?f='+f;}},
    open:     {ic:'external', t:'Ouvrir',             d:'Afficher dans le navigateur',          u:function(f){return '/raw?f='+f;}},
    download: {ic:'download', t:'Télécharger',        d:'Enregistrer une copie',                u:function(f){return '/raw?dl=1&f='+f;}},
    del:      {ic:'trash',    t:'Supprimer',          d:'Protégé par mot de passe',             u:null, danger:true}
  };
  var BY = {
    video:['watch','download'], pdf:['pdf','open','download'], text:['view','edit','download'],
    web:['preview','view','edit','download'], image:['open','download'], audio:['open','download'],
    binary:['download']
  };
  var wrap = document.getElementById('sheet');
  var bodyEl = document.getElementById('sh-body');

  var upRunning = false, upDirty = false;
  function closeSheet(){
    if (upRunning) return;
    var reload = upDirty;
    wrap.hidden = true; document.getElementById('newdlg').hidden = true; document.getElementById('deldlg').hidden = true;
    document.getElementById('updlg').hidden = true; bodyEl.innerHTML = '';
    if (reload) location.reload();
  }
  function esc(s){ return s.replace(/[&<>"']/g, function(c){ return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]; }); }

  function openMenu(a){
    var kind = a.dataset.kind, f = a.dataset.f;
    var list = (BY[kind] || ['view','edit','download']).filter(function(k){
      return !(cfg.readonly && k === 'edit');
    });
    if (cfg.canDelete) list.push('del');
    document.getElementById('sh-title').textContent = a.dataset.title;
    document.getElementById('sh-sub').textContent = a.dataset.size;
    var ic = document.getElementById('sh-ico');
    ic.innerHTML = ICO[a.dataset.ico] || '';
    ic.className = 'ico ' + (a.dataset.icls || '');
    bodyEl.innerHTML = list.map(function(k){
      var o = OPTS[k];
      return '<a class="opt' + (o.danger ? ' danger" data-del="1' : '') + '" href="' + (o.u ? o.u(f) : '#') + '"><span class="ico back">' + ICO[o.ic] + '</span>' +
        '<span class="text"><span class="name">' + esc(o.t) + '</span><div class="sub">' + esc(o.d) + '</div></span>' +
        '<span class="go">' + ICO.chevron + '</span></a>';
    }).join('');
    var dl = bodyEl.querySelector('[data-del]');
    if (dl) dl.addEventListener('click', function(e){ e.preventDefault(); askDelete(a); });
    document.getElementById('newdlg').hidden = true;
    document.getElementById('deldlg').hidden = true;
    document.getElementById('sheet-main').hidden = false;
    wrap.hidden = false;
  }

  // ----- suppression (mot de passe du .env)
  var delTarget = null;
  function askDelete(a){
    delTarget = a;
    var pw = document.getElementById('delpw');
    document.getElementById('del-name').textContent = a.dataset.title;
    document.getElementById('delerr').textContent = '';
    pw.value = '';
    document.getElementById('sheet-main').hidden = true;
    document.getElementById('deldlg').hidden = false;
    setTimeout(function(){ pw.focus(); }, 50);
  }
  document.getElementById('delcancel').addEventListener('click', closeSheet);
  document.getElementById('delform').addEventListener('submit', function(e){
    e.preventDefault();
    var pw = document.getElementById('delpw'), err = document.getElementById('delerr');
    var btn = document.getElementById('delok');
    if (!delTarget || !cfg.canDelete) return;
    if (!pw.value) { err.textContent = 'Saisis le mot de passe.'; return; }
    btn.disabled = true; err.textContent = '';
    fetch('/delete?f=' + delTarget.dataset.f, {
      method: 'POST',
      headers: {'X-Requested-With': 'biblio', 'Content-Type': 'text/plain; charset=utf-8'},
      body: pw.value
    }).then(function(r){ return r.json().then(function(j){ return {s: r.status, j: j}; }); })
      .then(function(x){
        btn.disabled = false;
        if (!x.j.ok) { err.textContent = x.j.error || ('Erreur ' + x.s); pw.value = ''; pw.focus(); return; }
        location.reload();
      })
      .catch(function(){ btn.disabled = false; err.textContent = 'Échec réseau, rien n\\u2019a été supprimé.'; });
  });

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

  // ----- envoi de fichiers, vidéos et dossiers (mot de passe du .env)
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

    upBtn.addEventListener('click', function(){
      upEl('sheet-main').hidden = true; upEl('newdlg').hidden = true; upEl('deldlg').hidden = true;
      upEl('updlg').hidden = false; wrap.hidden = false;
      upEl('up-dest').textContent = '/' + (cfg.folder || '');
      upEl('uperr').textContent = ''; upEl('uppw').value = '';
      if (upTicket && Date.now() < upExpire) upShow('uppick');
      else { upShow('upform'); setTimeout(function(){ upEl('uppw').focus(); }, 50); }
    });

    upEl('upform').addEventListener('submit', function(e){
      e.preventDefault();
      var pw = upEl('uppw'), err = upEl('uperr'), b = upEl('upok');
      if (!pw.value) { err.textContent = 'Saisis le mot de passe.'; return; }
      b.disabled = true; err.textContent = '';
      fetch('/upload-auth', {
        method: 'POST',
        headers: {'X-Requested-With': 'biblio', 'Content-Type': 'text/plain; charset=utf-8'},
        body: pw.value
      }).then(function(r){ return r.json().then(function(j){ return {s: r.status, j: j}; }); })
        .then(function(x){
          b.disabled = false; pw.value = '';
          if (!x.j.ok) { err.textContent = x.j.error || ('Erreur ' + x.s); pw.focus(); return; }
          upTicket = x.j.ticket; upTtl = x.j.ttl * 1000; upExpire = Date.now() + upTtl - 30000;
          upShow('uppick');
        })
        .catch(function(){ b.disabled = false; err.textContent = 'Échec réseau.'; });
    });

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
      var mark = function(it, cls, txt){ it.row.className = 'uprow ' + cls; it.s.textContent = txt; };
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
          if (x.status === 200 && j.ok) { ok++; mark(it, 'ok', '✓ ' + fmtB(it.f.size)); upExpire = Date.now() + upTtl - 30000; }
          else if (x.status === 409) { skipped++; mark(it, 'skip', j.error || 'déjà présent'); }
          else if (j.code === 'ticket') {
            failed++; upTicket = null; mark(it, 'bad', 'session expirée');
            return finish('mot de passe à saisir à nouveau (rouvre « Envoyer »)');
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
      var inp = document.getElementById('newname');
      inp.value = ''; document.getElementById('newerr').textContent = '';
      setTimeout(function(){ inp.focus(); }, 50);
    });
    document.getElementById('newform').addEventListener('submit', function(e){
      e.preventDefault();
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
.uprow .s{flex:none; color:var(--muted)}
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
    now = time.monotonic()
    with _auth_lock:
        count, until = _auth_fails.get(ip, (0, 0.0))
        if until > now:
            return False, f"Trop d'essais, réessaie dans {int(until - now) + 1} s."
        if until:                       # verrou expiré : on repart de zéro
            count = 0
        count += 1                      # l'essai est compté avant la vérification (essais parallèles)
        _auth_fails[ip] = (count, now + LOCK_SECONDS if count >= MAX_FAILS else 0.0)
    ok = bool(expected) and hmac.compare_digest(given.encode("utf-8", "replace"), expected.encode("utf-8", "replace"))
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

DASH_TTL = 30 * 60                 # inactivité maximale d'une session du tableau de bord
_dash_lock = threading.Lock()
_dash_sessions = {}                # identifiant de session -> expiration (monotonic)


def issue_dash_session():
    now = time.monotonic()
    with _dash_lock:
        for s in [s for s, exp in _dash_sessions.items() if exp < now]:
            del _dash_sessions[s]
        while len(_dash_sessions) >= 20:
            del _dash_sessions[min(_dash_sessions, key=_dash_sessions.get)]
        sid = secrets.token_urlsafe(24)
        _dash_sessions[sid] = now + DASH_TTL
    return sid


def use_dash_session(sid, touch=True):
    """Vrai si la session est valide. Les actions (touch) prolongent sa validité ; l'actualisation
    automatique de la page, non : un onglet oublié finit donc par se verrouiller."""
    if not sid:
        return False
    now = time.monotonic()
    with _dash_lock:
        exp = _dash_sessions.get(sid)
        if exp is None or exp < now:
            _dash_sessions.pop(sid, None)
            return False
        if touch:
            _dash_sessions[sid] = now + DASH_TTL
    return True


def drop_dash_session(sid):
    with _dash_lock:
        _dash_sessions.pop(sid, None)


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


_bundle_cache = {}


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
        f"<title>{escape(title)}</title>{THEME_INIT}<style>{CSS}{extra_css}</style></head>"
        f"<body class='{body_class}'>"
    )


def topbar(with_search):
    search = ""
    if with_search:
        search = (f"<label class='search'>{icon('search', 18)}"
                  "<input id='search' type='search' autocomplete='off' "
                  "placeholder='Rechercher dans ce dossier…'></label>")
    return (
        "<header class='topbar'><a class='brand' href='/'>"
        f"<span class='logo'>{icon('library', 22)}</span><span>Ma bibliothèque</span></a>"
        f"{search}{theme_button()}"
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
            "image": f"/raw?f={q}", "audio": f"/raw?f={q}", "binary": f"/raw?dl=1&f={q}"}[kind]
    direct = kind in ("pdf", "image", "audio", "binary")
    dot = " dot" if p.name.startswith(".") else ""
    ext = p.suffix[1:].upper() if p.suffix else "FICHIER"
    if kind in ("pdf", "image", "audio"):
        right = f"<button class='more' type='button' aria-label='Plus d’actions'>{icon('more', 18)}</button>"
    else:
        right = f"<span class='go'>{icon('chevron', 18)}</span>"
    return (
        f"<a class='item fcard{dot}' href='{href}' data-f='{q}' data-kind='{kind}' "
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
.stat{padding:14px 16px; border-radius:14px; background:var(--surface); border:1px solid var(--border); box-shadow:var(--shadow)}
.stat .label{font-size:12.5px; font-weight:600; color:var(--muted)}
.stat .value{margin-top:4px; font-size:24px; font-weight:700; letter-spacing:-.01em}
.meter{height:10px; margin-top:14px; border-radius:99px; background:var(--bg-2); overflow:hidden}
.meter span{display:block; height:100%; width:0; border-radius:99px; background:var(--green); transition:width .4s,background .3s}
.meter span.warn{background:var(--orange)}
.meter span.crit{background:var(--red)}
.dev{display:flex; align-items:center; gap:14px; padding:12px 14px; border-radius:14px; background:var(--surface); border:1px solid var(--border); box-shadow:var(--shadow)}
.dev.blocked{border-color:var(--red); background:var(--red-soft)}
.dev .text{flex:1; min-width:0; overflow-wrap:anywhere}
.dev .ico.danger{background:var(--red-soft); color:var(--red)}
.dev-top{display:flex; flex-wrap:wrap; align-items:center; gap:8px}
.ip{font:600 15px ui-monospace,SFMono-Regular,Menlo,Consolas,monospace}
.tag{font-size:11.5px; font-weight:600; padding:1px 8px; border-radius:99px; background:var(--gray-soft); color:var(--muted)}
.tag.me{background:var(--accent-soft); color:var(--accent)}
.tag.bad{background:var(--red-soft); color:var(--red)}
.pill.danger{color:var(--red); border-color:var(--red)}
.pill.danger:hover{background:var(--red-soft); color:var(--red)}
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

DASH_LOGIN_JS = """
(function(){
  var f = document.getElementById('login');
  var pwd = document.getElementById('pwd');
  var err = document.getElementById('err');
  var btn = document.getElementById('go');
  function fail(msg){
    err.textContent = msg; err.hidden = false; btn.disabled = false;
  }
  f.addEventListener('submit', function(e){
    e.preventDefault();
    btn.disabled = true; err.hidden = true;
    fetch('/dashboard/login', {
      method: 'POST', credentials: 'same-origin', body: pwd.value,
      headers: {'X-Requested-With': 'biblio', 'Content-Type': 'text/plain; charset=utf-8'}
    })
      .then(function(r){ return r.json(); })
      .then(function(j){
        if (j.ok) { location.reload(); return; }
        fail(j.error || 'Erreur'); pwd.select();
      })
      .catch(function(){ fail('Connexion impossible.'); });
  });
})();
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
  function ago(s){
    if (s === null) return 'pas vu depuis le démarrage';
    if (s < 5) return "à l'instant";
    if (s < 60) return 'il y a ' + s + ' s';
    if (s < 3600) return 'il y a ' + Math.floor(s / 60) + ' min';
    if (s < 86400) return 'il y a ' + Math.floor(s / 3600) + ' h';
    return 'il y a ' + Math.floor(s / 86400) + ' j';
  }
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
    if (!v.me && !v.local) {
      var b = el('button', 'pill' + (v.blocked ? '' : ' danger'), v.blocked ? 'Débloquer' : 'Bloquer');
      b.type = 'button';
      b.addEventListener('click', function(){ act(v.ip, !v.blocked); });
      r.appendChild(b);
    }
    return r;
  }
  function memory(m){
    $('mem').hidden = !m;
    $('mem-na').hidden = !!m;
    if (!m) return;
    $('m-used').textContent = m.used_h;
    $('m-free').textContent = m.free_h;
    $('m-total').textContent = m.total_h;
    var bar = $('meter-bar');
    bar.style.width = m.percent + '%';
    bar.className = m.percent >= 90 ? 'crit' : (m.percent >= 70 ? 'warn' : '');
    $('m-pct').textContent = String(m.percent).replace('.', ',') + ' % utilisée · libre = mémoire disponible (cache récupérable inclus)';
  }
  function render(d){
    $('host').textContent = d.host;
    memory(d.memory);
    $('n-active').textContent = d.active;
    $('dev-sub').textContent = d.active + (d.active > 1 ? ' appareils connectés' : ' appareil connecté')
      + ' (activité depuis moins de ' + Math.round(d.window / 60) + ' min) · ' + d.blocked
      + (d.blocked > 1 ? ' bloqués' : ' bloqué');
    var list = $('devices');
    list.textContent = '';
    d.devices.forEach(function(v){ list.appendChild(row(v)); });
    if (!d.devices.length) list.appendChild(el('div', 'empty', 'Aucun appareil pour le moment.'));
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
    fetch('/dashboard/logout', {method: 'POST', headers: H, credentials: 'same-origin'})
      .then(function(){ location.reload(); });
  });
  document.addEventListener('visibilitychange', function(){ if (!document.hidden) load(); });
  setInterval(function(){ if (!document.hidden) load(); }, 3000);
  load();
})();
"""


def dashboard_page(unlocked):
    parts = [doc_open("Tableau de bord — Ma bibliothèque", "", DASH_CSS), topbar(False)]
    if not unlocked:
        parts.append(
            "<main><div class='msgcard dash-login'>"
            f"<div class='ico code'>{icon('lock', 24)}</div>"
            "<h1>Tableau de bord</h1><p>Entre le mot de passe pour continuer.</p>"
            "<form id='login'><input id='pwd' type='password' placeholder='Mot de passe' "
            "autocomplete='current-password' required autofocus>"
            "<button id='go' class='pill primary' type='submit'>Déverrouiller</button></form>"
            "<p id='err' class='dash-err' role='alert' hidden></p></div></main>"
            f"<script>{THEME_JS}{DASH_LOGIN_JS}</script></body></html>")
        return "".join(parts)
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
        "<section class='section'><h2>Appareils connectés <span class='count' id='n-active'>0</span></h2>"
        "<div class='sub' id='dev-sub'></div><div class='list' id='devices' style='margin-top:12px'></div></section>"
        "</main>"
        f"<script>window.DCFG = {js_json({'monitor': icon('monitor', 22), 'ban': icon('ban', 22)})}; "
        f"{THEME_JS}{DASH_JS}</script></body></html>")
    return "".join(parts)


# --------------------------------------------------------------------------
# Serveur
# --------------------------------------------------------------------------
DASH_POSTS = ("/dashboard/login", "/dashboard/logout", "/dashboard/block", "/dashboard/unblock")


class FileHandler(BaseHTTPRequestHandler):
    server_version = "Biblio/1.0"

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
        track_device(ip, self.headers.get("User-Agent", ""), self.has_cookie(),
                     hit=not self.path.startswith("/dashboard/data"))
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

    def dash_session_id(self):
        c = SimpleCookie()
        try:
            c.load(self.headers.get("Cookie", ""))
        except Exception:
            return ""
        m = c.get("fl_dash")
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
            elif path == "/watch":
                self.page_watch(arg("f"))
            elif path == "/thumb":
                self.serve_thumb(arg("f"))
            elif path == "/meta":
                self.serve_meta(arg("f"))
            elif path == "/sub":
                self.serve_sub(arg("f"))
            elif path == "/pdf":
                self.route_pdf(arg("f"))
            elif path == "/dashboard":
                self.page_dashboard()
            elif path == "/dashboard/data":
                self.route_dash_data()
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
            if req.path not in ("/save", "/delete", "/upload-auth", "/upload") + DASH_POSTS:
                self.send_error(404)
                return
            if not self.has_cookie() or self.headers.get("X-Requested-With") != "biblio":
                self.send_json({"ok": False, "error": "Non autorisé"}, 403)
                return
            if req.path in DASH_POSTS:
                self.route_dash_post(req.path, q)
            elif req.path == "/delete":
                self.route_delete(q)
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
        parts = [doc_open(f"{title} — Ma bibliothèque"), topbar(has_content), "<main>"]

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
            "<form id='newform'><input id='newname' type='text' placeholder='nom.py, notes.txt, index.html…' "
            "autocomplete='off' autocapitalize='off' spellcheck='false'>"
            "<div id='newerr' class='err'></div>"
            f"<button class='pill primary' type='submit' style='justify-content:center'>{icon('edit', 16)}Créer et éditer</button>"
            "</form></div>"
            "<div id='deldlg' hidden><div class='sheet-head'><div class='ico back danger'>"
            f"{icon('trash', 22)}</div><div class='text'><div class='name'>Supprimer ce fichier ?</div>"
            "<div class='sub' id='del-name'></div></div>"
            f"<button class='ibtn' data-close type='button' aria-label='Fermer'>{icon('close', 18)}</button></div>"
            "<form id='delform'><input id='delpw' type='password' placeholder='Mot de passe' autocomplete='off'>"
            "<div id='delerr' class='err'></div>"
            f"<button id='delok' class='pill danger' type='submit' style='justify-content:center'>{icon('trash', 16)}Supprimer définitivement</button>"
            "<button id='delcancel' class='pill' type='button' style='justify-content:center'>Annuler</button>"
            "</form></div>"
            "<div id='updlg' hidden><div class='sheet-head'><div class='ico back'>"
            f"{icon('upload', 22)}</div><div class='text'><div class='name'>Envoyer dans ce dossier</div>"
            "<div class='sub' id='up-dest'></div></div>"
            f"<button class='ibtn' data-close type='button' aria-label='Fermer'>{icon('close', 18)}</button></div>"
            "<form id='upform'><input id='uppw' type='password' placeholder='Mot de passe' autocomplete='off'>"
            "<div id='uperr' class='err'></div>"
            "<button id='upok' class='pill primary' type='submit' style='justify-content:center'>Continuer</button></form>"
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

        cfg = {"readonly": READONLY, "canDelete": bool(PASSWORD) and not READONLY, "maxUpload": MAX_UPLOAD, "folder": relative.as_posix() if relative.parts else ""}
        icons_js = {n: icon(n, 22) for n in ICONS}
        parts.append(f"<script>window.FLCFG = {js_json(cfg)}; window.ICO = {js_json(icons_js)};"
                     f"{THEME_JS}{DECORATE_JS}{BROWSE_JS}</script></body></html>")
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
            if not READONLY:
                tools.append(f"<a class='pill primary' href='/edit?f={q}'>{icon('edit', 16)}Éditer</a>")
        else:
            tools.append(f"<a class='pill' href='/view?f={q}'>{icon('eye', 16)}Lire</a>")

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
            k("←", "left"), k("↓", "down"), k("↑", "up"), k("→", "right"),
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
            tools.append(f"<a class='pill primary' href='/edit?f={q}'>{icon('edit', 16)}Éditer</a>")
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

    def serve_thumb(self, rel):
        p = resolve_inside(rel)
        t = thumb_for(p) if p and p.is_file() and kind_of(p) == "video" else None
        if t is None:
            self.send_error(404)
            return
        self.send_bytes(t.read_bytes(), "image/jpeg", 200, {"Cache-Control": "private, max-age=86400"})

    def serve_meta(self, rel):
        p = resolve_inside(rel)
        if p is None or not p.is_file() or kind_of(p) != "video":
            self.send_error(404)
            return
        with _sem:
            dur = duration_of(p)
        self.send_json({"duration": dur})

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
        """POST /delete?f=<chemin> ; corps : mot de passe (BIBLIO_PASSWORD du .env)."""
        if READONLY:
            self.send_json({"ok": False, "error": "Mode lecture seule"}, 403)
            return
        if not PASSWORD:
            self.send_json({"ok": False, "error": "Suppression désactivée : BIBLIO_PASSWORD absent du .env"}, 403)
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            length = -1
        if length < 0 or length > 1024:
            self.send_json({"ok": False, "error": "Requête invalide"}, 400)
            return
        given = self.rfile.read(length).decode("utf-8", "replace")
        ok, msg = check_password(self.client_address[0], given)
        if not ok:
            self.send_json({"ok": False, "error": msg}, 429 if msg.startswith("Trop") else 403)
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

    # ----- tableau de bord (mot de passe -> session -> données, blocage)
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
            self.send_json({"ok": False, "error": "Session expirée"}, 401)
            return
        rows = device_rows(self.client_address[0])
        self.send_json({
            "ok": True, "host": socket.gethostname(), "memory": read_memory(), "devices": rows,
            "active": sum(1 for r in rows if r["active"]), "blocked": sum(1 for r in rows if r["blocked"]),
            "window": DEVICE_ACTIVE_SECONDS,
        })

    def route_dash_post(self, path, q):
        """POST /dashboard/login (corps : mot de passe), /logout, /block?ip=…, /unblock?ip=…"""
        cookie = "fl_dash={}; Path=/dashboard; HttpOnly; SameSite=Strict; Max-Age={}"
        if path == "/dashboard/login":
            if not DASH_PASSWORD:
                self.send_json({"ok": False, "error": "Tableau de bord désactivé : mot de passe absent du .env"}, 403)
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                length = -1
            if length < 0 or length > 1024:
                self.send_json({"ok": False, "error": "Requête invalide"}, 400)
                return
            given = self.rfile.read(length).decode("utf-8", "replace")
            ok, msg = check_password(self.client_address[0], given, DASH_PASSWORD)
            if not ok:
                self.send_json({"ok": False, "error": msg}, 429 if msg.startswith("Trop") else 403)
                return
            self.send_json({"ok": True}, extra={"Set-Cookie": cookie.format(issue_dash_session(), DASH_TTL)})
            return
        if path == "/dashboard/logout":
            drop_dash_session(self.dash_session_id())
            self.send_json({"ok": True}, extra={"Set-Cookie": cookie.format("", 0)})
            return
        if not use_dash_session(self.dash_session_id()):
            self.send_json({"ok": False, "error": "Session expirée, reconnecte-toi."}, 401)
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

    def route_upload_auth(self):
        """POST /upload-auth ; corps : mot de passe -> jeton d'envoi."""
        if READONLY:
            self.send_json({"ok": False, "error": "Mode lecture seule"}, 403)
            return
        if not PASSWORD:
            self.send_json({"ok": False, "error": "Envoi désactivé : BIBLIO_PASSWORD absent du .env"}, 403)
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            length = -1
        if length < 0 or length > 1024:
            self.send_json({"ok": False, "error": "Requête invalide"}, 400)
            return
        given = self.rfile.read(length).decode("utf-8", "replace")
        ok, msg = check_password(self.client_address[0], given)
        if not ok:
            self.send_json({"ok": False, "error": msg}, 429 if msg.startswith("Trop") else 403)
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
        if not use_ticket(self.headers.get("X-Upload-Ticket", "")):
            return self.upload_error(length, "Session d'envoi expirée : saisis à nouveau le mot de passe", 403, "ticket")
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
    global ROOT, PORT, READONLY, TOKEN, ROOT_ID, PDFJS_DIR, PASSWORD, DASH_PASSWORD, ENV_PATH, MAX_UPLOAD

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
    TOKEN = load_token()
    try:
        MAX_UPLOAD = max(0, int(conf("BIBLIO_MAX_UPLOAD_MB") or 4096)) * 1024 * 1024
    except ValueError:
        print("Attention : BIBLIO_MAX_UPLOAD_MB invalide, valeur par défaut (4096 Mo) utilisée.")
    ROOT_ID = hashlib.sha1(str(ROOT).encode()).hexdigest()[:8]
    LOCAL_IPS.update(lan_ips())
    load_blocklist()
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


if __name__ == "__main__":
    main()
