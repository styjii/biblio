/* Lecteur vidéo : ordre de lecture, volume et vitesse, reprise de la position, boutons et clavier.
   Les fichiers de ce dossier forment un seul script (concaténés dans l'ordre) : le serveur les enveloppe dans une fonction anonyme (portée commune, voir app/assets.py). */
const cfg = window.WCFG;
const {items, index} = cfg;                              // vidéos du dossier [{f: chemin, u: adresse}], position de la vidéo ouverte
const icons = window.WICO ?? {};
const $ = (id) => document.getElementById(id);
const video = $('player');

/** Préférences conservées d'une vidéo à l'autre (clés « vl:… »). */
const prefs = {
  get(key, fallback) { try { return localStorage.getItem(`vl:${key}`) ?? fallback; } catch { return fallback; } },
  set(key, value) { try { localStorage.setItem(`vl:${key}`, value); } catch { /* préférence non mémorisée */ } },
};

/** Message court affiché en haut du lecteur, donc visible aussi en plein écran (s'efface seul). */
const say = (() => {
  let timer = 0;
  return (text = '') => {
    clearTimeout(timer);
    $('vp-toast').textContent = text;
    if (text) timer = setTimeout(() => { $('vp-toast').textContent = ''; }, 3500);
  };
})();

const setIcon = (button, name) => { button.innerHTML = icons[name] ?? ''; };
const play = () => video.play()?.catch(() => {});      // lecture interrompue ou refusée : sans conséquence

const END_GUARD = 1;                                     // s : un saut ne mène jamais jusqu'à la toute fin (la vidéo se terminerait d'un coup, et « lecture » la relancerait à 0:00)
const SEEK_DELAY = 120;                                  // ms : des sauts rapprochés sont regroupés en un seul déplacement (un seul chargement de la vidéo, pas une rafale)

/** Saut relatif (±10 s…). Les appuis rapprochés s'additionnent, mais le lecteur ne bouge qu'une fois. */
const seekBy = (() => {
  let target = null;
  let timer = 0;
  return (seconds) => {
    if (!Number.isFinite(video.duration)) return;        // durée inconnue : impossible de borner le saut
    const from = target ?? video.currentTime;
    const limit = Math.max(0, video.duration - END_GUARD);
    target = seconds > 0 ? Math.max(from, Math.min(limit, from + seconds)) : Math.max(0, from + seconds);
    clearTimeout(timer);
    timer = setTimeout(() => { video.currentTime = target; target = null; }, SEEK_DELAY);
  };
})();
