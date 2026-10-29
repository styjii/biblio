"""Ligne de commande : lecture des options, configuration, démarrage du serveur HTTP."""

import argparse
import signal
from http.server import ThreadingHTTPServer
from pathlib import Path

from app import config
from app.devices import monitor
from app.handler import FileHandler
from app.utils import fmt_size, lan_ips


class Application:
    """Une exécution de biblio : options -> configuration -> surveillance des appareils -> serveur HTTP."""

    def __init__(self):
        self.args = None
        self.server = None

    # --- options ---
    @staticmethod
    def build_parser():
        parser = argparse.ArgumentParser(description="Bibliothèque : documents, vidéos, texte et code")
        parser.add_argument("dossier", nargs="?", default=str(config.ROOT),
                            help="dossier à servir (défaut : dossier courant)")
        parser.add_argument("-p", "--port", type=int, default=config.PORT)
        parser.add_argument("-r", "--readonly", action="store_true", help="désactive l'édition")
        parser.add_argument("-e", "--env", help="fichier .env : BIBLIO_TOKEN, BIBLIO_PASSWORD (défaut : .env à côté de server.py)")
        parser.add_argument("-j", "--pdfjs", help="dossier contenant legacy/web/viewer.html (pdf.js)")
        return parser

    def configure(self):
        parser = self.build_parser()
        self.args = parser.parse_args()
        root = Path(self.args.dossier).expanduser().resolve()
        if not root.is_dir():
            parser.error(f"dossier introuvable : {root}")
        config.load(root, self.args.port, self.args.readonly, self.args.env, self.args.pdfjs)

    # --- messages de démarrage ---
    @staticmethod
    def print_status():
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
            print(f"Tableau de bord : activé (/dashboard), {len(monitor.blocklist)} appareil(s) bloqué(s).")
        else:
            print("Tableau de bord : désactivé (définis BIBLIO_DASHBOARD_PASSWORD ou BIBLIO_PASSWORD dans le .env).")
        warning = config.env.permissions_warning()
        if warning:
            print(warning)
        if not config.BUNDLE.is_file():
            print(f"Attention : {config.BUNDLE.name} introuvable à côté de server.py, la lecture et l'édition de texte ne fonctionneront pas.")
        if not config.FFMPEG:
            print("ffmpeg introuvable : pas de miniatures ni de durées pour les vidéos (sudo apt install ffmpeg).")
        if config.PDFJS_DIR is None:
            print("pdf.js introuvable : les PDF s'ouvriront avec le lecteur du navigateur (voir l'option --pdfjs).")

    @staticmethod
    def print_links():
        print(f"Local   : http://localhost:{config.PORT}/?token={config.TOKEN}")
        for ip in lan_ips():
            print(f"Réseau  : http://{ip}:{config.PORT}/?token={config.TOKEN}")
        print("Garde ce lien privé : il donne accès aux fichiers" + ("." if config.READONLY else " et permet de les modifier."))
        print("Ctrl+C pour arrêter.")

    # --- exécution ---
    @staticmethod
    def _on_sigterm(signum, frame):
        raise SystemExit(0)     # kill / arrêt du système : passe par le « finally » qui enregistre l'historique

    def run(self):
        self.configure()
        monitor.start()
        signal.signal(signal.SIGTERM, self._on_sigterm)
        self.print_status()
        self.server = ThreadingHTTPServer(("0.0.0.0", config.PORT), FileHandler)
        self.print_links()
        try:
            self.server.serve_forever()
        except KeyboardInterrupt:
            print("\nArrêt.")
        finally:
            monitor.stop()


def main():
    Application().run()
