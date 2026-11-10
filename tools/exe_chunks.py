"""Split the exe string table into translation jobs for the translators.

usage:
    python -I exe_chunks.py EXE_STRINGS_TSV FRAGCTX_JSON TRANS_DIR OUT_DIR [--per-job 140]

Reads exe_strings.tsv (va, sink, refs, english, japanese) and fragctx.json
({va: ["how the string is assembled", ...]}, from the disassembly), and writes
    OUT_DIR/chunks/exeNN.json  {"units": [{"id": va, "kind": sink, "en", "usage"?, "specs"?, "max_bytes"?}]}
    OUT_DIR/jobs/exeNN.json    {"chunks": [...], "glossary": {...}, "known": {...}}
Rows marked "internal" and rows that already have a translation are skipped
(already translated rows are given to every job as "known").
"""
import json
import os
import re
import sys

sys.stdout.reconfigure(encoding='utf-8')
SPEC = re.compile(r'%(?:\d\$)?[-+ #0]*\d*(?:\.\d+)?[hlL]?[diouxXeEfgGcsp]')


def main(argv):
    per_job = 140
    if '--per-job' in argv:
        per_job = int(argv[argv.index('--per-job') + 1])
    args = [a for i, a in enumerate(argv) if not a.startswith('--') and (i == 0 or argv[i - 1] != '--per-job')]
    if len(args) != 4:
        print(__doc__)
        return 2
    tsv, fragctx, tdir, out = args
    rows = [l.split('\t') for l in open(tsv, encoding='utf-8').read().split('\n')[1:] if l.strip()]
    ctx = json.load(open(fragctx, encoding='utf-8'))
    # where does each English string appear inside other strings' assembly descriptions?
    by_en = {}
    for va, descs in ctx.items():
        for d in descs:
            for m in re.finditer(r"'((?:[^'\\]|\\.)*)'", d):
                by_en.setdefault(m.group(1), set()).add(d)
    gloss = []
    for t in json.load(open(os.path.join(tdir, 'glossary.json'), encoding='utf-8')):
        if t.get('keep') and t.get('ja'):
            gloss.append((re.compile(r'\b' + re.escape(t['en'].rstrip('.')) + r'\b'), t['en'].rstrip('.'), t['ja'].rstrip('。')))
    known, units = {}, []
    for va, sink, refs, en, ja in rows:
        if 'internal' in sink:
            continue
        if ja.strip():
            known[en] = ja
            continue
        u = {'id': va, 'kind': sink or 'other', 'en': en}
        usage = list(ctx.get(va) or [])
        for d in sorted(by_en.get(en, ())):
            if d not in usage:
                usage.append(d)
        if usage:
            u['usage'] = usage[:4]
        sp = SPEC.findall(en)
        if sp:
            u['specs'] = sp
        if 'float' in sink:
            u['max_bytes'] = 39
        units.append(u)
    # Keep fragments that are assembled into the same message in the same job:
    # union-find over strings that appear together in one usage description.
    parent = {}

    def find(x):
        parent.setdefault(x, x)
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    en_to_ids = {}
    for u in units:
        en_to_ids.setdefault(u['en'], []).append(u['id'])
        find(u['id'])
    for u in units:
        for d in u.get('usage', []):
            for m in re.finditer(r"'((?:[^'\\]|\\.)*)'", d):
                for other in en_to_ids.get(m.group(1), []):
                    parent[find(other)] = find(u['id'])
    groups = {}
    for u in units:
        groups.setdefault(find(u['id']), []).append(u)
    ordered, seen = [], set()
    for u in units:
        r = find(u['id'])
        if r not in seen:
            seen.add(r)
            ordered += groups[r]
    batches, cur = [], []
    i = 0
    while i < len(ordered):
        g = groups[find(ordered[i]['id'])]
        if cur and len(cur) + len(g) > per_job:
            batches.append(cur)
            cur = []
        cur += g
        i += len(g)
    if cur:
        batches.append(cur)
    os.makedirs(os.path.join(out, 'chunks'), exist_ok=True)
    os.makedirs(os.path.join(out, 'jobs'), exist_ok=True)
    os.makedirs(os.path.join(out, 'ja'), exist_ok=True)
    n = 0
    for part in batches:
        name = f'exe{n:02d}'
        text = '\n'.join(u['en'] for u in part)
        g = {}
        for rx, en, ja in gloss:
            if rx.search(text):
                g[en] = ja
        with open(os.path.join(out, 'chunks', name + '.json'), 'w', encoding='utf-8') as f:
            json.dump({'units': part}, f, ensure_ascii=False, indent=0)
        with open(os.path.join(out, 'jobs', name + '.json'), 'w', encoding='utf-8') as f:
            json.dump({'chunks': [name], 'glossary': g, 'known': known}, f, ensure_ascii=False, indent=0)
        print(f'{name}: {len(part)} units, {len(g)} glossary terms')
        n += 1
    print(f'{len(units)} units to translate, {len(known)} already translated')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
