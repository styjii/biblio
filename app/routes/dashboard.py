"""Tableau de bord : page, données, historique, blocage d'appareils."""

import ipaddress
import socket

from app import config
from app.devices import DEVICE_ACTIVE_SECONDS, device_rows, history_report, set_blocked
from app.sysinfo import read_disks, read_memory
from app.views.dashboard import dashboard_page
from app.views.layout import message_page, pill_link


class DashboardRoutes:
    def page_dashboard(self):
        if not config.DASH_PASSWORD:
            self.send_html(message_page(
                "Tableau de bord désactivé",
                "Définis BIBLIO_DASHBOARD_PASSWORD (ou BIBLIO_PASSWORD) dans le .env, puis relance biblio.",
                pill_link("/", "home", "Accueil")), 403)
            return
        self.send_html(dashboard_page(config.use_dash_session(self.dash_session_id(), touch=False)))

    def route_dash_data(self):
        if not config.use_dash_session(self.dash_session_id(), touch=False):
            self.send_json({"ok": False, "error": "Accès verrouillé"}, 401)
            return
        rows = device_rows(self.client_address[0])
        self.send_json({
            "ok": True, "host": socket.gethostname(), "memory": read_memory(), "disks": read_disks(), "devices": rows,
            "active": sum(1 for r in rows if r["active"]), "blocked": sum(1 for r in rows if r["blocked"]),
            "window": DEVICE_ACTIVE_SECONDS,
        })

    def route_dash_history(self, q):
        if not config.use_dash_session(self.dash_session_id(), touch=False):
            self.send_json({"ok": False, "error": "Accès verrouillé"}, 401)
            return
        ip = q.get("ip", ["all"])[0]
        if ip != "all":
            try:
                ip = str(ipaddress.ip_address(ip))
            except ValueError:
                self.send_json({"ok": False, "error": "Adresse IP invalide."}, 400)
                return
        self.send_json(history_report(ip, q.get("range", ["24h"])[0]))

    def route_dash_post(self, path, q):
        """POST /dashboard/block?ip=…, /dashboard/unblock?ip=… (accès déverrouillé requis)."""
        if not config.use_dash_session(self.dash_session_id()):
            self.send_json({"ok": False, "error": "Accès verrouillé", "locked": True}, 401)
            return
        ok, err, warning = set_blocked(q.get("ip", [""])[0], path == "/dashboard/block", self.client_address[0])
        if not ok:
            self.send_json({"ok": False, "error": err}, 400)
            return
        self.send_json({"ok": True, "warning": warning})
