"""Mobile : les lecteurs (vidéo et audio) restent collés sous la barre du haut, avec toutes leurs commandes, pendant que la liste défile."""
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
    def test_video_lecteur_colle_avec_toutes_ses_commandes(self):
        mobile = media_block(assets.CSS, "max-width:999px")
        player = re.search(r"\.player\{([^}]*)\}", mobile).group(1)
        self.assertIn("position:sticky", player)
        self.assertIn("top:var(--tb)", player)
        self.assertIn(".info{display:contents}", mobile)
        # plus aucune barre de commandes en dehors du lecteur (donc rien à coller sous lui)
        self.assertNotIn(".wbar", assets.CSS)
        self.assertNotIn(".wctrls", assets.CSS)

    def test_video_plus_de_mesure_de_la_hauteur_du_lecteur(self):
        self.assertNotIn("'--ph'", assets.WATCH_JS)

    def test_audio_lecteur_colle_sous_la_barre_du_haut(self):
        mobile = media_block(assets.LISTEN_CSS, "max-width:639px")
        self.assertIn(".listen{display:block", mobile)        # une grille limiterait le collage à la hauteur de sa ligne
        lplayer = re.search(r"\.lplayer\{([^}]*)\}", mobile).group(1)
        self.assertIn("position:sticky", lplayer)
        self.assertIn("top:var(--tb)", lplayer)


if __name__ == "__main__":
    unittest.main()
