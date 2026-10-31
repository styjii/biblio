"""playback.py : dernière position de lecture mémorisée pour chaque appareil (adresse IP)."""
import json
import tempfile
import time
import unittest
from pathlib import Path

from app import config
from app.playback import PlaybackStore


class PlaybackStoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.saved = config.PLAYBACK_PATH
        config.PLAYBACK_PATH = Path(self.tmp.name) / "playback.json"
        self.s = PlaybackStore()

    def tearDown(self):
        config.PLAYBACK_PATH = self.saved
        self.tmp.cleanup()

    def pos(self, ip, rel, store=None):
        """Position mémorisée (secondes), None si rien."""
        entry = (store or self.s).get(ip, rel)
        return entry["t"] if entry else None

    def test_chaque_appareil_a_sa_propre_position(self):
        self.assertTrue(self.s.put("192.168.1.10", "films/a.mp4", 125.34, 3600))
        self.assertTrue(self.s.put("192.168.1.11", "films/a.mp4", 40, 3600))
        self.assertEqual(self.s.get("192.168.1.10", "films/a.mp4"), {"t": 125.3, "d": 3600.0})
        self.assertEqual(self.pos("192.168.1.11", "films/a.mp4"), 40.0)
        self.assertIsNone(self.s.get("192.168.1.12", "films/a.mp4"))
        self.assertIsNone(self.s.get("192.168.1.10", "films/b.mp4"))

    def test_valeurs_invalides_refusees(self):
        for t, d in ((-1, 10), ("abc", 10), (float("nan"), 10), (float("inf"), 10), (10 ** 9, 10), (5, -3), (5, "x")):
            self.assertFalse(self.s.put("10.0.0.1", "a.mp3", t, d), (t, d))
        self.assertFalse(self.s.put("10.0.0.1", "", 5, 10))
        self.assertFalse(self.s.put("10.0.0.1", "x" * 2000, 5, 10))
        self.assertIsNone(self.s.get("10.0.0.1", "a.mp3"))

    def test_oubli_d_une_position(self):
        self.s.put("10.0.0.1", "a.mp3", 50, 200)
        self.s.forget("10.0.0.1", "a.mp3")
        self.assertIsNone(self.s.get("10.0.0.1", "a.mp3"))
        self.s.forget("10.0.0.1", "inconnu.mp3")             # sans effet, sans erreur

    def test_les_positions_suivent_un_renommage_et_disparaissent_avec_le_fichier(self):
        for ip in ("10.0.0.1", "10.0.0.2"):
            self.s.put(ip, "cours/un.mp4", 10, 100)
            self.s.put(ip, "cours/sous/deux.mp3", 20, 100)
            self.s.put(ip, "cours-bis/trois.mp3", 30, 100)    # même préfixe de texte, autre dossier
        self.s.move("cours", "archive")
        self.assertEqual(self.pos("10.0.0.1", "archive/un.mp4"), 10)
        self.assertEqual(self.pos("10.0.0.2", "archive/sous/deux.mp3"), 20)
        self.assertIsNone(self.s.get("10.0.0.1", "cours/un.mp4"))
        self.assertEqual(self.pos("10.0.0.1", "cours-bis/trois.mp3"), 30)
        self.s.drop("archive")
        self.assertIsNone(self.s.get("10.0.0.1", "archive/un.mp4"))
        self.assertIsNone(self.s.get("10.0.0.2", "archive/sous/deux.mp3"))
        self.assertEqual(self.pos("10.0.0.2", "cours-bis/trois.mp3"), 30)

    def test_limites_par_appareil(self):
        self.s.MAX_PER_DEVICE = 3
        for i in range(5):
            self.s.put("10.0.0.1", f"f{i}.mp3", 10 + i, 100)
            time.sleep(0.002)
        kept = [i for i in range(5) if self.s.get("10.0.0.1", f"f{i}.mp3")]
        self.assertEqual(kept, [2, 3, 4])                    # les moins récents sont oubliés

    def test_persistance_et_purge(self):
        self.s.put("10.0.0.1", "a.mp3", 50, 200)
        self.s.put("10.0.0.2", "vieux.mp3", 50, 200)
        self.s._data["10.0.0.2"]["vieux.mp3"][2] = time.time() - (PlaybackStore.DAYS + 1) * 86400
        self.s.save()
        self.assertEqual(config.PLAYBACK_PATH.stat().st_mode & 0o777, 0o600)
        again = PlaybackStore()
        again.load()
        self.assertEqual(self.pos("10.0.0.1", "a.mp3", again), 50.0)
        self.assertIsNone(again.get("10.0.0.2", "vieux.mp3"))      # trop ancienne : purgée à l'enregistrement
        config.PLAYBACK_PATH.write_text(json.dumps({"pas-une-ip": {"a": [1, 2, 3]}, "10.0.0.3": {"b": "oups"}}))
        broken = PlaybackStore()
        broken.load()                                              # fichier abîmé : ignoré sans planter
        self.assertIsNone(broken.get("10.0.0.3", "b"))


if __name__ == "__main__":
    unittest.main()
