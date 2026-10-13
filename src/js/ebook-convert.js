/**
 * ebook-convert.js — Main JavaScript API for ebook-converter-wasm
 *
 * Provides a high-level interface for converting ebooks in the browser
 * or Node.js using calibre's ebook-convert engine compiled to WebAssembly.
 *
 * Architecture:
 *   JS API → Pyodide (CPython in WASM) → Calibre Python → Native C libs (WASM)
 *
 * @example
 *   const converter = new EbookConverter();
 *   await converter.init();
 *   converter.writeFile('book.epub', epubBytes);
 *   await converter.convert('book.epub', 'book.html');
 *   const htmlBytes = converter.readFile('book.html');
 */

const PYODIDE_CDN = 'https://cdn.jsdelivr.net/pyodide/v0.26.1/full/';

// Packages shipped with the Pyodide distribution
const PYODIDE_PACKAGES = [
    'micropip', 'Pillow', 'packaging', 'python-dateutil', 'msgpack', 'regex',
    'lxml', 'beautifulsoup4', 'html5lib', 'fonttools',
];

// Packages installed from PyPI with micropip
const PYPI_PACKAGES = [
    'css-parser==1.0.10',
    'html2text==2025.4.15',
    'chardet==5.2.0',
    'defusedxml==0.7.1',
    'fpdf2==2.8.7',
    'markdown==3.7',
];

/**
 * @typedef {Object} ConvertOptions
 * @property {string}  [title]           - Override book title
 * @property {string}  [authors]         - Override book authors
 * @property {string}  [language]        - Override book language
 * @property {number}  [base_font_size]  - Base font size in pt
 * @property {string}  [output_profile]  - Output profile (e.g. 'kindle', 'tablet')
 * @property {boolean} [no_images]       - PDF input only: ignore images
 * @property {boolean} [linearize_tables]- Linearize tables in output
 * @property {string}  [extra_css]       - Extra CSS to inject
 */

export class EbookConverter {
    /**
     * @param {Object} [config]
     * @param {string} [config.pyodideUrl]  - Custom Pyodide CDN URL
     * @param {string} [config.wasmUrl]     - Custom URL for native WASM module
     * @param {string} [config.pythonPkgUrl]- Custom URL for calibre-python.zip
     */
    constructor(config = {}) {
        this._config = {
            pyodideUrl: config.pyodideUrl || PYODIDE_CDN,
            wasmUrl: config.wasmUrl || null,
            pythonPkgUrl: config.pythonPkgUrl || null,
        };
        this._pyodide = null;
        this._nativeModule = null;
        this._ready = false;
    }

    /**
     * Initialize the converter. Downloads and sets up Pyodide, the native
     * WASM libs, and the Calibre Python package.
     *
     * @param {function} [onProgress] - Callback: (stage: string, pct: number) => void
     */
    async init(onProgress) {
        if (this._ready) return;

        const report = onProgress || (() => {});

        report('pyodide', 0);
        this._pyodide = await this._loadPyodide();
        report('pyodide', 100);

        report('native', 0);
        await this._loadNativeModule();
        report('native', 100);

        report('packages', 0);
        await this._pyodide.loadPackage(PYODIDE_PACKAGES);
        report('packages', 50);

        // Pure Python packages that are not part of the Pyodide distribution.
        // Versions are pinned so that a new upstream release cannot break
        // conversions (fpdf2 >= 2.8.8 imports urllib.request.HTTPSHandler,
        // which does not exist in Pyodide).
        this._pyodide.globals.set('_calibre_pypi_packages', PYPI_PACKAGES);
        await this._pyodide.runPythonAsync(`
import micropip
await micropip.install(list(_calibre_pypi_packages))
del _calibre_pypi_packages
`);
        report('packages', 100);

        report('calibre', 0);
        await this._loadCalibrePython();
        report('calibre', 100);

        this._ready = true;
    }

    /**
     * Write a file into the internal virtual filesystem so it can be used
     * as input to convert(). Required in the browser where there is no
     * real filesystem.
     *
     * @param {string}     name - Filename (e.g. 'book.epub')
     * @param {Uint8Array} data - Raw bytes of the file
     */
    writeFile(name, data) {
        if (!this._ready) {
            throw new Error('EbookConverter not initialized. Call init() first.');
        }
        const path = this._vfsPath(name);
        this._pyodide.FS.mkdirTree(path.substring(0, path.lastIndexOf('/')) || '/');
        this._pyodide.FS.writeFile(path, data);
    }

