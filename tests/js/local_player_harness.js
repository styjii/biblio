// Exécute le script du lecteur vidéo (frontend/js/watch/*.js) en mode « local » (page d'accueil) avec une fausse page :
// fichiers de l'appareil ajoutés, enchaînés, retirés, vidés ; modes Vidéo / Audio ; plein écran. Aucun accès au serveur n'est possible
// (pas de fetch, pas de Progress.get/save/done). Horloge et minuteries sont simulées (advance) : les tests sont instantanés et déterministes.
const vm = require('vm'), fs = require('fs'), path = require('path');
const dir = path.join(__dirname, '..', '..', 'frontend', 'js', 'watch');
const code = '\n(() => {\n' + fs.readdirSync(dir).filter((f) => f.endsWith('.js')).sort().map((f) => fs.readFileSync(path.join(dir, f), 'utf8')).join('') + '})();\n';

let now = 1_000_000;
let timerId = 0;
const timers = [];
const fakeSetTimeout = (fn, ms = 0) => { timers.push({id: ++timerId, at: now + ms, fn}); return timerId; };
const fakeClearTimeout = (id) => { const i = timers.findIndex((t) => t.id === id); if (i >= 0) timers.splice(i, 1); };
const advance = (ms) => {
  const end = now + ms;
  for (let due = null; (due = timers.filter((t) => t.at <= end).sort((a, b) => a.at - b.at)[0]);) {
    timers.splice(timers.indexOf(due), 1);
    now = Math.max(now, due.at);
    due.fn();
  }
  now = end;
};
class FakeDate extends Date { static now() { return now; } }

const listeners = (target) => {
  const map = {};
  target.addEventListener = (type, fn, options) => {
    const list = (map[type] ??= []);
    if (options?.once === true) {                         // comme le navigateur : l'écouteur disparaît après son premier appel
      const wrapper = (ev) => { list.splice(list.indexOf(wrapper), 1); fn(ev); };
      list.push(wrapper);
    } else list.push(fn);
  };
  target.emit = (type, ev = {}) => { let prevented = false; for (const fn of [...(map[type] ?? [])]) fn({type, target, preventDefault() { prevented = true; }, ...ev}); return prevented; };
};
const element = () => {
  const el = {textContent: '', innerHTML: '', value: '', checked: true, dataset: {}, style: {setProperty() {}}, className: '', hidden: false, children: [],
    classList: {toggle() {}, add() {}, remove() {}, contains: () => false}, setAttribute() {}, removeAttribute() {}, blur() {}, focus() {}, scrollIntoView() {},
    querySelector: () => null, querySelectorAll: () => [], append(...c) { this.children.push(...c); }, replaceChildren(...c) { this.children = c; },
    closest: () => null, getBoundingClientRect: () => ({left: 0, top: 0, width: 640, height: 360}), offsetWidth: 40, offsetHeight: 225};
  listeners(el);
  return el;
};

const elements = {};
const selectors = {};
const video = element();
Object.assign(video, {currentTime: 0, duration: NaN, paused: true, ended: false, readyState: 0, error: null, volume: 1, muted: false, playbackRate: 1,
  defaultPlaybackRate: 1, loop: false, autoplay: true, textTracks: [], buffered: {length: 0}, controls: true, poster: '',
  play() { this.paused = false; return Promise.resolve(); }, pause() { this.paused = true; }, load() { this.loads = (this.loads ?? 0) + 1; }});
