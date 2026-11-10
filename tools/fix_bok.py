"""One-off: add glossary fixes so every "-Bok" name ends in 「・ボック」 (STYLE.md 8).

usage: python -I fix_bok.py TRANS_DIR
"""
import json
import os
import sys

sys.stdout.reconfigure(encoding='utf-8')
tdir = sys.argv[1]
g = json.load(open(os.path.join(tdir, 'glossary.json'), encoding='utf-8'))
zp = os.path.join(tdir, 'gloss_out', 'zz_fix.json')
z = json.load(open(zp, encoding='utf-8'))
have = {x['en'] for x in z}
for t in g:
    if t['en'].endswith('-Bok') and 'ボック' not in t['ja'] and t['en'] not in have:
        ja = t['ja'].replace('・ボク', '・ボック')
        if not ja.endswith('ボック'):
            ja = ja.rstrip('ボク') + 'ボック' if ja.endswith('ボク') else ja
        if t.get('max_bytes') and len(ja.encode('euc_jp')) > t['max_bytes']:
            ja = ja.replace('・', '')
        z.append({'en': t['en'], 'ja': ja, 'keep': t['keep']})
        print(t['en'], '->', ja)
json.dump(z, open(zp, 'w', encoding='utf-8'), ensure_ascii=False, indent=0)