    /**
     * Read a file from the internal virtual filesystem.
     * Use this to retrieve the conversion output.
     *
     * @param {string} name - Filename (e.g. 'book.html')
     * @returns {Uint8Array} Raw bytes of the file
     */
    readFile(name) {
        if (!this._ready) {
            throw new Error('EbookConverter not initialized. Call init() first.');
        }
        return new Uint8Array(this._pyodide.FS.readFile(this._vfsPath(name)));
    }

    /**
     * Convert an ebook.
     *
     * Mirrors calibre's CLI: `ebook-convert input_file output_file [options]`
     *
     * Load the input file first with writeFile(), then call convert().
     * Retrieve the output with readFile().
     *
     * Options use the names of ebook-convert's command line options, with
     * either dashes or underscores (base_font_size or 'base-font-size').
     * Values are converted to the type of the option, like the command line
     * does, so strings such as '12' or 'true' are accepted.
     *
     * Output to .html produces a single self contained HTML file, with the
     * stylesheet inlined and images embedded.
     *
     * @param {string}         inputFile  - Input filename (previously loaded via writeFile)
     * @param {string}         outputFile - Output filename (format inferred from extension)
     * @param {ConvertOptions} [options]  - Conversion options
     * @param {function}       [onProgress] - Callback: (fraction: number, message: string) => void
     * @returns {Promise<Uint8Array>}      - Raw bytes of the converted file
     */
    async convert(inputFile, outputFile, options = {}, onProgress) {
        if (!this._ready) {
            throw new Error('EbookConverter not initialized. Call init() first.');
        }

        const py = this._pyodide;
        const inputPath = this._vfsPath(inputFile);
        if (!py.FS.analyzePath(inputPath).exists) {
            throw new Error(
                `File "${inputFile}" not found in VFS. ` +
                `Use writeFile('${inputFile}', data) to load it first.`
            );
        }

        const outputName = String(outputFile);
        const outputExt = outputName.match(/\.([^./]+)$/)?.[1]?.toLowerCase();
        if (!outputExt) {
            throw new Error('outputFile must have a file extension to determine output format');
        }

        // HTML output is produced as HTMLZ and turned into a single file
        const needsHtmlExtract = outputExt === 'html' || outputExt === 'htm';
        const userOutputPath = this._vfsPath(outputName);
        const outputPath = needsHtmlExtract
            ? userOutputPath.replace(/\.[^./]+$/, '.htmlz')
            : userOutputPath;
        py.FS.mkdirTree(outputPath.substring(0, outputPath.lastIndexOf('/')) || '/');

        const wasm = py.pyimport('ebook_convert_wasm');
        let pyOptions = null;
        if (typeof onProgress === 'function') {
            globalThis._calibreProgressCallback = (frac, msg) => {
                onProgress(frac, msg);
            };
        }
        try {
            pyOptions = options && Object.keys(options).length ? py.toPy(options) : null;
            wasm.convert(inputPath, outputPath, pyOptions);

            let outputData;
            const info = py.FS.analyzePath(outputPath);
            if (!info.exists) {
                throw new Error(`Conversion failed: output file not found at ${outputPath}`);
            }
            if (py.FS.isDir(info.object.mode)) {
                // Formats such as OEB produce a directory, return it as a ZIP
                const packed = wasm.pack_directory(outputPath);
                outputData = packed.toJs();
                packed.destroy();
            } else if (needsHtmlExtract) {
                const html = wasm.htmlz_to_html(outputPath);
                outputData = html.toJs();
                html.destroy();
            } else {
                outputData = py.FS.readFile(outputPath);
            }

            const finalOutput = new Uint8Array(outputData);
            if (userOutputPath !== outputPath) {
                py.FS.writeFile(userOutputPath, finalOutput);
            }
            return finalOutput;
        } finally {
            delete globalThis._calibreProgressCallback;
            if (pyOptions) pyOptions.destroy();
            wasm.destroy();
        }
    }

    /**
     * Resolve a filename to its path in the virtual filesystem.
     * @private
     */
    _vfsPath(name) {
        name = String(name);
        return name.startsWith('/') ? name : `/tmp/calibre-convert/${name}`;
    }

