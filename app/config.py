"""Configuration et sécurité de biblio : tout est centralisé ici.

Ce module regroupe :
  - les emplacements, réglages et limites du serveur ;
  - la lecture du fichier .env (jeton d'accès, mots de passe) et le chargement de la configuration au démarrage ;
  - la sécurité : jeton d'accès, mots de passe (anti force brute), jetons d'envoi, sessions déverrouillées,
    et le contrôle d'accès aux fichiers (chemins sûrs, .env et programme protégés, noms valides).

Les autres modules font simplement `from app import config` puis utilisent `config.X` (jamais
`from app.config import X` pour une valeur modifiable à l'exécution : cela figerait sa valeur au chargement).
`config.load()` renseigne les valeurs au démarrage. Les comportements sont portés par des classes, chacune
avec une instance prête à l'emploi : `env` (EnvFile), `passwords` (PasswordGuard), `tickets` (TicketStore),
`sessions` (SessionStore) et `paths` (PathGuard). Ce module n'importe que `app.utils` (sans dépendance).
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

from app.utils import atomic_write

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
class EnvFile:
    """Fichier .env (CLE=valeur) : jeton d'accès et mots de passe. Une variable d'environnement de même nom l'emporte."""

    def __init__(self, path=None):
        self.path = path
        self.values = {}

    def load(self, path):
        self.path = path
        self.values = self.read(path)

    @staticmethod
    def read(path):
        """Lit un fichier .env (CLE=valeur, # commentaires, « export », guillemets facultatifs)."""
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

    def get(self, key):
        """Variable d'environnement si définie, sinon valeur du .env, sinon chaîne vide."""
        return os.environ.get(key) or self.values.get(key) or ""

    def set(self, key, value):
        """Ajoute ou remplace CLE=valeur dans le fichier (écriture atomique, droits 0600)."""
        try:
            lines = self.path.read_text(encoding="utf-8-sig").splitlines()
        except OSError:
            lines = []
        pattern = re.compile(rf"\s*(export\s+)?{re.escape(key)}\s*=")
        for i, line in enumerate(lines):
            if pattern.match(line):
                lines[i] = f"{key}={value}"
                break
        else:
            lines.append(f"{key}={value}")
        atomic_write(self.path, "\n".join(lines) + "\n")
        self.values[key] = value

    def permissions_warning(self):
        """Message d'avertissement si le fichier est lisible par d'autres utilisateurs, sinon chaîne vide."""
        try:
            if self.path.stat().st_mode & 0o077:
                return f"Attention : {self.path.name} est lisible par d'autres utilisateurs (chmod 600 recommandé)."
        except (OSError, AttributeError):
            pass
        return ""


env = EnvFile()


def _load_token():
    """Jeton d'accès : BIBLIO_TOKEN (environnement ou .env). Absent, il est créé et écrit dans le .env."""
    value = env.get("BIBLIO_TOKEN")
    if value:
        return value
    try:        # migration : ancien emplacement ~/.config/biblio/token
        value = (CONFIG_DIR / "token").read_text().strip()
    except (OSError, RuntimeError):
        value = ""
    value = value or secrets.token_urlsafe(12)
    try:
        env.set("BIBLIO_TOKEN", value)
    except OSError as e:
        print(f"Attention : impossible d'écrire {env.path} ({e.strerror}) : le jeton ne sera pas conservé.")
    return value


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
    env.load(ENV_PATH)
    PASSWORD = env.get("BIBLIO_PASSWORD")
    DASH_PASSWORD = env.get("BIBLIO_DASHBOARD_PASSWORD") or PASSWORD
    if env.get("BIBLIO_DISKS"):
        DISKS = parse_disks(env.get("BIBLIO_DISKS"))
    TOKEN = _load_token()
    try:
        MAX_UPLOAD = max(0, int(env.get("BIBLIO_MAX_UPLOAD_MB") or 4096)) * 1024 * 1024
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


class PasswordGuard:
    """Vérification des mots de passe, avec verrouillage temporaire par adresse IP (anti force brute)."""

    def __init__(self):
        self._lock = threading.Lock()
        self._fails = {}       # ip -> (essais, verrouillé jusqu'à)

    def check(self, ip, given, expected=None):
        """Vérifie un mot de passe (par défaut celui de BIBLIO_PASSWORD). -> (ok, message)"""
        expected = PASSWORD if expected is None else expected
        candidates = [e for e in ([expected] if isinstance(expected, str) else expected) if e]
        now = time.monotonic()
        with self._lock:
            count, until = self._fails.get(ip, (0, 0.0))
            if until > now:
                return False, f"Trop d'essais, réessaie dans {int(until - now) + 1} s."
            if until:                       # verrou expiré : on repart de zéro
                count = 0
            count += 1                      # l'essai est compté avant la vérification (essais parallèles)
            self._fails[ip] = (count, now + LOCK_SECONDS if count >= MAX_FAILS else 0.0)
        raw = given.encode("utf-8", "replace")
        ok = any([hmac.compare_digest(raw, e.encode("utf-8", "replace")) for e in candidates])
        if ok:
            with self._lock:
                self._fails.pop(ip, None)
            return True, ""
        time.sleep(0.5)                     # ralentit les essais successifs
        return False, "Mot de passe incorrect."

    @staticmethod
    def scopes(given):
        """Parties que ce mot de passe déverrouille : « files » (BIBLIO_PASSWORD) et/ou « dash » (tableau de bord)."""
        raw = given.encode("utf-8", "replace")
        return {scope for scope, pw in (("files", PASSWORD), ("dash", DASH_PASSWORD))
                if pw and hmac.compare_digest(raw, pw.encode("utf-8", "replace"))}


