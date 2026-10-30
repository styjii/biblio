"""Moteur d'envoi (frontend/js/transfers/engine.js) : exécuté avec Node et un faux XMLHttpRequest / fetch."""
import json
import shutil
import subprocess
import unittest
from pathlib import Path

HARNESS = Path(__file__).resolve().parent / "js" / "engine_harness.js"


@unittest.skipUnless(shutil.which("node"), "Node.js n'est pas installé")
class TransferEngineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        out = subprocess.run(["node", str(HARNESS)], capture_output=True, text=True, timeout=60)
        assert out.returncode == 0, out.stderr
        cls.r = json.loads(out.stdout)

    def test_envoi_simple_avec_un_seul_jeton(self):
        r = self.r["simple"]
        self.assertEqual((r["ok"], r["failed"], r["finished"], r["tickets"]), (3, 0, True, 1))
        self.assertEqual(r["urls"][0], "/upload?d=dossier%2Fsous&n=f0.bin&o=1")
        self.assertEqual(r["okDests"], ["dossier/sous"])

    def test_fichier_deja_present_est_ignore(self):
        r = self.r["deja"]
        self.assertEqual((r["ok"], r["skipped"]), (2, 1))
        self.assertEqual(r["msg"], "existe déjà")

    def test_jeton_expire_est_renouvele(self):
        r = self.r["jeton"]
        self.assertEqual((r["ok"], r["failed"], r["tickets"], r["uploads"]), (1, 0, 2, 2))
        self.assertEqual(r["tokens"], ["t1", "t2"])

    def test_acces_verrouille_arrete_la_serie(self):
        r = self.r["verrou"]
        self.assertEqual((r["ok"], r["failed"], r["skipped"], r["uploads"], r["running"]), (1, 1, 2, 2, False))
        self.assertIn("verrouillé", r["note"])

    def test_fichier_trop_volumineux_n_est_pas_envoye(self):
        r = self.r["taille"]
        self.assertEqual((r["ok"], r["failed"], r["uploads"]), (1, 1, 1))
        self.assertIn("trop volumineux", r["msg"])

    def test_coupure_reseau_arrete_la_serie(self):
        r = self.r["reseau"]
        self.assertEqual((r["ok"], r["failed"], r["skipped"], r["note"]), (1, 1, 2, "connexion perdue"))

    def test_arret_demande_pendant_un_envoi(self):
        r = self.r["arret"]
        self.assertEqual((r["running"], r["note"], r["failed"], r["skipped"]), (False, "arrêté", 1, 2))
        self.assertEqual(r["msgs"], ["arrêté", "annulé", "annulé"])

    def test_ajout_pendant_l_envoi_puis_nouvelle_serie(self):
        r = self.r["series"]
        self.assertEqual(r["first"], {"count": 4, "ok": 4, "dests": ["a", "b"], "run": 1})
        self.assertEqual(r["second"], {"count": 1, "ok": 1, "dests": ["c"], "run": 2})
        self.assertEqual(self.r["clear"]["count"], 0)

    def test_la_vue_d_une_longue_file_reste_bornee(self):
        r = self.r["longue"]
        self.assertEqual((r["count"], r["firstRowRunning"]), (1000, "run"))
        self.assertLessEqual(r["rows"], 200)                    # jamais plus de 200 lignes envoyées aux pages
        self.assertEqual(r["more"], 1000 - r["rows"])           # le reste est résumé par « … et N autres fichiers »


if __name__ == "__main__":
    unittest.main()
