"""Redraw the English text in the Avernum UI images in Japanese.

usage:
    python -I make_images.py ORIGINAL_DIR OUTPUT_DIR [PREVIEW_DIR] [NAME ...]

ORIGINAL_DIR: the untouched images (_backup_original/Avernum Graphics Core).
Each image keeps its size, format and (for 8-bit BMPs) its palette; only the boxes
listed in SPEC are erased and redrawn, so clickable areas stay where they were.
"""
import os
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageChops

FONTS = 'C:/Windows/Fonts/'
MINCHO_B = FONTS + 'yumindb.ttf'       # Yu Mincho Demibold
GOTHIC_B = FONTS + 'YuGothB.ttc'       # Yu Gothic Bold
UD_GOTHIC_B = FONTS + 'BIZ-UDGothicB.ttc'

INK = (24, 16, 12)          # black-brown text of the table images
RED_INK = (92, 20, 16)      # dark red of the tutorial images
STONE_INK = (40, 32, 30)    # stats screen labels

# erase: 'clear' (transparent), 'fill' (median border colour), 'inpaint' (stone texture)
# text entries: (box, lines, font, max_size, colour, align)
from spec_a4 import SPEC, PAGES, PAGE_BOX, PAGE_INK, COPY, PARCH, MINCHO_B as PAGE_FONT  # noqa: E402


