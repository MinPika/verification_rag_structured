// Smoke test for logs/viewer/*.html: renders every view and every trial section with a DOM stub.
// Usage: node tests/viewer_smoke.js logs/viewer/index.html
const fs = require('fs'), path = require('path');
const file = process.argv[2], base = path.dirname(file);
const html = fs.readFileSync(file, 'utf8');
let js = html.slice(html.indexOf('<script>\n') + 9, html.lastIndexOf('</script>'));
const els = {};
const mk = id => ({id, innerHTML: '', value: '', querySelector: () => null, querySelectorAll: () => [],
  set onchange(f) {}, set oninput(f) {}});
global.document = {getElementById: id => els[id] || (els[id] = mk(id)), addEventListener() {},
  querySelectorAll: () => []};
global.window = {}; global.location = {hash: ''}; global.history = {replaceState() {}};
global.fetch = u => Promise.resolve({json: () => JSON.parse(fs.readFileSync(path.join(base, u), 'utf8'))});
js = js.replace('render();\n', '') + `
(async () => {
  for (const v of VIEWS) { S.view = v; render(); }
  let n = 0;
  for (const t of D.trials) for (const sub of SUBS) {
    S = {...S, view: 'Trials', run: t.run, key: t.key, sub}; render(); await drawTrial(); n++;
  }
  console.log('ok', VIEWS.length, 'views', D.trials.length, 'trials', n, 'renders');
})().catch(e => { console.error('FAIL', e); process.exit(1); });`;
eval(js);
