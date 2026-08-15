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

Ordered for a hackathon judging panel — one claim per slide, stated in the
slide's own accent bar:

| # | Slide | The claim |
|---|---|---|
| 1 | Title | Satellite heat data → a safe, ranked, cost-aware plan a planner can explore now |
| 2 | The problem | Heat is uneven; choosing well needs a map at the scale of the decision |
| 3 | The solution | Four steps, each auditable — decision support, not prediction |
| 4 | Data and architecture | Real data in, auditable plan out |
| 5 | Key result | ₹10 Cr, 249 cells — and cooling values are assumptions, not guarantees |
| 6 | Interactive demo | Both surfaces, live, for any selection |
| 7 | Safety and trust | The rules that stop a bad recommendation |
| 8 | Impact | What a planner can do on Monday |
| 9 | Limitations and next step | What we would validate first |
| 10 | Close | From satellite pixels to a defensible urban cooling shortlist |

Two positions the deck holds deliberately, because both are credibility risks in
front of judges:

- **Cooling values are planning assumptions used to compare scenarios, never
  measured guarantees.** Slide 5 says so in red under the headline figures, and
  slide 9 leads with it.
- **The model is not the decision-maker.** The visible recommendation comes from
  an auditable rule and cost engine. The architecture diagram marks the ML branch
  as a diagnostic that terminates, rather than implying the plan is model output.

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
