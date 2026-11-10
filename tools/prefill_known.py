"""Reuse the Escape From the Pit translations for identical English strings.

usage:
    python -I prefill_known.py TRANS_DIR KNOWN_JSON

Reads TRANS_DIR/units/*.json and writes TRANS_DIR/ja/<file>__known.json with every
unit whose English text is exactly in KNOWN_JSON ({"English": "日本語"}).
Name fields are left to the glossary. build_scripts.py reads these like any other
ja/ file; a chunk translation for the same literal is applied as well, and the last
file read wins, so translated chunks (<file>__NN.json) are sorted after "__known".
"""
import json
import os
import sys

sys.stdout.reconfigure(encoding='utf-8')
NAME_KINDS = {'cr_name', 'it_name', 'ab_name', 'ob_name', 'set_name', 'set_personality_name', 'shop'}


def main(argv):
    if len(argv) != 2:
        print(__doc__)
        return 2
    tdir, kp = argv
    known = json.load(open(kp, encoding='utf-8'))
    jdir = os.path.join(tdir, 'ja')
    os.makedirs(jdir, exist_ok=True)
    total = hits = 0
    for fn in sorted(os.listdir(os.path.join(tdir, 'units'))):
        out = {}
        for u in json.load(open(os.path.join(tdir, 'units', fn), encoding='utf-8')):
            if u['kind'] in NAME_KINDS:
                continue
            total += 1
            if u['en'] in known:
                out[str(u['n'])] = known[u['en']]
        p = os.path.join(jdir, fn[:-5] + '__known.json')
        if out:
            json.dump(out, open(p, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
            hits += len(out)
        elif os.path.exists(p):
            os.remove(p)
    print(f'{hits} of {total} body units reused')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
