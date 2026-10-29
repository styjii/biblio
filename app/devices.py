"""Appareils connectés, blocage par adresse IP et historique d'activité (tableau de bord).

Trois classes se partagent un même verrou (créé par `Monitor`) et sont réunies dans l'instance `monitor` :
  - `Blocklist`        : adresses IP bloquées (enregistrées dans `config.BLOCKLIST_PATH`) ;
  - `DeviceTracker`    : appareils vus (dernier passage, requêtes, navigateur) ;
  - `ActivityHistory`  : actions de chaque appareil (fichier ouvert, octets servis…), courbes du tableau de bord.
"""

import ipaddress
import json
import threading
import time
from collections import deque
from urllib.parse import unquote

from app import config
from app.filesystem import kind_of
from app.filetypes import MD_EXT
from app.utils import atomic_write, lan_ips


class Blocklist:
    """Adresses IP bloquées par l'administrateur (ip -> date du blocage)."""

    def __init__(self, lock, local_ips):
        self._lock = lock
        self._local_ips = local_ips
        self._since = {}

    def __len__(self):
        with self._lock:
            return len(self._since)

    def is_blocked(self, ip):
        with self._lock:
            return ip in self._since

    def snapshot(self):
        """Ensemble des adresses bloquées. À appeler avec le verrou tenu."""
        return set(self._since)

    def load(self):
        try:
            data = json.loads(config.BLOCKLIST_PATH.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return
        if not isinstance(data, list):
            return
        with self._lock:
            for item in data:
                try:
                    self._since[str(ipaddress.ip_address(str(item["ip"])))] = float(item.get("since", 0))
                except (ValueError, KeyError, TypeError, AttributeError):
                    continue

    def _save(self):
        """Écrit la liste (atomique, droits 0600). À appeler avec le verrou tenu."""
        data = [{"ip": ip, "since": since} for ip, since in sorted(self._since.items())]
        atomic_write(config.BLOCKLIST_PATH, json.dumps(data))

    def set(self, ip_text, block, requester):
        """Bloque ou débloque une adresse IP. -> (ok, erreur, avertissement)"""
        try:
            ip = str(ipaddress.ip_address(ip_text.strip()))
        except ValueError:
            return False, "Adresse IP invalide.", ""
        if block:
            if ip == requester:
                return False, "Tu ne peux pas bloquer l'appareil que tu utilises.", ""
            if ipaddress.ip_address(ip).is_loopback or ip in self._local_ips or ip in lan_ips():
                return False, "Tu ne peux pas bloquer l'appareil qui héberge le serveur.", ""
        warning = ""
        with self._lock:
            if block:
                self._since[ip] = time.time()
            else:
                self._since.pop(ip, None)
            try:
                self._save()
            except OSError as e:
                warning = (f"Appliqué, mais la liste n'a pas pu être enregistrée dans {config.BLOCKLIST_PATH} "
                           f"({e.strerror}) : elle sera perdue au redémarrage.")
        return True, "", warning


class DeviceTracker:
    """Appareils vus : un par adresse IP, avec leur dernier passage, leur nombre de requêtes et leur navigateur."""
    ACTIVE_SECONDS = 5 * 60     # un appareil est « connecté » s'il a fait une requête depuis moins de 5 min
    MAX_DEVICES = 500           # appareils gardés en mémoire (les plus anciens sont oubliés)

    BROWSERS = (("Edg/", "Edge"), ("OPR/", "Opera"), ("Firefox/", "Firefox"), ("FxiOS/", "Firefox"),
                ("SamsungBrowser/", "Samsung Internet"), ("CriOS/", "Chrome"), ("Chrome/", "Chrome"),
                ("Safari/", "Safari"))
    SYSTEMS = (("Android", "Android"), ("iPhone", "iPhone"), ("iPad", "iPad"), ("Windows", "Windows"),
               ("Mac OS X", "macOS"), ("CrOS", "ChromeOS"), ("Linux", "Linux"))

    def __init__(self, lock, blocklist, local_ips):
        self._lock = lock
        self._blocklist = blocklist
        self._local_ips = local_ips
        self._devices = {}      # ip -> {first, last, hits, ua, auth}

    @classmethod
    def short_ua(cls, ua):
        """User-Agent -> libellé court (« Chrome · Android »)."""
        ua = ua or ""
        browser = next((name for key, name in cls.BROWSERS if key in ua), "")
        system = next((name for key, name in cls.SYSTEMS if key in ua), "")
        label = " · ".join(x for x in (browser, system) if x)
        return label or ua.split("/")[0][:30]

    def track(self, ip, ua, authed, hit=True):
        """Enregistre le passage d'un appareil (authed : a présenté le jeton d'accès, mémorisé). -> `hit`"""
        now = time.time()
        with self._lock:
            d = self._devices.get(ip)
            if d is None:
                if len(self._devices) >= self.MAX_DEVICES:
                    del self._devices[min(self._devices, key=lambda k: self._devices[k]["last"])]
                d = self._devices[ip] = {"first": now, "hits": 0, "auth": False, "ua": ""}
            d["last"] = now
            d["ua"] = self.short_ua(ua) or d["ua"]
            d["auth"] = d["auth"] or bool(authed)
            if hit:
                d["hits"] += 1
        return hit

    @staticmethod
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

    def rows(self, me):
        """Appareils vus + appareils bloqués, prêts pour le JSON du tableau de bord."""
        now = time.time()
        macs = self.arp_macs()
        with self._lock:
            seen = {ip: dict(d) for ip, d in self._devices.items()}
            blocked = self._blocklist.snapshot()
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
                "active": ago is not None and ago <= self.ACTIVE_SECONDS and ip not in blocked,
                "blocked": ip in blocked, "me": ip == me, "local": loopback or ip in self._local_ips,
            })
        rows.sort(key=lambda r: (r["blocked"], not r["active"], r["ago"] if r["ago"] is not None else 1 << 40, r["ip"]))
        return rows

    # --- persistance (appelée par ActivityHistory, verrou tenu) ---
    def prune(self, cutoff):
        """Oublie les appareils inactifs depuis `cutoff` (sauf ceux qui sont bloqués)."""
        blocked = self._blocklist.snapshot()
        for ip in [ip for ip, d in self._devices.items() if d["last"] < cutoff and ip not in blocked]:
            del self._devices[ip]

    def export(self):
        return {ip: dict(d) for ip, d in self._devices.items()}

    def restore(self, devices):
        for ip, d in devices.items():
            try:
                ipaddress.ip_address(ip)
                self._devices[ip] = {"first": float(d["first"]), "last": float(d["last"]), "hits": int(d["hits"]),
                                     "ua": str(d.get("ua", ""))[:60], "auth": bool(d.get("auth"))}
            except (ValueError, KeyError, TypeError, AttributeError):
                continue


