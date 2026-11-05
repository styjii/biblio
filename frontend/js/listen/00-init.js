/* Lecteur audio : liste des pistes, ordre de lecture, affichage, reprise de la position, boutons et clavier.
   Les fichiers de ce dossier forment un seul script (concaténés dans l'ordre) : celui-ci ouvre la fonction, le dernier la ferme. */
(() => {
  const cfg = window.LCFG;
  const tracks = cfg.tracks;                                 // [{f: chemin, q: chemin encodé, n: nom, e: extension}]
  const icons = window.LICO ?? {};
  const $ = (id) => document.getElementById(id);
  const audio = $('l-audio');

  /** Préférences conservées d'une piste à l'autre (clés « al:… »). */
  const prefs = {
    get(key, fallback) { try { return localStorage.getItem(`al:${key}`) ?? fallback; } catch { return fallback; } },
    set(key, value) { try { localStorage.setItem(`al:${key}`, value); } catch { /* préférence non mémorisée */ } },
  };

  /** Secondes -> « m:ss » ou « h:mm:ss ». */
  const formatTime = (seconds) => {
    const s = Number.isFinite(seconds) && seconds > 0 ? Math.floor(seconds) : 0;
    const h = Math.floor(s / 3600);
    const m = Math.floor(s % 3600 / 60);
    return `${h ? `${h}:${String(m).padStart(2, '0')}` : m}:${String(s % 60).padStart(2, '0')}`;
  };

  /** Message sous les commandes : `keep` = il reste (erreurs) ; sinon il s'efface seul. */
  const say = (() => {
    let timer = 0;
    return (text = '', keep = false) => {
      clearTimeout(timer);
      $('l-msg').textContent = text;
      if (text && !keep) timer = setTimeout(() => { $('l-msg').textContent = ''; }, 4000);
    };
  })();

  const setIcon = (button, name) => { button.innerHTML = icons[name] ?? ''; };
  const isReady = () => Number.isFinite(audio.duration) && audio.duration > 0;
  const RATES = [0.75, 1, 1.25, 1.5, 1.75, 2];
