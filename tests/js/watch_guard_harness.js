// Exécute le script du lecteur vidéo (frontend/js/watch/*.js, concaténé comme le serveur le fait) avec une fausse page,
// un faux élément <video> relié à un faux réseau et une horloge simulée, puis affiche le résultat de chaque scénario en JSON.
const vm = require('vm'), fs = require('fs'), path = require('path');
const dir = path.join(__dirname, '..', '..', 'frontend', 'js', 'watch');
const code = '\n' + fs.readdirSync(dir).sort().map((f) => fs.readFileSync(path.join(dir, f), 'utf8')).join('');

/** Page factice : horloge simulée, réseau coupé / rétabli à volonté, vidéo de 600 s. */
function makeWorld({shuffle = false, startPaused = false} = {}) {
  let now = 0;
  let timers = [];
  let seq = 0;
  const net = {up: true, loads: 0};
  const listeners = (target) => {
    const map = {};
    target.addEventListener = (type, fn) => { (map[type] ??= []).push(fn); };
    target.emit = (type, ev = {}) => { for (const fn of [...(map[type] ?? [])]) fn({type, target, ...ev}); };
    // les écouteurs « once » (option {once: true}) sont retirés après usage par le script lui-même : on les simule
    const add = target.addEventListener;
    target.addEventListener = (type, fn, opts) => {
      if (opts?.once) { const wrapper = (e) => { map[type] = map[type].filter((f) => f !== wrapper); fn(e); }; add(type, wrapper); } else add(type, fn);
    };
  };
  const setTimeoutFake = (fn, ms = 0) => { const id = ++seq; timers.push({id, at: now + ms, fn}); return id; };
  const clearTimeoutFake = (id) => { timers = timers.filter((t) => t.id !== id); };
  const advance = (ms) => {
    const end = now + ms;
    for (;;) {
      const due = timers.filter((t) => t.at <= end).sort((a, b) => a.at - b.at || a.id - b.id)[0];
      if (!due) break;
      timers = timers.filter((t) => t !== due);
      now = Math.max(now, due.at);
      due.fn();
    }
    now = end;
  };

  const element = () => {
    const el = {textContent: '', innerHTML: '', value: '', checked: true, dataset: {}, style: {setProperty() {}},
      classList: {toggle() {}, add() {}, remove() {}, contains: () => false}, setAttribute() {}, blur() {}, focus() {},
      querySelector: () => null, querySelectorAll: () => [], append() {}, replaceChildren() {}, closest: () => null,
      getBoundingClientRect: () => ({left: 0, top: 0, width: 640, height: 360}), offsetWidth: 40, hidden: false};
    listeners(el);
    return el;
  };
  const elements = {};
  const video = element();
  Object.assign(video, {
    currentTime: 0, duration: NaN, paused: true, ended: false, seeking: false, readyState: 0, error: null,
    volume: 1, muted: false, playbackRate: 1, defaultPlaybackRate: 1, loop: false, autoplay: !startPaused, networkState: 0,
    play() {
      if (this.error) return Promise.reject(new Error('NotSupportedError'));   // lecteur en erreur : aucun événement, la promesse échoue
      this.paused = false;
      this.emit('play');
      if (this.readyState >= 3) this.emit('playing'); else this.emit('waiting');
      return Promise.resolve();
    },
    pause() { if (!this.paused) { this.paused = true; this.emit('pause'); } },
    load() {
      net.loads++;
      Object.assign(this, {error: null, currentTime: 0, duration: NaN, readyState: 0, paused: true, ended: false, networkState: 2});
      setTimeoutFake(() => {
        if (!net.up) { this.error = {code: 2}; this.networkState = 3; this.emit('error'); return; }
        Object.assign(this, {duration: 600, readyState: 4, networkState: 1});
        this.emit('loadedmetadata');
        this.emit('canplay');
        if (this.autoplay && this.paused) { this.paused = false; this.emit('play'); this.emit('playing'); }
      }, 50);
    },
  });
  Object.assign(video, {textTracks: [], buffered: {length: 0}, controls: true});
  video.parentElement = {offsetHeight: 225};
  elements.player = video;
  const doc = {visibilityState: 'visible', fullscreenElement: null, documentElement: {style: {setProperty() {}}},
    getElementById: (id) => (elements[id] ??= element()), querySelector: () => null, createElement: () => element()};
  listeners(doc);

  const win = {};
  listeners(win);
  const ctx = {
    window: win, document: doc, navigator: {onLine: true}, location: {href: '/watch?f=a.mp4'}, innerWidth: 500,
    setTimeout: setTimeoutFake, clearTimeout: clearTimeoutFake, Date: {now: () => now}, JSON, Math, Number, Object, Array, Map, Promise, String, Set,
    localStorage: {getItem: () => null, setItem() {}, removeItem() {}}, sessionStorage: {getItem: () => null, setItem() {}},
    matchMedia: () => ({matches: false}), requestAnimationFrame: (fn) => setTimeoutFake(fn, 16), screen: {},
    Progress: {get: async () => null, save() {}, done() {}, fmt: (s) => `${Math.floor(s)} s`},
  };
  ctx.addEventListener = win.addEventListener;      // le script écoute aussi bien `window.…` que les événements globaux
  win.WCFG = {key: 'k:a.mp4', folder: 'k:', index: 0, items: [{f: 'a.mp4', u: '/watch?f=a.mp4'}, {f: 'b.mp4', u: '/watch?f=b.mp4'}]};
  win.WICO = {};
  win.document = doc;
  win.navigator = ctx.navigator;
  vm.createContext(ctx);
  ctx.window.emit = ctx.window.emit;                 // (le contexte `window` est l'objet `win` ; `online` y est émis)
  // le script lit window.WCFG / window.WICO et utilise les globales document, navigator, location, setTimeout…
  vm.runInContext(code, ctx);

  /** La vidéo avance de `sec` secondes de lecture (si elle lit réellement). */
  const play = (sec) => {
    for (let i = 0; i < sec; i++) {
      if (video.paused || video.readyState < 3 || video.ended) break;
      video.currentTime += 1;
      video.emit('timeupdate');
      advance(1000);
    }
  };
  const dropNetwork = () => {
    net.up = false;
    ctx.navigator.onLine = false;
    win.emit('offline');
  };
  const restoreNetwork = (event = true) => {
    net.up = true;
    ctx.navigator.onLine = true;
    if (event) win.emit('online');
  };
  /** Coupure réseau pendant la lecture : la mémoire tampon est vide, le lecteur attend des données. */
  const stall = () => { video.readyState = 1; video.emit('waiting'); };
  const settle = (ms) => advance(ms);
  return {video, net, ctx, win, doc, advance, play, dropNetwork, restoreNetwork, stall, settle, msg: () => elements['w-msg'].textContent};
}

