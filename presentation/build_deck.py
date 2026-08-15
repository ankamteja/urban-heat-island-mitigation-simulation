"""Builds UHI-Presentation.pptx.

Thirteen slides in the order a technical panel reads: problem, solution,
novelty, approach, algorithm, validation, dashboard, impact, limitations,
future work, links, citations.

Written as bullets and tables rather than prose. Two constraints the content
holds to, because both are credibility risks in front of judges:

  1. Cooling values are planning assumptions used to compare scenarios, never
     measured guarantees. The slide that shows them says where they came from.
  2. The model is not the decision-maker. The recommendation comes from an
     auditable rule and cost engine.

Every headline figure is either read from the pipeline's own output at build
time or listed in FIGURES with the document it came from. The validation table
is computed from frontend/data/grid.geojson - see presentation/README.md.

Palette and type follow frontend/style.css so the deck and the dashboard read
as one product.

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


def bullets(slide, x, y, w, items, *, size=14, gap=0.34, colour=FG, lead=None):
    """A bulleted block. Each item is a string, or (lead, rest) to bold the lead.

    Bullets rather than prose because a judge reads a slide in seconds and a
    paragraph makes them hunt for the claim.
    """
    cur = y
    for item in items:
        dot = slide.shapes.add_shape(MSO_SHAPE.OVAL, x, cur + Inches(0.075), Inches(0.055), Inches(0.055))
        dot.fill.solid()
        dot.fill.fore_color.rgb = lead or ACCENT
        dot.line.fill.background()
        dot.shadow.inherit = False

        if isinstance(item, tuple):
            runs = [(item[0], size, FG, True, UI), (item[1], size, colour, False, UI)]
        else:
            runs = [(item, size, colour, False, UI)]
        box = text(slide, x + Inches(0.2), cur, w - Inches(0.2), Inches(0.4),
                   runs, line_spacing=1.32)
        cur += Inches(gap) + Inches(0.055) * max(0, len(str(item)) // 95)
    return cur


def table(slide, x, y, w, headers, rows, *, widths=None, size=12.5,
          row_h=0.34, highlight=None):
    """A compact data table. `highlight` bolds one row index in the accent."""
    n = len(headers)
    widths = widths or [1 / n] * n
    cols = [int(w * f) for f in widths]

    hx = x
    for i, h in enumerate(headers):
        text(slide, hx, y, cols[i], Inches(0.28),
             [(h.upper(), 9.5, DIM, False, DATA)],
             align=PP_ALIGN.RIGHT if i else PP_ALIGN.LEFT)
        hx += cols[i]

    rule(slide, x, y + Inches(0.28), w, SURFACE_3)

    cy = y + Inches(0.38)
    for r_i, row in enumerate(rows):
        on = highlight is not None and r_i == highlight
        cx = x
        for i, cell in enumerate(row):
            text(slide, cx, cy, cols[i], Inches(0.3),
                 [(str(cell), size, ACCENT if on else (FG if i == 0 else MUTED),
                   on, UI if i == 0 else DATA)],
                 align=PP_ALIGN.RIGHT if i else PP_ALIGN.LEFT)
            cx += cols[i]
        cy += Inches(row_h)
    return cy


# ----------------------------------------------------------------- slides ---
def slide_title(prs, f, n, total):
    s = add_slide(prs)

    seg = W / len(RAMP)
    for i, c in enumerate(RAMP):
        bar = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, int(seg * i), 0, int(seg) + 1, Inches(0.08))
        bar.fill.solid()
        bar.fill.fore_color.rgb = c
        bar.line.fill.background()
        bar.shadow.inherit = False

    text(s, MARGIN, Inches(1.16), Inches(10), Inches(0.3),
         [("URBAN HEAT ISLAND MITIGATION · GUWAHATI, ASSAM", 11, ACCENT, True, DATA)])
    text(s, MARGIN, Inches(1.7), Inches(11.4), Inches(1.5),
         [[("Heatwise", 54, FG, True, UI)],
          [("Budget-constrained urban heat mitigation planning", 26, MUTED, False, UI)]],
         line_spacing=1.06)

    text(s, MARGIN, Inches(3.7), Inches(11.2), Inches(0.6),
         [("A satellite-derived 100 m heat grid, land-cover safety rules and a "
           "cost model, combined into a ranked mitigation shortlist that fits a "
           "stated municipal budget.", 15, MUTED, False, UI)], line_spacing=1.4)

    rule(s, MARGIN, Inches(4.66), Inches(11.9))

    text(s, MARGIN, Inches(4.92), Inches(6.4), Inches(0.3),
         [("TEAM", 9.5, DIM, False, DATA)])
    for i, (name, role) in enumerate(TEAM):
        text(s, MARGIN, Inches(5.2) + Inches(0.29) * i, Inches(6.6), Inches(0.3),
             [(name, 12.5, FG, False, UI), ("  ·  ", 12.5, DIM, False, UI),
              (role, 12.5, MUTED, False, UI)])

    text(s, Inches(8.0), Inches(4.92), Inches(4.6), Inches(0.3),
         [("PROJECT", 9.5, DIM, False, DATA)])
    text(s, Inches(8.0), Inches(5.2), Inches(4.6), Inches(1.3),
         [[("↗ Live dashboard", 12, ACCENT, False, DATA, LINKS["dashboard"])],
          [("↗ Source repository", 12, ACCENT, False, DATA, LINKS["repo"])],
          [("↗ Technical documentation", 12, ACCENT, False, DATA, LINKS["docs"])]],
         line_spacing=1.5)

    text(s, Inches(10.6), Inches(6.86), Inches(2.05), Inches(0.3),
         [(f"{n} / {total}", 9, DIM, False, DATA)], align=PP_ALIGN.RIGHT)


def slide_problem(prs, f, n, total):
    s = add_slide(prs)
    eyebrow(s, "01 — problem")
    heading(s, "Heat is unevenly distributed; budgets are not")

    png = ASSETS / "dash-overview.jpg"
    if png.exists():
        s.shapes.add_picture(str(png), Inches(6.5), Inches(2.0), width=Inches(6.12))

    bullets(s, MARGIN, Inches(2.1), Inches(5.5), [
        ("Surface temperature spans 21.1–33.2 °C ", "across the study area — a 12 °C "
         "range inside one city."),
        ("Ward-level averages hide it. ", "Adjacent 100 m cells differ by several "
         "degrees, so the decision scale is the block, not the district."),
        ("530 cells sit in the top decile ", "of the observed range and drive "
         "heat-related health and energy load."),
        ("Mitigation budgets are finite. ", "Treating every eligible cell would cost "
         "₹167.5 Cr against a typical annual allocation of ₹10 Cr."),
        ("No ranking exists. ", "Standard practice produces a heat map and stops "
         "short of which sites to fund first."),
    ], gap=0.72)

    footer(s, n, total)


def slide_solution(prs, f, n, total):
    s = add_slide(prs)
    eyebrow(s, "02 — solution")
    heading(s, "A ranked, costed, budget-capped shortlist")

    bullets(s, MARGIN, Inches(2.16), Inches(11.6), [
        ("End-to-end pipeline. ", "Landsat 8 thermal imagery → 100 m heat grid → "
         "land-cover eligibility → cost model → budget-constrained selection → dashboard."),
        ("Safety rules first. ", "8,144 cells reduce to 4,157 eligible; water, wetland "
         "and existing tree cover are excluded in code before any ranking occurs."),
        ("Explicit cost model. ", "Each measure is priced as rate × coverage fraction × "
         "cell area, from published municipal rates rather than assumed figures."),
        ("Greedy selection under constraint. ", "Cells are ordered by cooling per rupee, "
         "ties broken by surface temperature, and funded until the budget is exhausted."),
        ("Operational dashboard. ", "Budget scenarios, per-cell inspection with the "
         "reason for each recommendation, current-versus-mitigation comparison, and an "
         "exportable report."),
    ], gap=0.62)

    rule(s, MARGIN, Inches(5.78), Inches(11.9))
    cols = [
        (f"{f['cells']:,}", "cells mapped"),
        (f"{f['treatable']:,}", "eligible after safety rules"),
        (f"₹{FIGURES['funded_cr']} Cr", "committed at ₹10 Cr budget"),
        (FIGURES["funded_cells"], "sites funded"),
    ]
    for i, (v, l) in enumerate(cols):
        stat(s, MARGIN + Inches(3.0) * i, Inches(6.0), Inches(2.9), v, l, value_pt=22)

    footer(s, n, total)


def slide_novelty(prs, f, n, total):
    s = add_slide(prs)
    eyebrow(s, "03 — novelty")
    heading(s, "What is new here")

    items = [
        ("Selection, not just detection",
         "Published UHI mapping work stops at a risk surface. This system carries the "
         "surface through eligibility, cost and a budget constraint to a specific, "
         "orderable list of sites."),
        ("Safety encoded as a gate, not guidance",
         "Land-cover exclusions run before ranking and are asserted by tests, so no "
         "recommendation can reach the interface proposing work on water, wetland or "
         "existing canopy."),
        ("Cost-efficiency as the objective",
         "Ranking on cooling per rupee rather than temperature alone funds 249 sites "
         "where hottest-first funds 229 for the same money — the cheaper measure fits "
         "more sites into the same budget."),
        ("Auditable by construction",
         "Every funded cell resolves to a rule, a rate and a rank. The dashboard re-runs "
         "the pipeline's own ordering client-side, so an interactive change of budget or "
         "area cannot diverge from the committed plan."),
        ("Model kept in its lane",
         "The RandomForest is reported as a diagnostic. The visible recommendation comes "
         "from the rule and cost engine, which is what makes it explainable to a planner."),
    ]

    y = Inches(2.16)
    for title, body in items:
        text(s, MARGIN, y, Inches(3.9), Inches(0.4), [(title, 14.5, ACCENT, True, UI)])
        text(s, MARGIN + Inches(4.1), y, Inches(7.8), Inches(0.8),
             [(body, 13, MUTED, False, UI)], line_spacing=1.35)
        y += Inches(0.92)

    footer(s, n, total)


def slide_approach(prs, f, n, total):
    s = add_slide(prs)
    eyebrow(s, "04 — approach")
    heading(s, "Processing pipeline", size=34)

    png = ASSETS / "architecture.png"
    if png.exists():
        s.shapes.add_picture(str(png), MARGIN, Inches(1.86), width=Inches(11.9))
    footer(s, n, total, link=LINKS["docs"], link_label="docs/01-architecture.md")


def slide_algorithm(prs, f, n, total):
    s = add_slide(prs)
    eyebrow(s, "05 — algorithm and worked example")
    heading(s, "How one cell is selected", size=34)

    # left: the model
    text(s, MARGIN, Inches(1.94), Inches(6.0), Inches(0.3),
         [("COST AND COOLING MODEL", 9.5, DIM, False, DATA)])
    table(s, MARGIN, Inches(2.3), Inches(6.0),
          ["Measure", "₹/m²", "Cover", "ΔT °C", "₹/cell"],
          [["Cool roof", "300", "15%", "1.0", "4.01 L"],
           ["Tree canopy", "150", "25%", "0.8", "3.75 L"],
           ["Pocket park", "1,150", "10%", "2.0", "11.5 L"]],
          widths=[.30, .16, .16, .16, .22], highlight=0)

    text(s, MARGIN, Inches(3.72), Inches(6.0), Inches(0.62),
         [("Cost = rate × coverage fraction × cell area. Rates are published "
           "municipal figures; ΔT values are planning assumptions, not measurements.",
           11.5, DIM, False, UI)], line_spacing=1.35)

    text(s, MARGIN, Inches(4.46), Inches(6.0), Inches(0.3),
         [("SELECTION RULE", 9.5, DIM, False, DATA)])
    card(s, MARGIN, Inches(4.76), Inches(6.0), Inches(1.24), fill=SURFACE)
    text(s, MARGIN + Inches(0.26), Inches(4.98), Inches(5.5), Inches(0.4),
         [("sort by ΔT / cost  desc", 13.5, ACCENT, False, DATA)])
    text(s, MARGIN + Inches(0.26), Inches(5.28), Inches(5.5), Inches(0.4),
         [("then LST desc, then grid_id asc", 13.5, FG, False, DATA)])
    text(s, MARGIN + Inches(0.26), Inches(5.58), Inches(5.5), Inches(0.4),
         [("fill while cumulative cost ≤ budget", 12, MUTED, False, UI)])

    # right: the worked cell
    x2 = Inches(7.1)
    text(s, x2, Inches(1.94), Inches(5.5), Inches(0.3),
         [("WORKED EXAMPLE — RANK #1 OF 4,157", 9.5, DIM, False, DATA)])
    card(s, x2, Inches(2.3), Inches(5.52), Inches(3.7), fill=SURFACE, line=ACCENT, line_w=1.1)

    text(s, x2 + Inches(0.28), Inches(2.54), Inches(5.0), Inches(0.3),
         [("+102070+29080", 15, FG, True, DATA)])
    text(s, x2 + Inches(0.28), Inches(2.86), Inches(5.0), Inches(0.3),
         [("Railway Colony, Maligaon · 26.1235, 91.6915", 11.5, MUTED, False, UI)])

    rows = [
        ["Surface temperature", "33.2 °C", "top 10%"],
        ["Built-up intensity (NDBI)", "0.121", "top 10%"],
        ["Vegetation (NDVI)", "0.210", "bottom 10%"],
        ["Land cover", "Built-up", "eligible"],
        ["Measure", "Cool roof", "gated"],
        ["Estimated cost", "₹4.01 L", "priced"],
        ["Expected cooling", "−1.00 °C", "assumed"],
    ]
    table(s, x2 + Inches(0.28), Inches(3.3), Inches(4.96),
          ["Attribute", "Value", "Basis"], rows,
          widths=[.48, .28, .24], size=12, row_h=0.31)

    footer(s, n, total)


def slide_validation(prs, f, n, total):
    s = add_slide(prs)
    eyebrow(s, "06 — validation")
    heading(s, "Compared against the obvious alternatives")

    text(s, MARGIN, Inches(1.96), Inches(11.6), Inches(0.5),
         [("Same ₹10 Cr budget, same eligible pool, same cooling assumptions. "
           "Only the selection rule changes.", 14, MUTED, False, UI)])

    table(s, MARGIN, Inches(2.66), Inches(11.9),
          ["Selection strategy", "Sites", "Spend", "Total ΔT", "Mean °C", "Hotspots cut"],
          [["Random among eligible", "248", "₹9.99 Cr", "245", "27.94", "25"],
           ["Hottest eligible first", "229", "₹9.98 Cr", "240", "30.28", "154"],
           ["Cooling per rupee, then hottest", "249", "₹9.99 Cr", "249", "30.16", "180"]],
          widths=[.34, .12, .14, .13, .13, .14], highlight=2, row_h=0.42)

    rule(s, MARGIN, Inches(4.5), Inches(11.9))

    bullets(s, MARGIN, Inches(4.74), Inches(11.6), [
        ("Against hottest-first: ", "20 more sites and 26 more hotspot cells removed for "
         "the same spend, because the cheapest measure per degree fits more sites in."),
        ("Against random: ", "180 hotspot cells removed versus 25 — the ranking, not the "
         "budget, is doing the work."),
        ("Against no safety gate: ", "taking the hottest 249 cells outright places 14 of "
         "them (6%) on existing tree cover, where planting is already redundant."),
    ], gap=0.62)

    footer(s, n, total)


def slide_demo(prs, f, n, total):
    s = add_slide(prs)
    eyebrow(s, "07 — dashboard")
    heading(s, "Every recommendation is inspectable", size=34)

    png = ASSETS / "dash-compare.jpg"
    if png.exists():
        pic_h = Inches(4.26)
        pic_w = Inches(4.26 * 1680 / 892)
        s.shapes.add_picture(str(png), int((W - pic_w) / 2), Inches(1.9),
                             width=int(pic_w), height=int(pic_h))

    text(s, MARGIN, Inches(6.34), Inches(11.9), Inches(0.4),
         [("Click any cell for why it ranks where it does, what the rule engine "
           "proposes, what it costs, whether the budget reaches it, and a Street View "
           "link to inspect the site.", 12.5, MUTED, False, UI)], align=PP_ALIGN.CENTER)
    footer(s, n, total, link=LINKS["dashboard"], link_label="live dashboard")


def slide_impact(prs, f, n, total):
    s = add_slide(prs)
    eyebrow(s, "08 — impact and benefits")
    heading(s, "What the plan delivers, and where it goes next")

    items = [
        (f"{FIGURES['hotspots_before']} → {FIGURES['hotspots_after']}",
         "hotspot cells", "Top-decile cells removed at ₹10 Cr — a 34% reduction "
         "in the population most exposed to extreme surface heat."),
        (f"₹{FIGURES['funded_cr']} Cr", "committed, not ₹167.5 Cr",
         "The plan fits a realistic municipal allocation instead of an "
         "unfundable whole-city figure."),
        ("249", "sites, each defensible",
         "Every site carries its temperature, land cover, measure, price and rank, "
         "so the shortlist survives procurement scrutiny."),
    ]
    x = MARGIN
    w = Inches(3.76)
    for v, k, body in items:
        card(s, x, Inches(2.16), w, Inches(2.1), fill=SURFACE)
        text(s, x + Inches(0.3), Inches(2.4), w - Inches(0.6), Inches(0.5),
             [(v, 26, ACCENT, True, UI)])
        text(s, x + Inches(0.3), Inches(2.88), w - Inches(0.6), Inches(0.3),
             [(k, 11, DIM, False, DATA)])
        text(s, x + Inches(0.3), Inches(3.2), w - Inches(0.6), Inches(0.9),
             [(body, 12, MUTED, False, UI)], line_spacing=1.35)
        x += w + Inches(0.31)

    text(s, MARGIN, Inches(4.6), Inches(11.9), Inches(0.3),
         [("SCALABILITY AND PRACTICALITY", 9.5, DIM, False, DATA)])
    bullets(s, MARGIN, Inches(4.94), Inches(11.6), [
        ("Inputs are global. ", "Landsat 8 and ESA WorldCover cover any city on Earth "
         "at no cost; porting the pipeline is a boundary file and a rate table."),
        ("Rates are configuration, not code. ", "Unit costs and cooling assumptions live "
         "in one JSON file read by every module, so a new city changes data, not logic."),
        ("Reproducible. ", "133 tests and CI that regenerates every artefact and fails if "
         "a committed copy differs. MIT licensed with data attribution."),
    ], gap=0.56)

    footer(s, n, total)


def slide_limits(prs, f, n, total):
    s = add_slide(prs)
    eyebrow(s, "09 — limitations")
    heading(s, "What this does not yet establish")

    bullets(s, MARGIN, Inches(2.16), Inches(11.6), [
        ("Cooling values are assumptions. ", "0.8 / 1.0 / 2.0 °C per measure originate in "
         "a planning catalogue. They were never fitted to Guwahati or validated against a "
         "field trial, and they determine the ranking."),
        ("One unit rate is unanchored. ", "Cool roof and pocket park rates come from the "
         "Telangana Cool Roof Policy and Gujarat AMRUT 2.0. The tree-canopy rate has no "
         "published municipal equivalent."),
        ("Cool roof leads by 4%. ", "That margin sits inside the error of an unvalidated "
         "rate, so the measure mix should be read as approximate, not settled."),
        ("Surface, not air temperature. ", "Landsat measures skin temperature. The health "
         "and comfort outcomes a city cares about depend on air temperature."),
        ("One thermal snapshot. ", "A single scene describes one moment, not a seasonal "
         "or diurnal pattern."),
        ("Model is not in the decision path. ", "Spatial-block R² is 0.513 against 0.895 "
         "on a random split; the honest figure is the lower one, and nothing downstream "
         "consumes either."),
    ], gap=0.63)

    footer(s, n, total, link=LINKS["docs"], link_label="docs/08-limitations.md")


def slide_future(prs, f, n, total):
    s = add_slide(prs)
    eyebrow(s, "10 — future work")
    heading(s, "Ordered by effect on decision quality")

    items = [
        ("01", "Calibrate cooling against observation",
         "Compare existing parks and canopy against matched built-up cells across "
         "seasons, replacing each assumed constant with a local estimate and a range."),
        ("02", "Propagate uncertainty into the ranking",
         "Run the selection over a scenario grid of rates and cooling values, and report "
         "which cells stay funded across them."),
        ("03", "Add temporal coverage",
         "Multi-date and seasonal composites, so the plan responds to a pattern rather "
         "than a single scene."),
        ("04", "Surface-to-air temperature transfer",
         "Add the step that converts skin temperature to the air temperature that governs "
         "health outcomes."),
        ("05", "Population weighting",
         "Optimise people-degrees rather than cell-degrees, weighting schools, hospitals "
         "and dense settlement."),
    ]
    y = Inches(2.16)
    for num, title, body in items:
        text(s, MARGIN, y, Inches(0.7), Inches(0.4), [(num, 17, ACCENT, True, DATA)])
        text(s, MARGIN + Inches(0.86), y - Inches(0.02), Inches(10.9), Inches(0.36),
             [(title, 15, FG, True, UI)])
        text(s, MARGIN + Inches(0.86), y + Inches(0.3), Inches(10.6), Inches(0.5),
             [(body, 12.5, MUTED, False, UI)], line_spacing=1.32)
        y += Inches(0.88)

    footer(s, n, total)


def slide_links(prs, f, n, total):
    s = add_slide(prs)
    eyebrow(s, "11 — links and documentation")
    heading(s, "Everything is public and reproducible", size=34)

    rows = [
        ["Live dashboard", "Interactive planning console", LINKS["dashboard"]],
        ["Landing page", "Project overview and figures", LINKS["site"]],
        ["Source repository", "Full pipeline, tests and CI", LINKS["repo"]],
        ["Documentation", "Architecture, data contracts, limitations", LINKS["docs"]],
    ]

    text(s, MARGIN, Inches(2.0), Inches(3.0), Inches(0.28), [("RESOURCE", 9.5, DIM, False, DATA)])
    text(s, Inches(3.9), Inches(2.0), Inches(4.2), Inches(0.28), [("CONTENTS", 9.5, DIM, False, DATA)])
    text(s, Inches(8.2), Inches(2.0), Inches(4.4), Inches(0.28), [("LINK", 9.5, DIM, False, DATA)])
    rule(s, MARGIN, Inches(2.28), Inches(11.9))

    y = Inches(2.44)
    for label, desc, url in rows:
        text(s, MARGIN, y, Inches(3.1), Inches(0.3), [(label, 13.5, FG, False, UI)])
        text(s, Inches(3.9), y, Inches(4.2), Inches(0.3), [(desc, 12.5, MUTED, False, UI)])
        text(s, Inches(8.2), y, Inches(4.4), Inches(0.3),
             [("↗ ", 11.5, ACCENT, False, DATA), (url.replace("https://", ""), 11.5, ACCENT, False, DATA, url)])
        y += Inches(0.52)

    rule(s, MARGIN, y + Inches(0.08), Inches(11.9))

    text(s, MARGIN, y + Inches(0.32), Inches(11.9), Inches(0.28),
         [("KEY DOCUMENTS IN THE REPOSITORY", 9.5, DIM, False, DATA)])
    docs = [
        ["docs/01-architecture.md", "Module boundaries and the data contract between them"],
        ["docs/07-data-contracts.md", "Column-by-column reference for every file crossing a module"],
        ["docs/08-limitations.md", "Every assumption, with the reason it is still an assumption"],
        ["STATUS.md", "What is true now, verified against the committed data"],
    ]
    dy = y + Inches(0.62)
    for path, desc in docs:
        text(s, MARGIN, dy, Inches(3.1), Inches(0.28), [(path, 12, ACCENT, False, DATA)])
        text(s, Inches(3.9), dy, Inches(8.7), Inches(0.28), [(desc, 12, MUTED, False, UI)])
        dy += Inches(0.34)

    footer(s, n, total)


def slide_citations(prs, f, n, total):
    s = add_slide(prs)
    eyebrow(s, "12 — data sources and citations")
    heading(s, "Sources", size=34)

    y = Inches(1.96)
    for group, entries in CITATIONS:
        text(s, MARGIN, y, Inches(11.9), Inches(0.28),
             [(group.upper(), 9.5, DIM, False, DATA)])
        y += Inches(0.3)
        for e in entries:
            text(s, MARGIN, y, Inches(11.6), Inches(0.32),
                 [(e, 12, MUTED, False, UI)], line_spacing=1.3)
            y += Inches(0.34)
        y += Inches(0.12)

    text(s, MARGIN, Inches(6.5), Inches(11.9), Inches(0.3),
         [("Landsat and ESA WorldCover are open data. Full attribution is in "
           "NOTICE.md; the project is MIT licensed.", 11.5, DIM, False, UI)])

    footer(s, n, total)


# ------------------------------------------------------------- static copy ---
# Roles are taken from each contributor's actual commit history rather than
# assigned, so the slide is accurate rather than flattering.
TEAM = [
    ("Ankam Charan Teja", "ML pipeline, decision engine, documentation"),
    ("Yogeshwar S", "Dashboard, presentation, ML integration"),
    ("Sriya Sudakshina", "Decision-support module"),
    ("Nikhil Cheepati", "Remote sensing, Earth Engine export"),
    ("Dandu Uddeep Sri Shourya", "Frontend"),
]

CITATIONS = [
    ("Satellite and geospatial data", [
        "USGS. Landsat 8–9 Collection 2 Level-2 Science Products. U.S. Geological Survey, 2024.",
        "Zanaga, D. et al. ESA WorldCover 10 m 2021 v200. European Space Agency, 2022. doi:10.5281/zenodo.7254221",
        "Gorelick, N. et al. Google Earth Engine: Planetary-scale geospatial analysis for everyone. Remote Sensing of Environment, 2017.",
    ]),
    ("Unit rates", [
        "Government of Telangana. Telangana Cool Roof Policy 2023–28 — ₹300/m² for cool-roof coating or tiles.",
        "Government of Gujarat. AMRUT 2.0 municipal garden development schedule — ₹1,152–2,250/m².",
    ]),
    ("Methods and tooling", [
        "Pedregosa, F. et al. Scikit-learn: Machine Learning in Python. JMLR 12, 2011 — RandomForestRegressor.",
        "Roberts, D. R. et al. Cross-validation strategies for data with spatial, temporal, phylogenetic or "
        "spatial-temporal structure. Ecography 40, 2017 — spatial-block validation.",
        "QGIS Development Team. QGIS Geographic Information System. Open Source Geospatial Foundation, 2024.",
        "Agafonkin, V. Leaflet — an open-source JavaScript library for interactive maps, 2024.",
    ]),
]


# -------------------------------------------------------------------- main ---
BUILDERS = [
    slide_title,
    slide_problem,
    slide_solution,
    slide_novelty,
    slide_approach,
    slide_algorithm,
    slide_validation,
    slide_demo,
    slide_impact,
    slide_limits,
    slide_future,
    slide_links,
    slide_citations,
]


def main():
    figures = load_figures()

    prs = Presentation()
    prs.slide_width, prs.slide_height = W, H

    total = len(BUILDERS)
    for i, build in enumerate(BUILDERS, start=1):
        build(prs, figures, i, total)

    prs.save(OUT)
    print(f"wrote {OUT.relative_to(ROOT)} - {total} slides, "
          f"{OUT.stat().st_size / 1e6:.2f} MB")


if __name__ == "__main__":
    main()
