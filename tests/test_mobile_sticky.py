"""Mobile : les commandes de lecture (vidéo et audio) restent collées sous la barre du haut pendant que la liste défile."""
import re
import unittest

from app import assets


def media_block(css, query):
    """Contenu de la règle @media dont la condition est exactement `query` (accolades équilibrées)."""
    start = css.index("@media(" + query + "){") + len("@media(" + query + "){")
    depth, i = 1, start
    while depth:
        depth += {"{": 1, "}": -1}.get(css[i], 0)
        i += 1
    return css[start:i - 1]


class MobileStickyTests(unittest.TestCase):
    def test_video_commandes_collees_sous_le_lecteur(self):
        mobile = media_block(assets.CSS, "max-width:999px")
        wbar = re.search(r"\.wbar\{([^}]*)\}", mobile).group(1)
        self.assertIn("position:sticky", wbar)
        self.assertIn("var(--ph", wbar)                       # calé sur la hauteur réelle du lecteur, mesurée par le script
        self.assertIn(".info{display:contents}", mobile)      # sinon la barre ne pourrait pas dépasser la hauteur de sa section
        self.assertNotIn(".wbar{", media_block(assets.CSS, "min-width:1000px"))   # le bureau n'est pas modifié

    def test_video_mesure_de_la_hauteur_du_lecteur(self):
        self.assertIn("'--ph'", assets.WATCH_JS)

    def test_audio_lecteur_colle_sous_la_barre_du_haut(self):
        mobile = media_block(assets.LISTEN_CSS, "max-width:899px")
        self.assertIn(".listen{display:block", mobile)        # une grille limiterait le collage à la hauteur de sa ligne
        lplayer = re.search(r"\.lplayer\{([^}]*)\}", mobile).group(1)
        self.assertIn("position:sticky", lplayer)
        self.assertIn("top:var(--tb)", lplayer)


if __name__ == "__main__":
    unittest.main()
