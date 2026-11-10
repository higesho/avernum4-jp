"""Boxes and texts of the Avernum 3: Ruined World UI images (used by make_images.py).

Coordinates were measured on the original images (_backup_original/Graphics Core).
Images whose content is identical to an already translated image of Escape From the Pit or
Avernum 2 are copied from that mod (COPY below) instead of being redrawn.
"""
import os

FONTS = 'C:/Windows/Fonts/'
MINCHO_B = FONTS + 'yumindb.ttf'       # Yu Mincho Demibold
GOTHIC_B = FONTS + 'YuGothB.ttc'       # Yu Gothic Bold

INK = (52, 16, 14)          # dark red-brown of the help images
STONE_INK = (40, 32, 30)
PARCH_INK = (52, 30, 18)    # "Continent of Valorim" plaque
WHITE = (255, 255, 255)
PANEL_WHITE = (244, 244, 244)   # the game shows pure white as transparent on G128 (letters broke into dots)

HERE = os.path.dirname(os.path.abspath(__file__))
COMMON = os.path.join(HERE, '..', '..', '..')
EFTP_OUT = os.path.join(COMMON, 'Avernum Escape From the Pit', '_jp_mod', 'img_out')
A2_OUT = os.path.join(COMMON, 'Avernum 2 Crystal Souls', '_jp_mod', 'img_out')
# output name -> Japanese image of the same original content
COPY = {
    'G169.png': os.path.join(A2_OUT, 'G169.png'),
    'G203.png': os.path.join(A2_OUT, 'G203.png'),
    'G202.png': os.path.join(EFTP_OUT, 'G202.bmp'),
    'G216.png': os.path.join(EFTP_OUT, 'G216.bmp'),
    'G219.png': os.path.join(A2_OUT, 'G215.png'),
}

SPEC = {
    'G158.png': {
        'erase': 'clear-all',
        'style': 'outlined', 'outline_colour': (66, 36, 52), 'fill': (222, 218, 196),
        'texts': [((x0, y0, x1, y1), [t], MINCHO_B, 30, None, 'center') for (x0, y0, x1, y1), t in [
            ((15, 12, 318, 43), '新しいゲーム'), ((61, 55, 273, 87), 'ロード'),
            ((50, 115, 286, 146), 'キャラクターエディター'), ((54, 158, 281, 189), '操作説明'),
            ((92, 201, 243, 239), '設定'), ((30, 244, 304, 275), '勲章と統計'), ((124, 287, 209, 325), '終了')]]},
    'G128.png': {
        'erase': 'inpaint',
        'texts': [
            ((812, 7, 858, 24), ['地図'], GOTHIC_B, 17, PANEL_WHITE, 'center', 'light'),
            ((766, 305, 828, 322), ['メンバー'], GOTHIC_B, 17, PANEL_WHITE, 'center', 'light'),
            ((386, 618, 452, 637), ['戦闘'], GOTHIC_B, 18, PANEL_WHITE, 'center', 'light'),
            ((498, 618, 562, 637), ['魔法'], GOTHIC_B, 18, PANEL_WHITE, 'center', 'light'),
            ((610, 618, 676, 637), ['特性'], GOTHIC_B, 18, PANEL_WHITE, 'center', 'light'),
            ((386, 659, 452, 680), ['戦闘'], GOTHIC_B, 18, PANEL_WHITE, 'center', 'light'),
            ((498, 659, 562, 680), ['魔法'], GOTHIC_B, 18, PANEL_WHITE, 'center', 'light'),
            ((610, 659, 676, 680), ['特性'], GOTHIC_B, 18, PANEL_WHITE, 'center', 'light'),
        ]},
    'G133.png': {
        'erase': 'inpaint',
        'texts': [
            ((42, 3, 78, 18), ['購入'], GOTHIC_B, 12, (60, 36, 20), 'center'),
            ((82, 3, 118, 18), ['購入'], GOTHIC_B, 12, (110, 100, 90), 'center'),
            ((146, 293, 212, 312), ['読み込み中'], MINCHO_B, 14, STONE_INK, 'center'),
        ]},
    'G167.png': {
        'erase': 'none',
        'fill_rects': [((250, 26, 368, 116), (241, 241, 241, 255))],
        'texts': [((254, y0 - 1, 368, y1 + 1), [t], GOTHIC_B, 12, INK, 'left') for (y0, y1), t in [
            ((32, 44), 'A - 地形'), ((46, 58), 'B - メンバー一覧'), ((60, 71), 'C - 自動地図'),
            ((73, 85), 'D - ゲームボタン'), ((87, 98), 'E - サイドボタン'), ((100, 111), 'F - テキスト欄')]]},
    'G168.png': {
        'erase': 'fill',
        'texts': [
            ((95, 15, 185, 44), ['既定の攻撃', '（sで切替）'], GOTHIC_B, 12, INK, 'left'),
            ((96, 57, 210, 87), ['魔術・祈祷', '（m / p）'], GOTHIC_B, 12, INK, 'left'),
            ((96, 97, 210, 127), ['戦闘修練', '（d）'], GOTHIC_B, 12, INK, 'left'),
            ((261, 20, 318, 37), ['拾う（g）'], GOTHIC_B, 12, INK, 'left'),
            ((261, 50, 332, 90), ['日誌と', 'クエスト'], GOTHIC_B, 12, INK, 'left'),
            ((261, 95, 366, 130), ['クイック呪文・使用', '（F5〜F12）'], GOTHIC_B, 12, INK, 'left'),
        ]},
    'G196.png': {
        'erase': 'fill',
        'texts': [
            ((5, 4, 142, 25), ['戦い方'], MINCHO_B, 20, INK, 'left'),
            ((12, 26, 214, 71), ['1. このボタンで攻撃の', '種類を切り替えます', '（近接武器か飛び道具）'], GOTHIC_B, 13, INK, 'left'),
            ((163, 88, 320, 137), ['2. 敵が立っている', 'マスを選択すると', '攻撃します。'], GOTHIC_B, 13, INK, 'left'),
        ]},
    'G197.png': {
        'erase': 'fill',
        'texts': [
            ((50, 13, 112, 30), ['ファイル'], GOTHIC_B, 12, INK, 'center'),
            ((43, 53, 120, 70), ['操作説明'], GOTHIC_B, 12, INK, 'center'),
            ((165, 13, 232, 30), ['世界地図'], GOTHIC_B, 12, INK, 'center'),
            ((168, 53, 230, 70), ['編成'], GOTHIC_B, 12, INK, 'center'),
            ((292, 24, 366, 58), ['戦闘の', '開始/終了'], GOTHIC_B, 12, INK, 'center'),
        ]},
    'G217.png': {
        'erase': 'inpaint',
        'texts': [((22, 34, 214, 98), ['ヴァロリム大陸'], MINCHO_B, 30, PARCH_INK, 'center')]},
    'G288.png': {
        'erase': 'fill',
        'style': 'olive',
        'texts': [((12, 2, 380, 30), ['冒険は続く……'], MINCHO_B, 24, None, 'left')]},
}

# Avernum 3 has no chapter book pages.
PAGE_BOX = (0, 0, 0, 0)
PAGE_INK = (28, 16, 10)
PAGES = {}
