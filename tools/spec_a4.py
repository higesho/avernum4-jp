"""Boxes and texts of the Avernum 4 pictures with English text (used by make_images.py).

Coordinates were measured on the original pictures (_backup_original/Data or orig_tree/Data).
Most of these BMPs are 8-bit with pure white as the transparent colour; they are drawn over
parchment, so letters are antialiased against PARCH and the white around them is kept
("key_white").
"""
from PIL import Image

FONTS = 'C:/Windows/Fonts/'
MINCHO_B = FONTS + 'yumindb.ttf'       # Yu Mincho Demibold
GOTHIC_B = FONTS + 'YuGothB.ttc'       # Yu Gothic Bold
GOTHIC = FONTS + 'YuGothM.ttc'         # Yu Gothic Medium

PARCH = (242, 237, 230)    # parchment behind the pictures
INK = (0, 0, 0)            # help panels: black text
TITLE_INK = (44, 0, 0)     # help panel titles: very dark red-brown

COPY = {}
PAGES = {}
PAGE_BOX = (0, 0, 0, 0)
PAGE_INK = (0, 0, 0)

SRC = None   # set by make_images (orig dir) when needed


def _size(name):
    import os
    for d in ('orig_tree/Data', '../_backup_original/Data', '../Data'):
        p = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', d, name)
        if os.path.exists(p):
            return Image.open(p).size
    raise FileNotFoundError(name)


def heading(name, text, pad=1, style=None):
    w, h = _size(name)
    spec = {'erase': 'white', 'key_white': True, 'style': 'a4head',
            'texts': [((pad, pad, w - pad - 1, h - pad - 1), [text], MINCHO_B, h - 3, None, 'left')],
            'top': (226, 184, 140), 'bottom': (150, 98, 58)}
    if style:
        spec.update(style)
    return spec


SPEC = {
    # ------------------------------------------------ headings (brown lettering)
    'G150.bmp': heading('G150.bmp', 'パーティーの編成'),
    'G151.bmp': heading('G151.bmp', '新しいキャラクター'),
    'G152.bmp': heading('G152.bmp', '能力値'),
    'G153.bmp': heading('G153.bmp', '呪文・能力'),
    'G155.bmp': heading('G155.bmp', 'ゲームをセーブ'),
    'G156.bmp': heading('G156.bmp', 'セーブデータのロード'),
    'G159.bmp': heading('G159.bmp', '記録'),
    'G160.BMP': heading('G160.BMP', 'アヴァーナム4 操作説明'),
    'G161.bmp': heading('G161.bmp', '読み込み中……', pad=6),
    'G162.bmp': heading('G162.bmp', 'パーティーの作成'),
    'G164.bmp': heading('G164.bmp', '製品登録'),
    'G178.bmp': heading('G178.bmp', 'ゲーム設定'),
    'G184.bmp': heading('G184.bmp', '転移門の使用'),
}

# ------------------------------------------------ buttons and menus (brown lettering on white rows)
BUTTON = {'style': 'a4button', 'edge': (236, 224, 206), 'top': (150, 100, 62), 'bottom': (92, 58, 32)}


def rows(texts, x0, x1, y0, step, align='left', size=20, skip=()):
    out, fills = [], []
    k = 0
    for i, t in enumerate(texts):
        y = y0 + i * step
        fills.append(((x0, y + 1, x1, y + step), (255, 255, 255, 255)))
        if t:
            out.append(((x0 + 2, y + 2, x1 - 2, y + step - 1), [t], MINCHO_B, size, None, align))
    return out, fills


_t202, _f202 = rows(['職業の変更', '名前の変更', '能力値の編集', '特性の編集', '削除', '新しいキャラクター',
                     '難易度：イージー', '難易度：ノーマル', '難易度：ハード', '難易度：トーメント'], 1, 223, 0, 26, size=20)
