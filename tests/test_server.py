"""Démarrage réel du serveur sur un dossier temporaire : pages principales, verrouillage, droits d'écriture."""
import http.client
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PORT = 18765
TOKEN = "test-token"
PASSWORD = "test-password"
XHR = {"X-Requested-With": "biblio"}


class ServerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        tmp = Path(cls.tmp.name)
        (tmp / "lib").mkdir()
        (tmp / "lib" / "notes.txt").write_text("bonjour\n", encoding="utf-8")
        (tmp / "lib" / "lisez.md").write_text("# Titre\n", encoding="utf-8")
        (tmp / "lib" / "page.html").write_text("<h1>x</h1>", encoding="utf-8")
        env = tmp / "test.env"
        env.write_text(f"BIBLIO_TOKEN={TOKEN}\nBIBLIO_PASSWORD={PASSWORD}\n", encoding="utf-8")
        env.chmod(0o600)
        cls.proc = subprocess.Popen(
            [sys.executable, "server.py", str(tmp / "lib"), "-p", str(PORT), "-e", str(env)], cwd=ROOT,
            env=dict(os.environ, XDG_CACHE_HOME=str(tmp / "cache"), XDG_CONFIG_HOME=str(tmp / "cfg"), HOME=str(tmp)),
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        for _ in range(60):
            try:
                conn = http.client.HTTPConnection("127.0.0.1", PORT, timeout=1)
                conn.request("GET", "/")
                conn.getresponse().read()
                conn.close()
                break
            except OSError:
                time.sleep(0.25)
        else:
            raise RuntimeError("le serveur ne démarre pas")
        cls.cookie = cls.fetch("GET", f"/?token={TOKEN}")[1].getheader("Set-Cookie").split(";")[0]

    @classmethod
    def tearDownClass(cls):
        cls.proc.terminate()
        cls.proc.wait(timeout=5)
        cls.tmp.cleanup()

    @classmethod
    def fetch(cls, method, path, body=None, headers=None, cookie=None):
        conn = http.client.HTTPConnection("127.0.0.1", PORT, timeout=10)
        h = dict(headers or {})
        if cookie:
            h["Cookie"] = cookie
        conn.request(method, path, body=body, headers=h)
        r = conn.getresponse()
        return r.status, r, r.read().decode("utf-8", "replace")

    def get(self, path):
        status, _, body = self.fetch("GET", path, cookie=self.cookie)
        return status, body

    def test_sans_cookie_acces_refuse(self):
        status, _, body = self.fetch("GET", "/")
        self.assertEqual(status, 401)
        self.assertNotIn("notes.txt", body)

    def test_pages_principales(self):
        for path, marker in [("/", "notes.txt"), ("/view?f=notes.txt", "edbar"), ("/preview?f=lisez.md", "md-art"),
                             ("/preview?f=page.html", "id='pv'"), ("/dashboard", "msgcard")]:
            with self.subTest(path=path):
                status, body = self.get(path)
                self.assertIn(status, (200, 403))
                self.assertIn(marker, body)

    def test_edition_verrouillee_sans_invite_de_mot_de_passe(self):
        status, body = self.get("/view?f=notes.txt")
        self.assertIn("Éditer · verrouillé", body)
        self.assertNotIn("href='/edit?", body)
        self.assertNotIn("type='password'", body)
        status, body = self.get("/edit?f=notes.txt")
        self.assertEqual(status, 403)

    def test_ecritures_refusees_tant_que_verrouille(self):
        for path in ("/save?f=notes.txt&mt=1&enc=utf-8", "/rename?f=notes.txt&to=x.txt", "/delete?f=notes.txt"):
            with self.subTest(path=path):
                status, _, body = self.fetch("POST", path, b"x", XHR, self.cookie)
                self.assertEqual(status, 403)
                self.assertIn('"locked": true', body)


if __name__ == "__main__":
    unittest.main()
