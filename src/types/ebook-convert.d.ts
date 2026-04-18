/**
 * ebook-converter-wasm — TypeScript declarations
 */

export interface ConvertOptions {
    /** Override book title */
    title?: string;
    /** Override book authors */
    authors?: string;
    /** Override book language */
    language?: string;
    /** Base font size in pt */
    base_font_size?: number;
    /** Output profile (e.g. 'kindle', 'tablet') */
    output_profile?: string;
    /** Strip images from output */
    no_images?: boolean;
    /** Linearize tables in output */
    linearize_tables?: boolean;
    /** Extra CSS to inject */
    extra_css?: string;

    [key: string]: any;
}

export interface EbookConverterConfig {
    /** Custom Pyodide CDN URL */
    pyodideUrl?: string;
    /** Custom URL for native WASM module */
    wasmUrl?: string;
    /** Custom URL for calibre-python.zip */
    pythonPkgUrl?: string;
}

export interface VersionInfo {
    calibreWasm: string;
    nativeModule: string;
    pyodide: string;
}

/**
 * Progress callback invoked during initialization.
 * @param stage - Current initialization stage
 * @param pct - Percentage complete (0-100)
 */
export type ProgressCallback = (stage: string, pct: number) => void;

/**
 * Progress callback invoked during conversion.
 * @param frac - Fraction complete (0.0-1.0)
 * @param message - Description of current conversion step
 */
export type ConversionProgressCallback = (frac: number, message: string) => void;

/**
 * Main ebook converter class.
 *
 * Provides a high-level interface for converting ebooks in the browser
 * or Node.js using calibre's conversion engine compiled to WebAssembly.
 *
 * @example
 * ```js
 * import { EbookConverter } from 'ebook-converter-wasm';
 *
 * const converter = new EbookConverter();
 * await converter.init();
 * converter.writeFile('book.epub', epubBytes);
 * await converter.convert('book.epub', 'book.html');
 * const htmlBytes = converter.readFile('book.html');
 * ```
 */
export class EbookConverter {
    constructor(config?: EbookConverterConfig);

    /**
     * Initialize the converter. Downloads and sets up Pyodide, native
     * WASM libs, and the Python conversion package.
     */
    init(onProgress?: ProgressCallback): Promise<void>;

    /** Write a file into the internal VFS for use as input to convert(). */
    writeFile(name: string, data: Uint8Array): void;

    /** Read a file from the internal VFS (e.g. to retrieve conversion output). */
    readFile(name: string): Uint8Array;

    /**
     * Convert an ebook file.
     *
     * Mirrors calibre's CLI: `ebook-convert input_file output_file [options]`
     *
     * Load the input first with writeFile(), then retrieve the output
     * with readFile().
     *
     * @param inputFile - Input filename (loaded via writeFile)
     * @param outputFile - Output filename (format inferred from extension)
     * @param options - Conversion options
     * @returns Raw bytes of the converted file
     */
    convert(
        inputFile: string,
        outputFile: string,
        options?: ConvertOptions,
        onProgress?: ConversionProgressCallback
    ): Promise<Uint8Array>;

    /** Get the list of supported input formats */
    getSupportedInputFormats(): string[];

    /** Get the list of supported output formats */
    getSupportedOutputFormats(): string[];

    /** Get version information */
    getVersion(): VersionInfo;

    /** Release resources */
    destroy(): Promise<void>;
}