_t203l, _f203l = rows(['兵士', '狂戦士', '司祭', '妖術師', 'ならず者', '射手', '反逆者', '田舎魔術師', 'シャーマン',
                       'カスタム'], 1, 223, 0, 24, align='center', size=19)
_t203r, _f203r = rows(['ゲームに戻る', '', 'ゲームをセーブ', 'セーブデータのロード', '', '設定', 'アヴァーナム4について', '',
                       'タイトル画面に戻る', '終了'], 224, 446, 0, 24, align='center', size=19)

# title menu: light letters with a dark teal edge; only the text rows are repainted (the frame stays)
_menu = [(34, 60, '新しいゲーム'), (76, 103, 'ゲームをロード'), (117, 144, '購入方法'), (160, 193, '製品登録'),
         (202, 228, '操作説明'), (244, 276, 'ゲーム設定'), (286, 312, 'クレジット'), (328, 360, '終了')]

SPEC.update({
    'G202.bmp': dict(BUTTON, erase='none', key_white=True, fill_rects=_f202, texts=_t202),
    'G203.bmp': dict(BUTTON, erase='none', key_white=True, fill_rects=_f203l + _f203r, texts=_t203l + _t203r),
    'G158.bmp': {'erase': 'none', 'key_white': True, 'style': 'a4menu', 'parch': (21, 76, 95),
                 'edge': (8, 36, 46), 'top': (222, 244, 228), 'bottom': (178, 218, 192), 'bold': 1,
                 'fill_rects': [((24, y0 - 3, 336, y1 + 3), (255, 255, 255, 255)) for y0, y1, _ in _menu],
                 'texts': [((26, y0 - 2, 334, y1 + 2), [t], MINCHO_B, 30, None, 'center') for y0, y1, t in _menu]},
})

# ------------------------------------------------ help panels (469 x 178: text on white, picture at the right)
# Line boxes were found from the dark-ink rows of the originals (16 px line pitch).
HELP_INK = (44, 0, 0)


def panel(title_box, title, blocks, body=13):
    texts = [(title_box, [title], MINCHO_B, 21, HELP_INK, 'left')]
    for b in blocks:
        box, lines = b[0], b[1]
        size = b[2] if len(b) > 2 else body
        texts.append((box, lines, GOTHIC_B, size, HELP_INK, 'left'))
    return {'erase': 'fill', 'fill_colour': (255, 255, 255, 255), 'key_white': True, 'no_grid': True, 'texts': texts}


