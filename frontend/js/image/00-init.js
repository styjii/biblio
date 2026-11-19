/* Visionneuse d'images (page /image). Les fichiers de ce dossier forment un seul script (concaténés dans l'ordre) : le dernier
   crée l'objet. Données : window.ICFG = {items: [{f, n, o, b, m, e}], current, back, key}, icônes : window.IICO. */
const cfg = window.ICFG;
const ICO = window.IICO ?? {};
const $ = (id) => document.getElementById(id);
const clamp = (value, min, max) => Math.min(max, Math.max(min, value));
