/**
 * test-quality.mjs — Conversion quality tests.
 *
 * Each test covers a behavior where the WASM build used to differ from
 * calibre's own ebook-convert: lost or garbled text, lost metadata,
 * options that had no effect, broken output formats, etc.
 */
import assert from 'node:assert/strict';
import { execSync, fork } from 'node:child_process';
import { mkdtempSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { availableParallelism, tmpdir } from 'node:os';
import { join } from 'node:path';
import { after, before, describe, test } from 'node:test';
import { fileURLToPath } from 'node:url';
import { inflateSync } from 'node:zlib';

const POOL_SIZE = Math.max(1, Math.min(availableParallelism() - 1, 4));
const workers = [];
const idle = [];
const waiting = [];
let nextId = 0;

const workerPath = fileURLToPath(new URL('./helpers/converter-worker.mjs', import.meta.url));

function createWorker() {
    return new Promise((resolve, reject) => {
        const child = fork(workerPath, [], { stdio: ['ignore', 'ignore', 'inherit', 'ipc'] });
        const pending = new Map();
        child._pending = pending;
        child.on('message', (msg) => {
            if (msg.type === 'ready') return resolve(child);
            const p = pending.get(msg.id);
            if (!p) return;
            pending.delete(msg.id);
            if (msg.type === 'result') {
                p.resolve(Buffer.from(msg.data, 'base64'));
            } else {
                p.reject(new Error(msg.message));
            }
        });
        child.on('error', (err) => {
            for (const [, p] of pending) p.reject(err);
            pending.clear();
            reject(err);
        });
        child.on('exit', (code) => {
            for (const [, p] of pending) p.reject(new Error(`Worker exited with code ${code}`));
            pending.clear();
        });
    });
}

function acquire() {
    const w = idle.pop();
    if (w) return Promise.resolve(w);
    return new Promise((res) => waiting.push(res));
}

function release(w) {
    const next = waiting.shift();
    if (next) next(w);
    else idle.push(w);
}

async function convert(inputData, inputName, outputFile, options = {}) {
    const worker = await acquire();
    try {
        const id = nextId++;
        return await new Promise((resolve, reject) => {
            worker._pending.set(id, { resolve, reject });
            worker.send({
                type: 'convert',
                id,
                inputData: Buffer.from(inputData).toString('base64'),
                inputName,
                outputFile,
                options,
            });
        });
    } finally {
        release(worker);
    }
}

const fixture = (name) => readFileSync(`tests/fixtures/${name}`);

/** Concatenated contents of the entries of a ZIP based output matching the patterns */
function unzipText(buf, ...patterns) {
    const tmpDir = mkdtempSync(join(tmpdir(), 'quality-'));
    const zipPath = join(tmpDir, 'out.zip');
    writeFileSync(zipPath, buf);
    try {
        const pats = patterns.map((p) => `"${p}"`).join(' ');
        return execSync(`unzip -p "${zipPath}" ${pats} 2>/dev/null || true`, {
            maxBuffer: 50 * 1024 * 1024, encoding: 'utf-8',
        });
    } finally {
        rmSync(tmpDir, { recursive: true, force: true });
    }
}

function unzipNames(buf) {
    const tmpDir = mkdtempSync(join(tmpdir(), 'quality-'));
    const zipPath = join(tmpDir, 'out.zip');
    writeFileSync(zipPath, buf);
    try {
        return execSync(`unzip -Z1 "${zipPath}"`, { encoding: 'utf-8' }).split('\n').filter(Boolean);
    } finally {
        rmSync(tmpDir, { recursive: true, force: true });
    }
}

/** Decompressed content streams of a PDF, as latin1 text */
function pdfContent(buf) {
    const raw = buf.toString('latin1');
    const parts = [];
    for (const m of raw.matchAll(/stream\r?\n([\s\S]*?)\r?\nendstream/g)) {
        const data = Buffer.from(m[1], 'latin1');
        try {
            parts.push(inflateSync(data).toString('latin1'));
        } catch {
            parts.push(m[1]);
        }
    }
    return parts.join('\n');
}

/** Record types of the EXTH header of a MOBI/AZW3 file */
function exthRecordTypes(buf) {
    const rec0Start = buf.readUInt32BE(78);
    const rec0End = buf.readUInt32BE(86);
    const rec0 = buf.subarray(rec0Start, rec0End);
    const pos = rec0.indexOf('EXTH');
    if (pos < 0) return [];
    const count = rec0.readUInt32BE(pos + 8);
    const types = [];
    let p = pos + 12;
    for (let i = 0; i < count; i++) {
        types.push(rec0.readUInt32BE(p));
        p += rec0.readUInt32BE(p + 4);
    }
    return types;
}

const opfMetadata = (epub) => unzipText(epub, '*.opf');

describe('conversion quality', { concurrency: POOL_SIZE }, () => {
    before(async () => {
        const inits = Array.from({ length: POOL_SIZE }, () => createWorker());
        workers.push(...(await Promise.all(inits)));
        idle.push(...workers);
    });

    after(async () => {
        for (const w of workers) w.send({ type: 'exit' });
        await Promise.all(workers.map((w) => new Promise((r) => w.on('exit', r))));
    });

    test('RB input keeps all of the text', async () => {
        const [fromRb, fromEpub] = await Promise.all([
            convert(fixture('test.rb'), 'test.rb', 'rb.txt'),
            convert(fixture('test.epub'), 'test.epub', 'epub.txt'),
        ]);
        const text = fromRb.toString('utf-8');
        assert.match(text, /Calibre is an open source e-book management tool/);
        assert.match(text, /Where to get help/);
        assert.ok(text.length > 0.9 * fromEpub.length,
            `RB text is too short: ${text.length} vs ${fromEpub.length} characters`);
    });

    test('MOBI input decodes UTF-8 text', async () => {
        const text = (await convert(fixture('test.mobi'), 'test.mobi', 'mobi.txt')).toString('utf-8');
        assert.match(text, /Copyright © 2010/);
        assert.match(text, /Apple’s macOS/);
        assert.doesNotMatch(text, /Â©|â€/, 'UTF-8 text decoded as cp1252');
    });

    test('malformed HTML is parsed with the HTML 5 algorithm', async () => {
        const html = '<html><head><title>Tag soup</title></head><body>' +
            '<p>First <b>bold<p>Second &eacute; para<br>line after break' +
            '<table><tr><td>Cell one<td>Cell two</table>' +
            '<P>Last &amp; final</body></html>';
        const epub = await convert(Buffer.from(html), 'soup.html', 'soup.epub');
        const markup = unzipText(epub, '*.html', '*.xhtml');
        assert.match(markup, /Second é para/);
        assert.match(markup, /line after break/);
        assert.match(markup, /<td[^>]*>Cell two<\/td>/);
        assert.match(markup, /Last &amp; final/);
        assert.match(markup, /<b[^>]*>bold<\/b>/);
        assert.doesNotMatch(markup, /&lt;p&gt;|&lt;b&gt;/, 'markup was escaped into text');
    });

    test('the encoding of non UTF-8 text is detected', async () => {
        const text = 'Ação e coração — “aspas” em São Paulo.\n\nEducação pública é essencial.\n';
        // Encode as windows-1252: latin-1 code points map to themselves
        const cp1252 = { '—': 0x97, '“': 0x93, '”': 0x94 };
        const bytes = Buffer.from([...text].map((ch) => cp1252[ch] ?? ch.charCodeAt(0)));
        const epub = await convert(bytes, 'latin.txt', 'latin.epub');
        const markup = unzipText(epub, '*.html', '*.xhtml');
        assert.match(markup, /Ação e coração — “aspas” em São Paulo/);
        assert.doesNotMatch(markup, /�/);
    });

    for (const fmt of ['docx', 'fb2', 'htmlz', 'odt', 'pdf', 'rtf']) {
        test(`metadata is read from ${fmt.toUpperCase()} input`, async () => {
            const opf = opfMetadata(await convert(fixture(`test.${fmt}`), `test.${fmt}`, `meta_${fmt}.epub`));
            assert.match(opf, /<dc:title[^>]*>Quick Start Guide<\/dc:title>/);
            assert.match(opf, /<dc:creator[^>]*>John Schember<\/dc:creator>/);
        });
    }

    test('language codes are canonicalized', async () => {
        // The OPF of the fixture has <dc:language>C</dc:language>
        const opf = opfMetadata(await convert(fixture('test.htmlz'), 'test.htmlz', 'lang.epub'));
        assert.match(opf, /<dc:language>en<\/dc:language>/);
    });

    test('options are converted to the type of the option', async () => {
        const epub = await convert(fixture('test.epub'), 'test.epub', 'opts.epub', {
            'change-justification': 'left',
            base_font_size: '14',
            title: "O'Título",
        });
        const css = unzipText(epub, '*.css');
        assert.doesNotMatch(css, /text-align:\s*justify/);
        assert.match(opfMetadata(epub), /<dc:title[^>]*>O'Título<\/dc:title>/);
    });

    test('device output profiles are available', async () => {
        const [plain, kindle] = await Promise.all([
            convert(fixture('test.mobi'), 'test.mobi', 'profile_default.epub'),
            convert(fixture('test.mobi'), 'test.mobi', 'profile_kindle.epub', { output_profile: 'kindle_pw3' }),
        ]);
        assert.notEqual(unzipText(plain, '*.css'), unzipText(kindle, '*.css'),
            'the output profile had no effect on font size mapping');
    });

    test('file names with quotes work', async () => {
        const name = 'O\'Reilly "draft".epub';
        const txt = await convert(fixture('test.epub'), name, 'O\'Reilly "draft".txt');
        assert.match(txt.toString('utf-8'), /Calibre Quick Start Guide/);
    });

    for (const fmt of ['mobi', 'azw3']) {
        test(`${fmt.toUpperCase()} output has a cover thumbnail`, async () => {
            const out = await convert(fixture('test.epub'), 'test.epub', `thumb.${fmt}`);
            assert.ok(exthRecordTypes(out).includes(202), 'no EXTH thumbnail offset record');
        });
    }

    test('PDF output keeps typographic characters and the book styles', async () => {
        const content = pdfContent(await convert(fixture('test.epub'), 'test.epub', 'typo.pdf'));
        // ’ and – in the WinAnsi encoding of the PDF core fonts
        assert.ok(content.includes('\x92'), 'right single quote replaced');
        assert.ok(content.includes('\x96'), 'en dash replaced');
        // fpdf2 default heading and bullet colors (dark red) are not used
        assert.doesNotMatch(content, /0\.5882 0 0 rg|0\.7451 0 0 rg/);
    });

    test('PDF output renders documents with tables', async () => {
        const html = '<html><body><h1>Report</h1><table>' +
            '<tr><th>Name</th><th>Value</th></tr>' +
            '<tr><td>first<br/>line</td><td><b>bold</b> and plain</td></tr>' +
            '</table><p>After the table</p></body></html>';
        const content = pdfContent(await convert(Buffer.from(html), 'table.html', 'table.pdf'));
        for (const text of ['Report', 'first line', 'bold and plain', 'After the table']) {
            assert.ok(content.includes(text), `missing "${text}"`);
        }
    });

    test('KEPUB output uses calibre\'s kepubify', async () => {
        const kepub = await convert(fixture('test.epub'), 'test.epub', 'test.kepub');
        const markup = unzipText(kepub, '*.html', '*.xhtml');
        assert.match(markup, /<span class="koboSpan" id="kobo\.\d+\.\d+">/);
        assert.match(markup, /id="book-columns"/);
        assert.ok(unzipNames(kepub).some((n) => n.endsWith('kobo.js')));
    });

    test('HTML output is a single self contained file', async () => {
        const png = 'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==';
        const html = '<html><head><style>p.note { color: #336699; font-style: italic }</style></head><body>' +
            `<p class="note">Styled text</p><p><img src="data:image/png;base64,${png}" alt="dot"/></p></body></html>`;
        const out = (await convert(Buffer.from(html), 'page.html', 'single.html')).toString('utf-8');
        assert.match(out, /Styled text/);
        assert.match(out, /<style[^>]*>[\s\S]*font-style:\s*italic/);
        assert.doesNotMatch(out, /<link[^>]+stylesheet/i);
        assert.match(out, /<img[^>]+src="data:image\/png;base64,/);
    });
});
