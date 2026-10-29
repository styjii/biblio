"""Médias : miniatures et durées (ffmpeg), tags audio, pochettes, sous-titres."""

import hashlib
import json
import re
import subprocess
import threading
from html import escape

from app import config
from app.filesystem import rel_of
from app.utils import natural_key


class MediaLibrary:
    """Extraction d'informations sur les vidéos et les pistes audio (ffmpeg / ffprobe), avec caches en mémoire et sur disque."""
    SUB_TYPES = {".srt", ".vtt"}
    LANGS = {"fr": "Français", "en": "English", "ar": "Arabe", "es": "Español", "de": "Deutsch", "it": "Italiano"}
    COVER_NAMES = {"cover", "folder", "front", "album", "albumart", "artwork"}
    COVER_EXT = {".jpg", ".jpeg", ".png", ".webp"}
    MAX_AUDIO_CACHE = 5000
    EMPTY_AUDIO = {"duration": None, "title": "", "artist": "", "album": "", "embedded": False}

    def __init__(self, cache_dir, ffmpeg, ffprobe, max_parallel=2):
        self.cache_dir = cache_dir
        self.ffmpeg = ffmpeg
        self.ffprobe = ffprobe
        self.semaphore = threading.Semaphore(max_parallel)   # limite les processus ffmpeg simultanés
        self._durations = {}
        self._audio = {}
        self._failed = set()

    # --- utilitaires ---
    @staticmethod
    def key(p):
        """Clé stable d'un média (dossier servi + chemin), utilisée côté navigateur pour mémoriser la lecture."""
        return escape(f"{config.ROOT_ID}:{rel_of(p)}", quote=True)

    @staticmethod
    def _signature(path):
        st = path.stat()
        return str(path), st.st_mtime_ns, st.st_size

    @staticmethod
    def _tag(tags, *names):
        low = {str(k).lower(): v for k, v in (tags or {}).items()}
        for n in names:
            v = low.get(n)
            if v is not None and str(v).strip():
                return str(v).strip()
        return ""

    # --- durées et miniatures ---
    def duration(self, path):
        """Durée en secondes (ffprobe), None si indisponible. Mise en cache."""
        if not self.ffprobe:
            return None
        key = self._signature(path)
        if key in self._durations:
            return self._durations[key]
        try:
            out = subprocess.run(
                [self.ffprobe, "-v", "error", "-show_entries", "format=duration", "-of", "default=nw=1:nk=1", str(path)],
                capture_output=True, text=True, timeout=20)
            value = float(out.stdout.strip())
        except (ValueError, subprocess.SubprocessError, OSError):
            value = None
        self._durations[key] = value
        return value

    def _cached_image(self, key, attempts):
        """Image JPEG en cache : `attempts(tmp)` donne les commandes ffmpeg à essayer pour la produire (None si toutes échouent)."""
        out = self.cache_dir / f"{key}.jpg"
        if out.exists():
            return out
        if key in self._failed:
            return None
        with self.semaphore:
            if out.exists():
                return out
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            tmp = self.cache_dir / f"{key}.tmp.jpg"
            for command in attempts(tmp):
                try:
                    subprocess.run(command, capture_output=True, timeout=40)
                except (subprocess.SubprocessError, OSError):
                    continue
                if tmp.exists() and tmp.stat().st_size > 0:
                    tmp.replace(out)
                    return out
            self._failed.add(key)
        return None

    def thumbnail(self, path):
        """Miniature JPEG d'une vidéo (ffmpeg), None si impossible."""
        if not self.ffmpeg:
            return None
        _, mtime, size = self._signature(path)
        key = hashlib.sha1(f"{path}|{mtime}|{size}".encode()).hexdigest()

        def attempts(tmp):
            dur = self.duration(path)
            for ss in ([max(dur * 0.1, 1.0)] if dur else []) + [0.0]:
                yield [self.ffmpeg, "-v", "error", "-y", "-ss", f"{ss:.2f}", "-i", str(path),
                       "-frames:v", "1", "-vf", "scale=480:-2", "-q:v", "5", str(tmp)]

        return self._cached_image(key, attempts)

    # --- audio ---
    def audio_info(self, path):
        """Durée, titre, artiste, album d'un fichier audio (ffprobe), mis en cache.
        Sans ffprobe ou si le fichier est illisible : valeurs vides, le lecteur se rabat sur le nom du fichier."""
        if not self.ffprobe:
            return dict(self.EMPTY_AUDIO)
        try:
            key = self._signature(path)
        except OSError:
            return dict(self.EMPTY_AUDIO)
        if key in self._audio:
            return self._audio[key]
        info = dict(self.EMPTY_AUDIO)
        try:
            out = subprocess.run(
                [self.ffprobe, "-v", "error", "-print_format", "json", "-show_format", "-show_streams", str(path)],
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
        info["title"] = self._tag(tags, "title")
        info["artist"] = self._tag(tags, "artist", "album_artist", "albumartist")
        info["album"] = self._tag(tags, "album")
        if len(self._audio) > self.MAX_AUDIO_CACHE:
            self._audio.clear()
        self._audio[key] = info
        return info

    def folder_cover(self, directory):
        """cover.jpg, folder.png, front.webp… présent dans le dossier de la piste."""
        try:
            for f in sorted(directory.iterdir(), key=lambda x: x.name.lower()):
                if f.suffix.lower() in self.COVER_EXT and f.stem.lower() in self.COVER_NAMES and f.is_file():
                    return f
        except OSError:
            pass
        return None

    def has_cover(self, path, info):
        return bool((info["embedded"] and self.ffmpeg) or self.folder_cover(path.parent))

    def cover_for(self, path):
        """Pochette d'une piste : image intégrée aux tags (ffmpeg, JPEG en cache), sinon image du dossier."""
        info = self.audio_info(path)
        if info["embedded"] and self.ffmpeg:
            _, mtime, size = self._signature(path)
            key = hashlib.sha1(f"cover|{path}|{mtime}|{size}".encode()).hexdigest()

            def attempts(tmp):
                yield [self.ffmpeg, "-v", "error", "-y", "-i", str(path), "-an", "-map", "0:v:0", "-frames:v", "1",
                       "-vf", "scale='min(640,iw)':-2", "-q:v", "4", str(tmp)]

            cover = self._cached_image(key, attempts)
            if cover:
                return cover
        return self.folder_cover(path.parent)

    # --- sous-titres ---
    def find_subtitles(self, video):
        """Sous-titres voisins de la vidéo (« film.fr.srt »…) -> [(fichier, suffixe de langue)]."""
        subs = []
        stem = video.stem.casefold() + "."
        try:
            for f in sorted(video.parent.iterdir(), key=natural_key):
                if f.suffix.lower() in self.SUB_TYPES and f.name.casefold().startswith(stem) and f.is_file():
                    subs.append((f, f.stem[len(video.stem) + 1:]))
        except OSError:
            pass
        return subs

    @staticmethod
    def srt_to_vtt(text):
        text = text.replace("\r\n", "\n").replace("\r", "\n").lstrip("\ufeff")
        if text.startswith("WEBVTT"):
            return text
        text = re.sub(r"(\d{2}:\d{2}:\d{2}),(\d{3})", r"\1.\2", text)
        return "WEBVTT\n\n" + text


media = MediaLibrary(config.CACHE, config.FFMPEG, config.FFPROBE)
