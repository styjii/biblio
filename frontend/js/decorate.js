(function(){
  function fmt(s){
    s = Math.floor(s);
    var h = Math.floor(s / 3600), m = Math.floor(s % 3600 / 60), x = s % 60;
    var mm = h ? ('0' + m).slice(-2) : String(m);
    return (h ? h + ':' : '') + mm + ':' + ('0' + x).slice(-2);
  }
  function load(key){
    try { return JSON.parse(localStorage.getItem('vl:pos:' + key)); }
    catch(e) { return null; }
  }
  function bar(el, t, d){
    var b = el.querySelector('.bar');
    if (!b || !d || !t) return;
    b.hidden = false;
    b.firstElementChild.style.width = Math.min(100, t / d * 100) + '%';
  }
  var items = document.querySelectorAll('[data-key]');
  var io = 'IntersectionObserver' in window ? new IntersectionObserver(function(es){
    es.forEach(function(e){
      if (!e.isIntersecting) return;
      io.unobserve(e.target);
      var el = e.target;
      fetch('/meta?f=' + el.dataset.f)
        .then(function(r){ return r.json(); })
        .then(function(j){
          if (!j.duration) return;
          var d = el.querySelector('.dur');
          if (d) { d.textContent = fmt(j.duration); d.hidden = false; }
          var s = load(el.dataset.key);
          if (s) bar(el, s.t, s.d || j.duration);
        }).catch(function(){});
    });
  }, {rootMargin: '200px'}) : null;
  items.forEach(function(el){
    var s = load(el.dataset.key);
    if (s && s.d) bar(el, s.t, s.d);
    if (io) io.observe(el);
  });
})();
