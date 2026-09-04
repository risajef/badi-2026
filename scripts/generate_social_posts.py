#!/usr/bin/env python3
"""Generate the statement cards from the designer's 1080x1920 templates.

The supplied SVGs contain the complete artwork, illustrations and footer
lockup. This script removes the sample name, function and quote from the
templates, then renders the same layout with the statement-specific copy.

Run: python3 scripts/generate_social_posts.py
Output: site/assets/social/*.png (1080x1920)
"""

import re
import subprocess
import xml.etree.ElementTree as ET
from copy import deepcopy
from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps


ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
OUT_DIR = ROOT / "site" / "assets" / "social"
TEMPLATE_DIR = ROOT / "socialmediavorlagen"
CACHE_DIR = ROOT / "scripts" / ".cache"
STATEMENTS_DIR = ROOT / "site" / "statements"
EVP_LOGO_PATH = ROOT / "site" / "assets" / "elements" / "logo-evp.png"

OUT_DIR.mkdir(parents=True, exist_ok=True)
CACHE_DIR.mkdir(parents=True, exist_ok=True)

W, H = 1080, 1920
SVG_NS = "http://www.w3.org/2000/svg"
XLINK_NS = "http://www.w3.org/1999/xlink"

# These are the colors used by the designer artwork for the dynamic copy.
TEMPLATE_NAVY = (0, 70, 113)

FONT_TTF = CACHE_DIR / "Montserrat-Black.ttf"
QUOTE_FONT_CANDIDATES = (
    DATA / "Montserrat-Regular.otf",
    Path("/usr/share/texlive/texmf-dist/fonts/opentype/public/montserrat/Montserrat-Regular.otf"),
    Path("/usr/share/fonts/truetype/montserrat/Montserrat-Regular.ttf"),
)
TEMPLATE_PATHS = [
    TEMPLATE_DIR / f"Badi-Beringen-Social-Media_1080x1920-{number:02d}.svg"
    for number in range(1, 5)
]
TEMPLATE_RENDER_VERSION = "v3"
PHOTO_BOX = (330, 146, 750, 566)
PHOTO_FOREGROUND_MAX_Y = 700
EVP_LOGO_POSITION = (318, 1769)
EVP_LOGO_SIZE = (91, 91)


def ensure_font():
    """Convert the supplied Montserrat Black webfont for Pillow."""
    if FONT_TTF.exists():
        return

    from fontTools.ttLib import TTFont

    font_file = TTFont(DATA / "font-0024.woff")
    font_file.flavor = None
    font_file.save(str(FONT_TTF))


@lru_cache(maxsize=None)
def font(size):
    return ImageFont.truetype(str(FONT_TTF), size)


def quote_font_path():
    for candidate in QUOTE_FONT_CANDIDATES:
        if candidate.exists():
            return candidate
    # The supplied webfont is a safe fallback on machines without a separate
    # Montserrat Regular installation. The generated layout still remains
    # fully functional; the designer's exact weight is used when available.
    return FONT_TTF


@lru_cache(maxsize=None)
def quote_font(size):
    return ImageFont.truetype(str(quote_font_path()), size)


def local_name(tag):
    return tag.rsplit("}", 1)[-1]


def element_text(element):
    return " ".join(
        part.strip()
        for part in element.itertext()
        if part and part.strip()
    )


def is_vectorized_quote(element):
    """Identify the converted-to-path quote group in the supplied SVG."""
    return any(
        local_name(child.tag) == "path"
        and child.attrib.get("d", "").startswith("M135.3,938.7")
        for child in element.iter()
    )


def has_photo_foreground_path(element):
    """Identify the illustration group drawn over the photo frame."""
    number = r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)"
    move_pattern = re.compile(rf"^\s*M\s*({number})\s*[, ]\s*({number})")
    for descendant in element.iter():
        if local_name(descendant.tag) != "path":
            continue
        match = move_pattern.match(descendant.attrib.get("d", ""))
        if match and float(match.group(2)) <= PHOTO_FOREGROUND_MAX_Y:
            return True
    return False


