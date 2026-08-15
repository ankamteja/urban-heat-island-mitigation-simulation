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

Thirteen slides in the order a technical panel reads them:

| # | Slide | Carries |
|---|---|---|
| 1 | Title | Project, team and roles, the three project links |
| 2 | Problem | Why block-scale ranking is needed at all |
| 3 | Solution | The pipeline in five bullets, then the headline figures |
| 4 | Novelty | Five specific claims, each falsifiable |
| 5 | Approach | The eight-stage pipeline diagram |
| 6 | Algorithm | Cost/cooling table, the selection rule, one worked cell |
| 7 | Validation | Random vs hottest-first vs ours, at the same budget |
| 8 | Dashboard | Screenshot of the cell inspector |
| 9 | Impact | Hotspot reduction, then scalability and reproducibility |
| 10 | Limitations | Six, each naming what would settle it |
| 11 | Future work | Five, ordered by effect on decision quality |
| 12 | Links | Resource table plus the four key repository documents |
| 13 | Citations | Data sources, unit rates, methods |

Written as bullets and tables. Two positions the content holds deliberately,
because both are credibility risks in front of judges:

- **Cooling values are planning assumptions, not measured guarantees.** Slide 6
  shows where each one came from; slide 10 leads with the fact that they
  determine the ranking and were never validated locally.
- **The model is not the decision-maker.** The recommendation comes from the
  rule and cost engine. Slide 4 says so as a design claim rather than a caveat.

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
