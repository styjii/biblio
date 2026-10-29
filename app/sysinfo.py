"""Informations système du tableau de bord : mémoire et disques."""

import os
import shutil

from app import config
from app.utils import fmt_size


def read_memory():
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


def read_disks():
    """Capacité de chaque volume configuré (octets), ou un message d'erreur s'il est illisible."""
    out = []
    for path, label in config.DISKS:
        row = {"path": path, "label": label}
        try:
            u = shutil.disk_usage(path)
        except FileNotFoundError:
            row["error"] = "Introuvable (non monté ?)"
        except PermissionError:
            row["error"] = "Accès refusé"
        except OSError as e:
            row["error"] = e.strerror or "Illisible"
        else:
            row.update(total=u.total, used=u.used, free=u.free,
                       percent=round(u.used * 100 / u.total, 1) if u.total else 0.0,
                       total_h=fmt_size(u.total), used_h=fmt_size(u.used), free_h=fmt_size(u.free))
            try:   # même volume que « / » : le disque n'est probablement pas monté
                row["system"] = os.stat(path).st_dev == os.stat("/").st_dev and os.path.realpath(path) != "/"
            except OSError:
                row["system"] = False
        out.append(row)
    return out
