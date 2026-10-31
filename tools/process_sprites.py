# -*- coding: utf-8 -*-
"""把生成图里的纯色背景抠掉，压回像素网格，输出可直接使用的 PNG（不依赖 numpy）。"""
import glob
import os
from PIL import Image, ImageChops

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(ROOT, "tools", "raw")
OUT = os.path.join(ROOT, "static", "assets")
TOOLS = os.path.dirname(os.path.abspath(__file__))


def bg_color(im):
    px = im.load()
    pts = [(4, 4), (im.width - 5, 4), (4, im.height - 5), (im.width - 5, im.height - 5)]
    cols = sorted([px[p] for p in pts], key=lambda c: sum(c))
    return cols[len(cols) // 2]


def key_out(path, crop_bottom=0, tol=58):
    im = Image.open(path).convert("RGB")
    if crop_bottom:
        im = im.crop((0, 0, im.width, im.height - crop_bottom))
    bg = bg_color(im)
    solid = Image.new("RGB", im.size, bg)
    diff = ImageChops.difference(im, solid)
    r, g, b = diff.split()
    d = ImageChops.lighter(ImageChops.lighter(r, g), b)
    mask = d.point(lambda v: 0 if v < tol else 255)

    # 透明区域填成不透明部分的平均色，避免缩放时洋红渗边
    mean = Image.composite(im, Image.new("RGB", im.size, (0, 0, 0)), mask)
    stat = mean.resize((1, 1), Image.BOX).getpixel((0, 0))
    filled = Image.composite(im, Image.new("RGB", im.size, stat), mask)

    rgba = filled.convert("RGBA")
    rgba.putalpha(mask)
    return rgba, im.size


def to_grid(rgba, target_w):
    w, h = rgba.size
    target_h = max(1, int(round(target_w * h / w)))
    small = rgba.resize((target_w, target_h), Image.BOX)
    a = small.split()[3].point(lambda v: 255 if v > 118 else 0)
    small.putalpha(a)
    return small


def crop_alpha(im, pad=1):
    box = im.split()[3].getbbox()
    if not box:
        return im
    x0, y0, x1, y1 = box
    return im.crop((max(0, x0 - pad), max(0, y0 - pad),
                    min(im.width, x1 + pad), min(im.height, y1 + pad)))


def build(pattern, out_name, grid_w, scale=4, crop_bottom=96):
    files = sorted(glob.glob(os.path.join(RAW, pattern)))
    if not files:
        raise SystemExit("no raw file for " + pattern)
    rgba, size = key_out(files[0], crop_bottom=crop_bottom)
    rgba = crop_alpha(rgba, pad=0)          # 先裁到主体，再压网格，避免边缘被拉低分辨率
    small = crop_alpha(to_grid(rgba, grid_w))
    big = small.resize((small.width * scale, small.height * scale), Image.NEAREST)
    big.save(os.path.join(OUT, out_name))
    print("%-12s %s -> %dx%d -> %dx%d" % (out_name, size, small.width, small.height, big.width, big.height))
    return small


if __name__ == "__main__":
    jobs = [
        ("Pixel_art_game_sprite_of_a_sma_*.png", "dragon.png", 44, 90),
        ("Pixel_art_character_portrait_s_*.png", "avatar.png", 34, 104, 3),
        ("Pixel_art_game_sprite_of_a_cut_2026-10-30T19-15-44.png", "cat.png", 40, 100),
        ("Pixel_art_game_sprite_of_a_cut_2026-10-30T19-16-48.png", "dog.png", 40, 100),
    ]
    made = []
    for job in jobs:
        pattern, out, w, crop = job[:4]
        scale = job[4] if len(job) > 4 else 4
        made.append((out.replace(".png", ""), build(pattern, out, w, scale, crop)))

    for name, im in made:
        bg = Image.new("RGBA", (im.width * 8 + 80, im.height * 8 + 80), (250, 248, 243, 255))
        up = im.resize((im.width * 8, im.height * 8), Image.NEAREST)
        bg.paste(up, (40, 40), up)
        bg.save(os.path.join(TOOLS, "_ck_%s.png" % name))
        print("preview", name, bg.size)
