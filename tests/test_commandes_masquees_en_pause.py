"""Lecteur vidéo : en pause, les commandes se masquent après un moment d'inactivité et reviennent au moindre mouvement,
comme pendant la lecture ; la vidéo elle-même n'est pas touchée."""
import unittest

from app import assets


class CommandesEnPauseTests(unittest.TestCase):
    js = assets.WATCH_JS

    def _method(self, signature):
        return self.js.split(signature)[1].split("\n")[0]

    def test_masquage_possible_en_pause(self):
        hide = self._method("#hideUI() {")
        self.assertNotIn("video.paused", hide)                 # plus réservé à la lecture
        self.assertIn("!video.ended", hide)                    # mais pas quand la vidéo est terminée (Revoir, suivante)
        schedule = self.js.split("#schedule(delay = PlayerUI.HIDE_AFTER) {")[1].split("\n  }\n")[0]
        self.assertNotIn("video.paused", schedule)
        self.assertIn("video.ended", schedule)

    def test_la_pause_lance_le_delai_d_inactivite(self):
        self.assertIn("on('pause', () => this.#poke());", self.js)
        self.assertIn("on('ended', () => this.#showUI());", self.js)

    def test_le_masquage_ne_touche_pas_a_la_video(self):
        for name in ("#hideUI() {", "#schedule(delay = PlayerUI.HIDE_AFTER) {"):
            body = self.js.split(name)[1].split("\n  }\n")[0]
            for forbidden in ("video.pause", "video.play", "currentTime", "play()"):
                self.assertNotIn(forbidden, body)

    def test_reaffichage_au_mouvement_inchange(self):
        auto = self.js.split("#bindAutoHide() {")[1].split("\n  }\n")[0]
        self.assertIn("box.addEventListener('pointermove', (e) => { if (e.pointerType === 'mouse') this.#poke(); });", auto)
        self.assertIn("this.#ui.addEventListener('pointerdown', () => this.#poke());", auto)
        self.assertIn("document.addEventListener('keydown', () => this.#poke());", auto)


if __name__ == "__main__":
    unittest.main()