def clean_template(template_path):
    """Build the cleaned background and the transparent figure foreground."""
    ET.register_namespace("", SVG_NS)
    ET.register_namespace("xlink", XLINK_NS)
    root = ET.parse(template_path).getroot()

    # The sample name and function are live SVG text elements. Remove them so
    # Pillow can draw replacement text with the local Montserrat font.
    placeholders = {"VORNAME UND NACHNAME", "FUNKTION"}
    for parent in root.iter():
        for child in list(parent):
            if local_name(child.tag) == "text" and element_text(child) in placeholders:
                parent.remove(child)

    # The sample quote was expanded to paths by the designer, so it is a
    # group rather than editable text. It is the only direct child containing
    # the quote's first glyph path.
    quote_groups = [child for child in root if is_vectorized_quote(child)]
    if len(quote_groups) != 1:
        raise RuntimeError(
            f"Expected one vectorized quote group in {template_path}, "
            f"found {len(quote_groups)}"
        )
    root.remove(quote_groups[0])

    # The designer's red X is embedded as two raster images: one in the top
    # photo frame and one in the footer party-logo slot. Remove those images
    # so the real photo and EVP logo can be composited cleanly below.
    for parent in root.iter():
        for child in list(parent):
            if local_name(child.tag) != "image":
                continue
            width = child.attrib.get("width")
            height = child.attrib.get("height")
            transform = child.attrib.get("transform", "")
            is_top_placeholder = (
                width == "300"
                and height == "300"
                and "translate(320 136.8)" in transform
            )
            is_footer_placeholder = (
                width == "150"
                and height == "150"
                and "translate(317.9346 1769.5266)" in transform
            )
            if is_top_placeholder or is_footer_placeholder:
                parent.remove(child)

    foreground_groups = [
        child
        for child in root
        if local_name(child.tag) == "g" and has_photo_foreground_path(child)
    ]
    if len(foreground_groups) != 1:
        raise RuntimeError(
            f"Expected one photo foreground group in {template_path}, "
            f"found {len(foreground_groups)}"
        )

    foreground_group = foreground_groups[0]
    root.remove(foreground_group)
    foreground_root = ET.Element(root.tag, root.attrib)
    for child in root:
        if local_name(child.tag) == "defs":
            foreground_root.append(deepcopy(child))
    foreground_root.append(foreground_group)

    return (
        ET.tostring(root, encoding="unicode"),
        ET.tostring(foreground_root, encoding="unicode"),
    )


def render_template(template_path, template_number):
    """Render a cleaned SVG once and return its pixel background."""
    clean_path = CACHE_DIR / (
        f"social-template-{template_number:02d}-{TEMPLATE_RENDER_VERSION}-clean.svg"
    )
    png_path = CACHE_DIR / (
        f"social-template-{template_number:02d}-{TEMPLATE_RENDER_VERSION}-clean.png"
    )
    foreground_path = CACHE_DIR / (
        f"social-template-{template_number:02d}-{TEMPLATE_RENDER_VERSION}-foreground.svg"
    )
    foreground_png_path = CACHE_DIR / (
        f"social-template-{template_number:02d}-{TEMPLATE_RENDER_VERSION}-foreground.png"
    )

    # Rebuild the cached render whenever the designer replaces a template.
    cache_paths = (clean_path, png_path, foreground_path, foreground_png_path)
    if any(
        not path.exists() or path.stat().st_mtime < template_path.stat().st_mtime
        for path in cache_paths
    ):
        clean_svg, foreground_svg = clean_template(template_path)
        clean_path.write_text(clean_svg, encoding="utf-8")
        foreground_path.write_text(foreground_svg, encoding="utf-8")
        try:
            for svg_path, output_path in (
                (clean_path, png_path),
                (foreground_path, foreground_png_path),
            ):
                subprocess.run(
                    [
                        "inkscape",
                        str(svg_path),
                        "--export-filename",
                        str(output_path),
                        "--export-width",
                        str(W),
                        "--export-height",
                        str(H),
                    ],
                    check=True,
                    capture_output=True,
                    text=True,
                )
        except FileNotFoundError as error:
            raise RuntimeError(
                "Inkscape ist zum Rendern der Social-Media-Vorlagen nicht installiert."
            ) from error
        except subprocess.CalledProcessError as error:
            details = error.stderr.strip() or error.stdout.strip()
            raise RuntimeError(
                f"Vorlage {template_path.name} konnte nicht gerendert werden: {details}"
            ) from error

    return (
        Image.open(png_path).convert("RGBA"),
        Image.open(foreground_png_path).convert("RGBA"),
    )


def fit_single_line(draw, text, max_width, start_size, min_size):
    for size in range(start_size, min_size - 1, -1):
        current_font = font(size)
        if draw.textlength(text, font=current_font) <= max_width:
            return current_font
    return font(min_size)


def wrap_text(draw, text, current_font, max_width):
    """Wrap words by rendered width, including a safe long-word fallback."""
    lines = []
    current = ""

    for word in text.split():
        trial = f"{current} {word}".strip()
        if not current or draw.textlength(trial, font=current_font) <= max_width:
            current = trial
            continue

        lines.append(current)
        current = word

    if current:
        lines.append(current)

    # The supplied statements do not contain long unbroken words, but keeping
    # this fallback makes the generator safe for future statements as well.
    safe_lines = []
    for line in lines:
        if draw.textlength(line, font=current_font) <= max_width:
            safe_lines.append(line)
            continue

        fragment = ""
        for character in line:
            trial = fragment + character
            if fragment and draw.textlength(trial, font=current_font) > max_width:
                safe_lines.append(fragment)
                fragment = character
            else:
                fragment = trial
        if fragment:
            safe_lines.append(fragment)

    return safe_lines


