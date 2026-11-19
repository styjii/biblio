/** Ordre des images : celui de la liste du dossier (tri choisi dans la liste, mémorisé sous « fl:sort »), les fichiers cachés
    n'étant parcourus que si la liste les affiche. Même règle que ListSort (frontend/js/browse/00-tri.js) : valeur inconnue en dernier,
    égalité départagée par le nom. */
class ImageOrder {
  static sorted(items, current) {
    let key = 'name';
    let dir = 'asc';
    let showHidden = false;
    try {
      const [savedKey, savedDir] = (localStorage.getItem('fl:sort') ?? '').split(':');
      if (['name', 'date', 'size', 'type'].includes(savedKey)) { key = savedKey; dir = savedDir === 'desc' ? 'desc' : 'asc'; }
      showHidden = localStorage.getItem('fl:hidden') === '1';
    } catch { /* tri par nom */ }
    const sign = dir === 'asc' ? 1 : -1;
    const value = (item) => ({date: item.m, size: item.b, type: item.e})[key];
    const byName = (a, b) => a.o - b.o;
    const compare = (a, b) => {
      if (key === 'name') return sign * byName(a, b);
      const x = value(a);
      const y = value(b);
      if (x === y) return byName(a, b);
      return sign * (typeof x === 'string' ? x.localeCompare(y) : x - y);
    };
    return items.filter((item) => showHidden || !item.n.startsWith('.') || item.f === current).sort(compare);
  }
}
