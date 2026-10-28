/* ---------- Navigation interne ---------- */
function fold(s){
  return s.toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g, '').replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');
}
function findEl(id){
  try { id = decodeURIComponent(id); } catch(e) {}
  var el = document.getElementById(id);
  if (el && art.contains(el)) return el;
  var key = fold(id);
  for (var i = 0; i < heads.length; i++) if (fold(heads[i].id) === key) return document.getElementById(heads[i].id);
  return null;
}
var reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
function goTo(el, smooth){
  var top = sc.scrollTop + el.getBoundingClientRect().top - sc.getBoundingClientRect().top - 14;
  sc.scrollTo({top: Math.max(0, top), behavior: smooth && !reduce ? 'smooth' : 'auto'});
}
document.addEventListener('click', function(e){
  var a = e.target.closest ? e.target.closest('a[href^="#"]') : null;
  if (!a || e.ctrlKey || e.metaKey || e.shiftKey) return;
  var el = findEl(a.getAttribute('href').slice(1));
  if (!el) return;
  e.preventDefault();
  goTo(el, true);
  try { history.replaceState(null, '', '#' + encodeURIComponent(el.id)); } catch(err) {}
  if (!wide.matches) closeToc();
});

