"""Pure-Python PalmDoc LZ77 compression/decompression for calibre_extensions.cPalmdoc."""

import io
from struct import pack

def decompress(data):
    """PalmDoc LZ77 decompression."""
    if not data:
        return b''
    if isinstance(data, str):
        data = data.encode('latin-1')

    out = bytearray()
    i = 0
    length = len(data)

    while i < length:
        c = data[i]
        i += 1

        if c == 0x00:

            out.append(c)
        elif 1 <= c <= 8:

            end = min(i + c, length)
            out.extend(data[i:end])
            i = end
        elif c <= 0x7F:

            out.append(c)
        elif c <= 0xBF:

            if i >= length:
                break
            c2 = data[i]
            i += 1
            distance = ((c << 8 | c2) >> 3) & 0x7FF
            copy_len = (c2 & 0x07) + 3
            if distance > 0:
                pos = len(out) - distance
                for _ in range(copy_len):
                    out.append(out[pos])
                    pos += 1
        else:

            out.append(0x20)
            out.append(c ^ 0x80)

    return bytes(out)

def compress(data):
    """PalmDoc LZ77 compression."""
    if not data:
        return b''
    if isinstance(data, str):
        data = data.encode('utf-8')

    out = io.BytesIO()
    i = 0
    ldata = len(data)

    while i < ldata:

        if i > 10 and (ldata - i) > 10:
            chunk = b''
            match = -1
            for j in range(10, 2, -1):
                chunk = data[i:i + j]
                try:
                    match = data.rindex(chunk, 0, i)
                except ValueError:
                    continue
                if (i - match) <= 2047:
                    break
                match = -1
            if match >= 0:
                n = len(chunk)
                m = i - match
                code = 0x8000 + ((m << 3) & 0x3FF8) + (n - 3)
                out.write(pack('>H', code))
                i += n
                continue

        ch = data[i:i + 1]
        och = ord(ch)
        i += 1

        if ch == b' ' and (i + 1) < ldata:
            onch = ord(data[i:i + 1])
            if 0x40 <= onch < 0x80:
                out.write(bytes([onch ^ 0x80]))
                i += 1
                continue

        if och == 0 or (0x09 <= och <= 0x7F):
            out.write(ch)
        else:

            j = i
            binseq = [och]
            while j < ldata and len(binseq) < 8:
                onch = ord(data[j:j + 1])
                if onch == 0 or (0x09 <= onch <= 0x7F):
                    break
                binseq.append(onch)
                j += 1
            out.write(bytes([len(binseq)] + binseq))
            i = j

    return out.getvalue()
