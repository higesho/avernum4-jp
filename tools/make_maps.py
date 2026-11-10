"""Redraw the place names on the world map images in Japanese.

usage:
    python -I make_maps.py ORIGINAL_DIR OUTPUT_DIR [PREVIEW_DIR]

G200.jpg is the in-game world map (1024x768). G176.jpg / G177.jpg are the west and east
halves of the same map at ~1.30x (affine transforms below were measured with ORB
feature matching). Labels are given in G200 coordinates and mapped to the others.
Names follow the game's translations (glossary / scenario data).
"""
import os
import sys

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

FONT = 'C:/Windows/Fonts/HGRGY.TTC'     # HG Gyoshotai (brush style, like the hand-lettered map)
INK = (28, 24, 44)

# (box in G200 coordinates, Japanese, vertical?)
LABELS = [
    ((157, 42, 207, 75), '灼熱の地', False), ((38, 106, 77, 125), '溶岩', False),
    ((37, 147, 80, 165), '道', False), ((39, 182, 80, 200), '水域', False),
    ((44, 235, 74, 253), '砦', False), ((34, 284, 84, 304), '急流', False),
    ((284, 199, 337, 217), 'バルガ', False), ((247, 224, 288, 260), '深淵', False),
    ((358, 280, 419, 312), '滝の巣窟', False), ((256, 338, 297, 359), 'スパイア', False),
    ((485, 366, 537, 389), '陸路', False), ((733, 80, 803, 99), 'ドラコ砦', False),
    ((892, 163, 946, 183), 'フォルメロ', False, (858, 163, 926, 183)), ((612, 316, 695, 337), 'ドランロン砦', False),
    ((700, 328, 776, 380), '東の回廊', False), ((784, 362, 856, 383), 'ドゥヴノ砦', False),
    ((928, 95, 996, 412), 'アヴァーナム', True), ((222, 410, 291, 431), 'スパイア砦', False),
    ((236, 510, 319, 531), 'サフラン砦', False), ((312, 546, 349, 564), 'ブロスク', False, (296, 548, 346, 566)),
    ((368, 537, 451, 557), 'エメラルド砦', False, (376, 537, 462, 557)), ((240, 588, 301, 608), 'ダーモン', False),
    ((340, 598, 451, 627), '大洞窟', False), ((465, 620, 536, 643), '城', False),
    ((167, 654, 246, 676), 'リモート砦', False), ((155, 698, 223, 729), '未踏の|トンネル', False),
    ((310, 712, 403, 731), 'パトリックの塔', False), ((668, 404, 742, 423), 'コトラの廃墟', False),
    ((806, 433, 846, 450), 'シルヴァー', False), ((385, 58, 506, 138), '占領|地域', False),
    ((680, 463, 712, 497), '暗い湖', False), ((697, 552, 758, 581), '蜂の巣', False),
    ((805, 582, 846, 601), 'メルティス', False), ((543, 668, 601, 687), 'アルマリア', False),
    ((888, 676, 981, 695), '魔術師の塔', False),
]
# G200 -> image affine (scale, tx, ty)
MAPS = {'G200.jpg': (1.0, 0.0, 0.0), 'G176.jpg': (1.3230, -1.4, -1.8), 'G177.jpg': (1.3114, -663.7, 11.9)}


def tbox(box, tr, w, h):
    s, tx, ty = tr
    x0, y0, x1, y1 = box
    b = [x0 * s + tx, y0 * s + ty, x1 * s + tx, y1 * s + ty]
    if b[2] < 0 or b[0] > w or b[3] < 0 or b[1] > h:
        return None
    return [int(round(v)) for v in b]


# Labels with big or dense lettering, where the glow test misses part of the letters:
# every dark pixel in the box is erased.
STRONG = {'占領|地域', '滝の巣窟', '暗い湖', 'リモート砦'}


