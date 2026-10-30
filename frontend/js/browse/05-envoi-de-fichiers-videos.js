  // ----- envoi de fichiers, vidéos et dossiers (déverrouillage requis)
  // La feuille ne sert qu'à choisir les fichiers : l'envoi est confié à Transfers (js/transfers), qui le poursuit
  // en arrière-plan dans un SharedWorker, même si l'on change de dossier ou de page.
  if (window.Transfers) window.Transfers.currentFolder = cfg.folder || '';   // pour actualiser la liste à la fin d'un envoi ici
  var upBtn = document.getElementById('uploadbtn');
  if (upBtn && window.Transfers) {
    var upEl = function(id){ return document.getElementById(id); };
    var upShow = function(step){
      ['upform', 'uppick'].forEach(function(id){ upEl(id).hidden = (id !== step); });
    };
    var upMsg = function(text){ upEl('uperr').textContent = text; upShow('upform'); };

    upBtn.addEventListener('click', function(){
      ['sheet-main', 'newdlg', 'mkdlg', 'deldlg', 'rendlg', 'edtdlg'].forEach(function(id){ upEl(id).hidden = true; });
      upEl('updlg').hidden = false; wrap.hidden = false;
      upEl('up-dest').textContent = '/' + (cfg.folder || '');
      if (!cfg.unlocked) {
        upMsg('Accès verrouillé : déverrouille l’accès (cadenas en haut de la page) pour envoyer des fichiers.');
        return;
      }
      upShow('uppick');
    });

    upEl('upcancel').addEventListener('click', closeSheet);
    upEl('up-pick-files').addEventListener('click', function(e){ e.preventDefault(); upEl('up-in-files').click(); });
    upEl('up-pick-dir').addEventListener('click', function(e){ e.preventDefault(); upEl('up-in-dir').click(); });
    ['up-in-files', 'up-in-dir'].forEach(function(id){
      upEl(id).addEventListener('change', function(){
        var files = Array.prototype.slice.call(this.files);
        this.value = '';
        if (!files.length) return;
        window.Transfers.start(files, cfg.folder || '', upEl('upover').checked, cfg.maxUpload || 0);
        closeSheet();
      });
    });
  }