    /**
     * Get the list of supported input formats.
     * @returns {string[]}
     */
    getSupportedInputFormats() {
        if (this._ready && this._pyodide) {
            let formatsProxy = null;
            try {
                formatsProxy = this._pyodide.runPython(`
from ebook_convert_wasm import available_input_formats
sorted(list(available_input_formats()))
`);
                return Array.from(formatsProxy.toJs());
            } catch (e) {
                console.warn('Could not load dynamic input formats, using fallback list:', e.message);
            } finally {
                if (formatsProxy && typeof formatsProxy.destroy === 'function') {
                    formatsProxy.destroy();
                }
            }
        }

        return [
            'azw', 'azw3', 'azw4', 'cbc', 'cbr', 'cbz',
            'chm', 'docx', 'epub', 'fb2', 'htm', 'html',
            'htmlz', 'lit', 'lrf', 'mobi', 'odt', 'pdb',
            'pdf', 'pml', 'prc', 'rb', 'rtf', 'snb',
            'tcr', 'txt', 'txtz',
        ];
    }

    /**
     * Get the list of supported output formats.
     * @returns {string[]}
     */
    getSupportedOutputFormats() {
        if (this._ready && this._pyodide) {
            let formatsProxy = null;
            try {
                formatsProxy = this._pyodide.runPython(`
from ebook_convert_wasm import available_output_formats
sorted(list(available_output_formats()))
`);
                return Array.from(formatsProxy.toJs());
            } catch (e) {
                console.warn('Could not load dynamic output formats, using fallback list:', e.message);
            } finally {
                if (formatsProxy && typeof formatsProxy.destroy === 'function') {
                    formatsProxy.destroy();
                }
            }
        }

        return [
            'azw3', 'docx', 'epub', 'fb2', 'html', 'htmlz',
            'lrf', 'mobi', 'oeb', 'pdb', 'pdf', 'pml',
            'rtf', 'snb', 'tcr', 'txt',
        ];
    }

    /**
     * Get version information.
     * @returns {Object}
     */
    getVersion() {
        const native = this._nativeModule
            ? this._nativeModule.ccall('calibre_get_version', 'string', [], [])
            : 'not loaded';
        return {
            calibreWasm: '0.1.0',
            nativeModule: native,
            pyodide: this._pyodide ? this._pyodide.version : 'not loaded',
        };
    }

    /**
     * Release resources.
     */
    async destroy() {
        if (this._pyodide) {

            try {
                this._pyodide.runPython(`
import shutil, os
for d in ['/tmp/calibre-convert', '/calibre']:
    shutil.rmtree(d, ignore_errors=True)
`);
            } catch (e) {  }
        }
        this._pyodide = null;
        this._nativeModule = null;
        this._ready = false;
    }

    async _loadPyodide() {
        const isNode = typeof process !== 'undefined' && process.versions?.node;

        if (isNode) {

            const { loadPyodide } = await import('pyodide');
            return await loadPyodide();
        } else if (typeof document === 'undefined') {

            const pyodideMjs = this._config.pyodideUrl + 'pyodide.mjs';
            const mod = await import( pyodideMjs);
            const loadPyodide = mod.loadPyodide || mod.default;
            return await loadPyodide({
                indexURL: this._config.pyodideUrl,
            });
        } else {

            if (!globalThis.loadPyodide) {
                await this._loadScript(this._config.pyodideUrl + 'pyodide.js');
            }
            return await globalThis.loadPyodide({
                indexURL: this._config.pyodideUrl,
            });
        }
    }

    async _loadNativeModule() {
        try {
            const isNode = typeof process !== 'undefined' && process.versions?.node;
            const wasmUrl = this._config.wasmUrl;
            let modulePath;

            if (wasmUrl) {
                modulePath = wasmUrl;
            } else if (isNode) {

                const { fileURLToPath } = await import('node:url');
                const { dirname, join } = await import('node:path');
                const thisDir = dirname(fileURLToPath(import.meta.url));
                modulePath = join(thisDir, 'ebook-convert-native.js');
            } else {
                modulePath = './ebook-convert-native.js';
            }

            const mod = await import(modulePath);
            const CalibreNative = mod.default || mod;
            const instance = typeof CalibreNative === 'function'
                ? await CalibreNative()
                : CalibreNative;
            this._nativeModule = instance;

            this._nativeModule.ccall('calibre_init', 'number', [], []);
        } catch (e) {
            console.warn('Native WASM module not loaded (conversion will use pure Python):', e.message);
            this._nativeModule = null;
        }
    }