// currentTime espionné (chaque affectation du lecteur est notée) ; src recharge le média comme un navigateur (durée inconnue, position 0, rien de prêt)
const sets = [];
delete video.currentTime;
Object.defineProperty(video, 'currentTime', {get() { return this._t ?? 0; }, set(v) { this._t = v; sets.push(v); }, configurable: true});
Object.defineProperty(video, 'src', {get() { return this._src; }, set(v) {
  this._src = v; this.currentSrc = v ?? ''; this.readyState = 0; this.duration = NaN; this._t = 0;
}, configurable: true});
video.plays = 0;
video.play = function () { this.paused = false; this.plays += 1; return Promise.resolve(); };
video.removeAttribute = (name) => { if (name === 'src') video.src = undefined; if (name === 'poster') video.poster = ''; };
elements.player = video;
elements.vbox = element();
elements.vbox.requestFullscreen = async () => {};
const doc = {visibilityState: 'visible', fullscreenElement: null, documentElement: {style: {setProperty() {}, minHeight: ''}, scrollHeight: 3000}, title: '',
  getElementById: (id) => (elements[id] ??= element()), querySelector: (sel) => (selectors[sel] ??= element()), querySelectorAll: () => [],
  createElement: () => element(), dispatchEvent(event) { events.push(event); return true; }};
listeners(doc);
const events = [];
const revoked = [];
let blobs = 0;
const win = {};
listeners(win);
const page = {x: 0, y: 0, calls: []};          // défilement de la page
const ctx = {
  window: win, document: doc, navigator: {onLine: true}, location: {href: '/'}, innerWidth: 500, setTimeout: fakeSetTimeout, clearTimeout: fakeClearTimeout, Date: FakeDate, JSON, Math, Number, Object, Array, Map, Promise, String, Set,
  localStorage: {getItem: () => null, setItem() {}, removeItem() {}}, sessionStorage: {getItem: () => null, setItem() {}}, matchMedia: () => ({matches: false}),
  get scrollX() { return page.x; }, get scrollY() { return page.y; }, scrollTo(x, y) { page.x = x; page.y = y; page.calls.push([x, y]); },
  requestAnimationFrame: (fn) => fakeSetTimeout(fn, 16), screen: {}, console,
  CustomEvent: class { constructor(type, init) { this.type = type; this.detail = init?.detail; } },
  URL: {createObjectURL: () => `blob:${++blobs}`, revokeObjectURL: (url) => revoked.push(url)},
  Progress: {fmt: (s) => `${Math.floor(s)} s`},      // ni get, ni save, ni done : tout appel au serveur de position échouerait
};
ctx.addEventListener = win.addEventListener;
win.WCFG = {local: true, folder: 'local', key: 'local', index: 0, download: '', items: []};
win.WICO = {};
win.document = doc;
win.navigator = ctx.navigator;
vm.createContext(ctx);
vm.runInContext(code, ctx);

const file = (name, size = 10, type = '') => ({name, size, type});
const local = win.BiblioLocal;
const watch = elements.watch;
const out = {};
const state = () => ({src: video.src, poster: video.poster ? 'audio' : '', hidden: watch.hidden, count: win.WCFG.items.length, title: selectors['.vtitle'].textContent,
  pos: elements['list-pos'].textContent, rows: elements['mp-list'].children.length});

out.api = Object.keys(local).sort();
out.vide = {...state(), espaceIgnore: !elements.player.emit || !doc.emit('keydown', {key: ' ', target: {tagName: 'BODY'}, ctrlKey: false})};

// ---------- mode Vidéo ----------
out.ajout = {result: local.add([file('a.mp4', 1500, 'video/mp4'), file('b.flac'), file('c.txt', 3, 'text/plain'), file('d.mkv')]), ...state()};
out.dernierEvenement = events.at(-1).detail;
ctx.revoked = revoked;
video.emit('ended');                                  // fin de a.mp4 : enchaîne d.mkv
out.suite = {...state(), revoked: [...revoked]};
local.play(0);                                        // a.mp4 (clic dans la file d'attente)
out.clic = {...state(), revoked: [...revoked]};
local.remove(1);                                      // retire d.mkv, qui n'est pas en cours
out.retraitAutre = {...state()};

