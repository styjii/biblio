"""Médias : miniatures et durées (ffmpeg), tags audio, pochettes, sous-titres."""

import hashlib
import json
import re
import subprocess
import threading
from html import escape

from app import config
from app.config import CACHE, FFMPEG, FFPROBE
from app.filesystem import rel_of
from app.utils import natural_key

SUB_TYPES = {".srt", ".vtt"}

LANGS = {"fr": "Français", "en": "English", "ar": "Arabe",
         "es": "Español", "de": "Deutsch", "it": "Italiano"}

ffmpeg_semaphore = threading.Semaphore(2)
_durations = {}
_ainfo = {}
_failed = set()
COVER_NAMES = {"cover", "folder", "front", "album", "albumart", "artwork"}
COVER_EXT = {".jpg", ".jpeg", ".png", ".webp"}


def media_key(p):
    return escape(f"{config.ROOT_ID}:{rel_of(p)}", quote=True)


def duration_of(path):
    """Durée en secondes (ffprobe), None si indisponible. Mise en cache."""
    if not FFPROBE:
        return None
    st = path.stat()
    key = (str(path), st.st_mtime_ns, st.st_size)
    if key in _durations:
        return _durations[key]
    value = None
    try:
        out = subprocess.run(
            [FFPROBE, "-v", "error", "-show_entries", "format=duration",
             "-of", "default=nw=1:nk=1", str(path)],
            capture_output=True, text=True, timeout=20)
        value = float(out.stdout.strip())
    except (ValueError, subprocess.SubprocessError, OSError):
        value = None
    _durations[key] = value
    return value


def thumb_for(path):
    """Miniature JPEG en cache (ffmpeg), None si impossible."""
    if not FFMPEG:
        return None
    st = path.stat()
    key = hashlib.sha1(f"{path}|{st.st_mtime_ns}|{st.st_size}".encode()).hexdigest()
    out = CACHE / f"{key}.jpg"
    if out.exists():
        return out
    if key in _failed:
        return None
    with ffmpeg_semaphore:
        if out.exists():
            return out
        CACHE.mkdir(parents=True, exist_ok=True)
        dur = duration_of(path)
        tries = ([max(dur * 0.1, 1.0)] if dur else []) + [0.0]
        tmp = CACHE / f"{key}.tmp.jpg"
        for ss in tries:
            try:
                subprocess.run(
                    [FFMPEG, "-v", "error", "-y", "-ss", f"{ss:.2f}", "-i", str(path),
                     "-frames:v", "1", "-vf", "scale=480:-2", "-q:v", "5", str(tmp)],
                    capture_output=True, timeout=40)
            except (subprocess.SubprocessError, OSError):
                continue
            if tmp.exists() and tmp.stat().st_size > 0:
                tmp.replace(out)
                return out
        _failed.add(key)
    return None


def _tag(tags, *names):
    low = {str(k).lower(): v for k, v in (tags or {}).items()}
    for n in names:
        v = low.get(n)
        if v is not None and str(v).strip():
            return str(v).strip()
    return ""


def audio_info(path):
    """Durée, titre, artiste, album d'un fichier audio (ffprobe), mis en cache.
    Sans ffprobe ou si le fichier est illisible : valeurs vides, le lecteur se rabat sur le nom du fichier."""
    empty = {"duration": None, "title": "", "artist": "", "album": "", "embedded": False}
    if not FFPROBE:
        return empty
    try:
        st = path.stat()
    except OSError:
        return empty
    key = (str(path), st.st_mtime_ns, st.st_size)
    if key in _ainfo:
        return _ainfo[key]
    info = dict(empty)
    try:
        out = subprocess.run(
            [FFPROBE, "-v", "error", "-print_format", "json", "-show_format", "-show_streams", str(path)],
            capture_output=True, text=True, timeout=20)
        j = json.loads(out.stdout or "{}")
    except (ValueError, subprocess.SubprocessError, OSError):
        j = {}
    fmt = j.get("format") or {}
    try:
        d = float(fmt.get("duration"))
        info["duration"] = d if d > 0 else None
    except (TypeError, ValueError):
        pass
    tags = dict(fmt.get("tags") or {})
    for stream in j.get("streams") or []:
        if stream.get("codec_type") == "audio":
            for k, v in (stream.get("tags") or {}).items():     # ogg / opus : tags portés par le flux
                tags.setdefault(k, v)
        elif stream.get("codec_type") == "video" and (stream.get("disposition") or {}).get("attached_pic"):
            info["embedded"] = True
    info["title"] = _tag(tags, "title")
    info["artist"] = _tag(tags, "artist", "album_artist", "albumartist")
    info["album"] = _tag(tags, "album")
    if len(_ainfo) > 5000:
        _ainfo.clear()
    _ainfo[key] = info
    return info


def folder_cover(directory):
    """cover.jpg, folder.png, front.webp… présent dans le dossier de la piste."""
    try:
        for f in sorted(directory.iterdir(), key=lambda x: x.name.lower()):
            if f.suffix.lower() in COVER_EXT and f.stem.lower() in COVER_NAMES and f.is_file():
                return f
    except OSError:
        pass
    return None


def has_cover(path, info):
    return bool((info["embedded"] and FFMPEG) or folder_cover(path.parent))


def cover_for(path):
    """Pochette d'une piste : image intégrée aux tags (ffmpeg, JPEG en cache), sinon image du dossier."""
    info = audio_info(path)
    if info["embedded"] and FFMPEG:
        st = path.stat()
        key = hashlib.sha1(f"cover|{path}|{st.st_mtime_ns}|{st.st_size}".encode()).hexdigest()
        out = CACHE / f"{key}.jpg"
        if out.exists():
            return out
        if key not in _failed:
            with ffmpeg_semaphore:
                if out.exists():
                    return out
                CACHE.mkdir(parents=True, exist_ok=True)
                tmp = CACHE / f"{key}.tmp.jpg"
                try:
                    subprocess.run(
                        [FFMPEG, "-v", "error", "-y", "-i", str(path), "-an", "-map", "0:v:0", "-frames:v", "1",
                         "-vf", "scale='min(640,iw)':-2", "-q:v", "4", str(tmp)],
                        capture_output=True, timeout=40)
                except (subprocess.SubprocessError, OSError):
                    pass
                if tmp.exists() and tmp.stat().st_size > 0:
                    tmp.replace(out)
                    return out
                _failed.add(key)
    return folder_cover(path.parent)


def find_subtitles(video):
    subs = []
    stem = video.stem.casefold() + "."
    try:
        for f in sorted(video.parent.iterdir(), key=natural_key):
            if f.suffix.lower() in SUB_TYPES and f.name.casefold().startswith(stem) and f.is_file():
                subs.append((f, f.stem[len(video.stem) + 1:]))
    except OSError:
        pass
    return subs


def srt_to_vtt(text):
    text = text.replace("\r\n", "\n").replace("\r", "\n").lstrip("\ufeff")
    if text.startswith("WEBVTT"):
        return text
    text = re.sub(r"(\d{2}:\d{2}:\d{2}),(\d{3})", r"\1.\2", text)
    return "WEBVTT\n\n" + text
