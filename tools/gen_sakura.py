# -*- coding: utf-8 -*-
"""生成樱花侧栏花枝 SVG：一条纵向长枝，落在侧栏中段空白处。"""
import math
import os

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "static", "assets")

W, H = 64, 470
BRANCH = "#A07E64"
PETAL = "#F3B6C9"
PETAL_D = "#E68FAD"
CORE = "#D8698D"
BUD = "#EFA9C0"


def blossom(cx, cy, scale=1.0, rot=0.0):
    parts = []
    for i in range(5):
        a = math.radians(rot + i * 72)
        parts.append('<circle cx="%.2f" cy="%.2f" r="%.2f" fill="%s"/>'
                     % (cx + math.cos(a) * 3.4 * scale, cy + math.sin(a) * 3.4 * scale, 2.9 * scale, PETAL))
    for i in range(5):
        a = math.radians(rot + i * 72 + 36)
        parts.append('<circle cx="%.2f" cy="%.2f" r="%.2f" fill="%s" opacity=".5"/>'
                     % (cx + math.cos(a) * 2.1 * scale, cy + math.sin(a) * 2.1 * scale, 1.4 * scale, PETAL_D))
    parts.append('<circle cx="%.2f" cy="%.2f" r="%.2f" fill="%s"/>' % (cx, cy, 1.2 * scale, CORE))
    return "".join(parts)


def build():
    body = (
        '<g fill="none" stroke="%s" stroke-linecap="round" opacity=".55">'
        '<path d="M30 -8 C 22 52, 42 96, 34 152 S 18 244, 30 300 S 46 386, 36 470" stroke-width="2"/>'
        '<path d="M34 152 C 26 172, 20 186, 14 200" stroke-width="1.4"/>'
        '<path d="M30 300 C 40 318, 46 332, 50 348" stroke-width="1.4"/>'
        '<path d="M31 62 C 40 76, 44 88, 46 102" stroke-width="1.3"/>'
        '<path d="M28 396 C 20 410, 16 422, 14 436" stroke-width="1.2"/>'
        '</g>' % BRANCH
    )
    for cx, cy, sc, rot in ((14.5, 200, 1.0, 18), (46, 102, 0.9, -6), (50, 348, 0.95, 24),
                            (34, 60, 0.75, 40), (20, 250, 0.62, 8), (14, 436, 0.85, -20),
                            (44, 300, 0.7, 12)):
        body += blossom(cx, cy, sc, rot)
    for cx, cy in ((24, 120), (40, 226), (26, 366), (48, 40)):
        body += '<circle cx="%s" cy="%s" r="1.8" fill="%s"/>' % (cx, cy, BUD)
    return ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 %d %d" width="%d" height="%d">%s</svg>'
            % (W, H, W, H, body))


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    path = os.path.join(OUT, "sakura-branch.svg")
    open(path, "w", encoding="utf-8").write(build())
    print("sakura-branch.svg", os.path.getsize(path), "bytes")
    old = os.path.join(OUT, "sakura-branch-bottom.svg")
    if os.path.exists(old):
        os.remove(old)
    old = os.path.join(OUT, "sakura-branch-top.svg")
    if os.path.exists(old):
        os.remove(old)
