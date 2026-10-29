"""Petits utilitaires sans dépendance applicative."""

import json
import os
import re
import subprocess


def natural_key(p):
    return [int(t) if t.isdigit() else t.casefold() for t in re.split(r"(\d+)", p.name)]


def fmt_size(n):
    for unit, div in (("Go", 1024 ** 3), ("Mo", 1024 ** 2), ("Ko", 1024)):
        if n >= div:
            v = n / div
            return (f"{v:.1f}" if v < 10 else f"{v:.0f}").replace(".", ",") + " " + unit
    return f"{n} o"


def js_json(obj):
    return (json.dumps(obj).replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026"))


def lan_ips():
    try:
        out = subprocess.run(["hostname", "-I"], capture_output=True, text=True, timeout=3).stdout.split()
        return [ip for ip in out if ":" not in ip]
    except (OSError, subprocess.SubprocessError):
        return []


def atomic_write(path, text, mode=0o600):
    """Écrit un fichier texte de façon atomique (fichier temporaire puis remplacement), avec ces droits."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, mode)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(text)
    os.chmod(tmp, mode)
    os.replace(tmp, path)
