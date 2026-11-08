"""Liste des fichiers : sous-titres rattachés à une vidéo masqués, liste unique triable (nom, date, taille, durée, type)."""
import tempfile
import unittest
from pathlib import Path

from app import assets
from app.media import media
from app.views.cards import sort_attrs


class SousTitresMasquesTests(unittest.TestCase):
    def test_seuls_les_sous_titres_d_une_video_du_dossier_sont_masques(self):
        with tempfile.TemporaryDirectory() as tmp:
            names = ["film.mp4", "film.fr.srt", "film.en.vtt", "film.srt", "Clip.MP4", "clip.fr.srt",
                     "seul.srt", "notes.txt", "autre.fr.srt"]
            files = [Path(tmp) / n for n in names]
            hidden = {f.name for f in media.attached_subtitles(files)}
        self.assertEqual(hidden, {"film.fr.srt", "film.en.vtt", "film.srt", "clip.fr.srt"})

    def test_sans_video_rien_n_est_masque(self):
        files = [Path("a.srt"), Path("b.vtt"), Path("c.txt")]
        self.assertEqual(media.attached_subtitles(files), set())

    def test_meme_regle_que_le_lecteur(self):
        """Un sous-titre masqué dans la liste est bien celui que le lecteur propose pour la vidéo."""
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            for n in ("film.mp4", "film.fr.srt", "film.en.vtt", "autre.srt"):
                (d / n).write_text("x")
            files = sorted(d.iterdir())
            player = {f for f, _ in media.find_subtitles(d / "film.mp4")}
            self.assertEqual(media.attached_subtitles(files), player)


class ListeTrieeTests(unittest.TestCase):
    def test_attributs_de_tri(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "Cours.PDF"
            p.write_bytes(b"x" * 10)
            attrs = sort_attrs(p, 3)
        self.assertIn("data-order='3'", attrs)
        self.assertIn("data-bytes='10'", attrs)
        self.assertIn("data-ext='pdf'", attrs)
        self.assertRegex(attrs, r"data-mtime='\d+'")

    def test_une_seule_liste_sans_regroupement_par_categorie(self):
        src = (assets.FRONTEND_DIR.parent / "app/routes/browse.py").read_text(encoding="utf-8")
        self.assertIn('key="files"', src)
        self.assertNotIn("grouped", src)

    def test_filtres_conserves_et_filtrent_par_fichier(self):
        self.assertIn("this.#active !== 'all' && el.dataset.group !== this.#active", assets.BROWSE_JS)
        self.assertIn("data-g='{{ key }}'", (assets.FRONTEND_DIR / "templates/browse/filter_chip.html").read_text(encoding="utf-8"))

    def test_criteres_de_tri(self):
        tpl = (assets.FRONTEND_DIR / "templates/browse/listbar.html").read_text(encoding="utf-8")
        for value in ("name", "date", "size", "duration", "type"):
            self.assertIn(f"<option value='{value}'>", tpl)
        self.assertIn("id='sort-dir'", tpl)                                   # sens croissant / décroissant
        self.assertIn("DEFAULT_DIR = {name: 'asc'", assets.BROWSE_JS)         # par défaut : nom croissant
        self.assertIn("localStorage.setItem(ListSort.KEY", assets.BROWSE_JS)  # choix mémorisé

    def test_valeurs_inconnues_toujours_a_la_fin(self):
        self.assertIn("unknownX === unknownY ? byName(a, b) : (unknownX ? 1 : -1)", assets.BROWSE_JS)

    def test_durees_lues_pour_tout_le_dossier(self):
        self.assertIn("[data-kind=\"video\"], [data-kind=\"audio\"]", assets.BROWSE_JS)
        self.assertIn("card.dataset.dur", assets.DECORATE_JS)                 # durée déjà lue par les vignettes : réutilisée


if __name__ == "__main__":
    unittest.main()
