"""Visionneuse d'images (/image), miniatures d'images et modes d'affichage de la liste."""
import http.client
import json
import os
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import time
import unittest
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PORT = 18768
TOKEN = "test-token"


def png(width=4, height=2):
    """Petite image PNG valide (sans dépendance)."""
    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)
    rows = b"".join(b"\x00" + b"\xff\x80\x00" * width for _ in range(height))
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(rows)) + chunk(b"IEND", b""))


@unittest.skipUnless(shutil.which("node"), "Node.js n'est pas installé")
class VisionneuseJsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        out = subprocess.run(["node", str(Path(__file__).resolve().parent / "js" / "gallery_harness.js")], capture_output=True, text=True, timeout=60)
        assert out.returncode == 0, out.stderr
        cls.r = json.loads(out.stdout)

    def test_ordre_de_la_liste_tri_memorise_et_fichiers_caches(self):
        # tri « taille décroissante » de la liste : b (300), d (200), a (100) ; « .c.png » (900) est caché
        r = self.r["ordre"]["state"]
        self.assertEqual((r["name"], r["count"]), ("a.png", "3 / 3"))
        self.assertTrue(r["nextOff"])
        self.assertFalse(r["prevOff"])
        self.assertIn("/raw?f=d.gif", self.r["ordre"]["preload"])         # l'image voisine est préchargée

    def test_zoom_au_clavier_et_aux_boutons(self):
        self.assertEqual(self.r["ajuste"]["zoom"], "50 %")                # 2000 px dans 1000 : ajusté
        self.assertEqual(self.r["zoomPlus"]["zoom"], "63 %")              # touche +
        self.assertEqual(self.r["zoomMoins"]["zoom"], "40 %")             # touche − (deux fois)
        self.assertEqual(self.r["reel"]["zoom"], "100 %")                 # touche 1 : taille réelle
        self.assertEqual(self.r["reajuste"]["zoom"], "50 %")              # touche 0 : ajusté
        self.assertTrue(self.r["ajuste"]["transform"].startswith("translate(0px, 50px)"))   # centrée

    def test_precedente_et_suivante(self):
        self.assertEqual(self.r["suivante"]["count"], "3 / 3")            # déjà la dernière : rien ne bouge
        self.assertEqual(self.r["suivante"]["replaced"], ["/image?f=a.png"])
        self.assertEqual((self.r["precedente"]["name"], self.r["precedente"]["count"]), ("d.gif", "2 / 3"))
        self.assertEqual(self.r["fin"]["count"], "3 / 3")
        self.assertEqual(self.r["debut"]["count"], "1 / 3")
        self.assertTrue(self.r["debut"]["prevOff"])

    def test_retour_a_la_liste_et_raccourcis_ignores(self):
        self.assertEqual(self.r["retourL"], "/browse?folder=x")           # touche L
        self.assertEqual(self.r["retourEchap"], "/browse?folder=x")       # Échap
        self.assertEqual(self.r["echapPleinEcran"], "/image")             # Échap quitte d'abord le plein écran
        self.assertFalse(self.r["modificateur"])                          # Ctrl+flèche : raccourci du navigateur
        self.assertFalse(self.r["champ"])                                 # saisie dans un champ : touches libres

    def test_molette_bascule_et_double_clic(self):
        self.assertEqual(self.r["molette"]["zoom"], "63 %")
        self.assertEqual(self.r["basculeAjuste"]["zoom"], "50 %")
        self.assertEqual(self.r["basculeReel"]["zoom"], "100 %")
        self.assertEqual(self.r["doubleClic"]["zoom"], "50 %")

    def test_erreur_deplacement_et_balayage(self):
        self.assertEqual(self.r["erreur"], {"error": False, "loading": True})
        self.assertNotEqual(self.r["glisser"]["before"], self.r["glisser"]["after"])     # image agrandie : glisser la déplace
        self.assertEqual(self.r["balayage"], {"from": "1 / 3", "to": "2 / 3"})           # doigt vers la gauche : suivante
        self.assertTrue(self.r["sourisSansBalayage"])

    def test_mode_d_affichage_global_et_conserve_entre_les_dossiers(self):
        self.assertEqual(self.r["modeDefaut"], {"view": "medium", "select": "medium", "saved": None})
        self.assertEqual(self.r["modeDetails"]["saved"], "details")
        # un sous-dossier (autre page) et le retour à la racine gardent le mode choisi
        self.assertEqual(self.r["sousDossier"]["view"], "details")
        self.assertEqual(self.r["retourRacine"]["view"], "details")
        self.assertEqual(self.r["modeGrand"]["view"], "large")
        self.assertEqual(self.r["retourDefaut"]["saved"], None)          # le mode par défaut n'est pas stocké
        self.assertEqual(self.r["modeInvalide"]["view"], "medium")

    def test_mode_suivi_par_les_autres_onglets_et_valeurs_alterees(self):
        self.assertEqual(self.r["autreOnglet"]["view"], "list")
        self.assertEqual(self.r["pageChargee"], "medium")                       # chargement normal : rien à resynchroniser
        self.assertEqual(self.r["pageRestauree"], {"view": "details", "select": "details", "saved": "details"})   # Retour : mode choisi entre-temps
        self.assertEqual(self.r["pageRestaureeDefaut"]["view"], "medium")
        self.assertEqual(self.r["autreCle"], "list")                     # une autre clé du navigateur est ignorée
        self.assertEqual(self.r["valeurInconnue"]["view"], "medium")
        self.assertEqual(self.r["valeurHostile"]["view"], "medium")
        self.assertEqual(self.r["dates"][0], "—")                        # date inconnue
        self.assertTrue(self.r["dates"][1])


class GalerieServerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        t = Path(cls.tmp.name)
        lib = t / "lib"
        (lib / "sous").mkdir(parents=True)
        for name in ("a.png", "b.png", "c.png"):
            (lib / name).write_bytes(png())
        (lib / "notes.txt").write_text("texte\n", encoding="utf-8")
        (lib / "faux.png").write_bytes(b"pas une image")
        env = t / "test.env"
        env.write_text(f"BIBLIO_TOKEN={TOKEN}\n", encoding="utf-8")
        env.chmod(0o600)
        cls.proc = subprocess.Popen([sys.executable, "server.py", str(lib), "-p", str(PORT), "-e", str(env)], cwd=ROOT,
                                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                    env=dict(os.environ, XDG_CACHE_HOME=str(t / "cache"), XDG_CONFIG_HOME=str(t / "cfg"), HOME=str(t)))
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

    @classmethod
    def tearDownClass(cls):
        cls.proc.terminate()
        cls.proc.wait(timeout=5)
        cls.tmp.cleanup()

    @classmethod
    def fetch(cls, method, path, cookie=None):
        conn = http.client.HTTPConnection("127.0.0.1", PORT, timeout=10)
        conn.request(method, path, headers={"Cookie": cookie} if cookie else {})
        r = conn.getresponse()
        return r.status, r, r.read()

    def get(self, path):
        status, r, body = self.fetch("GET", path, self.cookie)
        return status, r, body.decode("utf-8", "replace")

    # --- visionneuse ---
    def test_page_de_la_visionneuse(self):
        status, _, page = self.get("/image?f=b.png")
        self.assertEqual(status, 200)
        for marker in ("id='iv-back'", "id='iv-prev'", "id='iv-next'", "id='iv-zin'", "id='iv-zout'", "id='iv-fit'", "id='iv-zoom'",
                       "id='iv-stage'", "href='/browse'", "2 / 4", "class ImageViewer", "window.ICFG"):
            self.assertIn(marker, page, marker)
        cfg = json.loads(re.search(r"window\.ICFG = (\{.*?\});", page).group(1))
        self.assertEqual([i["f"] for i in cfg["items"]], ["a.png", "b.png", "c.png", "faux.png"])
        self.assertEqual(cfg["current"], "b.png")
        self.assertEqual(cfg["back"], "/browse")

    def test_retour_vers_le_bon_dossier(self):
        (Path(self.tmp.name) / "lib" / "sous" / "z.png").write_bytes(png())
        _, _, page = self.get("/image?f=sous%2Fz.png")
        self.assertIn("href='/browse?folder=sous'", page)

    def test_fichier_qui_n_est_pas_une_image(self):
        self.assertEqual(self.get("/image?f=notes.txt")[0], 404)
        self.assertEqual(self.get("/image?f=absent.png")[0], 404)
        self.assertIn(self.get("/image?f=..%2F..%2Fetc%2Fpasswd")[0], (403, 404))
        self.assertEqual(self.fetch("GET", "/image?f=a.png")[0], 401)       # accès protégé comme le reste

    # --- liste : ouverture et modes d'affichage ---
    def test_un_clic_sur_une_image_ouvre_la_visionneuse(self):
        _, _, page = self.get("/browse")
        self.assertRegex(page, r"<a class='item fcard' href='/image\?f=a\.png'")
        self.assertNotIn("href='/raw?f=a.png'", page)

    def test_selecteur_de_mode_a_cote_du_tri(self):
        _, _, page = self.get("/browse")
        bar = page.split("class='sortbox'")[1].split("id='sort-dir'")[0]
        self.assertIn("id='view'", bar)                                       # dans le même bloc que le tri
        self.assertLess(page.index("id='view'"), page.index("id='sort'"))
        for value, label in (("large", "Grandes icônes"), ("medium", "Icônes moyennes"), ("small", "Petites icônes"), ("list", "Liste"), ("details", "Détails")):
            self.assertIn(f"<option value='{value}'>{label}</option>", page)
        self.assertIn("<main id='listing'>", page)
        self.assertIn("localStorage.getItem('fl:view')", page)                # mode appliqué avant l'affichage de la liste
        self.assertIn("class ViewMode", page)

    def test_mode_applique_avant_le_contenu_de_la_liste(self):
        """Le mode est posé avant que le navigateur lise la première carte : pas d'affichage provisoire en « Icônes moyennes »."""
        (Path(self.tmp.name) / "lib" / "sous" / "y.png").write_bytes(png())
        early = "dataset.view=['large','small','list','details'].includes(v)?v:'medium'"
        for url in ("/browse", "/browse?folder=sous"):                        # racine et sous-dossier (retour au dossier précédent)
            _, _, page = self.get(url)
            main = page.index("<main id='listing'>")
            self.assertTrue(page.startswith("<script>", main + len("<main id='listing'>")))   # premier enfant de <main>
            self.assertEqual(page.index(early), page.index(early, main))      # dans <main>, avant son contenu
            self.assertLess(page.index(early), page.index("<section", main))  # avant les dossiers et les fichiers
            self.assertLess(page.index(early), page.index("class='listbar'"))
            self.assertNotIn("getElementById('listing').dataset.view=v", page)   # l'ancien script, placé après la liste
            # le sélecteur reflète le mode dès son affichage (sinon il montre sa première option jusqu'au chargement des scripts)
            sync = page.index("s.value=document.getElementById('listing').dataset.view")
            self.assertLess(page.index("id='view'"), sync)
            self.assertLess(sync, page.index("<section", main))

    def test_colonnes_du_mode_details_et_miniatures(self):
        _, _, page = self.get("/browse")
        self.assertEqual(page.count("class='cols'"), 6)                       # 1 dossier + 5 fichiers
        self.assertIn("<span class='c-type'>Dossier</span>", page)
        self.assertIn("<span class='c-type'>PNG</span>", page)
        self.assertEqual(page.count("class='dhead'"), 2)                      # en-tête de colonnes : dossiers et fichiers
        self.assertEqual(page.count("class='fthumb'"), 4)                     # une miniature par image
        self.assertIn("src='/thumb?f=a.png'", page)
        self.assertIn("main[data-view='details']", page)                      # mise en page des modes dans la page

    def test_meme_mode_dans_tous_les_dossiers(self):
        (Path(self.tmp.name) / "lib" / "sous" / "y.png").write_bytes(png())    # la barre de la liste n'apparaît que dans un dossier non vide
        _, _, root = self.get("/browse")
        _, _, sub = self.get("/browse?folder=sous")
        for page in (root, sub):                                              # racine et sous-dossier : même réglage global, pas de clé par dossier
            self.assertIn("localStorage.getItem('fl:view')", page)
            self.assertIn("id='view'", page.split("class='sortbox'")[1])
            self.assertNotIn("data-view-key", page)

    # --- miniatures ---
    @unittest.skipUnless(shutil.which("ffmpeg"), "ffmpeg n'est pas installé")
    def test_miniature_d_image(self):
        status, r, body = self.fetch("GET", "/thumb?f=a.png", self.cookie)
        self.assertEqual((status, r.getheader("Content-Type")), (200, "image/jpeg"))
        self.assertTrue(body.startswith(b"\xff\xd8"))
        self.assertEqual(self.fetch("GET", "/thumb?f=faux.png", self.cookie)[0], 404)     # illisible : l'icône reste
        self.assertEqual(self.fetch("GET", "/thumb?f=notes.txt", self.cookie)[0], 404)

    def test_la_visionneuse_est_comptee_comme_une_image_consultee(self):
        from app.devices import ActivityHistory
        self.assertIn("image", ActivityHistory.FREQUENT_CATS)
        self.get("/image?f=c.png")
        _, _, home = self.get("/")
        self.assertIn("%2Fimage%3Ff%3Dc.png", home)                            # fichier fréquent : rouvert dans la visionneuse


if __name__ == "__main__":
    unittest.main()
