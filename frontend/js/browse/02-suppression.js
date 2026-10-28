  // ----- suppression (déverrouillage requis ; aucun mot de passe n'est demandé ici)
  var delTarget = null;
  function delPaint(){
    var locked = !cfg.unlocked;
    document.getElementById('del-locked').hidden = !locked;
    document.getElementById('delok').hidden = locked;
  }
  function askDelete(a){
    delTarget = a;
    var fo = a.dataset.kind === 'folder';
    document.getElementById('del-title').textContent = fo ? 'Supprimer ce dossier ?' : 'Supprimer ce fichier ?';
    document.getElementById('del-warn').hidden = !fo;
    document.getElementById('del-locked').textContent = 'Accès verrouillé : déverrouille l\'accès (cadenas en haut de la page) pour supprimer ' + (fo ? 'ce dossier.' : 'ce fichier.');
    document.getElementById('del-name').textContent = a.dataset.title;
    document.getElementById('delerr').textContent = '';
    delPaint();
    document.getElementById('sheet-main').hidden = true;
    document.getElementById('deldlg').hidden = false;
  }
  document.getElementById('delcancel').addEventListener('click', closeSheet);
  document.getElementById('delform').addEventListener('submit', function(e){
    e.preventDefault();
    var err = document.getElementById('delerr'), btn = document.getElementById('delok');
    if (!delTarget || !cfg.canDelete || !cfg.unlocked) return;
    btn.disabled = true; err.textContent = '';
    fetch('/delete?f=' + delTarget.dataset.f, {method: 'POST', headers: {'X-Requested-With': 'biblio'}})
      .then(function(r){ return r.json().then(function(j){ return {s: r.status, j: j}; }); })
      .then(function(x){
        btn.disabled = false;
        if (!x.j.ok) {
          if (x.j.locked) { cfg.unlocked = false; delPaint(); return; }
          err.textContent = x.j.error || ('Erreur ' + x.s);
          return;
        }
        location.reload();
      })
      .catch(function(){ btn.disabled = false; err.textContent = 'Échec réseau, rien n’a été supprimé.'; });
  });

