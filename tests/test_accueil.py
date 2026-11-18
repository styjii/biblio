"""Page d'accueil, dossiers d'entrée multiples (.env), fichiers fréquents et stockage du tableau de bord sans double comptage."""
import http.client
import json
import os
import re
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

from app import config
from app.devices import ActivityHistory
from app.sysinfo import SystemInfo, folder_sizes

ROOT = Path(__file__).resolve().parent.parent
PORT = 18766
TOKEN = "test-token"
PASSWORD = "test-password"
XHR = {"X-Requested-With": "biblio"}


class DisksParsingTests(unittest.TestCase):
    def test_nombre_variable_de_chemins_chacun_avec_un_nom(self):
        self.assertEqual(config.parse_disks("/a=Disque A"), [("/a", "Disque A")])
        self.assertEqual(config.parse_disks(" /a=Interne ; /b=Externe ;/c=Cle USB;"),
                         [("/a", "Interne"), ("/b", "Externe"), ("/c", "Cle USB")])
        self.assertEqual(config.parse_disks(""), [])

    def test_un_chemin_sans_nom_est_refuse(self):
        for text in ("/a", "/a=", "=Nom", "/a=Disque A;/b"):
            with self.subTest(text=text), self.assertRaises(config.ConfigError):
                config.parse_disks(text)


class LibraryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.t = Path(self.tmp.name)
        for name in ("a", "b", "c"):
            (self.t / name).mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    def test_au_moins_un_dossier(self):
        with self.assertRaises(config.ConfigError):
            config.Library().build(None, [])
        lib = config.Library()
        lib.build(self.t / "a", [])                      # le dossier courant suffit
        self.assertEqual([m.name for m in lib.mounts], ["Dossier courant"])
        lib = config.Library()
        lib.build(None, [(str(self.t / "a"), "A")])      # un chemin du .env suffit
        self.assertEqual(lib.default.name, "A")
        self.assertIsNone(lib.launch)

    def test_dossier_courant_et_disques(self):
        lib = config.Library()
        lib.build(self.t / "c", [(str(self.t / "a"), "A"), (str(self.t / "b"), "B")])
        self.assertEqual([m.name for m in lib.mounts], ["Dossier courant", "A", "B"])
        self.assertIs(lib.default, lib.launch)
        self.assertFalse(lib.launch.configured)

    def test_dossier_courant_deja_dans_le_env_n_est_pas_ajoute_deux_fois(self):
        lib = config.Library()
        lib.build(self.t / "a", [(str(self.t / "a"), "A"), (str(self.t / "b"), "B")])
        self.assertEqual([m.name for m in lib.mounts], ["A", "B"])
        self.assertTrue(lib.get(lib.launch.id).configured)
        self.assertEqual(lib.launch.name, "A")

    def test_doublons_refuses(self):
        lib = config.Library()
        with self.assertRaises(config.ConfigError):      # même dossier sous deux noms
            lib.build(None, [(str(self.t / "a"), "A"), (str(self.t / "a" / "."), "A2")])
        with self.assertRaises(config.ConfigError):      # même nom pour deux dossiers
            lib.build(None, [(str(self.t / "a"), "Disque"), (str(self.t / "b"), "disque")])

    def test_selection_par_fil_d_execution_et_inconnu(self):
        lib = config.Library()
        lib.build(None, [(str(self.t / "a"), "A"), (str(self.t / "b"), "B")])
        lib.select(lib.mounts[1].id)
        self.assertEqual(lib.root, (self.t / "b").resolve())
        lib.select("inconnu")
        self.assertIs(lib.current, lib.default)

    def test_chemins_resolus_dans_le_dossier_choisi(self):
        (self.t / "b" / "x.txt").write_text("x", encoding="utf-8")
        lib = config.Library()
        lib.build(None, [(str(self.t / "a"), "A"), (str(self.t / "b"), "B")])
        saved = config.library
        config.library = lib
        try:
            self.assertEqual(config.paths.resolve("x.txt"), (self.t / "a" / "x.txt").resolve())   # racine par défaut : A
            self.assertEqual(config.paths.resolve("x.txt", lib.mounts[1]), (self.t / "b" / "x.txt").resolve())
            self.assertIsNone(config.paths.resolve("../b/x.txt", lib.mounts[0]))   # pas d'évasion vers un autre disque
        finally:
            config.library = saved


