"""Lecteur vidéo : écran d'erreur, touches multimédia complètes, clavier et molette, pastille de vitesse, position dans la liste."""
import re
import unittest

from app import assets, config

WATCH_HTML = (assets.FRONTEND_DIR / "templates/player/watch.html").read_text(encoding="utf-8")


class EcranDErreurTests(unittest.TestCase):
    js = assets.WATCH_JS

    def test_panneau_dans_le_lecteur_masque_au_depart(self):
        self.assertRegex(WATCH_HTML, r"<div class='vp-err' id='vp-err' role='alert' hidden>")
        for action in ("retry", "download", "next"):
            self.assertIn(f"data-err='{action}'", WATCH_HTML)
        # hors de la barre de commandes : il ne disparaît pas avec elle après l'inactivité
        panel, ui = WATCH_HTML.index("id='vp-err'"), WATCH_HTML.index("id='vp-ui'")
        self.assertLess(panel, ui)

    def test_format_non_pris_en_charge_affiche_le_panneau(self):
        body = self.js.split("#bindError() {")[1].split("\n  }\n")[0]
        self.assertIn("video.error?.code === 4 && !this.#loadedOnce", body)
        self.assertIn("this.#loadedOnce = true; this.#hideError();", body)
        self.assertIn("[data-err]", body)

    def test_le_garde_previent_l_interface_quand_il_abandonne(self):
        self.assertIn("this.onFatal?.(", self.js.split("#giveUp() {")[1])
        self.assertIn("this.#guard.onFatal = (text) => this.#ui.showError(text);", self.js)

    def test_changement_de_video_efface_l_erreur(self):
        reload = self.js.split("  reload() {")[1].split("\n  }\n")[0]
        self.assertIn("this.#loadedOnce = false;", reload)
        self.assertIn("this.#hideError();", reload)

    def test_css(self):
        css = assets.CSS
        self.assertIn(".vp-err[hidden]{display:none}", css)
        self.assertRegex(css, r"\.vp-err\{position:absolute; inset:0;")
        self.assertNotRegex(re.search(r"\.vp-err\{[^}]*\}", css).group(0), "z-index")      # la barre reste au-dessus, utilisable


class TouchesMultimediaTests(unittest.TestCase):
    js = assets.WATCH_JS

    def test_actions_du_systeme(self):
        handlers = self.js.split("const handlers = {")[1].split("\n    };")[0]
        for name in ("previoustrack", "nexttrack", "seekbackward", "seekforward", "play", "pause", "seekto"):
            self.assertIn(f"{name}:", handlers)

    def test_position_et_etat_annonces(self):
        sync = self.js.split("#syncMediaSession() {")[1].split("\n  }\n")[0]
        self.assertIn("session.playbackState = video.paused ? 'paused' : 'playing'", sync)
        self.assertIn("setPositionState({duration: video.duration, playbackRate: video.playbackRate || 1", sync)
        self.assertIn("'durationchange', 'play', 'pause', 'seeked', 'ratechange'", self.js)

    def test_titre_dossier_et_vignette(self):
        meta = self.js.split("#updateMediaTitle(title) {")[1].split("\n  }\n")[0]
        self.assertIn("artist: folder", meta)
        self.assertIn("/thumb?f=${encodeURIComponent(items[index].f)}", meta)


class ClavierEtMoletteTests(unittest.TestCase):
    js = assets.WATCH_JS

    def test_fin_et_image_par_image(self):
        self.assertIn("End: () => this.#ui.jumpTo(1),", self.js)
        self.assertIn("',': () => (video.paused ? this.#ui.step(-1) : this.#settings.stepRate(-1))", self.js)
        self.assertIn("'.': () => (video.paused ? this.#ui.step(1) : this.#settings.stepRate(1))", self.js)
        step = self.js.split("  step(direction) {")[1].split("\n  }\n")[0]
        self.assertIn("if (!video.paused", step)                 # seulement en pause
        self.assertIn("END_GUARD", step)                         # jamais jusqu'à la toute fin

    def test_vitesse_au_clavier_inchangee(self):
        self.assertIn("'<': () => this.#settings.stepRate(-1),", self.js)
        self.assertIn("'>': () => this.#settings.stepRate(1),", self.js)

    def test_molette_sur_le_volume_et_en_plein_ecran_seulement(self):
        wheel = self.js.split("#bindWheel() {")[1].split("\n  }\n")[0]
        self.assertIn("$('vp-volbox')?.addEventListener('wheel', change, {passive: false})", wheel)
        self.assertIn("if (this.#fullscreen && e.target === video) change(e);", wheel)     # hors plein écran, la molette fait défiler la page
        self.assertIn("e.preventDefault();", wheel)

    def test_raccourcis_documentes(self):
        for text in ("<kbd>Fin</kbd>", "image par image (en pause)", "molette sur le volume"):
            self.assertIn(text, WATCH_HTML)


class VitesseEtListeTests(unittest.TestCase):
    js = assets.WATCH_JS

    def test_vitesse_seulement_dans_le_menu(self):
        """La vitesse se règle dans le menu des paramètres (et aux touches < et >) : plus de pastille dans la barre."""
        self.assertNotIn("vp-rate", WATCH_HTML)
        self.assertNotIn("vp-rate", assets.CSS)
        self.assertNotIn("#renderRate", self.js)
        self.assertIn("row('Vitesse de lecture', {icon: ic('gauge')", self.js)
        self.assertIn("on('ratechange', () => { if (!this.#menu.hidden) this.#renderMenu(true); });", self.js)

    def test_position_dans_la_liste(self):
        self.assertIn("<span class='cnt' id='list-pos'>{{ pos }}</span>", WATCH_HTML)
        src = (config.HERE / "app/routes/player.py").read_text(encoding="utf-8")
        self.assertIn('pos=f"{idx + 1} / {len(siblings)}"', src)
        self.assertIn("document.querySelector('.next h2').innerHTML = page.querySelector('.next h2')?.innerHTML", self.js)   # suit la vidéo sur place


if __name__ == "__main__":
    unittest.main()
