"""Fix translations whose English contains a word: replace a Japanese term only in those units.

usage: python -I en_fix.py TRANS_DIR

RULES: (regex on the English, Japanese to replace, replacement). Used where one Japanese
word was given to two different English words (gazer / eyebeast -> 眼獣) and a plain
replacement over all files would be wrong.
"""
import json
import os
import re
import sys

sys.stdout.reconfigure(encoding='utf-8')
RULES = [
    (re.compile(r'\b[Gg]azers?\b'), '眼獣', 'ゲイザー'),
    (re.compile(r'\b[Nn]ephar\b'), 'ネファリム', 'ネファル'),
    (re.compile(r'Divine Lucre'), '神聖な金', '聖なる金銭'),
    (re.compile(r'\bClaw\b'), '爪', 'クロー'),          # the nephil shaman Claw (a name)
    (re.compile(r'Crusty Sailor'), '頑固なセイラー亭', '偏屈な船乗り亭'),
    (re.compile(r'Crusty Sailor'), '偏屈なセイラー', '偏屈な船乗り亭'),
    (re.compile(r'(?i)sailor'), 'セイラー', '船乗り'),       # a common noun, not a name
    (re.compile(r'\bFilth\b'), '汚穢', '汚濁'),
    (re.compile(r'\bFilth\b'), '汚物', '汚濁'),
    (re.compile(r'\b[Gg]hasts?\b'), 'ガースト', 'ガスト'),
    (re.compile(r'[Dd]oomguard'), 'ドゥームガード', '滅びの番人'),
    (re.compile(r'Eagle Rock'), 'イーグル岩', '鷲岩'),
    (re.compile(r'Deathrock'), 'デスロック一族', '死岩の一族'),
    (re.compile(r'Flame ?[Cc]lub'), 'フレイムクラブ一族', '炎棍の一族'),
    (re.compile(r'Soul ?[Dd]eath'), 'ソウルデス一族', '魂殺しの一族'),
    (re.compile(r'Access Port'), '出入り港', '出入り口'),
]


def main(tdir):
    n = 0
    for fn in sorted(os.listdir(os.path.join(tdir, 'ja'))):
        if fn.endswith('__known.json'):
            continue
        cp = os.path.join(tdir, 'chunks', fn)
        if not os.path.exists(cp):
            continue
        src = {str(u['id']): u['en'] for u in json.load(open(cp, encoding='utf-8'))['units']}   # script, exe and scen chunks
        p = os.path.join(tdir, 'ja', fn)
        j = json.load(open(p, encoding='utf-8'))
        changed = False
        for k, v in j.items():
            if not isinstance(v, str) or k not in src:
                continue
            nv = v
            for rx, a, b in RULES:
                if rx.search(src[k]) and a in nv:
                    nv = nv.replace(a, b)
            if nv != v:
                j[k] = nv
                changed = True
                n += 1
        if changed:
            json.dump(j, open(p, 'w', encoding='utf-8'), ensure_ascii=False, indent=0)
    print(f'{n} units fixed')


if __name__ == '__main__':
    main(sys.argv[1])