def fit_font(path, lines, box, max_size):
    w, h = box[2] - box[0], box[3] - box[1]
    for size in range(max_size, 7, -1):
        f = ImageFont.truetype(path, size)
        widths = [f.getbbox(t)[2] for t in lines]
        lh = size + max(1, size // 8)
        if max(widths) <= w and lh * len(lines) - (lh - size) <= h + 2:
            return f, size, lh
    f = ImageFont.truetype(path, 8)
    return f, 8, 9


def text_layer(size, box, lines, font_path, max_size, align):
    """Alpha mask (L) of the text placed in box."""
    f, s, lh = fit_font(font_path, lines, box, max_size)
    mask = Image.new('L', size, 0)
    d = ImageDraw.Draw(mask)
    total = lh * len(lines) - (lh - s)
    y = box[1] + (box[3] - box[1] - total) / 2
    for t in lines:
        bb = f.getbbox(t)
        tw = bb[2]
        if align == 'center':
            x = box[0] + (box[2] - box[0] - tw) / 2
        elif align == 'right':
            x = box[2] - tw
        else:
            x = box[0]
        d.text((x, y - bb[1] + (s - (bb[3] - bb[1])) / 2), t, font=f, fill=255)
        y += lh
    return mask


def border_colour(arr, box):
    x0, y0, x1, y1 = box
    edge = np.concatenate([arr[y0, x0:x1], arr[y1, x0:x1], arr[y0:y1, x0], arr[y0:y1, x1]])
    if (edge[:, 3] < 128).mean() > 0.5:      # transparent background
        return (0, 0, 0, 0)
    edge = edge[edge[:, 3] >= 128]
    return tuple(int(v) for v in np.median(edge, axis=0))


def gradient_fill(size, mask, top, bottom, box):
    w, h = size
    grad = Image.new('RGB', size)
    gd = ImageDraw.Draw(grad)
    y0, y1 = box[1], box[3]
    for y in range(h):
        t = min(1, max(0, (y - y0) / max(1, y1 - y0)))
        c = tuple(int(top[i] + (bottom[i] - top[i]) * t) for i in range(3))
        gd.line([(0, y), (w, y)], fill=c)
    out = Image.new('RGBA', size, (0, 0, 0, 0))
    out.paste(grad, (0, 0), mask)
    return out


def to_palette(rgb, pal_img):
    """Exact nearest-colour mapping onto the original palette (Pillow's quantize is approximate and
    can map pure white, the transparent colour of Avernum 4 pictures, to another entry)."""
    pal = np.array(pal_img.getpalette()[:768], dtype=np.int32).reshape(-1, 3)
    used = sorted(set(np.unique(np.array(pal_img)).tolist()))   # prefer entries the original uses
    cand = pal[used]
    a = np.array(rgb, dtype=np.int32).reshape(-1, 3)
    cols, inv = np.unique(a, axis=0, return_inverse=True)
    d = ((cols[:, None, :] - cand[None, :, :]) ** 2).sum(2)
    idx = np.array(used)[d.argmin(1)]
    out = Image.fromarray(idx[inv.reshape(-1)].reshape(rgb.size[1], rgb.size[0]).astype(np.uint8), 'P')
    out.putpalette(pal_img.getpalette())
    return out


def render(name, src_dir):
    spec = SPEC[name]
    src = Image.open(os.path.join(src_dir, name))
    palette_img = src if src.mode == 'P' else None
    img = src.convert('RGBA')
    size = img.size
    arr = np.array(img)

    if spec['erase'] == 'clear-all':
        img = Image.new('RGBA', size, (0, 0, 0, 0))
    elif spec['erase'] == 'white':            # Avernum 4: pure white is the transparent colour
        img = Image.new('RGBA', size, (255, 255, 255, 255))
    elif spec['erase'] == 'fill':
        pad = spec.get('pad', 0)
        out_arr = arr.copy()
        for t in spec['texts']:
            x0, y0, x1, y1 = t[0]
            x0, y0 = max(0, x0 - pad), max(0, y0 - pad)
            x1, y1 = min(size[0] - 1, x1 + pad), min(size[1] - 1, y1 + pad)
            c = spec.get('fill_colour') or border_colour(arr, (x0, y0, x1, y1))
            blk = arr[y0:y1 + 1, x0:x1 + 1]
            sub = (blk[:, :, :3].astype(int).sum(axis=2) < 300) & (blk[:, :, 3] > 128)
            grid_rows = sub.mean(axis=1) > 0.7     # table rules: keep them
            grid_cols = sub.mean(axis=0) > 0.7
            if spec.get('no_grid'):
                grid_rows[:] = False
                grid_cols[:] = False
            for yy in range(y0, y1 + 1):
                if grid_rows[yy - y0]:
                    continue
                for xx in range(x0, x1 + 1):
                    if not grid_cols[xx - x0]:
                        out_arr[yy, xx] = c
        img = Image.fromarray(out_arr, 'RGBA')
    elif spec['erase'] == 'inpaint':
        alpha = np.array(img)[:, :, 3]
        rgb = cv2.cvtColor(np.array(img.convert('RGB')), cv2.COLOR_RGB2BGR)
        m = np.zeros(rgb.shape[:2], np.uint8)
        gray = cv2.cvtColor(rgb, cv2.COLOR_BGR2GRAY)
        for t in spec['texts']:
            x0, y0, x1, y1 = t[0]
            light = len(t) > 6 and t[6] in ('outline', 'light')
            sub = gray[y0:y1, x0:x1]
            if len(t) > 6 and t[6] == 'light':      # light text on a dark button
                hit = sub > 105
            elif len(t) > 7 and t[7] == 'orange':  # orange letters (Avernum 4 TRAIN / Buy buttons)
                rgbs = rgb[y0:y1, x0:x1].astype(int)
                hit = (rgbs[:, :, 2] > 150) & (rgbs[:, :, 0] < 140)   # BGR: red high, blue low
            elif len(t) > 7 and t[7] == 'brown':   # brown lettering on parchment (Job Board)
                rgbs = rgb[y0:y1, x0:x1].astype(int)
                hit = (rgbs[:, :, 2] - rgbs[:, :, 0] > 24) | (rgbs.sum(2) < 400)
            elif len(t) > 7 and t[7] == 'bw':      # white letters with a black edge over a picture
                rgbs = rgb[y0:y1, x0:x1].astype(int)
                hit = (rgbs.min(2) > 200) | (rgbs.max(2) < 50)
            else:
                hit = (sub > 200) | (sub < 60) if light else (sub < 120)
            m[y0:y1, x0:x1] |= hit.astype(np.uint8) * 255
        m = cv2.dilate(m, np.ones((3, 3), np.uint8), iterations=1)
        rgb = cv2.inpaint(rgb, m, 4, cv2.INPAINT_TELEA)
        out = np.dstack([cv2.cvtColor(rgb, cv2.COLOR_BGR2RGB), alpha])
        img = Image.fromarray(out.astype(np.uint8), 'RGBA')

    if spec.get('bg_from'):           # repaint with a texture taken from another picture
        name2, (bx, by) = spec['bg_from']
        tex = Image.open(os.path.join(src_dir, name2)).convert('RGBA').crop((bx, by, bx + size[0], by + size[1]))
        img = tex
    for (x0, y0, x1, y1), c in spec.get('fill_rects', []):   # plain panels: repaint the whole area
        ImageDraw.Draw(img).rectangle([x0, y0, x1 - 1, y1 - 1], fill=c)
    for x0, y0, x1, y1 in spec.get('clear_rects', []):
        ImageDraw.Draw(img).rectangle([x0, y0, x1 - 1, y1 - 1], fill=(0, 0, 0, 0))
    style = spec.get('style')
    key = spec.get('key_white')
    keyed = np.zeros((size[1], size[0]), bool)
    for t in spec['texts']:
        box, lines, font_path, max_size, colour, align = t[:6]
        mask = text_layer(size, box, lines, font_path, max_size, align)
        if key:
            # Avernum 4 shows these over parchment with pure white as the transparent colour:
            # antialias the letters against parchment, and put white back around them afterwards.
            reg = np.array(mask.filter(ImageFilter.MaxFilter(5))) > 0
            arr = np.array(img)
            wh = (arr[:, :, 0] == 255) & (arr[:, :, 1] == 255) & (arr[:, :, 2] == 255)
            arr[reg & wh] = spec.get('parch', PARCH) + (255,)
            img = Image.fromarray(arr, 'RGBA')
            keyed |= reg
        if len(t) > 6 and t[6] == 'light':
            # white bold letters, like the English panel titles / tabs. No dark edge: the game
            # draws this sheet scaled down (about 0.88 at 1024x768) and a 1-pixel edge breaks
            # up into dots inside the letters.
            bold = ImageChops.lighter(mask, ImageChops.offset(mask, 1, 0))
            img.alpha_composite(Image.composite(Image.new('RGBA', size, colour + (255,)),
                                                Image.new('RGBA', size, (0, 0, 0, 0)), bold))
            continue
        if len(t) > 6 and t[6] == 'outline':
            edge = mask.filter(ImageFilter.MaxFilter(3))
            img.alpha_composite(Image.composite(Image.new('RGBA', size, (0, 0, 0, 255)),
                                                Image.new('RGBA', size, (0, 0, 0, 0)), edge))
            img.alpha_composite(Image.composite(Image.new('RGBA', size, colour + (255,)),
                                                Image.new('RGBA', size, (0, 0, 0, 0)), mask))
            continue
        if style in ('a4button', 'a4menu'):
            if spec.get('bold'):
                mask = ImageChops.lighter(mask, ImageChops.offset(mask, 1, 0))
            # a4button: brown letters with a light halo (party buttons, menus)
            # a4menu:   light letters with a dark teal edge (title menu)
            edge = mask.filter(ImageFilter.MaxFilter(3))
            img.alpha_composite(Image.composite(Image.new('RGBA', size, spec['edge'] + (255,)),
                                                Image.new('RGBA', size, (0, 0, 0, 0)), edge))
            img.alpha_composite(gradient_fill(size, mask, spec['top'], spec['bottom'], box))
            continue
        if style == 'a4head':
            # Avernum 4 headings: brown letters with a dark brown edge
            edge = mask.filter(ImageFilter.MaxFilter(3))
            img.alpha_composite(Image.composite(Image.new('RGBA', size, spec.get('edge', (86, 50, 26)) + (255,)),
                                                Image.new('RGBA', size, (0, 0, 0, 0)), edge))
            img.alpha_composite(gradient_fill(size, mask, spec.get('top', (214, 168, 124)), spec.get('bottom', (138, 88, 52)), box))
        elif style == 'gold':
            # dark outline + shadow, then gold gradient (colours sampled from the original menu)
            shadow = mask.filter(ImageFilter.MaxFilter(5)).filter(ImageFilter.GaussianBlur(1.5))
            img.alpha_composite(Image.composite(Image.new('RGBA', size, (20, 12, 4, 230)),
                                                Image.new('RGBA', size, (0, 0, 0, 0)), shadow.point(lambda v: min(255, v * 2))),
                                (1, 2))
            edge = mask.filter(ImageFilter.MaxFilter(3))
            img.alpha_composite(Image.composite(Image.new('RGBA', size, (58, 40, 18, 255)),
                                                Image.new('RGBA', size, (0, 0, 0, 0)), edge))
            img.alpha_composite(gradient_fill(size, mask, (250, 236, 190), (176, 136, 70), box))
        elif style == 'blue':
            img.alpha_composite(gradient_fill(size, mask, (110, 120, 200), (40, 44, 110), box))
        elif style == 'olive':
            # "The Adventure Continues" of Avernum 3: khaki gradient with a dark edge
            edge = mask.filter(ImageFilter.MaxFilter(3))
            img.alpha_composite(Image.composite(Image.new('RGBA', size, (43, 33, 16, 255)),
                                                Image.new('RGBA', size, (0, 0, 0, 0)), edge))
            img.alpha_composite(gradient_fill(size, mask, (176, 160, 112), (96, 84, 44), box))
        elif style == 'outlined':
            # light letters with a dark outline (Avernum 3 title menu)
            edge = mask.filter(ImageFilter.MaxFilter(5))
            img.alpha_composite(Image.composite(Image.new('RGBA', size, spec['outline_colour'] + (255,)),
                                                Image.new('RGBA', size, (0, 0, 0, 0)), edge))
            img.alpha_composite(Image.composite(Image.new('RGBA', size, spec['fill'] + (255,)),
                                                Image.new('RGBA', size, (0, 0, 0, 0)), mask))
        else:
            layer = Image.new('RGBA', size, colour + (255,))
            img.alpha_composite(Image.composite(layer, Image.new('RGBA', size, (0, 0, 0, 0)), mask))

    if key:
        arr = np.array(img)
        pc = spec.get('parch', PARCH)
        p = (arr[:, :, 0] == pc[0]) & (arr[:, :, 1] == pc[1]) & (arr[:, :, 2] == pc[2])
        arr[keyed & p] = (255, 255, 255, 255)
        img = Image.fromarray(arr, 'RGBA')
    if palette_img is not None:
        out = to_palette(img.convert('RGB'), palette_img)
    elif name.lower().endswith('.jpg'):
        out = img.convert('RGB')
    else:
        out = img
    return out


NO_LINE_START = set('、。，．・：；？！ー―…‥）」』】〉》〕］｝ぁぃぅぇぉっゃゅょゎァィゥェォッャュョヮヵヶ')


def wrap_ja(text, font, width):
    """Break Japanese text into lines that fit width (simple kinsoku: no line starts with
    closing punctuation or a small kana)."""
    lines, cur = [], ''
    for ch in text:
        if font.getlength(cur + ch) <= width or not cur:
            cur += ch
            continue
        if ch in NO_LINE_START:      # pull the last char down with it
            lines.append(cur[:-1])
            cur = cur[-1] + ch
        else:
            lines.append(cur)
            cur = ch
    if cur:
        lines.append(cur)
    return lines


def render_page(name, src_dir):
    """Chapter page of the introduction book: inpaint the printed text, then lay out the
    Japanese part number, title and paragraphs in the same area."""
    part, title, paras = PAGES[name]
    img = Image.open(os.path.join(src_dir, name)).convert('RGB')
    x0, y0, x1, y1 = PAGE_BOX
    bgr = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    m = np.zeros(gray.shape, np.uint8)
    m[y0:y1, x0:x1] = (gray[y0:y1, x0:x1] < 150).astype(np.uint8) * 255
    m = cv2.dilate(m, np.ones((3, 3), np.uint8), iterations=2)
    bgr = cv2.inpaint(bgr, m, 5, cv2.INPAINT_TELEA)
    img = Image.fromarray(cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB))
    d = ImageDraw.Draw(img)
    fpart = ImageFont.truetype(PAGE_FONT, 22)
    ftitle = ImageFont.truetype(PAGE_FONT, 40)
    y = y0 + 4
    d.text((x0 + 2, y), part, font=fpart, fill=PAGE_INK)
    y += 30
    d.text((x0, y), title, font=ftitle, fill=PAGE_INK)
    y += 62
    width = x1 - x0
    for size in range(17, 11, -1):   # the largest body size whose text fits the page
        fbody = ImageFont.truetype(PAGE_FONT, size)
        lh = int(size * 1.55)
        wrapped = [wrap_ja(p, fbody, width) for p in paras]
        total = sum(len(w) for w in wrapped) * lh + (len(paras) - 1) * int(lh * 0.8)
        if y + total <= y1:
            break
    for w in wrapped:
        for line in w:
            d.text((x0, y), line, font=fbody, fill=PAGE_INK)
            y += lh
        y += int(lh * 0.8)
    return img


