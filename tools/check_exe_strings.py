"""Check the exe string translation table (exe_strings.tsv) before installing it.

usage: python -I check_exe_strings.py exe_strings.tsv [GAME_DIR]

Checks every row that has a Japanese translation:
  * printf specifiers must match the English ones (same kinds, same count).
    Reordering is allowed only with positional form %1$s %2$d ... (the DLL then
    hooks sprintf and uses _vsprintf_p).
  * floating text (sink "float") must be <= 39 bytes in EUC-JP.
  * every character must exist in EUC-JP.
  * leading/trailing spaces of concatenation fragments are reported if dropped.
  * rows marked "internal" and paths / file names (PATHLIKE) must stay English.
With GAME_DIR, the file is also copied there as avernum_jp_exe.tsv when no errors.
"""
import csv
import os
import re
import shutil
import sys

sys.stdout.reconfigure(encoding='utf-8')

SPEC = re.compile(r'%(?:(\d)\$)?[-+ #0]*\d*(?:\.\d+)?[hlL]?([diouxXeEfgGcsp%])')
NORMALIZE = str.maketrans({'～': '〜', '－': '−', '∥': '‖'})
# Paths and file names built by the game ("%s%sAvernum 3 Files%s", "G%d.png", "Scripts\\...").
# Translating one breaks file loading (the intro cutscene hung on a grey floor in A3 v0.9.0).
PATHLIKE = re.compile(r'\b(?:Avernum \d )?(?:Files|Graphics Core|Scripts|Sounds)%s|%s[\\/]|[\\/]%s'
                      r'|\.(?:txt|png|dat|bmp|wav|ogg|mp3|jpg|exe|dll|sav|ini)\b(?!\s+\w)', re.I)


def specs(s):
    out = []
    for m in SPEC.finditer(s):
        if m.group(2) == '%':
            continue
        out.append((int(m.group(1)) if m.group(1) else None, 'd' if m.group(2) in 'diouxX' else m.group(2)))
    return out


def unescape(s):
    return re.sub(r'\\(.)', lambda m: {'n': '\n', 'r': '\r', 't': '\t'}.get(m.group(1), m.group(1)), s)


def main(argv):
    if not argv:
        print(__doc__)
        return 2
    errors, warnings, done, total = [], [], 0, 0
    with open(argv[0], encoding='utf-8-sig', newline='') as f:
        rows = list(csv.reader(f, delimiter='\t', quoting=csv.QUOTE_NONE))
    for n, row in enumerate(rows[1:], 2):
        if len(row) < 4:
            continue
        total += 1
        if len(row) < 5 or not row[4]:
            continue
        done += 1
        va, sink, en, ja = row[0], row[1], unescape(row[3]), unescape(row[4]).translate(NORMALIZE)
        where = f'{n}行目 ({va} 「{en[:30]}」)'
        try:
            euc = ja.encode('euc_jp')
        except UnicodeEncodeError as e:
            errors.append(f'{where}: EUC-JPにない文字 {ja[e.start:e.end]!r}')
            continue
        se, sj = specs(en), specs(ja)
        if any(p for p, _ in sj):
            errors.append(f'{where}: Avernum 4 では %1$s 形式（順番の入れ替え）は使えません')
        if any(p for p, _ in sj):
            if any(p is None for p, _ in sj):
                errors.append(f'{where}: %1$s 形式と通常の %s を混在できません')
            elif sorted(sj, key=lambda x: x[0]) != [(i + 1, k) for i, (_, k) in enumerate(se)]:
                errors.append(f'{where}: 書式指定子が英語と対応していません 英:{[k for _, k in se]} 訳:{sj}')
        elif [k for _, k in se] != [k for _, k in sj]:
            errors.append(f'{where}: 書式指定子が英語と一致しません 英:{[k for _, k in se]} 訳:{[k for _, k in sj]}')
        if sink == 'internal' or PATHLIKE.search(en):
            errors.append(f'{where}: ファイル名・フォルダ名・内部用の文字列は訳せません（ゲームがデータを読めなくなる）')
        if 'float' in sink and len(euc) > 39:
            errors.append(f'{where}: 頭上テキストが {len(euc)}/39 バイトです（表示されません）')
        if en[:1] == ' ' and ja[:1] not in (' ', '　') or en[-1:] == ' ' and ja[-1:] not in (' ', '　'):
            warnings.append(f'{where}: 英語の前後の空白が訳文にありません（つなげて表示する部品の可能性）')
    for e in errors:
        print('ERROR', e)
    for w in warnings:
        print('warn ', w)
    print(f'{done}/{total} 件翻訳済み、エラー {len(errors)} 件、警告 {len(warnings)} 件')
    if len(argv) > 1 and not errors:
        dst = os.path.join(argv[1], 'avernum_jp_exe.tsv')
        shutil.copyfile(argv[0], dst)
        print('copied to', dst)
    return 1 if errors else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
