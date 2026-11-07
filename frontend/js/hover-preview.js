/* Aperçu vidéo sur les vidéos (cartes de la navigation, lignes de la liste du lecteur) : un court extrait est lu en boucle,
   sans le son, dans la vignette, tant que la souris survole la vidéo ou qu'un doigt reste appuyé dessus. La zone sensible est
   TOUTE la carte (vignette, titre, informations), pas seulement l'image. Dès que le curseur ou le doigt quitte la carte,
   la vidéo est arrêtée et retirée : la vignette retrouve son état initial.
   - souris : l'aperçu démarre après un court survol (pas pendant qu'on traverse la liste) ;
   - tactile : appui maintenu (un simple tape ouvre toujours la vidéo, un défilement n'en lance aucun) ;
   - jamais pour la vidéo en cours de lecture. */
(() => {
  const ITEM = '.vcard,.row[data-f]';                    // la carte entière (navigation) ou la ligne (liste du lecteur)
  const THUMB = '.thumb,.rthumb';                        // la vignette, où l'extrait est affiché
  const HOVER_DELAY = 280;                               // ms de survol (souris) avant de lancer l'aperçu
  const HOLD_DELAY = 220;                                // ms d'appui (tactile) avant de lancer l'aperçu
  const CLIP = 6;                                        // s : durée de l'extrait lu en boucle
  const START_AT = 0.25;                                 // l'extrait commence à 25 % de la vidéo (le début est rarement parlant)

  let current = null;                                    // {item, thumb, video} : l'aperçu en cours (un seul à la fois)
  let timer = 0;                                         // lancement différé
  let lastType = 'mouse';                                // type du dernier pointeur : mouse | touch | pen
  let swallowClick = false;                              // l'appui maintenu ne doit pas ouvrir la vidéo au relâchement

  /** Arrête l'aperçu : la vidéo est vidée (la connexion est libérée) puis retirée, la vignette reprend son état initial. */
  const stop = () => {
    clearTimeout(timer);
    timer = 0;
    if (!current) return;
    const {thumb, video} = current;
    current = null;
    thumb.classList.remove('pv-live', 'pv-on');
    video.pause();
    video.removeAttribute('src');
    video.load();
    video.remove();
  };

  const start = (item) => {
    const thumb = item.querySelector(THUMB);
    if (!thumb || item.classList.contains('cur')) return;
    stop();
    const video = document.createElement('video');
    video.className = 'pv';
    video.muted = true;
    video.defaultMuted = true;
    video.loop = true;
    video.autoplay = true;
    video.controls = false;
    video.disablePictureInPicture = true;
    video.setAttribute('muted', '');                      // certains navigateurs mobiles ne lisent que si l'attribut est présent
    video.setAttribute('playsinline', '');
    video.preload = 'auto';

    let from = 0;
    let to = 0;                                          // extrait : de `from` à `to` (0 = vidéo courte, la boucle native suffit)
    video.addEventListener('loadedmetadata', () => {
      const {duration} = video;
      if (!Number.isFinite(duration) || duration <= CLIP * 2) return;
      from = Math.min(duration * START_AT, duration - CLIP - 1);
      to = from + CLIP;
      video.currentTime = from;
    }, {once: true});
    video.addEventListener('timeupdate', () => { if (to && video.currentTime >= to) video.currentTime = from; });
    video.addEventListener('playing', () => thumb.classList.add('pv-on'));
    video.addEventListener('error', stop);

    video.src = `/raw?f=${item.dataset.f}`;
    // Ordre du gabarit : .ph (icône), puis <img>, puis durée / barre / boutons. La vidéo se place juste après l'image (la dernière des
    // deux, pas la première : sinon l'image, positionnée plus tard dans la page, la recouvre) et reste sous la durée et les boutons.
    (thumb.querySelector('img') ?? thumb.querySelector('.ph'))?.after(video);
    if (!video.isConnected) thumb.prepend(video);
    thumb.classList.add('pv-live');
    current = {item, thumb, video};
    video.play()?.catch((err) => {
      if (err?.name !== 'AbortError') console.warn('Aperçu vidéo : lecture refusée', err);   // AbortError = arrêt volontaire
    });
  };

  const itemOf = (target) => target.closest?.(ITEM) ?? null;

  /* ----- souris : survol ----- */
  document.addEventListener('pointerover', (e) => {
    if (e.pointerType !== 'mouse') return;
    const item = itemOf(e.target);
    if (!item || item.contains(e.relatedTarget)) return;
    clearTimeout(timer);
    timer = setTimeout(() => start(item), HOVER_DELAY);
  });
  document.addEventListener('pointerout', (e) => {
    if (e.pointerType !== 'mouse') return;
    const item = itemOf(e.target);
    if (item && !item.contains(e.relatedTarget)) stop();
  });

  /* ----- tactile : appui maintenu ----- */
  document.addEventListener('pointerdown', (e) => {
    lastType = e.pointerType;
    if (e.pointerType === 'mouse') return;
    const item = itemOf(e.target);
    if (!item || e.target.closest('button')) return;      // le bouton « plus d'actions » garde son rôle
    clearTimeout(timer);
    timer = setTimeout(() => start(item), HOLD_DELAY);
  });
  const release = (e) => {
    if (e.pointerType === 'mouse') return;
    if (current && e.type === 'pointerup') {              // l'aperçu était lancé : le relâchement n'ouvre pas la vidéo
      swallowClick = true;
      setTimeout(() => { swallowClick = false; }, 500);
    }
    stop();
  };
  document.addEventListener('pointerup', release);
  document.addEventListener('pointercancel', release);   // le navigateur prend la main (défilement) : fin de l'aperçu
  document.addEventListener('pointermove', (e) => {      // le doigt glisse hors de la vignette
    if (e.pointerType === 'mouse' || !current) return;
    const {left, right, top, bottom} = current.item.getBoundingClientRect();
    if (e.clientX < left || e.clientX > right || e.clientY < top || e.clientY > bottom) stop();
  });
  document.addEventListener('click', (e) => {
    if (!swallowClick || !itemOf(e.target)) return;
    swallowClick = false;
    e.preventDefault();
    e.stopPropagation();
  }, true);
  document.addEventListener('dragstart', (e) => {         // l'appui long sur un lien ou une image peut lancer un glisser-déposer
    if (itemOf(e.target) && (current || timer)) e.preventDefault();   // (le navigateur annulerait alors l'appui, donc l'aperçu)
  });
  document.addEventListener('contextmenu', (e) => {      // l'appui long ne doit pas ouvrir le menu du navigateur (lien, image)
    if (lastType !== 'mouse' && itemOf(e.target) && (current || timer)) e.preventDefault();
  });

  /* ----- autres cas : défilement, onglet masqué, page quittée ----- */
  document.addEventListener('scroll', stop, {capture: true, passive: true});
  document.addEventListener('visibilitychange', () => { if (document.hidden) stop(); });
  window.addEventListener('pagehide', stop);
})();