SPEC.update({
    'G185.bmp': panel((2, 4, 215, 28), 'クエストを見る', [
        ((2, 37, 212, 84), ['受け取ったクエストを', '見るには……', '1. 日誌ボタンを押す。']),
        ((160, 100, 296, 130), ['2. 上の「現在のクエスト」', 'を選ぶ。'])]),
    'G187.bmp': panel((2, 4, 150, 26), '移動のしかた', [
        ((2, 49, 262, 66), ['行きたい場所をクリックする。']),
        ((2, 89, 262, 122), ['テンキーや矢印キーでも', '移動できる。'])]),
    'G190.bmp': panel((2, 4, 150, 28), 'アイテムを拾う', [
        ((2, 49, 294, 114), ['1. アイテムをクリックして拾う。', '2. 装備するにはキャラクターをクリック。',
                             '3. 背負い袋に入れるには、', '　空いているマスをクリック。'])]),
    'G191.bmp': panel((2, 4, 296, 28), 'クイック使用欄・アイテムの使用', [
        ((2, 49, 296, 95), ['ここに置くとクイック使用に設定できる。', 'メイン画面でクリックすると', '使える。']),
        ((2, 113, 196, 143), ['アイテムを使うには……', '1. 使用ボタンをクリック：'])]),
    'G192.bmp': panel((2, 4, 212, 28), '呪文の唱え方', [
        ((2, 37, 205, 70), ['1. 魔術か祈祷の', 'ボタンを押す。']),
        ((156, 68, 318, 149), ['2. 唱えたい呪文を', 'クリックする。', '（呪文にカーソルを', '合わせると説明が', '出る。）'])]),
    'G193.bmp': panel((2, 4, 150, 28), '物を使う', [
        ((2, 49, 272, 98), ['扉をクリックすると開く。', '箱をクリックすると中を見る。', 'レバーなら引く、など。'])]),
    'G196.bmp': panel((2, 4, 150, 28), '戦い方', [
        ((2, 37, 210, 69), ['1. 既定の攻撃を選ぶ', '（近接か飛び道具）。']),
        ((216, 72, 338, 102), ['2. 敵をクリックして', '攻撃する。'])]),
    'G210.bmp': panel((2, 4, 200, 28), 'ゲームのセーブ', [
        ((2, 37, 188, 52), ['1. ディスクボタンを押す。']),
        ((146, 69, 298, 115), ['3. 枠を選び、名前を', '入れて OK ボタンを', '押す。']),
        ((2, 132, 158, 148), ['2. 「セーブ」を選ぶ。'])]),
    'G212.bmp': panel((2, 4, 216, 28), '新しいゲームの始め方', [
        ((2, 29, 170, 62), ['手軽に新しいゲームを', '始めるには……']),
        ((2, 89, 232, 104), ['1. 新しい職業を選ぶ']), ((2, 105, 136, 120), ['（必要なら）。']),
        ((2, 121, 124, 136), ['2. 難易度を設定。']), ((2, 137, 196, 152), ['3. チェックボタンを押す。'])]),
    'G213.bmp': panel((2, 4, 216, 28), 'キャラクターの訓練', [
        ((2, 37, 194, 52), ['1. 訓練ボタンを押す。']),
        ((140, 69, 298, 150), ['2. 技能の横の＋ボタン', 'を押して上げる。', '技能の名前をクリック', 'すると説明が出る。'])]),
    'G214.bmp': panel((2, 4, 250, 28), 'アイテムを置く・使う', [
        ((2, 49, 284, 98), ['アイテムを置くには……', '1. クリックして持ち上げる。', '2. 地面の欄をクリックして置く。']),
        ((2, 113, 196, 143), ['アイテムを使うには……', '1. 使用ボタンをクリック：'])]),
    'G217.bmp': panel((2, 2, 210, 24), 'クイック呪文ボタン', [
        ((2, 72, 372, 137), ['クイック呪文ボタンを設定するには……', '1. 設定したいクイック呪文ボタンを押す。',
                             '2. 知っている呪文の一覧が出るので、', '　1つ選ぶ。'])]),
})

# ------------------------------------------------ legends and small help pictures
LEG_INK = (62, 22, 22)


def labels(items, size=12, font=None, ink=LEG_INK, align='left'):
    return [(box, lines, font or GOTHIC_B, size, ink, align) for box, lines in items]


def white(texts):
    return {'erase': 'fill', 'fill_colour': (255, 255, 255, 255), 'key_white': True, 'no_grid': True, 'texts': texts}


_g166 = []
for (x0, x1), names in zip([(18, 79), (97, 156), (174, 264), (282, 364)],
                           [['呪い', '祝福', '減速', '加速', '毒'], ['気絶', '魅了', '酸', '恐慌', '盾'],
                            ['精神の盾', '凍結', '持久の盾', '持久の鎧', '防護'], ['抵抗力', '強化', '分厚い皮膚', '朦朧', '無敵']]):
    for k, n in enumerate(names):
        y = 28 + k * 16
        _g166.append(((x0, y, x1, y + 15), [n]))

