"""Builds UHI-Presentation.pptx — a 10-slide hackathon deck.

Structure follows the judging brief: problem, solution, data + architecture,
key result, live demo, safety and trust, impact, limitations and next step,
wrapped in a title and a close.

Two rules the deck holds to, because both are credibility risks:

  1. Cooling values are planning assumptions used to compare scenarios, never
     measured guarantees. Every slide that shows a degree figure says so.
  2. The model is not the decision-maker. The visible recommendation comes from
     an auditable rule and cost engine, and the deck says that plainly rather
     than implying "AI predicts the future".

Palette and type come from frontend/style.css, so the deck and the dashboard it
describes look like the same product. Figures are read from the pipeline's own
outputs where possible; the rest are in FIGURES with their source.

    python presentation/build_deck.py
"""

from __future__ import annotations

import json
from pathlib import Path

from lxml import etree
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.oxml.ns import qn
from pptx.util import Emu, Inches, Pt

ROOT = Path(__file__).resolve().parent.parent
ASSETS = Path(__file__).resolve().parent / "assets"
OUT = ROOT / "UHI-Presentation.pptx"

# ---------------------------------------------------------------- palette ---
# frontend/style.css :root tokens. Keep these in step with that file.
BG = RGBColor(0x0C, 0x10, 0x17)          # --bg
SURFACE = RGBColor(0x11, 0x16, 0x1F)     # --surface
SURFACE_3 = RGBColor(0x1C, 0x24, 0x31)   # --surface-3
FG = RGBColor(0xE8, 0xEA, 0xF0)          # --fg
MUTED = RGBColor(0x9A, 0xA6, 0xBC)       # --fg-2
DIM = RGBColor(0x6B, 0x78, 0x91)         # --fg-3
PRIMARY = RGBColor(0x4C, 0x8D, 0xD9)     # --accent, the one interface accent
ACCENT = RGBColor(0xE0, 0xA2, 0x3C)      # --warn, reserved for emphasis
SUCCESS = RGBColor(0x5E, 0x9E, 0x7E)     # --ok
DANGER = RGBColor(0xD8, 0x63, 0x5F)      # --danger

# config.js HEAT_RAMP — magma, the same sequential ramp the dashboard uses.
# Deliberately not a rainbow: equal steps in temperature are equal steps in
# perceived brightness, so the title bar reads as a scale rather than decoration.
RAMP = [
    RGBColor(0x28, 0x10, 0x4A),
    RGBColor(0x5E, 0x17, 0x6C),
    RGBColor(0x94, 0x28, 0x6C),
    RGBColor(0xCC, 0x3E, 0x5B),
    RGBColor(0xF6, 0x6E, 0x5C),
    RGBColor(0xFC, 0xBB, 0x8C),
]

UI = "Inter"
DATA = "IBM Plex Mono"

W, H = Inches(13.333), Inches(7.5)
MARGIN = Inches(0.72)

REPO = "https://github.com/ankamteja/urban-heat-island-mitigation-simulation"
LINKS = {
    "repo": REPO,
    "docs": f"{REPO}/tree/main/docs",
    "site": "https://urban-heat-island-mitigation-simula.vercel.app",
    "dashboard": "https://urban-heat-island-mitigation-simula.vercel.app/frontend",
}


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
FIGURES = {
    "mean_lst": "27.0",          # STATUS.md / index.html
    "peak_lst": "33.2",          # index.html
    "mean_ndvi": "0.449",        # Machine Learning & Prediction/README.md
    "r2_blocked": "0.513",       # metrics.json, spatial-block split
    "funded_cr": "9.99",         # Decision-Support/ranking.csv, capped at 10 Cr
    "funded_cells": "249",       # ditto
    # The 10 Cr plan, not the whole programme. Pairing the 249-cell headline
    # with the all-4,157-cells drop was the exact denominator mismatch the
    # dashboard exists to prevent.
    "drop_treated": "1.00",      # dashboard, 249 funded cells at 10 Cr
    "drop_grid": "0.03",         # same plan, averaged over all 8,144 cells
    "drop_all_treated": "0.99",  # if all 4,157 eligible were treated
    "drop_all_grid": "0.51",     # ditto, over the whole grid
    "tests": "133",              # pytest tests/
    "hotspots_before": "530",    # top decile of the observed range
    "hotspots_after": "350",     # same, after the funded plan
    "excluded_green": "3,752",   # STATUS.md, already tree cover
    "excluded_water": "193",     # STATUS.md, 149 water + 44 wetland
}


