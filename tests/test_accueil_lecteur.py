"""Page d'accueil : onglets Vidéo / Audio, positionnement de la vue sur le lecteur, plein écran (gabarits, CSS, script de l'accueil)."""
import json
import re
import shutil
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def read(rel):
    return (ROOT / rel).read_text(encoding="utf-8")


class AccueilLecteurMarkupTests(unittest.TestCase):
    def test_deux_onglets_et_un_seul_panneau(self):
        html = read("frontend/templates/home/player.html")
        self.assertIn("role='tablist'", html)
        self.assertEqual(len(re.findall(r"role='tab'", html)), 2)
        for mode in ("video", "audio"):
            self.assertIn(f"id='mp-tab-{mode}'", html)
            self.assertIn(f"id='mp-n-{mode}'", html)
        self.assertEqual(html.count("role='tabpanel'"), 1)                         # un seul lecteur : pas de second <video>
        self.assertEqual(html.count("{{ box }}"), 1)
        self.assertRegex(html, r"id='mp-tab-video'[^>]*aria-selected='true'[^>]*tabindex='0'")
        self.assertRegex(html, r"id='mp-tab-audio'[^>]*aria-selected='false'[^>]*tabindex='-1'")   # navigation au clavier : un seul onglet dans l'ordre de tabulation

    def test_section_du_lecteur_et_lien_d_acces(self):
        body = read("frontend/templates/home/body.html")
        self.assertIn("<section class='section' id='lecteur'>", body)
        self.assertIn("href='#lecteur'", body)

    def test_defilement_cale_sous_la_barre_sans_scroll_snap_global(self):
        css = read("frontend/css/home.css")
        rules = re.sub(r"/\*.*?\*/", "", css, flags=re.S)                          # sans les commentaires
        self.assertRegex(css, r"#lecteur\{scroll-margin-top:calc\(var\(--tb\) \+ 12px\)\}")
        self.assertNotIn("scroll-snap", rules)                                       # la page reste libre de défiler
        self.assertNotIn("scroll-behavior", rules)                                   # le défilement doux est demandé par le script, jamais imposé à la page
        self.assertIn("prefers-reduced-motion", css)
        self.assertIn("prefers-reduced-motion", read("frontend/js/home/01-selection-de-fichiers.js"))

    def test_plein_ecran_sur_le_meme_element_sans_recreer_la_video(self):
        ui = read("frontend/js/watch/03-interface-du-lecteur.js")
        self.assertIn("this.#box.requestFullscreen", ui)                           # le conteneur, pas une nouvelle balise
        self.assertIn("webkitRequestFullscreen", ui)
        self.assertIn("webkitEnterFullscreen", ui)                                 # iPhone
        for forbidden in ("createElement('video')", "cloneNode", "replaceWith(video"):
            self.assertNotIn(forbidden, ui + read("frontend/js/watch/03-plein-ecran.js"))
        scroll = read("frontend/js/watch/03-defilement-plein-ecran.js")
        self.assertNotIn("scrollIntoView", scroll)                                # la sortie ne déclenche aucun défilement vers un élément
        self.assertIn("fullscreenScroll.expect()", ui)
        keeper = read("frontend/js/watch/03-plein-ecran.js")
        for event in ("fullscreenchange", "webkitfullscreenchange", "webkitbeginfullscreen", "webkitendfullscreen", "timeupdate", "loadedmetadata", "play", "pause", "seeked"):
            self.assertIn(event, keeper)


@unittest.skipUnless(shutil.which("node"), "Node.js n'est pas installé")
class AccueilSelecteurJsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        out = subprocess.run(["node", str(Path(__file__).resolve().parent / "js" / "home_picker_harness.js")], capture_output=True, text=True, timeout=60)
        assert out.returncode == 0, out.stderr
        cls.r = json.loads(out.stdout)

    def test_etat_initial_en_mode_video(self):
        r = self.r["initial"]
        self.assertEqual((r["selected"], r["tabIndex"], r["labelledby"]), (["true", "false"], [0, -1], "mp-tab-video"))
        self.assertEqual((r["title"], r["pick"]), ("Glisse une vidéo ici", "Choisir des vidéos"))
        self.assertTrue(r["accept"].startswith("video/*"))

    def test_clic_sur_l_onglet_audio(self):
        r = self.r["audio"]
        self.assertEqual((r["selected"], r["tabIndex"], r["counts"], r["calls"]), (["false", "true"], [-1, 0], [3, 1], ["audio"]))
        self.assertEqual((r["title"], r["pick"], r["labelledby"]), ("Glisse un son ici", "Choisir des sons", "mp-tab-audio"))
        self.assertTrue(r["accept"].startswith("audio/*"))              # le sélecteur de fichiers ne propose que le mode affiché
        self.assertEqual(self.r["memeOnglet"], ["audio"])               # même mode : le lecteur n'est pas sollicité

    def test_clavier_dans_les_onglets(self):
        r = self.r["fleche"]
        self.assertEqual((r["flags"], r["calls"], r["focus"]), ({"prevented": True, "stopped": True}, ["audio", "video"], [1, 0]))
        self.assertEqual(self.r["flecheDroite"], "audio")
        self.assertEqual(self.r["fin"], "video/audio")                  # Début / Fin
        self.assertEqual(self.r["autreTouche"], {"prevented": False, "stopped": False})

    def test_fichiers_de_l_autre_mode_signales_sans_etre_melanges(self):
        self.assertEqual(self.r["message"], {"text": "2 fichiers audio ignorés : passe en mode Audio pour les lire. 1 fichier ignoré : ni vidéo ni audio.", "hidden": False})
        self.assertEqual(self.r["messageUnique"], "1 fichier audio ignoré : passe en mode Audio pour le lire.")
        self.assertTrue(self.r["sansMessage"])
        self.assertEqual(self.r["messageAudio"], "3 fichiers vidéo ignorés : passe en mode Vidéo pour les lire.")

    def test_defilement_seulement_sur_action_et_si_necessaire(self):
        smooth = [{"behavior": "smooth", "block": "start"}]
        self.assertEqual(self.r["tropBas"], smooth)
        self.assertEqual(self.r["sousLaBarre"], smooth)
        self.assertEqual(self.r["bienPlacee"], [])                       # déjà bien placée : aucun mouvement
        self.assertEqual(self.r["animationsReduites"], [{"behavior": "auto", "block": "start"}])   # prefers-reduced-motion
        self.assertEqual(self.r["lien"], {"prevented": True, "scrolls": smooth, "hash": ["#lecteur"]})
        self.assertEqual(self.r["lienDejaCale"], [])
        self.assertEqual(self.r["pasDeDefilementSansAction"], 0)


if __name__ == "__main__":
    unittest.main()
