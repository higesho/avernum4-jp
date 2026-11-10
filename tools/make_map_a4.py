"""Redraw the place names on the Avernum 4 world map (G235.bmp) in Japanese.

usage: python -I make_map_a4.py ORIGINAL_DIR OUTPUT_DIR [PREVIEW_DIR]

Boxes are in image coordinates; "v" boxes hold a label rotated 90 degrees in the original and
are written top to bottom in Japanese. "|" breaks a label into lines.
"""
import os
import sys

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

sys.stdout.reconfigure(encoding='utf-8')
FONT = 'C:/Windows/Fonts/yumindb.ttf'
INK = (52, 36, 22)

LABELS = [
    ((352, 44, 419, 69), '修道院砦'),
    ((11, 63, 48, 185), '北西の坑道', 'v'),
    ((537, 118, 605, 132), 'ドレイコ砦'),
    ((143, 171, 192, 187), 'バルガ'),
    ((702, 169, 763, 183), 'フォルメロ'),
    ((92, 209, 178, 229), '深淵'),
    ((361, 210, 433, 224), 'グラインドストーン'),
    ((124, 248, 162, 264), '尖塔'),
    ((414, 312, 496, 327), 'ドランロン砦'),
    ((582, 311, 682, 346), '東の|回廊'),
    ((704, 340, 777, 355), 'ドゥヴノ砦'),
    ((576, 348, 616, 362), 'コトラ'),
    ((30, 374, 83, 402), '尖塔の|要塞'),
    ((716, 421, 759, 435), 'シルヴァー'),
    ((59, 451, 135, 467), 'サフラン砦'),
    ((233, 460, 316, 474), 'エメラルド砦'),
    ((25, 489, 47, 633), '未開の地', 'v'),
    ((130, 516, 175, 531), 'ブロスク'),
    ((603, 516, 698, 552), '蜂の巣|洞窟'),
    ((508, 527, 601, 541), 'サミュエルズ野営地'),
    ((118, 554, 190, 569), 'ダーモン'),
    ((223, 547, 309, 581), '大洞窟'),
    ((715, 568, 759, 582), 'メルティス'),
    ((341, 585, 430, 602), '城'),
    ((464, 631, 519, 645), 'アルマリア'),
    ((57, 650, 135, 664), 'リモート砦'),
    ((735, 680, 823, 694), '塔のコロニー'),
    ((220, 688, 317, 702), 'パトリックの塔'),
]


def fit(lines, w, h, start):
    size = start
    while size > 11:
        f = ImageFont.truetype(FONT, size)
        lh = size * 1.1
        if max(f.getlength(t) for t in lines) <= w * 1.3 and lh * len(lines) <= h + 4:
            return f, size, lh
        size -= 1
    return ImageFont.truetype(FONT, 11), 11, 12.1


def main(argv):
    src, out = argv[0], argv[1]
    preview = argv[2] if len(argv) > 2 else None
    im = Image.open(os.path.join(src, 'G235.bmp'))
    pal = im
    rgb = cv2.cvtColor(np.array(im.convert('RGB')), cv2.COLOR_RGB2BGR)
    a = rgb.astype(int)
    mask = np.zeros(rgb.shape[:2], np.uint8)
    for L in LABELS:
        x0, y0, x1, y1 = L[0]
        sub = a[y0:y1, x0:x1]
        hit = (sub.sum(2) < 330) & (sub[:, :, 0] < 120)       # dark brown letters
        mask[y0:y1, x0:x1] |= hit.astype(np.uint8) * 255
    mask = cv2.dilate(mask, np.ones((3, 3), np.uint8), iterations=2)
    rgb = cv2.inpaint(rgb, mask, 5, cv2.INPAINT_TELEA)
    img = Image.fromarray(cv2.cvtColor(rgb, cv2.COLOR_BGR2RGB))
    layer = Image.new('L', img.size, 0)
    d = ImageDraw.Draw(layer)
    for L in LABELS:
        (x0, y0, x1, y1), text = L[0], L[1]
        w, h = x1 - x0, y1 - y0
        if len(L) > 2 and L[2] == 'v':
            chars = list(text)
            size = min(w - 2, int(h / len(chars) / 1.05), 18)
            f = ImageFont.truetype(FONT, size)
            y = y0 + (h - size * 1.05 * len(chars)) / 2
            for ch in chars:
                d.text((x0 + (w - f.getlength(ch)) / 2, y), ch, font=f, fill=255)
                y += size * 1.05
            continue
        lines = text.split('|')
        f, size, lh = fit(lines, w, h, 14)
        y = y0 + (h - lh * len(lines)) / 2
        for t in lines:
            bb = f.getbbox(t)
            d.text((x0 + (w - f.getlength(t)) / 2, y - bb[1] + (size - (bb[3] - bb[1])) / 2), t, font=f, fill=255)
            y += lh
    ink = Image.new('RGB', img.size, INK)
    img = Image.composite(ink, img, layer)
    # back to the original palette (exact nearest colour)
    palarr = np.array(pal.getpalette()[:768], dtype=np.int32).reshape(-1, 3)
    used = sorted(set(np.unique(np.array(pal)).tolist()))
    cand = palarr[used]
    px = np.array(img, dtype=np.int32).reshape(-1, 3)
    cols, inv = np.unique(px, axis=0, return_inverse=True)
    idx = np.array(used)[((cols[:, None, :] - cand[None, :, :]) ** 2).sum(2).argmin(1)]
    res = Image.fromarray(idx[inv.reshape(-1)].reshape(img.size[1], img.size[0]).astype(np.uint8), 'P')
    res.putpalette(pal.getpalette())
    res.save(os.path.join(out, 'G235.bmp'))
    if preview:
        res.convert('RGB').save(os.path.join(preview, 'G235_jp.png'))
    print('wrote G235.bmp')


if __name__ == '__main__':
    main(sys.argv[1:])
