"""« Vidéo suivante / précédente » en plein écran : la vidéo se charge dans le même lecteur, le plein écran n'est jamais fermé."""
import unittest

from app import assets


class PleinEcranSuivanteTests(unittest.TestCase):
    js = assets.WATCH_JS

    def test_etat_du_plein_ecran_verifie_au_clic(self):
        self.assertIn("document.fullscreenElement", self.js)
        self.assertIn("webkitDisplayingFullscreen", self.js)              # plein écran natif d'iOS
        self.assertIn("this.#isFullscreen()", self.js)

    def test_chargement_sur_place_et_repli_par_navigation(self):
        self.assertIn("#loadInPlace(target)", self.js)
        self.assertIn(".catch(() => this.#leaveTo(target))", self.js)     # échec réseau : navigation classique
        self.assertIn("history.pushState", self.js)                       # l'adresse suit la vidéo

    def test_etat_remis_a_zero_pour_la_nouvelle_video(self):
        for needle in ("this.#guard.reset()", "this.#resume.reset()", "this.#resume.leave()", "this.#ui.reload()", "this.#order.restore("):
            self.assertIn(needle, self.js)
        self.assertIn("let {index} = cfg;", self.js)                      # l'index de la vidéo ouverte peut changer
        self.assertIn("get #rel() { return items[index].f; }", self.js)   # position mémorisée : toujours celle de la vidéo ouverte

    def test_le_plein_ecran_n_est_jamais_ferme(self):
        body = self.js.split("async #loadInPlace(target) {")[1].split("#applyPage(page) {")[0]
        self.assertNotIn("exitFullscreen", body)


if __name__ == "__main__":
    unittest.main()
