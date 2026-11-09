"""Lecteur vidéo : glissements au doigt (volume, position) et verrouillage des commandes."""
import re
import unittest

from app import assets, config

WATCH_HTML = (assets.FRONTEND_DIR / "templates/player/watch.html").read_text(encoding="utf-8")
PLAYER_PY = (config.HERE / "app/routes/player.py").read_text(encoding="utf-8")


class GlissementsTests(unittest.TestCase):
    """Plus aucun glissement du doigt sur la vidéo (volume, position) : seules les tapes comptent."""
    js = assets.WATCH_JS

    def test_aucun_geste_de_glissement(self):
        for mot in ("#bindSwipe", "swipe", "vswipe", "swiping", "#showHud", "vp-hud"):
            self.assertNotIn(mot, self.js, mot)
            self.assertNotIn(mot, assets.CSS, mot)
            self.assertNotIn(mot, WATCH_HTML, mot)

    def test_pas_d_indication_de_glissement_dans_l_aide(self):
        self.assertNotIn("glisser de haut en bas", WATCH_HTML)

    def test_une_tape_apres_un_pincement_est_ignoree(self):
        self.assertIn("if (fingers.size > 1) this.#pinched = true;", self.js)
        self.assertIn("if (this.#pinched) return;", self.js)

    def test_css_touch_action(self):
        self.assertIn(".player.vp-on video{touch-action:pan-y}", assets.CSS)


class VerrouillageTests(unittest.TestCase):
    js = assets.WATCH_JS

    def test_bouton_hors_de_la_couche_des_commandes(self):
        self.assertIn("id='vp-lock'", WATCH_HTML)
        self.assertGreater(WATCH_HTML.index("id='vp-lock'"), WATCH_HTML.index("id='vp-menu'"))
        self.assertLess(WATCH_HTML.index("id='vp-lock'"), WATCH_HTML.index("<section class='info'>"))
        self.assertIn('"lock", "unlock")', PLAYER_PY)                      # icônes fournies au script

    def test_le_bouton_change_d_icone_et_de_libelle(self):
        render = self.js.split("#renderLock() {")[1].split("\n  }\n")[0]
        self.assertIn("setIcon(button, this.#locked ? 'unlock' : 'lock');", render)
        self.assertIn("'Déverrouiller les commandes'", render)

    def test_boutons_gestes_molette_et_clavier_inactifs(self):
        self.assertIn("this.#ui.addEventListener('click', (e) => {\n      if (this.#locked) return;", self.js)
        self.assertIn("if (this.#locked) { this.#peekLock(); return; }", self.js)
        self.assertIn("if (this.#ui.locked) {", self.js)
        self.assertIn("if (lower === 'v') { this.#ui.toggleLock(); e.preventDefault(); }", self.js)
        self.assertIn("v: () => this.#ui.toggleLock(),", self.js)

    def test_verrouillage_conserve_pour_la_video_suivante(self):
        """Verrouillé, il le reste d'une vidéo à l'autre : mémorisé à chaque changement d'état, relu à chaque page, jamais effacé à la lecture."""
        toggle = self.js.split("toggleLock(force = !this.#locked) {")[1].split("\n  }\n")[0]
        self.assertIn("this.#rememberLock();", toggle)
        remember = self.js.split("#rememberLock() {")[1].split("\n  }\n")[0]
        self.assertIn("sessionStorage.setItem('vl:lock', '1')", remember)
        self.assertIn("sessionStorage.removeItem('vl:lock')", remember)    # effacé seulement au déverrouillage
        bind = self.js.split("#bindLock() {")[1].split("\n  }\n")[0]
        self.assertIn("sessionStorage.getItem('vl:lock')", bind)
        self.assertNotIn("removeItem", bind)                              # lu sans être consommé
        self.assertNotIn("carryLock", self.js)

    def test_css(self):
        css = assets.CSS
        self.assertIn(".player.locked .vp-ui{opacity:0; visibility:hidden; pointer-events:none}", css)
        self.assertIn(".player.locked:not(.lock-peek) .vp-lock", css)


if __name__ == "__main__":
    unittest.main()