class StorageTests(unittest.TestCase):
    """Un volume n'est compté qu'une fois ; le dossier courant est une part de son disque, pas un volume en plus."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.t = Path(self.tmp.name)
        (self.t / "a" / "sous" / "profond").mkdir(parents=True)
        (self.t / "b").mkdir()
        (self.t / "a" / "sous" / "f1.bin").write_bytes(b"x" * 1000)
        (self.t / "a" / "sous" / "profond" / "f2.bin").write_bytes(b"x" * 500)
        (self.t / "a" / "hors.bin").write_bytes(b"x" * 9000)
        self.saved = config.library
        folder_sizes._cache.clear()

    def tearDown(self):
        config.library = self.saved
        self.tmp.cleanup()

    def storage(self, launch, disks):
        config.library = config.Library()
        config.library.build(launch, disks)
        return SystemInfo.storage()

    def test_chaque_chemin_a_son_espace_libre(self):
        s = self.storage(None, [(str(self.t / "a"), "Interne"), (str(self.t / "b"), "Externe")])
        self.assertEqual([d["label"] for d in s["disks"]], ["Interne", "Externe"])
        for d in s["disks"]:
            self.assertIn("free_h", d)

    def test_deux_chemins_du_meme_volume_comptes_une_fois(self):
        s = self.storage(None, [(str(self.t / "a"), "Interne"), (str(self.t / "b"), "Externe")])
        first, second = s["disks"]
        self.assertNotIn("same_volume_as", first)
        self.assertEqual(second["same_volume_as"], "Interne")
        self.assertEqual(s["volumes"], 1)
        self.assertEqual(s["free_total"], first["free"])          # et non 2 x first["free"]

    def test_dossier_courant_dans_un_chemin_du_env_aucune_ligne_en_plus(self):
        s = self.storage(self.t / "a" / "sous", [(str(self.t / "a"), "Interne")])
        self.assertEqual(len(s["disks"]), 1)
        disk = s["disks"][0]
        self.assertFalse(disk["current"])
        deadline = time.time() + 5
        while disk["folder"]["computing"] and time.time() < deadline:
            time.sleep(0.05)
            disk = SystemInfo.storage()["disks"][0]
        self.assertEqual(disk["folder"]["bytes"], 1500)           # seulement le contenu du dossier courant
        self.assertEqual(disk["folder"]["files"], 2)
        self.assertEqual(s["free_total"], disk["free"])

    def test_dossier_courant_egal_a_un_chemin_du_env(self):
        s = self.storage(self.t / "a", [(str(self.t / "a"), "Interne")])
        self.assertEqual(len(s["disks"]), 1)
        self.assertTrue(s["disks"][0]["current"])
        self.assertNotIn("folder", s["disks"][0])                 # inutile de reparcourir tout le disque

    def test_dossier_courant_seul(self):
        s = self.storage(self.t / "a", [])
        self.assertEqual([d["label"] for d in s["disks"]], ["Dossier courant"])
        self.assertTrue(s["disks"][0]["current"])


class FrequentFilesTests(unittest.TestCase):
    def test_classement_par_nombre_de_consultations_et_par_appareil(self):
        from app.devices import monitor
        history = ActivityHistory(monitor.lock, monitor.devices)
        gap = ActivityHistory.DEFAULT_GAP + 1
        for cat, file, root in ([("video", "a.mp4", "r1")] * 3 + [("pdf", "b.pdf", "r1")] * 2
                                              + [("text", "c.txt", "r2")] + [("browse", "dossier", "r1")] * 4):
            history.record("10.0.0.1", cat, file, root)
            for e in history._log["10.0.0.1"]:      # espace les actions pour qu'elles ne fusionnent pas
                e[1] -= gap * 10
        history.record("10.0.0.2", "audio", "autre.mp3", "r1")
        top = history.frequent("10.0.0.1", limit=5)
        self.assertEqual([(t["file"], t["n"]) for t in top][:2], [("a.mp4", 3), ("b.pdf", 2)])
        self.assertNotIn("dossier", [t["file"] for t in top])     # les dossiers ne sont pas des fichiers
        self.assertNotIn("autre.mp3", [t["file"] for t in top])   # l'historique d'un autre appareil reste privé
        self.assertEqual(history.frequent("10.0.0.1", limit=1), top[:1])

    def test_anciennes_actions_rattachees_au_dossier_par_defaut(self):
        from app.devices import monitor
        history = ActivityHistory(monitor.lock, monitor.devices)
        history.record("10.0.0.3", "video", "v.mp4")              # enregistrée sans dossier d'entrée
        self.assertEqual(history.frequent("10.0.0.3", legacy_root="abc")[0]["root"], "abc")


class HomeServerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        t = Path(cls.tmp.name)
        for name, files in (("interne", ["memo-interne.txt", "clip.mp4"]), ("externe", ["rapport.txt"])):
            (t / name / "dossier").mkdir(parents=True)
            for f in files:
                (t / name / f).write_text("contenu\n", encoding="utf-8")
        (t / "dossier-courant").mkdir()
        (t / "dossier-courant" / "local.txt").write_text("local\n", encoding="utf-8")
        cls.t = t
        cls.interne, cls.externe = t / "interne", t / "externe"
        env = t / "test.env"
        env.write_text(f"BIBLIO_TOKEN={TOKEN}\nBIBLIO_PASSWORD={PASSWORD}\n"
                       f"BIBLIO_DISKS={cls.interne}=Disque interne;{cls.externe}=Disque externe;{t / 'absent'}=Cle USB\n",
                       encoding="utf-8")
        env.chmod(0o600)
        cls.env = env
        cls.proc = cls.start(None)

    @classmethod
    def start(cls, folder):
        args = [sys.executable, "server.py"] + ([str(folder)] if folder else []) + ["-p", str(PORT), "-e", str(cls.env)]
        proc = subprocess.Popen(args, cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
                                env=dict(os.environ, XDG_CACHE_HOME=str(cls.t / "cache"), XDG_CONFIG_HOME=str(cls.t / "cfg"), HOME=str(cls.t)))
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
        cls.cookie = cls.fetch("GET", f"/?token={TOKEN}")[1].getheader("Set-Cookie", "").split(";")[0]
        return proc

    @classmethod
    def stop(cls):
        cls.proc.terminate()
        cls.proc.wait(timeout=5)

    @classmethod
    def tearDownClass(cls):
        cls.stop()
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

    def get(self, path, extra=""):
        status, r, body = self.fetch("GET", path, cookie=f"{self.cookie}{extra}")
        return status, r, body

    def root_id(self, name):
        _, _, home = self.get("/")
        m = re.search(r"href='/open\?root=(\w+)' title='[^']*'>(?:(?!</a>).)*?<span class='name'>" + re.escape(name), home)
        self.assertIsNotNone(m, name)
        return m.group(1)

    # --- page d'accueil ---
    def test_accueil_liste_tous_les_dossiers_avec_leur_nom(self):
        status, _, home = self.get("/")
        self.assertEqual(status, 200)
        for name in ("Disque interne", "Disque externe", "Cle USB"):
            self.assertIn(name, home)
        self.assertIn("Introuvable", home)                        # le chemin absent est signalé et n'est pas cliquable
        self.assertEqual(home.count("href='/open?root="), 2)

    def test_accueil_a_les_trois_blocs(self):
        _, _, home = self.get("/")
        for marker in ("Dossier d'entrée", "Fichiers fréquents", "id='mp-zone'", "id='mp-input'", "id='mp-drop'"):
            self.assertIn(marker, home)
        self.assertIn("window.BiblioLocal", home)           # le lecteur local est le script de la page de lecture

    def test_sans_cookie_acces_refuse(self):
        self.assertEqual(self.fetch("GET", "/")[0], 401)
        self.assertEqual(self.fetch("GET", "/browse")[0], 401)

    def test_ancienne_adresse_des_dossiers_redirigee(self):
        status, r, _ = self.get("/?folder=dossier")
        self.assertEqual(status, 302)
        self.assertEqual(r.getheader("Location"), "/browse?folder=dossier")

    # --- lecteur : le même que celui de la page de lecture vidéo ---
    @staticmethod
    def player_markup(html):
        """Zone du lecteur (image, commandes, menu, verrouillage), sans ce qui varie d'une vidéo à l'autre."""
        zone = html.split("<div class='player' id='vbox'")[1].split("<section class='info'>")[0]
        zone = re.sub(r" src='[^']*'", "", zone)
        zone = re.sub(r"<track [^>]*>", "", zone)
        return re.sub(r"<div class='vp-top'>[^<]*</div>", "<div class='vp-top'></div>", zone)

    def test_lecteur_de_l_accueil_identique_a_celui_de_la_page_de_lecture(self):
        _, _, home = self.get("/")
        _, _, watch = self.get("/watch?f=clip.mp4", f"; fl_root={self.root_id('Disque interne')}")
        self.assertEqual(self.player_markup(home), self.player_markup(watch))      # mêmes commandes, mêmes icônes, même structure
        for command in ("data-act='prev'", "data-act='back'", "data-act='play'", "data-act='fwd'", "data-act='next'", "data-act='mute'",
                        "data-act='settings'", "data-act='theater'", "data-act='pip'", "data-act='fs'", "id='vp-seek'", "id='vp-lock'", "id='vp-menu'"):
            self.assertIn(command, home)
        # mêmes raccourcis documentés, même script (un seul exemplaire de chaque classe du lecteur)
        self.assertIn("<kbd>K</kbd> lecture/pause", home)
        for cls in ("class PlayerUI", "class VideoPlayer", "class PlaybackGuard", "class PlayOrder", "class LocalFiles"):
            self.assertEqual(home.count(cls), 1, cls)
        self.assertEqual(watch.count("class PlayerUI"), 1)
        self.assertNotIn("class LocalPlayer", home)                  # l'ancien lecteur de l'accueil n'existe plus
        self.assertIn('"local":true', home.replace(" ", ""))        # mode « fichiers de l'appareil » : aucune route du serveur n'est utilisée

    # --- choix du dossier d'entrée ---
    def test_choisir_un_disque_puis_parcourir_ses_fichiers(self):
        ext = self.root_id("Disque externe")
        status, r, _ = self.get(f"/open?root={ext}")
        self.assertEqual((status, r.getheader("Location")), (302, "/browse"))
        cookie = r.getheader("Set-Cookie").split(";")[0]
        self.assertEqual(cookie, f"fl_root={ext}")
        _, _, page = self.get("/browse", f"; {cookie}")
        self.assertIn("rapport.txt", page)
        self.assertNotIn("memo-interne.txt", page)
        self.assertIn("Disque externe", page)                     # fil d'Ariane au nom du disque
        _, _, other = self.get("/browse", f"; fl_root={self.root_id('Disque interne')}")
        self.assertIn("memo-interne.txt", other)
        self.assertNotIn("rapport.txt", other)

    def test_fichiers_servis_depuis_le_dossier_actif_seulement(self):
        ext = self.root_id("Disque externe")
        self.assertEqual(self.get("/raw?f=rapport.txt", f"; fl_root={ext}")[0], 200)
        self.assertEqual(self.get("/raw?f=memo-interne.txt", f"; fl_root={ext}")[0], 404)
        self.assertEqual(self.get("/raw?f=../interne/memo-interne.txt", f"; fl_root={ext}")[0], 404)

    def test_dossier_inconnu_ou_indisponible(self):
        self.assertEqual(self.get("/open?root=zzzz")[0], 404)
        self.assertEqual(self.get("/open")[0], 404)
        absent = config.Library.mount_id((self.t / "absent").resolve())
        self.assertEqual(self.get(f"/open?root={absent}")[0], 404)       # chemin du .env non monté

    def test_redirection_apres_ouverture_reste_locale(self):
        ext = self.root_id("Disque externe")
        for target, expected in (("/watch?f=a%20b.mp4", "/watch?f=a%20b.mp4"), ("//evil.example/x", "/browse"),
                                 ("http://evil.example/", "/browse"), ("/\\evil", "/browse"), ("", "/browse")):
            with self.subTest(target=target):
                status, r, _ = self.get(f"/open?root={ext}&to=" + target.replace("\\", "%5C"))
                self.assertEqual((status, r.getheader("Location")), (302, expected))

    def test_cookie_invalide_retombe_sur_le_dossier_par_defaut(self):
        status, _, page = self.get("/browse", "; fl_root=nimporte-quoi")
        self.assertEqual(status, 200)
        self.assertIn("memo-interne.txt", page)                          # premier chemin du .env

    # --- fichiers fréquents ---
    def test_fichiers_frequents_ouvrent_le_bon_dossier_d_entree(self):
        ext = self.root_id("Disque externe")
        for _ in range(2):
            self.get("/view?f=rapport.txt", f"; fl_root={ext}")
            time.sleep(0.01)
        _, _, home = self.get("/")
        block = home.split("Fichiers fréquents")[1].split("Lecteur multimédia")[0]
        self.assertIn("rapport.txt", block)
        self.assertIn(f"/open?root={ext}&amp;to=%2Fview%3Ff%3Drapport.txt", block)
        self.assertIn("Disque externe", block)
        self.assertLessEqual(block.count("class='item'"), 5)

    # --- tableau de bord ---
    def unlocked(self):
        _, r, _ = self.fetch("POST", "/unlock", PASSWORD.encode(), XHR, self.cookie)
        return self.cookie + "; " + r.getheader("Set-Cookie").split(";")[0]

    def test_tableau_de_bord_stockage_par_chemin(self):
        _, _, body = self.fetch("GET", "/dashboard/data", cookie=self.unlocked())
        storage = json.loads(body)["storage"]
        labels = [d["label"] for d in storage["disks"]]
        self.assertEqual(labels, ["Disque interne", "Disque externe", "Cle USB"])
        self.assertIn("error", storage["disks"][2])               # chemin absent : erreur, sans casser les autres
        self.assertEqual(storage["disks"][1].get("same_volume_as"), "Disque interne")
        self.assertEqual(storage["volumes"], 1)


class StartupTests(unittest.TestCase):
    def run_server(self, env_text, *args):
        with tempfile.TemporaryDirectory() as tmp:
            env = Path(tmp) / "t.env"
            env.write_text(env_text, encoding="utf-8")
            env.chmod(0o600)
            return subprocess.run([sys.executable, "server.py", *args, "-p", "18767", "-e", str(env)], cwd=ROOT,
                                  capture_output=True, text=True, timeout=20,
                                  env=dict(os.environ, XDG_CACHE_HOME=tmp, XDG_CONFIG_HOME=tmp, HOME=tmp))

    def test_aucun_dossier_configure_refuse_de_demarrer(self):
        r = self.run_server("BIBLIO_TOKEN=x\n")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("BIBLIO_DISKS", r.stderr)

    def test_chemin_sans_nom_refuse_de_demarrer(self):
        r = self.run_server("BIBLIO_TOKEN=x\nBIBLIO_DISKS=/tmp\n")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("chemin=Nom", r.stderr)


if __name__ == "__main__":
    unittest.main()
