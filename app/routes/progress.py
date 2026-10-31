"""Position de lecture mémorisée par appareil (adresse IP) : GET /progress?f=… et POST /progress?f=…&t=…&d=…"""

from app import config
from app.filesystem import kind_of, rel_of
from app.playback import playback
from app.routes.base import BaseHandler


class ProgressRoutes(BaseHandler):
    def _media_rel(self, rel):
        """Chemin relatif d'un fichier audio ou vidéo existant, ou None (la réponse d'erreur est alors déjà envoyée)."""
        p = config.paths.resolve(rel)
        if p is None:
            self.send_json({"ok": False, "error": "Chemin non autorisé"}, 403)
        elif not p.is_file() or kind_of(p) not in ("video", "audio"):
            self.send_json({"ok": False, "error": "Média introuvable"}, 404)
        else:
            return rel_of(p)
        return None

    def route_progress_get(self, rel):
        """Dernière position de CET appareil pour ce fichier : {"ok": true, "t": secondes, "d": durée}."""
        key = self._media_rel(rel)
        if key is None:
            return
        saved = playback.get(self.client_address[0], key) or {"t": 0, "d": 0}
        self.send_json({"ok": True, "t": saved["t"], "d": saved["d"]})

    def route_progress_save(self, q):
        """Mémorise la position (t, d) de cet appareil ; `done=1` ou une position proche du début efface la mémoire."""
        key = self._media_rel(q.get("f", [""])[0])
        if key is None:
            return
        ip = self.client_address[0]
        try:
            t = float(q.get("t", ["0"])[0])
        except ValueError:
            t = -1.0
        if q.get("done", [""])[0] == "1" or 0 <= t < 3:
            playback.forget(ip, key)
            self.send_json({"ok": True, "saved": False})
        elif playback.put(ip, key, t, q.get("d", ["0"])[0]):
            self.send_json({"ok": True, "saved": True})
        else:
            self.send_json({"ok": False, "error": "Position invalide"}, 400)
