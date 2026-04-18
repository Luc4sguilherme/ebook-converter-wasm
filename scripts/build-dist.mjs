#!/usr/bin/env node
/**
 * build-dist.mjs — Build production bundles for Node.js and browser.
 *
 * Creates:
 *   dist/
 *     node/
 *       ebook-convert.mjs       — ESM entry for Node.js
 *       ebook-convert.cjs       — CJS entry for Node.js
 *       ebook-convert-native.js — Emscripten glue (copied)
 *       ebook-convert-native.wasm
 *       calibre-python.zip
 *       pdftohtml.cjs + pdftohtml.wasm (when SINGLE_FILE=0)
 *       pdfinfo.cjs + pdfinfo.wasm (when SINGLE_FILE=0)
 *     browser/
 *       ebook-convert.mjs       — ESM entry for browser
 *       worker.mjs              — Web Worker bundle
 *       ebook-convert-native.js — Emscripten glue (copied)
 *       ebook-convert-native.wasm
 *       calibre-python.zip
 *       pdftohtml.js + pdftohtml.wasm (when SINGLE_FILE=0)
 *       pdfinfo.js + pdfinfo.wasm (when SINGLE_FILE=0)
 *
 * Usage:
 *   node scripts/build-dist.mjs [--no-minify]
 */

