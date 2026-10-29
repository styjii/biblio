"""Envoi de fichiers (ticket d'envoi, puis un POST par fichier, en flux)."""

import errno
import os
import secrets
import shutil
import stat
from pathlib import Path

from app import config
from app.config import DRAIN_MAX, UPLOAD_CHUNK, UPLOAD_MIN_FREE
from app.utils import fmt_size


class UploadRoutes:
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
        """POST /upload-auth ; l'accès doit être déverrouillé -> jeton d'envoi."""
        if config.READONLY:
            self.send_json({"ok": False, "error": "Mode lecture seule"}, 403)
            return
        if not config.PASSWORD:
            self.send_json({"ok": False, "error": "Envoi désactivé : BIBLIO_PASSWORD absent du .env"}, 403)
            return
        if "files" not in config.sessions.scopes(self.dash_session_id()):
            self.send_json({"ok": False, "error": "Accès verrouillé", "locked": True}, 403)
            return
        self.send_json({"ok": True, "ticket": config.tickets.issue(), "ttl": config.TICKET_TTL})

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
        if config.READONLY:
            return self.upload_error(length, "Mode lecture seule", 403)
        if not config.PASSWORD:
            return self.upload_error(length, "Envoi désactivé : BIBLIO_PASSWORD absent du .env", 403)
        if "files" not in config.sessions.scopes(self.dash_session_id()):
            return self.upload_error(length, "Accès verrouillé", 403, "locked")
        if not config.tickets.use(self.headers.get("X-Upload-Ticket", "")):
            return self.upload_error(length, "Session d'envoi expirée : rouvre « Envoyer »", 403, "ticket")
        if config.MAX_UPLOAD and length > config.MAX_UPLOAD:
            return self.upload_error(length, f"Fichier trop volumineux (maximum {fmt_size(config.MAX_UPLOAD)})", 413)

        parts = config.paths.clean_upload_name(arg("n"))
        if parts is None:
            return self.upload_error(length, "Nom de fichier invalide", 400)
        folder = config.paths.resolve(arg("d"))
        if folder is None:
            return self.upload_error(length, "Dossier non autorisé", 403)
        if not folder.is_dir():
            return self.upload_error(length, "Dossier de destination introuvable", 404)
        final = Path(os.path.normpath(folder.joinpath(*parts)))
        try:
            final.relative_to(config.ROOT)
        except ValueError:
            return self.upload_error(length, "Chemin non autorisé", 403)
        if config.paths.is_env_file(final):
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
