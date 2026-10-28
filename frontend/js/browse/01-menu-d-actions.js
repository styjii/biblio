  // ----- menu d'actions
  var OPTS = {
    watch:    {ic:'play',     t:'Regarder',           d:'Lire la vidéo',                        u:function(f){return '/watch?f='+f;}},
    pdf:      {ic:'file',     t:'Lire le PDF',        d:'Ouvrir dans le lecteur PDF',           u:function(f){return '/pdf?f='+f;}},
    view:     {ic:'eye',      t:'Lire',               d:'Affichage avec coloration syntaxique', u:function(f){return '/view?f='+f;}},
    edit:     {ic:'edit',     t:'Éditer',             d:'Éditeur de type Vim',                  u:function(f){return '/edit?f='+f;}, prot:true},
    preview:  {ic:'globe',    t:'Aperçu de la page',  d:'Afficher la page web rendue',          u:function(f){return '/preview?f='+f;}},
    mdview:   {ic:'book',     t:'Aperçu',             d:'Rendu Markdown, mis en page pour la lecture', u:function(f){return '/preview?f='+f;}},
    mdsrc:    {ic:'code',     t:'Source',             d:'Texte brut avec coloration syntaxique', u:function(f){return '/view?f='+f;}},
    listen:   {ic:'music',    t:'Écouter',            d:'Lecteur audio (aléatoire, répétition…)', u:function(f){return '/listen?f='+f;}},
    open:     {ic:'external', t:'Ouvrir',             d:'Afficher dans le navigateur',          u:function(f){return '/raw?f='+f;}},
    download: {ic:'download', t:'Télécharger',        d:'Enregistrer une copie',                u:function(f){return '/raw?dl=1&f='+f;}},
    rename:   {ic:'rename',   t:'Renommer',           d:'Changer le nom du fichier',            u:null, prot:true},
    del:      {ic:'trash',    t:'Supprimer',          d:'Supprimer définitivement',             u:null, danger:true, prot:true}
  };
  var BY = {
    video:['watch','open','download'], pdf:['pdf','open','download'], text:['view','edit','download'],
    web:['preview','view','edit','download'], image:['open','download'], audio:['listen','open','download'],
    binary:['download'], md:['mdview','mdsrc','edit','download']
  };
  var wrap = document.getElementById('sheet');
  var bodyEl = document.getElementById('sh-body');

  var upRunning = false, upDirty = false, upMin = false, upMinimize = null;
  function closeSheet(){
    var upShown = !document.getElementById('updlg').hidden;
    // Envoi en cours : fermer la feuille d'envoi la masque (l'envoi continue) au lieu de ne rien faire.
    if (upRunning && upShown && upMinimize) { upMinimize(); return; }
    var reload = upDirty && upShown && !upRunning;
    if (upShown) { upMin = false; document.getElementById('up-tab').hidden = true; }
    wrap.hidden = true; document.getElementById('newdlg').hidden = true; document.getElementById('deldlg').hidden = true;
    document.getElementById('rendlg').hidden = true; document.getElementById('edtdlg').hidden = true;
    document.getElementById('updlg').hidden = true; bodyEl.innerHTML = '';
    if (reload) location.reload();
  }
  // Feuille ouverte : la page derrière ne défile plus (la molette / le doigt ne font défiler que le menu).
  function lockScroll(){
    var root = document.documentElement, on = !wrap.hidden;
    if (on === root.classList.contains('noscroll')) return;
    root.style.paddingRight = on && window.innerWidth > root.clientWidth ? (window.innerWidth - root.clientWidth) + 'px' : '';
    root.classList.toggle('noscroll', on);
  }
  new MutationObserver(lockScroll).observe(wrap, {attributes: true, attributeFilter: ['hidden']});
  lockScroll();
  function esc(s){ return s.replace(/[&<>"']/g, function(c){ return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]; }); }

  function openMenu(a){
    var kind = a.dataset.kind, f = a.dataset.f;
    var list = (a.dataset.md === '1' ? BY.md : (BY[kind] || ['view','edit','download'])).filter(function(k){
      return !(cfg.readonly && k === 'edit');
    });
    if (cfg.canDelete) list.push('rename', 'del');
    document.getElementById('sh-title').textContent = a.dataset.title;
    document.getElementById('sh-sub').textContent = a.dataset.size;
    var ic = document.getElementById('sh-ico');
    ic.innerHTML = ICO[a.dataset.ico] || '';
    ic.className = 'ico ' + (a.dataset.icls || '');
    bodyEl.innerHTML = list.map(function(k){
      var o = OPTS[k];
      var desc = (o.prot && cfg.protect && !cfg.unlocked) ? 'Accès verrouillé' : o.d;
      return '<a class="opt' + (o.danger ? ' danger" data-del="1' : (k === 'rename' ? '" data-ren="1' : (k === 'edit' ? '" data-edt="1' : ''))) + '" href="' + (o.u ? o.u(f) : '#') + '"><span class="ico back">' + ICO[o.ic] + '</span>' +
        '<span class="text"><span class="name">' + esc(o.t) + '</span><div class="sub">' + esc(desc) + '</div></span>' +
        '<span class="go">' + ICO.chevron + '</span></a>';
    }).join('');
    var dl = bodyEl.querySelector('[data-del]');
    if (dl) dl.addEventListener('click', function(e){ e.preventDefault(); askDelete(a); });
    var rn = bodyEl.querySelector('[data-ren]');
    if (rn) rn.addEventListener('click', function(e){ e.preventDefault(); askRename(a); });
    var ed = bodyEl.querySelector('[data-edt]');
    if (ed) ed.addEventListener('click', function(e){
      if (cfg.protect && !cfg.unlocked) { e.preventDefault(); askEdit(a); }
    });
    document.getElementById('rendlg').hidden = true;
    document.getElementById('newdlg').hidden = true;
    document.getElementById('deldlg').hidden = true;
    document.getElementById('edtdlg').hidden = true;
    document.getElementById('sheet-main').hidden = false;
    wrap.hidden = false;
  }

