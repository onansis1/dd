"""header_src.jpg 로 GUI 배경 이미지(bg_map.png, bg_full.png)를 만든다. (개발용: python make_bg.py)
위쪽에는 게임 대표 이미지(로고 포함)를 그대로 쓰고, 아래쪽은 입력 영역이라 어둡게 이어 붙인다."""
from PIL import Image, ImageDraw
import os
here = os.path.dirname(os.path.abspath(__file__))
src = Image.open(os.path.join(here, "header_src.jpg")).convert("RGB")
DARK = (12, 14, 11)

def make(w, h, name, banner_h, crop_rows=None):
    s = w / src.width
    im = src.resize((w, round(src.height * s)), Image.LANCZOS)
    if crop_rows:
        y0, y1 = round(crop_rows[0] * s), round(crop_rows[1] * s)
        im = im.crop((0, y0, w, y1))
    im = im.resize((w, banner_h), Image.LANCZOS) if im.height != banner_h else im
    canvas = Image.new("RGB", (w, h), DARK)
    canvas.paste(im, (0, 0))
    # 배너 아래쪽을 어두운 배경으로 자연스럽게 이어 붙인다
    fade = 46
    ov = Image.new("L", (w, h), 0)
    d = ImageDraw.Draw(ov)
    for i in range(fade):
        d.line([(0, banner_h - fade + i), (w, banner_h - fade + i)], fill=int(255 * (i / fade) ** 1.6))
    d.rectangle((0, banner_h, w, h), fill=255)
    canvas = Image.composite(Image.new("RGB", (w, h), DARK), canvas, ov)
    canvas.save(os.path.join(here, name), optimize=True)

make(580, 601, "bg_map.png", 271)
make(900, 1010, "bg_full.png", 225, crop_rows=(85, 200))
print("banner_h map=271 full=225")
