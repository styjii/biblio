/* Visionneuse et éditeur de texte (CodeMirror + mode Vim, voir editor.bundle.js). */
(() => {
  const C = window.FLCFG;
  const el = (id) => document.getElementById(id);
  const pref = {
    get(key) { try { return localStorage.getItem(key); } catch { return null; } },
    set(key, value) { try { localStorage.setItem(key, value); } catch { /* préférence non mémorisée */ } },
  };
  const showPosition = ({line, col, lines}) => {
    el('st-pos').textContent = `${line}:${col}`;
    el('st-lines').textContent = `${lines} lignes`;
  };

  // taille du texte
  let fontSize = parseInt(pref.get('fl:fs'), 10) || 15;
  const applyFontSize = () => {
    el('editor').style.setProperty('--fs', `${fontSize}px`);
    pref.set('fl:fs', String(fontSize));
  };
  applyFontSize();
  el('fs-down').addEventListener('click', () => { fontSize = Math.max(10, fontSize - 1); applyFontSize(); });
  el('fs-up').addEventListener('click', () => { fontSize = Math.min(26, fontSize + 1); applyFontSize(); });

  const wrapOn = pref.get('fl:wrap') !== '0';
  const numbersOn = pref.get('fl:num') !== '0';
  const ctrl = FL.create({
    parent: el('editor'), name: C.name, doc: C.doc, readOnly: C.readonlyView,
    vim: C.vim !== false, wrap: wrapOn, numbers: numbersOn,
    onChange: showPosition,
    onMode() {},
    onSave: (cb) => save(cb),
    onQuit: (force) => quit(force),
    onMessage: (text) => flash(text),
  });
  el('st-lang').textContent = ctrl.label;

  let messageTimer = null;
  const flash = (text) => {
    const box = el('st-msg');
    box.textContent = text;
    clearTimeout(messageTimer);
    messageTimer = setTimeout(() => { box.textContent = ''; }, 3500);
  };

  /** Bouton à bascule dont l'état est mémorisé : `apply(état)` est appelé à chaque clic. */
  const bindToggle = (id, key, initial, apply) => {
    const button = el(id);
    let on = initial;
    button.classList.toggle('on', on);
    button.addEventListener('click', () => {
      on = !on;
      pref.set(key, on ? '1' : '0');
      button.classList.toggle('on', on);
      apply(on);
    });
  };

  bindToggle('wrap-btn', 'fl:wrap', wrapOn, (on) => ctrl.setWrap(on));

  if (C.mode === 'view') {
    el('find-btn').addEventListener('click', () => ctrl.search());
    return;
  }

  // ------------------------------------------------ mode édition
  let leaving = false;
  const keysPanel = el('keys');
  const vimOn = pref.get('fl:vim') !== '0';
  const keysOn = pref.get('fl:keys') === null ? matchMedia('(pointer:coarse)').matches : pref.get('fl:keys') === '1';

  const MODE_LABELS = {normal: 'NORMAL', insert: 'INSERT', visual: 'VISUAL', replace: 'REMPLACER'};
  const setModeLabel = (mode, sub) => {
    const box = el('st-mode');
    let label = MODE_LABELS[mode] ?? mode.toUpperCase();
    if (mode === 'visual' && sub === 'linewise') label = 'V-LIGNE';
    if (mode === 'visual' && sub === 'blockwise') label = 'V-BLOC';
    if (mode === 'off') label = 'TEXTE';
    box.textContent = label;
    box.dataset.m = mode;
  };
  const syncVimUi = (on) => {
    keysPanel.classList.toggle('novim', !on);
    if (!on) setModeLabel('off');
  };

  ctrl.opts.onChange = (info) => {
    el('dirty').hidden = !info.dirty;
    showPosition(info);
  };
  ctrl.opts.onMode = setModeLabel;
  if (!vimOn) ctrl.setVim(false);
  syncVimUi(vimOn);
  keysPanel.hidden = !keysOn;

  bindToggle('btn-vim', 'fl:vim', vimOn, (on) => { ctrl.setVim(on); syncVimUi(on); ctrl.focus(); });
  bindToggle('btn-keys', 'fl:keys', keysOn, (on) => { keysPanel.hidden = !on; });
  bindToggle('num-btn', 'fl:num', numbersOn, (on) => ctrl.setNumbers(on));

  keysPanel.addEventListener('pointerdown', (e) => e.preventDefault());       // les touches virtuelles ne volent pas le focus
  keysPanel.addEventListener('click', (e) => {
    const key = e.target.closest('[data-k]');
    if (key) ctrl.send(key.dataset.k);
  });

  async function save(then, force = false) {
    if (C.readonly) return flash('Mode lecture seule');
    const url = `/save?f=${C.q}&mt=${encodeURIComponent(C.mt)}&enc=${encodeURIComponent(C.enc)}&crlf=${C.crlf ? 1 : 0}${force ? '&force=1' : ''}`;
    let status, answer;
    try {
      const r = await fetch(url, {
        method: 'POST',
        headers: {'X-Requested-With': 'biblio', 'Content-Type': 'text/plain; charset=utf-8'},
        body: ctrl.getText(),
      });
      status = r.status;
      answer = await r.json();
    } catch {
      return flash('Échec réseau, rien n’a été enregistré');
    }
    if (status === 409 && !force) {
      if (confirm('Le fichier a changé sur le disque depuis son ouverture. Écraser quand même ?')) return save(then, true);
      return flash('Enregistrement annulé');
    }
    if (!answer.ok) return flash(`Erreur : ${answer.error || status}`);
    C.mt = answer.mtime;
    if (answer.enc) C.enc = answer.enc;
    ctrl.markSaved();
    flash(`Enregistré · ${answer.lines} lignes`);
    then?.();
  }

  function quit(force) {
    if (!force && ctrl.isDirty()) return flash('Modifications non enregistrées (:q! pour quitter quand même)');
    leaving = true;
    location.href = C.back;
  }

  window.addEventListener('beforeunload', (e) => {
    if (!leaving && ctrl.isDirty()) { e.preventDefault(); e.returnValue = ''; }
  });
  el('btn-save').addEventListener('click', () => save());
  document.addEventListener('keydown', (e) => {
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 's') { e.preventDefault(); save(); }
  });
  ctrl.focus();
})();