# ------------------------------------------------------------- primitives ---
HLINK_CLR_NS = "http://schemas.microsoft.com/office/drawing/2018/hyperlinkcolor"
HLINK_EXT_URI = "{A12FA001-AC4F-418D-AE19-62706E023703}"


def link_uses_text_colour(run):
    """Stop PowerPoint repainting a link run in theme blue with an underline.

    A run's own <a:solidFill> loses to the theme's hyperlink colour, so setting
    font.color alone has no visible effect. The 2018 hlinkClr extension is the
    supported way to say "use the text colour", which is what keeps the links on
    the deck's palette instead of Office default blue.
    """
    rPr = run._r.get_or_add_rPr()
    rPr.set("u", "none")
    hlink = rPr.find(qn("a:hlinkClick"))
    if hlink is None:
        return
    ext_lst = etree.SubElement(hlink, qn("a:extLst"))
    ext = etree.SubElement(ext_lst, qn("a:ext"))
    ext.set("uri", HLINK_EXT_URI)
    clr = etree.SubElement(ext, f"{{{HLINK_CLR_NS}}}hlinkClr")
    clr.set("val", "tx")


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
    """runs: (body, size, colour, bold, font) or (..., font, link) per chunk.

    A list of chunks is one paragraph; a list of lists is several.
    """
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
            body, size, colour, bold, font = chunk[:5]
            link = chunk[5] if len(chunk) > 5 else None
            r = p.add_run()
            r.text = body
            r.font.size = Pt(size)
            r.font.bold = bold
            r.font.name = font
            r.font.color.rgb = colour
            if link:
                r.hyperlink.address = link
                link_uses_text_colour(r)
    return box


def eyebrow(slide, label):
    text(slide, MARGIN, Inches(0.56), Inches(9), Inches(0.3),
         [(label.upper(), 11, ACCENT, True, DATA)])


def heading(slide, title, sub=None, *, size=40):
    text(slide, MARGIN, Inches(0.98), Inches(11.9), Inches(0.9),
         [(title, size, FG, True, UI)])
    if sub:
        text(slide, MARGIN, Inches(1.86), Inches(10.8), Inches(0.5),
             [(sub, 15, MUTED, False, UI)], line_spacing=1.35)


def footer(slide, n, total, *, link=None, link_label=None):
    if link:
        text(slide, MARGIN, Inches(6.86), Inches(9), Inches(0.3),
             [("↗ ", 9, ACCENT, False, DATA),
              (link_label or link, 9, ACCENT, False, DATA, link)])
    else:
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
    text(slide, x, y, w, Inches(0.62), [(value, value_pt, colour, True, UI)])
    text(slide, x, y + Inches(0.62), w, Inches(0.3),
         [(label.upper(), 9.5, DIM, False, DATA)])


def rule(slide, x, y, w, colour=SURFACE_3):
    ln = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, x, y, w, Emu(9525))
    ln.fill.solid()
    ln.fill.fore_color.rgb = colour
    ln.line.fill.background()
    ln.shadow.inherit = False
    return ln


def claim(slide, y, body, *, colour=ACCENT, size=17):
    """The one-line assertion a judge should leave the slide with."""
    bar = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, MARGIN, y, Inches(0.05), Inches(0.62))
    bar.fill.solid()
    bar.fill.fore_color.rgb = colour
    bar.line.fill.background()
    bar.shadow.inherit = False
    text(slide, MARGIN + Inches(0.28), y + Inches(0.04), Inches(11.4), Inches(0.6),
         [(body, size, colour, False, UI)], line_spacing=1.35)