class MenuSansDefilementEtBarresTests(unittest.TestCase):
    js = assets.WATCH_JS
    css = assets.CSS

    def test_menu_ne_defile_jamais(self):
        menu = self.css.split(".vp-menu{position:absolute;")[1].split("}")[0]
        self.assertIn("overflow:hidden", menu)
        self.assertNotIn("overflow:auto", menu)
        self.assertNotIn("scrollbar", menu)
        self.assertIn(".vp-menu.cols{display:grid; grid-template-columns:1fr 1fr;", self.css)
        self.assertIn(".vp-menu[hidden]{display:none}", self.css)          # « cols » ne doit pas rouvrir un menu fermé

    def test_menu_ajuste_a_chaque_affichage_et_redimensionnement(self):
        render = self.js.split("this.#menu.replaceChildren(...rows);")[1].split("\n  }\n")[0]
        self.assertIn("this.#fitMenu();", render)
        self.assertIn("addEventListener('resize', () => { if (!this.#menu.hidden) this.#fitMenu(); });", self.js)
        fit = self.js.split("#fitMenu() {")[1].split("\n  }\n")[0]
        self.assertIn("menu.scrollHeight > menu.clientHeight", fit)
        self.assertIn("MENU_FIT", fit)

    def test_lignes_du_menu_compressibles(self):
        self.assertIn("min-height:var(--vp-row,42px); padding:0 12px", self.css)
        self.assertIn(".vp-menu button{min-height:var(--vp-row,46px)}", self.css)   # doigt : lignes plus hautes tant que la place le permet

    def test_volume_et_position_partagent_rail_et_pastille(self):
        self.assertIn("--vp-track:4px; --vp-track-on:6px; --vp-thumb:14px;", self.css)
        for rule in (".vp-rail{position:relative; width:100%; height:var(--vp-track);",
                     ".vp-rng::-webkit-slider-runnable-track{height:var(--vp-track);",
                     ".vp-rng::-moz-range-track{height:var(--vp-track);",
                     ".vp-rng::-webkit-slider-thumb{-webkit-appearance:none; width:var(--vp-thumb);"):
            self.assertIn(rule, self.css)

    def test_reglages_actifs_meme_repere(self):
        self.assertIn(".vp-row .vp-b[aria-pressed='true']:not([data-act='mute'])", self.css)


class MenuSansDoublonsTests(unittest.TestCase):
    """Ce que contient le menu des paramètres ne figure jamais dans la barre principale, quelle que soit la taille du lecteur."""
    js = assets.WATCH_JS
    css = assets.CSS

    def test_barre_sans_les_commandes_du_menu(self):
        bar = WATCH_HTML.split("<div class='vp-bar'>")[1].split("<div class='vp-menu'")[0]
        for ident in ("vp-shuffle", "vp-repeat", "vp-rate"):
            self.assertNotIn(ident, WATCH_HTML)
        for act in ("shuffle", "repeat", "rate"):
            self.assertNotIn(f"data-act='{act}'", bar)
        for act in ("prev", "back", "play", "fwd", "next", "mute", "cc", "settings", "theater", "pip", "fs"):
            self.assertIn(f"data-act='{act}'", bar)

    def test_commandes_du_menu_toujours_accessibles(self):
        for label in ("Lecture automatique", "Lecture aléatoire", "Répétition", "Vitesse de lecture", "Sous-titres", "Télécharger la vidéo"):
            self.assertIn(f"row('{label}'", self.js)
        for key in ("s: () => this.setShuffle(", "r: () => this.cycleRepeat(),", "c: () => this.#ui.toggleCaptions(),"):
            self.assertIn(key, self.js)                                    # les raccourcis clavier restent actifs

    def test_plus_de_code_mort_pour_les_boutons_retires(self):
        for token in ("$('vp-shuffle')", "$('vp-repeat')", "$('vp-rate')"):
            self.assertNotIn(token, self.js)
        for token in (".vp-mode", ".vp-rate"):
            self.assertNotIn(token, self.css)


class BoutonSousTitresTests(unittest.TestCase):
    """Bouton « sous-titres » de la barre : à gauche du bouton des paramètres, caché sans piste, enfoncé quand une piste est affichée."""
    js = assets.WATCH_JS
    css = assets.CSS

    def test_a_gauche_des_parametres_dans_le_groupe_de_droite(self):
        right = WATCH_HTML.split("<div class='vp-r'>")[1].split("</div>")[0]
        self.assertLess(right.index("data-act='cc'"), right.index("data-act='settings'"))
        button = re.search(r"<button[^>]*data-act='cc'[^>]*>", right).group(0)
        self.assertIn("aria-pressed='false'", button)
        self.assertIn(" hidden", button)                                   # caché tant que la vidéo n'a aucune piste

    def test_le_clic_active_ou_desactive_les_sous_titres(self):
        self.assertIn("cc: () => this.toggleCaptions(),", self.js)         # même action que la touche C
        self.assertIn("this.#syncCaptionsButton();", self.js)              # état remis à jour à chaque changement de piste et de vidéo
        self.assertIn("button.hidden = !this.#tracks.length;", self.js)
        self.assertIn("aria-pressed", self.js.split("#syncCaptionsButton() {")[1].split("\n  }")[0])

    def test_meme_repere_que_les_autres_reglages_actifs(self):
        self.assertIn(".vp-row .vp-b[aria-pressed='true']:not([data-act='mute'])", self.css)


