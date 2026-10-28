  /* ----- ordre de lecture ----- */
  function rebuild(){
    var i, rest = [];
    if (shuffle) {
      for (i = 0; i < n; i++) if (i !== idx) rest.push(i);
      for (i = rest.length - 1; i > 0; i--) {
        var j = Math.floor(Math.random() * (i + 1)), t = rest[i];
        rest[i] = rest[j]; rest[j] = t;
      }
      order = [idx].concat(rest); pos = 0;
    } else {
      order = []; for (i = 0; i < n; i++) order.push(i);
      pos = idx;
    }
  }

