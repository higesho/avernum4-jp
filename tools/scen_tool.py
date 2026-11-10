"""Translate the strings of AScenData.dat (see scen_extract.py for the layout).

usage:
    python -I scen_tool.py chunk SCEN_DIR TRANS_DIR     make SCEN_DIR/chunks/*.json and jobs/*.json
    python -I scen_tool.py check SCEN_DIR [CHUNK ...]   check SCEN_DIR/ja/*.json
    python -I scen_tool.py build SCEN_DIR ORIGINAL_DAT OUTPUT_DAT

check: every id present, EUC-JP length <= max_bytes, '|' count kept, no '_' left,
       glossary terms used (warning), English left (warning)
build: copies ORIGINAL_DAT and writes each translation into all of its fields
       (EUC-JP, zero-filled to the field size). Untranslated fields stay English.
"""
import json
import os
import re
import shutil
import sys

sys.stdout.reconfigure(encoding='utf-8')
NORMALIZE = str.maketrans({'～': '〜', '－': '−', '∥': '‖', '￠': '¢', '￡': '£', '￢': '¬'})
GROUPS = [('scen00', ('outdoor name', 'town name', 'outdoor label', 'town label')),
          ('scen01', ('outdoor area', 'town area')),
          ('scen02', ('outdoor sign', 'town sign'))]
PER_CHUNK = 220


def euc(s):
    return s.translate(NORMALIZE).encode('euc_jp')


def chunk(sdir, tdir):
    units = json.load(open(os.path.join(sdir, 'units.json'), encoding='utf-8'))
    gloss = []
    for t in json.load(open(os.path.join(tdir, 'glossary.json'), encoding='utf-8')):
        if t.get('keep') and t.get('ja'):
            gloss.append((re.compile(r'\b' + re.escape(t['en'].rstrip('.')) + r'\b'), t['en'].rstrip('.'), t['ja'].rstrip('。')))
    os.makedirs(os.path.join(sdir, 'chunks'), exist_ok=True)
    os.makedirs(os.path.join(sdir, 'jobs'), exist_ok=True)
    os.makedirs(os.path.join(sdir, 'ja'), exist_ok=True)
    # ja/known.json (Escape From the Pit translations of the same English, from
    # scen_known.py) is not given to the translators again.
    kp = os.path.join(sdir, 'ja', 'known.json')
    known = json.load(open(kp, encoding='utf-8')) if os.path.exists(kp) else {}
    pieces = []
    for name, kinds in GROUPS:
        todo = [u for u in units if u['kind'] in kinds and u['id'] not in known]
        for i in range(0, len(todo), PER_CHUNK):
            pieces.append((f'{name}_{i // PER_CHUNK}', todo[i:i + PER_CHUNK]))
    for name, todo in pieces:
        part = [{'id': u['id'], 'kind': u['kind'], 'en': u['en'], 'max_bytes': u['max_bytes']}
                for u in todo]
        text = '\n'.join(u['en'] for u in part)
        g = {en: ja for rx, en, ja in gloss if rx.search(text)}
        json.dump({'units': part}, open(os.path.join(sdir, 'chunks', name + '.json'), 'w', encoding='utf-8'),
                  ensure_ascii=False, indent=0)
        json.dump({'chunks': [name], 'glossary': g}, open(os.path.join(sdir, 'jobs', name + '.json'), 'w',
                  encoding='utf-8'), ensure_ascii=False, indent=0)
        print(f'{name}: {len(part)} units, {sum(len(u["en"]) for u in part)} chars, {len(g)} glossary terms')


def check(sdir, names):
    names = names or sorted(f[:-5] for f in os.listdir(os.path.join(sdir, 'chunks')) if f.endswith('.json'))
    ne = nw = 0
    for name in names:
        src = json.load(open(os.path.join(sdir, 'chunks', name + '.json'), encoding='utf-8'))['units']
        job = json.load(open(os.path.join(sdir, 'jobs', name + '.json'), encoding='utf-8'))
        gloss = sorted(((re.compile(r'\b' + re.escape(e) + r'\b'), e, j) for e, j in job['glossary'].items()),
                       key=lambda x: -len(x[1]))
        try:
            ja = json.load(open(os.path.join(sdir, 'ja', name + '.json'), encoding='utf-8'))
        except (FileNotFoundError, json.JSONDecodeError) as e:
            print(f'== {name}: 出力を読めない: {e}')
            ne += 1
            continue
        errs, warns = [], []
        for u in src:
            k, en, t = u['id'], u['en'], ja.get(u['id'])
            if not isinstance(t, str) or not t.strip():
                errs.append(f'{k}: 訳がない')
                continue
            try:
                n = len(euc(t))
                if n > u['max_bytes']:
                    errs.append(f'{k}: 長すぎる（{n}バイト、上限{u["max_bytes"]}バイト＝全角{u["max_bytes"] // 2}文字）「{t}」')
            except UnicodeEncodeError as e:
                errs.append(f'{k}: EUC-JPにない文字 {t[e.start:e.end]!r}')
            if en.count('|') != t.count('|'):
                errs.append(f'{k}: | の数が原文と違う')
            if '_' in t:
                errs.append(f'{k}: _ が残っている（「」にする）')
            if re.search(r'[A-Za-z]{3}', en) and not re.search(r'[぀-ヿ一-鿿]', t):
                warns.append(f'{k}: 英語のまま')
            used = en
            for rx, ten, tja in gloss:
                if rx.search(used):
                    used = rx.sub(' ', used)
                    if tja not in t:
                        warns.append(f'{k}: 対訳表の「{ten}」→「{tja}」が使われていない')
        if errs or warns:
            print(f'== {name}: エラー{len(errs)} 警告{len(warns)}')
            for x in errs[:30]:
                print('  E', x)
            for x in warns[:15]:
                print('  W', x)
        ne += len(errs)
        nw += len(warns)
    print(f'{len(names)} chunks, errors {ne}, warnings {nw}')
    return 1 if ne else 0


def build(sdir, orig, out):
    units = {u['id']: u for u in json.load(open(os.path.join(sdir, 'units.json'), encoding='utf-8'))}
    tr = {}
    for fn in os.listdir(os.path.join(sdir, 'ja')):
        if fn.endswith('.json'):
            tr.update(json.load(open(os.path.join(sdir, 'ja', fn), encoding='utf-8')))
    data = bytearray(open(orig, 'rb').read())
    n = skipped = 0
    for k, t in tr.items():
        u = units.get(k)
        if not u or not isinstance(t, str) or t == u['en']:
            continue
        try:
            b = euc(t)
        except UnicodeEncodeError:
            skipped += 1
            continue
        if len(b) > u['max_bytes']:
            print(f'skip (too long): {k} {t}')
            skipped += 1
            continue
        for off, fsize in u['fields']:
            data[off:off + fsize] = b + b'\0' * (fsize - len(b))
            n += 1
    if os.path.abspath(out) == os.path.abspath(orig):
        raise SystemExit('refusing to overwrite the original')
    open(out, 'wb').write(bytes(data))
    print(f'{n} fields written, {skipped} skipped -> {out}')
    return 0


def main(argv):
    if not argv:
        print(__doc__)
        return 2
    cmd, args = argv[0], argv[1:]
    if cmd == 'chunk':
        return chunk(*args) or 0
    if cmd == 'check':
        return check(args[0], args[1:])
    if cmd == 'build':
        return build(*args)
    print(__doc__)
    return 2


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
