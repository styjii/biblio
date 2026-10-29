"""Verrouillage / déverrouillage de l'accès."""

from app import config


class AuthRoutes:
    def route_lock_state(self):
        scopes = config.sessions.scopes(self.dash_session_id())
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
        ok, msg = config.passwords.check(self.client_address[0], given, [config.PASSWORD, config.DASH_PASSWORD])
        if not ok:
            self.send_json({"ok": False, "error": msg}, 429 if msg.startswith("Trop") else 403)
            return
        scopes = config.passwords.scopes(given)
        sid = config.sessions.grant(self.dash_session_id(), scopes)
        self.send_json({"ok": True, "files": "files" in scopes, "dash": "dash" in scopes},
                       extra={"Set-Cookie": f"{config.UNLOCK_COOKIE}={sid}; Path=/; HttpOnly; SameSite=Strict"})

    def route_lock(self):
        config.sessions.drop(self.dash_session_id())
        self.send_json({"ok": True}, extra={"Set-Cookie": f"{config.UNLOCK_COOKIE}=; Path=/; HttpOnly; SameSite=Strict; Max-Age=0"})
