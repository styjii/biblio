# Biblio

Bibliothèque web légère : navigation dans un dossier, lecture et édition de texte/code (Vim), aperçu web et
Markdown, lecteurs vidéo et audio, PDF (pdf.js), envoi de fichiers, tableau de bord. Aucune dépendance Python
au-delà de la bibliothèque standard.

```
python3 server.py [dossier] [-p PORT] [-r] [-e .env] [-j dossier-pdfjs]     # voir --help
```

Configuration : copier `.env.example` en `.env` (jeton d'accès, mots de passe).

## Organisation

```
server.py                 point d'entrée (ne contient que l'appel à app.cli.main)
editor.bundle.js          éditeur de texte (bundle JavaScript tiers, servi sur /static/editor.js)
legacy/                   pdf.js (viewer PDF)
app/                      code Python
frontend/                 tout le front-end : CSS, JS et HTML
tests/                    tests (python3 -m unittest discover -s tests -t .)
```

### `app/` — Python

| Module | Rôle |
|---|---|
| `cli.py` | options de la ligne de commande, configuration, démarrage |
| `config.py` | réglages (dossier servi, jeton, mots de passe, limites, chemins) |
| `handler.py` | `FileHandler` : assemble les routes, répartit GET / POST |
| `routes/` | une famille de routes par fichier : `browse`, `viewer`, `player`, `serve`, `edit`, `upload`, `auth`, `dashboard` (+ `base` : envoi des réponses, cookies) |
| `views/` | briques HTML : `layout` (page, barre du haut, messages), `cards` (cartes de fichiers), `dashboard` |
| `security.py` | mot de passe (anti force brute), tickets d'envoi, sessions déverrouillées |
| `devices.py` | appareils connectés, blocage par IP, historique d'activité |
| `media.py`, `sysinfo.py` | miniatures/durées/tags/sous-titres (ffmpeg) ; mémoire et disques |
| `filesystem.py`, `filetypes.py`, `utils.py`, `envfile.py`, `icons.py` | accès disque, types de fichiers, utilitaires, `.env`, icônes SVG |
| `templating.py`, `assets.py` | moteur de gabarits ; chargement des CSS/JS/HTML de `frontend/` |

Les dépendances vont toujours dans le même sens (`config` → services → `views` → `routes` → `handler` → `cli`) :
aucun import circulaire.

**Règle importante** : les réglages renseignés au démarrage (`ROOT`, `TOKEN`, `PASSWORD`, `READONLY`…) se lisent
avec `config.ROOT`, jamais avec `from app.config import ROOT` (la valeur serait figée au chargement du module).

### `frontend/` — HTML, CSS, JavaScript

```
frontend/
  templates/   gabarits HTML (layout/, components/, browse/, viewer/, player/, dashboard/, pages/, partials/)
  css/         main/ (thèmes : base, barre du haut, menu…), markdown.css, dashboard.css, listen.css
  js/          un script par page ; les gros sont découpés par fonctionnalité (browse/, markdown/, dashboard/, listen/)
```

Les fichiers sont lus au démarrage (`app/assets.py`) puis insérés dans les pages : le navigateur ne fait
aucune requête supplémentaire. Après une modification du front-end, relancer le serveur.

- **Dossier de scripts/styles** (`js/browse/`, `css/main/`…) : les fichiers `NN-nom` sont concaténés dans l'ordre
  alphabétique. Pour les scripts, ils forment *un seul bloc* : le serveur les enveloppe dans une fonction anonyme (`asset(..., wrap=True)`),
  `00-init.js` contient les variables partagées. Chaque fichier reste un JavaScript valide pris isolément ;
  le `jsconfig.json` du dossier indique à l'éditeur (tsserver) que ces fichiers forment un seul script.
- **Gabarits** (`templates/*.html`), syntaxe volontairement minimale :
  - `{{ nom }}` : valeur insérée **telle quelle** (échapper avec `html.escape` côté Python tout ce qui vient d'un nom
    de fichier, d'un paramètre, etc.) ;
  - `{{ icon nom taille }}` : icône SVG ;
  - `{# commentaire #}` : retiré au rendu.
  Les sauts de ligne et l'indentation sont supprimés au rendu : on écrit un gabarit lisible sans changer le HTML.
  Pour garder une espace entre deux éléments, la mettre sur la même ligne.

### Lecteur vidéo (`/watch`)

Lecteur façon YouTube : les commandes natives du navigateur sont remplacées par une interface dessinée par
`frontend/js/watch/03-interface-du-lecteur.js` (classe `PlayerUI`) et `frontend/css/main/12-lecteur-youtube.css`.
Sans JavaScript, l'attribut `controls` de la balise `<video>` garde les commandes natives.

- **Commandes** : lecture/pause, vidéo suivante, volume, durée, sous-titres (CC), paramètres (vitesse de 0,25× à 2×,
  sous-titres, lecture automatique), mode cinéma (grand écran), image dans l'image, plein écran.
- **Barre de position** : plage chargée, bulle de temps au survol, glissement à la souris ou au doigt, redessinée à
  chaque image pendant la lecture. Les commandes se masquent après 3 s en lecture et réapparaissent au mouvement.
- **Tactile** : tape = afficher/masquer les commandes, double tape à gauche/droite = ∓10 s (les sauts s'additionnent),
  double tape au centre = lecture/pause ; gros boutons précédente / lecture / suivante au centre.
- **Clavier** : `K`/espace, `J`/`L` ±10 s, flèches ±5 s et volume, `0`–`9` (0–90 %), `N`/`P`, `S`, `R`, `<`/`>`,
  `M`, `C`, `T`, `I`, `F`.
- **Responsive** : la taille des commandes suit la largeur du lecteur (requêtes de conteneur), donc aussi en plein
  écran ; le plein écran est celui du conteneur (la vidéo *et* ses commandes). La couleur de la barre de position est la
  variable `--vp-accent` (`12-lecteur-youtube.css`).
- `PlaybackGuard` (`03-reprise-apres-incident.js`) reprend la lecture après une coupure du réseau ; `ResumeTracker`
  (`03-position.js`) mémorise la position côté serveur.

### Ajouter ou modifier une page

1. Écrire le gabarit dans `frontend/templates/…` ; le CSS/JS associé dans `frontend/css`, `frontend/js`.
2. Déclarer les constantes dans `app/assets.py` (`MA_PAGE_JS = asset("js/ma_page.js")`).
3. Dans une route (`app/routes/…`) : `render("ma/page", valeur=…)`, entourée de `doc_open(…)` et `doc_close(…)`.
4. Ajouter la route dans `FileHandler.do_GET` (`app/handler.py`).

Les tests vérifient que chaque appel `render(…)` fournit exactement les variables du gabarit, qu'aucun gabarit
n'est orphelin et que les scripts assemblés sont du JavaScript valide (si `node` est installé).
