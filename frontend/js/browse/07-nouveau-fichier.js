  // ----- nouveau fichier
  var nb = document.getElementById('newfile');
  if (nb) {
    nb.addEventListener('click', function(){
      document.getElementById('sheet-main').hidden = true;
      document.getElementById('deldlg').hidden = true;
      document.getElementById('newdlg').hidden = false;
      wrap.hidden = false;
      var inp = document.getElementById('newname'), nlock = !!cfg.protect && !cfg.unlocked;
      document.getElementById('rendlg').hidden = true; document.getElementById('edtdlg').hidden = true;
      document.getElementById('mkdlg').hidden = true;
      document.getElementById('new-locked').hidden = !nlock;
      inp.hidden = nlock; document.getElementById('newok').hidden = nlock;
      inp.value = ''; document.getElementById('newerr').textContent = '';
      if (!nlock) setTimeout(function(){ inp.focus(); }, 50);
    });
    document.getElementById('newcancel').addEventListener('click', closeSheet);
    document.getElementById('newform').addEventListener('submit', function(e){
      e.preventDefault();
      if (cfg.protect && !cfg.unlocked) return;
      var name = document.getElementById('newname').value.trim();
      var err = document.getElementById('newerr');
      if (!name || name.indexOf('/') >= 0 || name.indexOf(String.fromCharCode(92)) >= 0 || name === '.' || name === '..') {
        err.textContent = 'Nom invalide (sans « / »).'; return;
      }
      var rel = cfg.folder ? cfg.folder + '/' + name : name;
      location.href = '/edit?new=1&f=' + encodeURIComponent(rel);
    });
  }
})();