    async _loadCalibrePython() {
        const py = this._pyodide;
        const isNode = typeof process !== 'undefined' && process.versions?.node;

        let zipData = null;

        if (isNode) {
            try {
                const { readFileSync } = await import('node:fs');
                const { fileURLToPath } = await import('node:url');
                const { dirname, join } = await import('node:path');

                let zipPath;
                if (this._config.pythonPkgUrl) {

                    zipPath = this._config.pythonPkgUrl.startsWith('file://')
                        ? fileURLToPath(this._config.pythonPkgUrl)
                        : this._config.pythonPkgUrl;
                } else {

                    const thisDir = dirname(fileURLToPath(import.meta.url));
                    zipPath = join(thisDir, 'calibre-python.zip');
                }

                zipData = readFileSync(zipPath);
            } catch (e) {
                console.warn('Could not load calibre-python.zip:', e.message);
            }
        } else {

            const pkgUrl = this._config.pythonPkgUrl || './calibre-python.zip';
            try {
                const response = await fetch(pkgUrl);
                if (response.ok) {
                    zipData = new Uint8Array(await response.arrayBuffer());
                }
            } catch (e) {
                console.warn('Could not load calibre-python.zip:', e.message);
            }
        }

        if (zipData) {
            py.unpackArchive(new Uint8Array(zipData), 'zip', {
                extractDir: '/calibre-python',
            });
        }

        if (!zipData) {
            throw new Error(
                'Failed to load calibre-python.zip. Make sure it is available at the configured URL.'
            );
        }

        py.runPython(`
import sys
if '/calibre-python' not in sys.path:
    sys.path.insert(0, '/calibre-python')

from ebook_convert_wasm import _init_calibre_env
_init_calibre_env()
`);

        await this._registerPdftohtmlWasm();

        await this._registerPdfinfoWasm();
    }

    /**
     * Load pdftohtml WASM binary and register it as a global JS function
     * that Python code can call via Pyodide's JS interop.
     *
     * Node.js: runs pdftohtml as a child process (standalone Emscripten CLI
     * with NODERAWFS + EXIT_RUNTIME), bridging files between Pyodide VFS
     * and real temp directories.
     *
     * Browser: loads pdftohtml.js (Emscripten MODULARIZE build with
     * MEMFS), instantiates the module per invocation, writes input files to
     * its MEMFS, calls main(), and reads output files back.
     * @private
     */
    async _registerPdftohtmlWasm() {
        const isNode = typeof process !== 'undefined' && process.versions?.node;
        const isBrowser = typeof window !== 'undefined' || typeof self !== 'undefined';

        if (isNode) {
            await this._registerPdftohtmlNode();
        } else if (isBrowser) {
            await this._registerPdftohtmlBrowser();
        } else {
            globalThis._pdftohtmlWasmCall = null;
            globalThis._pdftohtmlWasmOutput = null;
        }
    }