import { build } from 'esbuild';
import { cpSync, mkdirSync, existsSync, rmSync, writeFileSync, readdirSync, statSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = resolve(__dirname, '..');
const SRC_JS = join(ROOT, 'src', 'js');
const DEV_DIST = join(ROOT, 'dist');
const DIST = join(ROOT, 'dist');
const NODE_OUT = join(DIST, 'node');
const BROWSER_OUT = join(DIST, 'browser');

const noMinify = process.argv.includes('--no-minify');
const minify = !noMinify;

function ensureDir(dir) {
    mkdirSync(dir, { recursive: true });
}

function copyIfExists(src, dest) {
    if (existsSync(src)) {
        cpSync(src, dest);
        return true;
    }
    console.warn(`  WARN: ${src} not found, skipping`);
    return false;
}

console.log('=== Building production bundles ===\n');

for (const dir of [NODE_OUT, BROWSER_OUT]) {
    ensureDir(dir);

    for (const f of readdirSync(dir)) {
        if (f.endsWith('.mjs') || f.endsWith('.mjs.map') || f.endsWith('.d.ts')
            || f === 'ebook-convert.cjs') {
            rmSync(join(dir, f));
        }
    }
}

console.log('>>> Node.js ESM bundle');
await build({
    entryPoints: [join(SRC_JS, 'ebook-convert.js')],
    outfile: join(NODE_OUT, 'ebook-convert.mjs'),
    bundle: true,
    format: 'esm',
    platform: 'node',
    target: 'node18',
    minify,
    sourcemap: true,
    external: ['pyodide'],
    banner: {
        js: '// ebook-converter-wasm — Node.js ESM build\n'
            + '// https://github.com/Luc4sguilherme/ebook-converter-wasm\n',
    },
    define: {
        'globalThis.__CALIBRE_WASM_PLATFORM__': '"node"',
    },
});
console.log('  ebook-convert.mjs');

console.log('>>> Node.js CJS wrapper');
const cjsWrapper = `// ebook-converter-wasm — Node.js CJS compatibility wrapper
'use strict';

const { createRequire } = require('node:module');
const req = createRequire(__filename);

// Re-export the ESM module via dynamic import
let _mod;
async function load() {
    if (!_mod) {
        _mod = await import('./ebook-convert.mjs');
    }
    return _mod;
}

class EbookConverter {
    constructor(config) {
        this._config = config;
        this._inner = null;
    }

    async init(onProgress) {
        const mod = await load();
        this._inner = new mod.EbookConverter(this._config);
        return this._inner.init(onProgress);
    }

    async convert(inputData, inputName, outputFormat, options) {
        if (!this._inner) throw new Error('Call init() first');
        return this._inner.convert(inputData, inputName, outputFormat, options);
    }

    getSupportedInputFormats() {
        if (!this._inner) return [];
        return this._inner.getSupportedInputFormats();
    }

    getSupportedOutputFormats() {
        if (!this._inner) return [];
        return this._inner.getSupportedOutputFormats();
    }

    getVersion() {
        if (!this._inner) return { calibreWasm: '0.1.0' };
        return this._inner.getVersion();
    }

    async destroy() {
        if (this._inner) return this._inner.destroy();
    }
}

module.exports = { EbookConverter };
module.exports.default = { EbookConverter };
`;
writeFileSync(join(NODE_OUT, 'ebook-convert.cjs'), cjsWrapper);
console.log('  ebook-convert.cjs');

console.log('>>> Browser ESM bundle');
await build({
    entryPoints: [join(SRC_JS, 'ebook-convert.js')],
    outfile: join(BROWSER_OUT, 'ebook-convert.mjs'),
    bundle: true,
    format: 'esm',
    platform: 'browser',
    target: ['es2020', 'chrome90', 'firefox90', 'safari15'],
    minify,
    sourcemap: true,
    external: ['pyodide', 'node:*'],
    banner: {
        js: '// ebook-converter-wasm — Browser ESM build\n'
            + '// https://github.com/Luc4sguilherme/ebook-converter-wasm\n',
    },
    define: {
        'globalThis.__CALIBRE_WASM_PLATFORM__': '"browser"',
    },
});
console.log('  ebook-convert.mjs');

console.log('>>> Browser Worker bundle');
await build({
    entryPoints: [join(SRC_JS, 'worker.js')],
    outfile: join(BROWSER_OUT, 'worker.mjs'),
    bundle: true,
    format: 'esm',
    platform: 'browser',
    target: ['es2020', 'chrome90', 'firefox90', 'safari15'],
    minify,
    sourcemap: true,
    external: ['pyodide', 'node:*'],
    banner: {
        js: '// ebook-converter-wasm — Web Worker bundle\n',
    },
    define: {
        'globalThis.__CALIBRE_WASM_PLATFORM__': '"browser"',
    },
});
console.log('  worker.mjs');

console.log('>>> Copying binary assets');

const typesFile = join(ROOT, 'src', 'types', 'ebook-convert.d.ts');
copyIfExists(typesFile, join(NODE_OUT, 'ebook-convert.d.ts'));
copyIfExists(typesFile, join(BROWSER_OUT, 'ebook-convert.d.ts'));
console.log('  ebook-convert.d.ts → node/ + browser/');

const sharedAssets = [
    'ebook-convert-native.js',
    'ebook-convert-native.wasm',
    'calibre-python.zip',
];

for (const file of sharedAssets) {
    const src = join(DEV_DIST, file);
    copyIfExists(src, join(NODE_OUT, file));
    copyIfExists(src, join(BROWSER_OUT, file));
    console.log(`  ${file} → node/ + browser/`);
}

const nodeAssets = [
    'pdftohtml.cjs',
    'pdftohtml.wasm',
    'pdfinfo.cjs',
    'pdfinfo.wasm',
];

for (const file of nodeAssets) {
    copyIfExists(join(DEV_DIST, file), join(NODE_OUT, file));
    console.log(`  ${file} → node/`);
}

const browserAssets = [
    'pdftohtml.js',
    'pdftohtml.wasm',
    'pdfinfo.js',
    'pdfinfo.wasm',
];

for (const file of browserAssets) {
    copyIfExists(join(DEV_DIST, file), join(BROWSER_OUT, file));
    console.log(`  ${file} → browser/`);
}

console.log('\n=== Build complete ===\n');

for (const [label, dir] of [['Node.js', NODE_OUT], ['Browser', BROWSER_OUT]]) {
    const files = readdirSync(dir).sort();
    console.log(`${label} (${dir}):`);
    let total = 0;
    for (const f of files) {
        const size = statSync(join(dir, f)).size;
        total += size;
        const sizeStr = size > 1024 * 1024
            ? `${(size / 1024 / 1024).toFixed(1)}MB`
            : `${(size / 1024).toFixed(1)}KB`;
        console.log(`  ${f.padEnd(30)} ${sizeStr}`);
    }
    const totalStr = total > 1024 * 1024
        ? `${(total / 1024 / 1024).toFixed(1)}MB`
        : `${(total / 1024).toFixed(1)}KB`;
    console.log(`  ${'TOTAL'.padEnd(30)} ${totalStr}`);
    console.log('');
}
