"""Écriture : enregistrement, suppression et renommage (accès déverrouillé requis)."""

import os
import stat
from pathlib import Path

from app import config
from app.config import MAX_SAVE
from app.filesystem import is_binary_file, resolve_inside
from app.security import unlock_scopes
from app.utils import fmt_size


class EditRoutes:
    def route_save(self, q):
        def arg(name, default=""):
            return q.get(name, [default])[0]

        if config.READONLY:
            self.send_json({"ok": False, "error": "Mode lecture seule"}, 403)
            return
        if config.PASSWORD and "files" not in unlock_scopes(self.dash_session_id()):
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
        if config.READONLY:
            self.send_json({"ok": False, "error": "Mode lecture seule"}, 403)
            return
        if not config.PASSWORD:
            self.send_json({"ok": False, "error": "Suppression désactivée : BIBLIO_PASSWORD absent du .env"}, 403)
            return
        if "files" not in unlock_scopes(self.dash_session_id()):
            self.send_json({"ok": False, "error": "Accès verrouillé", "locked": True}, 403)
            return

        p = resolve_inside(q.get("f", [""])[0])
        if p is None or p == config.ROOT:
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

    def route_rename(self, q):
        """POST /rename?f=<chemin>&to=<nouveau nom> ; l'accès doit être déverrouillé (comme la suppression)."""
        if config.READONLY:
            self.send_json({"ok": False, "error": "Mode lecture seule"}, 403)
            return
        if not config.PASSWORD:
            self.send_json({"ok": False, "error": "Renommage désactivé : BIBLIO_PASSWORD absent du .env"}, 403)
            return
        if "files" not in unlock_scopes(self.dash_session_id()):
            self.send_json({"ok": False, "error": "Accès verrouillé", "locked": True}, 403)
            return
        p = resolve_inside(q.get("f", [""])[0])
        if p is None or p == config.ROOT:
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
        if config.ENV_PATH is not None and os.path.normcase(str(target)) == os.path.normcase(str(config.ENV_PATH)):
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
