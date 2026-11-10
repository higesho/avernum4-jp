"""Check translated chunks against the source chunks, style rules and the glossary.

usage:
    python -I check_trans.py TRANS_DIR [CHUNK ...]

For each TRANS_DIR/chunks/<name>.json that has TRANS_DIR/ja/<name>.json, report
  errors   (must be fixed): missing ids, forbidden characters, '|' / '$' / edge spaces
           not kept, '_' left in, too long, not encodable in EUC-JP
  warnings: text left in English, glossary term not used
Writes TRANS_DIR/check_report.json: {chunk: {"errors": [...], "warnings": [...]}}
"""
import json
import os
import re
import sys

sys.stdout.reconfigure(encoding='utf-8')

NORMALIZE = str.maketrans({'～': '〜', '－': '−', '∥': '‖', '￠': '¢', '￡': '£', '￢': '¬'})
LITERAL_MAX = 510
KIND_MAX = {'give_char_text_bubble': 39, 'run_text_on_char': 39, 'set_cutscene_text': 80, 'cr_name': 19, 'set_name': 19, 'set_personality_name': 19,
            'ab_name': 19, 'ob_name': 19, 'it_name': 25,
            # joined as "<name><text>" into a 256-byte buffer by the DLL (0x47bcfc); name <= 19 bytes
            'print_named_str': 230}


def euc_len(s):
    return len(s.translate(NORMALIZE).encode('euc_jp'))


def load_glossary(tdir):
    p = os.path.join(tdir, 'glossary.json')
    if not os.path.exists(p):
        return []
    out = []
    for t in json.load(open(p, encoding='utf-8')):
        if t.get('keep') and t['ja']:
            en, ja = t['en'].rstrip('.'), t['ja'].rstrip('。.')  # quest titles end with "."
            out.append((re.compile(r'\b' + re.escape(en) + r'\b'), en, ja))
    # longer terms first so that "Fort Avernum" is checked before "Avernum"
    out.sort(key=lambda x: -len(x[1]))
    return out


def edge(s):
    return re.match(r'^\s*', s).group(0), re.search(r'\s*$', s).group(0)


def check_unit(u, ja, gloss):
    errs, warns = [], []
    en = u['en']
    if not isinstance(ja, str) or not ja.strip():
        return [f'{u["id"]}: 訳がない'], []
    if '"' in ja or '\\' in ja:
        errs.append(f'{u["id"]}: 使えない文字（" または \\）がある')
    if '_' in ja:
        errs.append(f'{u["id"]}: _ が残っている（台詞は「」にする）')
    if en.count('|') != ja.count('|'):
        errs.append(f'{u["id"]}: | の数が原文と違う（原文{en.count("|")}、訳{ja.count("|")}）')
    if en.startswith('$') != ja.startswith('$'):
        errs.append(f'{u["id"]}: 先頭の $ を残していない')
    if edge(en) != edge(ja):
        errs.append(f'{u["id"]}: 先頭・末尾の空白が原文と違う（原文{edge(en)!r}、訳{edge(ja)!r}）')
    try:
        n = euc_len(ja)
        lim = KIND_MAX.get(u['kind'], LITERAL_MAX)
        if 'max' in u:
            lim = min(lim, u['max'] * 2)
        if n > lim:
            errs.append(f'{u["id"]}: 長すぎる（{n}バイト、上限{lim}バイト＝全角{lim // 2}文字）')
    except UnicodeEncodeError as e:
        errs.append(f'{u["id"]}: EUC-JPにない文字 {ja[e.start:e.end]!r}')
    if re.search(r'[A-Za-z]{3}', en) and not re.search(r'[぀-ヿ一-鿿]', ja):
        warns.append(f'{u["id"]}: 英語のまま')
    if re.search(r'\b(feet|foot|inch|inches|miles?|yards?)\b', en) and re.search(r'メートル|センチ|キロ', ja):
        warns.append(f'{u["id"]}: 単位を換算している（原文どおりフィート・インチ・マイルにする）')
    if re.fullmatch(r'\s*_[^_]*_\s*', en) and not re.match(r'\s*「', ja):
        errs.append(f'{u["id"]}: 原文全体が台詞（_…_）なのに「」で囲まれていない')
    if u['kind'] == 'question' and re.search(r'(ぞ|ぜ|だな|わよ|かしら|わね)[。！？!?]?」', ja):
        warns.append(f'{u["id"]}: 一行の発言に性別や癖の強い語尾がある（STYLE.md 1章）')
    used = en
    for rx, ten, tja in gloss:
        if rx.search(used):
            used = rx.sub(' ', used)
            if tja not in ja:
                warns.append(f'{u["id"]}: 対訳表の「{ten}」→「{tja}」が使われていない')
    return errs, warns


def main(argv):
    if not argv:
        print(__doc__)
        return 2
    tdir = argv[0]
    names = argv[1:] or sorted(f[:-5] for f in os.listdir(os.path.join(tdir, 'ja'))
                             if f.endswith('.json') and not f.endswith('__known.json'))  # reused EFTP text
    gloss = load_glossary(tdir)
    report = {}
    ne = nw = nunits = 0
    for name in names:
        src = json.load(open(os.path.join(tdir, 'chunks', name + '.json'), encoding='utf-8'))
        p = os.path.join(tdir, 'ja', name + '.json')
        errs, warns = [], []
        try:
            out = json.load(open(p, encoding='utf-8'))
        except FileNotFoundError:
            errs.append('出力ファイルがない')
            out = None
        except json.JSONDecodeError as e:
            errs.append(f'JSONとして読めない: {e}')
            out = None
        if out is not None:
            ids = {str(u['id']) for u in src['units']}
            extra = [k for k in out if k not in ids and not k.startswith('_')]
            if extra:
                errs.append(f'原文にないid: {extra[:10]}')
            for u in src['units']:
                e, w = check_unit(u, out.get(str(u['id'])), gloss)
                errs += e
                warns += w
                nunits += 1
        report[name] = {'errors': errs, 'warnings': warns}
        ne += len(errs)
        nw += len(warns)
        if errs or warns:
            print(f'== {name}: エラー{len(errs)} 警告{len(warns)}')
            for x in errs[:20]:
                print('  E', x)
            for x in warns[:10]:
                print('  W', x)
    # The same English text translated differently in different places (all chunks).
    seen = {}
    for fn in sorted(os.listdir(os.path.join(tdir, 'ja'))):
        name = fn[:-5]
        try:
            out = json.load(open(os.path.join(tdir, 'ja', fn), encoding='utf-8'))
            src = json.load(open(os.path.join(tdir, 'chunks', name + '.json'), encoding='utf-8'))
        except (json.JSONDecodeError, FileNotFoundError):
            continue
        for u in src['units']:
            ja = out.get(str(u['id']))
            if isinstance(ja, str) and len(u['en']) >= 12:
                seen.setdefault(u['en'], {}).setdefault(ja, name)
    for en, jas in seen.items():
        if len(jas) > 1:
            # report once, on the first checked chunk involved
            for n in jas.values():
                if n in report:
                    msg = f'同じ原文の訳が場所によって違う: 「{en[:40]}」→ ' + \
                        ' / '.join(f'{j[:25]}（{c}）' for j, c in jas.items())
                    report[n]['warnings'].append(msg)
                    print(f'  W [{n}] {msg}')
                    nw += 1
                    break
    with open(os.path.join(tdir, 'check_report.json'), 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=1)
    print(f'{len(names)} chunks, {nunits} units, errors {ne}, warnings {nw}')
    return 1 if ne else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
