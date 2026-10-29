"""Ligne de commande : lecture des options, configuration, démarrage du serveur HTTP."""

import argparse
import signal
import threading
from http.server import ThreadingHTTPServer
from pathlib import Path

from app import config
from app.config import BUNDLE, FFMPEG
from app.devices import (LOCAL_IPS, blocked_count, handle_sigterm, history_flusher, load_blocklist, load_history,
                         save_history)
from app.handler import FileHandler
from app.utils import fmt_size, lan_ips


def main():
    parser = argparse.ArgumentParser(description="Bibliothèque : documents, vidéos, texte et code")
    parser.add_argument("dossier", nargs="?", default=str(config.ROOT),
                        help="dossier à servir (défaut : dossier courant)")
    parser.add_argument("-p", "--port", type=int, default=config.PORT)
    parser.add_argument("-r", "--readonly", action="store_true", help="désactive l'édition")
    parser.add_argument("-e", "--env", help="fichier .env : BIBLIO_TOKEN, BIBLIO_PASSWORD (défaut : .env à côté de server.py)")
    parser.add_argument("-j", "--pdfjs", help="dossier contenant legacy/web/viewer.html (pdf.js)")
    args = parser.parse_args()

    root = Path(args.dossier).expanduser().resolve()
    if not root.is_dir():
        parser.error(f"dossier introuvable : {root}")
    config.load(root, args.port, args.readonly, args.env, args.pdfjs)
    LOCAL_IPS.update(lan_ips())
    load_blocklist()
    load_history()
    threading.Thread(target=history_flusher, daemon=True).start()
    signal.signal(signal.SIGTERM, handle_sigterm)

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
    if config.env_permissions_warning():
        print(config.env_permissions_warning())
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
