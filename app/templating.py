"""Moteur de gabarits HTML minimal (aucune dépendance) pour les fichiers de `frontend/templates/`.

Syntaxe :
    {{ nom }}                 valeur insérée telle quelle (l'appelant échappe ce qui vient de l'extérieur)
    {{ icon nom taille }}     icône SVG (voir app/icons.py) ; une classe CSS peut suivre la taille
    {# commentaire #}         retiré au rendu

Mise en forme : un saut de ligne et l'indentation qui le suit sont supprimés au rendu. On peut donc écrire
un gabarit lisible (une balise par ligne, indentée) sans changer le HTML produit. Pour garder une espace
entre deux éléments, la placer sur la même ligne.
"""

import re

from app import config
from app.icons import icon

TEMPLATES_DIR = config.HERE / "frontend" / "templates"
_TOKEN = re.compile(r"\{\{\s*(?:icon\s+(\w+)\s+(\d+)(?:\s+(\w+))?|(\w+))\s*\}\}")
_COMMENT = re.compile(r"\{#.*?#\}", re.S)
_cache = {}


def _compile(name):
    if name not in _cache:
        raw = (TEMPLATES_DIR / (name + ".html")).read_text(encoding="utf-8")
        _cache[name] = re.sub(r"\n[ \t]*", "", _COMMENT.sub("", raw).strip())
    return _cache[name]


def render(template, /, **values):
    """Rend `frontend/templates/<template>.html` avec les valeurs données (toute valeur manquante est une erreur)."""
    def fill(m):
        if m.group(4) is None:
            return icon(m.group(1), int(m.group(2)), m.group(3) or "i")
        try:
            return str(values[m.group(4)])
        except KeyError:
            raise KeyError(f"gabarit « {template} » : valeur « {m.group(4)} » non fournie") from None

    return _TOKEN.sub(fill, _compile(template))
