"""Configuration et sécurité de biblio : tout est centralisé ici.

Ce module regroupe :
  - les emplacements, réglages et limites du serveur ;
  - la lecture du fichier .env (jeton d'accès, mots de passe) et le chargement de la configuration au démarrage ;
  - la sécurité : jeton d'accès, mots de passe (anti force brute), jetons d'envoi, sessions déverrouillées,
    et le contrôle d'accès aux fichiers (chemins sûrs, .env et programme protégés, noms valides).

Les autres modules font simplement `from app import config` puis utilisent `config.X` (jamais
`from app.config import X` pour une valeur modifiable à l'exécution : cela figerait sa valeur au chargement).
`config.load()` renseigne les valeurs au démarrage ; ce module n'importe aucun autre module de l'application.
"""

import hashlib
import hmac
import os
import re
import secrets
import shutil
import threading
import time
from pathlib import Path

# =====================================================================================================
# Emplacements
# =====================================================================================================
HERE = Path(__file__).resolve().parent.parent   # racine du projet (dossier de server.py)
BUNDLE = HERE / "editor.bundle.js"              # éditeur de texte (bundle JavaScript)
CACHE = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / "biblio"   # miniatures, tags audio
CONFIG_DIR = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "biblio"
BLOCKLIST_PATH = CONFIG_DIR / "blocked_devices.json"   # appareils bloqués (tableau de bord)
HISTORY_PATH = CONFIG_DIR / "history.json"             # historique d'activité (tableau de bord)

# =====================================================================================================
# Renseignés au démarrage par load()
# =====================================================================================================
# Dossier servi : celui passé en argument, sinon le dossier courant.
ROOT = Path(os.environ.get("BIBLIO_DOCS", Path.cwd())).resolve()
ROOT_ID = ""
PORT = int(os.environ.get("BIBLIO_PORT", "8088"))
READONLY = False
TOKEN = ""
PASSWORD = ""        # BIBLIO_PASSWORD (.env) : vide = suppression, renommage et envoi désactivés (aucun déverrouillage possible)
DASH_PASSWORD = ""   # BIBLIO_DASHBOARD_PASSWORD (.env), à défaut BIBLIO_PASSWORD : vide = tableau de bord désactivé
ENV_PATH = None      # fichier .env (jeton, mot de passe)
ENV = {}             # valeurs lues dans le .env
PDFJS_DIR = None     # dossier contenant legacy/web/viewer.html (pdf.js), s'il est trouvé
DISKS = [("/mnt/ext0", "Disque externe"), ("/sdcard", "Stockage interne")]   # BIBLIO_DISKS=chemin=Nom;chemin=Nom

# =====================================================================================================
# Limites
# =====================================================================================================
MAX_TEXT = 2 * 1024 * 1024        # lecture / édition
MAX_SAVE = 5 * 1024 * 1024        # enregistrement
MAX_UPLOAD = 4096 * 1024 * 1024   # taille max d'un fichier envoyé (BIBLIO_MAX_UPLOAD_MB, 0 = illimité)
UPLOAD_CHUNK = 1024 * 1024
UPLOAD_MIN_FREE = 64 * 1024 * 1024    # espace disque à toujours laisser libre
DRAIN_MAX = 512 * 1024 * 1024         # corps d'une requête refusée que l'on accepte de lire et jeter

# Sécurité : essais de mot de passe, durée de validité des jetons d'envoi, cookies
MAX_FAILS = 5          # essais de mot de passe avant verrouillage
LOCK_SECONDS = 60
TICKET_TTL = 15 * 60   # durée de validité d'un jeton d'envoi (fenêtre glissante)
AUTH_COOKIE = "fl_auth"        # cookie d'accès (contient le jeton)
UNLOCK_COOKIE = "fl_unlock"    # cookie de session déverrouillée

# =====================================================================================================
# Outils externes
# =====================================================================================================
FFMPEG = shutil.which("ffmpeg")
FFPROBE = shutil.which("ffprobe")


# =====================================================================================================
# Fichier .env
# =====================================================================================================
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
        value = (CONFIG_DIR / "token").read_text().strip()
    except (OSError, RuntimeError):
        value = ""
    value = value or secrets.token_urlsafe(12)
    try:
        write_env_value(ENV_PATH, "BIBLIO_TOKEN", value)
    except OSError as e:
        print(f"Attention : impossible d'écrire {ENV_PATH} ({e.strerror}) : le jeton ne sera pas conservé.")
    return value


