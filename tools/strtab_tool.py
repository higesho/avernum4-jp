"""The exe's string table (RT_STRING, loaded with LoadStringW) of Avernum 4.

usage:
    python -I strtab_tool.py extract EXE OUT_DIR            OUT_DIR/units.json  [{"id", "en", "group"}]
    python -I strtab_tool.py chunk OUT_DIR [KNOWN_JSON]      OUT_DIR/chunks/strNN.json, OUT_DIR/jobs.json,
                                                            OUT_DIR/ja/known.json (exact matches in KNOWN_JSON)
    python -I strtab_tool.py check OUT_DIR [CHUNK ...]      check OUT_DIR/ja/*.json against the chunks
    python -I strtab_tool.py build OUT_DIR OUT_TSV          write the table the DLL reads (id, english, japanese)

The game copies a loaded string into a 256-byte buffer after converting it to the game encoding
(EUC-JP), so a translation must stay within 255 bytes (127 full-width characters).
"|" is a line break; keep the same number of them.
"""
import json
import os
import re
import sys

sys.stdout.reconfigure(encoding='utf-8')
MAX_BYTES = 255
NORMALIZE = str.maketrans({'～': '〜', '－': '−', '∥': '‖'})

# id ranges -> what the strings are (shown to translators)
GROUPS = [
    (900, 999, 'skill name'), (1000, 1099, 'skill description'), (1100, 1199, 'skill name (abbrev.)'),
    (1200, 1499, 'message / menu'), (1500, 1599, 'quest title'), (1600, 1799, 'quest description'),
    (1800, 2699, 'help'), (2700, 2999, 'keyboard help'), (3000, 3299, 'trait'), (3300, 3599, 'lore'),
    (3600, 4099, 'spell'), (4100, 4799, 'spell help'), (4800, 4999, 'quest title'), (5000, 9999, 'quest text'),
]


def group_of(i):
    for lo, hi, g in GROUPS:
        if lo <= i <= hi:
            return g
    return 'other'