def fit_quote(draw, text, max_width, max_height, start_size=65, min_size=36):
    for size in range(start_size, min_size - 1, -1):
        current_font = quote_font(size)
        lines = wrap_text(draw, text, current_font, max_width)
        line_height = int(size * 1.28)
        if line_height * len(lines) <= max_height:
            return current_font, lines, line_height

    current_font = quote_font(min_size)
    return current_font, wrap_text(draw, text, current_font, max_width), int(min_size * 1.28)


def draw_baseline_text(draw, text, x, baseline, current_font, fill=TEMPLATE_NAVY, centered=False):
    if centered:
        x -= draw.textlength(text, font=current_font) / 2
    draw.text((x, baseline), text, font=current_font, fill=fill, anchor="ls")


def draw_quote(draw, quote):
    # This matches the quote block in the supplied artwork: white background,
    # centered Montserrat copy and generous vertical breathing room.
    quote_text = f"«{quote}»"
    left, top, right, bottom = 90, 860, 990, 1280
    current_font, lines, line_height = fit_quote(
        draw,
        quote_text,
        max_width=right - left,
        max_height=bottom - top,
    )

    block_height = line_height * len(lines)
    y = top + max(0, (bottom - top - block_height) // 2)
    for line in lines:
        width = draw.textlength(line, font=current_font)
        bbox = draw.textbbox((0, 0), line, font=current_font)
        # Pillow's default text origin is above the actual glyph box. Offset
        # it so the visible glyphs use the same centered block as the SVG.
        draw.text(
            ((W - width) / 2, y - bbox[1]),
            line,
            font=current_font,
            fill=TEMPLATE_NAVY,
        )
        y += line_height


def draw_person_photo(canvas, entry):
    """Place the statement-specific photo in the template's top frame."""
    if not entry["photo"].exists():
        raise FileNotFoundError(f"Personenfoto fehlt: {entry['photo']}")

    source = Image.open(entry["photo"]).convert("RGBA")
    # Flatten possible transparent source pixels against white before fitting
    # the image. This avoids black corners for the supplied RGBA portrait.
    flattened = Image.new("RGBA", source.size, (255, 255, 255, 255))
    flattened.alpha_composite(source)
    photo = ImageOps.fit(
        flattened.convert("RGB"),
        (PHOTO_BOX[2] - PHOTO_BOX[0], PHOTO_BOX[3] - PHOTO_BOX[1]),
        method=Image.Resampling.LANCZOS,
        centering=entry["focus"],
    )
    canvas.paste(photo, PHOTO_BOX[:2])


def draw_evp_logo(canvas):
    """Place the supplied EVP logo in the footer's former red-X slot."""
    if not EVP_LOGO_PATH.exists():
        raise FileNotFoundError(f"EVP-Logo fehlt: {EVP_LOGO_PATH}")

    logo = Image.open(EVP_LOGO_PATH).convert("RGBA")
    logo = ImageOps.contain(logo, EVP_LOGO_SIZE, method=Image.Resampling.LANCZOS)
    canvas.alpha_composite(logo, EVP_LOGO_POSITION)


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
    dict(
        slug="timo-wuersch",
        name="Timo Würsch",
        role="Co-Präsident GLP Schaffhausen",
        photo=STATEMENTS_DIR / "TimoWursch.jpg",
        focus=(0.5, 0.5),
        quote=(
            "Die Naturbadi Beringen ist nicht nur Ort für Spass, Sport und "
            "Entspannung, sondern mit ihrer chlorfreien Wasseraufbereitung "
            "ein Vorzeigeprojekt für umweltfreundliche, nachhaltige "
            "Spitzentechnologie. Solche Technologien stärken den lokalen "
            "Wirtschaftsstandort. Deshalb ein klares Ja!"
        ),
    ),
]


def build(entry, index):
    template_number = index % len(TEMPLATE_PATHS) + 1
    template_path = TEMPLATE_PATHS[template_number - 1]
    if not template_path.exists():
        raise FileNotFoundError(f"Designer-Vorlage fehlt: {template_path}")

    canvas, foreground = render_template(template_path, template_number)
    draw_person_photo(canvas, entry)
    canvas.alpha_composite(foreground)
    draw_evp_logo(canvas)
    draw = ImageDraw.Draw(canvas)

    name_font = fit_single_line(draw, entry["name"], 1000, 65, 40)
    role_font = fit_single_line(draw, entry["role"], 1000, 50, 32)
    draw_baseline_text(draw, entry["name"], 40.6, 710.3, name_font)
    draw_baseline_text(draw, entry["role"], W / 2, 773.7, role_font, centered=True)
    draw_quote(draw, entry["quote"])

    out_path = OUT_DIR / f"statement-{entry['slug']}.png"
    canvas.convert("RGB").save(out_path, format="PNG", optimize=True)
    print(f"wrote {out_path} (Vorlage {template_number:02d})")


def main():
    ensure_font()
    for index, entry in enumerate(STATEMENTS):
        build(entry, index)


if __name__ == "__main__":
    main()
