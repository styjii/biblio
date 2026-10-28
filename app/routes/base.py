"""Socle du gestionnaire HTTP : envoi des réponses, cookies, session."""

import hmac
import json
import re
from http.cookies import SimpleCookie
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler
from urllib.parse import parse_qs, unquote, urlsplit

from app import config
from app.devices import add_bytes, classify, is_blocked, record_event, track_device
from app.security import unlock_scopes
from app.views.layout import error_page, message_page


class BaseHandler(BaseHTTPRequestHandler):
    server_version = "Biblio/1.0"

    _entry = None      # action d'historique de la requête en cours (voir parse_request)

    def send_bytes(self, content, ctype, status=200, extra=None):
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(content)))
        self.send_header("X-Content-Type-Options", "nosniff")
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(content)
        add_bytes(self._entry, len(content))

    # Ressources chargées par la page elle-même (vignettes, sous-titres, scripts…) : erreur brute, sans page HTML.
    _PLAIN_ERROR_PREFIXES = ("/thumb", "/cover", "/meta", "/sub", "/static/", "/docs/", "/legacy/",
                             "/build/", "/web/", "/dashboard/", "/s/")

    def send_error(self, code, message=None, explain=None):
        """Réponse d'erreur : page HTML aux couleurs de l'application pour une navigation (GET),
        réponse HTTP standard pour le reste (POST, HEAD, ressources internes, codes sans corps)."""
        path = unquote(urlsplit(getattr(self, "path", "") or "").path)
        if (self.command != "GET" or code < 400 or path.startswith(self._PLAIN_ERROR_PREFIXES)):
            return super().send_error(code, message, explain)
        self.log_error("code %d, message %s", code, message)
        where = path if len(path) <= 200 else path[:197] + "…"
        self.close_connection = True
        try:
            body = error_page(code, message or "", where)
        except Exception:                       # jamais d'échec dans la page d'erreur elle-même
            return super().send_error(code, message, explain)
        reason = HTTPStatus(code).phrase if code in HTTPStatus._value2member_map_ else "Erreur"
        self.send_response(code, reason)
        self.send_bytes_body(body.encode("utf-8"), "text/html; charset=utf-8",
                             {"Cache-Control": "no-store", "Connection": "close"})

    def send_bytes_body(self, content, ctype, extra=None):
        """Fin d'une réponse dont send_response() a déjà été appelé."""
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(content)))
        self.send_header("X-Content-Type-Options", "nosniff")
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(content)
        add_bytes(self._entry, len(content))

    def send_html(self, html, status=200):
        self.send_bytes(html.encode("utf-8"), "text/html; charset=utf-8", status,
                        {"Cache-Control": "no-store"})

    def send_json(self, obj, status=200, extra=None):
        self.send_bytes(json.dumps(obj).encode(), "application/json", status,
                        {"Cache-Control": "no-store", **(extra or {})})

    def send_file(self, path, ctype, disposition=None, extra=None):
        try:
            size = path.stat().st_size
        except OSError:
            self.send_error(404)
            return
        start, end, status = 0, size - 1, 200
        header = self.headers.get("Range")
        if header:
            m = re.match(r"bytes=(\d*)-(\d*)$", header.strip())
            if m and (m.group(1) or m.group(2)):
                s, e = m.groups()
                if s == "":
                    start = max(size - int(e), 0)
                else:
                    start = int(s)
                    if e:
                        end = min(int(e), size - 1)
                if start > end or start >= size:
                    self.send_response(416)
                    self.send_header("Content-Range", f"bytes */{size}")
                    self.send_header("Content-Length", "0")
                    self.end_headers()
                    return
                status = 206
        length = max(end - start + 1, 0)
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Content-Length", str(length))
        self.send_header("X-Content-Type-Options", "nosniff")
        if status == 206:
            self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        if disposition:
            self.send_header("Content-Disposition", disposition)
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        try:
            with open(path, "rb") as f:
                f.seek(start)
                remaining = length
                while remaining > 0:
                    chunk = f.read(min(256 * 1024, remaining))
                    if not chunk:
                        break
                    self.wfile.write(chunk)
                    add_bytes(self._entry, len(chunk))
                    remaining -= len(chunk)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def parse_request(self):
        if not super().parse_request():
            return False
        ip = self.client_address[0]
        if is_blocked(ip):
            self.close_connection = True
            self.send_html(message_page("Accès bloqué", "Cet appareil a été bloqué par l'administrateur."), 403)
            return False
        req = urlsplit(self.path)
        authed = self.has_cookie()
        track_device(ip, self.headers.get("User-Agent", ""), authed, hit=not req.path.startswith("/dashboard/"))
        self._entry = None
        if not req.path.startswith("/dashboard"):
            if req.path.startswith("/s/"):     # les aperçus web s'authentifient par le jeton dans l'URL
                parts = req.path.split("/", 3)
                authed = authed or (len(parts) > 2 and hmac.compare_digest(
                    unquote(parts[2]).encode("utf-8", "replace"), config.TOKEN.encode()))
            if authed:
                action = classify(req.path, parse_qs(req.query))
                if action:
                    self._entry = record_event(ip, *action)
        return True

    def has_cookie(self):
        c = SimpleCookie()
        try:
            c.load(self.headers.get("Cookie", ""))
        except Exception:
            return False
        m = c.get("fl_auth")
        return bool(m) and hmac.compare_digest(m.value.encode("utf-8", "replace"), config.TOKEN.encode())

    def page_locked(self):
        html = message_page(
            "Accès protégé",
            "Ouvre le lien complet affiché dans le terminal au démarrage de biblio "
            "(il se termine par ?token=…).")
        self.send_html(html, 401)

    def files_locked(self):
        """Vrai si un mot de passe est configuré et que cette session n'est pas déverrouillée."""
        return bool(config.PASSWORD) and "files" not in unlock_scopes(self.dash_session_id())

    def dash_session_id(self):
        c = SimpleCookie()
        try:
            c.load(self.headers.get("Cookie", ""))
        except Exception:
            return ""
        m = c.get("fl_unlock")
        return m.value if m else ""
