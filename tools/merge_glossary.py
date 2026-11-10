"""Merge translated glossary parts into TRANS_DIR/glossary.json and check them.

usage:
    python -I merge_glossary.py TRANS_DIR

Reads TRANS_DIR/glossary_candidates.json (categories, limits) and every
TRANS_DIR/gloss_out/*.json ([{"en", "ja", "keep"}]); later files do not override
earlier ones, except TRANS_DIR/gloss_out/zz_fix.json which always wins (manual fixes).
Reports:
  * missing / extra terms
  * names over their byte limit
  * compound terms whose parts are translated differently
    (e.g. "Erika" = エリカ but "Archmage Erika" does not contain エリカ)
"""
import json
import os
import re
import sys

sys.stdout.reconfigure(encoding='utf-8')
NORMALIZE = str.maketrans({'～': '〜', '－': '−', '∥': '‖', '￠': '¢', '￡': '£', '￢': '¬'})


def main(argv):
    if len(argv) != 1:
        print(__doc__)
        return 2
    tdir = argv[0]
    cands = {t['en']: t for t in json.load(open(os.path.join(tdir, 'glossary_candidates.json'), encoding='utf-8'))}
    tr = {}
    odir = os.path.join(tdir, 'gloss_out')
    files = sorted(f for f in os.listdir(odir) if f.endswith('.json'))
    files = [f for f in files if f != 'zz_fix.json'] + (['zz_fix.json'] if 'zz_fix.json' in files else [])
    for fn in files:
        try:
            items = json.load(open(os.path.join(odir, fn), encoding='utf-8'))
        except json.JSONDecodeError as e:
            print(f'{fn}: JSONとして読めない: {e}')
            continue
        for it in items:
            en = it.get('en')
            if en is None:
                continue
            if fn == 'zz_fix.json' or en not in tr:
                tr[en] = {'ja': (it.get('ja') or '').strip(), 'keep': bool(it.get('keep', True))}
    problems = []
    out = []
    for en, c in cands.items():
        if en not in tr:
            problems.append(f'未訳: {en}')
            continue
        t = tr[en]
        e = {'en': en, 'ja': t['ja'], 'keep': t['keep'], 'cat': c['cat']}
        if c.get('max_bytes'):
            e['max_bytes'] = c['max_bytes']
            try:
                n = len(t['ja'].translate(NORMALIZE).encode('euc_jp'))
                if n > c['max_bytes']:
                    problems.append(f'長すぎる: {en} → {t["ja"]}（{n}/{c["max_bytes"]}バイト）')
            except UnicodeEncodeError:
                problems.append(f'EUC-JPにない文字: {en} → {t["ja"]}')
        if re.search(r'["\\_]', t['ja']):
            problems.append(f'使えない文字: {en} → {t["ja"]}')
        out.append(e)
    manual = set()
    if 'zz_fix.json' in files:
        manual = {it['en'] for it in json.load(open(os.path.join(odir, 'zz_fix.json'), encoding='utf-8'))}
    for en in tr:
        if en not in cands:
            if en in manual:  # terms added by hand (e.g. names the candidate scan split)
                out.append({'en': en, 'ja': tr[en]['ja'], 'keep': tr[en]['keep'], 'cat': 'manual'})
            else:
                problems.append(f'候補にない語（無視）: {en}')
    # compound consistency: a kept single-word name inside a longer kept term
    names = {e['en']: e['ja'] for e in out if e['keep'] and e['ja']}
    singles = {en: ja for en, ja in names.items() if ' ' not in en and en[:1].isupper()}
    for en, ja in names.items():
        if ' ' not in en:
            continue
        for w in re.findall(r"[A-Z][a-z]+", en):
            if w in singles and singles[w] not in ja and w not in ('The', 'Of'):
                problems.append(f'表記ゆれ: {en} → {ja}（{w} は「{singles[w]}」）')
    with open(os.path.join(tdir, 'glossary.json'), 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=0)
    for p in problems:
        print(p)
    print(f'{len(out)} terms ({sum(e["keep"] for e in out)} kept), {len(problems)} problems')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