    /**
     * Node.js pdftohtml registration — child process approach.
     * @private
     */
    async _registerPdftohtmlNode() {
        let pdftohtmlPath = null;

        try {
            const { existsSync } = await import('node:fs');
            const { fileURLToPath } = await import('node:url');
            const { dirname, join } = await import('node:path');
            const thisDir = dirname(fileURLToPath(import.meta.url));
            const candidate = join(thisDir, 'pdftohtml.cjs');
            if (existsSync(candidate)) {
                pdftohtmlPath = candidate;
            }
        } catch (e) {
            console.warn('pdftohtml WASM not available (PDF input disabled):', e.message);
        }

        if (typeof globalThis !== 'undefined') {
            if (pdftohtmlPath) {
                const { createRequire } = await import('node:module');
                const require = createRequire(import.meta.url);
                const childProcess = require('child_process');
                const nodeFs = require('fs');
                const nodeOs = require('os');
                const nodePath = require('path');
                const nodeExec = process.execPath;
                const storedPdftohtmlPath = pdftohtmlPath;
                const pyodide = this._pyodide;

                const copyVfsToReal = (vfsDir, realDir) => {
                    const entries = pyodide.FS.readdir(vfsDir);
                    for (const entry of entries) {
                        if (entry === '.' || entry === '..') continue;
                        try {
                            const data = pyodide.FS.readFile(vfsDir + '/' + entry);
                            nodeFs.writeFileSync(nodePath.join(realDir, entry), data);
                        } catch (e) {  }
                    }
                };

                const copyRealToVfs = (realDir, vfsDir) => {
                    const entries = nodeFs.readdirSync(realDir);
                    for (const entry of entries) {
                        const fullPath = nodePath.join(realDir, entry);
                        if (!nodeFs.statSync(fullPath).isFile()) continue;
                        const data = nodeFs.readFileSync(fullPath);
                        pyodide.FS.writeFile(vfsDir + '/' + entry, data);
                    }
                };

                globalThis._pdftohtmlWasmCall = (args, cwd) => {
                    const tmpDir = nodeFs.mkdtempSync(nodePath.join(nodeOs.tmpdir(), 'pdftohtml-'));
                    try {
                        if (cwd) copyVfsToReal(cwd, tmpDir);
                        childProcess.execFileSync(nodeExec, [storedPdftohtmlPath, ...args.slice(1)], {
                            cwd: tmpDir,
                            stdio: ['pipe', 'pipe', 'pipe'],
                            timeout: 120000,
                        });
                        if (cwd) copyRealToVfs(tmpDir, cwd);
                        return 0;
                    } catch (e) {

                        try { if (cwd) copyRealToVfs(tmpDir, cwd); } catch (_) {}
                        if (e.status != null) return e.status;
                        return 1;
                    } finally {
                        try { nodeFs.rmSync(tmpDir, { recursive: true, force: true }); } catch (_) {}
                    }
                };

                globalThis._pdftohtmlWasmOutput = (args, cwd) => {
                    const tmpDir = nodeFs.mkdtempSync(nodePath.join(nodeOs.tmpdir(), 'pdftohtml-'));
                    try {
                        if (cwd) copyVfsToReal(cwd, tmpDir);
                        const out = childProcess.execFileSync(nodeExec, [storedPdftohtmlPath, ...args.slice(1)], {
                            cwd: tmpDir,
                            stdio: ['pipe', 'pipe', 'pipe'],
                            timeout: 120000,
                        });
                        return out.toString('utf-8');
                    } catch (e) {
                        if (e.stdout) return e.stdout.toString('utf-8');
                        return '';
                    } finally {
                        try { nodeFs.rmSync(tmpDir, { recursive: true, force: true }); } catch (_) {}
                    }
                };

                console.log('pdftohtml WASM loaded — PDF input enabled');
            } else {
                globalThis._pdftohtmlWasmCall = null;
                globalThis._pdftohtmlWasmOutput = null;
            }
        }
    }

