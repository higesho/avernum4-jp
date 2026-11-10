"""Split extracted units into translation chunks and group chunks into jobs.

usage:
    python -I make_chunks.py TRANS_DIR [--chunk-chars 6000] [--job-chars 30000]

Reads TRANS_DIR/units/*.json and writes
    TRANS_DIR/chunks/<file>__NN.json   {"file", "part", "units": [{"id", "kind", "en", "ctx"?, "code"?, "max"?}]}
    TRANS_DIR/jobs.json                [[chunk name, ...], ...]  (a job never splits a file)
A chunk boundary prefers a change of the "ctx" comment (e.g. a new speaker in a dialogue file).
"""
import json
import os
import sys

# Japanese runs roughly half the length of English; flag long units with an explicit limit.
LONG_EN = 380
LONG_MAX_JA = 250
# Name fields are filled from the glossary by build_scripts.py, not translated in chunks.
NAME_KINDS = {'cr_name', 'it_name', 'ab_name', 'ob_name', 'set_name', 'set_personality_name', 'shop'}


def main(argv):
    chunk_chars = 6000
    job_chars = 30000
    for i, a in enumerate(argv):
        if a == '--chunk-chars':
            chunk_chars = int(argv[i + 1])
        if a == '--job-chars':
            job_chars = int(argv[i + 1])
    args = [a for i, a in enumerate(argv) if not a.startswith('--') and (i == 0 or not argv[i - 1].startswith('--'))]
    if len(args) != 1:
        print(__doc__)
        return 2
    tdir = args[0]
    cdir = os.path.join(tdir, 'chunks')
    os.makedirs(cdir, exist_ok=True)
    # Units whose English is already translated (TRANS_DIR/known.json: the Escape From the
    # Pit translations, filled in by prefill_known.py) are not given to the translators.
    kp = os.path.join(tdir, 'known.json')
    known = json.load(open(kp, encoding='utf-8')) if os.path.exists(kp) else {}
    jobs, job, job_size = [], [], 0
    total = 0
    for fn in sorted(os.listdir(os.path.join(tdir, 'units'))):
        base = fn[:-5]
        units = json.load(open(os.path.join(tdir, 'units', fn), encoding='utf-8'))
        parts, cur, size, last_ctx = [], [], 0, None
        units = [u for u in units if u['kind'] not in NAME_KINDS and u['en'] not in known]
        for u in units:
            v = {'id': u['n'], 'kind': u['kind'], 'en': u['en']}
            for k in ('ctx', 'code'):
                if k in u:
                    v[k] = u[k]
            if len(u['en']) >= LONG_EN:
                v['max'] = LONG_MAX_JA
            n = len(u['en'])
            ctx_change = u.get('ctx') != last_ctx
            if cur and (size + n > chunk_chars * 1.3 or (size > chunk_chars * 0.6 and ctx_change)):
                parts.append(cur)
                cur, size = [], 0
            cur.append(v)
            size += n
            last_ctx = u.get('ctx')
        if cur:
            parts.append(cur)
        names = []
        for i, p in enumerate(parts, 1):
            name = f'{base}__{i:02d}'
            with open(os.path.join(cdir, name + '.json'), 'w', encoding='utf-8') as f:
                json.dump({'file': base, 'part': i, 'of': len(parts), 'units': p}, f, ensure_ascii=False, indent=0)
            names.append(name)
        fsize = sum(len(u['en']) for u in units)
        total += fsize
        if job and job_size + fsize > job_chars:
            jobs.append(job)
            job, job_size = [], 0
        job += names
        job_size += fsize
    if job:
        jobs.append(job)
    with open(os.path.join(tdir, 'jobs.json'), 'w', encoding='utf-8') as f:
        json.dump(jobs, f, indent=0)
    print(f'{sum(len(j) for j in jobs)} chunks in {len(jobs)} jobs, {total} chars')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
