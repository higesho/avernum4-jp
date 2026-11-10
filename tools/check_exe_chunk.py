"""Check translated exe-string chunks (trans_exe/ja/exeNN.json) before merging.

usage:
    python -I check_exe_chunk.py OUT_DIR [CHUNK ...]

errors:   missing ids, printf specifiers that differ from the English (kinds and count;
          positional %1$s allowed only if every specifier is positional), floating
          text over 39 bytes, characters not in EUC-JP, tabs
warnings: text left in English (unless it is a debug message), glossary term not used
"""
import json
import os
import re
import sys

sys.stdout.reconfigure(encoding='utf-8')
SPEC = re.compile(r'%(?:(\d)\$)?[-+ #0]*\d*(?:\.\d+)?[hlL]?([diouxXeEfgGcsp%])')
NORMALIZE = str.maketrans({'～': '〜', '－': '−', '∥': '‖', '￠': '¢', '￡': '£', '￢': '¬'})
DEBUG = re.compile(r'NULL|engine|queried|called prematurely|given as|_[a-z]+_|Error|error|failure|Invalid|script', re.I)


def specs(s):
    out = []
    for m in SPEC.finditer(s):
        if m.group(2) == '%':
            continue
        out.append((int(m.group(1)) if m.group(1) else None, 'd' if m.group(2) in 'diouxX' else m.group(2)))
    return out


def check(u, ja, gloss):
    errs, warns = [], []
    k, en = u['id'], u['en']
    if not isinstance(ja, str) or ja == '':
        return [f'{k}: 訳がない'], []
    se, sj = specs(en), specs(ja)
    pos = [p for p, _ in sj if p is not None]
    if pos:
        errs.append(f'{k}: Avernum 4 では %1$s 形式（順番の入れ替え）は使えない。原文と同じ順番の %s / %d にする')
    if pos and len(pos) != len(sj):
        errs.append(f'{k}: 順番指定（%1$s）と通常の %s を混在させている')
    if pos:
        order = [t for _, t in sorted(sj)]
        if sorted(pos) != list(range(1, len(sj) + 1)) or order != [t for _, t in se]:
            errs.append(f'{k}: 順番指定の番号・種類が原文の書式指定子と合わない（原文 {se}、訳 {sj}）')
    elif [t for _, t in sj] != [t for _, t in se]:
        errs.append(f'{k}: 書式指定子が原文と違う（原文 {[t for _, t in se]}、訳 {[t for _, t in sj]}）')
    if '\t' in ja:
        errs.append(f'{k}: タブ文字がある')
    try:
        n = len(ja.translate(NORMALIZE).encode('euc_jp'))
        if 'max_bytes' in u and n > u['max_bytes']:
            errs.append(f'{k}: 長すぎる（{n}バイト、上限{u["max_bytes"]}＝全角{u["max_bytes"] // 2}文字）')
    except UnicodeEncodeError as e:
        errs.append(f'{k}: EUC-JPにない文字 {ja[e.start:e.end]!r}')
    if re.search(r'[A-Za-z]{3}', en) and not re.search(r'[぀-ヿ一-鿿]', ja) and not DEBUG.search(en):
        warns.append(f'{k}: 英語のまま')
    used = en
    for rx, ten, tja in gloss:
        if rx.search(used):
            used = rx.sub(' ', used)
            if tja not in ja and not DEBUG.search(en):
                warns.append(f'{k}: 対訳表の「{ten}」→「{tja}」が使われていない')
    return errs, warns


def main(argv):
    if not argv:
        print(__doc__)
        return 2
    out = argv[0]
    names = argv[1:] or sorted(f[:-5] for f in os.listdir(os.path.join(out, 'ja')) if f.endswith('.json'))
    ne = nw = 0
    for name in names:
        src = json.load(open(os.path.join(out, 'chunks', name + '.json'), encoding='utf-8'))['units']
        job = json.load(open(os.path.join(out, 'jobs', name + '.json'), encoding='utf-8'))
        gloss = sorted(((re.compile(r'\b' + re.escape(e) + r'\b'), e, j) for e, j in job['glossary'].items()),
                       key=lambda x: -len(x[1]))
        try:
            ja = json.load(open(os.path.join(out, 'ja', name + '.json'), encoding='utf-8'))
        except FileNotFoundError:
            print(f'== {name}: 出力ファイルがない')
            ne += 1
            continue
        except json.JSONDecodeError as e:
            print(f'== {name}: JSONとして読めない: {e}')
            ne += 1
            continue
        errs, warns = [], []
        for u in src:
            e, w = check(u, ja.get(u['id']), gloss)
            errs += e
            warns += w
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


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
