import { EbookConverter } from '../../dist/node/ebook-convert.mjs';

const converter = new EbookConverter();
await converter.init();

process.send({ type: 'ready' });

process.on('message', async (msg) => {
    if (msg.type === 'convert') {
        try {
            const inputData = new Uint8Array(Buffer.from(msg.inputData, 'base64'));
            converter.writeFile(msg.inputName, inputData);
            const baseName = msg.inputName.replace(/\.[^.]+$/, '');
            const outputFile = msg.outputFile || `${baseName}.${msg.outputFormat}`;
            const result = await converter.convert(
                msg.inputName,
                outputFile,
            );
            process.send({
                type: 'result',
                id: msg.id,
                data: Buffer.from(result).toString('base64'),
            });
        } catch (e) {
            process.send({ type: 'error', id: msg.id, message: e?.message ?? String(e) });
        }
    } else if (msg.type === 'exit') {
        try { await converter.destroy(); } catch {}
        process.exit(0);
    }
});
