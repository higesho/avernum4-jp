"""Collect the "_voices" notes from translated chunks into TRANS_DIR/voices.json.

usage:
    python -I merge_voices.py TRANS_DIR

The first note written for a speaker wins, so later jobs follow the voice
decided earlier. Keys look like "アンドリュー（Andrew）"; prep_job.py matches the
English part against the chunks it prepares.
"""
import json
import os
import re
import sys

sys.stdout.reconfigure(encoding='utf-8')


def english_key(name):
    m = re.search(r'[（(]([^）)]*)[）)]', name)
    return (m.group(1) if m else name).strip()


def main(argv):
    if len(argv) != 1:
        print(__doc__)
        return 2
    tdir = argv[0]
    vp = os.path.join(tdir, 'voices.json')
    voices = json.load(open(vp, encoding='utf-8')) if os.path.exists(vp) else {}
    known = {english_key(k) for k in voices}
    added = 0
    jdir = os.path.join(tdir, 'ja')
    for fn in sorted(os.listdir(jdir)):
        if not fn.endswith('.json'):
            continue
        try:
            d = json.load(open(os.path.join(jdir, fn), encoding='utf-8'))
        except json.JSONDecodeError:
            continue
        for name, note in (d.get('_voices') or {}).items():
            ek = english_key(name)
            if ek and ek not in known:
                voices[name] = note
                known.add(ek)
                added += 1
    with open(vp, 'w', encoding='utf-8') as f:
        json.dump(voices, f, ensure_ascii=False, indent=0)
    print(f'{len(voices)} voices ({added} new)')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
