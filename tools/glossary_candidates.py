"""Collect glossary candidates (proper nouns and game terms) from extracted units.

usage:
    python -I glossary_candidates.py TRANS_DIR

Reads TRANS_DIR/units/*.json, writes TRANS_DIR/glossary_candidates.json:
    [{"en", "cat", "max_bytes" (EUC-JP, or null), "count", "example"}]
"""
import collections
import json
import os
import re
import sys

sys.stdout.reconfigure(encoding='utf-8')

# name fields: category and EUC-JP byte limit (see jpconv.py)
NAME_KINDS = {
    'cr_name': ('creature', 19), 'set_name': ('creature/person', 19),
    'set_personality_name': ('person', 19), 'it_name': ('item', 25),
    'ab_name': ('ability', 19), 'ob_name': ('object', 19), 'shop': ('shop', None),
}
# text libraries whose short entries are names of game terms
TERM_LIBS = {
    'textskills': 'skill', 'textspelldescs': 'spell', 'texttraits': 'trait',
    'textdisciplines': 'discipline', 'textstatus': 'status', 'textspecitems': 'special item',
    'textcheevos': 'achievement',
}
STOP = set('''I I'm I'll I've I'd You You're You've You'll Your The This That These Those It It's Its
He She They We My Our His Her Their What Why Who How When Where Which There Here Then If And But Or
So Yes No Not Some All Any Each Every One Two Three Four Five Ten Give Tell Show Pay Ask Leave
Goodbye Thanks Thank Well Oh Ah Hmm Now Please Perhaps Maybe Also Still Just Only Even Once After
Before While Unfortunately Fortunately Sadly Finally Suddenly Alas Hello Greetings Good Very Don't
Can't Won't Isn't Aren't Doesn't Didn't Let Let's Come Go Get Take Look Wait Stop Ok Okay As At By
For From In Into Of On To With Without About Over Under Up Down Out Off Mr Mrs Sir Lady Lord
'''.split())


def main(argv):
    if len(argv) != 1:
        print(__doc__)
        return 2
    tdir = argv[0]
    terms = {}

    def add(en, cat, limit, example):
        en = en.strip()
        if not en or len(en) > 60:
            return
        t = terms.setdefault(en, {'en': en, 'cat': set(), 'max_bytes': None, 'count': 0, 'example': example})
        t['cat'].add(cat)
        t['count'] += 1
        if limit and (t['max_bytes'] is None or limit < t['max_bytes']):
            t['max_bytes'] = limit

    prose = collections.Counter()
    example = {}
    for fn in sorted(os.listdir(os.path.join(tdir, 'units'))):
        base = fn[:-5]
        for u in json.load(open(os.path.join(tdir, 'units', fn), encoding='utf-8')):
            en, kind = u['en'], u['kind']
            if kind in NAME_KINDS:
                cat, limit = NAME_KINDS[kind]
                add(en, cat, limit, base)
                continue
            if base in TERM_LIBS and len(en) <= 40 and not re.search(r'[.!?]$', en):
                add(en, TERM_LIBS[base], None, base)
            if base == 'textquests' and len(en) <= 60 and u['n'] % 3 == 0:
                add(en, 'quest title', None, base)
            if kind == 'question' and u.get('ctx') == en:
                add(en, 'person', None, base)
            # Capitalised word sequences not at a sentence start.
            for m in re.finditer(r"(?<=[a-z,;] )([A-Z][a-z']+(?: (?:of |the |of the )?[A-Z][a-z']+)*)", en):
                w = re.sub(r"'s?$", '', m.group(1))
                if w.split()[0] in STOP:
                    continue
                prose[w] += 1
                if w not in example:
                    s = en[max(0, m.start() - 80):m.end() + 80]
                    example[w] = s
    for w, c in prose.items():
        if c >= 2 and w not in terms:
            add(w, 'term in text', None, example[w])
            terms[w]['count'] = c
        elif w in terms:
            terms[w]['count'] += c
    out = sorted(terms.values(), key=lambda t: (-t['count'], t['en']))
    for t in out:
        t['cat'] = '/'.join(sorted(t['cat']))
    with open(os.path.join(tdir, 'glossary_candidates.json'), 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=0)
    print(len(out), 'candidates')
    print(collections.Counter(t['cat'] for t in out).most_common(20))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
