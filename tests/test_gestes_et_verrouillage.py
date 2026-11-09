"""Lecteur vidéo : glissements au doigt (volume, position) et verrouillage des commandes."""
import unittest

from app import assets, config

WATCH_HTML = (assets.FRONTEND_DIR / "templates/player/watch.html").read_text(encoding="utf-8")
PLAYER_PY = (config.HERE / "app/routes/player.py").read_text(encoding="utf-8")


class GlissementsTests(unittest.TestCase):
    js = assets.WATCH_JS

    def test_indicateur_dans_le_lecteur(self):
        self.assertIn("id='vp-hud'", WATCH_HTML)
        for ident in ("vp-hud-ic", "vp-hud-tx", "vp-hud-sub"):
            self.assertIn(f"id='{ident}'", WATCH_HTML)

    def test_sens_choisi_une_fois_et_geste_tactile_seulement(self):
        body = self.js.split("#bindSwipe() {")[1].split("\n  }\n")[0]
        self.assertIn("if (e.pointerType === 'mouse') return;", body)
        self.assertIn("swipe.mode = !possible ? 'ignored' : horizontal ? 'seek' : 'volume';", body)
        self.assertIn("if (fingers.size > 1)", body)                       # pincement : pas un glissement
        self.assertIn("if (swipe.mode === 'seek' && commit) this.seekTo(swipe.target);", body)   # position appliquée au relâchement

    def test_une_tape_apres_un_glissement_est_ignoree(self):
        self.assertLess(self.js.index("this.#bindSwipe();"), self.js.index("this.#bindGestures();"))
        self.assertIn("if (this.#swiped) { this.#swiped = false; return; }", self.js)

    def test_position_jamais_jusqu_a_la_fin(self):
        seek = self.js.split("#swipeSeek(swipe, dx) {")[1].split("\n  }\n")[0]
        self.assertIn("END_GUARD", seek)

    def test_css_touch_action(self):
        css = assets.CSS
        self.assertIn(".player.vp-on video{touch-action:pan-y}", css)
        self.assertIn(".player.vp-on.vswipe video{touch-action:none}", css)


class VerrouillageTests(unittest.TestCase):
    js = assets.WATCH_JS

    def test_bouton_hors_de_la_couche_des_commandes(self):
        self.assertIn("id='vp-lock'", WATCH_HTML)
        self.assertGreater(WATCH_HTML.index("id='vp-lock'"), WATCH_HTML.index("id='vp-menu'"))
        self.assertLess(WATCH_HTML.index("id='vp-lock'"), WATCH_HTML.index("<section class='info'>"))
        self.assertIn('"lock", "unlock")', PLAYER_PY)                      # icônes fournies au script

    def test_le_bouton_change_d_icone_et_de_libelle(self):
        render = self.js.split("#renderLock() {")[1].split("\n  }\n")[0]
        self.assertIn("setIcon(button, this.#locked ? 'unlock' : 'lock');", render)
        self.assertIn("'Déverrouiller les commandes'", render)

    def test_boutons_gestes_molette_et_clavier_inactifs(self):
        self.assertIn("this.#ui.addEventListener('click', (e) => {\n      if (this.#locked) return;", self.js)
        self.assertIn("if (this.#locked) { this.#peekLock(); return; }", self.js)
        self.assertIn("if (this.#ui.locked) {", self.js)
        self.assertIn("if (lower === 'v') { this.#ui.toggleLock(); e.preventDefault(); }", self.js)
        self.assertIn("v: () => this.#ui.toggleLock(),", self.js)

    def test_verrouillage_transmis_a_la_page_suivante_seulement(self):
        self.assertIn("this.#ui.carryLock();", self.js)
        self.assertIn("sessionStorage.removeItem('vl:lock')", self.js)    # lu une seule fois

    def test_css(self):
        css = assets.CSS
        self.assertIn(".player.locked .vp-ui{opacity:0; visibility:hidden; pointer-events:none}", css)
        self.assertIn(".player.locked:not(.lock-peek) .vp-lock", css)


if __name__ == "__main__":
    unittest.main()
