
/* ----- SharedWorker : un seul moteur pour toutes les pages ouvertes du site ----- */
let clients = [];                       // {port, seen} : une entrée par page connectée
const engine = new TransferEngine((view) => broadcast({type: 'state', view, clients: clients.length}));

function broadcast(message) {
  for (const {port} of clients) {
    try { port.postMessage(message); } catch { /* page déjà fermée */ }
  }
}

function prune() {                      // pages disparues sans prévenir : plus de signe de vie depuis 90 s
  const now = Date.now();
  clients = clients.filter(({seen}) => now - seen < 90_000);
}

onconnect = ({ports: [port]}) => {
  const me = {port, seen: Date.now()};
  clients.push(me);
  port.onmessage = ({data = {}}) => {
    me.seen = Date.now();
    switch (data.cmd) {
      case 'add': engine.add(data.files, data.rels, data.dest, data.over, data.max); break;
      case 'cancel': engine.cancel(); break;
      case 'clear': engine.clear(); break;
      case 'bye': clients = clients.filter((c) => c !== me); return;
    }
    if (data.cmd === 'hello' || data.cmd === 'ping') {
      prune();
      port.postMessage({type: 'state', view: engine.view(), clients: clients.length});
    }
  };
  port.start();
};
