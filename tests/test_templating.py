"""Moteur de gabarits et cohérence entre les appels `render(...)` et les fichiers de frontend/templates/."""
import ast
import re
import unittest
from pathlib import Path

from app.templating import TEMPLATES_DIR, TemplateEngine, render

APP = Path(__file__).resolve().parent.parent / "app"


def template_variables(name):
    raw = TemplateEngine.COMMENT.sub("", (TEMPLATES_DIR / (name + ".html")).read_text(encoding="utf-8"))
    return {m.group(4) for m in TemplateEngine.TOKEN.finditer(raw) if m.group(4)}


def render_calls():
    """(fichier, gabarit, noms des arguments) pour chaque `render("gabarit", a=…, b=…)` du code."""
    for path in sorted(APP.rglob("*.py")):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "render"
                    and node.args):
                continue
            if any(k.arg is None for k in node.keywords):
                continue  # **valeurs : non vérifiable statiquement
            first = node.args[0]
            names = ([first.value] if isinstance(first, ast.Constant)
                     else [first.body.value, first.orelse.value] if isinstance(first, ast.IfExp) else [])
            for name in names:  # `render("a" if cond else "b")` : les deux gabarits doivent convenir
                yield path.name, name, {k.arg for k in node.keywords}


class RenderTests(unittest.TestCase):
    def test_variable_et_collapse(self):
        out = render("components/pill_back", href="/x")
        self.assertTrue(out.startswith("<a class='pill' href='/x'><svg"))
        self.assertNotIn("\n", out)

    def test_valeur_manquante(self):
        with self.assertRaises(KeyError):
            render("components/pill_back")

    def test_valeurs_inserees_telles_quelles(self):
        self.assertIn("a\\1&b", render("pages/message", title="a\\1&b", text="", actions=""))


class TemplateConsistency(unittest.TestCase):
    def test_chaque_appel_fournit_exactement_les_variables_du_gabarit(self):
        calls = list(render_calls())
        self.assertGreater(len(calls), 30)
        for filename, name, given in calls:
            with self.subTest(template=name, file=filename):
                self.assertTrue((TEMPLATES_DIR / (name + ".html")).is_file(), "gabarit introuvable")
                self.assertEqual(template_variables(name), given)

    def test_aucun_gabarit_orphelin(self):
        used = {name for _, name, _ in render_calls()}
        # gabarits rendus avec **valeurs ou référencés autrement : à lister ici
        used |= {"partials/theme_init"}
        existing = {p.relative_to(TEMPLATES_DIR).with_suffix("").as_posix() for p in TEMPLATES_DIR.rglob("*.html")}
        self.assertEqual(existing - used, set())

    def test_les_gabarits_n_ont_pas_de_jeton_inconnu(self):
        for path in TEMPLATES_DIR.rglob("*.html"):
            text = TemplateEngine.COMMENT.sub("", path.read_text(encoding="utf-8"))
            leftovers = re.sub(TemplateEngine.TOKEN, "", text)
            self.assertNotIn("{{", leftovers, path.name)


if __name__ == "__main__":
    unittest.main()