def copy_translated(name, src, out_dir):
    """Copy the Japanese image of another mod; convert when the file format differs."""
    dst = os.path.join(out_dir, name)
    if os.path.splitext(src)[1].lower() == os.path.splitext(name)[1].lower():
        shutil.copyfile(src, dst)
    else:
        Image.open(src).convert('RGBA').save(dst)


def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 2
    src_dir, out_dir = argv[0], argv[1]
    preview = argv[2] if len(argv) > 2 and not argv[2].startswith('G') else None
    names = [a for a in argv[2:] if a.startswith('G')] or (list(SPEC) + list(PAGES) + list(COPY))
    for name in names:
        if name in COPY:
            copy_translated(name, COPY[name], out_dir)
            print('copied', name)
            continue
        out = render_page(name, src_dir) if name in PAGES else render(name, src_dir)
        p = os.path.join(out_dir, name)
        if name.lower().endswith('.jpg'):
            out.save(p, quality=95)
        else:
            out.save(p)
        if preview:
            pv = out.convert('RGBA')
            bg = Image.new('RGBA', pv.size, (90, 90, 90, 255))
            bg.alpha_composite(pv)
            bg.convert('RGB').save(os.path.join(preview, name.rsplit('.', 1)[0] + '_jp.png'))
        print('wrote', p)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
