"""Gestionnaire HTTP : assemble les routes et répartit les requêtes GET / POST."""

import hmac
from urllib.parse import parse_qs, urlencode, urlsplit

from app import config
from app.routes.auth import AuthRoutes
from app.routes.base import BaseHandler
from app.routes.browse import BrowseRoutes
from app.routes.dashboard import DashboardRoutes
from app.routes.edit import EditRoutes
from app.routes.player import PlayerRoutes
from app.routes.serve import ServeRoutes
from app.routes.upload import UploadRoutes
from app.routes.viewer import ViewerRoutes

POSTS = ("/save", "/delete", "/rename", "/mkdir", "/upload-auth", "/upload", "/unlock", "/lock")
DASH_POSTS = ("/dashboard/block", "/dashboard/unblock")


class FileHandler(BaseHandler, BrowseRoutes, ViewerRoutes, PlayerRoutes, ServeRoutes, EditRoutes, UploadRoutes,
                  AuthRoutes, DashboardRoutes):
    """Un gestionnaire = le socle HTTP + une famille de routes par module de `app/routes/`."""

    def do_GET(self):
        req = urlsplit(self.path)
        q = parse_qs(req.query)
        path = req.path

        def arg(name):
            return q.get(name, [""])[0]

        try:
            if path.startswith("/s/"):
                return self.route_site(path)

            tok = arg("token")
            if tok and hmac.compare_digest(tok.encode("utf-8", "replace"), config.TOKEN.encode()):
                rest = {k: v for k, v in q.items() if k != "token"}
                loc = "/" + path.lstrip("/") + ("?" + urlencode(rest, doseq=True) if rest else "")
                self.send_response(302)
                self.send_header("Location", loc)
                self.send_header("Set-Cookie",
                                 f"fl_auth={config.TOKEN}; Path=/; HttpOnly; SameSite=Strict; Max-Age=31536000")
                self.send_header("Content-Length", "0")
                self.end_headers()
                return
            if not self.has_cookie():
                return self.page_locked()

            if path == "/":
                self.page_browse(arg("folder"))
            elif path == "/view":
                self.page_text(arg("f"), edit=False)
            elif path == "/edit":
                self.page_text(arg("f"), edit=True, new=arg("new") == "1")
            elif path == "/preview":
                self.page_preview(arg("f"))
            elif path == "/raw":
                self.route_raw(arg("f"), arg("dl") == "1")
            elif path == "/static/editor.js":
                self.route_bundle()
            elif path == "/lock-state":
                self.route_lock_state()
            elif path == "/watch":
                self.page_watch(arg("f"))
            elif path == "/listen":
                self.page_listen(arg("f"))
            elif path == "/thumb":
                self.serve_thumb(arg("f"))
            elif path == "/meta":
                self.serve_meta(arg("f"))
            elif path == "/cover":
                self.serve_cover(arg("f"))
            elif path == "/sub":
                self.serve_sub(arg("f"))
            elif path == "/pdf":
                self.route_pdf(arg("f"))
            elif path == "/zip":
                self.route_zip(arg("f"))
            elif path == "/dashboard":
                self.page_dashboard()
            elif path == "/dashboard/data":
                self.route_dash_data()
            elif path == "/dashboard/history":
                self.route_dash_history(q)
            elif path.startswith("/docs/"):
                self.route_docs(path)
            elif path.startswith(("/legacy/", "/build/", "/web/")):
                self.route_pdfjs(path)
            else:
                self.send_error(404, "Page introuvable")
        except (BrokenPipeError, ConnectionResetError):
            pass

    def do_POST(self):
        req = urlsplit(self.path)
        q = parse_qs(req.query)
        try:
            if req.path not in POSTS + DASH_POSTS:
                self.send_error(404)
                return
            if not self.has_cookie() or self.headers.get("X-Requested-With") != "biblio":
                self.send_json({"ok": False, "error": "Non autorisé"}, 403)
                return
            if req.path in DASH_POSTS:
                self.route_dash_post(req.path, q)
            elif req.path == "/unlock":
                self.route_unlock()
            elif req.path == "/lock":
                self.route_lock()
            elif req.path == "/delete":
                self.route_delete(q)
            elif req.path == "/rename":
                self.route_rename(q)
            elif req.path == "/mkdir":
                self.route_mkdir(q)
            elif req.path == "/upload-auth":
                self.route_upload_auth()
            elif req.path == "/upload":
                self.route_upload(q)
            else:
                self.route_save(q)
        except (BrokenPipeError, ConnectionResetError):
            pass