class ZoneFixeMobileTests(unittest.TestCase):
    """Mobile à lecteur fixe : lecteur, informations ET en-tête de la liste restent en haut ; aucun glissement dans cette zone ne fait défiler la liste."""
    css = assets.CSS
    js = assets.WATCH_JS
    fixed = "@media(max-width:999px) and (min-height:501px){"

    def block(self):
        return self.css.split(self.fixed)[1].split("@keyframes rowflash")[0]

    def test_en_tete_de_la_liste_colle_sous_la_zone_fixe(self):
        head = self.block().split(".next h2{")[1].split("}")[0]
        self.assertIn("position:sticky", head)
        self.assertIn("top:calc(var(--tb) + var(--dock-h,0px))", head)
        self.assertIn("background:var(--bg)", head)                       # les lignes passent dessous sans transparaître

    def test_aucun_defilement_de_la_liste_depuis_la_zone(self):
        block = self.block()
        self.assertIn("touch-action:pinch-zoom", block.split(".dock{")[1].split("}")[0])
        self.assertIn("touch-action:pinch-zoom", block.split(".next h2{")[1].split("}")[0])
        self.assertIn(".dock .chips{touch-action:pan-x}", block)          # les pastilles gardent leur défilement horizontal

    def test_hors_mode_fixe_rien_ne_change(self):
        outside = self.css.replace(self.block(), "")
        self.assertNotIn(".next h2{position:sticky", outside)
        self.assertNotIn("touch-action:pinch-zoom", outside)

    def test_hauteur_de_la_zone_publiee_pour_le_css(self):
        body = self.js.split("#bindDock() {")[1].split("\n  }\n")[0]
        self.assertIn("typeof ResizeObserver === 'undefined'", body)
        self.assertIn("setProperty('--dock-h', `${dock.offsetHeight}px`)", body)
        self.assertIn("this.#bindDock();", self.js)

    def test_ligne_en_cours_amenee_sous_l_en_tete(self):
        body = self.js.split("#revealCurrent(smooth) {")[1].split("\n  }\n")[0]
        self.assertIn("document.querySelector('.next h2')", body)
        self.assertIn("head?.offsetHeight", body)


class StyleDuVolumeTests(unittest.TestCase):
    """Même contrôle du volume à toutes les tailles : bouton muet en carré arrondi d'accent, curseur accent + pastille blanche toujours visible."""
    css = assets.CSS

    def test_bouton_muet_carre_arrondi_accent_quand_le_curseur_est_ouvert(self):
        self.assertIn(".vp-vol .vp-b{border-radius:28%;", self.css)
        self.assertIn(".vp-vol:hover .vp-b,.vp-vol:focus-within .vp-b,.vp-vol.peek .vp-b{background-color:var(--vp-accent);", self.css)

    def test_curseur_accent_et_pastille_blanche(self):
        self.assertIn("--vp-fill:var(--vp-accent);", self.css)
        self.assertIn("--vp-knob:#fff", self.css)
        thumb = self.css.split(".vp-rng::-webkit-slider-thumb{")[1].split("}")[0]
        self.assertIn("background:var(--vp-knob)", thumb)
        self.assertNotIn("scale(0)", thumb)                                # pastille visible dès que le curseur l'est
        rules = "".join(rule for rule in self.css.split("\n") if ".vp-rng" in rule)
        self.assertNotIn("scale(0)", rules)

    def test_un_seul_style_a_toutes_les_tailles(self):
        # les modes tactile et étroit ne changent que les dimensions du curseur, jamais ses couleurs ni la forme du bouton
        for token in ("--vp-fill", "--vp-knob"):
            self.assertEqual(self.css.count(f"{token}:"), 1)
        self.assertEqual(self.css.count(".vp-vol .vp-b{border-radius"), 1)
