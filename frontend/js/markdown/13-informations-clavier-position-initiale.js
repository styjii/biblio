/* ---------- Informations, clavier, position initiale ---------- */
(function(){
  var c = art.cloneNode(true), words = 0;
  Array.prototype.forEach.call(c.querySelectorAll('figure.code,.anc'), function(x){ x.remove(); });
  try { words = (c.textContent.match(/[\p{L}\p{N}]+(?:['\u2019-][\p{L}\p{N}]+)*/gu) || []).length; }
  catch(e) { words = (c.textContent.match(/\S+/g) || []).length; }
  var min = Math.max(1, Math.round(words / 220));
  $('md-meta').textContent = 'Aper\u00e7u \u00b7 ' + cfg.label + ' \u00b7 ' + min + ' min de lecture \u00b7 ' + words.toLocaleString('fr-FR') + ' mots';
})();
document.addEventListener('keydown', function(e){
  if (e.ctrlKey || e.metaKey || e.altKey) return;
  var t = e.target && e.target.tagName;
  if (t === 'INPUT' || t === 'TEXTAREA') return;
  if (e.key === 't' && !tocBtn.hidden) tocBtn.click();
  else if (e.key === 'Escape' && tocNav.classList.contains('open')) closeToc();
});
sc.tabIndex = 0;
var start = location.hash.length > 1 ? findEl(location.hash.slice(1)) : null;
if (start) goTo(start, false);
else {
  var saved = parseFloat(store(posKey) || '0');
  if (saved > 0 && saved < 1) sc.scrollTop = saved * sc.scrollHeight;
}
update();
try { sc.focus({preventScroll: true}); } catch(e) {}
})();
