# Biblio

[![Licence : MIT](https://img.shields.io/badge/licence-MIT-green.svg)](LICENSE)

Bibliothèque web légère et auto-hébergée : on pointe un dossier, et Biblio le rend consultable depuis n'importe quel
navigateur du réseau local (ordinateur, téléphone, tablette). Navigation, lecture et édition de texte et de code
(mode Vim), aperçu Markdown et pages web, lecteurs vidéo et audio, visionneuse PDF, envoi de fichiers et tableau de
bord de supervision.

**Aucune dépendance Python** au-delà de la bibliothèque standard : pas de `pip install`, pas de base de données, pas
de compilation du front-end.

## Sommaire

- [Fonctionnalités](#fonctionnalités)
- [Prérequis](#prérequis)
- [Installation](#installation)
- [Démarrage rapide](#démarrage-rapide)
- [Utilisation](#utilisation)
- [Configuration](#configuration)
- [Sécurité](#sécurité)
- [Guide des fonctionnalités](#guide-des-fonctionnalités)
- [Architecture](#architecture)
- [Développement](#développement)
- [Dépannage](#dépannage)
- [Composants tiers et licences](#composants-tiers-et-licences)

## Fonctionnalités

| Domaine | Ce que fait Biblio |
|---|---|
| Navigation | Dossiers et fichiers en cartes, fil d'Ariane, recherche dans le dossier, filtres par catégorie, tri (nom, date, taille, durée, type), miniatures des vidéos |
| Texte et code | Lecture et édition avec CodeMirror, mode Vim, numéros de ligne, retour à la ligne, taille du texte réglable |
| Markdown | Aperçu rendu dans le navigateur : sommaire, progression de lecture, réglages de lecture, copie du code, impression |
| Pages web | Aperçu isolé (sandbox) des fichiers HTML, avec navigation entre les pages du dossier |
| Vidéo | Lecteur complet : sous-titres, vitesse, mode cinéma, image dans l'image, liste de lecture du dossier, reprise de la position |
| Audio | Lecteur avec liste de lecture, pochettes et tags, lecture aléatoire, répétition, touches multimédia du téléphone |
| PDF | Visionneuse pdf.js (ou lecteur du navigateur si pdf.js est absent) |
| Fichiers | Création de fichiers et de dossiers, renommage, suppression, envoi de fichiers et de dossiers, téléchargement d'un dossier en ZIP |
| Accès | Jeton d'accès dans le lien, cadenas protégé par mot de passe pour les actions d'écriture, mode lecture seule |
| Supervision | Tableau de bord : mémoire, disques, appareils connectés, historique d'activité, blocage par adresse IP |
| Interface | Thème clair et sombre, adaptée au téléphone comme à l'ordinateur, textes en français |

## Prérequis

- Python 3 récent (développé avec Python 3.13). Linux, macOS, Windows, et aussi Android via Termux.
- Un navigateur moderne (Chrome, Firefox, Safari, Edge, Samsung Internet).
- Facultatif :
  - `ffmpeg` et `ffprobe` : miniatures et durées des vidéos, pochettes et tags audio. Sans eux, Biblio fonctionne,
    mais sans ces aperçus (Debian et Ubuntu : `sudo apt install ffmpeg`).
  - `node` : uniquement pour que les tests vérifient que les scripts assemblés sont du JavaScript valide.

## Installation

```bash
git clone https://github.com/styjii/biblio.git
cd biblio
cp .env.example .env
chmod 600 .env
```

Le dépôt contient tout ce qu'il faut : l'éditeur de texte (`editor.bundle.js`) et pdf.js (`legacy/`) sont fournis.

## Démarrage rapide

```bash
python3 server.py /chemin/vers/mon/dossier
```

Au démarrage, Biblio affiche les adresses à ouvrir :

```
Bibliothèque : /chemin/vers/mon/dossier
Configuration : /chemin/vers/biblio/.env
Local   : http://localhost:8088/?token=XXXXXXXXXXXXXXXX
Réseau  : http://192.168.1.20:8088/?token=XXXXXXXXXXXXXXXX
```

Ouvrir l'adresse « Réseau » depuis un autre appareil du même réseau. Le jeton est mémorisé dans un cookie : il
n'est plus nécessaire dans l'adresse ensuite. Le jeton est créé automatiquement au premier démarrage et écrit dans
le `.env`. **Gardez le lien privé** : il donne accès aux fichiers.

## Utilisation

```
python3 server.py [dossier] [-p PORT] [-r] [-e FICHIER_ENV] [-j DOSSIER_PDFJS]
```

| Option | Rôle | Défaut |
|---|---|---|
| `dossier` | Dossier à servir | dossier courant (ou `BIBLIO_DOCS`) |
| `-p`, `--port` | Port d'écoute | `8088` (ou `BIBLIO_PORT`) |
| `-r`, `--readonly` | Désactive toute écriture : édition, suppression, renommage, envoi | désactivé |
| `-e`, `--env` | Fichier `.env` à utiliser (ou `BIBLIO_ENV`) | `.env` à côté de `server.py` |
| `-j`, `--pdfjs` | Dossier contenant `legacy/web/viewer.html` (ou `BIBLIO_PDFJS`) | `legacy/` du projet |
| `-h`, `--help` | Aide | |

Exemples :

```bash
python3 server.py                               # sert le dossier courant sur le port 8088
python3 server.py ~/Documents -p 9000           # autre dossier, autre port
python3 server.py /mnt/ext0/films --readonly    # consultation seule
python3 server.py ~/Documents -e /etc/biblio.env
```

Arrêt : `Ctrl+C` (ou signal `SIGTERM`). L'historique d'activité et les positions de lecture sont alors enregistrés.

### Lancer en service (systemd)

```ini
# ~/.config/systemd/user/biblio.service
[Unit]
Description=Biblio

[Service]
ExecStart=/usr/bin/python3 /chemin/vers/biblio/server.py /chemin/vers/mon/dossier
Restart=on-failure

[Install]
WantedBy=default.target
```

```bash
systemctl --user enable --now biblio
```

## Configuration

La configuration se fait dans le fichier `.env` (copie de `.env.example`). Format : une ligne `CLE=valeur`, sans
commentaire en fin de ligne, guillemets facultatifs. **Une variable d'environnement du même nom l'emporte** sur le
fichier.

| Variable | Rôle | Défaut |
|---|---|---|
| `BIBLIO_TOKEN` | Jeton d'accès (lien `?token=…`). Absent : généré et écrit dans le `.env` au premier démarrage | généré |
| `BIBLIO_PASSWORD` | Mot de passe du cadenas : renommer, supprimer, envoyer des fichiers. Absent ou vide : ces actions sont désactivées | aucun |
| `BIBLIO_MAX_UPLOAD_MB` | Taille maximale d'un fichier envoyé, en Mo (`0` = illimitée) | `4096` |
| `BIBLIO_DASHBOARD_PASSWORD` | Mot de passe du tableau de bord. Absent : `BIBLIO_PASSWORD` est utilisé ; sans aucun des deux, le tableau de bord est désactivé | `BIBLIO_PASSWORD` |
| `BIBLIO_DISKS` | Volumes affichés dans le tableau de bord, `chemin=Nom` séparés par des points-virgules | `/mnt/ext0=Disque externe;/sdcard=Stockage interne` |
| `BIBLIO_DOCS` | Dossier servi quand aucun n'est passé en argument | dossier courant |
| `BIBLIO_PORT` | Port d'écoute | `8088` |
| `BIBLIO_ENV` | Chemin du fichier `.env` | `.env` du projet |
| `BIBLIO_PDFJS` | Dossier contenant pdf.js | `legacy/` du projet |

Données de fonctionnement, enregistrées dans `~/.config/biblio/` (ou `$XDG_CONFIG_HOME/biblio/`) :

| Fichier | Contenu |
|---|---|
| `blocked_devices.json` | Appareils bloqués depuis le tableau de bord |
| `history.json` | Historique d'activité du tableau de bord |
| `playback.json` | Dernière position de lecture de chaque appareil (conservée 180 jours) |

Les miniatures, durées, tags et pochettes sont mises en cache dans `~/.cache/biblio/` (ou `$XDG_CACHE_HOME/biblio/`).

## Sécurité

Biblio est conçu pour un réseau local de confiance. Voici ce qu'il met en place :

- **Jeton d'accès** : sans lui, toute page répond « verrouillé ». Il est comparé en temps constant et conservé dans un
  cookie `HttpOnly` et `SameSite=Strict`.
- **Cadenas** : renommer, supprimer, créer, enregistrer et envoyer exigent d'avoir déverrouillé l'accès avec
  `BIBLIO_PASSWORD`. Le mot de passe n'est demandé qu'au déverrouillage ; la session déverrouillée vit en mémoire et
  disparaît au redémarrage du serveur.
- **Anti force brute** : 5 essais de mot de passe par adresse IP, puis blocage de 60 secondes ; chaque échec est
  ralenti.
- **Requêtes d'écriture** : réservées aux requêtes `POST` portant l'en-tête `X-Requested-With: biblio` et le cookie
  d'accès.
- **Envoi** : un jeton d'envoi à durée limitée (15 minutes, renouvelé pendant l'envoi) est délivré après
  déverrouillage ; l'envoi écrit en flux et laisse toujours 64 Mo d'espace disque libre.
- **Chemins** : tout chemin est résolu sous le dossier servi ; les `..` et chemins absolus sont refusés. Le fichier
  `.env` n'est jamais lisible, modifiable ni inclus dans un ZIP, et le dossier qui contient le programme ou le `.env`
  ne peut être ni supprimé ni déplacé.
- **Contenu servi** : les fichiers texte et web sont envoyés avec `Content-Security-Policy: sandbox`. Les aperçus de
  pages web sont isolés dans un bac à sable (`/s/<jeton>/…`).
- **Mode lecture seule** (`-r`) : aucune écriture possible, quel que soit le mot de passe.
- **Appareils** : le tableau de bord permet de bloquer une adresse IP.

Recommandations :

- N'exposez pas Biblio directement sur Internet : le serveur parle HTTP sans chiffrement. Si vous devez l'ouvrir à
  distance, placez-le derrière un VPN ou un proxy inverse HTTPS.
- Protégez le `.env` : `chmod 600 .env` (Biblio avertit au démarrage si le fichier est lisible par d'autres).
- Ne versionnez jamais le `.env` (le `.gitignore` fourni l'exclut).
- Choisissez des mots de passe longs et différents pour le cadenas et le tableau de bord.

## Guide des fonctionnalités

### Navigation

- **Cartes** par type de fichier (vidéo, audio, image, PDF, texte, code, web, archive…), avec miniatures pour les
  vidéos et aperçu animé au survol (souris) ou à l'appui maintenu (tactile).
- **Fil d'Ariane** pour remonter dans l'arborescence.
- **Recherche** dans le dossier courant (champ « Rechercher dans ce dossier… »).
- **Filtres** par catégorie de fichiers, et interrupteur pour afficher ou masquer les fichiers cachés.
- **Tri** par nom (ordre naturel), date, taille, durée ou type, croissant ou décroissant. Le choix est mémorisé dans le
  navigateur. Les valeurs inconnues passent toujours en dernier.
- **Menu d'actions** de chaque élément : ouvrir, éditer, renommer, supprimer, télécharger. Un dossier se télécharge en
  archive ZIP construite au fil de l'envoi (le `.env` en est exclu, les raccourcis vers des dossiers ne sont pas suivis).

### Lecture et édition de texte

Basés sur CodeMirror (bundle `editor.bundle.js`).

- **Lecture seule** (`/view`) et **édition** (`/edit`), avec coloration selon le type de fichier.
- **Mode Vim** activable ou non (bouton « Vim »), avec une barre de touches d'aide (bouton « Touches »).
- Numéros de ligne, retour à la ligne, taille du texte de 10 à 26 px, recherche dans le fichier.
- Ligne d'état : position du curseur, nombre de lignes, langage détecté, indicateur de modifications non enregistrées.
- Limites : 2 Mo pour la lecture et l'édition, 5 Mo pour l'enregistrement.
- Les préférences (taille, retour à la ligne, numéros, Vim) sont mémorisées dans le navigateur.

Types reconnus comme texte : `.txt`, `.srt`, `.vtt`, `.csv`, `.log`, `.ini`, `.conf`, `.tex`, `.patch`… ; comme code :
`.py`, `.js`, `.ts`, `.java`, `.c`, `.cpp`, `.rs`, `.go`, `.php`, `.rb`, `.sh`, `.sql`, `.css`, `.json`, `.yml`, `.toml`,
`.xml`, `.md`, `.ipynb`… (voir `app/filetypes.py`).

### Aperçu Markdown

Le rendu se fait dans le navigateur, sans dépendance (`frontend/js/markdown/`).

- Titres, listes, tableaux, citations, code, liens de référence, notes de bas de page, en-tête YAML.
- Coloration syntaxique légère des blocs de code, bouton « Copier », agrandissement des images.
- Encadrés d'alerte (information, astuce, attention, danger).
- HTML brut filtré : seules les balises et attributs sûrs sont conservés, rien ne s'exécute.
- Liens relatifs résolus dans la bibliothèque : les fichiers voisins s'ouvrent avec le bon lecteur.
- **Sommaire** (jusqu'au niveau 4) : panneau fixe sur grand écran, tiroir sur petit écran (touche `T`), repère de la
  section courante.
- Barre de progression, temps de lecture estimé, position de lecture mémorisée.
- Réglages : taille du texte (14 à 26 px), police avec ou sans empattement, impression.

### Aperçu de pages web

Les fichiers `.html`, `.htm`, `.xhtml` et `.svg` s'ouvrent en aperçu dans une zone isolée, avec les liens et ressources
du dossier. Un bouton ouvre la page dans un nouvel onglet ; un autre affiche le code source.

### Lecteur vidéo (`/watch`)

Lecteur professionnel (conventions de YouTube, Video.js et Plyr) : les commandes natives du navigateur sont remplacées
par une interface dessinée par `frontend/js/watch/03-interface-du-lecteur.js` (classe `PlayerUI`) et
`frontend/css/main/12-lecteur-youtube.css`. Sans JavaScript, l'attribut `controls` de la balise `<video>` garde les
commandes natives.

Formats : `.mp4`, `.webm`, `.mkv`, `.mov`, `.m4v`, `.avi`, `.ogv` (selon la prise en charge du navigateur).

- **Liste de lecture** : les vidéos du dossier, avec lecture automatique de la suivante, lecture aléatoire et
  répétition.
- **Sous-titres** : les fichiers `.srt` placés à côté de la vidéo sont détectés et convertis en WebVTT à la volée ;
  ils ne sont pas listés dans la navigation. Un bouton « sous-titres » (touche `C`), à gauche du bouton des paramètres,
  les active ou les désactive : il n'apparaît que si la vidéo a au moins une piste, et reste marqué tant qu'une piste
  est affichée. Le choix de la piste se fait dans le menu des paramètres, et la dernière langue choisie est mémorisée.
- **Reprise** : la dernière position de chaque vidéo est mémorisée côté serveur, par appareil (`ResumeTracker`,
  `03-position.js`) ; `PlaybackGuard` (`03-reprise-apres-incident.js`) reprend la lecture après une coupure du réseau.
- **Style** : tout se règle avec les jetons `--vp-…` en tête de `12-lecteur-youtube.css` (accent, tailles, verre
  dépoli, rayon, animation) ; infobulles au survol, gros bouton de lecture au centre en pause (souris), aperçu du point
  visé sur la barre de position, menus animés, interrupteurs.
  Volume : bouton muet en carré arrondi d'accent tant que le curseur est ouvert, curseur à la partie réglée en accent et
  pastille blanche, identiques à toutes les tailles (ouvert au survol sur grand écran, toujours visible au doigt ou en
  lecteur étroit) ; les barres de position et de volume ont le même rail. Le menu des paramètres ne défile jamais : ses
  lignes se resserrent, puis passent sur deux colonnes si le lecteur est petit (téléphone en paysage, par exemple).
- **Zone fixe (mobile, portrait)** : le lecteur, ses informations (titre, dossier, taille) et l'en-tête de la liste
  (« Dans ce dossier ») restent collés en haut de l'écran ; seules les lignes de la liste défilent dessous. Un
  glissement du doigt commencé dans cette zone ne fait défiler ni la liste ni la page (hors gestes du lecteur : volume,
  position). La barre de défilement de la page est masquée dans ce mode, pour ne pas se dessiner par-dessus le lecteur.
- **Commandes** : la barre ne porte que lecture/pause, précédente/suivante, ±10 s, volume, durée, sous-titres (si la vidéo en a), paramètres, mode
  cinéma (grand écran), image dans l'image et plein écran, quelle que soit la taille du lecteur. Tout ce que contient le
  menu des paramètres (lecture automatique, aléatoire, répétition, vitesse de 0,25× à 2×, sous-titres, orientation,
  téléchargement) n'est jamais répété dans la barre, à une exception près : le bouton de sous-titres, qui active ou
  désactive la piste choisie dans le menu.
- **Barre de position** : plage chargée, bulle de temps au survol, glissement à la souris ou au doigt, redessinée à
  chaque image pendant la lecture. Les commandes se masquent après 3 s en lecture et réapparaissent au mouvement.
- **Tactile** : tape = afficher ou masquer les commandes, double tape à gauche ou à droite = -10 s ou +10 s (les sauts
  s'additionnent), double tape au centre = lecture ou pause ; gros boutons précédente, lecture et suivante au centre.
  Aucun glissement du doigt (volume, position) : le volume se règle avec le curseur du lecteur, la position avec la
  barre de position.
- **Verrouillage** : le bouton cadenas (en haut à droite, touche `V`) désactive boutons, gestes et clavier ; il devient
  alors un bouton de déverrouillage, affiché 3 s après chaque tape sur l'écran. La lecture continue et le verrouillage
  suit la lecture automatique vers la vidéo suivante.
- **Responsive** : la taille des commandes suit la largeur du lecteur (requêtes de conteneur), donc aussi en plein
  écran ; le plein écran est celui du conteneur (la vidéo et ses commandes). La couleur de la barre de position est la
  variable `--vp-accent`.

Raccourcis clavier :

| Touche | Action |
|---|---|
| `K` ou `Espace` | Lecture / pause |
| `J` / `L` | -10 s / +10 s |
| `←` / `→` | -5 s / +5 s |
| `↑` / `↓` | Volume |
| `0` à `9` | Aller à 0 % … 90 % de la vidéo |
| `N` / `P` | Vidéo suivante / précédente |
| `S` | Lecture aléatoire |
| `R` | Répétition |
| `<` / `>` | Vitesse moins / plus rapide |
| `M` | Muet |
| `C` | Sous-titres |
| `T` | Mode cinéma |
| `I` | Image dans l'image |
| `F` | Plein écran |
| `V` | Verrouiller / déverrouiller |

### Lecteur audio (`/listen`)

Formats : `.mp3`, `.wav`, `.ogg`, `.m4a`, `.flac`, `.opus`, `.aac`.

- Liste de lecture du dossier avec filtre (touche `/`), pochettes et tags (titre, artiste, album) lus par `ffmpeg`.
- Lecture aléatoire, répétition (désactivée, toutes les pistes, une piste), vitesse de lecture, volume, muet.
- Reprise de la dernière position de chaque piste, par appareil.
- Touches multimédia du téléphone ou du clavier et écran de verrouillage (Media Session).

| Touche | Action |
|---|---|
| `K` ou `Espace` | Lecture / pause |
| `N` / `P` | Piste suivante / précédente |
| `J` / `L` | -10 s / +10 s |
| `←` / `→` | -5 s / +5 s |
| `↑` / `↓` | Volume |
| `0` à `9` | Aller à 0 % … 90 % de la piste |
| `S` / `R` | Lecture aléatoire / répétition |
| `<` ou `,` / `>` ou `.` | Vitesse moins / plus rapide |
| `M` | Muet |
| `/` | Filtrer la liste |

### PDF

Les PDF s'ouvrent dans pdf.js (`legacy/`). Si pdf.js est introuvable, le lecteur du navigateur prend le relais. Le
chemin de pdf.js se règle avec `-j` ou `BIBLIO_PDFJS`.

### Gestion des fichiers

Toutes ces actions exigent d'avoir déverrouillé l'accès avec le cadenas, et sont absentes en mode lecture seule.

- **Nouveau fichier** et **nouveau dossier**.
- **Renommer** et **supprimer** (fichiers et dossiers), avec confirmation.
- **Envoyer** des fichiers ou des dossiers entiers, avec option d'écrasement. L'envoi est confié à un `SharedWorker` :
  il se poursuit en arrière-plan quand on change de dossier ou de page, et toutes les pages ouvertes affichent le
  panneau de progression. Sans `SharedWorker`, l'envoi tourne dans la page qui l'a lancé.
- **Télécharger** un fichier ou un dossier (ZIP).

### Tableau de bord (`/dashboard`)

Activé si `BIBLIO_DASHBOARD_PASSWORD` ou `BIBLIO_PASSWORD` est défini.

- **Mémoire** : utilisée, libre, totale, avec jauge.
- **Disques** : capacité et occupation des volumes de `BIBLIO_DISKS`.
- **Appareils connectés** : adresse IP, navigateur, dernier passage, nombre de requêtes.
- **Historique d'activité** par appareil : navigation, lecture de texte, édition, vidéo, audio, PDF, web, images,
  téléchargements, avec courbes sur plusieurs durées.
- **Blocage** et déblocage d'un appareil par adresse IP.

## Architecture

```
server.py                 point d'entrée (ne contient que l'appel à app.cli.main)
editor.bundle.js          éditeur de texte (bundle JavaScript tiers, servi sur /static/editor.js)
legacy/                   pdf.js (visionneuse PDF)
app/                      code Python
frontend/                 tout le front-end : CSS, JS et HTML
tests/                    tests
.env.example              modèle de configuration
```

### Routes

| Route | Rôle |
|---|---|
| `/` | Navigation (`?folder=…`) |
| `/view`, `/edit` | Lecture et édition de texte |
| `/preview` | Aperçu Markdown ou page web |
| `/watch`, `/listen` | Lecteurs vidéo et audio |
| `/pdf`, `/docs/…` | PDF |
| `/raw`, `/zip` | Contenu brut, téléchargement, archive d'un dossier |
| `/s/<jeton>/…` | Pages web servies en bac à sable |
| `/thumb`, `/meta`, `/cover`, `/sub` | Miniatures, métadonnées, pochettes, sous-titres |
| `/progress` | Position de lecture (GET et POST) |
| `/save`, `/delete`, `/rename`, `/mkdir` | Écriture (POST) |
| `/upload-auth`, `/upload` | Jeton d'envoi, envoi en flux (POST) |
| `/unlock`, `/lock`, `/lock-state` | Cadenas |
| `/dashboard`, `/dashboard/data`, `/dashboard/history`, `/dashboard/block`, `/dashboard/unblock` | Tableau de bord |

### `app/` — Python

| Module | Rôle |
|---|---|
| `cli.py` | options de la ligne de commande, configuration, démarrage |
| `config.py` | réglages (dossier servi, jeton, mots de passe, limites, chemins), sécurité (`PasswordGuard`, `TicketStore`, `SessionStore`, `PathGuard`) |
| `handler.py` | `FileHandler` : assemble les routes, répartit GET / POST |
| `routes/` | une famille de routes par fichier : `browse`, `viewer`, `player`, `progress`, `serve`, `edit`, `upload`, `auth`, `dashboard` (+ `base` : envoi des réponses, cookies) |
| `views/` | briques HTML : `layout` (page, barre du haut, messages), `cards` (cartes de fichiers), `dashboard` |
| `devices.py` | appareils connectés, blocage par IP, historique d'activité |
| `playback.py` | dernière position de lecture de chaque appareil |
| `media.py`, `sysinfo.py` | miniatures, durées, tags, sous-titres (ffmpeg) ; mémoire et disques |
| `filesystem.py`, `filetypes.py`, `utils.py`, `envfile.py`, `icons.py` | accès disque, types de fichiers, utilitaires, `.env`, icônes SVG |
| `templating.py`, `assets.py` | moteur de gabarits ; chargement des CSS/JS/HTML de `frontend/` |

Les dépendances vont toujours dans le même sens (`config` → services → `views` → `routes` → `handler` → `cli`) :
aucun import circulaire.

**Règle importante** : les réglages renseignés au démarrage (`ROOT`, `TOKEN`, `PASSWORD`, `READONLY`…) se lisent avec
`config.ROOT`, jamais avec `from app.config import ROOT` (la valeur serait figée au chargement du module).

### `frontend/` — HTML, CSS, JavaScript

```
frontend/
  templates/   gabarits HTML (layout/, components/, browse/, viewer/, player/, dashboard/, pages/, partials/)
  css/         main/ (thèmes : base, barre du haut, menu…), markdown.css, dashboard.css, listen.css
  js/          un script par page ; les gros sont découpés par fonctionnalité (browse/, markdown/, dashboard/, listen/, watch/, transfers/)
```

Les fichiers sont lus au démarrage (`app/assets.py`) puis insérés dans les pages : le navigateur ne fait aucune requête
supplémentaire. **Après une modification du front-end, relancer le serveur.**

- **Dossier de scripts ou de styles** (`js/browse/`, `css/main/`…) : les fichiers `NN-nom` sont concaténés dans l'ordre
  alphabétique. Pour les scripts, ils forment *un seul bloc* : le serveur les enveloppe dans une fonction anonyme
  (`asset(..., wrap=True)`), `00-init.js` contient les variables partagées. Chaque fichier reste un JavaScript valide
  pris isolément ; le `jsconfig.json` du dossier indique à l'éditeur (tsserver) que ces fichiers forment un seul
  script.
- **Gabarits** (`templates/*.html`), syntaxe volontairement minimale :
  - `{{ nom }}` : valeur insérée **telle quelle** (échapper avec `html.escape` côté Python tout ce qui vient d'un nom de
    fichier, d'un paramètre, etc.) ;
  - `{{ icon nom taille }}` : icône SVG ;
  - `{# commentaire #}` : retiré au rendu.

  Les sauts de ligne et l'indentation sont supprimés au rendu : on écrit un gabarit lisible sans changer le HTML. Pour
  garder une espace entre deux éléments, la mettre sur la même ligne.

### Préférences mémorisées dans le navigateur

Stockées dans le `localStorage` : tri de la liste (`fl:sort`), taille du texte (`fl:fs`), retour à la ligne (`fl:wrap`),
numéros de ligne (`fl:num`), mode Vim (`fl:vim`), barre de touches (`fl:keys`), affichage des fichiers cachés
(`fl:hidden`), thème clair ou sombre (`theme`).

## Développement

### Lancer les tests

```bash
python3 -m unittest discover -s tests -t .
```

Les tests vérifient notamment que chaque appel `render(…)` fournit exactement les variables du gabarit, qu'aucun
gabarit n'est orphelin, que le comportement mobile du lecteur vidéo (zone fixe, barre de défilement) est bien cantonné
à son mode, et que les scripts assemblés sont du JavaScript valide (si `node` est installé).

### Ajouter ou modifier une page

1. Écrire le gabarit dans `frontend/templates/…` ; le CSS et le JS associés dans `frontend/css` et `frontend/js`.
2. Déclarer les constantes dans `app/assets.py` (`MA_PAGE_JS = asset("js/ma_page.js")`).
3. Dans une route (`app/routes/…`) : `render("ma/page", valeur=…)`, entourée de `doc_open(…)` et `doc_close(…)`.
4. Ajouter la route dans `FileHandler.do_GET` (`app/handler.py`).

### Conventions

- Code, commentaires et interface en français ; bibliothèque standard uniquement côté Python.
- Tout ce qui vient d'un nom de fichier ou d'un paramètre est échappé avant d'être inséré dans une page.
- Toute écriture passe par `config.paths` (chemins sûrs) et exige l'accès déverrouillé.
- Le comportement mobile du lecteur vidéo ne doit pas modifier le mode PC.

## Dépannage

| Symptôme | Cause probable et solution |
|---|---|
| Page « verrouillé » | Ouvrir le lien complet avec `?token=…` affiché au démarrage |
| Impossible de joindre le serveur depuis un autre appareil | Même réseau requis ; vérifier le pare-feu et le port (`-p`) |
| Suppression, renommage ou envoi refusés | `BIBLIO_PASSWORD` absent du `.env`, mode lecture seule (`-r`), ou accès verrouillé (utiliser le cadenas) |
| Pas de miniatures ni de durées pour les vidéos | Installer `ffmpeg` |
| Les PDF s'ouvrent avec le lecteur du navigateur | pdf.js introuvable : vérifier `legacy/` ou l'option `-j` |
| Lecture et édition de texte indisponibles | `editor.bundle.js` absent à côté de `server.py` |
| « Trop d'essais » | Cinq mots de passe erronés : attendre 60 secondes |
| Une modification du front-end n'apparaît pas | Relancer le serveur (les fichiers sont lus au démarrage) |
| Tableau de bord désactivé | Définir `BIBLIO_DASHBOARD_PASSWORD` ou `BIBLIO_PASSWORD` |
| Avertissement sur les droits du `.env` | `chmod 600 .env` |

## Licence et composants tiers

Biblio est distribué sous [licence MIT](LICENSE) : vous pouvez l'utiliser, le copier, le modifier et le redistribuer,
à condition de conserver la mention de copyright et le texte de la licence.

Les composants tiers fournis avec le projet restent soumis à leur propre licence :

| Composant | Usage | Licence |
|---|---|---|
| [pdf.js](https://mozilla.github.io/pdf.js/) 4.10 (`legacy/`) | Visionneuse PDF | Apache 2.0 (`legacy/LICENSE`) |
| [CodeMirror](https://codemirror.net/) et son mode Vim (`editor.bundle.js`) | Éditeur de texte | licences d'origine de ces projets |