class ActivityHistory:
    """Actions de chaque appareil : [début, fin, catégorie, fichier, octets, requêtes], enregistrées sur disque."""
    CATEGORIES = [   # (identifiant, libellé, couleur)
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
    GAP = {"video": 300, "audio": 300}   # secondes sans requête avant de compter une nouvelle action
    DEFAULT_GAP = 90
    DAYS = 30                            # durée de conservation
    MAX_PER_DEVICE = 3000                # actions gardées par appareil
    RANGES = {"24h": (24 * 3600, 900), "7d": (7 * 24 * 3600, 3600), "30d": (30 * 24 * 3600, 6 * 3600)}
    FLUSH_SECONDS = 120

    def __init__(self, lock, tracker):
        self._lock = lock
        self._tracker = tracker
        self._log = {}       # ip -> deque d'actions
        self.dirty = False   # modifications non enregistrées

    # --- classement des requêtes ---
    @classmethod
    def classify(cls, path, q):
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
            pf = config.paths.resolve(arg("f"))
            return ("text" if pf is not None and pf.suffix.lower() in MD_EXT else "web"), arg("f")
        if path == "/raw":
            f = arg("f")
            if arg("dl") == "1":
                return "download", f
            p = config.paths.resolve(f)
            return cls.KIND_CATS.get(kind_of(p) if p else "text", "text"), f
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

    # --- enregistrement ---
    def record(self, ip, cat, file):
        """Ajoute une action ; les requêtes rapprochées sur un même fichier (flux vidéo découpé en plages,
        par exemple) sont fusionnées en une seule action. -> entrée modifiable (voir add_bytes)."""
        now = time.time()
        gap = self.GAP.get(cat, self.DEFAULT_GAP)
        file = file[:300]
        with self._lock:
            h = self._log.get(ip)
            if h is None:
                h = self._log[ip] = deque(maxlen=self.MAX_PER_DEVICE)
            self.dirty = True
            for i, e in enumerate(reversed(h)):
                if i >= 8:
                    break
                if e[2] == cat and e[3] == file and now - e[1] <= gap:
                    e[1] = now
                    e[5] += 1
                    return e
            e = [now, now, cat, file, 0, 1]
            h.append(e)
            return e

    def add_bytes(self, entry, n):
        if entry is not None and n:
            with self._lock:
                entry[4] += n

    # --- persistance ---
    def save(self):
        """Écrit appareils + historique (atomique, droits 0600) après avoir purgé ce qui est trop ancien."""
        cutoff = time.time() - self.DAYS * 86400
        with self._lock:
            for ip in list(self._log):
                h = self._log[ip]
                while h and h[0][1] < cutoff:
                    h.popleft()
                if not h:
                    del self._log[ip]
            self._tracker.prune(cutoff)
            data = {"devices": self._tracker.export(),
                    "history": {ip: [list(e) for e in h] for ip, h in self._log.items()}}
            self.dirty = False
        try:
            atomic_write(config.HISTORY_PATH, json.dumps(data, separators=(",", ":")))
        except OSError:
            self.dirty = True      # nouvel essai au prochain passage

    def load(self):
        try:
            data = json.loads(config.HISTORY_PATH.read_text(encoding="utf-8"))
            devices, history = data.get("devices", {}), data.get("history", {})
        except (OSError, ValueError, AttributeError):
            return
        cats = {c[0] for c in self.CATEGORIES}
        with self._lock:
            self._tracker.restore(devices)
            for ip, items in history.items():
                try:
                    ipaddress.ip_address(ip)
                except ValueError:
                    continue
                h = deque(maxlen=self.MAX_PER_DEVICE)
                for e in items if isinstance(items, list) else []:
                    try:
                        if e[2] in cats:
                            h.append([float(e[0]), float(e[1]), e[2], str(e[3])[:300], int(e[4]), int(e[5])])
                    except (IndexError, ValueError, TypeError):
                        continue
                if h:
                    self._log[ip] = h

    def flush_forever(self):
        """Boucle du fil d'arrière-plan : enregistre l'historique s'il a changé."""
        while True:
            time.sleep(self.FLUSH_SECONDS)
            if self.dirty:
                self.save()

    # --- rapport ---
    def report(self, ip, rng):
        """Courbes, totaux, fichiers les plus consultés et liste récente pour un appareil (ou « all »)."""
        span, step = self.RANGES.get(rng, self.RANGES["24h"])
        n = span // step
        now = time.time()
        start = (int(now // step) + 1) * step - span
        series = {c[0]: {"actions": [0] * n, "bytes": [0] * n, "seconds": [0.0] * n} for c in self.CATEGORIES}
        totals = {c[0]: {"actions": 0, "bytes": 0, "seconds": 0.0} for c in self.CATEGORIES}
        with self._lock:
            sources = self._log.items() if ip == "all" else [(ip, self._log.get(ip, ()))]
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
            "ok": True, "ip": ip, "range": rng if rng in self.RANGES else "24h", "start": start, "step": step, "n": n,
            "series": series, "totals": totals,
            "top": [{"cat": k[0], "file": k[1], "n": v[0], "seconds": round(v[1]), "bytes": v[2]} for k, v in top_rows],
            "recent": [{"ip": dev, "t": s, "end": e, "cat": cat, "file": file, "bytes": nb, "n": reqs}
                       for dev, (s, e, cat, file, nb, reqs) in recent],
        }


class Monitor:
    """Surveillance des appareils : réunit liste de blocage, appareils vus et historique autour d'un même verrou."""

    def __init__(self):
        self.lock = threading.Lock()
        self.local_ips = {"127.0.0.1"}     # adresses de la machine qui héberge le serveur (remplie au démarrage)
        self.blocklist = Blocklist(self.lock, self.local_ips)
        self.devices = DeviceTracker(self.lock, self.blocklist, self.local_ips)
        self.history = ActivityHistory(self.lock, self.devices)

    def track(self, ip, ua, authed, hit=True):
        """Enregistre le passage d'un appareil ; une requête « utile » marque l'historique comme modifié."""
        if self.devices.track(ip, ua, authed, hit):
            self.history.dirty = True

    def start(self):
        """Au démarrage : charge la liste de blocage et l'historique, lance l'enregistrement périodique."""
        self.local_ips.update(lan_ips())
        self.blocklist.load()
        self.history.load()
        threading.Thread(target=self.history.flush_forever, daemon=True).start()

    def stop(self):
        self.history.save()


monitor = Monitor()