# ----------------------------------------------------------------- slides ---
def slide_title(prs, f, n, total):
    s = add_slide(prs)

    seg = W / len(RAMP)
    for i, c in enumerate(RAMP):
        bar = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, int(seg * i), 0, int(seg) + 1, Inches(0.09))
        bar.fill.solid()
        bar.fill.fore_color.rgb = c
        bar.line.fill.background()
        bar.shadow.inherit = False

    text(s, MARGIN, Inches(1.24), Inches(9), Inches(0.3),
         [("REMOTE SENSING · DECISION SUPPORT · URBAN PLANNING", 11, ACCENT, True, DATA)])
    text(s, MARGIN, Inches(1.82), Inches(11.4), Inches(1.7),
         [[("Urban Heat Island", 56, FG, True, UI)],
          [("Mitigation Simulation", 56, MUTED, False, UI)]], line_spacing=1.02)

    text(s, MARGIN, Inches(3.96), Inches(11.2), Inches(0.9),
         [("We turn satellite-derived urban heat data into a ", 18, FG, False, UI),
          ("safe, ranked, cost-aware mitigation plan", 18, ACCENT, True, UI),
          (" that a city planner can explore immediately.", 18, FG, False, UI)],
         line_spacing=1.4)

    rule(s, MARGIN, Inches(5.16), Inches(11.9))

    cols = [
        (f"{f['cells']:,}", "cells mapped"),
        (f"{f['treatable']:,}", "actionable"),
        (f"₹{FIGURES['funded_cr']} Cr", "ranked shortlist"),
        (FIGURES["funded_cells"], "cells funded"),
    ]
    for i, (v, l) in enumerate(cols):
        stat(s, MARGIN + Inches(3.0) * i, Inches(5.44), Inches(2.8), v, l, value_pt=26)

    text(s, MARGIN, Inches(6.86), Inches(11.9), Inches(0.3),
         [("↗ live dashboard  ", 10, ACCENT, False, DATA, LINKS["dashboard"]),
          ("   ·   ", 10, DIM, False, DATA),
          ("↗ source", 10, ACCENT, False, DATA, LINKS["repo"])])
    text(s, Inches(10.6), Inches(6.86), Inches(2.05), Inches(0.3),
         [(f"{n} / {total}", 9, DIM, False, DATA)], align=PP_ALIGN.RIGHT)


def slide_problem(prs, f, n, total):
    s = add_slide(prs)
    eyebrow(s, "01 — the problem")
    heading(s, "Heat is uneven. Budgets are not infinite.")

    png = ASSETS / "dash-overview.jpg"
    if png.exists():
        s.shapes.add_picture(str(png), Inches(6.2), Inches(1.98), width=Inches(6.42))

    text(s, MARGIN, Inches(2.06), Inches(5.1), Inches(2.6),
         [("Guwahati's surface temperature spans "
           f"{FIGURES['mean_lst']} °C on average and peaks at {FIGURES['peak_lst']} °C — "
           "and the hot ground is not where you would guess. It clusters, block "
           "by block, on built-up surface.", 15, FG, False, UI)], line_spacing=1.45)

    text(s, MARGIN, Inches(4.06), Inches(5.1), Inches(1.6),
         [("A city cannot cool every block. It has to choose a few hundred, "
           "defend the choice, and price it.", 15, MUTED, False, UI)],
         line_spacing=1.45)

    claim(s, Inches(5.42),
          "Choosing well needs a map at the scale of the decision — 100 m, not district averages.")
    footer(s, n, total)


