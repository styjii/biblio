"""Lecture/écriture du fichier .env (jeton d'accès, mots de passe)."""

import os
import re
import secrets
from pathlib import Path

from app import config


def read_env(path):
    """Lit un fichier .env (CLE=valeur, # commentaires, guillemets facultatifs)."""
    values = {}
    try:
        text = path.read_text(encoding="utf-8-sig")
    except OSError:
        return values
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        if line.startswith("export "):
            line = line[7:].lstrip()
        key, _, val = line.partition("=")
        key, val = key.strip(), val.strip()
        if len(val) >= 2 and val[0] == val[-1] and val[0] in "\"'":
            val = val[1:-1]
        if key:
            values[key] = val
    return values


def write_env_value(path, key, value):
    """Ajoute ou remplace CLE=valeur dans le .env (écriture atomique, droits 0600)."""
    try:
        lines = path.read_text(encoding="utf-8-sig").splitlines()
    except OSError:
        lines = []
    new = f"{key}={value}"
    pattern = re.compile(rf"\s*(export\s+)?{re.escape(key)}\s*=")
    for i, line in enumerate(lines):
        if pattern.match(line):
            lines[i] = new
            break
    else:
        lines.append(new)
    tmp = path.with_name(path.name + ".tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    os.chmod(tmp, 0o600)
    os.replace(tmp, path)


def conf(key):
    """Variable d'environnement si définie, sinon valeur du .env."""
    return os.environ.get(key) or config.ENV.get(key) or ""


def load_token():
    """Jeton d'accès : BIBLIO_TOKEN (environnement ou .env). Absent, il est créé et écrit dans le .env."""
    value = conf("BIBLIO_TOKEN")
    if value:
        return value
    # Migration : ancien emplacement ~/.config/biblio/token
    try:
        legacy = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "biblio" / "token"
        value = legacy.read_text().strip()
    except (OSError, RuntimeError):
        value = ""
    value = value or secrets.token_urlsafe(12)
    try:
        write_env_value(config.ENV_PATH, "BIBLIO_TOKEN", value)
    except OSError as e:
        print(f"Attention : impossible d'écrire {config.ENV_PATH} ({e.strerror}) : le jeton ne sera pas conservé.")
    return value