def erase(rgb, boxes, margin=8, strong=()):
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    glow = cv2.blur(gray, (15, 15))
    mask = np.zeros(gray.shape, np.uint8)
    H, W = gray.shape
    for i, (x0, y0, x1, y1) in enumerate(boxes):
        x0, y0, x1, y1 = max(0, x0 - margin), max(0, y0 - margin // 2), min(W, x1 + margin), min(H, y1 + margin // 2)
        g, gl = gray[y0:y1, x0:x1], glow[y0:y1, x0:x1]
        if i in strong:
            mask[y0:y1, x0:x1] |= ((g < 150).astype(np.uint8) * 255)
            continue
        mask[y0:y1, x0:x1] |= (((g < 145) & (gl > 135)).astype(np.uint8) * 255)
    mask = cv2.dilate(mask, np.ones((3, 3), np.uint8))
    return cv2.inpaint(rgb, mask, 5, cv2.INPAINT_TELEA)


def draw_label(img, box, text, vertical, scale):
    x0, y0, x1, y1 = box
    bw, bh = x1 - x0, y1 - y0
    lines = text.split('|')
    layer = Image.new('L', img.size, 0)
    d = ImageDraw.Draw(layer)
    if vertical:
        n = len(text)
        size = int(min(bw * 0.85, bh / n * 0.95))
        f = ImageFont.truetype(FONT, size)
        cy = y0 + (bh - size * n * 1.0) / 2
        for ch in text:
            chw = f.getbbox(ch)[2]
            if ch in 'ー':   # rotate the long-vowel mark for vertical writing
                tmp = Image.new('L', (size * 2, size * 2), 0)
                ImageDraw.Draw(tmp).text((size // 2, size // 2), ch, font=f, fill=255)
                tmp = tmp.rotate(-90)
                layer.paste(255, (int(x0 + (bw - size) / 2 - size // 2), int(cy - size // 2)), tmp)
            else:
                d.text((x0 + (bw - chw) / 2, cy), ch, font=f, fill=255)
            cy += size
    else:
        max_w = bw * 1.3 + 4 * scale          # Japanese names may be a little wider than the English
        size = int(min(bh / len(lines) * 0.95, 26 * scale))
        while size > 9:
            f = ImageFont.truetype(FONT, size)
            if max(f.getbbox(t)[2] for t in lines) <= max_w:
                break
            size -= 1
        f = ImageFont.truetype(FONT, size)
        total = size * len(lines) * 1.05
        cy = y0 + (bh - total) / 2
        for t in lines:
            tw = f.getbbox(t)[2]
            d.text((x0 + (bw - tw) / 2, cy), t, font=f, fill=255)
            cy += size * 1.05
    glow = layer.filter(ImageFilter.MaxFilter(7)).filter(ImageFilter.GaussianBlur(3 * scale))
    white = Image.new('RGB', img.size, (250, 246, 232))
    img.paste(white, (0, 0), glow.point(lambda v: min(255, int(v * 1.1))))
    img.paste(Image.new('RGB', img.size, INK), (0, 0), layer)


def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 2
    src, out = argv[0], argv[1]
    preview = argv[2] if len(argv) > 2 else None
    for name, tr in MAPS.items():
        im = Image.open(os.path.join(src, name)).convert('RGB')
        w, h = im.size
        placed = []
        for lab in LABELS:
            b, t, v = lab[:3]
            eb = tbox(b, tr, w, h)
            if eb:
                placed.append((eb, tbox(lab[3], tr, w, h) if len(lab) > 3 else eb, t, v))
        rgb = erase(np.array(im), [p[0] for p in placed], int(round(8 * tr[0])),
                    {i for i, p in enumerate(placed) if p[2] in STRONG})
        img = Image.fromarray(rgb)
        for eb, db, t, v in placed:
            draw_label(img, db, t, v, tr[0])
        img.save(os.path.join(out, name), quality=95)
        if preview:
            img.save(os.path.join(preview, name[:-4] + '_jp.png'))
        print('wrote', name, len(placed), 'labels')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
