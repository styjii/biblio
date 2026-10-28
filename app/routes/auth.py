"""Verrouillage / déverrouillage de l'accès."""

import hmac

from app import config
from app.security import check_password, drop_dash_session, grant_unlock, unlock_scopes


class AuthRoutes:
    def route_lock_state(self):
        scopes = unlock_scopes(self.dash_session_id())
        self.send_json({"enabled": bool(config.PASSWORD or config.DASH_PASSWORD), "unlocked": bool(scopes),
                        "files": "files" in scopes, "dash": "dash" in scopes})

    def route_unlock(self):
        """POST /unlock ; corps : mot de passe (BIBLIO_PASSWORD ou BIBLIO_DASHBOARD_PASSWORD) -> session déverrouillée."""
        if not (config.PASSWORD or config.DASH_PASSWORD):
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
        ok, msg = check_password(self.client_address[0], given, [config.PASSWORD, config.DASH_PASSWORD])
        if not ok:
            self.send_json({"ok": False, "error": msg}, 429 if msg.startswith("Trop") else 403)
            return
        raw = given.encode("utf-8", "replace")
        scopes = {scope for scope, pw in (("files", config.PASSWORD), ("dash", config.DASH_PASSWORD))
                  if pw and hmac.compare_digest(raw, pw.encode("utf-8", "replace"))}
        sid = grant_unlock(self.dash_session_id(), scopes)
        self.send_json({"ok": True, "files": "files" in scopes, "dash": "dash" in scopes},
                       extra={"Set-Cookie": f"fl_unlock={sid}; Path=/; HttpOnly; SameSite=Strict"})

    def route_lock(self):
        drop_dash_session(self.dash_session_id())
        self.send_json({"ok": True}, extra={"Set-Cookie": "fl_unlock=; Path=/; HttpOnly; SameSite=Strict; Max-Age=0"})
