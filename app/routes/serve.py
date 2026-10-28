"""Service de fichiers : contenu brut, sites, bundle de l'éditeur, PDF et pdf.js."""

import hmac
from urllib.parse import quote, unquote

from app import config
from app.assets import bundle_bytes
from app.config import BUNDLE
from app.filesystem import guess_mime, kind_of, rel_of, resolve_inside


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