// ---------- passage Vidéo -> Audio -> Vidéo : file, position, lecture/pause conservées ; volume, muet et vitesse communs ----------
Object.assign(video, {duration: 100, readyState: 4, paused: false, volume: 0.4, muted: true, playbackRate: 1.5});
video._t = 42; sets.length = 0;
const shot = () => ({src: video.src, autoplay: video.autoplay, paused: video.paused, time: video._t, poster: video.poster ? 'audio' : '', volume: video.volume, muted: video.muted, rate: video.playbackRate});
out.versAudio = {changed: local.setMode('audio'), ...state(), ...shot(), event: events.at(-1).detail, memeMode: local.setMode('audio'), inconnu: local.setMode('texte')};
out.ajoutAudio = {result: local.add([file('b.flac'), file('e.mp3'), file('f.mp4', 5, 'video/mp4')]), ...state(), event: events.at(-1).detail};
Object.assign(video, {duration: 200, readyState: 4, paused: false}); video._t = 7;
out.retourVideo = {changed: local.setMode('video'), ...state(), ...shot()};            // avant les métadonnées : la position n'est pas encore rejointe
out.avantMetadonnees = {sets: [...sets]};
Object.assign(video, {duration: 100, readyState: 1}); video.emit('loadedmetadata');
out.retourVideoPrete = {...shot(), sets: [...sets], plays: video.plays};
video.paused = true; video._t = 45;                    // l'utilisateur met la vidéo en pause à 0:45
out.versAudio2 = {...(local.setMode('audio'), state()), ...shot()};
Object.assign(video, {duration: 200, readyState: 1}); video.emit('loadedmetadata');
out.audioRepris = {...shot(), poster: video.poster ? 'audio' : ''};
video.paused = true; video._t = 11;                    // pause de l'audio à 0:11
local.setMode('video');
Object.assign(video, {duration: 100, readyState: 1}); const playsAvant = video.plays; video.emit('loadedmetadata');
out.videoRestaureeEnPause = {...shot(), plays: video.plays - playsAvant, ...state()};
out.compteurs = events.at(-1).detail;

// ---------- plein écran : position et état conservés ----------
const scene = (time, playing) => { Object.assign(video, {readyState: 4, duration: 600, paused: !playing}); video._t = time; sets.length = 0; video.emit('timeupdate'); };
const pressF = () => doc.emit('keydown', {key: 'f', target: {tagName: 'BODY'}});
const enter = () => { doc.fullscreenElement = elements.vbox; doc.emit('fullscreenchange'); };
const leave = () => { doc.fullscreenElement = null; doc.emit('fullscreenchange'); };
const outcome = () => ({time: video._t, paused: video.paused, sets: [...sets]});
const plays0 = () => video.plays;

scene(120, true); pressF(); enter();                   // le navigateur remet la lecture à 0:00 et l'interrompt
video._t = 0; video.paused = true; video.emit('pause');
advance(600); out.pleinEcranPerte = outcome();
advance(5000); out.pleinEcranSansBoucle = outcome().sets;

scene(50, false); pressF(); enter(); advance(600); out.pleinEcranPause = outcome();                 // en pause : reste en pause, rien n'est touché

scene(10, true); pressF(); enter(); video._t = 10.4; const p0 = plays0(); advance(600);              // tout va bien : aucune intervention
out.pleinEcranNormal = {...outcome(), plays: video.plays - p0};

scene(80, true); pressF(); enter(); video._t = 0; video.paused = true; video.emit('pause');          // l'utilisateur agit pendant la transition
advance(10); doc.emit('pointerdown', {}); advance(600); out.pleinEcranActionUtilisateur = outcome();

scene(200, true); pressF(); leave(); video.paused = true; video.emit('pause'); advance(600);          // sortie : le navigateur met en pause
out.sortieEnPause = outcome();

scene(100, true); advance(1000); video._t = 101; video.emit('timeupdate'); advance(100);              // plein écran natif d'iOS, sans demande du lecteur
video.paused = true; video.emit('pause'); advance(10); video.emit('webkitendfullscreen'); advance(600);
out.natifIos = outcome();

scene(30, true); advance(700); video.paused = true; video.emit('pause');                          // plusieurs événements pour une seule transition : une seule vérification
const p1 = plays0(); video.emit('webkitbeginfullscreen'); video.emit('fullscreenchange'); doc.emit('webkitfullscreenchange'); advance(600);
out.eventsMultiples = {...outcome(), plays: video.plays - p1};

