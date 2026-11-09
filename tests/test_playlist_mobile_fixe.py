"""Mobile à lecteur fixe : le lecteur et ses informations restent collés ensemble, la playlist met en évidence la vidéo en cours.
Les autres affichages (PC, mobile en paysage bas) ne changent pas."""
import re
import unittest

from app import assets
from test_mobile_sticky import media_block

FIXED = "max-width:999px) and (min-height:501px"


class DockMobileFixeTests(unittest.TestCase):
    css = assets.CSS

    def test_gabarit_lecteur_et_informations_dans_un_meme_conteneur(self):
        html = (assets.FRONTEND_DIR / "templates/player/watch.html").read_text(encoding="utf-8")
        dock = html[html.index("<div class='dock' id='dock'>"):html.index("<aside class='next'>")]
        self.assertIn("id='vbox'", dock)
        self.assertIn("class='info'", dock)
        self.assertIn("class='vtitle'", dock)
        self.assertIn("class='chips'", dock)                  # dossier, taille, sous-titres
        self.assertNotIn("class='next'", dock)                # la liste reste en dehors : c'est elle qui défile

    def test_hors_mode_fixe_le_conteneur_est_transparent(self):
        self.assertIn(".dock{display:contents}", self.css)

    def test_mode_fixe_colle_lecteur_et_informations(self):
        block = media_block(self.css, FIXED)
        dock = re.search(r"\.dock\{([^}]*)\}", block).group(1)
        for part in ("position:sticky", "top:var(--tb)", "display:block", "background:var(--bg)"):
            self.assertIn(part, dock)
        self.assertIn('grid-template-areas:"dock" "next"', block)

    def test_le_mode_fixe_est_la_complementaire_exacte_du_paysage_bas(self):
        self.assertIn("@media(max-width:999px) and (max-height:500px){", self.css)     # inchangé
        self.assertIn(f"@media({FIXED}){{", self.css)

    def test_blocs_existants_inchanges(self):
        mobile = media_block(self.css, "max-width:999px")
        self.assertIn(".info{display:contents}", mobile)
        self.assertIn("position:sticky", re.search(r"\.player\{([^}]*)\}", mobile).group(1))
        desktop = media_block(self.css, "min-width:1000px")
        self.assertNotIn("dock", desktop)

    def test_barre_de_defilement_masquee_seulement_en_mode_fixe(self):
        """La barre de la page (celle de la playlist) ne s'affiche pas par-dessus le lecteur fixe ; ailleurs, elle reste."""
        block = media_block(self.css, FIXED)
        self.assertIn("html:has(#watch){scrollbar-width:none}", block)
        self.assertIn("html:has(#watch)::-webkit-scrollbar{display:none}", block)
        outside = self.css.replace(block, "")
        self.assertNotIn("scrollbar-width:none}\n  html:has(#watch)", outside)
        self.assertNotIn("html:has(#watch)", outside)

    def test_clignotement_seulement_en_mode_fixe(self):
        outside = self.css.replace(media_block(self.css, FIXED), "")
        self.assertNotIn(".row.flash", outside)


class PlaylistSuitLaVideoTests(unittest.TestCase):
    js = assets.WATCH_JS

    def test_meme_condition_que_le_css(self):
        self.assertIn("matchMedia('(max-width:999px) and (min-height:501px)')", self.js)

    def test_vue_en_cours_amenee_sous_le_lecteur_fixe(self):
        body = self.js.split("#revealCurrent(smooth) {")[1].split("\n  }\n")[0]
        self.assertIn("dock.getBoundingClientRect().bottom", body)           # la ligne se place sous le lecteur et ses informations
        self.assertIn("scrollBy(", body)
        self.assertIn("classList.add('flash')", body)

    def test_appel_a_l_ouverture_et_a_chaque_changement_sur_place(self):
        self.assertIn("else if (list === 'fixed') requestAnimationFrame(() => this.#revealCurrent(false))", self.js)
        self.assertIn("if (list === 'fixed') this.#revealCurrent(!this.#isFullscreen());", self.js)

    def test_pc_avec_volet_lateral_conserve(self):
        self.assertIn("if (list === 'aside') document.querySelector('.row.cur')?.scrollIntoView({block: 'nearest'});", self.js)
        self.assertIn("else if (list === 'aside') document.querySelector('.list .row.cur')?.scrollIntoView({block: 'nearest'});", self.js)

    def test_lecteur_non_fixe_sans_defilement_automatique(self):
        """Mode cinéma et mobile en paysage bas : la liste est dans la page, qui ne doit pas descendre toute seule à la vidéo en cours."""
        mode = self.js.split("#listMode() {")[1].split("\n  }\n")[0]
        self.assertIn("if (VideoPlayer.FIXED_MOBILE.matches) return 'fixed';", mode)
        self.assertIn("if (innerWidth >= 1000 && !$('watch')?.classList.contains('theater')) return 'aside';", mode)
        self.assertIn("return 'static';", mode)
        # seuls les modes « fixed » et « aside » font défiler : aucun appel pour « static »
        self.assertEqual(self.js.count("scrollIntoView("), 2)
        self.assertNotIn("list === 'static'", self.js)


if __name__ == "__main__":
    unittest.main()
