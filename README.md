# ebook-converter-wasm

> **Note:** This project is an experiment/proof-of-concept. It is not production-ready and may have bugs, limitations.

Port of [calibre](https://github.com/kovidgoyal/calibre)'s `ebook-convert` command-line tool to WebAssembly. Convert ebooks in the Node.js or browser without a server.

Uses [Pyodide](https://pyodide.org/) (CPython 3.12 in WASM) with native C libraries (libxml2, libxslt, zlib, libjpeg, libpng, freetype, hunspell) compiled to WebAssembly.

## Supported Formats

| | Formats |
|---|---|
| **Input** | azw3, docx, epub, fb2, html, htmlz, lrf, mobi, odt, pdb, pdf, rb, rtf, tcr, txt, txtz |
| **Output** | azw3, docx, epub, fb2, html, htmlz, kepub, lrf, mobi, oeb, pdb, pdf, pmlz, rb, rtf, snb, tcr, txt |

## Quick Start

```bash
docker compose up builder
```

### Browser

```html
<script type="module">
import { EbookConverter } from './dist/browser/ebook-convert.mjs';

const converter = new EbookConverter();
await converter.init();

converter.writeFile('input.epub', new Uint8Array(epubBytes));
await converter.convert('input.epub', 'output.html');
const output = converter.readFile('output.html');
</script>
```

### Node.js

```js
import { EbookConverter } from './dist/node/ebook-convert.mjs';

const converter = new EbookConverter();
await converter.init();

converter.writeFile('book.epub', fs.readFileSync('book.epub'));
await converter.convert('book.epub', 'book.txt');
fs.writeFileSync('book.txt', converter.readFile('book.txt'));
```

## Building

Requires Docker + Docker Compose (~8 GB disk space, first build ~10 min).

```bash
docker compose up builder
```

By default, `.wasm` binaries are embedded as base64 inside the JS files (`SINGLE_FILE=1`). For smaller JS bundles with separate `.wasm` files:

```bash
docker compose build --build-arg SINGLE_FILE=0 builder
```

## Limitations

- **PDF output** — Uses fpdf2 instead of Qt WebEngine. Supports text, images, tables, and basic HTML formatting. Advanced CSS layout, custom fonts, and complex tables are not supported.
- **Comic CBR** — Not supported. RAR extraction is unavailable in WASM.
- **SVG rasterization** — SVG-to-image conversion is skipped (requires Qt). SVGs are passed through as-is.

## License

GPLv3 (inherited from Calibre).
