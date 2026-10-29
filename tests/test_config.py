"""config.py : lecture du .env, chargement, jeton, mots de passe et contrôle d'accès aux fichiers."""
import os
import tempfile
import unittest
from pathlib import Path

from app import config


class ConfigTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.saved = {k: getattr(config, k) for k in
                     ("ROOT", "PORT", "READONLY", "ENV_PATH", "TOKEN", "PASSWORD", "DASH_PASSWORD", "MAX_UPLOAD", "ROOT_ID",
                      "MAX_FAILS", "LOCK_SECONDS")}
        cls.tmp = tempfile.TemporaryDirectory()
        t = Path(cls.tmp.name)
        (t / "lib" / "sub").mkdir(parents=True)
        cls.env = t / "mon.env"
        cls.env.write_text("# commentaire\nexport BIBLIO_TOKEN='abc123'\nBIBLIO_PASSWORD=\"secret\"\n"
                           "BIBLIO_MAX_UPLOAD_MB=1\nBIBLIO_DISKS=/a=Disque A;/b\n", encoding="utf-8")
        cls.env.chmod(0o600)
        config.load(t / "lib", 9999, True, str(cls.env))

    @classmethod
    def tearDownClass(cls):
        for k, v in cls.saved.items():
            setattr(config, k, v)
        cls.tmp.cleanup()

    def test_lecture_du_env_et_chargement(self):
        self.assertEqual(config.read_env(self.env)["BIBLIO_TOKEN"], "abc123")
        self.assertEqual((config.TOKEN, config.PASSWORD, config.DASH_PASSWORD), ("abc123", "secret", "secret"))
        self.assertEqual((config.PORT, config.READONLY, config.MAX_UPLOAD), (9999, True, 1024 * 1024))
        self.assertEqual(config.DISKS, [("/a", "Disque A"), ("/b", "/b")])
        self.assertEqual(config.ENV_PATH, self.env.resolve())
        self.assertEqual(config.env_permissions_warning(), "")

    def test_jeton_cree_et_ecrit_dans_le_env(self):
        env = Path(self.tmp.name) / "vide.env"
        saved = config.ENV_PATH, dict(config.ENV)
        try:
            config.ENV_PATH = env
            config.ENV.clear()
            token = config.load_token()
        finally:
            config.ENV_PATH = saved[0]
            config.ENV.clear(); config.ENV.update(saved[1])
        self.assertGreaterEqual(len(token), 12)
        self.assertEqual(config.read_env(env)["BIBLIO_TOKEN"], token)
        self.assertEqual(env.stat().st_mode & 0o777, 0o600)

    def test_jeton(self):
        self.assertTrue(config.token_ok("abc123"))
        for bad in ("", "abc124", "ABC123"):
            self.assertFalse(config.token_ok(bad))

    def test_mots_de_passe(self):
        self.assertEqual(config.password_scopes("secret"), {"files", "dash"})
        self.assertEqual(config.password_scopes("autre"), set())
        config.MAX_FAILS, config.LOCK_SECONDS = 2, 60
        self.assertEqual(config.check_password("1.1.1.1", "x"), (False, "Mot de passe incorrect."))
        self.assertEqual(config.check_password("1.1.1.1", "y")[0], False)
        ok, msg = config.check_password("1.1.1.1", "secret")        # verrouillé même avec le bon mot de passe
        self.assertFalse(ok)
        self.assertTrue(msg.startswith("Trop"))
        self.assertTrue(config.check_password("2.2.2.2", "secret")[0])

    def test_sessions_et_jetons_d_envoi(self):
        sid = config.grant_unlock("", {"files"})
        self.assertEqual(config.unlock_scopes(sid), {"files"})
        config.drop_dash_session(sid)
        self.assertEqual(config.unlock_scopes(sid), set())
        t = config.issue_ticket()
        self.assertTrue(config.use_ticket(t))
        self.assertFalse(config.use_ticket("inconnu"))

    def test_chemins_proteges(self):
        root = config.ROOT
        self.assertEqual(config.resolve_inside("sub"), root / "sub")
        for bad in ("../x", "/etc/passwd", "sub/../../x", "a\x00b"):
            self.assertIsNone(config.resolve_inside(bad), bad)
        self.assertTrue(config.is_env_path(self.env.resolve()))
        # le .env placé dans le dossier servi n'est jamais accessible, même par un lien
        inside = root / "mon.env"
        inside.write_text("BIBLIO_TOKEN=abc123\n")
        config.ENV_PATH = inside.resolve()
        try:
            self.assertIsNone(config.resolve_inside("mon.env"))
            self.assertTrue(config.holds_protected(root))
            self.assertFalse(config.holds_protected(root / "sub"))
        finally:
            config.ENV_PATH = self.env.resolve()
        self.assertTrue(config.holds_protected(config.HERE))

    def test_noms_valides(self):
        for ok in ("a.txt", "Cours été", ".cache"):
            self.assertTrue(config.valid_name(ok), ok)
        for bad in ("", ".", "..", "a/b", "a\\b", "x" * 300):
            self.assertFalse(config.valid_name(bad), bad)
        self.assertEqual(config.clean_upload_name("d/s/f.txt"), ["d", "s", "f.txt"])
        for bad in ("/abs", "a/../b", "a//b", "a\\b", ""):
            self.assertIsNone(config.clean_upload_name(bad), bad)


if __name__ == "__main__":
    unittest.main()