SPEC.update({
    'G166.bmp': white([((100, 6, 260, 26), ['魔法の効果'], MINCHO_B, 18, HELP_INK, 'center')] + labels(_g166, 13)),
    'G167.bmp': white(labels([((234, 35 + k * 17, 383, 50 + k * 17), [t]) for k, t in enumerate(
        ['A - 地形', 'B - パーティー一覧', 'C - 自動地図', 'D - ゲームボタン', 'E - サイドボタン'])], 12)),
    'G168.bmp': white(labels([((82, 10, 180, 46), ['既定の攻撃', '（sで切替）']), ((218, 12, 292, 44), ['拾う（g）']),
                              ((317, 10, 386, 46), ['クイック呪文', '（F5〜F8）']), ((82, 48, 180, 84), ['魔術・祈祷', '（m / p）']),
                              ((220, 58, 285, 78), ['攻撃']), ((317, 48, 386, 84), ['クイック使用', '（F9〜F12）'])], 13)),
    'G169.bmp': white([((2, 2, 192, 19), ['既定の攻撃ボタン：'], MINCHO_B, 16, HELP_INK, 'left')] +
                      labels([((40, 86, 94, 101), ['近接']), ((96, 86, 160, 101), ['飛び道具'])], 13, align='center')),
    'G188.bmp': white(labels([((28, 12, 80, 46), ['戦闘', '終了']), ((122, 12, 182, 46), ['日誌', 'クエスト']),
                              ((214, 12, 251, 46), ['編成']), ((280, 12, 318, 46), ['世界', '地図']),
                              ((28, 62, 80, 96), ['戦闘', '開始']), ((110, 62, 184, 82), ['操作説明']),
                              ((214, 62, 300, 96), ['ゲーム', 'メニュー'])], 14, align='center')),
    'G215.bmp': panel((2, 4, 180, 28), '戦闘の終了', [((20, 47, 210, 78), ['戦闘を終えるには、', '戦闘終了ボタンを押す。'])]),
    'G216.bmp': white(labels([((2, 4, 199, 54), ['このボタンで攻撃の', '種類を切り替える', '（近接武器か飛び道具）'])], 14,
                             ink=HELP_INK)),
    'G218.bmp': panel((2, 4, 180, 28), '世界地図', [((20, 47, 205, 96), ['いまいる場所を見るには、', '世界地図ボタンを押す。'])]),
    'G236.bmp': white([((2, 3, 300, 24), ['冒険は続く……'], MINCHO_B, 18, HELP_INK, 'left')]),
})

# ------------------------------------------------ buttons painted on stone / pictures
GOLD = (255, 186, 40)
SPEC.update({
    'G132.BMP': {'erase': 'inpaint', 'texts': [
        ((270, 152, 320, 168), ['訓練'], GOTHIC_B, 14, GOLD, 'center', 'outline', 'orange')]},
    'G133.BMP': {'erase': 'inpaint', 'texts': [
        ((41, 1, 80, 17), ['購入'], GOTHIC_B, 13, GOLD, 'center', 'outline', 'orange'),
        ((81, 1, 120, 17), ['購入'], GOTHIC_B, 13, (226, 200, 170), 'center', 'outline', 'orange'),
        ((0, 110, 11, 127), [''], GOTHIC_B, 12, (255, 255, 255), 'center', 'light'),   # leftover 'H'
        ((0, 108, 46, 127), ['人間'], GOTHIC_B, 12, (255, 255, 255), 'center', 'outline', 'bw'),
        ((46, 108, 92, 127), ['ネフィル'], GOTHIC_B, 11, (255, 255, 255), 'center', 'outline', 'bw'),
        ((92, 108, 138, 127), ['スリス'], GOTHIC_B, 12, (255, 255, 255), 'center', 'outline', 'bw')]},
})
SPEC['G163.bmp'] = {'erase': 'none', 'bg_from': ('G140.BMP', (40, 60)), 'style': 'a4head', 'top': (226, 184, 140), 'bottom': (150, 98, 58),
                    'texts': [((4, 2, 273, 42), ['依頼掲示板'], MINCHO_B, 38, None, 'left')]}
