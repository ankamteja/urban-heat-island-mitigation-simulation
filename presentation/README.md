# Presentation

Generates `UHI-Presentation.pptx` at the repository root: 10 slides, ~0.45 MB.

An earlier `presentation/` module was deleted in 8e6ba44 because it shipped
~4.3 MB of dashboard screenshots into every Vercel deployment. This one is a
generator, not a folder of exported assets, and `.vercelignore` keeps both the
module and the `.pptx` out of the deployment — so the deck can live in the
repository without the problem that got the last one removed.

## Build

```bash
pip install python-pptx
python presentation/build_deck.py
```

## Structure

Thirteen slides, in the section order a technical panel reads. Section titles
state what the slide contains; the evidence carries the argument.

| # | Section | Carries |
|---|---|---|
| 1 | Title | Problem statement, team, project links, headline figures |
| 2 | Problem understanding & motivation | Why urban heat matters, stated generally |
| 3 | Literature review & existing approaches | Four prior strands and the identified gap |
| 4 | Proposed methodology & technical approach | Five stages, then the distinguishing choices |
| 5 | System architecture & processing pipeline | The eight-stage diagram |
| 6 | Data sources & preprocessing | Datasets, preprocessing steps, derived fields, QC |
| 7 | Selection algorithm & worked example | Cost model, ordering rule, one cell traced |
| 8 | Validation & comparative evaluation | Three ordering strategies at one budget |
| 9 | Dashboard & decision interface | Interface screenshot and capabilities |
| 10 | Expected outcomes & impact | Outcomes, scalability, sustainability relevance |
| 11 | Limitations & future work | Four each, side by side |
| 12 | Team composition & contributions | Roles from commit history |
| 13 | Appendix: links & references | Project links, data sources, cited work |

Layout follows the reference deck: content column 0.65–12.65 in, eyebrow 0.38,
title 0.95 at 30pt, standfirst 1.73, body from 2.20, footer rule 6.88, page
number at 12.10.

Two positions the content holds deliberately:

- **Cooling values are planning assumptions, not measured guarantees.** Slide 7
  labels the basis of every figure in the worked example; slide 11 leads with it.
- **The model is not the decision-maker.** The recommendation comes from the rule
  and cost engine. Slide 4 states it as a design choice.

## Regenerating the validation table

Slide 7 is the one table that is not read from a committed artefact. It is
computed by replaying three selection strategies over `frontend/data/grid.geojson`
at the same ₹10 Cr budget:

- **Random among eligible** — mean of 200 seeded shuffles
- **Hottest eligible first** — eligible cells by LST descending
- **Cooling per rupee, then hottest** — the shipped rule

Each fills greedily while cumulative cost stays under budget. "Hotspots cut" is
the change in cells at or above the top decile of the observed range. The
current figures are in `FIGURES` in `build_deck.py`; re-derive them with the
script in that section's comment if the grid changes.

## Where the numbers come from

`build_deck.py` reads what the pipeline emits — cell count, action counts, total
cost and the release ID — from `frontend/data/release.json` and
`shared/constants.json`. A pipeline re-run therefore cannot leave the deck
quoting a stale grid.

Everything else lives in the `FIGURES` dict at the top of the script, each entry
commented with the document it came from. If one of those documents changes,
change `FIGURES` and rebuild. This is the deck's known weak spot: those values
are copied, not derived.

## Assets

| File | Slide | Regenerate |
|---|---|---|
| `assets/architecture.png` | 4 | render `architecture.html` (below) |
| `assets/dash-overview.jpg` | 2 | screenshot the dashboard, whole city |
| `assets/dash-compare.jpg` | 6 | screenshot with an area selected |

All three are committed, so the build needs no browser. To re-render the
diagram after editing `architecture.html`:

```bash
# any Chromium; --force-device-scale-factor=2 keeps it crisp when projected
chrome --headless --disable-gpu --hide-scrollbars \
       --force-device-scale-factor=2 --window-size=1440,560 \
       --default-background-color=0B1120 \
       --screenshot=presentation/assets/architecture.png \
       presentation/architecture.html
```

The dashboard screenshots were captured from a local `python -m http.server`
against `frontend/`, then downscaled to 1600 px wide JPEG (quality 88) — a PNG
of the same frame is ~700 KB and buys nothing at projection size.

## The diagram

`architecture.html` is a self-contained diagram built on the `diagram-design`
system ([cathrynlavery/diagram-design](https://github.com/cathrynlavery/diagram-design)),
skinned to the dashboard's own palette from `frontend/style.css`. Fira Sans and
Fira Code stand in for the system's default Geist so the diagram, the deck and
the dashboard read as one product.

Verify it with the skill's own checker:

```bash
python ~/.claude/skills/diagram-design/scripts/self_check.py presentation/architecture.html
```
