// Visionneuse d'images (frontend/js/image/*.js) et modes d'affichage (frontend/js/browse/01-modes-d-affichage.js) exécutés
// avec une fausse page : zoom, ajustement, navigation, raccourcis clavier, ordre des images, mémorisation du mode par dossier.
const vm = require('vm'), fs = require('fs'), path = require('path');
const js = path.join(__dirname, '..', '..', 'frontend', 'js');
const bundle = (dir) => '\n(() => {\n' + fs.readdirSync(path.join(js, dir)).filter((f) => f.endsWith('.js')).sort().map((f) => fs.readFileSync(path.join(js, dir, f), 'utf8')).join('') + '})();\n';

const listeners = (t) => {
  const map = {};
  t.addEventListener = (type, fn) => { (map[type] ??= []).push(fn); };
  t.emit = (type, ev = {}) => { let prevented = false; for (const fn of [...(map[type] ?? [])]) fn({type, target: t, preventDefault() { prevented = true; }, ...ev}); return prevented; };
};
const element = (extra = {}) => {
  const el = {textContent: '', innerHTML: '', hidden: false, disabled: false, title: '', alt: '', value: '', dataset: {}, style: {}, children: [], clientWidth: 1000, clientHeight: 600,
    classList: {names: new Set(), toggle(n, on) { (on ?? !this.names.has(n)) ? this.names.add(n) : this.names.delete(n); }, add(n) { this.names.add(n); }, remove(n) { this.names.delete(n); }},
    setPointerCapture() {}, getBoundingClientRect: () => ({left: 0, top: 0, width: el.clientWidth, height: el.clientHeight}), closest: () => null, ...extra};
  listeners(el);
  return el;
};
const run = (code, ctx) => { vm.createContext(ctx); vm.runInContext(code, ctx); };
const out = {};

// ---------- visionneuse ----------
{
  const els = {};
  const get = (id) => (els[id] ??= element());
  const doc = {title: '', fullscreenElement: null, fullscreenEnabled: true, getElementById: get};
  listeners(doc);
  const stage = get('iv-stage');
  const img = get('iv-img');
  Object.assign(img, {naturalWidth: 2000, naturalHeight: 1000});
  const sizes = [];
  const store = {'fl:sort': 'size:desc'};
  const items = [
    {f: 'a.png', n: 'a.png', o: 0, b: 100, m: 5, e: 'png'}, {f: 'b.jpg', n: 'b.jpg', o: 1, b: 300, m: 3, e: 'jpg'},
    {f: '.c.png', n: '.c.png', o: 2, b: 900, m: 9, e: 'png'}, {f: 'd.gif', n: 'd.gif', o: 3, b: 200, m: 7, e: 'gif'}];
  const replaced = [];
  const ctx = {document: doc, window: {ICFG: {items, current: 'a.png', back: '/browse?folder=x', key: 'k'}, IICO: {}}, location: {href: '/image'},
    history: {replaceState: (a, b, url) => replaced.push(url)}, localStorage: {getItem: (k) => store[k] ?? null},
    ResizeObserver: class { observe() {} }, Image: class { set src(v) { sizes.push(v); } }, Math, Number, Object, Array, Map, Set, setTimeout, clearTimeout, encodeURIComponent, RegExp};
  run(bundle('image'), ctx);
  const state = () => ({zoom: get('iv-zoom').textContent, name: get('iv-name').textContent, count: get('iv-count').textContent, transform: img.style.transform,
    prevOff: get('iv-prev').disabled, nextOff: get('iv-next').disabled, src: img.src, zin: get('iv-zin').disabled, zout: get('iv-zout').disabled});
  out.ordre = {state: state(), preload: sizes};
  img.emit('load');                                       // 2000x1000 dans 1000x600 : ajusté à 50 %
  out.ajuste = state();
  const key = (k, extra = {}) => doc.emit('keydown', {key: k, target: {tagName: 'BODY'}, ...extra});
  const prevented = {};
  prevented['+'] = key('+'); out.zoomPlus = state();
  key('-'); key('-'); out.zoomMoins = state();
  key('1'); out.reel = state();
  key('0'); out.reajuste = state();
  key('ArrowRight'); out.suivante = {...state(), replaced: [...replaced]};
  key('ArrowLeft'); out.precedente = state();
  key('End'); out.fin = state();
  key('Home'); out.debut = state();
  key('n'); key('p');
  out.modificateur = key('ArrowRight', {ctrlKey: true});
  out.champ = doc.emit('keydown', {key: '+', target: {tagName: 'INPUT'}});
  key('l'); out.retourL = ctx.location.href;
  ctx.location.href = '/image'; key('Escape'); out.retourEchap = ctx.location.href;
  ctx.location.href = '/image'; doc.fullscreenElement = stage; key('Escape'); out.echapPleinEcran = ctx.location.href;
  doc.fullscreenElement = null;
  // molette : zoom autour du curseur, l'image reste sous la souris
  stage.emit('wheel', {deltaY: -100, clientX: 500, clientY: 300});
  out.molette = state();
  get('iv-zoom').emit('click'); out.basculeAjuste = state();
  get('iv-zoom').emit('click'); out.basculeReel = state();
  stage.emit('dblclick', {clientX: 100, clientY: 100}); out.doubleClic = state();
  // erreur de chargement
  img.emit('error'); out.erreur = {error: get('iv-error').hidden, loading: get('iv-loading').hidden};
  // glisser quand l'image est agrandie
  img.emit('load'); key('1'); const before = img.style.transform;
  stage.emit('pointerdown', {pointerId: 1, pointerType: 'touch', clientX: 500, clientY: 300, timeStamp: 0});
  stage.emit('pointermove', {pointerId: 1, clientX: 450, clientY: 280});
  stage.emit('pointerup', {pointerId: 1, clientX: 450, clientY: 280, timeStamp: 50});
  out.glisser = {before, after: img.style.transform};
  // balayage (image ajustée, doigt) : vers la gauche = suivante
  key('0'); img.emit('load');
  const idx = get('iv-count').textContent;
  stage.emit('pointerdown', {pointerId: 2, pointerType: 'touch', clientX: 600, clientY: 300, timeStamp: 0});
  stage.emit('pointermove', {pointerId: 2, clientX: 400, clientY: 305});
  stage.emit('pointerup', {pointerId: 2, clientX: 400, clientY: 305, timeStamp: 200});
  out.balayage = {from: idx, to: get('iv-count').textContent};
  // à la souris : pas de balayage
  const idx2 = get('iv-count').textContent;
  stage.emit('pointerdown', {pointerId: 3, pointerType: 'mouse', button: 0, clientX: 600, clientY: 300, timeStamp: 0});
  stage.emit('pointermove', {pointerId: 3, clientX: 400, clientY: 300});
  stage.emit('pointerup', {pointerId: 3, clientX: 400, clientY: 300, timeStamp: 100});
  out.sourisSansBalayage = idx2 === get('iv-count').textContent;
}

