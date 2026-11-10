"""Reuse Escape From the Pit translations of scenario strings with the same English.

usage:
    python -I scen_known.py SCEN_DIR EFTP_SCEN_DIR

EFTP_SCEN_DIR is the Escape From the Pit trans_scen folder (units.json and ja/*.json).
Writes SCEN_DIR/ja/known.json {id: 日本語} for units of SCEN_DIR/units.json whose kind
group (name/label, area, sign) and English match, and whose translation fits max_bytes.
"""
import json
import os
import sys

sys.stdout.reconfigure(encoding='utf-8')
NORMALIZE = str.maketrans({'～': '〜', '－': '−', '∥': '‖', '￠': '¢', '￡': '£', '￢': '¬'})


def main(argv):
    if len(argv) != 2:
        print(__doc__)
        return 2
    sdir, edir = argv
    etr = {}
    for fn in os.listdir(os.path.join(edir, 'ja')):
        if fn.endswith('.json'):
            etr.update(json.load(open(os.path.join(edir, 'ja', fn), encoding='utf-8')))
    eng = {}
    for u in json.load(open(os.path.join(edir, 'units.json'), encoding='utf-8')):
        t = etr.get(u['id'])
        if isinstance(t, str) and t.strip() and t != u['en']:
            eng.setdefault((u['kind'].split()[1], u['en']), t)
    out = {}
    for u in json.load(open(os.path.join(sdir, 'units.json'), encoding='utf-8')):
        t = eng.get((u['kind'].split()[1], u['en']))
        if t and len(t.translate(NORMALIZE).encode('euc_jp')) <= u['max_bytes']:
            out[u['id']] = t
    os.makedirs(os.path.join(sdir, 'ja'), exist_ok=True)
    json.dump(out, open(os.path.join(sdir, 'ja', 'known.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=0)
    print(f'{len(out)} strings reused')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
