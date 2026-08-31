#!/usr/bin/env python3
"""Generate Instagram/Facebook Story-format (1080x1920) quote cards for the
personal statements on the site, reusing the campaign's mint/navy
Montserrat-Black design language (same as 260731_Ja-zur-Badi-Digital-1080x1920.jpg
and site/index.html #statements).

Run: python3 scripts/generate_social_posts.py
Output: site/assets/social/*.jpg
"""
import subprocess
import textwrap
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
STATEMENTS_DIR = ROOT / "site" / "statements"
ELEMENTS_DIR = ROOT / "site" / "assets" / "elements"
OUT_DIR = ROOT / "site" / "assets" / "social"
CACHE_DIR = ROOT / "scripts" / ".cache"
OUT_DIR.mkdir(parents=True, exist_ok=True)
CACHE_DIR.mkdir(parents=True, exist_ok=True)

# ---- Brand palette (from site/css/styles.css :root) ----
MINT = (156, 209, 201)
MINT_LIGHT = (232, 244, 242)
NAVY = (0, 91, 145)
WHITE = (255, 255, 255)

W, H = 1080, 1920

FONT_TTF = CACHE_DIR / "Montserrat-Black.ttf"


def ensure_font():
    if FONT_TTF.exists():
        return
    from fontTools.ttLib import TTFont
    f = TTFont(DATA / "font-0024.woff")
    f.flavor = None
    f.save(str(FONT_TTF))


def font(size):
    return ImageFont.truetype(str(FONT_TTF), size)


LOGO_SVGS = {
    "fdp": ELEMENTS_DIR / "logo_fdp.svg",
    "gl": ELEMENTS_DIR / "logo-gruenliberale.svg",
    "sp": ELEMENTS_DIR / "logo-sp.svg",
}


def ensure_logo_pngs():
    for name, svg in LOGO_SVGS.items():
        out = CACHE_DIR / f"logo-{name}.png"
        if out.exists():
            continue
        subprocess.run(
            [
                "inkscape", str(svg),
                "--export-type=png",
                "--export-height=500",
                "--export-background-opacity=0",
                f"--export-filename={out}",
            ],
            check=True, capture_output=True,
        )


def load_logo(name):
    if name == "evp":
        return Image.open(ELEMENTS_DIR / "logo-evp.png").convert("RGBA")
    return Image.open(CACHE_DIR / f"logo-{name}.png").convert("RGBA")


def paste_logo_row(canvas, y_center, height_footer):
    """Reproduces the flyer's footer logo row: FDP, EVP, Grünliberale, SP,
    each sized to a fraction of the footer band height (same ratios as
    site/css/styles.css .site-footer__logo--*), scaled down together if
    the row would otherwise overflow the canvas width."""
    specs = [
        ("fdp", 0.45),
        ("evp", 0.85),
        ("gl", 0.28),
        ("sp", 0.60),
    ]
    gap = 56
    margin = 60
    max_w = W - margin * 2

    imgs = []
    for name, frac in specs:
        logo = load_logo(name)
        target_h = int(height_footer * frac)
        ratio = target_h / logo.height
        imgs.append(logo.resize((max(1, int(logo.width * ratio)), target_h), Image.LANCZOS))

    total_w = sum(im.width for im in imgs) + gap * (len(imgs) - 1)
    if total_w > max_w:
        scale = max_w / total_w
        imgs = [im.resize((max(1, int(im.width * scale)), max(1, int(im.height * scale))), Image.LANCZOS) for im in imgs]
        total_w = sum(im.width for im in imgs) + gap * (len(imgs) - 1)

    x = (W - total_w) // 2
    for im in imgs:
        y = y_center - im.height // 2
        canvas.alpha_composite(im, (x, y))
        x += im.width + gap


def rounded_mask(size, radius):
    mask = Image.new("L", size, 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, size[0] - 1, size[1] - 1], radius=radius, fill=255)
    return mask


def circle_portrait(path, diameter, focus=(0.5, 0.5)):
    im = Image.open(path).convert("RGB")
    im = ImageOps.fit(im, (diameter, diameter), method=Image.LANCZOS, centering=focus)
    mask = Image.new("L", (diameter, diameter), 0)
    ImageDraw.Draw(mask).ellipse([0, 0, diameter - 1, diameter - 1], fill=255)
    out = Image.new("RGBA", (diameter, diameter))
    out.paste(im, (0, 0), mask)
    return out


