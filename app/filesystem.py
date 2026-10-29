"""Accès au dossier servi : chemins sûrs, listage, lecture de texte, type des fichiers."""

import mimetypes

from app import config
from app.config import MAX_TEXT
from app.filetypes import AUDIO_EXT, BINARY_EXT, CODE_EXT, EXTRA_MIME, IMAGE_EXT, TEXT_EXT, VIDEO_EXT, WEB_EXT
from app.utils import natural_key


def rel_of(p):
    return p.relative_to(config.ROOT).as_posix()


def kind_of(p):
    ext = p.suffix.lower()
    if ext in WEB_EXT:
        return "web"
    if ext in IMAGE_EXT:
        return "image"
    if ext == ".pdf":
        return "pdf"
    if ext in VIDEO_EXT:
        return "video"
    if ext in AUDIO_EXT:
        return "audio"
    if ext in BINARY_EXT:
        return "binary"
    return "text"


def card_kind(p):
    """Type pour le menu : un fichier d'extension inconnue est testé (octets nuls)."""
    kind = kind_of(p)
    if kind == "text" and p.suffix.lower() not in CODE_EXT | TEXT_EXT and is_binary_file(p):
        return "binary"
    return kind


def list_dir(current):
    try:
        entries = sorted(current.iterdir(), key=natural_key)
    except (PermissionError, OSError):
        return None, None
    folders = [p for p in entries if p.is_dir()]  # is_dir() suit les liens symboliques
    files = [p for p in entries if p.is_file() and not config.paths.is_env_file(p)]
    return folders, files


def load_text(p):
    """-> (texte, encodage, crlf, erreur) ; erreur : None | 'big' | 'binary'."""
    try:
        raw = p.read_bytes()
    except OSError:
        return None, "utf-8", False, "io"
    if len(raw) > MAX_TEXT:
        return None, "utf-8", False, "big"
    if b"\x00" in raw[:8192]:
        return None, "utf-8", False, "binary"
    try:
        text = raw.decode("utf-8-sig")
        enc = "utf-8-sig" if raw.startswith(b"\xef\xbb\xbf") else "utf-8"
    except UnicodeDecodeError:
        text, enc = raw.decode("latin-1"), "latin-1"
    crlf = "\r\n" in text
    if crlf:
        text = text.replace("\r\n", "\n")
    return text, enc, crlf, None


def is_binary_file(p):
    try:
        with open(p, "rb") as f:
            return b"\x00" in f.read(8192)
    except OSError:
        return True


def guess_mime(p):
    ext = p.suffix.lower()
    if ext in EXTRA_MIME:
        mime = EXTRA_MIME[ext]
    else:
        mime = mimetypes.guess_type(p.name)[0] or "application/octet-stream"
    if mime.startswith("text/") or mime in ("application/json", "application/javascript", "image/svg+xml"):
        if "charset" not in mime:
            mime += "; charset=utf-8" if mime.startswith("text/") or mime == "application/json" else ""
    return mime
