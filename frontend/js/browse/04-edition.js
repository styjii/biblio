  // ----- édition (déverrouillage requis ; aucun mot de passe n'est demandé ici : on indique seulement que c'est verrouillé)
  function askEdit(a){
    document.getElementById('edt-name').textContent = a.dataset.title;
    document.getElementById('sheet-main').hidden = true;
    document.getElementById('edtdlg').hidden = false;
  }
  document.getElementById('edtcancel').addEventListener('click', closeSheet);

  document.querySelectorAll('.fcard').forEach(function(a){
    a.addEventListener('click', function(e){
      var more = e.target.closest('.more');
      if (!more) {
        if (e.ctrlKey || e.metaKey || e.shiftKey || e.button) return;
        if (a.dataset.direct === '1') return;
      }
      e.preventDefault();
      openMenu(a);
    });
  });

  wrap.querySelectorAll('[data-close]').forEach(function(el){ el.addEventListener('click', closeSheet); });
  document.addEventListener('keydown', function(e){ if (e.key === 'Escape' && !wrap.hidden) closeSheet(); });