def extract(exe, out):
    import pefile
    pe = pefile.PE(exe)
    st = [e for e in pe.DIRECTORY_ENTRY_RESOURCE.entries if e.id == 6][0]
    units = []
    for blk in st.directory.entries:
        for lang in blk.directory.entries:
            data = pe.get_data(lang.data.struct.OffsetToData, lang.data.struct.Size)
            i = 0
            for k in range(16):
                ln = int.from_bytes(data[i:i + 2], 'little')
                s = data[i + 2:i + 2 + ln * 2].decode('utf-16-le')
                i += 2 + ln * 2
                if re.search('[A-Za-z]', s):
                    sid = (blk.id - 1) * 16 + k
                    units.append({'id': sid, 'en': s, 'group': group_of(sid)})
    units.sort(key=lambda u: u['id'])
    os.makedirs(out, exist_ok=True)
    json.dump(units, open(os.path.join(out, 'units.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=0)
    print(len(units), 'strings', sum(len(u['en']) for u in units), 'chars')


def chunk(out, known_path=None, chunk_chars=6000):
    units = json.load(open(os.path.join(out, 'units.json'), encoding='utf-8'))
    known = json.load(open(known_path, encoding='utf-8')) if known_path else {}
    os.makedirs(os.path.join(out, 'chunks'), exist_ok=True)
    os.makedirs(os.path.join(out, 'ja'), exist_ok=True)
    reuse = {str(u['id']): known[u['en']] for u in units if u['en'] in known
             and len(known[u['en']].translate(NORMALIZE).encode('euc_jp', 'replace')) <= MAX_BYTES}
    json.dump(reuse, open(os.path.join(out, 'ja', 'known.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=0)
    todo = [u for u in units if str(u['id']) not in reuse]
    chunks, cur, size = [], [], 0
    for u in todo:
        if cur and (size + len(u['en']) > chunk_chars or u['group'] != cur[-1]['kind'] and size > chunk_chars // 2):
            chunks.append(cur)
            cur, size = [], 0
        cur.append({'id': u['id'], 'kind': u['group'], 'en': u['en'], 'max_bytes': MAX_BYTES})
        size += len(u['en'])
    if cur:
        chunks.append(cur)
    names = []
    for n, c in enumerate(chunks):
        name = f'str{n:02d}'
        json.dump({'file': 'strtab', 'part': n, 'units': c}, open(os.path.join(out, 'chunks', name + '.json'), 'w',
                  encoding='utf-8'), ensure_ascii=False, indent=0)
        names.append(name)
    json.dump(names, open(os.path.join(out, 'jobs.json'), 'w'), indent=0)
    print(f'{len(reuse)} reused, {len(todo)} to translate in {len(chunks)} chunks ({sum(len(u["en"]) for u in todo)} chars)')


def check(out, names):
    cdir = os.path.join(out, 'chunks')
    if not names:
        names = sorted(f[:-5] for f in os.listdir(cdir) if f.endswith('.json'))
    errs = warns = 0
    for name in names:
        c = json.load(open(os.path.join(cdir, name + '.json'), encoding='utf-8'))
        jp = os.path.join(out, 'ja', name + '.json')
        if not os.path.exists(jp):
            print(f'== {name}: 訳のファイルがありません')
            errs += 1
            continue
        ja = json.load(open(jp, encoding='utf-8'))
        e = w = 0
        msgs = []
        for u in c['units']:
            t = ja.get(str(u['id']))
            if not isinstance(t, str) or not t.strip():
                msgs.append(f'  E {u["id"]}: 訳がありません')
                e += 1
                continue
            t = t.translate(NORMALIZE)
            try:
                b = len(t.encode('euc_jp'))
            except UnicodeEncodeError as ex:
                msgs.append(f'  E {u["id"]}: EUC-JPにない文字 {t[ex.start:ex.end]!r}')
                e += 1
                continue
            if b > MAX_BYTES:
                msgs.append(f'  E {u["id"]}: {b}/{MAX_BYTES} バイト（全角{MAX_BYTES // 2}文字まで）。縮めてください')
                e += 1
            if t.count('|') != u['en'].count('|'):
                msgs.append(f'  E {u["id"]}: 改行記号 | の数が原文（{u["en"].count("|")}）と違います')
                e += 1
            if re.findall(r'%[-+#0-9.]*[A-Za-z]', t) != re.findall(r'%[-+#0-9.]*[A-Za-z]', u['en']):
                msgs.append(f'  E {u["id"]}: 書式指定子が原文と違います')
                e += 1
            if '_' in t or '"' in t or '\\' in t:
                msgs.append(f'  E {u["id"]}: 使えない記号（_ " \\）があります')
                e += 1
            if t.strip() == u['en'].strip() and re.search('[a-z]{3}', t):
                msgs.append(f'  W {u["id"]}: 英語のまま')
                w += 1
        extra = [k for k in ja if not k.startswith('_') and k not in {str(u['id']) for u in c['units']}]
        if extra:
            msgs.append(f'  W 余分なid: {extra[:5]}')
            w += 1
        print(f'== {name}: エラー{e} 警告{w}')
        for m in msgs:
            print(m)
        errs += e
        warns += w
    print(f'{len(names)} chunks, errors {errs}, warnings {warns}')
    return 1 if errs else 0


def build(out, tsv):
    units = {str(u['id']): u for u in json.load(open(os.path.join(out, 'units.json'), encoding='utf-8'))}
    tr = {}
    jdir = os.path.join(out, 'ja')
    for fn in sorted(os.listdir(jdir), key=lambda f: (f != 'known.json', f)):   # chunks override known.json
        if fn.endswith('.json'):
            for k, v in json.load(open(os.path.join(jdir, fn), encoding='utf-8')).items():
                if k in units and isinstance(v, str) and v.strip():
                    tr[k] = v.translate(NORMALIZE)
    esc = lambda s: s.replace('\\', '\\\\').replace('\t', '\\t').replace('\n', '\\n')
    with open(tsv, 'w', encoding='utf-8', newline='\n') as f:
        f.write('id\tenglish\tjapanese\n')
        for k in sorted(tr, key=int):
            f.write(f'{k}\t{esc(units[k]["en"])}\t{esc(tr[k])}\n')
    print(f'{len(tr)}/{len(units)} translated -> {tsv}')


def main(argv):
    if not argv:
        print(__doc__)
        return 2
    cmd, args = argv[0], argv[1:]
    if cmd == 'extract':
        extract(*args)
    elif cmd == 'chunk':
        chunk(*args)
    elif cmd == 'check':
        return check(args[0], args[1:])
    elif cmd == 'build':
        build(*args)
    else:
        print(__doc__)
        return 2
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
