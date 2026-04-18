/**
 * test-regression.mjs — Regression tests for conversion quality.
 *
 * Validates that conversions preserve content, structure, and formatting.
 * Uses a rich HTML fixture with known markers and verifies they survive
 * round-trip through each output format.
 */
import assert from 'node:assert/strict';
import { execSync, fork } from 'node:child_process';
import { existsSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir, availableParallelism } from 'node:os';
import { join } from 'node:path';
import { after, before, describe, test } from 'node:test';
import { fileURLToPath } from 'node:url';

const POOL_SIZE = Math.max(1, Math.min(availableParallelism() - 1, 4));
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

/**
 * Extract readable text from output bytes based on format.
 * Returns a string of extracted text content for content verification.
 */
function extractText(data, format) {
    const buf = Buffer.from(data);

    switch (format) {
        case 'txt':
            return buf.toString('utf-8');

        case 'html':
        case 'htm':
            return stripHtmlTags(buf.toString('utf-8'));

        case 'htmlz':
        case 'epub':
        case 'docx':
        case 'oeb': {

            return extractTextFromZip(buf, format);
        }

        case 'fb2': {

            const xml = buf.toString('utf-8');
            return stripXmlTags(xml);
        }

        case 'rtf': {

            return extractRtfText(buf.toString('latin1'));
        }

        case 'pdb':
        case 'tcr':
        case 'pmlz':
        case 'snb':
        case 'rb':
        case 'lrf':
        case 'mobi':
        case 'azw3': {

            return extractBinaryText(buf);
        }

        case 'pdf': {

            return extractPdfText(buf);
        }

        default:
            return '';
    }
}

function stripHtmlTags(html) {
    return html
        .replace(/<script[^>]*>[\s\S]*?<\/script>/gi, '')
        .replace(/<style[^>]*>[\s\S]*?<\/style>/gi, '')
        .replace(/<[^>]+>/g, ' ')
        .replace(/&nbsp;/g, ' ')
        .replace(/&amp;/g, '&')
        .replace(/&lt;/g, '<')
        .replace(/&gt;/g, '>')
        .replace(/&quot;/g, '"')
        .replace(/&#(\d+);/g, (_, n) => String.fromCharCode(parseInt(n)))
        .replace(/\s+/g, ' ')
        .trim();
}

function stripXmlTags(xml) {
    return xml
        .replace(/<[^>]+>/g, ' ')
        .replace(/&amp;/g, '&')
        .replace(/&lt;/g, '<')
        .replace(/&gt;/g, '>')
        .replace(/&quot;/g, '"')
        .replace(/&#(\d+);/g, (_, n) => String.fromCharCode(parseInt(n)))
        .replace(/\s+/g, ' ')
        .trim();
}

function extractTextFromZip(buf, format) {

    const tmpDir = mkdtempSync(join(tmpdir(), 'regtest-'));
    const zipPath = join(tmpDir, `test.${format}`);
    writeFileSync(zipPath, buf);

    try {

        const raw = execSync(`unzip -p "${zipPath}" 2>/dev/null || true`, {
            maxBuffer: 10 * 1024 * 1024,
            encoding: 'utf-8',
        });

        let text = raw;

        if (format === 'docx') {
            const wt = [...text.matchAll(/<w:t[^>]*>(.*?)<\/w:t>/gs)];
            if (wt.length > 0) {
                text = wt.map(m => m[1]).join(' ');
            }
        }

        text = stripHtmlTags(text);
        return text;
    } catch {

        return extractBinaryText(buf);
    } finally {
        try { rmSync(tmpDir, { recursive: true, force: true }); } catch {}
    }
}

function extractRtfText(rtf) {

    let text = rtf;

    text = text.replace(/^\{\\rtf[^}]*/, '');

    text = text.replace(/\\'([0-9a-fA-F]{2})/g, (_, hex) =>
        String.fromCharCode(parseInt(hex, 16)));
    // Remove RTF control words
    text = text.replace(/\\[a-z]+[-]?\d*\s?/g, ' ');
    // Remove braces
    text = text.replace(/[{}]/g, '');
    // Clean up
    text = text.replace(/\s+/g, ' ').trim();
    return text;
}

function extractBinaryText(buf) {
    // Extract printable ASCII sequences (min 4 chars) from binary data
    const strings = [];
    let current = '';

    for (let i = 0; i < buf.length; i++) {
        const byte = buf[i];
        if (byte >= 0x20 && byte < 0x7f) {
            current += String.fromCharCode(byte);
        } else {
            if (current.length >= 4) {
                strings.push(current);
            }
            current = '';
        }
    }
    if (current.length >= 4) {
        strings.push(current);
    }
    return strings.join(' ');
}

function extractPdfText(buf) {
    // Basic PDF text extraction: look for text in stream objects and Tj/TJ operators
    const str = buf.toString('latin1');
    const texts = [];

    // Extract text from BT...ET blocks
    const btMatches = str.matchAll(/BT\s([\s\S]*?)ET/g);
    for (const m of btMatches) {
        const block = m[1];
        // Extract (text) Tj operators
        const tjMatches = block.matchAll(/\(([^)]*)\)\s*Tj/g);
        for (const tj of tjMatches) {
            texts.push(tj[1]);
        }
        // Extract [(text)] TJ operators
        const tjArrayMatches = block.matchAll(/\[(.*?)\]\s*TJ/g);
        for (const tja of tjArrayMatches) {
            const innerTexts = tja[1].matchAll(/\(([^)]*)\)/g);
            for (const it of innerTexts) {
                texts.push(it[1]);
            }
        }
    }

    // Also try to find readable strings
    if (texts.length === 0) {
        return extractBinaryText(buf);
    }

    return texts.join(' ');
}

// --------------- Markup extraction helpers ---------------

/**
 * Extract raw markup from output bytes for formatting verification.
 * Returns the raw markup string (HTML/XML/RTF) that can be inspected for
 * formatting elements like bold, italic, headings, lists, tables, etc.
 */
function extractMarkup(data, format) {
    const buf = Buffer.from(data);

    switch (format) {
        case 'html':
        case 'htm':
            return buf.toString('utf-8');

        case 'epub':
        case 'htmlz':
        case 'oeb':
            return extractMarkupFromZip(buf, format);

        case 'fb2':
            return buf.toString('utf-8');

        case 'docx':
            return extractDocxMarkup(buf);

        case 'rtf':
            return buf.toString('latin1');

        default:
            return '';
    }
}

