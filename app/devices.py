"""Appareils connectés, blocage par adresse IP et historique d'activité (tableau de bord).

Appareils et historique partagent le même verrou et les mêmes tables : ils restent dans un seul module."""

import ipaddress
import json
import os
import threading
import time
from collections import deque
from urllib.parse import unquote

from app import config
from app.filesystem import kind_of
from app.filetypes import MD_EXT
from app.utils import lan_ips

DEVICE_ACTIVE_SECONDS = 5 * 60     # un appareil est « connecté » s'il a fait une requête depuis moins de 5 min
MAX_DEVICES = 500                  # appareils gardés en mémoire (les plus anciens sont oubliés)

LOCAL_IPS = {"127.0.0.1"}          # adresses de la machine qui héberge le serveur (remplie au démarrage)
_dev_lock = threading.Lock()
_devices = {}                      # ip -> {first, last, hits, ua, auth}
_blocked = {}                      # ip -> date du blocage (time.time())


def short_ua(ua):
    """User-Agent -> libellé court (« Chrome · Android »)."""
    ua = ua or ""
    browser = next((name for key, name in (
        ("Edg/", "Edge"), ("OPR/", "Opera"), ("Firefox/", "Firefox"), ("FxiOS/", "Firefox"),
        ("SamsungBrowser/", "Samsung Internet"), ("CriOS/", "Chrome"), ("Chrome/", "Chrome"),
        ("Safari/", "Safari")) if key in ua), "")
    system = next((name for key, name in (
        ("Android", "Android"), ("iPhone", "iPhone"), ("iPad", "iPad"), ("Windows", "Windows"),
        ("Mac OS X", "macOS"), ("CrOS", "ChromeOS"), ("Linux", "Linux")) if key in ua), "")
    label = " · ".join(x for x in (browser, system) if x)
    return label or ua.split("/")[0][:30]


def track_device(ip, ua, authed, hit=True):
    """Enregistre le passage d'un appareil. authed : a présenté le jeton d'accès (cookie), mémorisé."""
    global _hist_dirty
    now = time.time()
    with _dev_lock:
        d = _devices.get(ip)
        if d is None:
            if len(_devices) >= MAX_DEVICES:
                del _devices[min(_devices, key=lambda k: _devices[k]["last"])]
            d = _devices[ip] = {"first": now, "hits": 0, "auth": False, "ua": ""}
        d["last"] = now
        d["ua"] = short_ua(ua) or d["ua"]
        d["auth"] = d["auth"] or bool(authed)
        if hit:
            d["hits"] += 1
            _hist_dirty = True


def blocked_count():
    with _dev_lock:
        return len(_blocked)


def is_blocked(ip):
    with _dev_lock:
        return ip in _blocked


