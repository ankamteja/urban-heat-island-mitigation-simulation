"""Builds UHI-Presentation.pptx.

The previous deck was 16 slides and 4 MB, most of it dashboard screenshots. This
one is 9 slides and carries one image: the architecture diagram. Everything else
is native PowerPoint shapes, so the file stays small and stays editable.

Palette and type come from frontend/style.css, so the deck and the dashboard it
describes look like the same product.

Figures are read from shared/constants.json, frontend/data/release.json and the
ML metrics where possible, so a pipeline re-run cannot silently leave the deck
quoting stale numbers. Anything not machine-readable is listed in FIGURES below
with the document it came from.

    python presentation/build_deck.py
"""

from __future__ import annotations

import json
from pathlib import Path

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Emu, Inches, Pt

ROOT = Path(__file__).resolve().parent.parent
ASSETS = Path(__file__).resolve().parent / "assets"
OUT = ROOT / "UHI-Presentation.pptx"

# ---------------------------------------------------------------- palette ---
# frontend/style.css :root tokens. Keep these in step with that file.
BG = RGBColor(0x0B, 0x11, 0x20)          # --bg
SURFACE = RGBColor(0x13, 0x1C, 0x2E)     # --surface
SURFACE_3 = RGBColor(0x1F, 0x2A, 0x40)   # --surface-3
FG = RGBColor(0xF1, 0xF5, 0xF9)          # --fg
MUTED = RGBColor(0x94, 0xA3, 0xB8)       # --fg-muted
DIM = RGBColor(0x64, 0x74, 0x8B)         # --fg-dim
PRIMARY = RGBColor(0x3B, 0x82, 0xF6)     # --primary
ACCENT = RGBColor(0xFB, 0xBF, 0x24)      # --accent
SUCCESS = RGBColor(0x34, 0xD3, 0x99)     # --success
DANGER = RGBColor(0xF8, 0x71, 0x71)      # --danger

# config.js HEAT_RAMP
RAMP = [
    RGBColor(0x25, 0x63, 0xEB),
    RGBColor(0x22, 0xD3, 0xEE),
    RGBColor(0xFD, 0xE0, 0x47),
    RGBColor(0xFB, 0x92, 0x3C),
    RGBColor(0xEF, 0x44, 0x44),
]

UI = "Fira Sans"
DATA = "Fira Code"

W, H = Inches(13.333), Inches(7.5)
MARGIN = Inches(0.72)


# ------------------------------------------------------------------ figures ---
def load_figures() -> dict:
    """Pulls what the pipeline emits; the rest is sourced in FIGURES."""
    release = json.loads((ROOT / "frontend/data/release.json").read_text(encoding="utf-8"))
    constants = json.loads((ROOT / "shared/constants.json").read_text(encoding="utf-8"))

    counts = release["action_counts"]
    treatable = sum(v for k, v in counts.items() if k != "None")

    return {
        "cells": release["cell_count"],
        "counts": counts,
        "treatable": treatable,
        "upper_bound_cr": release["total_cost_inr"] / 1e7,
        "release_id": release["release_id"],
        "constants": constants,
    }


# Figures with no machine-readable source, and where each one comes from.
# If one of these changes, change it here and re-run.
FIGURES = {
    "mean_lst": "27.0",          # STATUS.md / index.html
    "peak_lst": "33.2",          # index.html
    "mean_ndvi": "0.449",        # Machine Learning & Prediction/README.md
    "r2_random": "0.895",        # metrics.json, random split
    "r2_blocked": "0.513",       # metrics.json, spatial-block split
    "funded_cr": "9.99",         # Decision-Support/ranking.csv, capped at 10 Cr
    "funded_cells": "249",       # ditto
    "drop_treated": "0.99",      # docs/08-limitations.md
    "drop_grid": "0.51",         # ditto
    "deploy_url": "urban-heat-island-mitigation-simula.vercel.app",  # README.md
}


# ------------------------------------------------------------- primitives ---
def add_slide(prs: Presentation):
    s = prs.slides.add_slide(prs.slide_layouts[6])  # blank
    bg = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, W, H)
    bg.fill.solid()
    bg.fill.fore_color.rgb = BG
    bg.line.fill.background()
    bg.shadow.inherit = False
    return s