/** Lecture démarrée normalement jusqu'à `at` secondes. */
function started(world, at = 120) {
  const {video} = world;
  video.load();
  world.advance(100);                  // métadonnées reçues, lecture lancée (autoplay)
  video.currentTime = 0;
  world.play(at);
  return world;
}

const out = {};

// 1. Coupure longue : trois rechargements ratés d'affilée, puis le réseau revient (événement « online » + retour sur la page)
{
  const w = started(makeWorld());
  w.dropNetwork();
  w.stall();
  w.advance(25000);                    // 20 s d'attente, puis les rechargements ratés
  w.advance(120000);                   // le Wi-Fi reste coupé deux minutes de plus
  const before = {error: !!w.video.error, paused: w.video.paused};
  w.restoreNetwork();
  w.doc.visibilityState = 'visible';
  w.doc.emit('visibilitychange');
  w.advance(1000);
  out.coupure_longue = {before, paused: w.video.paused, error: !!w.video.error, time: w.video.currentTime, playing: !w.video.paused && w.video.readyState >= 3};
}

// 2. Réseau rétabli sans aucun événement « online » (navigateur qui ne le signale pas) : la reprise doit venir toute seule
{
  const w = started(makeWorld());
  w.dropNetwork();
  w.stall();
  w.advance(25000);
  w.advance(60000);
  w.restoreNetwork(false);
  w.advance(20000);
  out.sans_evenement = {paused: w.video.paused, error: !!w.video.error, time: w.video.currentTime};
}

// 3. Connexion « morte » sans erreur (aucune donnée, aucun événement d'erreur) puis retour du réseau : reprise immédiate, sans attendre 20 s
{
  const w = started(makeWorld());
  w.dropNetwork();
  w.stall();
  w.advance(2000);
  w.restoreNetwork();
  w.advance(200);
  out.connexion_morte = {paused: w.video.paused, error: !!w.video.error, time: w.video.currentTime, ready: w.video.readyState >= 3};
}

