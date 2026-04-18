import assert from 'node:assert/strict';
import { fork } from 'node:child_process';
import { existsSync, readFileSync } from 'node:fs';
import { availableParallelism } from 'node:os';
import { after, before, describe, test } from 'node:test';
import { fileURLToPath } from 'node:url';

const POOL_SIZE = Math.max(1, availableParallelism() - 1);
const workers = [];
const idle = [];
const waiting = [];
let nextId = 0;

const workerPath = fileURLToPath(new URL('./helpers/converter-worker.mjs', import.meta.url));

function createWorker() {
    return new Promise((resolve, reject) => {
        const child = fork(workerPath, [], { stdio: 'inherit' });
        const pending = new Map();
        child._pending = pending;
        child.on('message', (msg) => {
            if (msg.type === 'ready') return resolve(child);
            const p = pending.get(msg.id);
            if (!p) return;
            pending.delete(msg.id);
            if (msg.type === 'result') {
                p.resolve(new Uint8Array(Buffer.from(msg.data, 'base64')));
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

function convert(worker, inputData, inputName, outputFile) {
    const id = nextId++;
    return new Promise((resolve, reject) => {
        worker._pending.set(id, { resolve, reject });
        worker.send({
            type: 'convert',
            id,
            inputData: Buffer.from(inputData).toString('base64'),
            inputName,
            outputFile,
        });
    });
}

const FIXTURES_DIR = 'tests/fixtures';

function loadFixture(filename) {
    const path = `${FIXTURES_DIR}/${filename}`;
    if (!existsSync(path)) return null;
    return readFileSync(path);
}

const fixtures = {
    azw3:  { data: loadFixture('test.azw3'),  name: 'test.azw3' },
    docx:  { data: loadFixture('test.docx'),  name: 'test.docx' },
    epub:  { data: loadFixture('test.epub'),  name: 'test.epub' },
    fb2:   { data: loadFixture('test.fb2'),   name: 'test.fb2' },
    html:  { data: loadFixture('test.html'),  name: 'test.html' },
    htmlz: { data: loadFixture('test.htmlz'), name: 'test.htmlz' },
    lrf:   { data: loadFixture('test.lrf'),   name: 'test.lrf' },
    mobi:  { data: loadFixture('test.mobi'),  name: 'test.mobi' },
    odt:   { data: loadFixture('test.odt'),   name: 'test.odt' },
    pdb:   { data: loadFixture('test.pdb'),   name: 'test.pdb' },
    pdf:   { data: loadFixture('test.pdf'),   name: 'test.pdf' },
    rb:    { data: loadFixture('test.rb'),    name: 'test.rb' },
    rtf:   { data: loadFixture('test.rtf'),   name: 'test.rtf' },
    tcr:   { data: loadFixture('test.tcr'),   name: 'test.tcr' },
    txt:   { data: loadFixture('test.txt'),   name: 'test.txt' },
    txtz:  { data: loadFixture('test.txtz'),  name: 'test.txtz' },
};

const outputFormats = [
    'azw3', 'docx', 'epub', 'fb2', 'html', 'htmlz', 'kepub',
    'lrf', 'mobi', 'oeb', 'pdb', 'pdf', 'pmlz', 'rb', 'rtf', 'snb', 'tcr', 'txt',
];

describe('ebook conversions', { concurrency: POOL_SIZE }, () => {
    before(async () => {
        console.log(`Initializing ${POOL_SIZE} converter worker(s)…`);
        const inits = Array.from({ length: POOL_SIZE }, () => createWorker());
        workers.push(...(await Promise.all(inits)));
        idle.push(...workers);
    });

    after(async () => {
        for (const w of workers) {
            w.send({ type: 'exit' });
        }
        await Promise.all(workers.map((w) => new Promise((r) => w.on('exit', r))));
    });

    for (const [inputFmt, fixture] of Object.entries(fixtures)) {
        if (!fixture.data) continue;

        for (const outputFmt of outputFormats) {
            const label = `${inputFmt.toUpperCase()} -> ${outputFmt.toUpperCase()}`;

            test(`${label} convert`, async () => {
                const worker = await acquire();
                try {
                    const outputFile = `${fixture.name.replace(/\.[^.]+$/, '')}.${outputFmt}`;
                    const result = await convert(worker, fixture.data, fixture.name, outputFile);
                    assert.ok(result.length > 0, `${label} returned empty output`);
                } catch (e) {
                    const message = e?.message ?? String(e);
                    const summary =
                        message
                            .split('\n')
                            .filter((line) =>
                                line.includes('Error') ||
                                line.includes('Import') ||
                                line.includes('Module') ||
                                line.includes('No module') ||
                                line.includes('attribute')
                            )
                            .slice(0, 3)
                            .join(' | ') || message.substring(0, 300);
                    assert.fail(`${label} failed: ${summary}`);
                } finally {
                    release(worker);
                }
            });
        }
    }
});
