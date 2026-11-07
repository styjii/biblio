"""Aperçu vidéo sur les vignettes : script servi sur la navigation et le lecteur, règles CSS, garde-fous."""
import unittest

from app import assets


class ApercuSurvolTests(unittest.TestCase):
    js = assets.HOVER_PREVIEW_JS

    def test_extrait_muet_en_boucle_et_automatique(self):
        for needle in ("video.muted = true", "video.loop = true", "video.autoplay = true", "playsinline"):
            self.assertIn(needle, self.js)

    def test_souris_et_tactile(self):
        for event in ("pointerover", "pointerout", "pointerdown", "pointerup", "pointercancel", "pointermove"):
            self.assertIn(f"'{event}'", self.js)

    def test_retour_a_l_etat_initial(self):
        # l'arrêt vide la source (connexion libérée) puis retire la vidéo
        self.assertIn("video.removeAttribute('src')", self.js)
        self.assertIn("video.remove()", self.js)
        for cause in ("scroll", "visibilitychange", "pagehide"):
            self.assertIn(cause, self.js)

    def test_zone_sensible_toute_la_carte(self):
        self.assertIn("const ITEM = '.vcard,.row[data-f]'", self.js)      # carte entière ou ligne de la liste, pas seulement l'image
        self.assertNotIn("thumbOf", self.js)
        self.assertIn(".vcard,.row{-webkit-touch-callout:none", assets.CSS)

    def test_video_placee_au_dessus_de_l_image(self):
        # gabarit : .ph, puis <img> : insérer après le premier des deux (.ph) cacherait la vidéo sous l'image
        card = (assets.FRONTEND_DIR / "templates/components/video_card.html").read_text(encoding="utf-8")
        self.assertLess(card.index("class='ph'"), card.index("<img"))
        self.assertIn("thumb.querySelector('img') ?? thumb.querySelector('.ph')", self.js)
        self.assertNotIn("querySelector('img, .ph')", self.js)

    def test_aucun_garde_fou_silencieux(self):
        # un réglage système (animations réduites, économie de données) ne doit pas désactiver l'aperçu sans rien dire
        self.assertNotIn("prefers-reduced-motion", self.js)
        self.assertNotIn("saveData", self.js)
        self.assertIn("dragstart", self.js)

    def test_garde_fous(self):
        self.assertIn("'cur'", self.js)                                   # pas d'aperçu de la vidéo en cours de lecture

    def test_style_de_l_apercu(self):
        self.assertIn("video.pv", assets.CSS)
        self.assertIn(".pv-on", assets.CSS)
        self.assertIn("-webkit-touch-callout:none", assets.CSS)           # appui long : pas de menu du navigateur


if __name__ == "__main__":
    unittest.main()
