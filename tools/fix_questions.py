"""Put 「」 around dialogue choices (kind "question") that are sentences (STYLE.md 1章).

usage: python -I fix_questions.py TRANS_DIR

A choice whose English ends with . ? ! (a spoken line) gets 「」 when the translation has none.
Topic names ("Andrew") and action choices in parentheses ("(Run away.)") are left alone.
Reused translations (TRANS_DIR/ja/*__known.json) are fixed too.
"""
import json
import os
import re
import sys

sys.stdout.reconfigure(encoding='utf-8')
SENTENCE = re.compile(r'[.?!]["\']?\s*$')


def main(tdir):
    cdir, jdir = os.path.join(tdir, 'chunks'), os.path.join(tdir, 'ja')
    kinds = {}
    for fn in os.listdir(cdir):
        c = json.load(open(os.path.join(cdir, fn), encoding='utf-8'))
        for u in c['units']:
            kinds[(c['file'], str(u['id']))] = (u['kind'], u['en'])
    udir = os.path.join(tdir, 'units')
    for fn in os.listdir(udir):          # units of reused (__known) translations
        for u in json.load(open(os.path.join(udir, fn), encoding='utf-8')):
            kinds.setdefault((fn[:-5], str(u['n'])), (u['kind'], u['en']))
    n = 0
    for fn in sorted(os.listdir(jdir)):
        if not fn.endswith('.json'):
            continue
        base = fn[:-5].rsplit('__', 1)[0]
        p = os.path.join(jdir, fn)
        d = json.load(open(p, encoding='utf-8'))
        changed = False
        for k, v in d.items():
            if k.startswith('_') or not isinstance(v, str):
                continue
            kind, en = kinds.get((base, k), (None, ''))
            if kind != 'question' or en.lstrip().startswith('(') or not SENTENCE.search(en):
                continue
            t = v.strip()
            if not t or t[0] in '「（『':
                continue
            d[k] = '「' + t + '」'
            changed = True
            n += 1
        if changed:
            json.dump(d, open(p, 'w', encoding='utf-8'), ensure_ascii=False, indent=0)
    print(f'{n} choices put in 「」')


if __name__ == '__main__':
    main(sys.argv[1])