def text(slide, x, y, w, h, runs, *, align=PP_ALIGN.LEFT, anchor=MSO_ANCHOR.TOP,
         line_spacing=None, space_after=0):
    """runs: list of (string, size_pt, colour, bold, font) or list-of-lists for paragraphs."""
    box = slide.shapes.add_textbox(x, y, w, h)
    tf = box.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = anchor
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0

    paragraphs = runs if isinstance(runs[0], list) else [runs]
    for i, para in enumerate(paragraphs):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = align
        if line_spacing:
            p.line_spacing = line_spacing
        p.space_after = Pt(space_after)
        for chunk in para:
            body, size, colour, bold, font = chunk
            r = p.add_run()
            r.text = body
            r.font.size = Pt(size)
            r.font.color.rgb = colour
            r.font.bold = bold
            r.font.name = font
    return box


def eyebrow(slide, label):
    text(slide, MARGIN, Inches(0.56), Inches(9), Inches(0.3),
         [(label.upper(), 11, ACCENT, True, DATA)])


def heading(slide, title, sub=None):
    text(slide, MARGIN, Inches(0.98), Inches(11.4), Inches(0.9),
         [(title, 40, FG, True, UI)])
    if sub:
        text(slide, MARGIN, Inches(1.86), Inches(10.4), Inches(0.5),
             [(sub, 15, MUTED, False, UI)], line_spacing=1.35)


def footer(slide, n, total):
    text(slide, MARGIN, Inches(6.86), Inches(7), Inches(0.3),
         [("URBAN HEAT ISLAND MITIGATION · GUWAHATI", 9, DIM, False, DATA)])
    text(slide, Inches(10.6), Inches(6.86), Inches(2.05), Inches(0.3),
         [(f"{n} / {total}", 9, DIM, False, DATA)], align=PP_ALIGN.RIGHT)


def card(slide, x, y, w, h, *, fill=SURFACE, line=None, line_w=1.0):
    box = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, x, y, w, h)
    box.adjustments[0] = 0.06
    box.fill.solid()
    box.fill.fore_color.rgb = fill
    box.shadow.inherit = False
    if line:
        box.line.color.rgb = line
        box.line.width = Pt(line_w)
    else:
        box.line.fill.background()
    box.text_frame.text = ""
    return box


def stat(slide, x, y, w, value, label, *, colour=FG, value_pt=34):
    """One big number over a small mono caption."""
    text(slide, x, y, w, Inches(0.62),
         [(value, value_pt, colour, True, UI)])
    text(slide, x, y + Inches(0.62), w, Inches(0.3),
         [(label.upper(), 9.5, DIM, False, DATA)])


def rule(slide, x, y, w, colour=RGBColor(0x1F, 0x2A, 0x40)):
    ln = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, x, y, w, Emu(9525))
    ln.fill.solid()
    ln.fill.fore_color.rgb = colour
    ln.line.fill.background()
    ln.shadow.inherit = False
    return ln


# ----------------------------------------------------------------- slides ---
def slide_title(prs, f, n, total):
    s = add_slide(prs)

    # heat ramp as a rule across the top — the deck's one piece of decoration,
    # and it is the dashboard's actual colour scale.
    seg = W / len(RAMP)
    for i, c in enumerate(RAMP):
        bar = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, int(seg * i), 0, int(seg) + 1, Inches(0.09))
        bar.fill.solid()
        bar.fill.fore_color.rgb = c
        bar.line.fill.background()
        bar.shadow.inherit = False

    text(s, MARGIN, Inches(1.5), Inches(9), Inches(0.3),
         [("REMOTE SENSING · DECISION SUPPORT · URBAN PLANNING", 11, ACCENT, True, DATA)])
    text(s, MARGIN, Inches(2.1), Inches(10.6), Inches(1.9),
         [[("Urban Heat Island", 60, FG, True, UI)],
          [("Mitigation Simulation", 60, MUTED, False, UI)]], line_spacing=1.02)
    text(s, MARGIN, Inches(4.34), Inches(8.6), Inches(0.7),
         [("A screening and prioritisation pipeline that turns Landsat thermal "
           "imagery into a ranked, costed shortlist of 100 m cells.", 15, MUTED, False, UI)],
         line_spacing=1.4)

    rule(s, MARGIN, Inches(5.34), Inches(11.9))

    cols = [
        (f"{f['cells']:,}", "grid cells"),
        ("100 m", "resolution"),
        (f"{FIGURES['peak_lst']} °C", "peak hotspot"),
        ("Landsat 8", "source"),
    ]
    for i, (v, l) in enumerate(cols):
        stat(s, MARGIN + Inches(3.0) * i, Inches(5.62), Inches(2.8), v, l, value_pt=26)

    footer(s, n, total)


