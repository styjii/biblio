"""Démarrage réel du serveur sur un dossier temporaire : pages principales, verrouillage, droits d'écriture."""
import http.client
import io
import os
import subprocess
import sys
import tempfile
import time
import unittest
import zipfile
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

    def test_page_404_stylee(self):
        status, r, body = self.fetch("GET", "/page-inexistante", cookie=self.cookie)
        self.assertEqual(status, 404)
        self.assertIn("text/html", r.getheader("Content-Type"))
        for marker in ("errcard", "Page introuvable", ">404<", "/page-inexistante", "Retour à l'accueil"):
            self.assertIn(marker, body)

    def test_page_404_fichier_et_echappement(self):
        status, body = self.get("/view?f=absent.txt")
        self.assertEqual(status, 404)
        self.assertIn("Fichier introuvable", body)
        status, _, body = self.fetch("GET", "/%3Cscript%3Ealert(1)%3C/script%3E", cookie=self.cookie)
        self.assertEqual(status, 404)
        self.assertNotIn("<script>alert(1)", body)
        self.assertIn("&lt;script&gt;", body)

    def test_erreurs_brutes_pour_ressources_et_post(self):
        status, r, body = self.fetch("GET", "/thumb?f=absent.mp4", cookie=self.cookie)
        self.assertEqual(status, 404)
        self.assertNotIn("errcard", body)
        status, r, body = self.fetch("POST", "/inconnu", b"", XHR, self.cookie)
        self.assertEqual(status, 404)
        self.assertNotIn("errcard", body)

    # ----- dossiers : création, ZIP, renommage, suppression
    def unlocked_cookie(self):
        status, r, _ = self.fetch("POST", "/unlock", PASSWORD.encode(), XHR, self.cookie)
        self.assertEqual(status, 200)
        return self.cookie + "; " + r.getheader("Set-Cookie").split(";")[0]

    def raw(self, method, path, cookie=None, body=None, headers=None):
        conn = http.client.HTTPConnection("127.0.0.1", PORT, timeout=10)
        conn.request(method, path, body=body, headers={**(headers or {}), "Cookie": cookie or self.cookie})
        r = conn.getresponse()
        return r.status, r, r.read()

    def test_bouton_et_menu_des_dossiers(self):
        status, body = self.get("/")
        self.assertIn("id='newdir'", body)
        self.assertIn("Créer un dossier", body)

    def test_creation_de_dossier_verrouillee(self):
        status, _, body = self.fetch("POST", "/mkdir?d=&to=interdit", b"", XHR, self.cookie)
        self.assertEqual(status, 403)
        self.assertIn('"locked": true', body)
        self.assertFalse((Path(self.tmp.name) / "lib" / "interdit").exists())

    def test_cycle_complet_d_un_dossier(self):
        lib, ck = Path(self.tmp.name) / "lib", self.unlocked_cookie()
        status, _, body = self.fetch("POST", "/mkdir?d=&to=Cours%20%C3%A9t%C3%A9", b"", XHR, ck)
        self.assertEqual(status, 200)
        self.assertTrue((lib / "Cours été").is_dir())
        self.assertEqual(self.fetch("POST", "/mkdir?d=&to=Cours%20%C3%A9t%C3%A9", b"", XHR, ck)[0], 409)
        for bad in ("a%2Fb", "..", "", "%20"):
            with self.subTest(bad=bad):
                self.assertEqual(self.fetch("POST", f"/mkdir?d=&to={bad}", b"", XHR, ck)[0], 400)
        self.assertEqual(self.fetch("POST", "/mkdir?d=..&to=evasion", b"", XHR, ck)[0], 403)
        # le dossier apparaît dans la liste, avec son menu
        status, page = self.get("/")
        self.assertIn("data-kind='folder'", page)
        # sous-dossier + fichiers, puis archive ZIP (téléchargement : aucun déverrouillage nécessaire)
        self.assertEqual(self.fetch("POST", "/mkdir?d=Cours%20%C3%A9t%C3%A9&to=vide", b"", XHR, ck)[0], 200)
        (lib / "Cours été" / "a.txt").write_text("alpha", encoding="utf-8")
        (lib / "Cours été" / "photo.png").write_bytes(b"\x89PNG" + bytes(50))
        status, r, data = self.raw("GET", "/zip?f=Cours%20%C3%A9t%C3%A9")
        self.assertEqual(status, 200)
        self.assertEqual(r.getheader("Content-Type"), "application/zip")
        self.assertIn("attachment", r.getheader("Content-Disposition"))
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            self.assertIsNone(zf.testzip())
            names = set(zf.namelist())
            self.assertEqual(zf.read("Cours été/a.txt"), b"alpha")
        self.assertTrue({"Cours été/a.txt", "Cours été/photo.png", "Cours été/vide/"} <= names)
        # renommage
        self.assertEqual(self.fetch("POST", "/rename?f=Cours%20%C3%A9t%C3%A9&to=Archive", b"", XHR, ck)[0], 200)
        self.assertTrue((lib / "Archive" / "a.txt").is_file())
        self.assertFalse((lib / "Cours été").exists())
        # un dossier verrouillé ne se renomme ni ne se supprime
        for path in ("/rename?f=Archive&to=x", "/delete?f=Archive"):
            self.assertEqual(self.fetch("POST", path, b"", XHR, self.cookie)[0], 403)
        self.assertTrue((lib / "Archive").is_dir())
        # suppression récursive, mais jamais la racine
        self.assertEqual(self.fetch("POST", "/delete?f=", b"", XHR, ck)[0], 403)
        self.assertEqual(self.fetch("POST", "/delete?f=Archive", b"", XHR, ck)[0], 200)
        self.assertFalse((lib / "Archive").exists())
        self.assertTrue((lib / "notes.txt").is_file())

    def test_zip_sans_cookie_et_dossier_absent(self):
        self.assertEqual(self.fetch("GET", "/zip?f=lib")[0], 401)
        self.assertEqual(self.get("/zip?f=absent")[0], 404)
        self.assertEqual(self.get("/zip?f=notes.txt")[0], 404)


if __name__ == "__main__":
    unittest.main()
