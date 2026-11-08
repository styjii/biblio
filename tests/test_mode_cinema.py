"""Mode cinéma : bouton toujours présent (plein écran ou non, grand ou petit écran) et effet visible dans chaque situation."""
import re
import unittest

from app import assets
from test_mobile_sticky import media_block


class BoutonCinemaTests(unittest.TestCase):
    css = assets.CSS

    def test_bouton_sans_restriction_d_ecran(self):
        html = (assets.FRONTEND_DIR / "templates/player/watch.html").read_text(encoding="utf-8")
        button = re.search(r"<button[^>]*data-act='theater'[^>]*>", html).group(0)
        self.assertNotIn("vp-desk", button)
        self.assertNotIn("hidden", button)
        self.assertNotIn("vp-desk", self.css)                          # plus aucune règle ne le masque (écran étroit, petit lecteur)

    def test_barre_resserree_sur_telephone_pour_tout_garder(self):
        self.assertIn("@container vp (max-width:420px){", self.css)
        block = self.css.split("@container vp (max-width:420px){")[1].split("\n}\n")[0]
        self.assertIn(".vp-b{width:34px; height:34px}", block)


class EffetDuModeCinemaTests(unittest.TestCase):
    css = assets.CSS
    js = assets.WATCH_JS

    def test_grand_ecran_inchange(self):
        wide = media_block(self.css, "min-width:1000px")
        self.assertIn(".watch.theater{grid-template-columns:minmax(0,1fr);", wide)
        self.assertIn(".watch.theater .next{position:static;", wide)

    def test_ecran_etroit_lecteur_a_la_forme_de_la_video(self):
        fixed = media_block(self.css, "max-width:999px) and (min-height:501px")
        rule = re.search(r"\.watch\.theater \.dock \.player\{([^}]*)\}", fixed).group(1)
        self.assertIn("aspect-ratio:var(--vp-ar,16/9)", rule)
        self.assertIn("max-height:calc(100dvh - var(--tb) - 190px)", rule)         # reste de la place pour les informations et la liste
        self.assertIn("--vp-ar", self.js)                                          # posée par le script d'après la vidéo

    def test_plein_ecran_image_sans_bandes_noires_si_peu_rognee(self):
        self.assertIn(".player.fill video{object-fit:cover}", self.css)
        fit = self.js.split("#fit() {")[1].split("\n  }\n")[0]
        self.assertIn("this.#page.classList.contains('theater') && this.#fullscreen", fit)
        self.assertIn("1 - Math.min(r, 1 / r) <= PlayerUI.FILL_MAX_CROP", fit)
        self.assertIn("static FILL_MAX_CROP = 0.25;", self.js)

    def test_remplissage_recalcule_a_chaque_changement(self):
        shape = self.js.split("#bindShape() {")[1].split("\n  }\n")[0]
        for event in ("loadedmetadata", "resize", "emptied"):
            self.assertIn(event, shape)
        self.assertIn("addEventListener('resize', () => this.#fit())", shape)       # rotation de l'appareil
        sync = self.js.split("#bindScreen() {")[1]
        self.assertIn("this.#fit();", sync)                                         # entrée / sortie du plein écran
        self.assertIn("this.#fit();", self.js.split("toggleTheater(force) {")[1].split("\n  }\n")[0])

    def test_message_quand_la_page_ne_montre_pas_le_changement(self):
        body = self.js.split("toggleTheater(force) {")[1].split("\n  }\n")[0]
        self.assertIn("force === undefined && (this.#fullscreen || innerWidth < 1000)", body)
        self.assertIn("say(on ? 'Mode cinéma activé' : 'Mode cinéma désactivé')", body)


if __name__ == "__main__":
    unittest.main()
