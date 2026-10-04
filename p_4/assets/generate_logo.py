"""Generate a professional logo for the Bubble Typing Game.

Run:  python assets/generate_logo.py
Produces: assets/logo.png  (600x600, transparent rounded card)
Requires: Pillow  (pip install pillow)
"""

import math
import os
from PIL import Image, ImageDraw, ImageFont, ImageFilter

W, H = 600, 600
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logo.png")

# --- font helper ----------------------------------------------------------
def load_font(size):
    for path in (
        r"C:\Windows\Fonts\arialbd.ttf",
        r"C:\Windows\Fonts\arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
    ):
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                pass
    return ImageFont.load_default()


def lerp(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def center_text(draw, text, font, y, fill):
    bbox = draw.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    x = (W - tw) // 2 - bbox[0]
    draw.text((x, y), text, font=font, fill=fill)
    return th


# --- background: vertical gradient on a rounded card ----------------------
top_color = (31, 42, 90)       # #1f2a5a
bottom_color = (11, 18, 48)    # #0b1230

bg = Image.new("RGB", (W, H))
bd = ImageDraw.Draw(bg)
for y in range(H):
    t = y / (H - 1)
    bd.line([(0, y), (W, y)], fill=lerp(top_color, bottom_color, t))

# rounded-corner mask
mask = Image.new("L", (W, H), 0)
ImageDraw.Draw(mask).rounded_rectangle([0, 0, W - 1, H - 1], radius=64, fill=255)
card = Image.new("RGBA", (W, H), (0, 0, 0, 0))
card.paste(bg, (0, 0))
card.putalpha(mask)

draw = ImageDraw.Draw(card)

# subtle accent border
draw.rounded_rectangle([0, 0, W - 1, H - 1], radius=64, outline=(90, 180, 255, 90), width=3)

# --- ambient glow behind the bubble ---------------------------------------
cx, cy, r = 300, 225, 125
glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
ImageDraw.Draw(glow).ellipse([cx - 190, cy - 190, cx + 190, cy + 190], fill=(90, 180, 255, 55))
glow = glow.filter(ImageFilter.GaussianBlur(45))
card.alpha_composite(glow)

# --- glossy bubble with radial gradient -----------------------------------
pad = 6
bs = 2 * r + pad * 2
bubble = Image.new("RGBA", (bs, bs), (0, 0, 0, 0))
center = bs // 2
inner = (150, 210, 255)       # light blue center
outer = (40, 110, 200)        # deeper blue edge
for px in range(bs):
    for py in range(bs):
        dx, dy = px - center, py - center
        dist = math.hypot(dx, dy)
        if dist <= r:
            t = dist / r
            bubble.putpixel((px, py), (*lerp(inner, outer, t), 255))

# white border
ImageDraw.Draw(bubble).ellipse([pad, pad, bs - pad, bs - pad], outline=(255, 255, 255), width=5)

# glossy highlight (upper-left)
hl = Image.new("RGBA", (bs, bs), (0, 0, 0, 0))
hld = ImageDraw.Draw(hl)
hlc = (center - int(r * 0.32), center - int(r * 0.34))
hld.ellipse([hlc[0] - int(r * 0.42), hlc[1] - int(r * 0.28),
             hlc[0] + int(r * 0.42), hlc[1] + int(r * 0.28)], fill=(255, 255, 255, 95))
bubble.alpha_composite(hl)

# letter "A" inside the bubble
f_letter = load_font(115)
ld = ImageDraw.Draw(bubble)
bbox = ld.textbbox((0, 0), "A", font=f_letter)
tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
ld.text(((bs - tw) // 2 - bbox[0], (bs - th) // 2 - bbox[1] - 6),
        "A", font=f_letter, fill=(20, 30, 60))

card.alpha_composite(bubble, (cx - center, cy - center))

# --- title text -----------------------------------------------------------
f_title = load_font(54)
f_sub = load_font(42)
center_text(draw, "BUBBLE TYPING", f_title, 395, (235, 240, 255))
center_text(draw, "GAME", f_sub, 460, (90, 180, 255))

# small decorative letter-key dots along the bottom
dot_y = 540
letters = "A B C D"
f_dot = load_font(22)
bbox = draw.textbbox((0, 0), letters, font=f_dot)
dw = bbox[2] - bbox[0]
draw.text(((W - dw) // 2 - bbox[0], dot_y), letters, font=f_dot, fill=(150, 160, 195))

card.save(OUT, "PNG")
print("Saved logo to", OUT)