// ---------- modes d'affichage ----------
{
  const store = {};
  const win = {};
  listeners(win);
  const page = (listing = element(), view = element()) => {
    const els = {listing, view};
    const cells = [{textContent: '', closest: () => ({dataset: {mtime: '0'}})}, {textContent: '', closest: () => ({dataset: {mtime: '1700000000'}})}];
    const ctx = {$: (id) => els[id], window: win, document: {querySelectorAll: () => ({forEach: (fn) => cells.forEach(fn)})},
      localStorage: {getItem: (k) => store[k] ?? null, setItem: (k, v) => { store[k] = v; }, removeItem: (k) => { delete store[k]; }}, Number, Object, Array, JSON, Date, Math};
    vm.createContext(ctx);
    vm.runInContext(fs.readFileSync(path.join(js, 'browse', '01-modes-d-affichage.js'), 'utf8') + '\nthis.ViewMode = ViewMode; this.instance = new ViewMode();', ctx);
    return {els, cells, instance: ctx.instance};
  };
  const mode = ({els}) => ({view: els.listing.dataset.view, select: els.view.value, saved: store['fl:view'] ?? null});
  const choose = ({els}, value) => { els.view.value = value; els.view.emit('change'); };

  const racine = page();
  out.modeDefaut = mode(racine);
  out.dates = [racine.cells[0].textContent, /\d/.test(racine.cells[1].textContent)];
  choose(racine, 'details'); out.modeDetails = mode(racine);
  // navigation : un sous-dossier (autre page, autre instance) garde le même mode, de même que le dossier d'où l'on vient
  out.sousDossier = mode(page());
  out.retourRacine = mode(page());
  choose(racine, 'large'); out.modeGrand = mode(page());
  choose(racine, 'medium'); out.retourDefaut = {...mode(page())};
  choose(racine, 'inconnu'); out.modeInvalide = mode(racine);
  // un autre onglet change de mode : cette page le suit
  const suivi = page();
  win.emit('storage', {key: 'fl:view', newValue: 'list'}); out.autreOnglet = mode(suivi);
  win.emit('storage', {key: 'autre', newValue: 'small'}); out.autreCle = mode(suivi).view;
  // retour arrière : la page restaurée du cache de navigation (aucun événement « storage » reçu) reprend le mode choisi entre-temps
  const restauree = page();
  store['fl:view'] = 'details';
  win.emit('pageshow', {persisted: false}); out.pageChargee = mode(restauree).view;        // chargement normal : rien à resynchroniser
  win.emit('pageshow', {persisted: true}); out.pageRestauree = mode(restauree);
  delete store['fl:view']; win.emit('pageshow', {persisted: true}); out.pageRestaureeDefaut = mode(restauree);
  // stockage altéré : retombe sur le mode par défaut
  store['fl:view'] = 'pirate'; out.valeurInconnue = mode(page());
  store['fl:view'] = '<script>'; out.valeurHostile = mode(page());
}
console.log(JSON.stringify(out));
