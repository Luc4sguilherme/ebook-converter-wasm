#!/usr/bin/env node
/**
 * convert.mjs — Node.js example for ebook-converter-wasm
 *
 * Usage:
 *   node convert.mjs input.epub output.html [--title "My Book"]
 */

import { readFileSync, writeFileSync } from 'node:fs';
import { basename, extname } from 'node:path';
import { EbookConverter } from '../../dist/node/ebook-convert.mjs';

async function main() {
    const args = process.argv.slice(2);

    if (args.length < 2) {
        console.error('Usage: node convert.mjs <input> <output> [options]');
        console.error('');
        console.error('Input formats:');
        console.error('  azw3, docx, epub, fb2, html, htmlz, lrf,');
        console.error('  mobi, odt, pdb, pdf, rb, rtf, tcr, txt, txtz');
        console.error('Output formats:');
        console.error('  azw3, docx, epub, fb2, html, htmlz, kepub,');
        console.error('  lrf, mobi, oeb, pdb, pdf, pmlz, rb, rtf, snb, tcr, txt');
        console.error('');
        console.error('Examples:');
        console.error('  node convert.mjs book.epub book.html');
        console.error('  node convert.mjs book.epub book.txt --title "My Book"');
        console.error('  node convert.mjs book.docx book.epub');
        console.error('  node convert.mjs book.fb2 book.mobi');
        process.exit(1);
    }

    const inputPath = args[0];
    const outputPath = args[1];
    const inputName = basename(inputPath);
    const outputName = basename(outputPath);
    const outputFormat = extname(outputPath).slice(1); 

    const options = {};
    for (let i = 2; i < args.length; i += 2) {
        if (args[i].startsWith('--') && args[i + 1]) {
            const key = args[i].slice(2).replace(/-/g, '_');
            options[key] = args[i + 1];
        }
    }

    console.log(`Converting: ${inputName} → ${outputFormat}`);
    if (Object.keys(options).length > 0) {
        console.log('Options:', options);
    }

    const converter = new EbookConverter();

    console.log('Initializing converter (this may take a moment on first run)...');
    await converter.init((stage, pct) => {
        process.stdout.write(`\r  [${stage}] ${pct}%`);
    });
    
    console.log('');

    converter.writeFile(inputName, new Uint8Array(readFileSync(inputPath)));

    console.log('Converting...');
    const startTime = Date.now();
    const outputData = await converter.convert(inputName, outputName, options);
    const elapsed = ((Date.now() - startTime) / 1000).toFixed(2);

    writeFileSync(outputPath, outputData);
    console.log(`Done in ${elapsed}s. Output: ${outputPath} (${outputData.length} bytes)`);

    const version = converter.getVersion();
    console.log(`\nVersion: ${JSON.stringify(version)}`);

    await converter.destroy();
}

main().catch((err) => {
    console.error('Error:', err.message);
    process.exit(1);
});
