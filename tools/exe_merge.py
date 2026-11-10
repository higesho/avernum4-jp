"""Write translated exe strings (OUT_DIR/ja/*.json) into the japanese column of exe_strings.tsv.

usage:
    python -I exe_merge.py EXE_STRINGS_TSV OUT_DIR

A translation identical to the English is left empty (the string stays English).
Real newlines / tabs in a translation are written as the TSV escapes \\n / \\t.
Then run check_exe_strings.py to validate and install the table.
"""
import json
import os
import sys

sys.stdout.reconfigure(encoding='utf-8')


def main(argv):
    if len(argv) != 2:
        print(__doc__)
        return 2
    tsv, out = argv
    tr = {}
    for fn in sorted(os.listdir(os.path.join(out, 'ja'))):
        if fn.endswith('.json'):
            for k, v in json.load(open(os.path.join(out, 'ja', fn), encoding='utf-8')).items():
                if not k.startswith('_') and isinstance(v, str):
                    tr[k] = v.replace('\t', '\\t').replace('\r', '\\r').replace('\n', '\\n')
    lines = open(tsv, encoding='utf-8').read().split('\n')
    n = 0
    for i, l in enumerate(lines[1:], 1):
        c = l.split('\t')
        if len(c) != 5 or c[0] not in tr:
            continue
        ja = tr[c[0]]
        c[4] = '' if ja == c[3] else ja
        lines[i] = '\t'.join(c)
        n += 1
    with open(tsv, 'w', encoding='utf-8', newline='') as f:
        f.write('\n'.join(lines))
    print(f'{n} rows updated')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