class TicketStore:
    """Jetons d'envoi à usage limité (obtenus avec le mot de passe, valables pour /upload uniquement)."""
    MAX_TICKETS = 50

    def __init__(self):
        self._lock = threading.Lock()
        self._expires = {}              # jeton -> expiration (monotonic)

    def issue(self):
        now = time.monotonic()
        with self._lock:
            for t in [t for t, exp in self._expires.items() if exp < now]:
                del self._expires[t]
            while len(self._expires) >= self.MAX_TICKETS:
                del self._expires[min(self._expires, key=self._expires.get)]
            ticket = secrets.token_urlsafe(24)
            self._expires[ticket] = now + TICKET_TTL
        return ticket

    def use(self, ticket):
        """Vrai si le jeton est valide ; sa validité est alors prolongée."""
        now = time.monotonic()
        with self._lock:
            exp = self._expires.get(ticket)
            if exp is None or exp < now:
                self._expires.pop(ticket, None)
                return False
            self._expires[ticket] = now + TICKET_TTL
        return True


class SessionStore:
    """Sessions déverrouillées : identifiant -> parties déverrouillées. En mémoire : tout est verrouillé au redémarrage."""
    MAX_SESSIONS = 50

    def __init__(self):
        self._lock = threading.Lock()
        self._scopes = {}

    def scopes(self, sid):
        """Parties déverrouillées de cette session : "files" (renommage, suppression, envoi) et/ou "dash"."""
        if not sid:
            return set()
        with self._lock:
            return set(self._scopes.get(sid, ()))

    def has(self, sid, scope):
        return scope in self.scopes(sid)

    def grant(self, sid, scopes):
        """Ajoute des parties à la session (nouvelle session si `sid` est inconnu) -> identifiant de session."""
        with self._lock:
            if sid not in self._scopes:
                while len(self._scopes) >= self.MAX_SESSIONS:
                    del self._scopes[next(iter(self._scopes))]
                sid = secrets.token_urlsafe(24)
                self._scopes[sid] = set()
            self._scopes[sid] |= set(scopes)
        return sid

    def drop(self, sid):
        with self._lock:
            self._scopes.pop(sid, None)


# =====================================================================================================
# Sécurité : contrôle d'accès aux fichiers
# =====================================================================================================
class PathGuard:
    """Ce qu'on a le droit de lire, modifier ou nommer : chemins sous le dossier servi, .env et programme protégés."""

    @staticmethod
    def is_env_file(p):
        """Vrai si p est le .env (ou un lien vers lui) : il contient le jeton et le mot de passe."""
        if ENV_PATH is None:
            return False
        try:
            return p.samefile(ENV_PATH)
        except OSError:
            return False

    @staticmethod
    def is_env_path(p):
        """Vrai si p désigne l'emplacement du .env (comparaison sur le nom, même si le fichier n'existe pas)."""
        return ENV_PATH is not None and os.path.normcase(str(p)) == os.path.normcase(str(ENV_PATH))

    def resolve(self, rel):
        """Chemin *logique* sous ROOT : les liens symboliques ne sont pas résolus, de sorte
        qu'un raccourci vers un dossier se comporte comme un vrai dossier (même hors de ROOT).
        Seuls les « .. » et les chemins absolus sont neutralisés, de façon purement lexicale. None si interdit."""
        if "\x00" in rel:
            return None
        p = Path(os.path.normpath(ROOT / rel))
        try:
            p.relative_to(ROOT)
        except ValueError:
            return None
        if self.is_env_file(p):
            return None
        return p

    @staticmethod
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

    @staticmethod
    def valid_name(new):
        """Nom de fichier ou de dossier simple (sans chemin) et de longueur raisonnable."""
        return not (not new or new in (".", "..") or "/" in new or "\\" in new or "\x00" in new
                    or len(new.encode("utf-8")) > 255)

    @staticmethod
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


passwords = PasswordGuard()
tickets = TicketStore()
sessions = SessionStore()
paths = PathGuard()
