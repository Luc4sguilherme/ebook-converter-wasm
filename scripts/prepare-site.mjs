#!/usr/bin/env node
/**
 * prepare-site.mjs — Assembles the public/ folder for GitHub Pages deployment.
 *
 * Structure produced:
 *   public/
 *     index.html              — redirect to examples/browser/
 *     coi-serviceworker.js    — injects COOP/COEP headers (required by Pyodide)
 *     dist/browser/           — built WASM/JS bundle
 *     examples/browser/       — demo UI
 */

import { cpSync, mkdirSync, rmSync, writeFileSync, existsSync } from 'node:fs';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = dirname(dirname(fileURLToPath(import.meta.url)));
const SITE = join(ROOT, 'public');

if (existsSync(SITE)) rmSync(SITE, { recursive: true });
mkdirSync(join(SITE, 'dist', 'browser'), { recursive: true });
mkdirSync(join(SITE, 'examples', 'browser'), { recursive: true });

cpSync(join(ROOT, 'dist', 'browser'), join(SITE, 'dist', 'browser'), { recursive: true });
cpSync(join(ROOT, 'examples', 'browser'), join(SITE, 'examples', 'browser'), { recursive: true });

const coiRes = await fetch(
    'https://cdn.jsdelivr.net/gh/gzuidhof/coi-serviceworker@master/coi-serviceworker.min.js'
);
writeFileSync(join(SITE, 'coi-serviceworker.js'), await coiRes.text());

writeFileSync(join(SITE, 'index.html'), `<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <meta http-equiv="refresh" content="0; url=examples/browser/">
  <title>ebook-converter-wasm</title>
</head>
<body>
  <p>Redirecting to <a href="examples/browser/">demo</a>…</p>
</body>
</html>
`);

console.log('Site prepared at public/');
