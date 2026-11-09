"""header_src.jpg 로 GUI 배경 이미지(bg_map.png, bg_full.png)를 만든다. (개발용: python make_bg.py)"""
from PIL import Image, ImageEnhance, ImageFilter, ImageDraw
import os
here = os.path.dirname(os.path.abspath(__file__))
src = Image.open(os.path.join(here, "header_src.jpg")).convert("RGB")

def make(w, h, name, anchor_right=True, zoom=1.0):
    s = max(w / src.width, h / src.height) * zoom
    im = src.resize((int(src.width * s) + 1, int(src.height * s) + 1), Image.LANCZOS)
    x0 = im.width - w if anchor_right else (im.width - w) // 2
    im = im.crop((x0, 0, x0 + w, h)).filter(ImageFilter.GaussianBlur(1.1))
    im = ImageEnhance.Brightness(im).enhance(0.55)
    im = ImageEnhance.Color(im).enhance(0.8)
    # 위쪽은 비교적 밝게, 아래쪽은 짙게 (내용이 올라가는 영역은 어둡게)
    ov = Image.new("L", (w, h))
    d = ImageDraw.Draw(ov)
    for y in range(h):
        d.line([(0, y), (w, y)], fill=int(255 * min(1.0, 0.0 + max(0, (y - 90)) / 260.0) * 0.78))
    dark = Image.new("RGB", (w, h), (8, 10, 7))
    im = Image.composite(dark, im, ov)
    # 가장자리 어둡게
    vg = Image.new("L", (w, h), 0)
    vd = ImageDraw.Draw(vg)
    vd.ellipse((-w * 0.25, -h * 0.25, w * 1.25, h * 1.25), fill=255)
    vg = vg.filter(ImageFilter.GaussianBlur(min(w, h) * 0.12))
    im = Image.composite(im, Image.new("RGB", (w, h), (4, 5, 4)), vg)
    im.save(os.path.join(here, name), optimize=True)

make(580, 470, "bg_map.png", zoom=1.3)
make(900, 830, "bg_full.png", zoom=1.3)
