(function(){
'use strict';
var cfg = window.MDCFG, EXT = cfg.exts, ICO = cfg.ico || {};
var src = String(cfg.doc || '').replace(/\r\n?/g, '\n');
function $(id){ return document.getElementById(id); }
function esc(s){
  return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}
function store(k, v){
  try { if (v === undefined) return localStorage.getItem(k); localStorage.setItem(k, v); } catch(e) {}
  return null;
}

