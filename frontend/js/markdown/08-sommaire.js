/* ---------- Sommaire ---------- */
var tocHeads = heads.filter(function(h){ return h.level <= 4; });
var tocBtn = $('md-toc-btn'), veil = $('md-veil'), wide = window.matchMedia('(min-width:1000px)');
if (tocHeads.length < 2) {
  tocNav.hidden = true;
  tocBtn.hidden = true;
} else {
  var minL = Math.min.apply(null, tocHeads.map(function(h){ return h.level; }));
  tocList.innerHTML = tocHeads.map(function(h){
    return '<a href="#' + esc(h.id) + '" data-id="' + esc(h.id) + '" style="--ind:' + (h.level - minL) + '">' + esc(h.text) + '</a>';
  }).join('');
}
var tocLinks = Array.prototype.slice.call(tocList.querySelectorAll('a'));
var hEls = tocHeads.map(function(h){ return document.getElementById(h.id); });
function syncTocBtn(){
  var on = wide.matches ? !document.body.classList.contains('toc-off') : tocNav.classList.contains('open');
  tocBtn.classList.toggle('on', on);
}
function closeToc(){ tocNav.classList.remove('open'); veil.hidden = true; syncTocBtn(); }
if (store('md-toc') === 'off') document.body.classList.add('toc-off');
syncTocBtn();
tocBtn.addEventListener('click', function(){
  if (wide.matches) {
    var off = document.body.classList.toggle('toc-off');
    store('md-toc', off ? 'off' : 'on');
  } else {
    var open = tocNav.classList.toggle('open');
    veil.hidden = !open;
  }
  syncTocBtn();
});
veil.addEventListener('click', closeToc);
(wide.addEventListener ? wide.addEventListener.bind(wide, 'change') : wide.addListener.bind(wide))(function(){ closeToc(); });