def env_permissions_warning():
    """Message d'avertissement si le .env est lisible par d'autres utilisateurs, sinon chaîne vide."""
    try:
        if ENV_PATH.stat().st_mode & 0o077:
            return f"Attention : {ENV_PATH.name} est lisible par d'autres utilisateurs (chmod 600 recommandé)."
    except (OSError, AttributeError):
        pass
    return ""


# =====================================================================================================
# Chargement de la configuration au démarrage
# =====================================================================================================
def parse_disks(text):
    """« /mnt/a=Disque A;/mnt/b=Disque B » -> [(chemin, nom), …]."""
    disks = []
    for item in text.split(";"):
        path, _, label = item.partition("=")
        path = path.strip()
        if path:
            disks.append((path, label.strip() or path))
    return disks


def find_pdfjs(cli=None):
    """Dossier contenant legacy/web/viewer.html (pdf.js) : option -j, BIBLIO_PDFJS, puis emplacements usuels."""
    candidates = [cli] if cli else []
    if os.environ.get("BIBLIO_PDFJS"):
        candidates.append(os.environ["BIBLIO_PDFJS"])
    candidates += [str(HERE), "/opt/pdf-library"]
    for c in candidates:
        d = Path(c).expanduser().resolve()
        if (d / "legacy" / "web" / "viewer.html").is_file():
            return d
    return None


def load(root, port, readonly=False, env_file=None, pdfjs=None):
    """Renseigne toute la configuration : dossier servi, port, .env, mots de passe, jeton, limites, pdf.js."""
    global ROOT, ROOT_ID, PORT, READONLY, TOKEN, PASSWORD, DASH_PASSWORD, ENV_PATH, PDFJS_DIR, DISKS, MAX_UPLOAD
    ROOT = Path(root).expanduser().resolve()
    PORT = port
    READONLY = bool(readonly)
    ENV_PATH = Path(env_file or os.environ.get("BIBLIO_ENV") or HERE / ".env").expanduser().resolve()
    ENV.clear()
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
    PDFJS_DIR = find_pdfjs(pdfjs)


# =====================================================================================================
# Sécurité : jeton d'accès, mots de passe, jetons d'envoi, sessions déverrouillées
# =====================================================================================================
def token_ok(given):
    """Vrai si `given` est le jeton d'accès (comparaison en temps constant)."""
    return bool(TOKEN) and bool(given) and hmac.compare_digest(given.encode("utf-8", "replace"), TOKEN.encode())


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


def password_scopes(given):
    """Parties que ce mot de passe déverrouille : « files » (BIBLIO_PASSWORD) et/ou « dash » (tableau de bord)."""
    raw = given.encode("utf-8", "replace")
    return {scope for scope, pw in (("files", PASSWORD), ("dash", DASH_PASSWORD))
            if pw and hmac.compare_digest(raw, pw.encode("utf-8", "replace"))}


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


# =====================================================================================================
# Sécurité : contrôle d'accès aux fichiers
# =====================================================================================================
def is_env_file(p):
    """Vrai si p est le .env (ou un lien vers lui) : il contient le jeton et le mot de passe."""
    if ENV_PATH is None:
        return False
    try:
        return p.samefile(ENV_PATH)
    except OSError:
        return False


def is_env_path(p):
    """Vrai si p désigne l'emplacement du .env (comparaison sur le nom, même si le fichier n'existe pas)."""
    return ENV_PATH is not None and os.path.normcase(str(p)) == os.path.normcase(str(ENV_PATH))


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


def holds_protected(folder):
    """Vrai si le dossier contient le .env ou le programme biblio lui-même (à ne jamais supprimer ni déplacer)."""
    try:
        f = os.path.realpath(folder)
        for target in (ENV_PATH, HERE):
            if target is not None and os.path.commonpath([f, os.path.realpath(target)]) == f:
                return True
    except (ValueError, OSError):
        return True
    return False


def valid_name(new):
    """Nom de fichier ou de dossier simple (sans chemin) et de longueur raisonnable."""
    return not (not new or new in (".", "..") or "/" in new or "\\" in new or "\x00" in new
                or len(new.encode("utf-8")) > 255)


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
