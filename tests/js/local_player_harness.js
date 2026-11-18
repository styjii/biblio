// Exécute le script du lecteur vidéo (frontend/js/watch/*.js) en mode « local » (page d'accueil) avec une fausse page :
// fichiers de l'appareil ajoutés, enchaînés, retirés, vidés. Aucun accès au serveur n'est possible (pas de fetch, pas de Progress.get/save/done).
const vm = require('vm'), fs = require('fs'), path = require('path');
const dir = path.join(__dirname, '..', '..', 'frontend', 'js', 'watch');
const code = '\n(() => {\n' + fs.readdirSync(dir).filter((f) => f.endsWith('.js')).sort().map((f) => fs.readFileSync(path.join(dir, f), 'utf8')).join('') + '})();\n';

const listeners = (target) => {
  const map = {};
  target.addEventListener = (type, fn) => { (map[type] ??= []).push(fn); };
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
video.removeAttribute = (name) => { if (name === 'src') video.src = undefined; if (name === 'poster') video.poster = ''; };
elements.player = video;
const doc = {visibilityState: 'visible', fullscreenElement: null, documentElement: {style: {setProperty() {}}}, title: '',
  getElementById: (id) => (elements[id] ??= element()), querySelector: (sel) => (selectors[sel] ??= element()), querySelectorAll: () => [],
  createElement: () => element(), dispatchEvent(event) { events.push(event); return true; }};
listeners(doc);
const events = [];
const revoked = [];
let blobs = 0;
const win = {};
listeners(win);
const ctx = {
  window: win, document: doc, navigator: {onLine: true}, location: {href: '/'}, innerWidth: 500, setTimeout, clearTimeout, Date, JSON, Math, Number, Object, Array, Map, Promise, String, Set,
  localStorage: {getItem: () => null, setItem() {}, removeItem() {}}, sessionStorage: {getItem: () => null, setItem() {}}, matchMedia: () => ({matches: false}),
  requestAnimationFrame: (fn) => setTimeout(fn, 16), screen: {}, console,
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
out.ajout = {result: local.add([file('a.mp4', 1500, 'video/mp4'), file('b.flac'), file('c.txt', 3, 'text/plain'), file('d.mkv')]), ...state()};
out.dernierEvenement = events.at(-1).detail;
ctx.revoked = revoked;
video.emit('ended');                                  // fin de a.mp4 : enchaîne b.flac (audio : image de remplacement)
out.suite = {...state(), revoked: [...revoked]};
local.play(2);                                        // d.mkv (clic dans la file d'attente)
out.clic = {...state(), revoked: [...revoked]};
local.remove(1);                                      // retire b.flac, qui n'est pas en cours
out.retraitAutre = {...state()};
local.remove(1);                                      // retire d.mkv, en cours : le précédent prend le relais
out.retraitCourant = {...state(), revoked: [...revoked]};
local.clear();
out.vidage = {...state(), revoked: [...revoked]};
out.espaceApresVidage = !doc.emit('keydown', {key: ' ', target: {tagName: 'BODY'}});
console.log(JSON.stringify(out));
