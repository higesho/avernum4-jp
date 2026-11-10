"""Redraw the place names on the Avernum 3 continent maps in Japanese.

usage:
    python -I make_maps_a3.py ORIGINAL_DIR TRANS_DIR OUTPUT_DIR [PREVIEW_DIR]

The world map is two 980x700 pages. The south page is G207 (base) with the province
overlays G209-G211; the north page is the overlays G212-G215. G174/G175 (south) and
G176/G177 (north) are the left/right halves of the pages at 1/0.7 scale, used by the
introduction (offsets measured with ORB feature matching: page = 0.7 * image + (tx, 0)).
Labels are given in page coordinates; names come from the glossary (TRANS_DIR/glossary.json).
"""
import json
import os
import sys

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

sys.stdout.reconfigure(encoding='utf-8')
FONT = 'C:/Windows/Fonts/yumindb.ttf'
INK = (44, 30, 20)

# (page, box in page coordinates, English name, big?)  big = province names (two lines)
LABELS = [
    ('south', (64, 138, 140, 159), 'Shayder', False),
    ('south', (146, 124, 244, 184), 'Isle of Bigail', True),
    ('south', (456, 64, 608, 128), 'Karnold Province', True),
    ('south', (482, 166, 562, 195), 'Sharimik', False),
    ('south', (232, 476, 313, 508), 'Fort Emergence', False),
    ('south', (449, 466, 587, 534), 'Krizsan Province', True),
    ('south', (357, 635, 422, 665), 'Krizsan', False),
    ('north', (202, 114, 268, 163), 'Keep of Tinraya', False),
    ('north', (86, 283, 224, 349), 'Footracer Province', True),
    ('north', (484, 52, 566, 92), 'Blackcrag Fortress', False),
    ('north', (651, 228, 789, 294), 'Monoroe Province', True),
    ('north', (889, 394, 926, 416), 'Gale', False),
    ('north', (484, 594, 546, 626), 'Lorelei', False),
    ('north', (608, 601, 732, 669), 'Midori Province', True),
]
# image -> (page, scale from page to image, x offset in page coordinates); None = overlay/base
IMAGES = {
    'G207.jpg': ('south', 1.0, 0), 'G209.png': ('south', 1.0, 0), 'G210.png': ('south', 1.0, 0),
    'G211.png': ('south', 1.0, 0), 'G212.png': ('north', 1.0, 0), 'G213.png': ('north', 1.0, 0),
    'G214.png': ('north', 1.0, 0), 'G215.png': ('north', 1.0, 0),
    'G174.jpg': ('south', 1 / 0.7, 0), 'G175.jpg': ('south', 1 / 0.7, 490),
    'G176.jpg': ('north', 1 / 0.7, 0), 'G177.jpg': ('north', 1 / 0.7, 490),
}
EXTRA = {'Isle of Bigail': 'ビゲイル島'}   # used only when the glossary has no entry
SPLIT = {'Blackcrag Fortress': '要塞'}       # two-line labels in the original: break before this word


def names(tdir):
    g = {t['en']: t['ja'] for t in json.load(open(os.path.join(tdir, 'glossary.json'), encoding='utf-8')) if t.get('ja')}
    out = {}
    for _, _, en, big in LABELS:
        ja = g.get(en) or EXTRA.get(en) or en
        if big and ja.endswith('地方') and len(ja) > 4:
            ja = ja[:-2] + '|地方'           # province names: two lines like the original
        w = SPLIT.get(en)
        if w and ja.endswith(w) and len(ja) > len(w):
            ja = ja[:-len(w)] + '|' + w
        out[en] = ja
    return out


def to_image(box, scale, off):
    x0, y0, x1, y1 = box
    return [int(round((x0 - off) * scale)), int(round(y0 * scale)), int(round((x1 - off) * scale)), int(round(y1 * scale))]


