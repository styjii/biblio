(() => {
  'use strict';
  const cfg = window.MDCFG;
  const EXT = cfg.exts; // extensions par type de fichier (pour résoudre les liens relatifs)
  const ICO = cfg.ico ?? {};
  const source = String(cfg.doc ?? '').replace(/\r\n?/g, '\n');
  const $ = (id) => document.getElementById(id);
  const esc = (s) => String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  const store = {
    // préférences de lecture (localStorage, silencieux si indisponible)
    get(key) {
      try {
        return localStorage.getItem(key);
      } catch {
        return null;
      }
    },
    set(key, value) {
      try {
        localStorage.setItem(key, value);
      } catch {
        /* préférence non mémorisée */
      }
    },
  };

  
