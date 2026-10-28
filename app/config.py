"""Réglages du serveur.

Les valeurs modifiables à l'exécution (dossier servi, jeton, mots de passe…) sont lues par les autres
modules via `config.X` (jamais `from app.config import X`, qui figerait la valeur au chargement).
`app.cli.main()` les renseigne au démarrage.
"""

import os
import shutil
from pathlib import Path

# --- Emplacements -----------------------------------------------------------------------------------
HERE = Path(__file__).resolve().parent.parent   # racine du projet (dossier de server.py)
BUNDLE = HERE / "editor.bundle.js"              # éditeur de texte (bundle JavaScript)
CACHE = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / "biblio"   # miniatures, tags audio

# --- Renseignés au démarrage par app.cli.main() ----------------------------------------------------
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

# --- Limites ---------------------------------------------------------------------------------------
MAX_TEXT = 2 * 1024 * 1024        # lecture / édition
MAX_SAVE = 5 * 1024 * 1024        # enregistrement
MAX_UPLOAD = 4096 * 1024 * 1024   # taille max d'un fichier envoyé (BIBLIO_MAX_UPLOAD_MB, 0 = illimité)
UPLOAD_CHUNK = 1024 * 1024
UPLOAD_MIN_FREE = 64 * 1024 * 1024    # espace disque à toujours laisser libre
DRAIN_MAX = 512 * 1024 * 1024         # corps d'une requête refusée que l'on accepte de lire et jeter

# --- Outils externes -------------------------------------------------------------------------------
FFMPEG = shutil.which("ffmpeg")
FFPROBE = shutil.which("ffprobe")
