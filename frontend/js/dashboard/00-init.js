/* Tableau de bord : appareils connectés, mémoire et disques, historique d'activité.
   Les fichiers de ce dossier forment un seul script (concaténés dans l'ordre) : celui-ci ouvre la fonction, le dernier la ferme. */
(() => {
  const HEADERS = {'X-Requested-With': 'biblio'};
  const config = window.DCFG ?? {};                       // icônes et catégories d'activité (fournies par le serveur)
  const $ = (id) => document.getElementById(id);

  /** Crée un élément : `el('span', 'tag', 'texte')`. */
  const el = (tag, className, text) => {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined && text !== null) node.textContent = text;
    return node;
  };

  /** Lit du JSON ; une session verrouillée (401) recharge la page. */
  async function getJson(url) {
    const r = await fetch(url, {credentials: 'same-origin', cache: 'no-store'});
    if (r.status === 401) { location.reload(); return null; }
    return r.json();
  }

  /** Mise en forme des nombres, durées, tailles et dates (en français). */
  class Format {
    static percent(p) { return String(p).replace('.', ','); }

    static ago(seconds) {
      if (seconds === null) return 'pas vu depuis le démarrage';
      if (seconds < 5) return "à l'instant";
      if (seconds < 60) return `il y a ${seconds} s`;
      if (seconds < 3600) return `il y a ${Math.floor(seconds / 60)} min`;
      if (seconds < 86400) return `il y a ${Math.floor(seconds / 3600)} h`;
      return `il y a ${Math.floor(seconds / 86400)} j`;
    }

    static bytes(n) {
      for (const [unit, size] of [['Go', 1073741824], ['Mo', 1048576], ['Ko', 1024]]) {
        if (n >= size) {
          const value = n / size;
          return `${(value < 10 ? value.toFixed(1) : String(Math.round(value))).replace('.', ',')} ${unit}`;
        }
      }
      return `${Math.round(n)} o`;
    }

    static duration(seconds) {
      const s = Math.round(seconds);
      if (s < 60) return `${s} s`;
      const m = Math.floor(s / 60);
      if (m < 60) return `${m} min`;
      const minutes = m % 60;
      return `${Math.floor(m / 60)} h${minutes ? ` ${String(minutes).padStart(2, '0')}` : ''}`;
    }

    static metric(value, metric) {
      if (metric === 'bytes') return Format.bytes(value);
      return metric === 'seconds' ? Format.duration(value) : String(Math.round(value));
    }

    /** Borne « ronde » de l'axe vertical (4, 8, 12… actions ; 1, 2, 5, 10 × une unité lisible sinon). */
    static niceMax(value, metric) {
      if (!(value > 0)) return metric === 'actions' ? 4 : 1;
      if (metric === 'actions') return Math.max(4, Math.ceil(value / 4) * 4);
      let unit;
      if (metric === 'bytes') unit = [1073741824, 1048576, 1024].find((u) => value >= u) ?? 1;
      else unit = [3600, 60].find((u) => value >= u) ?? 1;
      const x = value / unit;
      const power = 10 ** Math.floor(Math.log10(x));
      const mantissa = x / power;
      return (mantissa <= 1 ? 1 : mantissa <= 2 ? 2 : mantissa <= 5 ? 5 : 10) * power * unit;
    }

    static fixed(x) { return x.toFixed(1); }
  }