def slide_solution(prs, f, n, total):
    s = add_slide(prs)
    eyebrow(s, "02 — the solution")
    heading(s, "Four steps, each one auditable")

    steps = [
        ("SATELLITE", "Landsat 8 + ESA\nWorldCover", PRIMARY),
        ("HEAT-RISK GRID", f"{f['cells']:,} cells\nat 100 m", RAMP[3]),
        ("SUITABILITY RULES", "gated on real\nland cover", SUCCESS),
        ("RANKED PLAN", "cooling per rupee,\ncapped at budget", ACCENT),
    ]

    y = Inches(2.6)
    cw, gap = Inches(2.72), Inches(0.36)
    for i, (label, body, colour) in enumerate(steps):
        x = MARGIN + (cw + gap) * i
        card(s, x, y, cw, Inches(1.98), fill=SURFACE,
             line=colour if colour == ACCENT else None, line_w=1.25)
        tab = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, x, y, cw, Inches(0.05))
        tab.fill.solid()
        tab.fill.fore_color.rgb = colour
        tab.line.fill.background()
        tab.shadow.inherit = False

        text(s, x + Inches(0.3), y + Inches(0.34), cw - Inches(0.6), Inches(0.3),
             [(label, 10, colour, True, DATA)])
        text(s, x + Inches(0.3), y + Inches(0.82), cw - Inches(0.6), Inches(1.0),
             [(body, 14, FG, False, UI)], line_spacing=1.35)

        if i < len(steps) - 1:
            text(s, x + cw, y + Inches(0.82), gap, Inches(0.4),
                 [("→", 16, DIM, False, UI)], align=PP_ALIGN.CENTER)

    text(s, MARGIN, Inches(5.02), Inches(11.9), Inches(0.9),
         [("No step is a black box. Every funded cell can be traced back to its "
           "temperature, its land cover, the rule that admitted it and the rate "
           "that priced it.", 15, FG, False, UI)], line_spacing=1.45)

    claim(s, Inches(5.94),
          "Decision support, not prediction — the planner stays in the loop at every step.")
    footer(s, n, total)


def slide_architecture(prs, f, n, total):
    s = add_slide(prs)
    eyebrow(s, "03 — data and architecture")
    heading(s, "Real data in, auditable plan out")

    png = ASSETS / "architecture.png"
    if png.exists():
        s.shapes.add_picture(str(png), MARGIN, Inches(2.24), width=Inches(11.9))
    else:
        text(s, MARGIN, Inches(3.0), Inches(11.9), Inches(0.4),
             [("architecture.png missing — see presentation/README.md",
               13, DANGER, False, DATA)])
    footer(s, n, total, link=LINKS["docs"], link_label="full technical docs")


def slide_result(prs, f, n, total):
    s = add_slide(prs)
    eyebrow(s, "04 — key result")
    heading(s, "₹10 crore, spent where it is defensible",
            "Every actionable cell ranked on cooling per rupee, then funded until "
            "the budget runs out.")

    items = [
        (f"{f['cells']:,}", "cells mapped", FG),
        (f"{f['treatable']:,}", "actionable after safety rules", FG),
        (f"₹{FIGURES['funded_cr']} Cr", "ranked shortlist", ACCENT),
        (FIGURES["funded_cells"], "cells funded", ACCENT),
    ]
    for i, (v, l, c) in enumerate(items):
        stat(s, MARGIN + Inches(3.0) * i, Inches(2.72), Inches(2.9), v, l,
             colour=c, value_pt=32)

    rule(s, MARGIN, Inches(4.08), Inches(11.9))

    text(s, MARGIN, Inches(4.4), Inches(5.6), Inches(1.2),
         [[("−%s °C" % FIGURES["drop_treated"], 26, FG, True, UI)],
          [("on the 249 funded cells", 12, DIM, False, DATA)]], line_spacing=1.2)
    text(s, MARGIN + Inches(6.18), Inches(4.4), Inches(5.6), Inches(1.2),
         [[("−%s °C" % FIGURES["drop_grid"], 26, MUTED, True, UI)],
          [("same plan, averaged over all 8,144 cells", 12, DIM, False, DATA)]],
         line_spacing=1.2)

    text(s, MARGIN, Inches(5.5), Inches(11.9), Inches(0.4),
         [("Hotspot cells (top decile) fall from ", 14, FG, False, UI),
          (f"{FIGURES['hotspots_before']} to {FIGURES['hotspots_after']}", 14, ACCENT, True, UI),
          (" — the plan now buys the hottest eligible roofs, not the ones that "
           "happened to sort first.", 14, FG, False, UI)], line_spacing=1.4)

    claim(s, Inches(6.06),
          "Cooling values are planning assumptions used to compare scenarios, "
          "not measured guarantees.", colour=DANGER, size=15)
    footer(s, n, total)


