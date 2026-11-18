"""Page d'accueil et choix du dossier d'entrée."""

from urllib.parse import quote

from app import config
from app.routes.base import BaseHandler
from app.views.home import home_page


class HomeRoutes(BaseHandler):
    def page_home(self):
        self.send_html(home_page(self.client_address[0]))

    @staticmethod
    def _local_target(target):
        """Vrai pour un chemin du serveur (« /watch?f=… ») : jamais une autre adresse (« //site », « http://… »)."""
        return (target.startswith("/") and not target.startswith("//")
                and not any(c in target for c in "\\\r\n\x00"))

    def route_open(self, root_id, target):
        """GET /open?root=<id>[&to=<chemin>] : mémorise le dossier d'entrée choisi (cookie) puis redirige."""
        mount = config.library.get(root_id)
        if mount is None or not mount.available:
            self.send_error(404, "Dossier d'entrée introuvable")
            return
        location = quote(target, safe="/?&=%:+@!$'()*,;~-._") if self._local_target(target) else "/browse"
        self.send_response(302)
        self.send_header("Location", location)
        self.send_header("Set-Cookie", f"{config.ROOT_COOKIE}={mount.id}; Path=/; HttpOnly; SameSite=Strict; Max-Age=31536000")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", "0")
        self.end_headers()