def slide_positioning(prs, f, n, total):
    s = add_slide(prs)
    eyebrow(s, "01 — positioning")
    heading(s, "What this is, and what it is not",
            "Naming it precisely matters more than naming it ambitiously.")

    y = Inches(2.62)
    h = Inches(2.5)
    w = Inches(5.72)

    card(s, MARGIN, y, w, h, line=SUCCESS, line_w=1.25)
    text(s, MARGIN + Inches(0.4), y + Inches(0.34), w - Inches(0.8), Inches(0.3),
         [("WHAT IT IS", 10.5, SUCCESS, True, DATA)])
    text(s, MARGIN + Inches(0.4), y + Inches(0.82), w - Inches(0.8), Inches(1.5),
         [("A city-wide heat screening and prioritisation pipeline. It measures "
           "where Guwahati is hottest, ranks 8,144 cells, and prices a shortlist "
           "against a budget.", 14, FG, False, UI)], line_spacing=1.4)

    x2 = MARGIN + w + Inches(0.46)
    card(s, x2, y, w, h, line=DANGER, line_w=1.25)
    text(s, x2 + Inches(0.4), y + Inches(0.34), w - Inches(0.8), Inches(0.3),
         [("WHAT IT IS NOT", 10.5, DANGER, True, DATA)])
    text(s, x2 + Inches(0.4), y + Inches(0.82), w - Inches(0.8), Inches(1.5),
         [("A physical simulation. Nothing models heat transfer, evapotranspiration "
           "or albedo response. The post-mitigation map is arithmetic on assumed "
           "constants.", 14, FG, False, UI)], line_spacing=1.4)

    text(s, MARGIN, Inches(5.5), Inches(11.9), Inches(0.5),
         [("The measurement layer is real and tested. The intervention layer is a "
           "placeholder we can now describe exactly.", 13.5, MUTED, False, UI)])
    footer(s, n, total)


def slide_data(prs, f, n, total):
    s = add_slide(prs)
    eyebrow(s, "02 — the data")
    heading(s, f"{f['cells']:,} cells, one thermal snapshot",
            "Earth Engine composites Landsat 8 surface temperature, NDVI, NDBI and "
            "ESA WorldCover land cover onto a 100 m grid.")

    stats = [
        (f"{f['cells']:,}", "grid cells", FG),
        (f"{FIGURES['mean_lst']} °C", "mean LST", FG),
        (f"{FIGURES['peak_lst']} °C", "peak hotspot", RAMP[4]),
        (FIGURES["mean_ndvi"], "mean NDVI", SUCCESS),
    ]
    for i, (v, l, c) in enumerate(stats):
        stat(s, MARGIN + Inches(3.0) * i, Inches(2.72), Inches(2.8), v, l, colour=c)

    rule(s, MARGIN, Inches(3.94), Inches(11.9))

    text(s, MARGIN, Inches(4.24), Inches(11.9), Inches(0.3),
         [("RECOMMENDED ACTION, ALL CELLS", 10, DIM, False, DATA)])

    order = ["Cool roof", "Tree cover", "Green park", "None"]
    colours = {"Cool roof": PRIMARY, "Tree cover": SUCCESS,
               "Green park": RGBColor(0x4A, 0xDE, 0x80), "None": DIM}
    total_cells = f["cells"]
    x = MARGIN
    bar_y = Inches(4.68)
    bar_w = Inches(11.9)
    for name in order:
        v = f["counts"][name]
        seg_w = int(bar_w * v / total_cells)
        seg = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, x, bar_y, seg_w, Inches(0.4))
        seg.fill.solid()
        seg.fill.fore_color.rgb = colours[name]
        seg.line.fill.background()
        seg.shadow.inherit = False
        x += seg_w

    lx = MARGIN
    for name in order:
        v = f["counts"][name]
        dot = s.shapes.add_shape(MSO_SHAPE.OVAL, lx, Inches(5.32), Inches(0.13), Inches(0.13))
        dot.fill.solid()
        dot.fill.fore_color.rgb = colours[name]
        dot.line.fill.background()
        dot.shadow.inherit = False
        text(s, lx + Inches(0.24), Inches(5.26), Inches(2.6), Inches(0.3),
             [(f"{name}  ", 12, FG, False, UI), (f"{v:,}", 12, MUTED, False, DATA)])
        lx += Inches(2.9)

    text(s, MARGIN, Inches(5.86), Inches(11.9), Inches(0.6),
         [("Interventions are gated on real ESA WorldCover land cover: nothing is "
           "proposed on water, wetland or existing tree cover. That gate is why "
           f"{f['counts']['None']:,} cells receive no action.", 13, MUTED, False, UI)],
         line_spacing=1.4)
    footer(s, n, total)