def slide_demo(prs, f, n, total):
    s = add_slide(prs)
    eyebrow(s, "05 — interactive demo")
    heading(s, "Click a cell. Get a defensible answer.")

    png = ASSETS / "dash-compare.jpg"
    if png.exists():
        # Height-constrained: the space under the heading is ~4.3in, so sizing on
        # width would run the image off the bottom of the slide.
        pic_h = Inches(4.32)
        pic_w = Inches(4.32 * 1600 / 838)
        s.shapes.add_picture(str(png), int((W - pic_w) / 2), Inches(1.98),
                             width=int(pic_w), height=int(pic_h))

    text(s, MARGIN, Inches(6.46), Inches(11.9), Inches(0.4),
         [("Click any cell for why it ranks, what the rule engine proposes, what it "
           "costs, and a Street View link to go and look at the roof.",
           13, MUTED, False, UI)], align=PP_ALIGN.CENTER)
    footer(s, n, total, link=LINKS["dashboard"], link_label="try it live")


def slide_safety(prs, f, n, total):
    s = add_slide(prs)
    eyebrow(s, "06 — safety and trust")
    heading(s, "The rules that stop a bad recommendation")

    blocks = [
        ("NO WORK ON WATER OR WETLAND", SUCCESS,
         f"{FIGURES['excluded_water']} water and wetland cells excluded in code, not "
         "by convention. ESA WorldCover gates every measure."),
        ("NO PLANTING ON EXISTING CANOPY", SUCCESS,
         f"{FIGURES['excluded_green']} cells already classified as tree cover get no "
         "planting recommendation. The gate is asserted by tests."),
        ("CHECK IT ON THE GROUND", ACCENT,
         "Every cell links straight to Google Street View at its own coordinates, "
         "with the place name and the 100 m box it covers."),
        ("REPRODUCIBLE AND OPEN", PRIMARY,
         f"{FIGURES['tests']} passing tests. CI regenerates every artefact and fails "
         "if a committed copy differs. MIT licensed."),
    ]
    w, gap = Inches(2.78), Inches(0.26)
    for i, (label, colour, body) in enumerate(blocks):
        x = MARGIN + (w + gap) * i
        card(s, x, Inches(2.5), w, Inches(2.72), fill=SURFACE)
        tab = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, x, Inches(2.5), Inches(0.05), Inches(2.72))
        tab.fill.solid()
        tab.fill.fore_color.rgb = colour
        tab.line.fill.background()
        tab.shadow.inherit = False
        text(s, x + Inches(0.3), Inches(2.8), w - Inches(0.6), Inches(0.5),
             [(label, 9.5, colour, True, DATA)], line_spacing=1.3)
        text(s, x + Inches(0.3), Inches(3.42), w - Inches(0.6), Inches(1.8),
             [(body, 12.5, FG, False, UI)], line_spacing=1.4)

    claim(s, Inches(5.52),
          "A tool a city can act on has to be wrong safely. These rules are the "
          "difference between a demo and a proposal.")
    footer(s, n, total, link=LINKS["docs"], link_label="limitations and data contracts")


def slide_impact(prs, f, n, total):
    s = add_slide(prs)
    eyebrow(s, "07 — impact")
    heading(s, "What a planner can do on Monday")

    rows = [
        ("Compare, not guess",
         "Draw a box over any ward and get its cell count, mean temperature, "
         "eligible measures and cost — in seconds, not a procurement cycle."),
        ("Defend the shortlist",
         "Every funded cell carries its temperature, land cover, measure and price. "
         "The ranking is reproducible from the repository."),
        ("Re-run when the data moves",
         "A scheduled Earth Engine refresh regenerates the grid; the release "
         "manifest ties the dashboard to an exact dataset."),
    ]
    y = Inches(2.5)
    for title, body in rows:
        text(s, MARGIN, y, Inches(3.5), Inches(0.4), [(title, 18, ACCENT, True, UI)])
        text(s, MARGIN + Inches(3.8), y + Inches(0.02), Inches(8.1), Inches(0.8),
             [(body, 14, FG, False, UI)], line_spacing=1.4)
        y += Inches(1.16)

    rule(s, MARGIN, Inches(5.92), Inches(11.9))
    claim(s, Inches(6.08),
          "The output is a shortlist a committee can argue with — which is what "
          "makes it usable.")
    footer(s, n, total)


