"""Lecteurs : commandes de la vidéo rangées dans le lecteur, lecteur audio adaptatif (largeur, hauteur, tactile, encoches)."""
import re
import unittest

from app import assets


class LecteurVideoTests(unittest.TestCase):
    def test_gabarit_sans_commande_externe(self):
        html = (assets.FRONTEND_DIR / "templates/player/watch.html").read_text(encoding="utf-8")
        for gone in ("wbar", "wctrls", "id='autonext'", "id='w-", "class='switch'"):
            self.assertNotIn(gone, html)
        self.assertNotIn("raw?dl=1", html)                        # le téléchargement est dans le menu des paramètres
        for act in ("prev", "back", "fwd", "next", "settings"):
            self.assertIn(f"data-act='{act}'", html)
        for act in ("shuffle", "repeat", "cc", "rate"):               # ces commandes sont dans le menu des paramètres, pas dans la barre
            self.assertNotIn(f"data-act='{act}'", html)

    def test_script_sans_reference_aux_anciens_boutons(self):
        self.assertIsNone(re.search(r"\$\('w-", assets.WATCH_JS))
        self.assertNotIn("$('autonext')", assets.WATCH_JS)

    def test_menu_des_parametres_complet(self):
        for label in ("Lecture automatique", "Lecture aléatoire", "Répétition", "Vitesse de lecture", "Sous-titres",
                      "Télécharger la vidéo"):
            self.assertIn(label, assets.WATCH_JS)

    def test_mode_compact_du_lecteur(self):
        self.assertIn("@container vp (max-width:640px)", assets.CSS)      # lecteur étroit : commandes principales au centre
        self.assertIn(".vp-mid{display:flex}", assets.CSS)
        for cls in (".vp-sk", ".vp-skb"):
            self.assertIn(cls, assets.CSS)


    def test_volume_jamais_masque(self):
        """Le bouton muet et le curseur de volume ne sont masqués dans aucun mode (tactile, lecteur étroit, petit écran)."""
        for selector, body in re.findall(r"([^{}]+)\{([^{}]*)\}", assets.CSS):
            if "display:none" not in body.replace(" ", ""):
                continue
            for part in (p.strip() for p in selector.split(",")):
                self.assertNotIn(part, (".vp-vol", ".vp-vol .vp-b", "#vp-mute", "[data-act='mute']"), selector)
        # curseur toujours visible à l'écran tactile (pas de survol au doigt)
        self.assertRegex(assets.CSS, r"@media\(pointer:coarse\)\{[^@]*\.vp-vol \.vp-rng\{[^}]*opacity:1")

    def test_meme_barre_de_volume_partout(self):
        """Une seule barre de volume (celle du plein écran) : aucune règle de taille de lecteur ne la modifie, et sa largeur est un jeton unique."""
        css = assets.CSS
        self.assertIn("--vp-volw:80px", css)
        self.assertEqual(css.count("width:var(--vp-volw)"), 2)               # survol (souris) et écran tactile : même largeur
        for block in re.findall(r"@container vp \([^)]*\)\{((?:[^{}]|\{[^{}]*\})*)\}", css):
            self.assertNotIn(".vp-rng", block)                                 # ni largeur, ni pastille, ni opacité propres à un lecteur étroit

    def test_icones_toutes_en_contour(self):
        """Lecture, pause, précédent, suivant : contour arrondi comme l'icône du volume, jamais remplis."""
        for text in (assets.CSS, assets.LISTEN_CSS):
            self.assertNotIn("fill:currentColor", text)
        from app.icons import ICONS
        for name in ("play", "pause", "next", "prev", "back10", "fwd10"):
            self.assertNotIn("<polygon", ICONS[name], name)
            self.assertNotIn("<text", ICONS[name], name)

    def test_volume_impose_par_le_systeme(self):
        self.assertIn("classList.toggle('fixed'", assets.WATCH_JS)         # iPhone : curseur retiré, bouton muet conservé


class LecteurAudioTests(unittest.TestCase):
    css = assets.LISTEN_CSS

    def test_trois_dispositions(self):
        self.assertIn("@media(min-width:640px)", self.css)                # tablette / ordinateur : deux colonnes
        self.assertIn("@media(max-width:639px)", self.css)                # téléphone en portrait : lecteur collé
        self.assertIn("(max-height:520px)", self.css)                     # écran peu haut : disposition compacte

    def test_tailles_suivant_le_lecteur_et_l_ecran(self):
        self.assertIn("container:lp / inline-size", self.css)
        self.assertIn("cqw", self.css)
        self.assertIn("dvh", self.css)                                    # barre d'adresse mobile qui apparaît / disparaît
        self.assertIn("safe-area-inset", self.css)                        # encoches et coins arrondis
        self.assertIn("pointer:coarse", self.css)                         # cibles tactiles plus grandes

    def test_gabarit_audio(self):
        html = (assets.FRONTEND_DIR / "templates/player/listen.html").read_text(encoding="utf-8")
        self.assertIn("class='ltools'", html)                             # modes + volume sur une même ligne en compact
        self.assertIn("class='lbl'", html)                                # libellé du téléchargement masquable

    def test_accolades_equilibrees(self):
        self.assertEqual(self.css.count("{"), self.css.count("}"))


if __name__ == "__main__":
    unittest.main()
