"""Lecteur vidéo : orientation du plein écran (automatique, paysage, portrait) et masquage du curseur de la souris."""
import unittest

from app import assets, config
from app.icons import ICONS


class OrientationPleinEcranTests(unittest.TestCase):
    js = assets.WATCH_JS

    def test_trois_modes_dont_automatique(self):
        self.assertIn("static ORIENTATIONS = ['auto', 'landscape', 'portrait'];", self.js)
        for label in ("Automatique", "Paysage", "Portrait"):
            self.assertIn(label, self.js)

    def test_automatique_suit_la_forme_de_la_video(self):
        self.assertIn("video.videoHeight > video.videoWidth ? 'portrait' : 'landscape'", self.js)
        # autre vidéo chargée en plein écran, ou forme de l'image modifiée : l'écran suit
        self.assertIn("video.addEventListener('loadedmetadata'", self.js.split("#bindOrientation() {")[1])
        self.assertIn("video.addEventListener('resize'", self.js.split("#bindOrientation() {")[1])

    def test_verrouillage_seulement_en_plein_ecran(self):
        body = self.js.split("async #applyOrientation(announce = false) {")[1].split("#setOrientation(mode) {")[0]
        self.assertIn("if (!this.#fullscreen) return;", body)
        self.assertIn("screen.orientation.lock(this.#wantedOrientation())", body)
        self.assertIn("screen.orientation?.unlock?.()", self.js)           # déverrouillé à la sortie du plein écran

    def test_option_du_menu_visible_seulement_en_plein_ecran(self):
        self.assertIn("if (this.#fullscreen) {", self.js.split("row('Orientation'")[0][-600:])
        self.assertIn("panel === 'orient' && !this.#fullscreen ? 'root' : panel", self.js)

    def test_choix_memorise_et_ancien_verrouillage_paysage_retire(self):
        self.assertIn("prefs.set('orient', mode)", self.js)
        self.assertIn("prefs.get('orient', 'auto')", self.js)
        self.assertNotIn("lock?.('landscape')", self.js)

    def test_icone_fournie_au_lecteur(self):
        self.assertIn("orientation", ICONS)
        player = (config.HERE / "app/routes/player.py").read_text(encoding="utf-8")
        self.assertIn('"download", "orientation")', player)


class MasquageCurseurTests(unittest.TestCase):
    js = assets.WATCH_JS

    def test_delai_de_trois_secondes(self):
        self.assertIn("static CURSOR_HIDE_AFTER = 3000;", self.js)

    def test_masque_apres_inactivite_et_reaffiche_au_mouvement(self):
        body = self.js.split("#bindCursor() {")[1].split("/* ----- masquage automatique des commandes")[0]
        self.assertIn("box.classList.remove('cursor-off')", body)             # réaffiché à chaque mouvement
        self.assertIn("box.classList.add('cursor-off'), PlayerUI.CURSOR_HIDE_AFTER", body)
        self.assertIn("box.addEventListener('pointermove'", body)
        self.assertIn("e.pointerType === 'mouse'", body)                      # le tactile n'a pas de curseur

    def test_regle_css_sur_tout_le_lecteur(self):
        self.assertIn(".player.vp-on.cursor-off,.player.vp-on.cursor-off *{cursor:none!important}", assets.CSS)
        self.assertNotIn(".player.vp-on.ui-off:not(.paused){cursor:none}", assets.CSS)   # plus lié au masquage des commandes


if __name__ == "__main__":
    unittest.main()
