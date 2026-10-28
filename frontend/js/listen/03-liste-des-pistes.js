  /* ----- liste des pistes ----- */
  function buildList(){
    var box = $('l-list');
    box.textContent = '';
    var io = 'IntersectionObserver' in window ? new IntersectionObserver(function(es){
      es.forEach(function(e){
        if (!e.isIntersecting) return;
        io.unobserve(e.target);
        var i = +e.target.dataset.i;
        getInfo(i).then(function(j){ showDur(i, j && j.duration); });
      });
    }, {root: box, rootMargin: '120px'}) : null;
    T.forEach(function(t, i){
      var b = document.createElement('button');
      b.type = 'button'; b.className = 'ltrack'; b.dataset.i = i;
      var num = document.createElement('span'); num.className = 'num';
      var nn = document.createElement('span'); nn.className = 'n'; nn.textContent = i + 1;
      var eq = document.createElement('span'); eq.className = 'eqi'; eq.innerHTML = I.eq || '';
      num.appendChild(nn); num.appendChild(eq);
      var tn = document.createElement('span'); tn.className = 'tn'; tn.textContent = t.n;
      var td = document.createElement('span'); td.className = 'td';
      var te = document.createElement('span'); te.className = 'te'; te.textContent = t.e;
      b.appendChild(num); b.appendChild(tn); b.appendChild(td); b.appendChild(te);
      b.addEventListener('click', function(){ playIndex(i); });
      box.appendChild(b); rows.push(b);
      if (io) io.observe(b);
    });
  }
  function markCurrent(){
    if (curRow) { curRow.classList.remove('cur', 'playing'); curRow.removeAttribute('aria-current'); }
    curRow = rows[idx] || null;
    if (curRow) { curRow.classList.add('cur'); curRow.setAttribute('aria-current', 'true'); }
    renderPlayRow();
  }
  function renderPlayRow(){ if (curRow) curRow.classList.toggle('playing', !a.paused && !a.ended); }
  // fait défiler la liste elle-même (jamais la page) pour montrer la piste courante
  function reveal(){
    var box = $('l-list'), r = rows[idx];
    if (!box || !r) return;
    window.requestAnimationFrame(function(){
      box.scrollTop = Math.max(0, r.offsetTop - (box.clientHeight - r.offsetHeight) / 2);
    });
  }

