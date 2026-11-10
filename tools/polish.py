"""Final consistency pass over TRANSLATION outputs (TRANS_DIR/ja/*.json).

usage:
    python -I polish.py TRANS_DIR [--dry-run]

Fixes rules that were tightened while the translation was running:
  1. a sentence-like 「…」 must end with punctuation before 」  (「〜だ」 -> 「〜だ。」)
  2. player lines (question) must not use ぞ / ぜ / だな endings
  3. action notes in player lines are plain form: （彼女に渡します。） -> （彼女に渡す。）
  4. word choices fixed later: voles = ネズミ, singular nephar = ネファル
Prints every change; --dry-run only reports.
"""
import json
import os
import re
import sys

sys.stdout.reconfigure(encoding='utf-8')

JP = r'[ぁ-ヿ一-鿿ー]'
MASU = [('渡します', '渡す'), ('見せます', '見せる'), ('払います', '払う'), ('与えます', '与える'),
        ('置きます', '置く'), ('去ります', '去る'), ('食べます', '食べる'), ('言います', '言う'),
        ('教えます', '教える'), ('飲みます', '飲む'), ('使います', '使う'), ('待ちます', '待つ'),
        ('売ります', '売る'), ('買います', '買う'), ('読みます', '読む'), ('見ます', '見る'),
        ('取ります', '取る'), ('行きます', '行く'), ('帰ります', '帰る'), ('立ち去ります', '立ち去る'),
        ('出ます', '出る'), ('入ります', '入る'), ('離れます', '離れる')]
# godan verbs ending in す: 話します -> 話す (not 話する)
SU_STEMS = '話探返出貸示押指差落殺隠直戻倒放外離渡回流消残'
MASU += [(c + 'します', c + 'す') for c in SU_STEMS] + [('します', 'する')]


def close_quotes(s):
    def fix(m):
        body = m.group(1)
        after = s[m.end():m.end() + 1]
        if after in ('と', 'っ'):  # 「〜」と言う: no period before a quoting particle
            return m.group(0)
        sentence_like = re.search(r'[。！？、]', body) or len(body) >= 15
        if sentence_like and re.search(JP + r'$', body):
            return '「' + body + '。」'
        return m.group(0)
    return re.sub(r'「([^「」『』]+)」', fix, s)


def main(argv):
    dry = '--dry-run' in argv
    args = [a for a in argv if not a.startswith('--')]
    if len(args) != 1:
        print(__doc__)
        return 2
    tdir = args[0]
    total = 0
    for fn in sorted(os.listdir(os.path.join(tdir, 'ja'))):
        name = fn[:-5]
        p = os.path.join(tdir, 'ja', fn)
        try:
            out = json.load(open(p, encoding='utf-8'))
            src = {str(u['id']): u for u in
                   json.load(open(os.path.join(tdir, 'chunks', name + '.json'), encoding='utf-8'))['units']}
        except (json.JSONDecodeError, FileNotFoundError):
            continue
        changed = False
        for k, u in src.items():
            ja = out.get(k)
            if not isinstance(ja, str):
                continue
            new = close_quotes(ja)
            if u['kind'] == 'question':
                new = re.sub(r'(ぞ|ぜ)([。！？]?)」', lambda m: (m.group(2) or '。') + '」', new)
                new = re.sub(r'だな([。！？]?)」', lambda m: 'だ' + (m.group(1) or '。') + '」', new)

                def plain(m):
                    t = m.group(0)
                    for a, b in MASU:
                        t = t.replace(a, b)
                    return t
                new = re.sub(r'（[^（）]*ます。）', plain, new)
            new = new.replace('野ネズミ', 'ネズミ')
            if re.search(r'\bnephar\b', u['en'], re.I) and not re.search(r'nepharim', u['en'], re.I):
                new = new.replace('ネファリム', 'ネファル')
            if new != ja:
                print(f'[{name} {k}] {ja[:70]}\n      -> {new[:70]}')
                out[k] = new
                changed = True
                total += 1
        if changed and not dry:
            with open(p, 'w', encoding='utf-8') as f:
                json.dump(out, f, ensure_ascii=False, indent=0)
    print(f'{total} units changed' + (' (dry run)' if dry else ''))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