def render(name, src, jn):
    page, scale, off = IMAGES[name]
    im = Image.open(os.path.join(src, name))
    rgba = im.convert('RGBA')
    w, h = rgba.size
    arr = np.array(rgba)
    boxes = []
    for pg, box, en, big in LABELS:
        if pg != page:
            continue
        b = to_image(box, scale, off)
        if b[2] <= 0 or b[0] >= w or b[3] <= 0 or b[1] >= h:
            continue
        cb = [max(0, b[0]), max(0, b[1]), min(w, b[2]), min(h, b[3])]
        if (arr[cb[1]:cb[3], cb[0]:cb[2], 3] > 128).mean() < 0.02:  # label not on this overlay
            continue
        boxes.append((b, cb, en, big))
    if not boxes:
        return None
    rgb = cv2.cvtColor(arr[:, :, :3].copy(), cv2.COLOR_RGB2BGR)
    gray = cv2.cvtColor(rgb, cv2.COLOR_BGR2GRAY)
    mask = np.zeros(gray.shape, np.uint8)
    for b, cb, en, big in boxes:
        x0, y0, x1, y1 = cb
        sub = gray[y0:y1, x0:x1]
        opaque = arr[y0:y1, x0:x1, 3] > 128          # overlays: only the painted part carries a label
        thr = np.percentile(sub[opaque], 70) - (28 if big else 18)
        mask[y0:y1, x0:x1] |= (((sub < thr) & opaque).astype(np.uint8) * 255)
    mask = cv2.dilate(mask, np.ones((3, 3), np.uint8), iterations=2)
    rgb = cv2.inpaint(rgb, mask, 6, cv2.INPAINT_TELEA)
    out = Image.fromarray(np.dstack([cv2.cvtColor(rgb, cv2.COLOR_BGR2RGB), arr[:, :, 3]]).astype(np.uint8), 'RGBA')
    layer = Image.new('L', out.size, 0)
    d = ImageDraw.Draw(layer)
    for b, cb, en, big in boxes:
        lines = jn[en].split('|')
        bw, bh = b[2] - b[0], b[3] - b[1]
        size = int(bh / len(lines) * (0.82 if big else 0.75))
        while size > 8:
            f = ImageFont.truetype(FONT, size)
            if max(f.getlength(t) for t in lines) <= bw * 1.05:
                break
            size -= 1
        f = ImageFont.truetype(FONT, size)
        lh = size * 1.12
        y = b[1] + (bh - lh * len(lines)) / 2
        for t in lines:
            d.text((b[0] + (bw - f.getlength(t)) / 2, y), t, font=f, fill=255)
            y += lh
    ink = Image.new('RGBA', out.size, INK + (255,))
    out.alpha_composite(Image.composite(ink, Image.new('RGBA', out.size, (0, 0, 0, 0)), layer))
    if name.lower().endswith('.jpg'):
        return out.convert('RGB')
    return out


# The "Continent of Valorim" plaque (G217) is also painted into the right-hand slices at
# 1.64x (position found by template matching). Paste the Japanese G217 over it.
PLAQUE = {'G175.jpg': (303, 789, 1.64), 'G177.jpg': (298, 9, 1.64)}


def paste_plaque(img, name, out_dir):
    if name not in PLAQUE or not os.path.exists(os.path.join(out_dir, 'G217.png')):
        return img
    x, y, s = PLAQUE[name]
    p = Image.open(os.path.join(out_dir, 'G217.png')).convert('RGBA')
    p = p.resize((round(p.width * s), round(p.height * s)), Image.LANCZOS)
    base = img.convert('RGBA')
    base.alpha_composite(p, (x, y))
    return base.convert('RGB')


def main(argv):
    if len(argv) < 3:
        print(__doc__)
        return 2
    src, tdir, out_dir = argv[:3]
    preview = argv[3] if len(argv) > 3 else None
    jn = names(tdir)
    for name in IMAGES:
        img = render(name, src, jn)
        if img is None:
            print('no labels:', name)
            continue
        img = paste_plaque(img, name, out_dir)
        p = os.path.join(out_dir, name)
        img.save(p, quality=92) if name.endswith('.jpg') else img.save(p)
        if preview:
            img.convert('RGB').save(os.path.join(preview, name[:-4] + '_jp.png'))
        print('wrote', name)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
