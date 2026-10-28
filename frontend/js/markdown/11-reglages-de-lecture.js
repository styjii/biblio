/* ---------- Réglages de lecture ---------- */
var fs = parseInt(store('md-fs') || '18', 10);
if (!(fs >= 14 && fs <= 26)) fs = 18;
function applyFs(){ art.style.setProperty('--mdfs', fs + 'px'); store('md-fs', String(fs)); update(); }
applyFs();
$('md-fs-down').addEventListener('click', function(){ if (fs > 14) { fs--; applyFs(); } });
$('md-fs-up').addEventListener('click', function(){ if (fs < 26) { fs++; applyFs(); } });
var ff = $('md-ff'), sans = store('md-ff') === 'sans';
function applyFf(){ art.classList.toggle('sans', sans); ff.textContent = sans ? 'Sans' : 'Serif'; ff.classList.toggle('on', sans); }
applyFf();
ff.addEventListener('click', function(){ sans = !sans; store('md-ff', sans ? 'sans' : 'serif'); applyFf(); update(); });
$('md-print').addEventListener('click', function(){ window.print(); });

