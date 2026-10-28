"""Service de fichiers : contenu brut, sites, bundle de l'éditeur, PDF et pdf.js."""

import hmac
import os
import zipfile
from pathlib import Path
from urllib.parse import quote, unquote

from app import config
from app.assets import bundle_bytes
from app.config import BUNDLE
from app.devices import add_bytes
from app.filesystem import guess_mime, is_env_file, kind_of, rel_of, resolve_inside
from app.filetypes import AUDIO_EXT, IMAGE_EXT, VIDEO_EXT

# Formats déjà compressés : stockés tels quels dans l'archive (gain de temps, pas de gain de taille à espérer).
STORED_EXT = VIDEO_EXT | AUDIO_EXT | IMAGE_EXT | {
    ".zip", ".gz", ".tgz", ".bz2", ".xz", ".7z", ".rar", ".pdf", ".docx", ".xlsx", ".pptx", ".odt", ".ods",
    ".jar", ".apk", ".woff", ".woff2",
}


class _ZipSink:
    """Destination non « seekable » du ZIP : écrit sur la socket et compte les octets envoyés."""

    def __init__(self, wfile, entry):
        self.wfile, self.entry = wfile, entry

    def write(self, data):
        self.wfile.write(data)
        add_bytes(self.entry, len(data))
        return len(data)

    def flush(self):
        self.wfile.flush()


class ServeRoutes:
    def route_raw(self, rel, download):
        p = resolve_inside(rel)
        if p is None or not p.is_file():
            self.send_error(404, "Fichier introuvable")
            return
        kind = kind_of(p)
        if download:
            disp = "attachment; filename*=UTF-8''" + quote(p.name)
            ctype = "application/octet-stream"
        else:
            disp = None
            ctype = guess_mime(p)
            if kind in ("text", "web"):
                ctype = "text/plain; charset=utf-8"
        extra = {"Content-Security-Policy": "sandbox"} if kind in ("text", "web") else None
        self.send_file(p, ctype, disp, extra)

    def route_zip(self, rel):
        """GET /zip?f=<dossier> : archive ZIP du dossier et de son contenu, construite au fil de l'envoi."""
        p = resolve_inside(rel)
        if p is None or not p.is_dir():
            self.send_error(404, "Dossier introuvable")
            return
        top = p.name or config.ROOT.name or "bibliotheque"
        fname = top + ".zip"
        ascii_name = "".join(c if c.isascii() and c.isprintable() and c not in '"\\;' else "_" for c in fname)
        self.send_response(200)
        self.send_header("Content-Type", "application/zip")
        self.send_header("Content-Disposition",
                         f'attachment; filename="{ascii_name}"; filename*=UTF-8\'\'{quote(fname)}')
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Connection", "close")        # longueur inconnue : la fin de l'archive = fermeture
        self.end_headers()
        self.close_connection = True
        with zipfile.ZipFile(_ZipSink(self.wfile, self._entry), "w", zipfile.ZIP_DEFLATED,
                             allowZip64=True, strict_timestamps=False) as zf:
            for dirpath, dirnames, filenames in os.walk(p):     # les raccourcis vers des dossiers ne sont pas suivis
                dirnames.sort(key=str.casefold)
                here = Path(dirpath)
                arc_dir = Path(top, *here.relative_to(p).parts).as_posix()
                if not dirnames and not filenames:
                    info = zipfile.ZipInfo(arc_dir + "/")
                    info.external_attr = (0o40755 << 16) | 0x10
                    zf.writestr(info, b"")
                for name in sorted(filenames, key=str.casefold):
                    fp = here / name
                    if is_env_file(fp) or (name.startswith(".") and name.endswith(".fl-tmp")) or not fp.is_file():
                        continue
                    try:
                        with open(fp, "rb"):
                            pass                       # illisible : ignoré avant d'écrire l'en-tête de l'entrée
                        zf.write(fp, arc_dir + "/" + name, zipfile.ZIP_STORED if fp.suffix.lower() in STORED_EXT
                                 else zipfile.ZIP_DEFLATED)
                    except (BrokenPipeError, ConnectionResetError):
                        raise
                    except (OSError, UnicodeError, ValueError):
                        continue

    def route_site(self, path):
        """Aperçu des pages web : /s/<token>/<chemin> (isolé par CSP sandbox)."""
        parts = path.split("/", 3)  # ['', 's', token, rest]
        if len(parts) < 4 or not hmac.compare_digest(unquote(parts[2]).encode("utf-8", "replace"), config.TOKEN.encode()):
            self.send_error(403, "Accès refusé")
            return
        p = resolve_inside(unquote(parts[3]))
        if p is not None and p.is_dir():
            for name in ("index.html", "index.htm"):
                if (p / name).is_file():
                    p = p / name
                    break
        if p is None or not p.is_file():
            self.send_error(404, "Fichier introuvable")
            return
        self.send_file(p, guess_mime(p), None, {
            "Content-Security-Policy": "sandbox allow-scripts allow-forms allow-popups allow-modals",
            "Cache-Control": "no-store",
        })

    def route_bundle(self):
        if not BUNDLE.is_file():
            self.send_error(404, "editor.bundle.js introuvable à côté de server.py")
            return
        b = bundle_bytes()
        headers = {"Cache-Control": "public, max-age=86400", "Vary": "Accept-Encoding"}
        if "gzip" in self.headers.get("Accept-Encoding", ""):
            headers["Content-Encoding"] = "gzip"
            self.send_bytes(b["gz"], "text/javascript; charset=utf-8", 200, headers)
        else:
            self.send_bytes(b["raw"], "text/javascript; charset=utf-8", 200, headers)

    def route_pdf(self, rel):
        p = resolve_inside(rel)
        if p is None or not p.is_file() or p.suffix.lower() != ".pdf":
            self.send_error(404, "PDF introuvable")
            return
        if config.PDFJS_DIR is not None:
            loc = "/legacy/web/viewer.html?file=" + quote("/docs/" + rel_of(p), safe="")
        else:
            loc = "/raw?f=" + quote(rel_of(p), safe="")
        self.send_response(302)
        self.send_header("Location", loc)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def route_docs(self, path):
        p = resolve_inside(unquote(path[len("/docs/"):]))
        if p is None or not p.is_file() or p.suffix.lower() != ".pdf":
            self.send_error(404, "PDF introuvable")
            return
        self.send_file(p, "application/pdf", None, {"Cache-Control": "no-cache"})

    def route_pdfjs(self, path):
        if config.PDFJS_DIR is None:
            self.send_error(404, "pdf.js non installé")
            return
        rel = unquote(path.lstrip("/"))
        try:
            # seuls legacy/, build/ et web/ sont servis ; rien ne doit en sortir
            base = (config.PDFJS_DIR / rel.split("/", 1)[0]).resolve()
            base.relative_to(config.PDFJS_DIR)
            target = (config.PDFJS_DIR / rel).resolve()
            target.relative_to(base)
        except (ValueError, OSError):
            self.send_error(403, "Accès refusé")
            return
        if not target.is_file():
            self.send_error(404, "Fichier introuvable")
            return
        self.send_file(target, guess_mime(target), None, {"Cache-Control": "public, max-age=86400"})