// 4. Vidéo mise en pause par l'utilisateur avant la coupure : elle ne doit pas repartir toute seule
{
  const w = started(makeWorld());
  w.video.pause();
  w.video.error = {code: 2};
  w.video.emit('error');
  w.advance(5000);
  w.restoreNetwork();
  w.advance(1000);
  out.pause_respectee = {paused: w.video.paused, error: !!w.video.error, time: w.video.currentTime};
}

// 5. Fin de vidéo hors connexion : la suivante n'est ouverte qu'au retour du réseau
{
  const w = started(makeWorld());
  w.dropNetwork();
  w.video.currentTime = 599.9;
  w.video.ended = true;
  w.video.paused = true;
  w.video.emit('ended');
  const during = w.ctx.location.href;
  w.restoreNetwork();
  out.suivante_hors_connexion = {during, after: w.ctx.location.href};
}

// 6. Fin de vidéo avec réseau : la suivante s'ouvre aussitôt
{
  const w = started(makeWorld());
  w.video.currentTime = 599.9;
  w.video.ended = true;
  w.video.paused = true;
  w.video.emit('ended');
  out.suivante_en_ligne = {href: w.ctx.location.href};
}

// 7. Erreur de décodage répétée en ligne (fichier abîmé) : on n'insiste pas à l'infini
{
  const w = started(makeWorld());
  const before = w.net.loads;
  const origLoad = w.video.load.bind(w.video);
  w.video.load = function () { origLoad(); };       // chaque rechargement réussit, puis la lecture échoue au même endroit
  for (let i = 0; i < 12; i++) {
    w.video.error = {code: 3};
    w.video.emit('error');
    w.advance(20000);
    w.video.emit('timeupdate');
  }
  out.fichier_abime = {loads: w.net.loads - before};
}

// 8. Page rouverte au premier plan alors que le lecteur est resté en erreur (réseau déjà revenu)
{
  const w = started(makeWorld());
  w.dropNetwork();
  w.stall();
  w.advance(300000);
  w.restoreNetwork(false);
  w.doc.visibilityState = 'visible';
  w.doc.emit('visibilitychange');
  w.advance(200);
  out.retour_sur_la_page = {paused: w.video.paused, error: !!w.video.error, time: w.video.currentTime};
}

// 9. Reprise lente (saut loin dans un gros fichier, disque ou liaison lents) : les données arrivent au compte-gouttes pendant 2 minutes.
//    La vidéo ne doit JAMAIS être rechargée (ce serait repartir de zéro, en boucle), même avec un retour du réseau ou de l'onglet.
{
  const w = started(makeWorld());
  const loads = w.net.loads;
  w.video.currentTime = 3123;
  w.video.readyState = 1;
  w.video.seeking = true;
  w.video.emit('seeking');
  w.video.emit('waiting');
  for (let i = 0; i < 24; i++) {
    w.advance(5000);
    w.video.emit('progress');
    if (i === 6) w.win.emit('online');                                      // changement de réseau pendant le chargement
    if (i === 12) { w.doc.emit('visibilitychange'); w.win.emit('pageshow'); }
  }
  const reloaded = w.net.loads - loads;
  w.video.seeking = false;
  w.video.readyState = 4;
  w.video.emit('seeked');
  w.video.emit('canplay');
  w.video.emit('playing');
  w.play(5);
  out.reprise_lente = {reloaded, paused: w.video.paused, time: w.video.currentTime};
}

// 10. Réseau qui change (événement « online ») pendant une lecture normale : aucun rechargement.
{
  const w = started(makeWorld());
  const loads = w.net.loads;
  w.win.emit('online');
  w.doc.emit('visibilitychange');
  w.win.emit('pageshow');
  w.play(10);
  out.online_en_lecture = {reloaded: w.net.loads - loads, paused: w.video.paused, time: w.video.currentTime};
}

// 11. Silence complet du flux pendant plus de 30 s (connexion morte) : là, et seulement là, la vidéo est rechargée.
{
  const w = started(makeWorld());
  const loads = w.net.loads;
  w.stall();
  w.advance(20000);
  const early = w.net.loads - loads;
  w.advance(15000);
  out.silence_complet = {early, reloaded: w.net.loads - loads, time: w.video.currentTime, paused: w.video.paused};
}

console.log(JSON.stringify(out));
