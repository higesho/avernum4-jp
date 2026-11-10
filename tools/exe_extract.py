"""List the UI strings of Avernum 2.exe for translation, reusing the Escape From the Pit table.

usage:
    python -I exe_extract.py "Avernum 2.exe" REF_TSV OUT_TSV [--lo 0x5dd000 --hi 0x5f0000]

A string is listed when it is NUL-terminated printable text in .rdata, at least one
relocated 4-byte immediate in .text points at its first byte (push imm32 / mov reg, imm32,
the only way the DLL can redirect it), and it contains a letter.
Columns: va, sink, refs, english, japanese (same as the Escape From the Pit table).
* Strings whose English is in REF_TSV get that row's sink and translation.
* Other strings get a sink guessed from the function called right after the reference;
  call targets are learned from the reused rows (the call after a "message" string is the
  message function, and so on). Unknown: "?". Each row also gets a short "ctx" note in a
  separate JSON (OUT_TSV + '.ctx.json'): the instructions around each reference.
Strings before --lo belong to libraries (libpng, libtiff, CRT) and are skipped.
"""
import collections
import json
import re
import sys

import capstone
import pefile

sys.stdout.reconfigure(encoding='utf-8')


def esc(s):
    return s.replace('\\', '\\\\').replace('\t', '\\t').replace('\n', '\\n').replace('\r', '\\r')


def unesc(s):
    return re.sub(r'\\(.)', lambda m: {'n': '\n', 't': '\t', 'r': '\r'}.get(m.group(1), m.group(1)), s)


SPEC = re.compile(r'%[-+ #0]*\d*(?:\.\d+)?[hlL]?[diouxXeEfgGcsp%]')
INTERNAL_WORDS = ('Spiderweb Software', 'Avernum 2 Files', 'Saved Games', 'GL_', 'wgl', 'KGraphic', 'phelios',
                  '.dat', 'screenshot', 'Save%d', 'header', 'corporation', 'gdi generic')


def is_internal(s):
    """File names, cheat codes, library and format-only strings: never shown, keep English."""
    if not re.search('[A-Za-z]', SPEC.sub('', s)):
        return True
    if any(w in s for w in INTERNAL_WORDS):
        return True
    if ' ' not in s.strip() and (re.fullmatch(r'[a-z0-9_%]+', s.strip()) or re.search(r'[./\\]', s)):
        return True
    return False


def main(argv):
    lo, hi = 0x5dd000, 0x5f0000
    if '--lo' in argv:
        lo = int(argv[argv.index('--lo') + 1], 16)
    if '--hi' in argv:
        hi = int(argv[argv.index('--hi') + 1], 16)
    args = [a for i, a in enumerate(argv) if not a.startswith('--') and (i == 0 or not argv[i - 1].startswith('--'))]
    if len(args) != 3:
        print(__doc__)
        return 2
    exe, ref_tsv, out_tsv = args
    pe = pefile.PE(exe)
    base = pe.OPTIONAL_HEADER.ImageBase
    img = pe.get_memory_mapped_image()
    text = [s for s in pe.sections if s.Name.startswith(b'.text')][0]
    t0, t1 = base + text.VirtualAddress, base + text.VirtualAddress + text.Misc_VirtualSize
    # relocated dwords inside .text -> target
    refs = collections.defaultdict(list)
    for blk in pe.DIRECTORY_ENTRY_BASERELOC:
        for e in blk.entries:
            if e.type != 3:
                continue
            at = base + e.rva
            if t0 <= at < t1:
                tgt = int.from_bytes(img[e.rva:e.rva + 4], 'little')
                if lo <= tgt < hi:
                    refs[tgt].append(at)
    md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)

    def insns_around(at, before=24, after=40):
        """Disassemble from a little before the reference; return list of (va, text)."""
        for back in range(before, 0, -1):
            start = at - back
            code = img[start - base:start - base + back + after]
            out, ok = [], False
            for i in md.disasm(code, start):
                out.append((i.address, i.size, f'{i.mnemonic} {i.op_str}'))
                if i.address <= at < i.address + i.size:
                    ok = True
            if ok and any(a <= at < a + s for a, s, _ in out) and out and out[0][0] == start:
                return out
        return []

    def next_call(at):
        ins = insns_around(at)
        seen = False
        for a, s, t in ins:
            if a <= at < a + s:
                seen = True
                continue
            if seen and t.startswith('call 0x'):
                return int(t[5:], 16)
        return None

    strings = {}
    for tgt in refs:
        end = img.find(b'\0', tgt - base)
        b = img[tgt - base:end]
        if not b or len(b) > 2000:
            continue
        if img[tgt - base - 1] not in (0, 0xCC):  # a pointer into the middle of another string
            continue
        try:
            s = b.decode('ascii')
        except UnicodeDecodeError:
            continue
        if not all(32 <= ord(c) < 127 or c in '\n\r\t' for c in s) or not re.search('[A-Za-z]', s):
            continue
        strings[tgt] = s
    ref_rows = {}
    for line in open(ref_tsv, encoding='utf-8').read().split('\n')[1:]:
        c = line.split('\t')
        if len(c) >= 5:
            ref_rows.setdefault(unesc(c[3]), (c[1], c[4]))
    # learn call target -> sink from reused rows
    votes = collections.defaultdict(collections.Counter)
    for va, s in strings.items():
        if s in ref_rows and ref_rows[s][0]:
            for at in refs[va]:
                t = next_call(at)
                if t:
                    votes[t][ref_rows[s][0]] += 1
    sink_of = {t: c.most_common(1)[0][0] for t, c in votes.items() if c.most_common(1)[0][1] >= 2}
    rows, ctx = [], {}
    n_reuse = n_new = 0
    for va in sorted(strings):
        s = strings[va]
        if s in ref_rows:
            sink, ja = ref_rows[s]
            n_reuse += 1
        else:
            guess = collections.Counter(sink_of.get(next_call(at), '?') for at in refs[va])
            sink, ja = guess.most_common(1)[0][0], ''
            if is_internal(s):
                sink = 'internal'
            elif 'internal' in sink:      # a guess from the call after the reference: not enough to hide text
                sink = '?'
            n_new += 1
            notes = []
            for at in refs[va][:3]:
                notes.append('; '.join(t for a, sz, t in insns_around(at, 16, 30)))
            ctx['0x%06x' % va] = notes
        rows.append(['0x%06x' % va, sink, str(len(refs[va])), esc(s), esc(ja)])
    with open(out_tsv, 'w', encoding='utf-8', newline='\n') as f:
        f.write('va\tsink\trefs\tenglish\tjapanese\n')
        for r in rows:
            f.write('\t'.join(r) + '\n')
    json.dump(ctx, open(out_tsv + '.ctx.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=0)
    print(f'{len(rows)} strings: {n_reuse} from the reference table, {n_new} new; '
          f'{len(sink_of)} call targets classified')
    print(collections.Counter(r[1] for r in rows if not r[4]).most_common())
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
