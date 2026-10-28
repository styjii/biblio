  // ----- dossiers : menu d'actions (ouvrir, ZIP, renommer, supprimer) et création d'un dossier
  document.querySelectorAll('.item[data-kind="folder"]').forEach(function(a){
    a.addEventListener('click', function(e){
      if (!e.target.closest('.more')) return;      // ailleurs sur la ligne : on ouvre le dossier
      e.preventDefault();
      openMenu(a);
    });
  });

  var mkb = document.getElementById('newdir');
  if (mkb) {
    var mkLocked = function(){ return !!cfg.protect && !cfg.unlocked; };
    var mkPaint = function(){
      var lock = mkLocked();
      document.getElementById('mk-locked').hidden = !lock;
      document.getElementById('mkname').hidden = lock;
      document.getElementById('mkok').hidden = lock;
    };
    mkb.addEventListener('click', function(){
      ['sheet-main', 'newdlg', 'deldlg', 'rendlg', 'edtdlg', 'updlg'].forEach(function(id){ document.getElementById(id).hidden = true; });
      document.getElementById('mkdlg').hidden = false;
      document.getElementById('mk-dest').textContent = cfg.folder ? 'Dans « ' + cfg.folder + ' »' : 'À la racine de la bibliothèque';
      document.getElementById('mkerr').textContent = '';
      var inp = document.getElementById('mkname');
      inp.value = '';
      mkPaint();
      wrap.hidden = false;
      if (!mkLocked()) setTimeout(function(){ inp.focus(); }, 50);
    });
    document.getElementById('mkcancel').addEventListener('click', closeSheet);
    document.getElementById('mkform').addEventListener('submit', function(e){
      e.preventDefault();
      if (mkLocked()) return;
      var name = document.getElementById('mkname').value.trim();
      var err = document.getElementById('mkerr'), btn = document.getElementById('mkok');
      if (!name || name.indexOf('/') >= 0 || name.indexOf(String.fromCharCode(92)) >= 0 || name === '.' || name === '..') {
        err.textContent = 'Nom invalide (sans « / »).'; return;
      }
      btn.disabled = true; err.textContent = '';
      fetch('/mkdir?d=' + encodeURIComponent(cfg.folder) + '&to=' + encodeURIComponent(name), {method: 'POST', headers: {'X-Requested-With': 'biblio'}})
        .then(function(r){ return r.json().then(function(j){ return {s: r.status, j: j}; }); })
        .then(function(x){
          btn.disabled = false;
          if (!x.j.ok) {
            if (x.j.locked) { cfg.unlocked = false; mkPaint(); return; }
            err.textContent = x.j.error || ('Erreur ' + x.s);
            return;
          }
          location.reload();
        })
        .catch(function(){ btn.disabled = false; err.textContent = 'Échec réseau, le dossier n’a pas été créé.'; });
    });
  }