    /**
     * Browser pdftohtml registration — in-process Emscripten MEMFS approach.
     *
     * Loads pdftohtml.js (built with MODULARIZE + MEMFS), pre-
     * instantiates the WASM module during init(), then provides synchronous
     * _pdftohtmlWasmCall / _pdftohtmlWasmOutput functions that the Python
     * code can call via run_js without awaiting.
     *
     * Files are shuttled between Pyodide's VFS and the Emscripten module's
     * MEMFS for each invocation.
     * @private
     */
    async _registerPdftohtmlBrowser() {
        const pyodide = this._pyodide;

        let pdftohtmlModuleUrl = null;
        try {
            const baseUrl = typeof import.meta?.url === 'string'
                ? new URL('./', import.meta.url).href
                : '';
            pdftohtmlModuleUrl = baseUrl + 'pdftohtml.js';
        } catch (e) {
            pdftohtmlModuleUrl = './pdftohtml.js';
        }

        let createPdftohtml = null;
        try {
            const mod = await import( pdftohtmlModuleUrl);
            createPdftohtml = mod.default || mod.createPdftohtml;
            if (typeof createPdftohtml !== 'function') createPdftohtml = null;
        } catch (e) {  }

        if (!createPdftohtml) {
            try {
                const resp = await fetch(pdftohtmlModuleUrl);
                const text = await resp.text();
                const blob = new Blob(
                    [text + '\nexport default createPdftohtml;\n'],
                    { type: 'text/javascript' }
                );
                const blobUrl = URL.createObjectURL(blob);
                try {
                    const mod = await import( blobUrl);
                    createPdftohtml = mod.default;
                } finally {
                    URL.revokeObjectURL(blobUrl);
                }
            } catch (e) {
                console.warn('pdftohtml.js not available (PDF input disabled in browser):', e.message);
                globalThis._pdftohtmlWasmCall = null;
                globalThis._pdftohtmlWasmOutput = null;
                return;
            }
        }

        if (typeof createPdftohtml !== 'function') {
            console.warn('pdftohtml.js did not export a module factory (PDF input disabled)');            
            globalThis._pdftohtmlWasmCall = null;
            globalThis._pdftohtmlWasmOutput = null;
            return;
        }

        let stdoutBuf = [];
        let stderrBuf = [];
        let instance;

        const wasmBaseUrl = typeof import.meta?.url === 'string'
            ? new URL('./', import.meta.url).href : './';

        try {
            instance = await createPdftohtml({
                noInitialRun: true,
                locateFile: (path) => {
                    if (path.endsWith('.wasm')) {
                        return wasmBaseUrl + 'pdftohtml.wasm';
                    }
                    return path;
                },
                print: (text) => stdoutBuf.push(text),
                printErr: (text) => stderrBuf.push(text),
            });
        } catch (e) {
            console.warn('pdftohtml WASM module failed to instantiate:', e.message);
            globalThis._pdftohtmlWasmCall = null;
            globalThis._pdftohtmlWasmOutput = null;
            return;
        }

        const copyVfsToMemfs = (vfsDir, memfsDir) => {
            const entries = pyodide.FS.readdir(vfsDir);
            for (const entry of entries) {
                if (entry === '.' || entry === '..') continue;
                try {
                    const data = pyodide.FS.readFile(vfsDir + '/' + entry);
                    instance.FS.writeFile(memfsDir + '/' + entry, data);
                } catch (e) {  }
            }
        };

        const copyMemfsToVfs = (memfsDir, vfsDir) => {
            let entries;
            try {
                entries = instance.FS.readdir(memfsDir);
            } catch (e) { return; }
            for (const entry of entries) {
                if (entry === '.' || entry === '..') continue;
                try {
                    const stat = instance.FS.stat(memfsDir + '/' + entry);
                    if (instance.FS.isFile(stat.mode)) {
                        const data = instance.FS.readFile(memfsDir + '/' + entry);
                        pyodide.FS.writeFile(vfsDir + '/' + entry, data);
                    }
                } catch (e) {  }
            }
        };

        const cleanMemfsDir = (dir) => {
            let entries;
            try {
                entries = instance.FS.readdir(dir);
            } catch (e) { return; }
            for (const entry of entries) {
                if (entry === '.' || entry === '..') continue;
                const full = dir + '/' + entry;
                try {
                    const stat = instance.FS.stat(full);
                    if (instance.FS.isDir(stat.mode)) {
                        cleanMemfsDir(full);
                        instance.FS.rmdir(full);
                    } else {
                        instance.FS.unlink(full);
                    }
                } catch (e) {  }
            }
        };

        try { instance.FS.mkdir('/work'); } catch (e) {  }

        /**
         * Synchronous pdftohtml invocation for the browser.
         * Copies files from Pyodide VFS → MEMFS, calls main(), copies back.
         */
        globalThis._pdftohtmlWasmCall = (args, cwd) => {
            stdoutBuf = [];
            stderrBuf = [];
            try {
                cleanMemfsDir('/work');
                if (cwd) copyVfsToMemfs(cwd, '/work');

                const rewrittenArgs = args.slice(1).map(arg =>
                    cwd && arg.includes('/') ? arg.replace(cwd, '/work') : arg
                );

                instance.FS.chdir('/work');
                let ret = 0;
                try {
                    ret = instance.callMain(rewrittenArgs) || 0;
                } catch (exitErr) {

                    if (exitErr && typeof exitErr.status === 'number') {
                        ret = exitErr.status;
                    } else {
                        ret = 1;
                    }
                }

                if (cwd) copyMemfsToVfs('/work', cwd);
                return ret;
            } catch (e) {
                try { if (cwd) copyMemfsToVfs('/work', cwd); } catch (_) {}
                return 1;
            }
        };

        globalThis._pdftohtmlWasmOutput = (args, cwd) => {
            stdoutBuf = [];
            stderrBuf = [];
            try {
                cleanMemfsDir('/work');
                if (cwd) copyVfsToMemfs(cwd, '/work');

                const rewrittenArgs = args.slice(1).map(arg =>
                    cwd && arg.includes('/') ? arg.replace(cwd, '/work') : arg
                );

                instance.FS.chdir('/work');
                try {
                    instance.callMain(rewrittenArgs);
                } catch (exitErr) {

                }

                return stdoutBuf.join('\n');
            } catch (e) {
                return stdoutBuf.join('\n');
            }
        };

        console.log('pdftohtml WASM (browser) loaded — PDF input enabled');
    }