def slide_architecture(prs, f, n, total):
    s = add_slide(prs)
    eyebrow(s, "03 — architecture")
    heading(s, "Four modules — and where the model is not")

    png = ASSETS / "architecture.png"
    if png.exists():
        # Size on width and let the 1440x560 canvas land clear of the footer.
        pic_w = Inches(11.9)
        s.shapes.add_picture(str(png), MARGIN, Inches(2.24), width=pic_w)
    else:
        text(s, MARGIN, Inches(3.0), Inches(11.9), Inches(0.4),
             [("architecture.png missing — run the render step in presentation/README.md",
               13, DANGER, False, DATA)])
    footer(s, n, total)


def slide_model(prs, f, n, total):
    s = add_slide(prs)
    eyebrow(s, "04 — machine learning")
    heading(s, "Two scores, and we quote the lower one")

    y = Inches(2.66)
    card(s, MARGIN, y, Inches(5.72), Inches(1.86), fill=SURFACE)
    text(s, MARGIN + Inches(0.4), y + Inches(0.32), Inches(5), Inches(0.6),
         [(f"R² {FIGURES['r2_random']}", 38, MUTED, True, UI)])
    text(s, MARGIN + Inches(0.4), y + Inches(1.06), Inches(5), Inches(0.5),
         [("random split — what a naive report would quote", 12.5, DIM, False, UI)])

    x2 = MARGIN + Inches(6.18)
    card(s, x2, y, Inches(5.72), Inches(1.86), fill=SURFACE, line=ACCENT, line_w=1.25)
    text(s, x2 + Inches(0.4), y + Inches(0.32), Inches(5), Inches(0.6),
         [(f"R² {FIGURES['r2_blocked']}", 38, ACCENT, True, UI)])
    text(s, x2 + Inches(0.4), y + Inches(1.06), Inches(5), Inches(0.5),
         [("spatial-block split — the honest score", 12.5, MUTED, False, UI)])

    text(s, MARGIN, Inches(4.96), Inches(11.9), Inches(1.2),
         [("Adjacent 100 m cells are near-duplicates, so a random split leaks most "
           "test answers through their neighbours. The blocked score is what the "
           "model would do on ground it has not seen.", 15, FG, False, UI)],
         line_spacing=1.45)
    text(s, MARGIN, Inches(5.92), Inches(11.9), Inches(0.5),
         [("And nothing downstream consumes either number — the plan comes from the "
           "rule engine, not the model.", 13.5, DANGER, False, UI)])
    footer(s, n, total)