def soft_shadow(canvas, box, radius, blur=28, opacity=70, shape="rounded", corner_radius=0):
    """box=(x0,y0,x1,y1) in canvas coords. Draws a blurred dark shape behind content."""
    pad = blur * 3
    layer = Image.new("RGBA", (box[2] - box[0] + pad * 2, box[3] - box[1] + pad * 2), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    lb = [pad, pad, layer.width - pad, layer.height - pad]
    if shape == "ellipse":
        d.ellipse(lb, fill=(0, 40, 60, opacity))
    else:
        d.rounded_rectangle(lb, radius=corner_radius, fill=(0, 40, 60, opacity))
    layer = layer.filter(ImageFilter.GaussianBlur(blur))
    canvas.alpha_composite(layer, (box[0] - pad, box[1] - pad))


def fit_quote(draw, text, max_width, max_height, start_size=46, min_size=28):
    for size in range(start_size, min_size - 1, -2):
        f = font(size)
        # wrap by measuring, word by word
        words = text.split()
        lines, cur = [], ""
        for w in words:
            trial = (cur + " " + w).strip()
            if draw.textlength(trial, font=f) <= max_width:
                cur = trial
            else:
                lines.append(cur)
                cur = w
        if cur:
            lines.append(cur)
        line_h = int(size * 1.42)
        total_h = line_h * len(lines)
        if total_h <= max_height:
            return f, lines, line_h
    return f, lines, line_h


def draw_centered(draw, text, cy, size, fill, canvas_w=W):
    f = font(size)
    w = draw.textlength(text, font=f)
    draw.text(((canvas_w - w) / 2, cy), text, font=f, fill=fill)
    return f


STATEMENTS = [
    dict(
        slug="beat-knecht",
        name="Beat Knecht",
        role="Einwohnerrat Liste GLP",
        photo=STATEMENTS_DIR / "Beat_Knecht_Badi-Komitee.png",
        focus=(0.5, 0.35),
        quote=(
            "Der Hitzesommer 2026 hat uns eindrücklich gezeigt, wie wichtig "
            "unser Freibad für Beringen ist. Keine Badi ist für mich keine Option."
        ),
    ),
    dict(
        slug="carmen-vlah",
        name="Carmen Vlah",
        role="Co-Präsidentin SP Beringen",
        photo=STATEMENTS_DIR / "CarmenVlah.jpeg",
        focus=(0.5, 0.28),
        quote=(
            "Ich bin für die Sanierung der Badi Beringen und die neue "
            "Filteranlage, weil ich lieber sauberes Wasser in den Bach "
            "zurückgebe, als unnötig belastetes Wasser als Abwasser "
            "entsorgen zu müssen."
        ),
    ),
    dict(
        slug="reto-weber",
        name="Reto Weber",
        role="Einwohnerrat EVP",
        photo=STATEMENTS_DIR / "Reto2.jpg",
        focus=(0.5, 0.4),
        quote=(
            "Ich bin für diese Sanierung der Badi Beringen, "
            "weil sie günstiger und ökologischer ist als die Alternative."
        ),
    ),
    dict(
        slug="daniel-wulle",
        name="Daniel Wulle",
        role="Mitglied Copräsidium EVP Schaffhausen",
        photo=STATEMENTS_DIR / "DaniWulle.jpeg",
        focus=(0.5, 0.32),
        quote=(
            "Ich stimme JA für unsere schöne Badi, weil es der Treffpunkt "
            "für Begegnungen unter allen Generationen ist."
        ),
    ),
    dict(
        slug="vanessa-le-donne",
        name="Vanessa Le Donne",
        role="Kantons- und Einwohnerrätin FDP",
        photo=STATEMENTS_DIR / "vanessa2.jpeg",
        focus=(0.5, 0.3),
        quote=(
            "Ich stimme JA – aus Überzeugung. Eine Rückkehr zu Chlor wäre "
            "ein Rückschritt – in Sachen Innovation, Nachhaltigkeit und "
            "Einzigartigkeit."
        ),
    ),
    dict(
        slug="lukas-ruedlinger",
        name="Lukas Rüedlinger",
        role="Einwohnerrat SP Beringen",
        photo=STATEMENTS_DIR / "lukas.jpg",
        focus=(0.5, 0.45),
        quote=(
            "Eine Gemeinde in unserer Grösse braucht einen Ort wie diesen. "
            "Wir investieren nicht nur in ein Schwimmbecken – wir investieren "
            "in Begegnungen, in unsere Kinder und in unsere Gemeinschaft."
        ),
    ),
]


def build(entry):
    canvas = Image.new("RGBA", (W, H), MINT + (255,))
    draw = ImageDraw.Draw(canvas)

    # ---- top pill tag ----
    tag_text = "PERSÖNLICHE STIMME"
    tag_font = font(30)
    tw = draw.textlength(tag_text, font=tag_font)
    pill_w, pill_h = int(tw + 72), 74
    pill_box = [(W - pill_w) // 2, 78, (W - pill_w) // 2 + pill_w, 78 + pill_h]
    draw.rounded_rectangle(pill_box, radius=pill_h // 2, fill=NAVY + (255,))
    draw.text((pill_box[0] + 36, pill_box[1] + 20), tag_text, font=tag_font, fill=WHITE)

    # ---- portrait ----
    diameter = 460
    portrait_top = 210
    cx = W // 2
    ring = 16
    shadow_box = (cx - diameter // 2 - ring, portrait_top - ring, cx + diameter // 2 + ring, portrait_top + diameter + ring)
    soft_shadow(canvas, shadow_box, radius=0, blur=26, opacity=60, shape="ellipse")
    draw.ellipse(shadow_box, fill=WHITE + (255,))
    portrait = circle_portrait(entry["photo"], diameter, entry["focus"])
    canvas.alpha_composite(portrait, (cx - diameter // 2, portrait_top))

    # ---- name / role ----
    name_y = portrait_top + diameter + 46
    draw_centered(draw, entry["name"], name_y, 62, NAVY + (255,))
    role_y = name_y + 78
    draw_centered(draw, entry["role"], role_y, 34, NAVY + (200,))

    # ---- quote card ----
    card_top = role_y + 80
    card_bottom = 1430
    card_margin = 74
    card_box = [card_margin, card_top, W - card_margin, card_bottom]
    soft_shadow(canvas, card_box, radius=36, blur=24, opacity=45, corner_radius=36)
    draw.rounded_rectangle(card_box, radius=36, fill=WHITE + (255,))

    # decorative quote mark
    qmark_font = font(160)
    draw.text((card_box[0] + 34, card_box[1] - 34), "\u201e", font=qmark_font, fill=MINT_LIGHT + (255,))

    pad_x = 70
    top_clearance = 150  # keeps quote text clear of the decorative quote mark
    bottom_pad = 60
    max_w = (card_box[2] - card_box[0]) - pad_x * 2
    max_h = (card_box[3] - card_box[1]) - top_clearance - bottom_pad
    qfont, lines, line_h = fit_quote(draw, entry["quote"], max_w, max_h, start_size=48, min_size=30)
    total_h = line_h * len(lines)
    avail_h = (card_box[3] - card_box[1]) - top_clearance - bottom_pad
    ty = card_box[1] + top_clearance + max(0, (avail_h - total_h) // 2)
    for line in lines:
        draw.text((card_box[0] + pad_x, ty), line, font=qfont, fill=NAVY + (255,))
        ty += line_h

    # ---- CTA lockup (same copy as 260731_Ja-zur-Badi-Digital-1080x1920.jpg) ----
    cta_font = font(58)
    draw.text((card_margin, 1478), "JA zur Sanierung unserer Badi.", font=cta_font, fill=NAVY + (255,))
    link_font = font(44)
    draw.text((card_margin, 1478 + 76), "\u2192 badi-ja.ch", font=link_font, fill=NAVY + (255,))

    # ---- footer ----
    footer_h = 222
    footer_top = H - footer_h
    draw.rectangle([0, footer_top, W, H], fill=WHITE + (255,))
    paste_logo_row(canvas, footer_top + footer_h // 2, footer_h)

    out_path = OUT_DIR / f"statement-{entry['slug']}.jpg"
    canvas.convert("RGB").save(out_path, quality=92)
    print("wrote", out_path)


def main():
    ensure_font()
    ensure_logo_pngs()
    for entry in STATEMENTS:
        build(entry)


if __name__ == "__main__":
    main()
