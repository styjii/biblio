"""Dernière position de lecture de chaque appareil (adresse IP) pour chaque fichier audio ou vidéo."""

import ipaddress
import json
import math
import threading
import time

from app import config
from app.utils import atomic_write


class PlaybackStore:
    """ip -> {chemin relatif -> [position (s), durée (s), date de mise à jour]}, enregistré dans `config.PLAYBACK_PATH`."""
    MAX_DEVICES: int = 500          # appareils gardés (les plus anciens sont oubliés)
    MAX_PER_DEVICE: int = 1000      # fichiers gardés par appareil (les moins récents sont oubliés)
    DAYS = 180                 # durée de conservation d'une position
    MAX_SECONDS = 30 * 86400   # valeurs absurdes refusées
    FLUSH_SECONDS = 15

    def __init__(self):
        self._lock = threading.Lock()
        self._data = {}
        self._dirty = False

    # --- lecture / écriture ---
    def get(self, ip, rel):
        """{"t": position, "d": durée} ou None si l'appareil n'a rien mémorisé pour ce fichier."""
        with self._lock:
            entry = self._data.get(ip, {}).get(rel)
            return {"t": entry[0], "d": entry[1]} if entry else None

    def put(self, ip, rel, t, d):
        """Mémorise la position. Valeurs invalides ou position nulle : refusées (False)."""
        try:
            t, d = float(t), float(d or 0)
        except (TypeError, ValueError):
            return False
        if not (math.isfinite(t) and math.isfinite(d)) or not 0 <= t <= self.MAX_SECONDS or not 0 <= d <= self.MAX_SECONDS:
            return False
        if not rel or len(rel) > 1024:
            return False
        with self._lock:
            files = self._data.setdefault(ip, {})
            files[rel] = [round(t, 1), round(d, 1), time.time()]
            if len(files) > self.MAX_PER_DEVICE:
                oldest = min(files, key=lambda r: files[r][2])
                del files[oldest]
            if len(self._data) > self.MAX_DEVICES:
                stale = min(self._data, key=lambda i: max((e[2] for e in self._data[i].values()), default=0))
                del self._data[stale]
            self._dirty = True
        return True

    def forget(self, ip, rel):
        with self._lock:
            if self._data.get(ip, {}).pop(rel, None) is not None:
                self._dirty = True

    def drop(self, rel):
        """Un fichier (ou un dossier et son contenu) est supprimé : toutes les positions associées disparaissent."""
        prefix = rel + "/"
        with self._lock:
            for files in self._data.values():
                for r in [r for r in files if r == rel or r.startswith(prefix)]:
                    del files[r]
                    self._dirty = True

    def move(self, old, new):
        """Un fichier (ou un dossier) est renommé : les positions suivent."""
        prefix = old + "/"
        with self._lock:
            for files in self._data.values():
                for r in [r for r in files if r == old or r.startswith(prefix)]:
                    files[new + r[len(old):]] = files.pop(r)
                    self._dirty = True

    # --- persistance ---
    def save(self):
        cutoff = time.time() - self.DAYS * 86400
        with self._lock:
            for ip in list(self._data):
                files = self._data[ip]
                for r in [r for r, e in files.items() if e[2] < cutoff]:
                    del files[r]
                if not files:
                    del self._data[ip]
            text = json.dumps(self._data, separators=(",", ":"))
            self._dirty = False
        try:
            atomic_write(config.PLAYBACK_PATH, text)
        except OSError:
            self._dirty = True       # nouvel essai au prochain passage

    def load(self):
        try:
            data = json.loads(config.PLAYBACK_PATH.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return
        if not isinstance(data, dict):
            return
        with self._lock:
            for ip, files in data.items():
                try:
                    ipaddress.ip_address(ip)
                    clean = {r: [float(e[0]), float(e[1]), float(e[2])] for r, e in files.items() if isinstance(r, str)}
                except (ValueError, TypeError, IndexError, AttributeError):
                    continue
                if clean:
                    self._data[ip] = clean

    def _flush_forever(self):
        while True:
            time.sleep(self.FLUSH_SECONDS)
            if self._dirty:
                self.save()

    def start(self):
        self.load()
        threading.Thread(target=self._flush_forever, daemon=True).start()

    def stop(self):
        if self._dirty:
            self.save()


playback = PlaybackStore()
