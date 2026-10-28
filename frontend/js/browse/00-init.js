(function(){
  var cfg = window.FLCFG, ICO = window.ICO;
  var body = document.body;
  var active = 'all';
  try { if (localStorage.getItem('fl:hidden') === '1') body.classList.add('show-hidden'); } catch(e) {}

  function visible(el){
    return !el.hidden && (!el.classList.contains('dot') || body.classList.contains('show-hidden'));
  }
  function refresh(){
    var shown = 0, per = {};
    document.querySelectorAll('.section').forEach(function(s){
      var g = s.dataset.group, n = 0;
      s.querySelectorAll('[data-name]').forEach(function(el){ if (visible(el)) n++; });
      s.querySelector('.count').textContent = n;
      var off = g !== 'folders' && active !== 'all' && g !== active;
      s.classList.toggle('off', off);
      s.hidden = n === 0;
      if (g !== 'folders') per[g] = n;
      if (!off) shown += n;
    });
    document.querySelectorAll('.fchip').forEach(function(c){
      var g = c.dataset.g, n = 0;
      if (g === 'all') { Object.keys(per).forEach(function(k){ n += per[k]; }); }
      else { n = per[g] || 0; }
      c.querySelector('b').textContent = n;
      c.classList.toggle('on', g === active);
    });
    var none = document.getElementById('no-result');
    if (none) none.hidden = shown !== 0;
  }

  document.querySelectorAll('.fchip').forEach(function(c){
    c.addEventListener('click', function(){ active = c.dataset.g; refresh(); });
  });

  var hid = document.getElementById('toggle-hidden');
  if (hid) {
    hid.checked = body.classList.contains('show-hidden');
    hid.addEventListener('change', function(){
      body.classList.toggle('show-hidden', hid.checked);
      try { localStorage.setItem('fl:hidden', hid.checked ? '1' : '0'); } catch(e) {}
      refresh();
    });
  }

  var search = document.getElementById('search');
  if (search) {
    search.addEventListener('input', function(){
      var q = search.value.trim().toLowerCase();
      document.querySelectorAll('[data-name]').forEach(function(el){
        el.hidden = el.dataset.name.indexOf(q) === -1;
      });
      refresh();
    });
  }
  refresh();

