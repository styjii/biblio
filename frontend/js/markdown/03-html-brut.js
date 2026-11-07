/** HTML brut dans le Markdown : lu dans un document inerte (DOMParser, rien ne s'exécute) ; seuls les balises et attributs sûrs sont gardés. */
class HtmlSanitizer {
  static TAGS = new Set(
    'a abbr b blockquote br caption center cite code col colgroup dd del details div dl dt em figcaption figure h1 h2 h3 h4 h5 h6 hr i img ins kbd li mark ol p picture pre q s small span strong sub summary sup table tbody td tfoot th thead tr u ul'.split(
      ' ',
    ),
  );
  static ATTRIBUTES = new Set('href src alt title width height align colspan rowspan open start valign'.split(' '));
  static DROPPED = new Set(
    'script style iframe object embed noscript template textarea svg math link meta form input button select audio video source'.split(' '),
  );
  static VOID = new Set(['br', 'hr', 'img', 'col']);
  static NUMERIC = new Set(['width', 'height', 'colspan', 'rowspan', 'start']);

  static clean(html) {
    const doc = new DOMParser().parseFromString(`<body>${html}</body>`, 'text/html');
    return HtmlSanitizer.walk(doc.body);
  }

  static walk(node) {
    let out = '';
    for (const child of node.childNodes) {
      if (child.nodeType === Node.TEXT_NODE) {
        out += esc(child.nodeValue);
        continue;
      }
      if (child.nodeType !== Node.ELEMENT_NODE) continue;
      const tag = child.tagName.toLowerCase();
      if (HtmlSanitizer.DROPPED.has(tag)) continue;
      const inner = HtmlSanitizer.VOID.has(tag) ? '' : HtmlSanitizer.walk(child);
      if (!HtmlSanitizer.TAGS.has(tag)) {
        out += inner;
        continue;
      }
      let attributes = '';
      let external = false;
      for (const attribute of child.attributes) {
        const name = attribute.name.toLowerCase();
        let value = attribute.value;
        if (!HtmlSanitizer.ATTRIBUTES.has(name)) continue;
        if (name === 'href' || name === 'src') {
          const resolved = LinkResolver.safeUrl(value, tag === 'img');
          if (!resolved) continue;
          if (resolved.ext && name === 'href') external = true;
          value = resolved.href;
        } else if (name === 'align') {
          if (!/^(?:left|right|center|justify)$/i.test(value)) continue;
        } else if (HtmlSanitizer.NUMERIC.has(name)) {
          if (!/^\d+%?$/.test(value)) continue;
        } else if (name === 'open') {
          value = '';
        }
        attributes += ` ${name}="${esc(value)}"`;
      }
      if (tag === 'a' && external) attributes += ' target="_blank" rel="noopener noreferrer"';
      if (tag === 'img') attributes += ' loading="lazy"';
      out += HtmlSanitizer.VOID.has(tag) ? `<${tag}${attributes}>` : `<${tag}${attributes}>${inner}</${tag}>`;
    }
    return out;
  }
}
