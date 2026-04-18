/**
 * worker.js — Web Worker wrapper for ebook-converter-wasm
 *
 * Runs ebook conversion off the main thread to avoid blocking the UI.
 *
 * Usage from main thread:
 *   const worker = new Worker('./worker.js', { type: 'module' });
 *   worker.postMessage({
 *     type: 'convert',
 *     id: 'req-1',
 *     inputData: uint8Array,
 *     inputName: 'book.epub',
 *     outputFile: 'book.html',
 *     options: {}
 *   });
 *   worker.onmessage = (e) => {
 *     if (e.data.type === 'result') { ... }
 *     if (e.data.type === 'progress') { ... }
 *     if (e.data.type === 'error') { ... }
 *   };
 */

import { EbookConverter } from './ebook-convert.js';

let converter = null;
let initPromise = null;

/**
 * Ensure the converter is initialized (only once).
 */
async function ensureInit() {
    if (converter && converter._ready) return;

    if (!initPromise) {
        converter = new EbookConverter();
        initPromise = converter.init((stage, pct) => {
            self.postMessage({ type: 'progress', stage, pct });
        });
    }

    await initPromise;
}

/**
 * Handle messages from the main thread.
 */
self.onmessage = async function (e) {
    const msg = e.data;

    switch (msg.type) {
        case 'init': {
            try {
                if (msg.config) {
                    converter = new EbookConverter(msg.config);
                }
                await ensureInit();
                self.postMessage({ type: 'ready', id: msg.id });
            } catch (err) {
                self.postMessage({
                    type: 'error',
                    id: msg.id,
                    error: err.message,
                });
            }
            break;
        }

        case 'convert': {
            try {
                await ensureInit();

                self.postMessage({
                    type: 'progress',
                    id: msg.id,
                    stage: 'converting',
                    pct: 0,
                });

                converter.writeFile(msg.inputName, msg.inputData);
                const baseName = msg.inputName.replace(/\.[^.]+$/, '');
                const outputFile = msg.outputFile || `${baseName}.${msg.outputFormat}`;
                const result = await converter.convert(
                    msg.inputName,
                    outputFile,
                    msg.options || {},
                    (frac, message) => {
                        self.postMessage({
                            type: 'progress',
                            id: msg.id,
                            stage: 'converting',
                            pct: Math.round(frac * 100),
                            message,
                        });
                    }
                );

                self.postMessage({
                    type: 'result',
                    id: msg.id,
                    outputData: result,
                    outputFile,
                });
            } catch (err) {
                self.postMessage({
                    type: 'error',
                    id: msg.id,
                    error: err.message,
                    stack: err.stack,
                });
            } finally {
                if(converter) {
                    converter.destroy();
                    converter = null;
                    initPromise = null;
                }
            }
            break;
        }

        case 'version': {
            try {
                await ensureInit();
                const version = converter.getVersion();
                self.postMessage({ type: 'version', id: msg.id, version });
            } catch (err) {
                self.postMessage({
                    type: 'error',
                    id: msg.id,
                    error: err.message,
                });
            }
            break;
        }

        case 'formats': {
            self.postMessage({
                type: 'formats',
                id: msg.id,
                input: converter
                    ? converter.getSupportedInputFormats()
                    : [],
                output: converter
                    ? converter.getSupportedOutputFormats()
                    : [],
            });
            break;
        }

        case 'destroy': {
            if (converter) {
                await converter.destroy();
                converter = null;
                initPromise = null;
            }
            self.postMessage({ type: 'destroyed', id: msg.id });
            break;
        }

        default:
            self.postMessage({
                type: 'error',
                id: msg.id,
                error: `Unknown message type: ${msg.type}`,
            });
    }
};

self.postMessage({ type: 'loaded' });
