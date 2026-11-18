"""Informations système du tableau de bord : mémoire et disques."""

import os
import shutil
import threading
import time

from app import config
from app.utils import fmt_size


class SystemInfo:
    """Mémoire de l'appareil et capacité des disques configurés (BIBLIO_DISKS)."""

    @staticmethod
    def memory():
        """Mémoire de l'appareil (octets) ou None. « Libre » = mémoire disponible (MemAvailable : cache
        récupérable inclus), et non le seul MemFree, toujours très bas sous Linux."""
        total = avail = None
        try:
            info = {}
            with open("/proc/meminfo", encoding="ascii", errors="replace") as f:
                for line in f:
                    key, _, rest = line.partition(":")
                    parts = rest.split()
                    if parts and parts[0].isdigit():
                        info[key] = int(parts[0]) * 1024      # valeurs en Kio
            total = info.get("MemTotal")
            avail = info.get("MemAvailable")
            if avail is None and total:                       # très vieux noyaux
                avail = info.get("MemFree", 0) + info.get("Buffers", 0) + info.get("Cached", 0)
        except OSError:
            pass
        if not total:
            try:
                page = os.sysconf("SC_PAGE_SIZE")
                total = page * os.sysconf("SC_PHYS_PAGES")
                avail = page * os.sysconf("SC_AVPHYS_PAGES")
            except (ValueError, OSError, AttributeError):
                return None
        if not total or avail is None:
            return None
        avail = max(0, min(avail, total))
        used = total - avail
        return {"total": total, "used": used, "free": avail, "percent": round(used * 100 / total, 1),
                "total_h": fmt_size(total), "used_h": fmt_size(used), "free_h": fmt_size(avail)}

    @staticmethod
    def volume(path):
        """Capacité du volume qui contient `path` : champs `total`, `used`, `free`… ou `error` s'il est illisible."""
        try:
            u = shutil.disk_usage(path)
        except FileNotFoundError:
            return {"error": "Introuvable (non monté ?)"}
        except PermissionError:
            return {"error": "Accès refusé"}
        except OSError as e:
            return {"error": e.strerror or "Illisible"}
        return {"total": u.total, "used": u.used, "free": u.free,
                "percent": round(u.used * 100 / u.total, 1) if u.total else 0.0,
                "total_h": fmt_size(u.total), "used_h": fmt_size(u.used), "free_h": fmt_size(u.free)}

    @staticmethod
    def _device(path):
        try:
            return os.stat(path).st_dev
        except OSError:
            return None

    @classmethod
    def storage(cls):
        """Stockage des chemins du .env, sans double comptage :

        - une ligne par chemin configuré, avec son espace libre ;
        - le dossier courant, déjà rattaché à l'un de ces chemins (il est dedans, ou sur le même volume), n'est pas
          recompté comme un volume : sa taille est une part du volume (`folder`, en octets de contenu) ;
          s'il est seul sur son volume, il apparaît comme une ligne à part ;
        - l'espace libre total additionne chaque volume une seule fois (deux chemins du même volume = un seul volume)."""
        mounts = list(config.library.mounts)
        launch = config.library.launch
        main = [m for m in mounts if m.configured] or mounts    # sans BIBLIO_DISKS, le dossier courant est le seul chemin
        rows, seen_dev = [], {}
        for m in main:
            row = {"id": m.id, "path": m.shown, "label": m.name, "current": m.launch}
            vol = cls.volume(m.path)
            row.update(vol)
            if "error" not in vol:
                dev = cls._device(m.path)
                if dev in seen_dev:
                    row["same_volume_as"] = seen_dev[dev]
                elif dev is not None:
                    seen_dev[dev] = m.name
                try:   # même volume que « / » : le disque n'est probablement pas monté
                    row["system"] = dev == os.stat("/").st_dev and os.path.realpath(m.path) != "/"
                except OSError:
                    row["system"] = False
                row["_counted"] = "same_volume_as" not in row
            rows.append(row)
        # dossier courant : rattaché à un chemin existant ou volume à part
        if launch is not None and launch not in main:
            host = cls._host_row(launch, main, rows)
            if host is not None:
                host["folder"] = cls._folder_info(launch, host)
            else:
                row = {"id": launch.id, "path": launch.shown, "label": launch.name, "current": True}
                row.update(cls.volume(launch.path))
                row["_counted"] = "error" not in row
                rows.insert(0, row)
        free_total = sum(r["free"] for r in rows if r.pop("_counted", False))
        return {"disks": rows, "free_total": free_total, "free_total_h": fmt_size(free_total),
                "volumes": sum(1 for r in rows if "error" not in r and "same_volume_as" not in r)}

    @classmethod
    def _host_row(cls, launch, main, rows):
        """Ligne du chemin configuré auquel le dossier courant est rattaché, ou None."""
        by_id = {r["id"]: r for r in rows}
        target = os.path.realpath(launch.path)
        best = None
        for m in main:
            base = os.path.realpath(m.path)
            try:
                inside = os.path.commonpath([target, base]) == base
            except ValueError:
                inside = False
            if inside and (best is None or len(str(m.path)) > len(str(best.path))):
                best = m
        if best is None:
            dev = cls._device(launch.path)
            best = next((m for m in main if dev is not None and cls._device(m.path) == dev), None)
        return by_id.get(best.id) if best else None

    @staticmethod
    def _folder_info(launch, host):
        size = folder_sizes.get(launch.path)
        info = {"name": launch.name, "path": str(launch.path), "computing": size["running"],
                "bytes": size["bytes"], "files": size["files"]}
        if size["bytes"] is not None:
            info["bytes_h"] = fmt_size(size["bytes"])
            if host.get("total"):
                info["percent"] = round(min(size["bytes"], host["total"]) * 100 / host["total"], 2)
        return info


class FolderSizes:
    """Taille du contenu d'un dossier, calculée en arrière-plan (un parcours peut durer) et mise en cache.
    Les liens symboliques ne sont pas suivis : un fichier n'est compté qu'une fois."""
    TTL = 300

    def __init__(self):
        self._lock = threading.Lock()
        self._cache = {}

    def get(self, path):
        """-> {"bytes", "files", "running"} ; `bytes` vaut None tant que le premier calcul n'a rien trouvé."""
        key = str(path)
        with self._lock:
            entry = self._cache.get(key)
            if entry is None or (not entry["running"] and time.time() - entry["at"] > self.TTL):
                entry = {"bytes": entry["bytes"] if entry else None, "files": entry["files"] if entry else 0,
                         "at": time.time(), "running": True}
                self._cache[key] = entry
                threading.Thread(target=self._scan, args=(key,), daemon=True).start()
            return {k: entry[k] for k in ("bytes", "files", "running")}

    def _scan(self, key):
        total = files = 0
        pending = [key]
        while pending:
            try:
                with os.scandir(pending.pop()) as it:
                    for ent in it:
                        try:
                            if ent.is_symlink():
                                continue
                            if ent.is_dir(follow_symlinks=False):
                                pending.append(ent.path)
                            elif ent.is_file(follow_symlinks=False):
                                total += ent.stat(follow_symlinks=False).st_size
                                files += 1
                        except OSError:
                            continue
            except OSError:
                continue
        with self._lock:
            self._cache[key].update(bytes=total, files=files, at=time.time(), running=False)


folder_sizes = FolderSizes()