function extractMarkupFromZip(buf, format) {
    const tmpDir = mkdtempSync(join(tmpdir(), 'regmarkup-'));
    const zipPath = join(tmpDir, `test.${format}`);
    writeFileSync(zipPath, buf);
    try {
        return execSync(`unzip -p "${zipPath}" 2>/dev/null || true`, {
            maxBuffer: 10 * 1024 * 1024,
            encoding: 'utf-8',
        });
    } catch {
        return '';
    } finally {
        try { rmSync(tmpDir, { recursive: true, force: true }); } catch {}
    }
}

function extractDocxMarkup(buf) {
    const tmpDir = mkdtempSync(join(tmpdir(), 'regdocx-'));
    const zipPath = join(tmpDir, 'test.docx');
    writeFileSync(zipPath, buf);
    try {
        // Extract both document.xml and styles.xml — formatting may be
        // defined via character styles (w:rStyle) in styles.xml rather
        // than inline in document.xml.
        const doc = execSync(
            `unzip -p "${zipPath}" "word/document.xml" 2>/dev/null || true`,
            { maxBuffer: 10 * 1024 * 1024, encoding: 'utf-8' }
        );
        const styles = execSync(
            `unzip -p "${zipPath}" "word/styles.xml" 2>/dev/null || true`,
            { maxBuffer: 10 * 1024 * 1024, encoding: 'utf-8' }
        );
        return doc + '\n' + styles;
    } catch {
        return '';
    } finally {
        try { rmSync(tmpDir, { recursive: true, force: true }); } catch {}
    }
}

/**
 * Detect formatting features present in the converted output.
 * Returns an object with boolean flags for each formatting element found.
 */
function detectFormatting(data, format) {
    const markup = extractMarkup(data, format);
    if (!markup) return {};

    switch (format) {
        case 'html':
        case 'htm':
        case 'epub':
        case 'htmlz':
        case 'oeb':
            return detectHtmlFormatting(markup);

        case 'fb2':
            return detectFb2Formatting(markup);

        case 'docx':
            return detectDocxFormatting(markup);

        case 'rtf':
            return detectRtfFormatting(markup);

        default:
            return {};
    }
}

function detectHtmlFormatting(html) {
    const lower = html.toLowerCase();
    return {
        bold: /<(b|strong)\b/i.test(html) ||
              /font-weight\s*:\s*(bold|[7-9]00)/i.test(html),
        italic: /<(i|em)\b/i.test(html) ||
                /font-style\s*:\s*italic/i.test(html),
        headings: /<h[1-6]\b/i.test(html),
        unorderedList: /<ul\b/i.test(html),
        orderedList: /<ol\b/i.test(html),
        table: /<table\b/i.test(html),
        blockquote: /<blockquote\b/i.test(html) ||
                    /margin[^;]*:\s*(2em|[3-9]|[1-9]\d)/i.test(html),
        preformatted: /<pre\b/i.test(html) || /<code\b/i.test(html) ||
                      /white-space\s*:\s*pre/i.test(html),
        links: /<a\b[^>]+href\s*=/i.test(html),
    };
}

function detectFb2Formatting(xml) {
    return {
        bold: /<strong\b/i.test(xml),
        italic: /<emphasis\b/i.test(xml),
        headings: /<title\b/i.test(xml),
        unorderedList: /<emphasis\b/i.test(xml), // FB2 has no native lists — often uses emphasis
        orderedList: false, // FB2 has no ordered list element
        table: /<table\b/i.test(xml),
        blockquote: /<cite\b/i.test(xml) || /<epigraph\b/i.test(xml),
        preformatted: /<code\b/i.test(xml) ||
                      /<p\b[^>]*>\s*(def |class |import )/i.test(xml),
        links: /<a\b[^>]+href/i.test(xml) || /l:href/i.test(xml),
    };
}

function detectDocxFormatting(xml) {
    return {
        bold: /<w:b\s[^>]*val="on"/i.test(xml) || /<w:b\/>/i.test(xml) || /<w:b>/i.test(xml),
        italic: /<w:i\s[^>]*val="on"/i.test(xml) || /<w:i\/>/i.test(xml) || /<w:i>/i.test(xml),
        headings: /w:val="Heading/i.test(xml) || /w:val="heading/i.test(xml) ||
                  /<w:pStyle\b[^>]*Heading/i.test(xml),
        unorderedList: /<w:numPr\b/i.test(xml),
        orderedList: /<w:numPr\b/i.test(xml), // DOCX uses same element for both
        table: /<w:tbl\b/i.test(xml),
        blockquote: /w:val="Quote/i.test(xml) || /w:val="Block/i.test(xml) ||
                    /w:val="IntenseQuote/i.test(xml) ||
                    /<w:ind\b[^>]*w:left="[1-9]/i.test(xml),
        preformatted: /w:val="Code/i.test(xml) || /w:val="HTML Preformatted/i.test(xml) ||
                      /Courier/i.test(xml),
        links: /<w:hyperlink\b/i.test(xml),
    };
}

function detectRtfFormatting(rtf) {
    return {
        bold: /\\b[^a-z]/i.test(rtf) && /\\b0/i.test(rtf) || /\\b\s/i.test(rtf),
        italic: /\\i[^a-z]/i.test(rtf) || /\\i\s/i.test(rtf),
        headings: /\\s[1-9]\b/i.test(rtf) || /Heading/i.test(rtf) ||
                  /\\fs[3-9]\d\b/.test(rtf), // large font sizes suggest headings
        unorderedList: /\\listlevel/i.test(rtf) || /\\bullet/i.test(rtf) ||
                       /\\u8226/i.test(rtf) || /\\pnlvlblt/i.test(rtf),
        orderedList: /\\listlevel/i.test(rtf) || /\\pnlvlbody/i.test(rtf) ||
                     /\\pndec/i.test(rtf),
        table: /\\trowd/i.test(rtf),
        blockquote: /\\li[1-9]\d{2,}/i.test(rtf), // large left indent
        preformatted: /Courier/i.test(rtf) || /\\f\d+\\fmodern/i.test(rtf),
        links: /HYPERLINK/i.test(rtf) || /\\field/i.test(rtf),
    };
}

// --------------- Structural validators ---------------

// --------------- Style/CSS extraction helpers ---------------

/**
 * Parse CSS text into a map of selector → { property: value }.
 * Only handles simple class selectors (.classname) which is what calibre emits.
 */
function parseCssClasses(css) {
    const classes = {};
    const ruleRe = /\.(\w[\w-]*)\s*\{([^}]+)\}/g;
    let m;
    while ((m = ruleRe.exec(css)) !== null) {
        const name = m[1];
        const body = m[2];
        const props = {};
        for (const decl of body.split(';')) {
            const colonIdx = decl.indexOf(':');
            if (colonIdx < 0) continue;
            const prop = decl.substring(0, colonIdx).trim().toLowerCase();
            const val = decl.substring(colonIdx + 1).trim().toLowerCase();
            if (prop) props[prop] = val;
        }
        classes[name] = props;
    }
    return classes;
}

