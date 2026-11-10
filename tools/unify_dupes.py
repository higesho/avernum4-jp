"""Make identical English units share one translation.

usage:
    python -I unify_dupes.py TRANS_DIR [--dry-run]

Many scripts are copies (door.txt / t1door.txt / t76door.txt ...), and some lines
recur across towns. For every English text (12+ chars) translated differently in
TRANS_DIR/ja/*.json, the translation found in the most chunks wins (ties: the
alphabetically first chunk) and is written to the others.
Also writes TRANS_DIR/known.json {English: 日本語} for prep_job.py.
"""
import collections
import json
import os
import sys

sys.stdout.reconfigure(encoding='utf-8')


def main(argv):
    dry = '--dry-run' in argv
    args = [a for a in argv if not a.startswith('--')]
    if len(args) != 1:
        print(__doc__)
        return 2
    tdir = args[0]
    occ = collections.defaultdict(list)  # en -> [(chunk, id, ja)]
    outs = {}
    for fn in sorted(os.listdir(os.path.join(tdir, 'ja'))):
        name = fn[:-5]
        try:
            out = json.load(open(os.path.join(tdir, 'ja', fn), encoding='utf-8'))
            src = json.load(open(os.path.join(tdir, 'chunks', name + '.json'), encoding='utf-8'))
        except (json.JSONDecodeError, FileNotFoundError):
            continue
        outs[name] = out
        for u in src['units']:
            ja = out.get(str(u['id']))
            if isinstance(ja, str) and ja.strip():
                occ[u['en']].append((name, str(u['id']), ja))
    known, changed = {}, set()
    n = 0
    for en, lst in occ.items():
        votes = collections.Counter(ja for _, _, ja in lst)
        best = max(votes, key=lambda j: (votes[j], -min(i for i, (c, _, x) in enumerate(lst) if x == j)))
        if len(en) >= 12:
            known[en] = best
        if len(votes) > 1 and len(en) >= 12:
            for c, k, ja in lst:
                if ja != best:
                    outs[c][k] = best
                    changed.add(c)
                    n += 1
            print(f'「{en[:50]}」 → {best[:40]}')
    if not dry:
        for c in changed:
            with open(os.path.join(tdir, 'ja', c + '.json'), 'w', encoding='utf-8') as f:
                json.dump(outs[c], f, ensure_ascii=False, indent=0)
        with open(os.path.join(tdir, 'known.json'), 'w', encoding='utf-8') as f:
            json.dump(known, f, ensure_ascii=False, indent=0)
    print(f'{n} units in {len(changed)} chunks unified; {len(known)} known translations')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