def slide_limits(prs, f, n, total):
    s = add_slide(prs)
    eyebrow(s, "08 — limitations and next step")
    heading(s, "What we would validate first")

    y = Inches(2.44)
    card(s, MARGIN, y, Inches(5.72), Inches(2.4), fill=SURFACE, line=DANGER, line_w=1.25)
    text(s, MARGIN + Inches(0.4), y + Inches(0.32), Inches(5), Inches(0.3),
         [("KNOWN LIMITATION", 10, DANGER, True, DATA)])
    text(s, MARGIN + Inches(0.4), y + Inches(0.8), Inches(4.94), Inches(1.4),
         [("Cooling values are planning assumptions, never fitted to Guwahati or "
           "validated against a field trial. One of three unit rates is still "
           "unanchored. The analysis is one thermal snapshot.",
           14, FG, False, UI)], line_spacing=1.4)

    x2 = MARGIN + Inches(6.18)
    card(s, x2, y, Inches(5.72), Inches(2.4), fill=SURFACE, line=SUCCESS, line_w=1.25)
    text(s, x2 + Inches(0.4), y + Inches(0.32), Inches(5), Inches(0.3),
         [("NEXT STEP", 10, SUCCESS, True, DATA)])
    text(s, x2 + Inches(0.4), y + Inches(0.8), Inches(4.94), Inches(1.4),
         [("Validate cooling with repeated observations: compare existing parks "
           "and canopy against matched built-up cells across seasons, then replace "
           "each constant with a local estimate and a range.",
           14, FG, False, UI)], line_spacing=1.4)

    text(s, MARGIN, Inches(5.24), Inches(11.9), Inches(0.8),
         [("We publish the limitations because a planning tool that hides them is "
           "worse than no tool. The measurement layer is real and tested; the "
           "intervention layer is a placeholder we can now describe exactly — which "
           "is the prerequisite for fixing it.", 14, MUTED, False, UI)],
         line_spacing=1.45)

    footer(s, n, total, link=LINKS["docs"], link_label="every assumption, documented")


def slide_close(prs, f, n, total):
    s = add_slide(prs)

    text(s, MARGIN, Inches(1.96), Inches(11.4), Inches(1.6),
         [("From satellite pixels to a", 40, MUTED, False, UI)])
    text(s, MARGIN, Inches(2.66), Inches(11.4), Inches(1.6),
         [("defensible urban cooling shortlist.", 40, FG, True, UI)])

    rule(s, MARGIN, Inches(3.92), Inches(11.9))

    cols = [
        ("Live site", LINKS["site"], "urban-heat-island-mitigation-simula.vercel.app"),
        ("Dashboard", LINKS["dashboard"], ".../frontend"),
        ("Source", LINKS["repo"], "github.com/ankamteja/…-simulation"),
        ("Docs", LINKS["docs"], ".../tree/main/docs"),
    ]
    y = Inches(4.26)
    for i, (label, url, shown) in enumerate(cols):
        x = MARGIN + Inches(3.0) * i
        text(s, x, y, Inches(2.85), Inches(0.3),
             [(label.upper(), 9.5, DIM, False, DATA)])
        text(s, x, y + Inches(0.32), Inches(2.85), Inches(0.7),
             [("↗ ", 11, ACCENT, False, DATA, url),
              (shown, 11, ACCENT, False, DATA, url)], line_spacing=1.3)

    text(s, MARGIN, Inches(5.72), Inches(11.9), Inches(0.6),
         [("Guwahati, Assam · Landsat 8 · 100 m grid · "
           f"{f['cells']:,} cells · data release {f['release_id']} · MIT licensed",
           12, DIM, False, DATA)])

    text(s, Inches(10.6), Inches(6.86), Inches(2.05), Inches(0.3),
         [(f"{n} / {total}", 9, DIM, False, DATA)], align=PP_ALIGN.RIGHT)


# -------------------------------------------------------------------- main ---
BUILDERS = [
    slide_title,
    slide_problem,
    slide_solution,
    slide_architecture,
    slide_result,
    slide_demo,
    slide_safety,
    slide_impact,
    slide_limits,
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
    print(f"wrote {OUT.relative_to(ROOT)} — {total} slides, "
          f"{OUT.stat().st_size / 1e6:.2f} MB")


if __name__ == "__main__":
    main()
