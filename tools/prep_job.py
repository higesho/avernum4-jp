"""Prepare one translation job: the glossary subset and voice notes its chunks need.

usage:
    python -I prep_job.py TRANS_DIR JOB_NAME CHUNK [CHUNK ...]

Writes TRANS_DIR/jobs/JOB_NAME.json:
    {"chunks": [...], "glossary": {"English": "日本語", ...}, "voices": {"人物": "口調メモ", ...}}
glossary: kept terms (TRANS_DIR/glossary.json) that occur in the chunks' English text.
voices:   notes from TRANS_DIR/voices.json for speakers named in the chunks.
"""
import json
import os
import re
import sys

sys.stdout.reconfigure(encoding='utf-8')


def main(argv):
    if len(argv) < 3:
        print(__doc__)
        return 2
    tdir, job, chunks = argv[0], argv[1], argv[2:]
    text = []
    for c in chunks:
        src = json.load(open(os.path.join(tdir, 'chunks', c + '.json'), encoding='utf-8'))
        for u in src['units']:
            text.append(u['en'])
            text.append(u.get('ctx', ''))
    text = '\n'.join(text)
    gloss = {}
    gp = os.path.join(tdir, 'glossary.json')
    for t in json.load(open(gp, encoding='utf-8')) if os.path.exists(gp) else []:
        en = t['en'].rstrip('.')  # quest titles end with "."
        if t.get('keep') and t.get('ja') and re.search(r'\b' + re.escape(en) + r'\b', text):
            gloss[en] = t['ja'].rstrip('。.')
    voices = {}
    vp = os.path.join(tdir, 'voices.json')
    for name, note in (json.load(open(vp, encoding='utf-8')).items() if os.path.exists(vp) else []):
        # Keys look like 「グラハム隊長（Captain Graham）」: match the English part in brackets.
        m = re.search(r'[（(]([^）)]*[A-Za-z][^）)]*)[）)]', name)
        key = (m.group(1) if m else name.split('（')[0].split('(')[0]).strip()
        if key and re.search(r'\b' + re.escape(key) + r'\b', text):
            voices[name] = note
    # Identical English already translated elsewhere (unify_dupes.py writes known.json).
    known = {}
    kp = os.path.join(tdir, 'known.json')
    if os.path.exists(kp):
        allk = json.load(open(kp, encoding='utf-8'))
        for c in chunks:
            src = json.load(open(os.path.join(tdir, 'chunks', c + '.json'), encoding='utf-8'))
            for u in src['units']:
                if u['en'] in allk:
                    known[u['en']] = allk[u['en']]
    os.makedirs(os.path.join(tdir, 'jobs'), exist_ok=True)
    with open(os.path.join(tdir, 'jobs', job + '.json'), 'w', encoding='utf-8') as f:
        json.dump({'chunks': chunks, 'glossary': gloss, 'voices': voices, 'known': known}, f,
                  ensure_ascii=False, indent=0)
    print(f'{job}: {len(chunks)} chunks, {len(gloss)} glossary terms, {len(voices)} voices, {len(known)} known')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
