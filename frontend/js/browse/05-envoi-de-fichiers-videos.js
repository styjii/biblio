  // ----- envoi de fichiers, vidéos et dossiers (déverrouillage requis)
  var upBtn = document.getElementById('uploadbtn');
  if (upBtn) {
    var upTicket = null, upExpire = 0, upTtl = 0, upCancel = false, upXhr = null;
    var upEl = function(id){ return document.getElementById(id); };
    var upWarn = function(e){ e.preventDefault(); e.returnValue = ''; };
    var fmtB = function(n){
      var u = ['o', 'Ko', 'Mo', 'Go', 'To'], i = 0;
      while (n >= 1024 && i < u.length - 1) { n /= 1024; i++; }
      return (i ? n.toFixed(n < 10 ? 1 : 0).replace('.', ',') : n) + ' ' + u[i];
    };
    var upShow = function(step){
      ['upform', 'uppick', 'uprun'].forEach(function(id){ upEl(id).hidden = (id !== step); });
      upEl('up-min').hidden = (step !== 'uprun');
    };
    // Masquer / afficher la section des envois : l'envoi continue, un onglet flottant permet de la rouvrir.
    var upTab = upEl('up-tab');
    var upTabSet = function(txt, p){
      upEl('up-tab-txt').textContent = txt;
      if (p !== undefined) upTab.style.setProperty('--p', p + '%');
    };
    upMinimize = function(){
      upMin = true; upEl('updlg').hidden = true; wrap.hidden = true; upTab.hidden = false;
    };
    var upRestore = function(){
      upMin = false; upTab.hidden = true;
      ['sheet-main', 'newdlg', 'mkdlg', 'deldlg', 'rendlg', 'edtdlg'].forEach(function(id){ upEl(id).hidden = true; });
      upEl('updlg').hidden = false; wrap.hidden = false;
    };
    upEl('up-min').addEventListener('click', upMinimize);
    upTab.addEventListener('click', upRestore);

    var upMsg = function(text){ upEl('uperr').textContent = text; upShow('upform'); };
    var upLocked = function(){
      cfg.unlocked = false; upTicket = null;
      upMsg('Accès verrouillé : déverrouille l’accès (cadenas en haut de la page) pour envoyer des fichiers.');
    };
    var upGetTicket = function(){
      upEl('uperr').textContent = '';
      fetch('/upload-auth', {method: 'POST', headers: {'X-Requested-With': 'biblio'}})
        .then(function(r){ return r.json().then(function(j){ return {s: r.status, j: j}; }); })
        .then(function(x){
          if (!x.j.ok) { if (x.j.locked) upLocked(); else upMsg(x.j.error || ('Erreur ' + x.s)); return; }
          upTicket = x.j.ticket; upTtl = x.j.ttl * 1000; upExpire = Date.now() + upTtl - 30000;
          upShow('uppick');
        })
        .catch(function(){ upMsg('Échec réseau.'); });
    };

    upBtn.addEventListener('click', function(){
      if (upMin) { upRestore(); return; }
      upEl('sheet-main').hidden = true; upEl('newdlg').hidden = true; upEl('deldlg').hidden = true; upEl('rendlg').hidden = true; upEl('edtdlg').hidden = true; upEl('mkdlg').hidden = true;
      upEl('updlg').hidden = false; wrap.hidden = false;
      upEl('up-dest').textContent = '/' + (cfg.folder || '');
      if (!cfg.unlocked) { upLocked(); return; }
      if (upTicket && Date.now() < upExpire) upShow('uppick'); else upGetTicket();
    });

    upEl('upcancel').addEventListener('click', closeSheet);
    upEl('up-pick-files').addEventListener('click', function(e){ e.preventDefault(); upEl('up-in-files').click(); });
    upEl('up-pick-dir').addEventListener('click', function(e){ e.preventDefault(); upEl('up-in-dir').click(); });
    ['up-in-files', 'up-in-dir'].forEach(function(id){
      upEl(id).addEventListener('change', function(){
        var files = Array.prototype.slice.call(this.files);
        this.value = '';
        if (files.length) upStart(files);
      });
    });

    upEl('up-cancel').addEventListener('click', function(){ upCancel = true; if (upXhr) upXhr.abort(); });
    upEl('up-done').addEventListener('click', function(){ upRunning = false; closeSheet(); });

    var upStart = function(files){
      var over = upEl('upover').checked, max = cfg.maxUpload || 0;
      var items = files.map(function(f){ return {f: f, rel: f.webkitRelativePath || f.name}; });
      var total = 0;
      var list = upEl('up-list');
      list.innerHTML = '';
      items.forEach(function(it){
        total += it.f.size;
        var row = document.createElement('div'); row.className = 'uprow';
        var n = document.createElement('span'); n.className = 'n'; n.textContent = it.rel;
        var s = document.createElement('span'); s.className = 's'; s.textContent = fmtB(it.f.size);
        row.appendChild(n); row.appendChild(s); list.appendChild(row);
        it.row = row; it.s = s;
      });
      upShow('uprun');
      upEl('up-done').hidden = true; upEl('up-cancel').hidden = false;
      upEl('up-bar').style.width = '0%';
      upTabSet('Envoi 0 %', 0);
      upRunning = true; upCancel = false;
      window.addEventListener('beforeunload', upWarn);

      var i = 0, sent = 0, ok = 0, skipped = 0, failed = 0;
      var setBar = function(bytes){
        var p = total ? Math.min(100, bytes / total * 100) : 100;
        upEl('up-bar').style.width = p + '%';
        upTabSet('Envoi ' + Math.round(p) + ' %', p);
        upEl('up-sum').textContent = (ok + skipped + failed) + ' / ' + items.length + ' · ' + fmtB(Math.min(bytes, total)) + ' sur ' + fmtB(total);
      };
      var mark = function(it, cls, txt, ico){
        it.row.className = 'uprow ' + cls;
        it.s.textContent = '';
        if (ico && ICO[ico]) { var w = document.createElement('span'); w.className = 'sico'; w.innerHTML = ICO[ico]; it.s.appendChild(w); }
        it.s.appendChild(document.createTextNode(txt));
      };
      var finish = function(msg){
        upRunning = false;
        window.removeEventListener('beforeunload', upWarn);
        upEl('up-cancel').hidden = true; upEl('up-done').hidden = false;
        upEl('up-bar').style.width = (msg ? upEl('up-bar').style.width : '100%');
        upEl('up-sum').textContent = ok + ' envoyé(s)' + (skipped ? ' · ' + skipped + ' déjà présent(s)' : '') +
          (failed ? ' · ' + failed + ' en échec' : '') + (msg ? ' · ' + msg : '');
        if (ok) upDirty = true;
        upTabSet(msg ? 'Envoi interrompu' : (failed ? 'Envoi terminé · ' + failed + ' en échec' : 'Envoi terminé'), 100);
      };
      var next = function(){
        if (upCancel) return finish('arrêté');
        if (i >= items.length) return finish('');
        var it = items[i++];
        if (max && it.f.size > max) {
          failed++; sent += it.f.size; mark(it, 'bad', 'trop volumineux (max ' + fmtB(max) + ')');
          setBar(sent); return next();
        }
        mark(it, 'run', '0 %');
        var x = new XMLHttpRequest();
        upXhr = x;
        x.open('POST', '/upload?d=' + encodeURIComponent(cfg.folder || '') + '&n=' + encodeURIComponent(it.rel) + (over ? '&o=1' : ''));
        x.setRequestHeader('X-Requested-With', 'biblio');
        x.setRequestHeader('X-Upload-Ticket', upTicket);
        x.setRequestHeader('Content-Type', 'application/octet-stream');
        x.upload.onprogress = function(e){
          if (!e.lengthComputable) return;
          mark(it, 'run', Math.round(e.loaded / e.total * 100) + ' %');
          setBar(sent + e.loaded);
        };
        x.onload = function(){
          var j = {};
          try { j = JSON.parse(x.responseText); } catch(err) {}
          sent += it.f.size;
          if (x.status === 200 && j.ok) { ok++; mark(it, 'ok', fmtB(it.f.size), 'check'); upExpire = Date.now() + upTtl - 30000; }
          else if (x.status === 409) { skipped++; mark(it, 'skip', j.error || 'déjà présent'); }
          else if (j.code === 'locked') {
            failed++; upTicket = null; cfg.unlocked = false; mark(it, 'bad', 'accès verrouillé');
            return finish('accès verrouillé : déverrouille puis rouvre « Envoyer »');
          }
          else if (j.code === 'ticket') {
            failed++; upTicket = null; mark(it, 'bad', 'session expirée');
            return finish('session d’envoi expirée (rouvre « Envoyer »)');
          }
          else { failed++; mark(it, 'bad', j.error || ('erreur ' + x.status)); }
          setBar(sent); next();
        };
        x.onabort = function(){ mark(it, 'bad', 'arrêté'); next(); };
        x.onerror = function(){ failed++; mark(it, 'bad', 'échec réseau'); finish('connexion perdue'); };
        x.send(it.f);
      };
      next();
    };
  }

