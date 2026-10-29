"""Tableau de bord : page, données, historique, blocage d'appareils."""

import ipaddress
import socket

from app import config
from app.devices import DeviceTracker, monitor
from app.sysinfo import SystemInfo
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
        self.send_html(dashboard_page(config.sessions.has(self.dash_session_id(), "dash")))

    def route_dash_data(self):
        if not config.sessions.has(self.dash_session_id(), "dash"):
            self.send_json({"ok": False, "error": "Accès verrouillé"}, 401)
            return
        rows = monitor.devices.rows(self.client_address[0])
        self.send_json({
            "ok": True, "host": socket.gethostname(), "memory": SystemInfo.memory(), "disks": SystemInfo.disks(), "devices": rows,
            "active": sum(1 for r in rows if r["active"]), "blocked": sum(1 for r in rows if r["blocked"]),
            "window": DeviceTracker.ACTIVE_SECONDS,
        })

    def route_dash_history(self, q):
        if not config.sessions.has(self.dash_session_id(), "dash"):
            self.send_json({"ok": False, "error": "Accès verrouillé"}, 401)
            return
        ip = q.get("ip", ["all"])[0]
        if ip != "all":
            try:
                ip = str(ipaddress.ip_address(ip))
            except ValueError:
                self.send_json({"ok": False, "error": "Adresse IP invalide."}, 400)
                return
        self.send_json(monitor.history.report(ip, q.get("range", ["24h"])[0]))

    def route_dash_post(self, path, q):
        """POST /dashboard/block?ip=…, /dashboard/unblock?ip=… (accès déverrouillé requis)."""
        if not config.sessions.has(self.dash_session_id(), "dash"):
            self.send_json({"ok": False, "error": "Accès verrouillé", "locked": True}, 401)
            return
        ok, err, warning = monitor.blocklist.set(q.get("ip", [""])[0], path == "/dashboard/block", self.client_address[0])
        if not ok:
            self.send_json({"ok": False, "error": err}, 400)
            return
        self.send_json({"ok": True, "warning": warning})
