"""Lecteur vidéo (frontend/js/watch) : reprise après une coupure du réseau, exécutée avec Node, une fausse page et une horloge simulée."""
import json
import shutil
import subprocess
import unittest
from pathlib import Path

HARNESS = Path(__file__).resolve().parent / "js" / "watch_guard_harness.js"


@unittest.skipUnless(shutil.which("node"), "Node.js n'est pas installé")
class WatchGuardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        out = subprocess.run(["node", str(HARNESS)], capture_output=True, text=True, timeout=60)
        assert out.returncode == 0, out.stderr
        cls.r = json.loads(out.stdout)

    def test_coupure_longue_puis_retour_du_reseau(self):
        r = self.r["coupure_longue"]
        self.assertTrue(r["before"]["error"])                       # pendant la coupure, le lecteur est bien en erreur
        self.assertTrue(r["playing"])                               # puis il repart seul...
        self.assertEqual(r["time"], 120)                            # ...là où il en était

    def test_reprise_meme_sans_evenement_online(self):
        r = self.r["sans_evenement"]
        self.assertEqual((r["paused"], r["error"], r["time"]), (False, False, 120))

    def test_connexion_morte_reprend_sans_attendre_le_delai(self):
        r = self.r["connexion_morte"]
        self.assertEqual((r["ready"], r["paused"], r["time"]), (True, False, 120))

    def test_pause_de_l_utilisateur_respectee(self):
        r = self.r["pause_respectee"]
        self.assertEqual((r["paused"], r["error"], r["time"]), (True, False, 120))

    def test_retour_sur_la_page_relance_le_lecteur(self):
        r = self.r["retour_sur_la_page"]
        self.assertEqual((r["paused"], r["error"], r["time"]), (False, False, 120))

    def test_video_suivante_attend_le_reseau(self):
        r = self.r["suivante_hors_connexion"]
        self.assertEqual(r["during"], "/watch?f=a.mp4")
        self.assertEqual(r["after"], "/watch?f=b.mp4")
        self.assertEqual(self.r["suivante_en_ligne"]["href"], "/watch?f=b.mp4")

    def test_fichier_abime_n_est_pas_recharge_indefiniment(self):
        self.assertLessEqual(self.r["fichier_abime"]["loads"], 4)


if __name__ == "__main__":
    unittest.main()