    /**
     * Load pdfinfo WASM binary and register it as a global JS function
     * that Python code can call via Pyodide's JS interop.
     *
     * Used by calibre's PDF metadata reader to extract title, author,
     * page count, encryption status, and XMP metadata from PDF files.
     * @private
     */
    async _registerPdfinfoWasm() {
        const isNode = typeof process !== 'undefined' && process.versions?.node;
        const isBrowser = typeof window !== 'undefined' || typeof self !== 'undefined';

        if (isNode) {
            await this._registerPdfinfoNode();
        } else if (isBrowser) {
            await this._registerPdfinfoBrowser();
        } else {
            globalThis._pdfinfoWasmOutput = null;
        }
    }

    /**
     * Node.js pdfinfo registration — child process approach.
     * @private
     */
    async _registerPdfinfoNode() {
        let pdfinfoPath = null;

        try {
            const { existsSync } = await import('node:fs');
            const { fileURLToPath } = await import('node:url');
            const { dirname, join } = await import('node:path');
            const thisDir = dirname(fileURLToPath(import.meta.url));
            const candidate = join(thisDir, 'pdfinfo.cjs');
            if (existsSync(candidate)) {
                pdfinfoPath = candidate;
            }
        } catch (e) {
            console.warn('pdfinfo WASM not available (PDF metadata disabled):', e.message);
        }

        if (pdfinfoPath) {
            const { createRequire } = await import('node:module');
            const require = createRequire(import.meta.url);
            const childProcess = require('child_process');
            const nodeFs = require('fs');
            const nodeOs = require('os');
            const nodePath = require('path');
            const nodeExec = process.execPath;
            const storedPdfinfoPath = pdfinfoPath;
            const pyodide = this._pyodide;

            globalThis._pdfinfoWasmOutput = (args, cwd) => {
                const tmpDir = nodeFs.mkdtempSync(nodePath.join(nodeOs.tmpdir(), 'pdfinfo-'));
                try {

                    if (cwd) {
                        const entries = pyodide.FS.readdir(cwd);
                        for (const entry of entries) {
                            if (entry === '.' || entry === '..') continue;
                            try {
                                const data = pyodide.FS.readFile(cwd + '/' + entry);
                                nodeFs.writeFileSync(nodePath.join(tmpDir, entry), data);
                            } catch (e) {  }
                        }
                    }

                    const rewrittenArgs = args.slice(1).map(arg => {
                        if (cwd && arg.startsWith(cwd)) {
                            return nodePath.join(tmpDir, arg.substring(cwd.length + 1));
                        }
                        return arg;
                    });

                    const out = childProcess.execFileSync(nodeExec, [storedPdfinfoPath, ...rewrittenArgs], {
                        cwd: tmpDir,
                        stdio: ['pipe', 'pipe', 'pipe'],
                        timeout: 30000,
                    });
                    return out.toString('utf-8');
                } catch (e) {
                    if (e.stdout) return e.stdout.toString('utf-8');
                    return '';
                } finally {
                    try { nodeFs.rmSync(tmpDir, { recursive: true, force: true }); } catch (_) {}
                }
            };

            console.log('pdfinfo WASM loaded — PDF metadata extraction enabled');
        } else {
            globalThis._pdfinfoWasmOutput = null;
        }
    }

