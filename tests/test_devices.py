"""devices.py : appareils, blocage, historique d'activité et rapport."""
import tempfile
import time
import unittest
from pathlib import Path

from app import config
from app.devices import ActivityHistory, DeviceTracker, Monitor


class MonitorTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.saved = config.BLOCKLIST_PATH, config.HISTORY_PATH
        config.BLOCKLIST_PATH = Path(self.tmp.name) / "blocked.json"
        config.HISTORY_PATH = Path(self.tmp.name) / "history.json"
        self.m = Monitor()

    def tearDown(self):
        config.BLOCKLIST_PATH, config.HISTORY_PATH = self.saved
        self.tmp.cleanup()

    def test_libelle_navigateur(self):
        ua = "Mozilla/5.0 (Linux; Android 14) AppleWebKit/537.36 Chrome/120.0 Mobile Safari/537.36"
        self.assertEqual(DeviceTracker.short_ua(ua), "Chrome · Android")
        self.assertEqual(DeviceTracker.short_ua(""), "")

    def test_appareils_et_lignes(self):
        self.m.track("192.168.1.20", "Firefox/120.0 (X11; Linux x86_64)", True)
        self.m.track("192.168.1.20", "", False, hit=False)
        rows = self.m.devices.rows(me="192.168.1.20")
        self.assertEqual(len(rows), 1)
        r = rows[0]
        self.assertEqual((r["ua"], r["hits"], r["auth"], r["active"], r["me"]), ("Firefox · Linux", 1, True, True, True))
        self.assertTrue(self.m.history.dirty)

    def test_blocage(self):
        ok, err, _ = self.m.blocklist.set("10.0.0.5", True, requester="10.0.0.9")
        self.assertTrue(ok, err)
        self.assertTrue(self.m.blocklist.is_blocked("10.0.0.5"))
        self.assertEqual(len(self.m.blocklist), 1)
        self.assertTrue(config.BLOCKLIST_PATH.is_file())
        self.assertEqual(config.BLOCKLIST_PATH.stat().st_mode & 0o777, 0o600)
        # rechargé au redémarrage
        again = Monitor()
        again.blocklist.load()
        self.assertTrue(again.blocklist.is_blocked("10.0.0.5"))
        self.assertTrue(self.m.devices.rows("")[0]["blocked"])
        # refus : adresse invalide, soi-même, machine hôte
        self.assertFalse(self.m.blocklist.set("pas-une-ip", True, "10.0.0.9")[0])
        self.assertFalse(self.m.blocklist.set("10.0.0.9", True, "10.0.0.9")[0])
        self.assertFalse(self.m.blocklist.set("127.0.0.1", True, "10.0.0.9")[0])
        self.assertTrue(self.m.blocklist.set("10.0.0.5", False, "10.0.0.9")[0])
        self.assertFalse(self.m.blocklist.is_blocked("10.0.0.5"))

    def test_classement_des_requetes(self):
        c = ActivityHistory.classify
        self.assertEqual(c("/watch", {"f": ["a.mp4"]}), ("video", "a.mp4"))
        self.assertEqual(c("/raw", {"f": ["a.zip"], "dl": ["1"]}), ("download", "a.zip"))
        self.assertEqual(c("/zip", {"f": ["Cours"]}), ("download", "Cours"))
        self.assertEqual(c("/mkdir", {"d": ["a"], "to": ["b"]}), ("edit", "a/b"))
        self.assertEqual(c("/s/jeton/page.html", {}), ("web", "page.html"))
        self.assertIsNone(c("/thumb", {"f": ["a.mp4"]}))
        self.assertIsNone(c("/", {"token": ["x"]}))

    def test_historique_fusion_rapport_et_persistance(self):
        h = self.m.history
        e = h.record("10.0.0.5", "video", "film.mp4")
        h.add_bytes(e, 1000)
        e2 = h.record("10.0.0.5", "video", "film.mp4")          # requête rapprochée : fusionnée
        self.assertIs(e, e2)
        self.assertEqual((e[4], e[5]), (1000, 2))
        h.record("10.0.0.5", "pdf", "cours.pdf")
        report = h.report("10.0.0.5", "24h")
        self.assertEqual(report["totals"]["video"]["actions"], 1)
        self.assertEqual(report["totals"]["video"]["bytes"], 1000)
        self.assertEqual({t["file"] for t in report["top"]}, {"film.mp4", "cours.pdf"})
        self.assertEqual(h.report("all", "inconnu")["range"], "24h")
        h.save()
        self.assertFalse(h.dirty)
        again = Monitor()
        again.history.load()
        self.assertEqual(again.history.report("10.0.0.5", "7d")["totals"]["pdf"]["actions"], 1)

    def test_purge_des_anciennes_actions(self):
        h = self.m.history
        old = time.time() - (ActivityHistory.DAYS + 1) * 86400
        h._log["10.0.0.7"] = __import__("collections").deque([[old, old, "pdf", "vieux.pdf", 0, 1]])
        self.m.devices.track("10.0.0.7", "", False)
        self.m.devices._devices["10.0.0.7"]["last"] = old
        h.save()
        self.assertEqual(h.report("all", "30d")["totals"], {})
        self.assertEqual(self.m.devices.rows(""), [])


if __name__ == "__main__":
    unittest.main()
