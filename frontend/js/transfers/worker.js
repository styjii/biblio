
/* ----- SharedWorker : un seul moteur pour toutes les pages ouvertes du site ----- */
var clients = [];                       // {port, seen} : une entrée par page connectée
var engine = TransferEngine(function (view) { broadcast({type: 'state', view: view, clients: clients.length}); });

function broadcast(msg) {
  clients.forEach(function (c) { try { c.port.postMessage(msg); } catch (e) {} });
}
function prune() {                      // pages disparues sans prévenir : plus de signe de vie depuis 90 s
  var now = Date.now();
  clients = clients.filter(function (c) { return now - c.seen < 90000; });
}

onconnect = function (ev) {
  var port = ev.ports[0], me = {port: port, seen: Date.now()};
  clients.push(me);
  port.onmessage = function (m) {
    var d = m.data || {};
    me.seen = Date.now();
    if (d.cmd === 'add') engine.add(d.files, d.rels, d.dest, d.over, d.max);
    else if (d.cmd === 'cancel') engine.cancel();
    else if (d.cmd === 'clear') engine.clear();
    else if (d.cmd === 'bye') { clients = clients.filter(function (c) { return c !== me; }); return; }
    if (d.cmd === 'hello' || d.cmd === 'ping') {
      prune();
      port.postMessage({type: 'state', view: engine.view(), clients: clients.length});
    }
  };
  port.start();
};