    /**
     * Browser pdfinfo registration — in-process Emscripten MEMFS approach.
     * @private
     */
    async _registerPdfinfoBrowser() {
        const pyodide = this._pyodide;

        let pdfinfoModuleUrl = null;
        try {
            const baseUrl = typeof import.meta?.url === 'string'
                ? new URL('./', import.meta.url).href
                : '';
            pdfinfoModuleUrl = baseUrl + 'pdfinfo.js';
        } catch (e) {
            pdfinfoModuleUrl = './pdfinfo.js';
        }

        let createPdfinfo = null;
        try {
            const mod = await import( pdfinfoModuleUrl);
            createPdfinfo = mod.default || mod.createPdfinfo;
            if (typeof createPdfinfo !== 'function') createPdfinfo = null;
        } catch (e) {  }

        if (!createPdfinfo) {
            try {
                const resp = await fetch(pdfinfoModuleUrl);
                const text = await resp.text();
                const blob = new Blob(
                    [text + '\nexport default createPdfinfo;\n'],
                    { type: 'text/javascript' }
                );
                const blobUrl = URL.createObjectURL(blob);
                try {
                    const mod = await import( blobUrl);
                    createPdfinfo = mod.default;
                } finally {
                    URL.revokeObjectURL(blobUrl);
                }
            } catch (e) {
                console.warn('pdfinfo.js not available (PDF metadata disabled in browser):', e.message);
                globalThis._pdfinfoWasmOutput = null;
                return;
            }
        }

        if (typeof createPdfinfo !== 'function') {
            console.warn('pdfinfo.js did not export a module factory (PDF metadata disabled)');
            globalThis._pdfinfoWasmOutput = null;
            return;
        }

        let stdoutBuf = [];
        let instance;
        const wasmBaseUrl = typeof import.meta?.url === 'string'
            ? new URL('./', import.meta.url).href : './';

        try {
            instance = await createPdfinfo({
                noInitialRun: true,
                locateFile: (path) => {
                    if (path.endsWith('.wasm')) {
                        return wasmBaseUrl + 'pdfinfo.wasm';
                    }
                    return path;
                },
                print: (text) => stdoutBuf.push(text),
                printErr: () => {},
            });
        } catch (e) {
            console.warn('pdfinfo WASM module failed to instantiate:', e.message);
            globalThis._pdfinfoWasmOutput = null;
            return;
        }

        const copyVfsToMemfs = (vfsDir, memfsDir) => {
            const entries = pyodide.FS.readdir(vfsDir);
            for (const entry of entries) {
                if (entry === '.' || entry === '..') continue;
                try {
                    const data = pyodide.FS.readFile(vfsDir + '/' + entry);
                    instance.FS.writeFile(memfsDir + '/' + entry, data);
                } catch (e) {  }
            }
        };

        const cleanMemfsDir = (dir) => {
            let entries;
            try { entries = instance.FS.readdir(dir); } catch (e) { return; }
            for (const entry of entries) {
                if (entry === '.' || entry === '..') continue;
                const full = dir + '/' + entry;
                try {
                    const stat = instance.FS.stat(full);
                    if (instance.FS.isDir(stat.mode)) {
                        cleanMemfsDir(full);
                        instance.FS.rmdir(full);
                    } else {
                        instance.FS.unlink(full);
                    }
                } catch (e) {  }
            }
        };

        try { instance.FS.mkdir('/work'); } catch (e) {  }

        globalThis._pdfinfoWasmOutput = (args, cwd) => {
            stdoutBuf = [];
            try {
                cleanMemfsDir('/work');
                if (cwd) copyVfsToMemfs(cwd, '/work');

                const rewrittenArgs = args.slice(1).map(arg => {
                    if (cwd && arg.startsWith(cwd)) {
                        return '/work' + arg.substring(cwd.length);
                    }
                    return arg;
                });

                instance.FS.chdir('/work');
                try {
                    instance.callMain(rewrittenArgs);
                } catch (exitErr) {

                }

                return stdoutBuf.join('\n');
            } catch (e) {
                return stdoutBuf.join('\n');
            }
        };

        console.log('pdfinfo WASM (browser) loaded — PDF metadata extraction enabled');
    }

    async _loadScript(url) {
        if (typeof document !== 'undefined') {
            return new Promise((resolve, reject) => {
                const script = document.createElement('script');
                script.src = url;
                script.onload = resolve;
                script.onerror = () => reject(new Error(`Failed to load script: ${url}`));
                document.head.appendChild(script);
            });
        } else if (typeof importScripts === 'function') {
            importScripts(url);
        } else {
            await import(url);
        }
    }
}

/**
 * Convenience function: initialize a converter, convert a single file and
 * release the converter.
 *
 * @param {Uint8Array}     inputData    - Raw bytes of the input file
 * @param {string}         inputName    - Input filename, its extension gives the input format
 * @param {string}         outputFormat - Output format, e.g. 'epub'
 * @param {ConvertOptions} [options]    - Conversion options
 * @param {Object}         [config]     - Configuration for the EbookConverter constructor
 * @returns {Promise<Uint8Array>}        - Raw bytes of the converted file
 */
export async function convertEbook(inputData, inputName, outputFormat, options = {}, config = {}) {
    const converter = new EbookConverter(config);
    await converter.init();
    try {
        converter.writeFile(inputName, inputData);
        const outputName = `${inputName.replace(/\.[^./]+$/, '')}.${String(outputFormat).replace(/^\./, '')}`;
        return await converter.convert(inputName, outputName, options);
    } finally {
        await converter.destroy();
    }
}
