/* ---------- Progression, repère du sommaire, position de lecture ---------- */
var curIdx = -1, ticking = false, saveT = 0, posKey = 'md-pos:' + cfg.q;
function update(){
  ticking = false;
  var max = sc.scrollHeight - sc.clientHeight;
  bar.style.width = (max > 0 ? sc.scrollTop / max * 100 : 100) + '%';
  if (!hEls.length) return;
  var limit = sc.getBoundingClientRect().top + 40, cur = -1, i;
  for (i = 0; i < hEls.length; i++) {
    if (hEls[i].getBoundingClientRect().top <= limit) cur = i; else break;
  }
  if (cur !== curIdx) {
    curIdx = cur;
    tocLinks.forEach(function(a, k){ a.classList.toggle('on', k === cur); });
    var a = tocLinks[cur];
    if (a && tocNav.offsetParent !== null) {
      if (a.offsetTop < tocNav.scrollTop + 40 || a.offsetTop + a.offsetHeight > tocNav.scrollTop + tocNav.clientHeight - 20) {
        tocNav.scrollTop = Math.max(0, a.offsetTop - tocNav.clientHeight / 3);
      }
    }
  }
}
sc.addEventListener('scroll', function(){
  if (!ticking) { ticking = true; requestAnimationFrame(update); }
  clearTimeout(saveT);
  saveT = setTimeout(function(){
    var h = sc.scrollHeight;
    store(posKey, String(h > 0 ? (sc.scrollTop / h).toFixed(4) : 0));
  }, 400);
}, {passive: true});
window.addEventListener('resize', update);