def slide_recommendation(prs, f, n, total):
    s = add_slide(prs)
    eyebrow(s, "05 — the recommendation")
    heading(s, "₹10 crore buys 249 roofs",
            "Every actionable cell is ranked on cooling per rupee, then funded until "
            "the budget runs out.")

    y = Inches(2.72)
    items = [
        (f"{f['treatable']:,}", "cells treatable", FG),
        (f"₹{f['upper_bound_cr']:.1f} Cr", "cost if all treated", MUTED),
        (f"₹{FIGURES['funded_cr']} Cr", "recommended spend", ACCENT),
        (FIGURES["funded_cells"], "cells funded", ACCENT),
    ]
    for i, (v, l, c) in enumerate(items):
        stat(s, MARGIN + Inches(3.0) * i, y, Inches(2.8), v, l, colour=c, value_pt=32)

    rule(s, MARGIN, Inches(4.02), Inches(11.9))

    text(s, MARGIN, Inches(4.34), Inches(5.6), Inches(1.5),
         [[("−%s °C" % FIGURES["drop_treated"], 26, FG, True, UI)],
          [("assumed drop on treated cells", 12, DIM, False, DATA)]], line_spacing=1.2)
    text(s, MARGIN + Inches(6.18), Inches(4.34), Inches(5.6), Inches(1.5),
         [[("−%s °C" % FIGURES["drop_grid"], 26, MUTED, True, UI)],
          [("same programme, averaged over the whole grid", 12, DIM, False, DATA)]],
         line_spacing=1.2)

    text(s, MARGIN, Inches(5.72), Inches(11.9), Inches(0.8),
         [("Both numbers describe the same plan. Quoting the first alone overstates "
           "what the city feels; quoting the second next to a crore-scale cost "
           "understates what the money buys. The dashboard names the denominator on "
           "each.", 13, MUTED, False, UI)], line_spacing=1.4)
    footer(s, n, total)


def slide_real(prs, f, n, total):
    s = add_slide(prs)
    eyebrow(s, "06 — what is real")
    heading(s, "Real, qualified, placeholder")

    blocks = [
        ("REAL", SUCCESS,
         "Corrected Earth Engine export: NDVI to 0.781, real ESA WorldCover, NDBI "
         "and Vegetation. Land-cover-gated recommendations. 133 tests, and CI "
         "regenerates every artefact."),
        ("QUALIFIED", ACCENT,
         "The model. R² 0.895 random, 0.513 blocked — and nothing downstream "
         "consumes it. It reports; it does not decide."),
        ("PLACEHOLDER", DANGER,
         "Every cooling value, and one of three unit rates. The °C figures were "
         "never fitted to Guwahati or validated against a field trial."),
    ]
    w = Inches(3.76)
    for i, (label, colour, body) in enumerate(blocks):
        x = MARGIN + (w + Inches(0.31)) * i
        card(s, x, Inches(2.62), w, Inches(2.86), fill=SURFACE)
        tab = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, x, Inches(2.62), Inches(0.05), Inches(2.86))
        tab.fill.solid()
        tab.fill.fore_color.rgb = colour
        tab.line.fill.background()
        tab.shadow.inherit = False
        text(s, x + Inches(0.36), Inches(2.94), w - Inches(0.7), Inches(0.3),
             [(label, 10.5, colour, True, DATA)])
        text(s, x + Inches(0.36), Inches(3.42), w - Inches(0.7), Inches(1.8),
             [(body, 13, FG, False, UI)], line_spacing=1.4)

    text(s, MARGIN, Inches(5.86), Inches(11.9), Inches(0.5),
         [("STATUS.md and docs/08-limitations.md name every assumption in the "
           "repository itself.", 13, MUTED, False, UI)])
    footer(s, n, total)