/**
 * Parse a CSS size value to a numeric value in a common unit (pt-like).
 * Handles em, pt, px. Returns NaN if unparseable.
 */
function parseCssSize(val) {
    if (!val) return NaN;
    const num = parseFloat(val);
    if (isNaN(num)) return NaN;
    if (val.includes('em')) return num * 12; // 1em = 12pt base
    if (val.includes('pt')) return num;
    if (val.includes('px')) return num * 0.75; // rough px→pt
    if (val.includes('%')) return num * 0.12;  // 100% ≈ 12pt
    return num;
}

/**
 * Extract style properties from an HTML-based output (HTML, EPUB, HTMLZ, OEB).
 * Returns a structured object with detected style features.
 */
function extractHtmlStyles(data, format) {
    const buf = Buffer.from(data);
    let css = '';
    let html = '';

    if (format === 'html' || format === 'htm') {
        html = buf.toString('utf-8');
        // Extract inline <style> blocks
        const styleBlocks = html.match(/<style[^>]*>([\s\S]*?)<\/style>/gi) || [];
        css = styleBlocks.map(b => b.replace(/<\/?style[^>]*>/gi, '')).join('\n');
    } else {
        // ZIP-based: extract CSS and HTML separately
        const tmpDir = mkdtempSync(join(tmpdir(), 'regstyle-'));
        const zipPath = join(tmpDir, `test.${format}`);
        writeFileSync(zipPath, buf);
        try {
            css = execSync(`unzip -p "${zipPath}" "*.css" 2>/dev/null || true`, {
                maxBuffer: 10 * 1024 * 1024, encoding: 'utf-8',
            });
            html = execSync(`unzip -p "${zipPath}" "*.html" "*.xhtml" "*.htm" 2>/dev/null || unzip -p "${zipPath}" 2>/dev/null || true`, {
                maxBuffer: 10 * 1024 * 1024, encoding: 'utf-8',
            });
        } catch { /* ignore */ } finally {
            try { rmSync(tmpDir, { recursive: true, force: true }); } catch {}
        }
    }

    const classes = parseCssClasses(css);
    const result = {
        headingSizeHierarchy: false,
        headingsBold: false,
        textAlignCenter: false,
        textAlignRight: false,
        blockquoteIndent: false,
        blockquoteItalic: false,
        preMonospace: false,
        preBackground: false,
        tableBorder: false,
        tableHeaderBold: false,
        tableHeaderBackground: false,
        nestedListIndent: false,
        listStyleDisc: false,
        listStyleDecimal: false,
        linkColor: false,
    };

    // Collect font sizes per heading level (from class names applied to h1/h2/h3 tags)
    const headingSizes = {};
    for (const level of [1, 2, 3]) {
        const tagRe = new RegExp(`<h${level}[^>]*class="([^"]+)"`, 'gi');
        let hm;
        while ((hm = tagRe.exec(html)) !== null) {
            const cls = hm[1].split(/\s+/);
            for (const cn of cls) {
                const props = classes[cn];
                if (props && props['font-size']) {
                    headingSizes[level] = parseCssSize(props['font-size']);
                    break;
                }
            }
            if (headingSizes[level]) break;
        }
    }
    // Also check inline style on h tags
    for (const level of [1, 2, 3]) {
        if (headingSizes[level]) continue;
        const inlineRe = new RegExp(`<h${level}[^>]*style="[^"]*font-size:\\s*([^;"]+)`, 'gi');
        const im = inlineRe.exec(html);
        if (im) headingSizes[level] = parseCssSize(im[1]);
    }

    if (headingSizes[1] && headingSizes[2] && headingSizes[3]) {
        result.headingSizeHierarchy = headingSizes[1] > headingSizes[2] && headingSizes[2] > headingSizes[3];
    } else if (headingSizes[1] && headingSizes[2]) {
        result.headingSizeHierarchy = headingSizes[1] > headingSizes[2];
    }

    // Check heading bold
    const headingClasses = [...new Set(
        (html.match(/<h[1-3][^>]*class="([^"]+)"/gi) || [])
            .flatMap(m => (m.match(/class="([^"]+)"/)?.[1] || '').split(/\s+/))
    )];
    result.headingsBold = headingClasses.some(cn =>
        classes[cn] && (classes[cn]['font-weight'] === 'bold' ||
                        parseInt(classes[cn]['font-weight']) >= 700));

    // Text alignment
    const allProps = Object.values(classes);
    result.textAlignCenter = allProps.some(p => p['text-align'] === 'center') ||
        /text-align\s*:\s*center/i.test(html);
    result.textAlignRight = allProps.some(p => p['text-align'] === 'right') ||
        /text-align\s*:\s*right/i.test(html);

    // Blockquote style
    const bqClasses = [...new Set(
        (html.match(/<blockquote[^>]*class="([^"]+)"/gi) || [])
            .flatMap(m => (m.match(/class="([^"]+)"/)?.[1] || '').split(/\s+/))
    )];
    for (const cn of bqClasses) {
        const p = classes[cn];
        if (!p) continue;
        if (p['margin-left'] && parseCssSize(p['margin-left']) > 0) {
            result.blockquoteIndent = true;
        } else if (p['margin']) {
            // Parse margin shorthand: top right bottom left
            const parts = p['margin'].trim().split(/\s+/);
            let leftVal;
            if (parts.length === 4) leftVal = parts[3];
            else if (parts.length === 3) leftVal = parts[1]; // left = right
            else if (parts.length === 2) leftVal = parts[1]; // left = right
            else leftVal = parts[0];
            if (parseCssSize(leftVal) > 0) result.blockquoteIndent = true;
        }
        if (p['font-style'] === 'italic') result.blockquoteItalic = true;
    }
    // Also check inline blockquote styles
    if (!result.blockquoteIndent) {
        result.blockquoteIndent = /blockquote[^>]*style="[^"]*margin[^"]*[1-9]/i.test(html);
    }

    // Pre/code monospace + background
    const preClasses = [...new Set(
        (html.match(/<pre[^>]*class="([^"]+)"/gi) || [])
            .flatMap(m => (m.match(/class="([^"]+)"/)?.[1] || '').split(/\s+/))
    )];
    for (const cn of preClasses) {
        const p = classes[cn];
        if (!p) continue;
        if (p['font-family'] && p['font-family'].includes('monospace')) result.preMonospace = true;
        if (p['background-color'] || p['background']) result.preBackground = true;
    }

    // Table border + header styling
    const thClasses = [...new Set(
        (html.match(/<th[^>]*class="([^"]+)"/gi) || [])
            .flatMap(m => (m.match(/class="([^"]+)"/)?.[1] || '').split(/\s+/))
    )];
    const tdClasses = [...new Set(
        (html.match(/<td[^>]*class="([^"]+)"/gi) || [])
            .flatMap(m => (m.match(/class="([^"]+)"/)?.[1] || '').split(/\s+/))
    )];
    for (const cn of [...thClasses, ...tdClasses]) {
        const p = classes[cn];
        if (!p) continue;
        if (Object.keys(p).some(k => k.startsWith('border'))) result.tableBorder = true;
    }
    for (const cn of thClasses) {
        const p = classes[cn];
        if (!p) continue;
        if (p['font-weight'] === 'bold') result.tableHeaderBold = true;
        if (p['background-color'] || p['background']) result.tableHeaderBackground = true;
    }

    // Nested list indentation: check for nested <ul>/<ol> inside <li>
    result.nestedListIndent = /<li[^>]*>[\s\S]*?<[ou]l\b/i.test(html);

    // List style types
    result.listStyleDisc = allProps.some(p => p['list-style-type'] === 'disc');
    result.listStyleDecimal = allProps.some(p => p['list-style-type'] === 'decimal');

    // Link color (blue or any explicit color on <a>)
    const aClasses = [...new Set(
        (html.match(/<a [^>]*class="([^"]+)"/gi) || [])
            .flatMap(m => (m.match(/class="([^"]+)"/)?.[1] || '').split(/\s+/))
    )];
    result.linkColor = aClasses.some(cn => classes[cn] && classes[cn]['color']);
    // Also common: calibre uses hyperlink style or inline color on <a>
    if (!result.linkColor) {
        result.linkColor = /<a [^>]*style="[^"]*color/i.test(html);
    }

    return result;
}

/**
 * Extract style properties from DOCX output.
 * Parses word/styles.xml for font sizes, alignment, indentation.
 */
function extractDocxStyles(data) {
    const buf = Buffer.from(data);
    const tmpDir = mkdtempSync(join(tmpdir(), 'regdocxst-'));
    const zipPath = join(tmpDir, 'test.docx');
    writeFileSync(zipPath, buf);

    const result = {
        headingSizeHierarchy: false,
        headingsBold: false,
        textAlignCenter: false,
        textAlignRight: false,
        blockquoteIndent: false,
        preMonospace: false,
        tableBorder: false,
    };

    try {
        const stylesXml = execSync(
            `unzip -p "${zipPath}" "word/styles.xml" 2>/dev/null || true`,
            { maxBuffer: 10 * 1024 * 1024, encoding: 'utf-8' }
        );
        const docXml = execSync(
            `unzip -p "${zipPath}" "word/document.xml" 2>/dev/null || true`,
            { maxBuffer: 10 * 1024 * 1024, encoding: 'utf-8' }
        );

        // Extract heading sizes (w:sz is in half-points: 24 = 12pt)
        const headingSizes = {};
        for (const level of [1, 2, 3]) {
            const re = new RegExp(
                `<w:style[^>]*styleId="Heading ${level}"[^>]*>[\\s\\S]*?</w:style>`, 'i'
            );
            const m = stylesXml.match(re);
            if (m) {
                const szMatch = m[0].match(/<w:sz\s+w:val="(\d+)"/);
                if (szMatch) headingSizes[level] = parseInt(szMatch[1]);
                if (/<w:b\s+w:val="on"/i.test(m[0])) result.headingsBold = true;
            }
        }
        if (headingSizes[1] && headingSizes[2] && headingSizes[3]) {
            result.headingSizeHierarchy = headingSizes[1] > headingSizes[2] && headingSizes[2] > headingSizes[3];
        } else if (headingSizes[1] && headingSizes[2]) {
            result.headingSizeHierarchy = headingSizes[1] > headingSizes[2];
        }

        // Check for bold headings via any heading style
        if (!result.headingsBold) {
            const headingStyles = stylesXml.match(/<w:style[^>]*styleId="Heading[^"]*"[\s\S]*?<\/w:style>/gi) || [];
            result.headingsBold = headingStyles.some(s => /<w:b\s+w:val="on"/i.test(s));
        }

        // Alignment: check both styles.xml and document.xml
        result.textAlignCenter = /w:val="center"/i.test(stylesXml) || /<w:jc\s+w:val="center"/i.test(docXml);
        result.textAlignRight = /w:val="right"/i.test(stylesXml) || /<w:jc\s+w:val="right"/i.test(docXml);

        // Indentation (blockquote-like)
        result.blockquoteIndent = /<w:ind\s+w:left="[1-9]\d{2,}"/i.test(stylesXml) ||
            /<w:ind\s+w:left="[1-9]\d{2,}"/i.test(docXml);

        // Monospace font for preformatted
        result.preMonospace = /monospace|courier/i.test(stylesXml);

        // Table borders
        result.tableBorder = /<w:tblBorders\b/i.test(docXml) || /<w:tcBorders\b/i.test(docXml);
    } catch { /* ignore */ } finally {
        try { rmSync(tmpDir, { recursive: true, force: true }); } catch {}
    }

    return result;
}

/**
 * Detect style properties in the converted output.
 */
function detectStyles(data, format) {
    switch (format) {
        case 'html':
        case 'htm':
        case 'epub':
        case 'htmlz':
        case 'oeb':
            return extractHtmlStyles(data, format);
        case 'docx':
            return extractDocxStyles(data);
        default:
            return {};
    }
}

// Formats that support CSS/style verification
// Note: 'html' excluded — calibre outputs HTML with external style.css link not in the buffer
const STYLE_FORMATS = ['epub', 'htmlz', 'oeb', 'docx'];

// Which style checks are expected to pass per format
const EXPECTED_STYLES = {
    epub:  { headingSizeHierarchy: true, headingsBold: true, textAlignCenter: true, textAlignRight: true, blockquoteIndent: true, blockquoteItalic: true, preMonospace: true, preBackground: true, tableBorder: true, tableHeaderBold: true, tableHeaderBackground: true, nestedListIndent: true, listStyleDisc: true, listStyleDecimal: true },
    htmlz: { headingSizeHierarchy: true, headingsBold: true, textAlignCenter: true, textAlignRight: true, blockquoteIndent: true, blockquoteItalic: true, preMonospace: true, preBackground: true, tableBorder: true, tableHeaderBold: true, tableHeaderBackground: true, nestedListIndent: true, listStyleDisc: true, listStyleDecimal: true },
    oeb:   { headingSizeHierarchy: true, headingsBold: true, textAlignCenter: true, textAlignRight: true, blockquoteIndent: true, blockquoteItalic: true, preMonospace: true, preBackground: true, tableBorder: true, tableHeaderBold: true, tableHeaderBackground: true, nestedListIndent: true, listStyleDisc: true, listStyleDecimal: true },
    docx:  { headingSizeHierarchy: true, headingsBold: true, textAlignCenter: true, textAlignRight: true, blockquoteIndent: true, preMonospace: true, tableBorder: false },
};

// --------------- Structural validators ---------------

/**
 * Check if data is a valid ZIP file (EPUB, DOCX, HTMLZ, OEB are ZIP-based).
 */
function isValidZip(data) {
    if (data.length < 4) return false;
    // ZIP magic: PK\x03\x04
    return data[0] === 0x50 && data[1] === 0x4B && data[2] === 0x03 && data[3] === 0x04;
}

/**
 * Check if data starts with a PDF header.
 */
function isValidPdf(data) {
    if (data.length < 5) return false;
    const header = String.fromCharCode(...data.slice(0, 5));
    return header === '%PDF-';
}

/**
 * Check if data is valid RTF.
 */
function isValidRtf(data) {
    if (data.length < 5) return false;
    const header = String.fromCharCode(...data.slice(0, 5));
    return header === '{\\rtf';
}

/**
 * Check if data looks like FB2 XML.
 */
function isValidFb2(data) {
    const str = Buffer.from(data).toString('utf-8', 0, Math.min(data.length, 500));
    return str.includes('FictionBook') || str.includes('<?xml');
}

// --------------- Test data ---------------

const FIXTURES_DIR = 'tests/fixtures';
const regressionHtml = readFileSync(`${FIXTURES_DIR}/regression.html`);

// Content markers that must survive conversion
const CONTENT_MARKERS = {
    title: 'The Art of Document Conversion',
    bold_text: 'bold text',
    italic_text: 'italic text',
    heading_ch1: 'Text Formatting',
    heading_ch2: 'Lists',
    heading_ch3: 'Tables',
    heading_ch4: 'Block Elements',
    list_item: 'First item',
    table_epub: 'EPUB',
    table_pdf: 'PDF',
    blockquote: 'Alan Kay',
    preformatted: 'convert_ebook',
    link_text: 'Calibre',
    special_cafe: 'caf',
    ordered_list: 'numbered item',
    definition_epub: 'Electronic Publication',
    author_ref: 'Test Author',
};

// Format-specific structural validators
const STRUCTURE_VALIDATORS = {
    epub:  (data) => ({ valid: isValidZip(data), reason: 'EPUB must be a valid ZIP file' }),
    docx:  (data) => ({ valid: isValidZip(data), reason: 'DOCX must be a valid ZIP file' }),
    htmlz: (data) => ({ valid: isValidZip(data), reason: 'HTMLZ must be a valid ZIP file' }),
    oeb:   (data) => ({ valid: isValidZip(data), reason: 'OEB must be a valid ZIP file' }),
    pmlz:  (data) => ({ valid: isValidZip(data), reason: 'PMLZ must be a valid ZIP file' }),
    pdf:   (data) => ({ valid: isValidPdf(data), reason: 'PDF must start with %PDF-' }),
    rtf:   (data) => ({ valid: isValidRtf(data), reason: 'RTF must start with {\\rtf' }),
    fb2:   (data) => ({ valid: isValidFb2(data), reason: 'FB2 must be valid XML with FictionBook' }),
};

// Minimum expected output sizes (bytes) per format
// These baselines catch catastrophic regressions (e.g., empty or truncated output)
const MIN_OUTPUT_SIZES = {
    epub:  1000,
    docx:  1000,
    htmlz: 500,
    html:  200,
    fb2:   500,
    pdf:   1000,
    txt:   100,
    rtf:   200,
    mobi:  1000,
    azw3:  1000,
    lrf:   500,
    pdb:   200,
    tcr:   100,
    snb:   200,
    rb:    200,
    pmlz:  200,
    oeb:   500,
};

// Output formats to test
const OUTPUT_FORMATS = [
    'epub', 'docx', 'htmlz', 'html', 'fb2', 'pdf', 'txt', 'rtf',
    'mobi', 'azw3', 'lrf', 'pdb', 'tcr', 'snb', 'rb', 'pmlz', 'oeb',
];

// Formats that support formatting verification via markup inspection
const FORMATTING_FORMATS = ['epub', 'docx', 'htmlz', 'html', 'fb2', 'rtf', 'oeb'];

// Expected formatting features per format (based on what the input HTML contains)
// Each entry lists which formatting features the format CAN represent.
const EXPECTED_FORMATTING = {
    html:  { bold: true, italic: true, headings: true, unorderedList: true, orderedList: true, table: true, blockquote: true, preformatted: true, links: true },
    epub:  { bold: true, italic: true, headings: true, unorderedList: true, orderedList: true, table: true, blockquote: true, preformatted: true, links: true },
    htmlz: { bold: true, italic: true, headings: true, unorderedList: true, orderedList: true, table: true, blockquote: true, preformatted: true, links: true },
    oeb:   { bold: true, italic: true, headings: true, unorderedList: true, orderedList: true, table: true, blockquote: true, preformatted: true, links: true },
    docx:  { bold: true, italic: true, headings: true, unorderedList: true, orderedList: true, table: true, blockquote: false, preformatted: false, links: true },
    fb2:   { bold: true, italic: true, headings: true, unorderedList: false, orderedList: false, table: false, blockquote: false, preformatted: false, links: true },
    rtf:   { bold: true, italic: true, headings: true, unorderedList: false, orderedList: false, table: false, blockquote: false, preformatted: false, links: false },
};

// --------------- Test suites ---------------

describe('regression tests', { concurrency: POOL_SIZE }, () => {
    before(async () => {
        console.log(`Initializing ${POOL_SIZE} regression test worker(s)…`);
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

    // === Structure validation ===
    for (const fmt of OUTPUT_FORMATS) {
        test(`structure: HTML -> ${fmt.toUpperCase()}`, async () => {
            const worker = await acquire();
            try {
                const result = await convert(
                    worker, regressionHtml, 'regression.html', `regression.${fmt}`
                );

                // 1. Non-empty output
                assert.ok(result.length > 0, `${fmt} output is empty`);

                // 2. Minimum size check
                const minSize = MIN_OUTPUT_SIZES[fmt] || 100;
                assert.ok(
                    result.length >= minSize,
                    `${fmt} output too small: ${result.length} bytes (min ${minSize})`
                );

                // 3. Format-specific structural validation
                const validator = STRUCTURE_VALIDATORS[fmt];
                if (validator) {
                    const { valid, reason } = validator(result);
                    assert.ok(valid, `${fmt} structural check failed: ${reason}`);
                }
            } finally {
                release(worker);
            }
        });
    }

    // === Content preservation ===
    const textFormats = ['epub', 'docx', 'htmlz', 'html', 'fb2', 'txt', 'rtf'];

    for (const fmt of textFormats) {
        test(`content: HTML -> ${fmt.toUpperCase()} title preserved`, async () => {
            const worker = await acquire();
            try {
                const result = await convert(
                    worker, regressionHtml, 'regression.html', `content_${fmt}.${fmt}`
                );
                const text = extractText(result, fmt);
                assert.ok(
                    text.includes(CONTENT_MARKERS.title) ||
                    text.toLowerCase().includes(CONTENT_MARKERS.title.toLowerCase()),
                    `${fmt}: title "${CONTENT_MARKERS.title}" not found in output`
                );
            } finally {
                release(worker);
            }
        });

        test(`content: HTML -> ${fmt.toUpperCase()} headings preserved`, async () => {
            const worker = await acquire();
            try {
                const result = await convert(
                    worker, regressionHtml, 'regression.html', `heading_${fmt}.${fmt}`
                );
                const text = extractText(result, fmt);
                assert.ok(
                    text.includes(CONTENT_MARKERS.heading_ch1) ||
                    text.toLowerCase().includes(CONTENT_MARKERS.heading_ch1.toLowerCase()),
                    `${fmt}: heading "${CONTENT_MARKERS.heading_ch1}" not found`
                );
            } finally {
                release(worker);
            }
        });

        test(`content: HTML -> ${fmt.toUpperCase()} body text preserved`, async () => {
            const worker = await acquire();
            try {
                const result = await convert(
                    worker, regressionHtml, 'regression.html', `body_${fmt}.${fmt}`
                );
                const text = extractText(result, fmt);
                const coreWords = ['formatting', 'document', 'conversion'];
                const found = coreWords.filter(w =>
                    text.toLowerCase().includes(w.toLowerCase()));
                assert.ok(
                    found.length >= 2,
                    `${fmt}: body text check failed. Found ${found.length}/3 core words: ${found.join(', ')}`
                );
            } finally {
                release(worker);
            }
        });

        test(`content: HTML -> ${fmt.toUpperCase()} table data preserved`, async () => {
            const worker = await acquire();
            try {
                const result = await convert(
                    worker, regressionHtml, 'regression.html', `table_${fmt}.${fmt}`
                );
                const text = extractText(result, fmt);
                const tableTerms = ['EPUB', 'Reflowable', 'DOCX'];
                const found = tableTerms.filter(t => text.includes(t));
                assert.ok(
                    found.length >= 1,
                    `${fmt}: table content check failed. Found: ${found.join(', ') || 'none'}`
                );
            } finally {
                release(worker);
            }
        });

        test(`content: HTML -> ${fmt.toUpperCase()} lists preserved`, async () => {
            const worker = await acquire();
            try {
                const result = await convert(
                    worker, regressionHtml, 'regression.html', `list_${fmt}.${fmt}`
                );
                const text = extractText(result, fmt);
                assert.ok(
                    text.toLowerCase().includes('first item') ||
                    text.toLowerCase().includes('unordered list') ||
                    text.toLowerCase().includes('numbered item'),
                    `${fmt}: no list content found in output`
                );
            } finally {
                release(worker);
            }
        });

        test(`content: HTML -> ${fmt.toUpperCase()} blockquote preserved`, async () => {
            const worker = await acquire();
            try {
                const result = await convert(
                    worker, regressionHtml, 'regression.html', `quote_${fmt}.${fmt}`
                );
                const text = extractText(result, fmt);
                assert.ok(
                    text.includes(CONTENT_MARKERS.blockquote) ||
                    text.includes('predict the future'),
                    `${fmt}: blockquote content "${CONTENT_MARKERS.blockquote}" not found`
                );
            } finally {
                release(worker);
            }
        });

        test(`content: HTML -> ${fmt.toUpperCase()} preformatted preserved`, async () => {
            const worker = await acquire();
            try {
                const result = await convert(
                    worker, regressionHtml, 'regression.html', `pre_${fmt}.${fmt}`
                );
                const text = extractText(result, fmt);
                assert.ok(
                    text.includes(CONTENT_MARKERS.preformatted) ||
                    text.includes('plumber') || text.includes('Plumber'),
                    `${fmt}: preformatted content "${CONTENT_MARKERS.preformatted}" not found`
                );
            } finally {
                release(worker);
            }
        });
    }

    // === Cross-format output size baselines ===
    const crossFormatTests = [
        { input: 'test.epub', output: 'epub' },
        { input: 'test.epub', output: 'docx' },
        { input: 'test.epub', output: 'pdf' },
        { input: 'test.epub', output: 'txt' },
        { input: 'test.epub', output: 'fb2' },
        { input: 'test.html', output: 'epub' },
        { input: 'test.fb2',  output: 'epub' },
        { input: 'test.txt',  output: 'epub' },
    ];

    for (const { input, output } of crossFormatTests) {
        const inputFmt = input.split('.').pop().toUpperCase();
        const outputFmt = output.toUpperCase();

        test(`size: ${inputFmt} -> ${outputFmt} reasonable`, async () => {
            const inputPath = `${FIXTURES_DIR}/${input}`;
            if (!existsSync(inputPath)) return;
            const inputData = readFileSync(inputPath);

            const worker = await acquire();
            try {
                const result = await convert(
                    worker, inputData, input, `size_output.${output}`
                );

                assert.ok(
                    result.length > 100,
                    `${inputFmt}->${outputFmt}: output only ${result.length} bytes`
                );

                const ratio = result.length / inputData.length;
                assert.ok(
                    ratio < 100,
                    `${inputFmt}->${outputFmt}: output/input ratio ${ratio.toFixed(1)}x is suspiciously high`
                );
            } finally {
                release(worker);
            }
        });
    }

    // === Round-trip fidelity ===
    const roundTripFormats = ['epub', 'htmlz', 'docx', 'fb2'];

    for (const fmt of roundTripFormats) {
        test(`round-trip: HTML -> ${fmt.toUpperCase()} -> HTML`, async () => {
            const worker = await acquire();
            try {
                // Step 1: Convert HTML → fmt
                const intermediate = await convert(
                    worker, regressionHtml, 'regression.html', `rt_intermediate.${fmt}`
                );
                assert.ok(intermediate.length > 0, `Intermediate ${fmt} is empty`);

                // Step 2: Convert fmt → HTML
                const roundTripped = await convert(
                    worker, intermediate, `rt_intermediate.${fmt}`, 'rt_output.html'
                );
                assert.ok(roundTripped.length > 0, 'Round-trip HTML output is empty');

                // Step 3: Check key content survived
                const text = stripHtmlTags(Buffer.from(roundTripped).toString('utf-8'));
                const keywords = ['Document Conversion', 'Formatting', 'Tables', 'Lists'];
                const found = keywords.filter(kw =>
                    text.toLowerCase().includes(kw.toLowerCase()));
                assert.ok(
                    found.length >= 2,
                    `Round-trip via ${fmt}: only ${found.length}/4 keywords survived: ${found.join(', ')}`
                );
            } finally {
                release(worker);
            }
        });
    }

    // === Formatting preservation ===
    // Verifies that formatting elements (bold, italic, headings, lists, tables, etc.)
    // survive conversion by inspecting the raw markup of the output.

    for (const fmt of FORMATTING_FORMATS) {
        const expected = EXPECTED_FORMATTING[fmt];
        if (!expected) continue;

        test(`formatting: HTML -> ${fmt.toUpperCase()} bold preserved`, async () => {
            const worker = await acquire();
            try {
                const result = await convert(
                    worker, regressionHtml, 'regression.html', `fmt_bold.${fmt}`
                );
                const detected = detectFormatting(result, fmt);
                assert.ok(
                    detected.bold,
                    `${fmt}: bold formatting not found in output markup`
                );
            } finally {
                release(worker);
            }
        });

        test(`formatting: HTML -> ${fmt.toUpperCase()} italic preserved`, async () => {
            const worker = await acquire();
            try {
                const result = await convert(
                    worker, regressionHtml, 'regression.html', `fmt_italic.${fmt}`
                );
                const detected = detectFormatting(result, fmt);
                assert.ok(
                    detected.italic,
                    `${fmt}: italic formatting not found in output markup`
                );
            } finally {
                release(worker);
            }
        });

        test(`formatting: HTML -> ${fmt.toUpperCase()} headings preserved`, async () => {
            const worker = await acquire();
            try {
                const result = await convert(
                    worker, regressionHtml, 'regression.html', `fmt_headings.${fmt}`
                );
                const detected = detectFormatting(result, fmt);
                assert.ok(
                    detected.headings,
                    `${fmt}: heading formatting not found in output markup`
                );
            } finally {
                release(worker);
            }
        });

        if (expected.unorderedList) {
            test(`formatting: HTML -> ${fmt.toUpperCase()} unordered list preserved`, async () => {
                const worker = await acquire();
                try {
                    const result = await convert(
                        worker, regressionHtml, 'regression.html', `fmt_ul.${fmt}`
                    );
                    const detected = detectFormatting(result, fmt);
                    assert.ok(
                        detected.unorderedList,
                        `${fmt}: unordered list formatting not found in output markup`
                    );
                } finally {
                    release(worker);
                }
            });
        }

        if (expected.orderedList) {
            test(`formatting: HTML -> ${fmt.toUpperCase()} ordered list preserved`, async () => {
                const worker = await acquire();
                try {
                    const result = await convert(
                        worker, regressionHtml, 'regression.html', `fmt_ol.${fmt}`
                    );
                    const detected = detectFormatting(result, fmt);
                    assert.ok(
                        detected.orderedList,
                        `${fmt}: ordered list formatting not found in output markup`
                    );
                } finally {
                    release(worker);
                }
            });
        }

        if (expected.table) {
            test(`formatting: HTML -> ${fmt.toUpperCase()} table preserved`, async () => {
                const worker = await acquire();
                try {
                    const result = await convert(
                        worker, regressionHtml, 'regression.html', `fmt_table.${fmt}`
                    );
                    const detected = detectFormatting(result, fmt);
                    assert.ok(
                        detected.table,
                        `${fmt}: table formatting not found in output markup`
                    );
                } finally {
                    release(worker);
                }
            });
        }

        if (expected.blockquote) {
            test(`formatting: HTML -> ${fmt.toUpperCase()} blockquote preserved`, async () => {
                const worker = await acquire();
                try {
                    const result = await convert(
                        worker, regressionHtml, 'regression.html', `fmt_bq.${fmt}`
                    );
                    const detected = detectFormatting(result, fmt);
                    assert.ok(
                        detected.blockquote,
                        `${fmt}: blockquote formatting not found in output markup`
                    );
                } finally {
                    release(worker);
                }
            });
        }

        if (expected.preformatted) {
            test(`formatting: HTML -> ${fmt.toUpperCase()} preformatted preserved`, async () => {
                const worker = await acquire();
                try {
                    const result = await convert(
                        worker, regressionHtml, 'regression.html', `fmt_pre.${fmt}`
                    );
                    const detected = detectFormatting(result, fmt);
                    assert.ok(
                        detected.preformatted,
                        `${fmt}: preformatted/code formatting not found in output markup`
                    );
                } finally {
                    release(worker);
                }
            });
        }

        if (expected.links) {
            test(`formatting: HTML -> ${fmt.toUpperCase()} links preserved`, async () => {
                const worker = await acquire();
                try {
                    const result = await convert(
                        worker, regressionHtml, 'regression.html', `fmt_links.${fmt}`
                    );
                    const detected = detectFormatting(result, fmt);
                    assert.ok(
                        detected.links,
                        `${fmt}: hyperlink formatting not found in output markup`
                    );
                } finally {
                    release(worker);
                }
            });
        }
    }

    // === Style/CSS preservation ===
    // Verifies that CSS properties (font-size hierarchy, text-align, margins,
    // font-family, colors, backgrounds) survive conversion.

    for (const fmt of STYLE_FORMATS) {
        const expectedStyle = EXPECTED_STYLES[fmt];
        if (!expectedStyle) continue;

        if (expectedStyle.headingSizeHierarchy) {
            test(`style: HTML -> ${fmt.toUpperCase()} heading size hierarchy (h1 > h2 > h3)`, async () => {
                const worker = await acquire();
                try {
                    const result = await convert(
                        worker, regressionHtml, 'regression.html', `sty_hsz.${fmt}`
                    );
                    const styles = detectStyles(result, fmt);
                    assert.ok(
                        styles.headingSizeHierarchy,
                        `${fmt}: heading font-size hierarchy not preserved (h1 > h2 > h3)`
                    );
                } finally {
                    release(worker);
                }
            });
        }

        if (expectedStyle.headingsBold) {
            test(`style: HTML -> ${fmt.toUpperCase()} headings are bold`, async () => {
                const worker = await acquire();
                try {
                    const result = await convert(
                        worker, regressionHtml, 'regression.html', `sty_hbold.${fmt}`
                    );
                    const styles = detectStyles(result, fmt);
                    assert.ok(
                        styles.headingsBold,
                        `${fmt}: heading bold style not preserved`
                    );
                } finally {
                    release(worker);
                }
            });
        }

        if (expectedStyle.textAlignCenter) {
            test(`style: HTML -> ${fmt.toUpperCase()} text-align center preserved`, async () => {
                const worker = await acquire();
                try {
                    const result = await convert(
                        worker, regressionHtml, 'regression.html', `sty_center.${fmt}`
                    );
                    const styles = detectStyles(result, fmt);
                    assert.ok(
                        styles.textAlignCenter,
                        `${fmt}: text-align: center not preserved`
                    );
                } finally {
                    release(worker);
                }
            });
        }

        if (expectedStyle.textAlignRight) {
            test(`style: HTML -> ${fmt.toUpperCase()} text-align right preserved`, async () => {
                const worker = await acquire();
                try {
                    const result = await convert(
                        worker, regressionHtml, 'regression.html', `sty_right.${fmt}`
                    );
                    const styles = detectStyles(result, fmt);
                    assert.ok(
                        styles.textAlignRight,
                        `${fmt}: text-align: right not preserved`
                    );
                } finally {
                    release(worker);
                }
            });
        }

        if (expectedStyle.blockquoteIndent) {
            test(`style: HTML -> ${fmt.toUpperCase()} blockquote indentation preserved`, async () => {
                const worker = await acquire();
                try {
                    const result = await convert(
                        worker, regressionHtml, 'regression.html', `sty_bqind.${fmt}`
                    );
                    const styles = detectStyles(result, fmt);
                    assert.ok(
                        styles.blockquoteIndent,
                        `${fmt}: blockquote margin-left/indent not preserved`
                    );
                } finally {
                    release(worker);
                }
            });
        }

        if (expectedStyle.blockquoteItalic) {
            test(`style: HTML -> ${fmt.toUpperCase()} blockquote italic style preserved`, async () => {
                const worker = await acquire();
                try {
                    const result = await convert(
                        worker, regressionHtml, 'regression.html', `sty_bqit.${fmt}`
                    );
                    const styles = detectStyles(result, fmt);
                    assert.ok(
                        styles.blockquoteItalic,
                        `${fmt}: blockquote font-style: italic not preserved`
                    );
                } finally {
                    release(worker);
                }
            });
        }

        if (expectedStyle.preMonospace) {
            test(`style: HTML -> ${fmt.toUpperCase()} pre monospace font preserved`, async () => {
                const worker = await acquire();
                try {
                    const result = await convert(
                        worker, regressionHtml, 'regression.html', `sty_mono.${fmt}`
                    );
                    const styles = detectStyles(result, fmt);
                    assert.ok(
                        styles.preMonospace,
                        `${fmt}: pre font-family: monospace not preserved`
                    );
                } finally {
                    release(worker);
                }
            });
        }

        if (expectedStyle.preBackground) {
            test(`style: HTML -> ${fmt.toUpperCase()} pre background-color preserved`, async () => {
                const worker = await acquire();
                try {
                    const result = await convert(
                        worker, regressionHtml, 'regression.html', `sty_prebg.${fmt}`
                    );
                    const styles = detectStyles(result, fmt);
                    assert.ok(
                        styles.preBackground,
                        `${fmt}: pre background-color not preserved`
                    );
                } finally {
                    release(worker);
                }
            });
        }

        if (expectedStyle.tableBorder) {
            test(`style: HTML -> ${fmt.toUpperCase()} table border preserved`, async () => {
                const worker = await acquire();
                try {
                    const result = await convert(
                        worker, regressionHtml, 'regression.html', `sty_tbrd.${fmt}`
                    );
                    const styles = detectStyles(result, fmt);
                    assert.ok(
                        styles.tableBorder,
                        `${fmt}: table border style not preserved`
                    );
                } finally {
                    release(worker);
                }
            });
        }

        if (expectedStyle.tableHeaderBold) {
            test(`style: HTML -> ${fmt.toUpperCase()} table header bold preserved`, async () => {
                const worker = await acquire();
                try {
                    const result = await convert(
                        worker, regressionHtml, 'regression.html', `sty_thb.${fmt}`
                    );
                    const styles = detectStyles(result, fmt);
                    assert.ok(
                        styles.tableHeaderBold,
                        `${fmt}: table header font-weight: bold not preserved`
                    );
                } finally {
                    release(worker);
                }
            });
        }

        if (expectedStyle.tableHeaderBackground) {
            test(`style: HTML -> ${fmt.toUpperCase()} table header background preserved`, async () => {
                const worker = await acquire();
                try {
                    const result = await convert(
                        worker, regressionHtml, 'regression.html', `sty_thbg.${fmt}`
                    );
                    const styles = detectStyles(result, fmt);
                    assert.ok(
                        styles.tableHeaderBackground,
                        `${fmt}: table header background-color not preserved`
                    );
                } finally {
                    release(worker);
                }
            });
        }

        if (expectedStyle.nestedListIndent) {
            test(`style: HTML -> ${fmt.toUpperCase()} nested list structure preserved`, async () => {
                const worker = await acquire();
                try {
                    const result = await convert(
                        worker, regressionHtml, 'regression.html', `sty_nest.${fmt}`
                    );
                    const styles = detectStyles(result, fmt);
                    assert.ok(
                        styles.nestedListIndent,
                        `${fmt}: nested list indentation not preserved`
                    );
                } finally {
                    release(worker);
                }
            });
        }

        if (expectedStyle.listStyleDisc) {
            test(`style: HTML -> ${fmt.toUpperCase()} list-style-type disc preserved`, async () => {
                const worker = await acquire();
                try {
                    const result = await convert(
                        worker, regressionHtml, 'regression.html', `sty_disc.${fmt}`
                    );
                    const styles = detectStyles(result, fmt);
                    assert.ok(
                        styles.listStyleDisc,
                        `${fmt}: list-style-type: disc not preserved`
                    );
                } finally {
                    release(worker);
                }
            });
        }

        if (expectedStyle.listStyleDecimal) {
            test(`style: HTML -> ${fmt.toUpperCase()} list-style-type decimal preserved`, async () => {
                const worker = await acquire();
                try {
                    const result = await convert(
                        worker, regressionHtml, 'regression.html', `sty_dec.${fmt}`
                    );
                    const styles = detectStyles(result, fmt);
                    assert.ok(
                        styles.listStyleDecimal,
                        `${fmt}: list-style-type: decimal not preserved`
                    );
                } finally {
                    release(worker);
                }
            });
        }
    }
});
