"""Put translations back into the original scripts and write EUC-JP files for the game.

usage:
    python -I build_scripts.py ORIG_SCRIPTS_DIR TRANS_DIR GAME_SCRIPTS_DIR [--dry-run]
        [--no-names] [--no-body] [--only-names=FILE_PREFIX ...]   (for bisecting problems)

Translations come from
  * TRANS_DIR/ja/<file>__NN.json   {"<literal index>": "訳", ...}   (body text)
  * TRANS_DIR/glossary.json        name fields (cr_name, it_name, ...) are looked up by English
Literals without a translation keep their original bytes. Every original file is written,
so files that are not translated yet are restored to the original.
"""
import json
import os
import re
import sys

sys.stdout.reconfigure(encoding='utf-8')
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import extract  # noqa: E402
import jpconv  # noqa: E402

NAME_KINDS = {'cr_name', 'it_name', 'ab_name', 'ob_name', 'set_name', 'set_personality_name', 'shop'}


def main(argv):
    dry = '--dry-run' in argv
    no_names = '--no-names' in argv
    no_body = '--no-body' in argv
    only = [a.split('=', 1)[1] for a in argv if a.startswith('--only-names=')]
    args = [a for a in argv if not a.startswith('--')]
    if len(args) != 3:
        print(__doc__)
        return 2
    orig, tdir, game = args
    body = {}
    jdir = os.path.join(tdir, 'ja')
    # <file>__known.json (reused Escape From the Pit translations) first, so that
    # translated chunks override them.
    for fn in sorted(os.listdir(jdir) if os.path.isdir(jdir) else [], key=lambda f: (not f.endswith('__known.json'), f)):
        if not fn.endswith('.json'):
            continue
        base = fn[:-5].rsplit('__', 1)[0]
        for k, v in json.load(open(os.path.join(jdir, fn), encoding='utf-8')).items():
            if not k.startswith('_') and isinstance(v, str) and v.strip():
                body.setdefault(base, {})[int(k)] = v
    names = {}
    gp = os.path.join(tdir, 'glossary.json')
    if os.path.exists(gp):
        for t in json.load(open(gp, encoding='utf-8')):
            if t.get('ja'):
                names[t['en']] = t['ja']

    problems = []
    n_files = n_lit = n_body = n_name = 0
    for fn in sorted(os.listdir(orig)):
        if not fn.lower().endswith('.txt'):
            continue
        base = fn[:-4]
        data = open(os.path.join(orig, fn), 'rb').read()
        tr = body.get(base, {})
        out, pos = [], 0
        for idx, (s, e, b, kind, _c, _st) in enumerate(extract.literals(data)):
            n_lit += 1
            en = extract.decode(b)
            ja = None if no_body else tr.get(idx)
            if ja is not None:
                n_body += 1
            elif (kind in NAME_KINDS and en.strip() in names and not no_names
                  and (not only or any(fn.startswith(o) for o in only))):
                lead, trail = re.match(r'^\s*', en).group(0), re.search(r'\s*$', en).group(0)
                ja = lead + names[en.strip()] + trail
                n_name += 1
            if ja is None:
                continue
            try:
                enc = ja.translate(jpconv.NORMALIZE).encode('euc_jp')
            except UnicodeEncodeError as ex:
                problems.append(f'{fn}: literal {idx}: EUC-JPにない文字 {ja[ex.start:ex.end]!r}（原文のまま）')
                continue
            if b'"' in enc or b'\r' in enc or b'\n' in enc:
                problems.append(f'{fn}: literal {idx}: " や改行を含む（原文のまま）')
                continue
            out.append(data[pos:s + 1])
            out.append(enc)
            pos = e - 1
        out.append(data[pos:])
        result = b''.join(out)
        found = []
        jpconv.check(result, fn, found)
        # tr_name / fl_name / tmp_name are internal and already over the limit in the original.
        problems += [p for p in found if not re.search(r'(tr|fl|tmp)_name', p)]
        if not dry:
            with open(os.path.join(game, fn), 'wb') as f:
                f.write(result)
        n_files += 1
    for p in problems:
        print(p)
    print(f'{n_files} files, {n_lit} literals: body {n_body}, names {n_name} translated; {len(problems)} problems')
    return 1 if problems else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