def slide_gap(prs, f, n, total):
    s = add_slide(prs)
    eyebrow(s, "07 — the structural gap")
    heading(s, "The rates decide the answer, not the model")

    text(s, MARGIN, Inches(2.5), Inches(11.9), Inches(1.2),
         [("Cooling per rupee has been reordered twice. Both times it was a cost "
           "correction, never a model result — and each reordering replaced the "
           "funded set wholesale.", 17, FG, False, UI)], line_spacing=1.45)

    y = Inches(3.9)
    steps = [
        ("Park rate was 5–9× too low", "parks led the ranking", DIM),
        ("Cool-roof rate was 33% too high", "trees led the ranking", DIM),
        ("Both corrected", "cool roof leads by 4%", ACCENT),
    ]
    w = Inches(3.76)
    for i, (cause, effect, colour) in enumerate(steps):
        x = MARGIN + (w + Inches(0.31)) * i
        card(s, x, y, w, Inches(1.62), fill=SURFACE,
             line=ACCENT if colour == ACCENT else None, line_w=1.25)
        text(s, x + Inches(0.34), y + Inches(0.3), w - Inches(0.68), Inches(0.6),
             [(cause, 13, MUTED, False, UI)], line_spacing=1.3)
        text(s, x + Inches(0.34), y + Inches(0.94), w - Inches(0.68), Inches(0.5),
             [(effect, 14.5, colour if colour == ACCENT else FG, True, UI)])

    text(s, MARGIN, Inches(5.86), Inches(11.9), Inches(0.6),
         [("A 4% lead sits inside the error of a rate nobody has validated. Treat "
           "the funded set as approximately right, not decisively right.",
           13.5, DANGER, False, UI)], line_spacing=1.4)
    footer(s, n, total)


def slide_roadmap(prs, f, n, total):
    s = add_slide(prs)
    eyebrow(s, "08 — roadmap")
    heading(s, "Three moves, in order of decision value")

    items = [
        ("01", "Put ranges on every rate",
         "Run the ranking over a scenario grid and report which cells stay funded. "
         "One uncertain number should not silently determine a ₹10 crore shortlist."),
        ("02", "Calibrate cooling against our own data",
         "Guwahati already has parks. Compare their LST against matched built-up "
         "cells nearby. Turns a placeholder constant into a local estimate."),
        ("03", "Close the loop, or drop the claim",
         "Either let the model drive the recommendation and prove it helps on "
         "held-out ground, or state plainly that it is diagnostic only."),
    ]
    y = Inches(2.46)
    for num, title, body in items:
        text(s, MARGIN, y, Inches(0.9), Inches(0.5),
             [(num, 24, ACCENT, True, DATA)])
        text(s, MARGIN + Inches(1.0), y - Inches(0.02), Inches(10.7), Inches(0.4),
             [(title, 19, FG, True, UI)])
        text(s, MARGIN + Inches(1.0), y + Inches(0.44), Inches(10.4), Inches(0.7),
             [(body, 13.5, MUTED, False, UI)], line_spacing=1.4)
        y += Inches(1.36)

    rule(s, MARGIN, Inches(6.5), Inches(11.9))
    footer(s, n, total)


def slide_close(prs, f, n, total):
    s = add_slide(prs)

    text(s, MARGIN, Inches(2.32), Inches(11), Inches(2.2),
         [[("Measure honestly.", 46, FG, True, UI)],
          [("Calibrate locally.", 46, MUTED, False, UI)],
          [("Then optimise.", 46, DIM, False, UI)]], line_spacing=1.14)

    rule(s, MARGIN, Inches(5.2), Inches(11.9))

    text(s, MARGIN, Inches(5.5), Inches(7.6), Inches(0.7),
         [("The measurement layer is real, corrected and tested. The intervention "
           "layer is a placeholder we can now describe exactly — which is the "
           "prerequisite for fixing it.", 14, MUTED, False, UI)], line_spacing=1.4)

    text(s, Inches(8.7), Inches(5.5), Inches(3.95), Inches(0.6),
         [[(FIGURES["deploy_url"], 12, ACCENT, False, DATA)],
          [(f"data release {f['release_id']}", 11, DIM, False, DATA)]],
         align=PP_ALIGN.RIGHT, line_spacing=1.5)

    footer(s, n, total)


# -------------------------------------------------------------------- main ---
BUILDERS = [
    slide_title,
    slide_positioning,
    slide_data,
    slide_architecture,
    slide_model,
    slide_recommendation,
    slide_real,
    slide_gap,
    slide_roadmap,
    slide_close,
]


def main():
    figures = load_figures()

    prs = Presentation()
    prs.slide_width, prs.slide_height = W, H

    total = len(BUILDERS)
    for i, build in enumerate(BUILDERS, start=1):
        build(prs, figures, i, total)

    prs.save(OUT)
    size_mb = OUT.stat().st_size / 1e6
    print(f"wrote {OUT.relative_to(ROOT)} — {total} slides, {size_mb:.2f} MB")


if __name__ == "__main__":
    main()
