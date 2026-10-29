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


class TemplateEngine:
    """Charge, met en cache et rend les gabarits d'un dossier."""
    TOKEN = re.compile(r"\{\{\s*(?:icon\s+(\w+)\s+(\d+)(?:\s+(\w+))?|(\w+))\s*\}\}")
    COMMENT = re.compile(r"\{#.*?#\}", re.S)

    def __init__(self, directory):
        self.directory = directory
        self._cache = {}

    def _compile(self, name):
        if name not in self._cache:
            raw = (self.directory / (name + ".html")).read_text(encoding="utf-8")
            self._cache[name] = re.sub(r"\n[ \t]*", "", self.COMMENT.sub("", raw).strip())
        return self._cache[name]

    def render(self, template, /, **values):
        """Rend `<dossier>/<template>.html` avec les valeurs données (toute valeur manquante est une erreur)."""
        def fill(m):
            if m.group(4) is None:
                return icon(m.group(1), int(m.group(2)), m.group(3) or "i")
            try:
                return str(values[m.group(4)])
            except KeyError:
                raise KeyError(f"gabarit « {template} » : valeur « {m.group(4)} » non fournie") from None

        return self.TOKEN.sub(fill, self._compile(template))


engine = TemplateEngine(TEMPLATES_DIR)
render = engine.render      # raccourci utilisé par toutes les pages : render("dossier/gabarit", valeur=…)
