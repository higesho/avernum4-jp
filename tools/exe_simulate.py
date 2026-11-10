"""Show how assembled messages will read in Japanese.

usage:
    python -I exe_simulate.py OUT_DIR

For every usage description in OUT_DIR/chunks/*.json, substitutes the translated
pieces (OUT_DIR/ja/*.json and the already-translated rows), [名前など]/[名前A] ->
ブリッサ, [名前Bまたは値] -> ゴブリン, [数値] -> 5, None -> "." and prints
English -> Japanese, one per unique description.
"""
import json
import os
import re
import sys

sys.stdout.reconfigure(encoding='utf-8')
QUOTED = re.compile(r"'((?:[^'\\]|\\.)*)'|\[名前など\]|\[名前A\]|\[名前Bまたは値\]|\[数値\]|None")


def main(argv):
    out = argv[0]
    tr = {}
    descs = []
    for fn in sorted(os.listdir(os.path.join(out, 'chunks'))):
        name = fn[:-5]
        units = json.load(open(os.path.join(out, 'chunks', fn), encoding='utf-8'))['units']
        job = json.load(open(os.path.join(out, 'jobs', fn), encoding='utf-8'))
        tr.update(job.get('known', {}))
        try:
            ja = json.load(open(os.path.join(out, 'ja', fn), encoding='utf-8'))
        except FileNotFoundError:
            ja = {}
        for u in units:
            if u['id'] in ja:
                tr[u['en']] = ja[u['id']]
            for d in u.get('usage', []):
                if d not in descs:
                    descs.append(d)
    names = iter(['ブリッサ', 'ゴブリン', 'ブリッサ', 'ゴブリン'])
    for d in descs:
        en_parts, ja_parts = [], []
        k = 0
        for m in QUOTED.finditer(d):
            t = m.group(0)
            if m.group(1) is not None:
                s = m.group(1)
                en_parts.append(s)
                ja_parts.append(tr.get(s, s))
            elif t in ('[名前など]', '[名前A]'):
                en_parts.append('Brissa' if k == 0 else 'Goblin')
                ja_parts.append('ブリッサ' if k == 0 else 'ゴブリン')
                k += 1
            elif t == '[名前Bまたは値]':
                en_parts.append('Goblin')
                ja_parts.append('ゴブリン')
                k += 1
            elif t == '[数値]':
                en_parts.append('5')
                ja_parts.append('5')
            elif t == 'None':
                en_parts.append('.')
                ja_parts.append('.')
        en_s, ja_s = ''.join(en_parts), ''.join(ja_parts)
        if '%' in en_s and '%s' in en_s:
            continue
        print(f'{en_s}\n   → {ja_s}')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
