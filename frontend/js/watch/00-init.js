/* Lecteur vidéo : ordre de lecture, volume et vitesse, reprise de la position, boutons et clavier.
   Les fichiers de ce dossier forment un seul script (concaténés dans l'ordre) : celui-ci ouvre la fonction, le dernier la ferme. */
(() => {
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

  /** Message court sous les commandes (s'efface seul). */
  const say = (() => {
    let timer = 0;
    return (text = '') => {
      clearTimeout(timer);
      $('w-msg').textContent = text;
      if (text) timer = setTimeout(() => { $('w-msg').textContent = ''; }, 4000);
    };
  })();

  const setIcon = (button, name) => { button.innerHTML = icons[name] ?? ''; };
  const play = () => video.play()?.catch(() => {});      // lecture interrompue ou refusée : sans conséquence
  const seekBy = (seconds) => {
    video.currentTime = Math.max(0, Math.min(video.duration || 1e9, video.currentTime + seconds));
  };
