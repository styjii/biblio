  // ----- renommage (déverrouillage requis ; aucun mot de passe n'est demandé ici)
  var renTarget = null;
  function renPaint(){
    var locked = !cfg.unlocked;
    document.getElementById('ren-locked').hidden = !locked;
    document.getElementById('rennew').hidden = locked;
    document.getElementById('renok').hidden = locked;
  }
  function askRename(a){
    renTarget = a;
    var inp = document.getElementById('rennew');
    document.getElementById('ren-name').textContent = a.dataset.title;
    document.getElementById('renerr').textContent = '';
    inp.value = a.dataset.title;
    renPaint();
    document.getElementById('sheet-main').hidden = true;
    document.getElementById('rendlg').hidden = false;
    if (cfg.unlocked) setTimeout(function(){
      inp.focus();
      var dot = inp.value.lastIndexOf('.');
      inp.setSelectionRange(0, dot > 0 ? dot : inp.value.length);
    }, 30);
  }
  document.getElementById('rencancel').addEventListener('click', closeSheet);
  document.getElementById('renform').addEventListener('submit', function(e){
    e.preventDefault();
    var err = document.getElementById('renerr'), btn = document.getElementById('renok');
    var name = document.getElementById('rennew').value.trim();
    if (!renTarget || !cfg.canDelete || !cfg.unlocked) return;
    if (!name) { err.textContent = 'Saisis un nom.'; return; }
    if (name === renTarget.dataset.title) { closeSheet(); return; }
    btn.disabled = true; err.textContent = '';
    fetch('/rename?f=' + renTarget.dataset.f + '&to=' + encodeURIComponent(name), {method: 'POST', headers: {'X-Requested-With': 'biblio'}})
      .then(function(r){ return r.json().then(function(j){ return {s: r.status, j: j}; }); })
      .then(function(x){
        btn.disabled = false;
        if (!x.j.ok) {
          if (x.j.locked) { cfg.unlocked = false; renPaint(); return; }
          err.textContent = x.j.error || ('Erreur ' + x.s);
          return;
        }
        location.reload();
      })
      .catch(function(){ btn.disabled = false; err.textContent = 'Échec réseau, le fichier n’a pas été renommé.'; });
  });

