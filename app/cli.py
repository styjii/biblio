"""Ligne de commande : lecture des options, configuration, démarrage du serveur HTTP."""

import argparse
import hashlib
import os
import signal
import threading
from http.server import ThreadingHTTPServer
from pathlib import Path

from app import config
from app.config import BUNDLE, FFMPEG, HERE
from app.devices import (LOCAL_IPS, blocked_count, handle_sigterm, history_flusher, load_blocklist, load_history,
                         save_history)
from app.envfile import conf, load_token, read_env
from app.handler import FileHandler
from app.sysinfo import parse_disks
from app.utils import fmt_size, lan_ips


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
    parser = argparse.ArgumentParser(description="Bibliothèque : documents, vidéos, texte et code")
    parser.add_argument("dossier", nargs="?", default=str(config.ROOT),
                        help="dossier à servir (défaut : dossier courant)")
    parser.add_argument("-p", "--port", type=int, default=config.PORT)
    parser.add_argument("-r", "--readonly", action="store_true", help="désactive l'édition")
    parser.add_argument("-e", "--env", help="fichier .env : BIBLIO_TOKEN, BIBLIO_PASSWORD (défaut : .env à côté de server.py)")
    parser.add_argument("-j", "--pdfjs", help="dossier contenant legacy/web/viewer.html (pdf.js)")
    args = parser.parse_args()

    config.ROOT = Path(args.dossier).expanduser().resolve()
    config.PORT = args.port
    config.READONLY = args.readonly
    if not config.ROOT.is_dir():
        parser.error(f"dossier introuvable : {config.ROOT}")
    config.ENV_PATH = Path(args.env or os.environ.get("BIBLIO_ENV") or HERE / ".env").expanduser().resolve()
    config.ENV.update(read_env(config.ENV_PATH))
    config.PASSWORD = conf("BIBLIO_PASSWORD")
    config.DASH_PASSWORD = conf("BIBLIO_DASHBOARD_PASSWORD") or config.PASSWORD
    if conf("BIBLIO_DISKS"):
        config.DISKS = parse_disks(conf("BIBLIO_DISKS"))
    config.TOKEN = load_token()
    try:
        config.MAX_UPLOAD = max(0, int(conf("BIBLIO_MAX_UPLOAD_MB") or 4096)) * 1024 * 1024
    except ValueError:
        print("Attention : BIBLIO_MAX_UPLOAD_MB invalide, valeur par défaut (4096 Mo) utilisée.")
    config.ROOT_ID = hashlib.sha1(str(config.ROOT).encode()).hexdigest()[:8]
    LOCAL_IPS.update(lan_ips())
    load_blocklist()
    load_history()
    threading.Thread(target=history_flusher, daemon=True).start()
    signal.signal(signal.SIGTERM, handle_sigterm)
    config.PDFJS_DIR = find_pdfjs(args.pdfjs)

    print(f"Bibliothèque : {config.ROOT}" + ("  (lecture seule)" if config.READONLY else ""))
    print(f"Configuration : {config.ENV_PATH}")
    if config.READONLY:
        pass
    elif config.PASSWORD:
        print("Suppression et envoi de fichiers : activés (mot de passe du .env).")
        print("Taille maximale par fichier envoyé : " + (fmt_size(config.MAX_UPLOAD) if config.MAX_UPLOAD else "illimitée") + ".")
    else:
        print("Suppression et envoi de fichiers : désactivés (définis BIBLIO_PASSWORD dans le .env).")
    if config.DASH_PASSWORD:
        print(f"Tableau de bord : activé (/dashboard), {blocked_count()} appareil(s) bloqué(s).")
    else:
        print("Tableau de bord : désactivé (définis BIBLIO_DASHBOARD_PASSWORD ou BIBLIO_PASSWORD dans le .env).")
    try:
        if config.ENV_PATH.stat().st_mode & 0o077:
            print(f"Attention : {config.ENV_PATH.name} est lisible par d'autres utilisateurs (chmod 600 recommandé).")
    except OSError:
        pass
    if not BUNDLE.is_file():
        print(f"Attention : {BUNDLE.name} introuvable à côté de server.py, la lecture et l'édition de texte ne fonctionneront pas.")
    if not FFMPEG:
        print("ffmpeg introuvable : pas de miniatures ni de durées pour les vidéos (sudo apt install ffmpeg).")
    if config.PDFJS_DIR is None:
        print("pdf.js introuvable : les PDF s'ouvriront avec le lecteur du navigateur (voir l'option --pdfjs).")
    server = ThreadingHTTPServer(("0.0.0.0", config.PORT), FileHandler)
    print(f"Local   : http://localhost:{config.PORT}/?token={config.TOKEN}")
    for ip in lan_ips():
        print(f"Réseau  : http://{ip}:{config.PORT}/?token={config.TOKEN}")
    print("Garde ce lien privé : il donne accès aux fichiers" + ("." if config.READONLY else " et permet de les modifier."))
    print("Ctrl+C pour arrêter.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nArrêt.")
    finally:
        save_history()
