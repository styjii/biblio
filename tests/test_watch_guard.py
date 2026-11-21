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

    def test_decodage_impossible_a_la_position_memorisee_recule_puis_repart(self):
        r = self.r["decodage_position_empoisonnee"]
        self.assertLessEqual(r["loads"], 4)                          # pas de boucle de rechargements
        self.assertEqual((r["paused"], r["error"]), (False, False))  # la lecture est repartie...
        self.assertLess(r["time"], 120 + 30)                         # ...et continue après le point qui posait problème
        self.assertEqual(r["forgotten"], 0)                          # position encore valable : on ne l'efface pas

    def test_decodage_repli_jusqu_au_debut_efface_la_position(self):
        r = self.r["decodage_repli_au_debut"]
        self.assertEqual((r["paused"], r["error"]), (False, False))
        self.assertGreaterEqual(r["forgotten"], 1)                   # sinon chaque rechargement de la page retournerait au même endroit

    def test_decodage_impossible_partout_s_arrete_sans_boucle(self):
        r = self.r["decodage_impossible"]
        self.assertLessEqual(r["loads"], 4)
        self.assertEqual(r["loads"], r["loadsLater"])                # plus aucun rechargement après l'abandon
        self.assertGreaterEqual(r["forgotten"], 1)
        self.assertIn("décodée", r["msg"])                           # message clair, plus « recharge la page » (inutile)

    def test_reprise_lente_n_est_jamais_rechargee(self):
        r = self.r["reprise_lente"]
        self.assertEqual(r["reloaded"], 0)                           # données au compte-gouttes : on attend, on ne repart pas de zéro
        self.assertEqual((r["paused"], r["time"]), (False, 3128))

    def test_changement_de_reseau_en_lecture_normale_ne_recharge_rien(self):
        r = self.r["online_en_lecture"]
        self.assertEqual((r["reloaded"], r["paused"], r["time"]), (0, False, 130))

    def test_silence_complet_du_flux_finit_par_recharger(self):
        r = self.r["silence_complet"]
        self.assertEqual(r["early"], 0)                              # pas avant 30 s de silence
        self.assertEqual((r["reloaded"], r["paused"], r["time"]), (1, False, 120))


if __name__ == "__main__":
    unittest.main()


