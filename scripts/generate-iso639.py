#!/usr/bin/env python3
"""
Generate the ISO 639 language code maps used by calibre.utils.localization.

calibre builds resources/localization/iso639.calibre_msgpack from the
iso-codes project at build time. This script applies the same algorithm
(see ISO639 in calibre's setup/translations.py) and writes the result as JSON,
which the WASM localization stub loads from calibre/data/localization/.

Usage:
    python3 scripts/generate-iso639.py <iso-codes.zip | iso_639-3.json> <output.json>

calibre uses https://download.calibre-ebook.com/iso-codes.zip, a snapshot of
the iso-codes project. iso_639-3.json is also shipped by the iso-codes package
(/usr/share/iso-codes/json/iso_639-3.json on Debian/Ubuntu).
"""
import json
import os
import sys
import zipfile


def build(entries):
    by_2, by_3, m2to3, m3to2, nm = {}, {}, {}, {}, {}
    for x in entries:
        two = x.get('alpha_2')
        threeb = x.get('alpha_3')
        if threeb is None:
            continue
        name = x.get('inverted_name') or x.get('name')
        if not name or name[0] in '!~=/\'"':
            continue
        if two is not None:
            by_2[two] = name
            m2to3[two] = threeb
            m3to2[threeb] = two
        by_3[threeb] = name
        nm[name.lower()] = threeb
    return {'by_2': by_2, 'by_3': by_3, '2to3': m2to3, '3to2': m3to2, 'name_map': nm}


def main():
    if len(sys.argv) != 3:
        raise SystemExit(__doc__)
    src, dest = sys.argv[1:]
    if zipfile.is_zipfile(src):
        with zipfile.ZipFile(src) as zf:
            name = next(n for n in zf.namelist() if n.endswith('/data/iso_639-3.json'))
            entries = json.loads(zf.read(name))['639-3']
    else:
        with open(src, 'rb') as f:
            entries = json.load(f)['639-3']
    data = build(entries)
    os.makedirs(os.path.dirname(os.path.abspath(dest)), exist_ok=True)
    with open(dest, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, separators=(',', ':'), sort_keys=True)
    print(f'  Wrote {len(data["by_3"])} ISO 639 languages to {dest}')


if __name__ == '__main__':
    main()
