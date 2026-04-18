// ebook-converter-wasm — Node.js CJS compatibility wrapper
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