@unittest.skipUnless(shutil.which("node"), "Node.js n'est pas installé")
class LecteurLocalTests(unittest.TestCase):
    """Le lecteur de l'accueil est le script de la page de lecture, en mode « local » (fichiers de l'appareil)."""

    @classmethod
    def setUpClass(cls):
        harness = Path(__file__).resolve().parent / "js" / "local_player_harness.js"
        out = subprocess.run(["node", str(harness)], capture_output=True, text=True, timeout=60)
        assert out.returncode == 0, out.stderr
        cls.r = json.loads(out.stdout)

    def test_interface_proposee_a_la_page(self):
        self.assertEqual(self.r["api"], ["add", "clear", "play", "remove", "setMode"])

    def test_sans_fichier_le_lecteur_est_masque_et_les_touches_restent_libres(self):
        r = self.r["vide"]
        self.assertTrue(r["hidden"])
        self.assertEqual((r["count"], r["pos"]), (0, "0 / 0"))
        self.assertTrue(r["espaceIgnore"])                           # espace : la page défile normalement

    def test_ajout_ne_garde_que_les_fichiers_du_mode_affiche(self):
        r = self.r["ajout"]
        self.assertEqual(r["result"], {"mode": "video", "accepted": 2, "rejected": 1, "other": 1})   # b.flac : autre mode ; c.txt : ni vidéo ni audio
        self.assertEqual((r["src"], r["hidden"], r["count"], r["title"], r["pos"], r["rows"]), ("blob:1", False, 2, "a", "1 / 2", 2))
        self.assertEqual(self.r["dernierEvenement"], {"count": 2, "mode": "video", "counts": {"video": 2, "audio": 0}})

    def test_enchainement_comme_sur_la_page_de_lecture(self):
        r = self.r["suite"]
        self.assertEqual((r["src"], r["pos"], r["revoked"]), ("blob:2", "2 / 2", ["blob:1"]))   # l'URL précédente est libérée
        self.assertEqual(r["poster"], "")                            # une vidéo : pas d'image de remplacement

    def test_clic_dans_la_file_et_retrait(self):
        self.assertEqual((self.r["clic"]["src"], self.r["clic"]["pos"]), ("blob:3", "1 / 2"))
        r = self.r["retraitAutre"]
        self.assertEqual((r["count"], r["pos"], r["src"]), (1, "1 / 1", "blob:3"))

    def test_vidage_libere_toutes_les_urls(self):
        r = self.r["vidage"]
        self.assertEqual((r["count"], r["hidden"], r.get("src"), r["poster"]), (0, True, None, ""))
        self.assertEqual(len(r["revoked"]), r["created"])            # aucune URL locale ne reste ouverte
        self.assertTrue(self.r["espaceApresVidage"])

    # --- modes Vidéo / Audio ---
    def test_passage_en_audio_met_la_video_de_cote(self):
        r = self.r["versAudio"]
        self.assertTrue(r["changed"])
        self.assertEqual((r["hidden"], r["count"], r["paused"]), (True, 0, True))     # mode Audio vide : zone de dépôt ; la lecture est interrompue
        self.assertEqual(r["event"], {"count": 0, "mode": "audio", "counts": {"audio": 0, "video": 1}})
        self.assertFalse(r["memeMode"])                              # même mode ou mode inconnu : rien ne change
        self.assertFalse(r["inconnu"])

    def test_chaque_mode_a_sa_file_et_l_audio_garde_son_image(self):
        r = self.r["ajoutAudio"]
        self.assertEqual(r["result"], {"mode": "audio", "accepted": 2, "rejected": 0, "other": 1})   # f.mp4 reste hors du mode Audio
        self.assertEqual((r["count"], r["pos"], r["poster"]), (2, "1 / 2", "audio"))
        self.assertEqual(r["event"]["counts"], {"audio": 2, "video": 1})

    def test_retour_a_un_mode_reprend_position_et_lecture(self):
        r = self.r["retourVideo"]
        self.assertEqual((r["count"], r["title"], r["poster"], r["autoplay"]), (1, "a", "", True))
        self.assertEqual(self.r["avantMetadonnees"]["sets"], [])      # pas de saut avant que la durée soit connue
        r = self.r["retourVideoPrete"]
        self.assertEqual((r["time"], r["paused"], r["sets"]), (42, False, [42]))   # position rejointe une seule fois, lecture reprise
        r = self.r["audioRepris"]
        self.assertEqual((r["time"], r["paused"], r["poster"]), (7, False, "audio"))

    def test_une_pause_est_conservee_au_retour(self):
        r = self.r["videoRestaureeEnPause"]
        self.assertEqual((r["time"], r["paused"], r["autoplay"], r["plays"]), (45, True, False, 0))   # ni lecture automatique, ni play()
        self.assertEqual(self.r["compteurs"], {"count": 1, "mode": "video", "counts": {"video": 1, "audio": 2}})

    def test_volume_muet_et_vitesse_ne_changent_pas_d_un_mode_a_l_autre(self):
        for name in ("versAudio", "retourVideo", "retourVideoPrete", "audioRepris", "videoRestaureeEnPause"):
            r = self.r[name]
            self.assertEqual((r["volume"], r["muted"], r["rate"]), (0.4, True, 1.5), name)

    # --- plein écran ---
    def test_plein_ecran_rattrape_une_position_perdue_une_seule_fois(self):
        r = self.r["pleinEcranPerte"]
        self.assertEqual((r["paused"], r["sets"]), (False, [120.75]))   # 120 s + 0,5 s de transition à la vitesse 1,5
        self.assertEqual(self.r["pleinEcranSansBoucle"], [120.75])       # aucune boucle de synchronisation

    def test_plein_ecran_ne_touche_a_rien_quand_tout_va_bien(self):
        self.assertEqual(self.r["pleinEcranPause"], {"time": 50, "paused": True, "sets": []})
        self.assertEqual(self.r["pleinEcranNormal"], {"time": 10.4, "paused": False, "sets": [], "plays": 0})

    def test_plein_ecran_respecte_l_action_de_l_utilisateur(self):
        self.assertEqual(self.r["pleinEcranActionUtilisateur"], {"time": 0, "paused": True, "sets": []})   # il a mis en pause : on n'y revient pas
        self.assertEqual(self.r["pauseVoulue"], {"time": 60, "paused": True, "sets": [], "plays": 0})

    def test_plein_ecran_relance_une_lecture_interrompue(self):
        self.assertEqual(self.r["sortieEnPause"], {"time": 200, "paused": False, "sets": []})      # sortie : le navigateur met en pause
        self.assertEqual(self.r["natifIos"], {"time": 101, "paused": False, "sets": []})            # plein écran natif d'iOS, sans demande du lecteur
        self.assertEqual(self.r["eventsMultiples"], {"time": 30, "paused": False, "sets": [], "plays": 1})   # plusieurs événements : une seule reprise

    def test_plein_ecran_ne_force_jamais_une_pause(self):
        self.assertEqual(self.r["jamaisDePauseForcee"], {"time": 70, "paused": False, "sets": []})

    # --- défilement de la page autour du plein écran ---
    def test_la_page_garde_sa_hauteur_pendant_le_plein_ecran(self):
        self.assertEqual(self.r["pageMaintenue"], "3000px")             # le recadrage du navigateur n'a plus de limite à imposer
        self.assertEqual(self.r["pendantPleinEcran"]["minHeight"], "3000px")
        self.assertEqual(self.r["pendantPleinEcran"]["appels"], 0)      # aucun défilement forcé pendant le plein écran

    def test_la_page_retrouve_sa_position_a_la_sortie_du_plein_ecran(self):
        self.assertEqual(self.r["sortieImmediate"], {"y": 1400, "appels": [[0, 1400]]})     # tout de suite, sans attendre
        self.assertEqual(self.r["sortieApres"], {"y": 1400, "minHeight": "", "appels": 1})  # une seule correction, hauteur rendue

    def test_aucun_defilement_si_la_page_n_a_pas_bouge(self):
        self.assertEqual(self.r["sansChangement"], {"y": 900, "appels": 1})

    def test_plein_ecran_natif_ios_et_plein_ecran_refuse(self):
        self.assertEqual(self.r["natifDefilement"], {"y": 700, "appels": 1})
        self.assertEqual(self.r["refuse"], {"retenue": "3000px", "apres": ""})   # pas de hauteur forcée si le plein écran ne vient pas