def load_blocklist():
    try:
        data = json.loads(config.BLOCKLIST_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return
    if not isinstance(data, list):
        return
    with _dev_lock:
        for item in data:
            try:
                _blocked[str(ipaddress.ip_address(str(item["ip"])))] = float(item.get("since", 0))
            except (ValueError, KeyError, TypeError, AttributeError):
                continue


def save_blocklist():
    """Écrit la liste des appareils bloqués (atomique, droits 0600). À appeler avec _dev_lock tenu."""
    data = [{"ip": ip, "since": since} for ip, since in sorted(_blocked.items())]
    config.BLOCKLIST_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = config.BLOCKLIST_PATH.with_name(config.BLOCKLIST_PATH.name + ".tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(data, f)
    os.replace(tmp, config.BLOCKLIST_PATH)


def set_blocked(ip_text, block, requester):
    """Bloque ou débloque une adresse IP. -> (ok, erreur, avertissement)"""
    try:
        ip = str(ipaddress.ip_address(ip_text.strip()))
    except ValueError:
        return False, "Adresse IP invalide.", ""
    if block:
        if ip == requester:
            return False, "Tu ne peux pas bloquer l'appareil que tu utilises.", ""
        if ipaddress.ip_address(ip).is_loopback or ip in LOCAL_IPS or ip in lan_ips():
            return False, "Tu ne peux pas bloquer l'appareil qui héberge le serveur.", ""
    warning = ""
    with _dev_lock:
        if block:
            _blocked[ip] = time.time()
        else:
            _blocked.pop(ip, None)
        try:
            save_blocklist()
        except OSError as e:
            warning = (f"Appliqué, mais la liste n'a pas pu être enregistrée dans {BLOCKLIST_PATH} "
                       f"({e.strerror}) : elle sera perdue au redémarrage.")
    return True, "", warning


def arp_macs():
    """ip -> adresse MAC d'après la table ARP du système (Linux ; vide si illisible)."""
    macs = {}
    try:
        with open("/proc/net/arp", encoding="ascii", errors="replace") as f:
            next(f, None)
            for line in f:
                cols = line.split()
                if len(cols) >= 4 and cols[3] != "00:00:00:00:00:00":
                    macs[cols[0]] = cols[3]
    except OSError:
        pass
    return macs


def device_rows(me):
    """Appareils vus + appareils bloqués, prêts pour le JSON du tableau de bord."""
    now = time.time()
    macs = arp_macs()
    with _dev_lock:
        seen = {ip: dict(d) for ip, d in _devices.items()}
        blocked = set(_blocked)
    rows = []
    for ip in set(seen) | blocked:
        d = seen.get(ip)
        ago = max(0, int(now - d["last"])) if d else None
        try:
            loopback = ipaddress.ip_address(ip).is_loopback
        except ValueError:
            loopback = False
        rows.append({
            "ip": ip, "mac": macs.get(ip, ""), "ua": d["ua"] if d else "", "ago": ago,
            "hits": d["hits"] if d else 0, "auth": bool(d and d["auth"]),
            "active": ago is not None and ago <= DEVICE_ACTIVE_SECONDS and ip not in blocked,
            "blocked": ip in blocked, "me": ip == me, "local": loopback or ip in LOCAL_IPS,
        })
    rows.sort(key=lambda r: (r["blocked"], not r["active"], r["ago"] if r["ago"] is not None else 1 << 40, r["ip"]))
    return rows


# --- historique des actions par appareil ---------------------------------------------------
ACTIVITY_CATS = [   # (identifiant, libellé, couleur)
    ("video", "Vidéos", "var(--pink)"),
    ("audio", "Audio", "var(--teal)"),
    ("pdf", "PDF", "var(--accent)"),
    ("text", "Texte et code", "var(--folder)"),
    ("web", "Navigation web", "var(--green)"),
    ("image", "Images", "var(--orange)"),
    ("browse", "Dossiers", "var(--muted)"),
    ("download", "Téléchargements", "var(--red)"),
    ("edit", "Modifications", "#9b6bd6"),
]

KIND_CATS = {"video": "video", "audio": "audio", "pdf": "pdf", "image": "image", "web": "web",
             "text": "text", "binary": "download"}

ACTIVITY_GAP = {"video": 300, "audio": 300}   # secondes sans requête avant de compter une nouvelle action
DEFAULT_GAP = 90
HISTORY_DAYS = 30                  # durée de conservation
HISTORY_MAX = 3000                 # actions gardées par appareil
HISTORY_RANGES = {"24h": (24 * 3600, 900), "7d": (7 * 24 * 3600, 3600), "30d": (30 * 24 * 3600, 6 * 3600)}
_history = {}                      # ip -> deque de [début, fin, catégorie, fichier, octets, requêtes]
_hist_dirty = False


def classify(path, q):
    """Requête -> (catégorie, fichier) si c'est une action de l'utilisateur, sinon None
    (miniatures, sous-titres, ressources pdf.js, tableau de bord… ne comptent pas)."""
    def arg(name):
        return q.get(name, [""])[0]

    if path == "/":
        return None if arg("token") else ("browse", arg("folder") or "/")
    if path == "/view":
        return "text", arg("f")
    if path == "/edit":
        return "edit", arg("f")
    if path == "/watch":
        return "video", arg("f")
    if path == "/listen":
        return "audio", arg("f")
    if path == "/pdf":
        return "pdf", arg("f")
    if path == "/preview":
        pf = config.resolve_inside(arg("f"))
        return ("text" if pf is not None and pf.suffix.lower() in MD_EXT else "web"), arg("f")
    if path == "/raw":
        f = arg("f")
        if arg("dl") == "1":
            return "download", f
        p = config.resolve_inside(f)
        return KIND_CATS.get(kind_of(p) if p else "text", "text"), f
    if path.startswith("/docs/"):
        return "pdf", unquote(path[len("/docs/"):])
    if path.startswith("/s/"):
        parts = path.split("/", 3)    # le jeton (parts[2]) n'est jamais conservé
        return "web", unquote(parts[3]) if len(parts) > 3 else ""
    if path == "/zip":
        return "download", arg("f") or "/"
    if path in ("/save", "/delete", "/rename"):
        return "edit", arg("f")
    if path == "/mkdir":
        return "edit", (arg("d") + "/" + arg("to")).strip("/")
    if path == "/upload":
        return "edit", (arg("d") + "/" + arg("n")).strip("/")
    return None


def record_event(ip, cat, file):
    """Ajoute une action à l'historique ; les requêtes rapprochées sur un même fichier (flux vidéo
    découpé en plages, par exemple) sont fusionnées en une seule action. -> entrée modifiable."""
    global _hist_dirty
    now = time.time()
    gap = ACTIVITY_GAP.get(cat, DEFAULT_GAP)
    file = file[:300]
    with _dev_lock:
        h = _history.get(ip)
        if h is None:
            h = _history[ip] = deque(maxlen=HISTORY_MAX)
        for i, e in enumerate(reversed(h)):
            if i >= 8:
                break
            if e[2] == cat and e[3] == file and now - e[1] <= gap:
                e[1] = now
                e[5] += 1
                _hist_dirty = True
                return e
        e = [now, now, cat, file, 0, 1]
        h.append(e)
        _hist_dirty = True
        return e


def add_bytes(entry, n):
    if entry is not None and n:
        with _dev_lock:
            entry[4] += n


def save_history():
    """Écrit appareils + historique (atomique, droits 0600) après avoir purgé ce qui est trop ancien."""
    global _hist_dirty
    cutoff = time.time() - HISTORY_DAYS * 86400
    with _dev_lock:
        for ip in list(_history):
            h = _history[ip]
            while h and h[0][1] < cutoff:
                h.popleft()
            if not h:
                del _history[ip]
        for ip in [ip for ip, d in _devices.items() if d["last"] < cutoff and ip not in _blocked]:
            del _devices[ip]
        data = {"devices": {ip: dict(d) for ip, d in _devices.items()},
                "history": {ip: [list(e) for e in h] for ip, h in _history.items()}}
        _hist_dirty = False
    try:
        config.HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
        tmp = config.HISTORY_PATH.with_name(config.HISTORY_PATH.name + ".tmp")
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, separators=(",", ":"))
        os.replace(tmp, config.HISTORY_PATH)
    except OSError:
        _hist_dirty = True      # nouvel essai au prochain passage


def load_history():
    try:
        data = json.loads(config.HISTORY_PATH.read_text(encoding="utf-8"))
        devices, history = data.get("devices", {}), data.get("history", {})
    except (OSError, ValueError, AttributeError):
        return
    cats = {c[0] for c in ACTIVITY_CATS}
    with _dev_lock:
        for ip, d in devices.items():
            try:
                ipaddress.ip_address(ip)
                _devices[ip] = {"first": float(d["first"]), "last": float(d["last"]), "hits": int(d["hits"]),
                                "ua": str(d.get("ua", ""))[:60], "auth": bool(d.get("auth"))}
            except (ValueError, KeyError, TypeError, AttributeError):
                continue
        for ip, items in history.items():
            try:
                ipaddress.ip_address(ip)
            except ValueError:
                continue
            h = deque(maxlen=HISTORY_MAX)
            for e in items if isinstance(items, list) else []:
                try:
                    if e[2] in cats:
                        h.append([float(e[0]), float(e[1]), e[2], str(e[3])[:300], int(e[4]), int(e[5])])
                except (IndexError, ValueError, TypeError):
                    continue
            if h:
                _history[ip] = h


def handle_sigterm(signum, frame):
    raise SystemExit(0)     # kill / arrêt du système : passe par le « finally » qui enregistre l'historique


def history_flusher():
    while True:
        time.sleep(120)
        if _hist_dirty:
            save_history()


def history_report(ip, rng):
    """Courbes, totaux, fichiers les plus consultés et liste récente pour un appareil (ou « all »)."""
    span, step = HISTORY_RANGES.get(rng, HISTORY_RANGES["24h"])
    n = span // step
    now = time.time()
    start = (int(now // step) + 1) * step - span
    series = {c[0]: {"actions": [0] * n, "bytes": [0] * n, "seconds": [0.0] * n} for c in ACTIVITY_CATS}
    totals = {c[0]: {"actions": 0, "bytes": 0, "seconds": 0.0} for c in ACTIVITY_CATS}
    with _dev_lock:
        sources = _history.items() if ip == "all" else [(ip, _history.get(ip, ()))]
        rows = [(dev, tuple(e)) for dev, h in sources for e in h if e[1] >= start]
    top = {}
    for dev, (s, e, cat, file, nbytes, reqs) in rows:
        if cat not in series:
            continue
        idx = int((s - start) // step)
        if 0 <= idx < n:
            series[cat]["actions"][idx] += 1
            series[cat]["bytes"][idx] += nbytes
            totals[cat]["actions"] += 1
            totals[cat]["bytes"] += nbytes
            if cat != "browse" and file:
                t = top.setdefault((cat, file), [0, 0.0, 0])
                t[0] += 1
                t[1] += e - s
                t[2] += nbytes
        a, b = max(s, start), min(e, start + span)
        if b > a:    # durée répartie sur les tranches recouvertes
            for i in range(int((a - start) // step), min(int((b - start) // step), n - 1) + 1):
                part = min(b, start + (i + 1) * step) - max(a, start + i * step)
                if part > 0:
                    series[cat]["seconds"][i] += part
                    totals[cat]["seconds"] += part
    for cat in list(series):
        series[cat]["seconds"] = [round(v) for v in series[cat]["seconds"]]
        totals[cat]["seconds"] = round(totals[cat]["seconds"])
        if not (totals[cat]["actions"] or totals[cat]["seconds"] or totals[cat]["bytes"]):
            del series[cat], totals[cat]
    top_rows = sorted(top.items(), key=lambda kv: (-kv[1][0], -kv[1][1]))[:8]
    recent = sorted(rows, key=lambda r: -r[1][1])[:100]
    return {
        "ok": True, "ip": ip, "range": rng if rng in HISTORY_RANGES else "24h", "start": start, "step": step, "n": n,
        "series": series, "totals": totals,
        "top": [{"cat": k[0], "file": k[1], "n": v[0], "seconds": round(v[1]), "bytes": v[2]} for k, v in top_rows],
        "recent": [{"ip": dev, "t": s, "end": e, "cat": cat, "file": file, "bytes": nb, "n": reqs}
                   for dev, (s, e, cat, file, nb, reqs) in recent],
    }
