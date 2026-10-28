(function(){
  var C = window.FLCFG;
  function el(id){ return document.getElementById(id); }
  function ls(k, v){ try { if (v === undefined) return localStorage.getItem(k); localStorage.setItem(k, v); } catch(e) {} return null; }

  var fs = parseInt(ls('fl:fs'), 10) || 15;
  function applyFs(){ el('editor').style.setProperty('--fs', fs + 'px'); ls('fl:fs', String(fs)); }
  applyFs();
  el('fs-down').addEventListener('click', function(){ fs = Math.max(10, fs - 1); applyFs(); });
  el('fs-up').addEventListener('click', function(){ fs = Math.min(26, fs + 1); applyFs(); });

  var wrapOn = ls('fl:wrap') !== '0';
  var numOn = ls('fl:num') !== '0';
  var ctrl = FL.create({
    parent: el('editor'), name: C.name, doc: C.doc, readOnly: C.readonlyView,
    vim: C.vim !== false, wrap: wrapOn, numbers: numOn,
    onChange: function(i){ el('st-pos').textContent = i.line + ':' + i.col; el('st-lines').textContent = i.lines + ' lignes'; },
    onMode: function(m){ },
    onSave: function(cb){ save(cb); },
    onQuit: function(force){ quit(force); },
    onMessage: function(t){ flash(t); }
  });
  el('st-lang').textContent = ctrl.label;

  var msgTimer = null;
  function flash(t){
    var m = el('st-msg'); m.textContent = t;
    clearTimeout(msgTimer); msgTimer = setTimeout(function(){ m.textContent = ''; }, 3500);
  }

  if (C.mode === 'view') {
    el('wrap-btn').classList.toggle('on', wrapOn);
    el('wrap-btn').addEventListener('click', function(){
      wrapOn = !wrapOn; ctrl.setWrap(wrapOn); ls('fl:wrap', wrapOn ? '1' : '0');
      el('wrap-btn').classList.toggle('on', wrapOn);
    });
    el('find-btn').addEventListener('click', function(){ ctrl.search(); });
    return;
  }

  // ------------------------------------------------ mode édition
  var dirty = false, leaving = false;
  var vimOn = ls('fl:vim') !== '0';
  var keysOn = ls('fl:keys') === null ? matchMedia('(pointer:coarse)').matches : ls('fl:keys') === '1';
  var keys = el('keys');

  function setModeLabel(m, sub){
    var b = el('st-mode');
    var map = {normal:'NORMAL', insert:'INSERT', visual:'VISUAL', replace:'REMPLACER'};
    var txt = map[m] || m.toUpperCase();
    if (m === 'visual' && sub === 'linewise') txt = 'V-LIGNE';
    if (m === 'visual' && sub === 'blockwise') txt = 'V-BLOC';
    if (m === 'off') txt = 'TEXTE';
    b.textContent = txt; b.dataset.m = m;
  }
  function syncVimUi(){
    el('btn-vim').classList.toggle('on', vimOn);
    keys.classList.toggle('novim', !vimOn);
    if (!vimOn) setModeLabel('off');
  }

  ctrl.opts.onChange = function(i){
    dirty = i.dirty;
    el('dirty').hidden = !i.dirty;
    el('st-pos').textContent = i.line + ':' + i.col;
    el('st-lines').textContent = i.lines + ' lignes';
  };
  ctrl.opts.onMode = setModeLabel;
  if (!vimOn) ctrl.setVim(false);
  syncVimUi();
  keys.hidden = !keysOn; el('btn-keys').classList.toggle('on', keysOn);

  el('btn-vim').addEventListener('click', function(){
    vimOn = !vimOn; ls('fl:vim', vimOn ? '1' : '0'); ctrl.setVim(vimOn); syncVimUi(); ctrl.focus();
  });
  el('btn-keys').addEventListener('click', function(){
    keysOn = !keysOn; ls('fl:keys', keysOn ? '1' : '0'); keys.hidden = !keysOn;
    el('btn-keys').classList.toggle('on', keysOn);
  });
  el('wrap-btn').classList.toggle('on', wrapOn);
  el('wrap-btn').addEventListener('click', function(){
    wrapOn = !wrapOn; ctrl.setWrap(wrapOn); ls('fl:wrap', wrapOn ? '1' : '0');
    el('wrap-btn').classList.toggle('on', wrapOn);
  });
  el('num-btn').classList.toggle('on', numOn);
  el('num-btn').addEventListener('click', function(){
    numOn = !numOn; ctrl.setNumbers(numOn); ls('fl:num', numOn ? '1' : '0');
    el('num-btn').classList.toggle('on', numOn);
  });

  keys.addEventListener('pointerdown', function(e){ e.preventDefault(); });
  keys.addEventListener('click', function(e){
    var b = e.target.closest('[data-k]');
    if (b) ctrl.send(b.dataset.k);
  });

  function save(cb, force){
    if (C.readonly) { flash('Mode lecture seule'); return; }
    var url = '/save?f=' + C.q + '&mt=' + encodeURIComponent(C.mt) + '&enc=' + encodeURIComponent(C.enc) +
      '&crlf=' + (C.crlf ? 1 : 0) + (force ? '&force=1' : '');
    fetch(url, {
      method: 'POST',
      headers: {'X-Requested-With': 'biblio', 'Content-Type': 'text/plain; charset=utf-8'},
      body: ctrl.getText()
    }).then(function(r){ return r.json().then(function(j){ return {s: r.status, j: j}; }); })
      .then(function(x){
        if (x.s === 409 && !force) {
          if (confirm('Le fichier a changé sur le disque depuis son ouverture. Écraser quand même ?')) save(cb, true);
          else flash('Enregistrement annulé');
          return;
        }
        if (!x.j.ok) { flash('Erreur : ' + (x.j.error || x.s)); return; }
        C.mt = x.j.mtime; if (x.j.enc) C.enc = x.j.enc;
        ctrl.markSaved(); flash('Enregistré · ' + x.j.lines + ' lignes');
        if (cb) cb();
      }).catch(function(){ flash('Échec réseau, rien n\u2019a été enregistré'); });
  }
  function quit(force){
    if (!force && ctrl.isDirty()) { flash('Modifications non enregistrées (:q! pour quitter quand même)'); return; }
    leaving = true; location.href = C.back;
  }
  window.addEventListener('beforeunload', function(e){
    if (!leaving && ctrl.isDirty()) { e.preventDefault(); e.returnValue = ''; }
  });
  el('btn-save').addEventListener('click', function(){ save(); });
  document.addEventListener('keydown', function(e){
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 's') { e.preventDefault(); save(); }
  });
  ctrl.focus();
})();
