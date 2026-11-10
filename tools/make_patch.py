"""Build the distributable patch file (no original game data inside).

usage:
    python -I make_patch.py ORIGINAL_ROOT PATCHED_ROOT OUT_FILE

ORIGINAL_ROOT and PATCHED_ROOT are game folders (the folder with Avernum 4.exe).
Every file under "Data" that differs between the two becomes one entry.

Format (little endian):
    b"AJPATCH1", u32 file_count
    per file: u16 path_len, path (UTF-8, '/' separated, relative to the game folder)
              u32 src_len, 32-byte SHA-256 of the original
              u32 dst_len, 32-byte SHA-256 of the result
              u32 op_count, ops
    ops:      1 COPY   u32 src_off, u32 len            (bytes from the original)
              2 INSERT u32 len, bytes                  (new bytes: the translation)
              3 ADD    u32 src_off, u32 len, bytes     (out[i] = bytes[i] + src[(src_off+i) % src_len])

Images are stored as one ADD op against the original image, so the patch file holds
no usable picture by itself. Text and data files use COPY/INSERT, so only the
translated text is stored.
"""
import hashlib
import os
import struct
import sys

BLOCK = 24
IMAGE_EXT = ('.png', '.jpg', '.bmp')


def delta_ops(src, dst):
    index = {}
    for i in range(0, len(src) - BLOCK + 1, BLOCK):
        index.setdefault(src[i:i + BLOCK], i)
    ops, lit, j, n = [], bytearray(), 0, len(dst)
    while j < n:
        k = index.get(dst[j:j + BLOCK]) if j + BLOCK <= n else None
        if k is None:
            lit.append(dst[j])
            j += 1
            continue
        # extend backwards into the pending literal, then forwards
        b = 0
        while b < len(lit) and k - b > 0 and src[k - b - 1] == lit[-1 - b]:
            b += 1
        if b:
            del lit[len(lit) - b:]
        s, d = k - b, j - b
        e = BLOCK + b
        while d + e < n and s + e < len(src) and src[s + e] == dst[d + e]:
            e += 1
        if lit:
            ops.append((2, bytes(lit)))
            lit = bytearray()
        if ops and ops[-1][0] == 1 and ops[-1][1] + ops[-1][2] == s:
            ops[-1] = (1, ops[-1][1], ops[-1][2] + e)
        else:
            ops.append((1, s, e))
        j = d + e
    if lit:
        ops.append((2, bytes(lit)))
    return ops


def add_ops(src, dst):
    m = len(src)
    return [(3, 0, bytes((dst[i] - src[i % m]) & 255 for i in range(len(dst))))]


def apply(src, ops):
    out = bytearray()
    for op in ops:
        if op[0] == 1:
            out += src[op[1]:op[1] + op[2]]
        elif op[0] == 2:
            out += op[1]
        else:
            m = len(src)
            out += bytes((b + src[(op[1] + i) % m]) & 255 for i, b in enumerate(op[2]))
    return bytes(out)


def encode(path, src, dst, ops):
    p = path.encode('utf-8')
    r = bytearray(struct.pack('<H', len(p)) + p)
    r += struct.pack('<I', len(src)) + hashlib.sha256(src).digest()
    r += struct.pack('<I', len(dst)) + hashlib.sha256(dst).digest()
    r += struct.pack('<I', len(ops))
    for op in ops:
        if op[0] == 1:
            r += struct.pack('<BII', 1, op[1], op[2])
        elif op[0] == 2:
            r += struct.pack('<BI', 2, len(op[1])) + op[1]
        else:
            r += struct.pack('<BII', 3, op[1], len(op[2])) + op[2]
    return r


def main(argv):
    if len(argv) != 3:
        print(__doc__)
        return 2
    orig, patched, out = argv
    entries, stats = [], {'files': 0, 'insert': 0, 'add': 0}
    base = os.path.join(patched, 'Data')
    for dirpath, _, files in os.walk(base):
        for fn in sorted(files):
            pf = os.path.join(dirpath, fn)
            rel = os.path.relpath(pf, patched).replace('\\', '/')
            of = os.path.join(orig, rel)
            if not os.path.exists(of):
                continue
            src, dst = open(of, 'rb').read(), open(pf, 'rb').read()
            if src == dst:
                continue
            ops = add_ops(src, dst) if fn.lower().endswith(IMAGE_EXT) else delta_ops(src, dst)
            if apply(src, ops) != dst:
                raise SystemExit('self-check failed: ' + rel)
            entries.append(encode(rel, src, dst, ops))
            stats['files'] += 1
            stats['insert'] += sum(len(o[1]) for o in ops if o[0] == 2)
            stats['add'] += sum(len(o[2]) for o in ops if o[0] == 3)
    with open(out, 'wb') as f:
        f.write(b'AJPATCH1' + struct.pack('<I', len(entries)))
        for e in entries:
            f.write(e)
    print('files %(files)d, inserted %(insert)d bytes, image delta %(add)d bytes' % stats,
          '->', out, os.path.getsize(out), 'bytes')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
