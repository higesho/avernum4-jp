"""Extract every string literal from the original Avernum scripts as translation units.

usage:
    python -I extract.py ORIG_SCRIPTS_DIR OUT_DIR

Writes OUT_DIR/units/<file>.json: a list of units
    {"n": literal index in file, "kind": ..., "en": English text, "ctx": nearby comment}
Only translatable units are written (see TRANSLATE); the index "n" counts every
literal in the file so that build_scripts.py can put translations back.
"""
import json
import os
import re
import sys

sys.stdout.reconfigure(encoding='utf-8')

# Kinds that are shown to the player.
TRANSLATE = {
    'text', 'question', 'it_name', 'cr_name', 'ab_name', 'ob_name', 'lib',
    'print_str', 'print_str_color', 'print_big_str', 'set_name', 'shop',
    'set_terrain_string_range', 'message_dialog', 'add_dialog_str', 'run_teleport',
    'give_char_text_bubble', 'print_named_str', 'set_personality_name',
    'run_text_on_char',    # floating text over a character (39 bytes, like text bubbles)
    'set_cutscene_text',   # one line of a cutscene caption
}
CALLS = {'print_str', 'print_str_color', 'print_big_str', 'print_named_str'}
NO_LETTERS = re.compile(r'^[^A-Za-z]*$')


def decode(b: bytes) -> str:
    # Original files are MacRoman (0xD5 = right single quote, 0xC9 = ellipsis ...).
    return b.decode('mac_roman')


def literals(data: bytes):
    """Yield (start, end, text_bytes, kind, comment) for each literal outside comments."""
    i, n = 0, len(data)
    last_comment = ''
    stmt_start = 0
    while i < n:
        c = data[i]
        if data.startswith(b'//', i):
            j = i
            while j < n and data[j] not in (10, 13):
                j += 1
            last_comment = decode(data[i + 2:j]).strip()
            i = j
            continue
        if data.startswith(b'/*', i):
            j = data.find(b'*/', i + 2)
            i = n if j < 0 else j + 2
            continue
        if c in (ord(';'), ord('{'), ord('}')):
            stmt_start = i + 1
            i += 1
            continue
        if c == ord('"'):
            j = i + 1
            while j < n and data[j] not in (ord('"'), 10, 13):
                j += 1
            head = decode(data[stmt_start:i])
            yield i, j + 1, data[i + 1:j], classify(head), last_comment, statement(data, i, j + 1, stmt_start)
            i = j + 1
            continue
        i += 1


def classify(head: str) -> str:
    h = re.sub(r'\s+', ' ', head).strip()
    m = re.search(r'([A-Za-z_][A-Za-z_0-9]*)\s*=\s*$', h)
    if m:
        k = m.group(1)
        return 'text' if re.fullmatch(r'text\d', k) else k
    if re.search(r'(^|\s)\d+\s*=\s*$', h):
        return 'lib'
    # Innermost call that is still open at the literal.
    stack = []
    for t in re.finditer(r'([A-Za-z_][A-Za-z_0-9]*)?\s*\(|\)', h):
        if t.group(0) == ')':
            if stack:
                stack.pop()
        else:
            stack.append(t.group(1) or '')
    f = stack[-1] if stack else ''
    if f == 'begin_shop_mode':
        return 'shop' if '"' not in h else 'shop_arg'
    return f or 'other'


def statement(data: bytes, s: int, e: int, stmt_start: int) -> str:
    j = data.find(b';', e)
    j = len(data) if j < 0 else j + 1
    return re.sub(r'\s+', ' ', decode(data[stmt_start:j])).strip()[:300]


def main(argv):
    if len(argv) != 2:
        print(__doc__)
        return 2
    src, out = argv
    os.makedirs(os.path.join(out, 'units'), exist_ok=True)
    total_units = total_chars = 0
    kinds = {}
    skipped = {}
    for fn in sorted(os.listdir(src)):
        if not fn.lower().endswith('.txt'):
            continue
        data = open(os.path.join(src, fn), 'rb').read()
        units = []
        for idx, (s, e, b, kind, comment, stmt) in enumerate(literals(data)):
            en = decode(b)
            if kind not in TRANSLATE or NO_LETTERS.match(en):
                if en.strip():
                    skipped[kind] = skipped.get(kind, 0) + 1
                continue
            u = {'n': idx, 'kind': kind, 'en': en}
            if comment:
                u['ctx'] = comment
            if kind in CALLS and stmt.count('"') > 2:
                u['code'] = stmt  # several literals / values are joined: translate as a fragment
            units.append(u)
            kinds[kind] = kinds.get(kind, 0) + 1
            total_chars += len(en)
        if units:
            with open(os.path.join(out, 'units', fn[:-4] + '.json'), 'w', encoding='utf-8') as f:
                json.dump(units, f, ensure_ascii=False, indent=0)
            total_units += len(units)
    print(f'{total_units} units, {total_chars} chars')
    for k, v in sorted(kinds.items(), key=lambda x: -x[1]):
        print(f'  {k}: {v}')
    print('skipped (not translated):', dict(sorted(skipped.items(), key=lambda x: -x[1])))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