scene(60, true); advance(700); advance(10); doc.emit('keydown', {key: 'k'}); video.paused = true; video.emit('pause');   // pause voulue juste avant un plein écran lancé par le navigateur
advance(50); const p2 = plays0(); doc.emit('fullscreenchange'); advance(600);
out.pauseVoulue = {...outcome(), plays: video.plays - p2};

scene(70, false); advance(700); video.emit('pause'); video.emit('timeupdate'); advance(10); doc.emit('fullscreenchange'); video.paused = false; advance(600);   // jamais de pause forcée sans demande du lecteur
out.jamaisDePauseForcee = outcome();

// ---------- plein écran : la page retrouve sa position de défilement ----------
// Le navigateur ramène le défilement dans les limites quand la page raccourcit (le lecteur sort du flux en plein écran), puis, sur mobile, le
// remet à zéro APRÈS l'événement de sortie (barres et fenêtre qui reprennent leur taille) : la position doit être rétablie et gardée un instant.
const root = doc.documentElement;
const scrolled = (y) => { page.y = y; win.emit('scroll'); };
const raccourcit = () => { page.y = 0; };                                        // recadrage du navigateur, sans l'événement « scroll » du lecteur
const cycle = () => { pressF(); enter(); raccourcit(); advance(10); leave(); };    // entrée, recadrage, sortie
scene(120, true); page.calls.length = 0; scrolled(1400); advance(1000);
pressF(); out.pageMaintenue = root.style.minHeight; enter(); raccourcit(); advance(10);
out.pendantPleinEcran = {y: page.y, minHeight: root.style.minHeight, appels: page.calls.length};
leave(); out.sortieImmediate = {y: page.y, appels: [...page.calls]};
advance(50); out.sortieApres = {y: page.y, minHeight: root.style.minHeight, appels: page.calls.length};   // hauteur gardée tant que la surveillance dure
advance(300); scrolled(0); out.remiseAZeroTardive = {y: page.y, appels: page.calls.length};         // le navigateur remet à zéro après coup : annulé
advance(300); win.emit('resize'); page.y = 0; win.emit('resize'); out.apresRedimensionnement = page.y;
advance(2000); out.finDeSurveillance = {minHeight: root.style.minHeight};
const appels = page.calls.length; scrolled(0); out.apresSurveillance = {y: page.y, appels: page.calls.length - appels};   // plus rien n'est forcé ensuite

scrolled(900); advance(1000); cycle(); win.emit('touchstart'); scrolled(300); advance(10);    // l'utilisateur fait défiler : on ne lutte pas contre lui
out.utilisateurDefile = {y: page.y, minHeight: root.style.minHeight}; advance(2000);

scrolled(900); advance(1000); const avant = page.calls.length; pressF(); enter(); leave(); advance(2000);     // la page n'a pas bougé : aucun défilement
out.sansChangement = {y: page.y, appels: page.calls.length - avant};

scrolled(700); advance(1000); const appelsAvant = page.calls.length;              // plein écran natif d'iOS : position relevée dans l'historique
doc.fullscreenElement = null; video.webkitDisplayingFullscreen = true; page.y = 0; video.emit('webkitbeginfullscreen');
video.webkitDisplayingFullscreen = false; video.emit('webkitendfullscreen'); advance(2000);
out.natifDefilement = {y: page.y, appels: page.calls.length - appelsAvant};

scrolled(500); advance(1000); video.webkitDisplayingFullscreen = false; pressF();   // plein écran refusé : la hauteur de la page est rendue
const retenue = root.style.minHeight; advance(2000);
out.refuse = {retenue, apres: root.style.minHeight};

// ---------- vidage ----------
local.clear();
out.vidage = {...state(), revoked: [...revoked], created: blobs};
out.espaceApresVidage = !doc.emit('keydown', {key: ' ', target: {tagName: 'BODY'}});
console.log(JSON.stringify(out));
