"""Extract the player-visible strings of Avernum 3 Files/A3ScenData.dat.

usage:
    python -I scen_extract.py ORIGINAL_ASCENDATA OUT_DIR

File layout of A3ScenData.dat (Avernum 3: Ruined World; record sizes from the script-name
fields, field offsets from the strings in the records):
    0x000000  header, 0xac bytes
    0x0000ac  90 outdoor sections, 0x66d8 bytes each
    0x24289c  200 towns, 0x1f89c bytes each
String fields used here (record-relative offset, count, stride, field size):
    outdoor  name  +0x0008  1        30      area names +0x3f60 16 x 0x100   signs +0x32b8 8 x 0x100
    town     name  +0x0002  1        26      area names +0x65e0 16 x 0x100   signs +0x7658 15 x 0x100
             labels +0x9a28 15 x 0x28
(designer notes at outdoor +0x4fb0 / town +0x85a8 and script names are not shown in game; outdoor
sections have no map labels in this game.)

Writes OUT_DIR/units.json: [{"id", "kind", "en", "max_bytes", "offsets": [file offsets]}]
with identical (kind, English) entries merged.
"""
import json
import os
import re
import sys

sys.stdout.reconfigure(encoding='utf-8')

# Avernum 4: a 0x148-byte header, then 168 zones of 0xCF28 bytes (outdoor areas are zones too).
TOWN = (0x148, 0xCF28, 168)
# kind, record set, first offset, count, stride, field size, max bytes for a translation
FIELDS = [
    ('town name', TOWN, 0x6, 1, 0, 20, 19),
    ('town label', TOWN, 0xcd5c, 10, 0x28, 0x28, 39),
]
TEXT = re.compile(rb'[\x20-\x7e]*[A-Za-z]{2}[\x20-\x7e]*')


def main(argv):
    if len(argv) != 2:
        print(__doc__)
        return 2
    src, out = argv
    d = open(src, 'rb').read()
    units = {}
    for kind, (base, size, n), first, count, stride, fsize, maxb in FIELDS:
        for r in range(n):
            for k in range(count):
                off = base + r * size + first + k * stride
                field = d[off:off + fsize]
                z = field.find(b'\0')
                if z <= 0:
                    continue
                s = field[:z]
                if not TEXT.fullmatch(s):
                    continue
                en = s.decode('ascii')
                key = (kind.split()[1], en)
                u = units.get(key)
                if u is None:
                    u = units[key] = {'id': f'{kind.split()[1]}{len(units):04d}', 'kind': kind, 'en': en,
                                      'max_bytes': maxb, 'fields': []}
                u['max_bytes'] = min(u['max_bytes'], maxb)
                u['fields'].append([off, fsize])
    os.makedirs(out, exist_ok=True)
    lst = list(units.values())
    with open(os.path.join(out, 'units.json'), 'w', encoding='utf-8') as f:
        json.dump(lst, f, ensure_ascii=False, indent=0)
    by = {}
    for u in lst:
        by[u['kind']] = by.get(u['kind'], 0) + 1
    print(len(lst), 'unique strings', sum(len(u['fields']) for u in lst), 'fields', by,
          sum(len(u['en']) for u in lst), 'chars')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
