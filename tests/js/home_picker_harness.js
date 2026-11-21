// Exécute le script de l'accueil (frontend/js/home/*.js) avec une fausse page et un faux lecteur (window.BiblioLocal) :
// onglets Vidéo / Audio (clic, clavier), textes du mode, messages de fichiers ignorés, positionnement de la vue sur le lecteur.
const vm = require('vm'), fs = require('fs'), path = require('path');
const dir = path.join(__dirname, '..', '..', 'frontend', 'js', 'home');
const code = '\n(() => {\n' + fs.readdirSync(dir).filter((f) => f.endsWith('.js')).sort().map((f) => fs.readFileSync(path.join(dir, f), 'utf8')).join('') + '})();\n';

const listeners = (target) => {
  const map = {};
  target.addEventListener = (type, fn) => { (map[type] ??= []).push(fn); };
  target.emit = (type, ev = {}) => {
    const flags = {prevented: false, stopped: false};
    for (const fn of [...(map[type] ?? [])]) fn({type, target, preventDefault() { flags.prevented = true; }, stopPropagation() { flags.stopped = true; }, ...ev});
    return flags;
  };
};
const element = (extra = {}) => {
  const el = {textContent: '', hidden: false, dataset: {}, attrs: {}, tabIndex: 0, focused: 0, accept: '', value: '', files: [], clicks: 0,
    classList: {add() {}, remove() {}, toggle() {}}, focus() { this.focused += 1; }, click() { this.clicks += 1; },
    setAttribute(name, value) { this.attrs[name] = value; }, ...extra};
  listeners(el);
  return el;
};

const elements = {};
const byId = (id) => (elements[id] ??= element());
const tabs = ['video', 'audio'].map((mode) => element({dataset: {mode}}));
const jump = element();
const section = element({scrolls: [], top: 0, scrollIntoView(options) { this.scrolls.push(options); }, getBoundingClientRect() { return {top: this.top}; }});
elements.lecteur = section;
const doc = {getElementById: byId, querySelectorAll: (sel) => (sel === '.mp-tab' ? tabs : []), querySelector: (sel) => (sel === 'a[href="#lecteur"]' ? jump : null)};
listeners(doc);
const win = {};
listeners(win);
const calls = [];
let reduced = false;
win.BiblioLocal = {
  mode: 'video',
  setMode(mode) { calls.push(mode); this.mode = mode; doc.emit('biblio:local', {detail: {count: 0, mode, counts: {video: 3, audio: 1}}}); },
  add: (files) => ({mode: win.BiblioLocal.mode, ...fakeAdd(files)}),
  clear() { calls.push('clear'); },
};
let fakeAdd = () => ({accepted: 0, rejected: 0, other: 0});
const history = {replaced: []};
history.replaceState = (...args) => history.replaced.push(args[2]);
const ctx = {window: win, document: doc, history, innerHeight: 800, matchMedia: () => ({matches: reduced}),
  getComputedStyle: () => ({scrollMarginTop: '76px'}), Number, Object, Array, String, Math};
win.document = doc;
vm.createContext(ctx);
vm.runInContext(code, ctx);

const out = {};
const state = () => ({
  selected: tabs.map((t) => t.attrs['aria-selected']), tabIndex: tabs.map((t) => t.tabIndex),
  counts: [byId('mp-n-video').textContent, byId('mp-n-audio').textContent], title: byId('mp-drop-title').textContent,
  pick: byId('mp-pick-label').textContent, label: byId('mp-drop').attrs['aria-label'], accept: byId('mp-input').accept,
  labelledby: byId('mp-panel').attrs['aria-labelledby'], dropHidden: byId('mp-drop').hidden,
});
out.initial = state();
tabs[1].emit('click'); out.audio = {...state(), calls: [...calls]};
tabs[1].emit('click'); out.memeOnglet = [...calls];                                  // même mode : rien n'est demandé au lecteur
const key = (name) => byId('mp-tabs').emit('keydown', {key: name});
out.fleche = {flags: key('ArrowLeft'), calls: [...calls], focus: tabs.map((t) => t.focused)};
out.flecheDroite = key('ArrowRight').stopped && calls.at(-1);
out.fin = (key('Home'), calls.at(-1)) + '/' + (key('End'), calls.at(-1));
out.autreTouche = key('a');
fakeAdd = () => ({accepted: 1, rejected: 1, other: 2});
win.BiblioLocal.mode = 'video';
byId('mp-input').files = [{}, {}]; byId('mp-input').emit('change');
out.message = {text: byId('mp-error').textContent, hidden: byId('mp-error').hidden};
fakeAdd = () => ({accepted: 1, rejected: 0, other: 1});
byId('mp-input').emit('change'); out.messageUnique = byId('mp-error').textContent;
fakeAdd = () => ({accepted: 2, rejected: 0, other: 0});
byId('mp-input').emit('change'); out.sansMessage = byId('mp-error').hidden;
win.BiblioLocal.mode = 'audio';
fakeAdd = () => ({accepted: 0, rejected: 0, other: 3});
byId('mp-input').emit('change'); out.messageAudio = byId('mp-error').textContent;

// positionnement : seulement sur une action, et seulement si la section est mal placée
const dropFiles = () => win.emit('drop', {dataTransfer: {types: ['Files'], files: []}});
section.top = 700; dropFiles(); out.tropBas = section.scrolls.splice(0);
section.top = 100; dropFiles(); out.bienPlacee = section.scrolls.splice(0);
section.top = 20; dropFiles(); out.sousLaBarre = section.scrolls.splice(0);
reduced = true; section.top = 700; dropFiles(); out.animationsReduites = section.scrolls.splice(0);
reduced = false;
section.top = 100; const lien = jump.emit('click'); out.lien = {prevented: lien.prevented, scrolls: section.scrolls.splice(0), hash: [...history.replaced]};
section.top = 76; jump.emit('click'); out.lienDejaCale = section.scrolls.splice(0);
out.pasDeDefilementSansAction = section.scrolls.length;
console.log(JSON.stringify(out));
