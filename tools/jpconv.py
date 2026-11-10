"""Convert translated Avernum script files (UTF-8) to the game's EUC-JP and check limits.

usage:
    python -I jpconv.py SRC_DIR DST_DIR          convert every *.txt in SRC_DIR into DST_DIR
    python -I jpconv.py --check SRC_DIR          only report problems

Source files are UTF-8. Bytes that are not valid UTF-8 (the original MacRoman
quotes such as 0xD5) are passed through unchanged.

Limits come from Avernum.exe (v1.0.1S) analysis:
  * every "..." literal in any script / text library : <= 510 bytes
      (tokenizer at 0x46fd24 rejects >= 511 -> "Overlong or unending string")
  * set_name(n, "...") creature names at runtime       : <= 19 bytes
      (0x47ac3d warns, and strcpy's into a fixed field -> memory corruption)
  * definition files (av*.txt), silently truncated:
      cr_name 19, it_name 25, ab_name 19 (conservative), ob_name 19,
      tr_name 12, fl_name 12, tmp_name 15  (internal names, not shown in game)
  * floating text over characters                      : <= 39 bytes
"""
import os
import re
import sys

sys.stdout.reconfigure(encoding='utf-8')

LITERAL_MAX = 510
SET_NAME_MAX = 19
FIELD_MAX = {
    'cr_name': 19, 'it_name': 25, 'ab_name': 19, 'ob_name': 19,
    'tr_name': 12, 'fl_name': 12, 'tmp_name': 15,
}
FIELD_RE = re.compile(rb'\b(' + b'|'.join(k.encode() for k in FIELD_MAX) + rb')\s*=\s*"([^"]*)"')
SET_NAME_RE = re.compile(rb'\bset_name\s*\(\s*[^,]+,\s*"([^"]*)"')
LITERAL_RE = re.compile(rb'"([^"\r\n]*)"')


# Windows-style code points that Python's euc_jp codec does not map.
NORMALIZE = str.maketrans({'～': '〜', '－': '−', '∥': '‖',
                           '￠': '¢', '￡': '£', '￢': '¬'})


def to_euc(data: bytes, name: str, problems: list) -> bytes:
    text = data.decode('utf-8', errors='surrogateescape').translate(NORMALIZE)
    out = []
    for lineno, line in enumerate(text.splitlines(keepends=True), 1):
        try:
            out.append(line.encode('euc_jp', errors='surrogateescape'))
        except UnicodeEncodeError as e:
            bad = line[e.start:e.end]
            problems.append(f'{name}:{lineno}: EUC-JPにない文字 {bad!r} (U+{ord(bad[0]):04X})')
            out.append(line.encode('euc_jp', errors='replace'))
    return b''.join(out)


def line_of(data: bytes, pos: int) -> int:
    return data.count(b'\n', 0, pos) + data.count(b'\r', 0, pos) - data.count(b'\r\n', 0, pos) + 1


def check(euc: bytes, name: str, problems: list):
    def show(b):
        return b.decode('euc_jp', errors='replace')[:30]
    for m in LITERAL_RE.finditer(euc):
        n = len(m.group(1))
        if n > LITERAL_MAX:
            problems.append(f'{name}:{line_of(euc, m.start())}: 文字列が長すぎます {n}/{LITERAL_MAX}バイト 「{show(m.group(1))}…」')
    for m in SET_NAME_RE.finditer(euc):
        n = len(m.group(1))
        if n > SET_NAME_MAX:
            problems.append(f'{name}:{line_of(euc, m.start())}: set_nameの名前が長すぎます {n}/{SET_NAME_MAX}バイト 「{show(m.group(1))}」')
    for m in FIELD_RE.finditer(euc):
        key, val = m.group(1).decode(), m.group(2)
        if len(val) > FIELD_MAX[key]:
            problems.append(f'{name}:{line_of(euc, m.start())}: {key}が長すぎます {len(val)}/{FIELD_MAX[key]}バイト 「{show(val)}」(超過分は切り捨て)')


def main(argv):
    check_only = '--check' in argv
    args = [a for a in argv if a != '--check']
    if (check_only and len(args) != 1) or (not check_only and len(args) != 2):
        print(__doc__)
        return 2
    src = args[0]
    dst = None if check_only else args[1]
    problems = []
    count = 0
    for fn in sorted(os.listdir(src)):
        if not fn.lower().endswith('.txt'):
            continue
        with open(os.path.join(src, fn), 'rb') as f:
            data = f.read()
        euc = to_euc(data, fn, problems)
        check(euc, fn, problems)
        if dst:
            with open(os.path.join(dst, fn), 'wb') as f:
                f.write(euc)
        count += 1
    for p in problems:
        print(p)
    print(f'{count} files, {len(problems)} problems')
    return 1 if problems else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
