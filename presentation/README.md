# Presentation

Two self-contained HTML deliverables. Both are static — open directly in a
browser, or serve the project root over HTTP so the screenshot assets resolve.

| File | What it is |
|---|---|
| `deck.html` | 15-slide presentation covering problem → method → results → dashboard → limitations |
| `architecture.html` | Standalone system architecture diagram |

## Viewing

```
cd "Urban Heat Island Mitigation"
py -m http.server 8000
```

- Deck — `http://localhost:8000/presentation/deck.html`
- Diagram — `http://localhost:8000/presentation/architecture.html`

**Deck navigation:** arrow keys, space, PageUp/PageDown, Home/End, or the on-screen
buttons. The URL hash tracks the slide, so `deck.html#8` opens slide 8 directly.

## Deck structure

1. Title
2. The problem — the 12.2 °C spread across one city
3. The approach — four modules, one data contract
4. System architecture (embeds the diagram)
5. The data — 8,144 cells, with the real temperature distribution
6. Machine learning — random split vs. spatial block split
7. Feature importance
8. Priority tiering — cells, actions and costs
9. The dashboard — how the blended surface is built
10. Selection-gated prediction and ecology pointers
11. The five ecological measures
12. Analytics
13. Impact — the headline numbers
14. Honest limitations
15. Next steps

## Where the numbers come from

Every figure is read from the pipeline outputs, not estimated:

| Figure | Source |
|---|---|
| 8,144 cells · temp range 20.9–33.1 °C · mean NDVI 0.181 | `frontend/data/grid.geojson` |
| Temperature histogram (1 °C bins) | computed from `frontend/data/grid.geojson` |
| R² / RMSE by model and split · feature importances | `Machine Learning & Prediction/Results/metrics.json` |
| Tier counts, mean LST and costs · ₹160.5 Cr total | `Machine Learning & Prediction/Results/tiering_summary.md` |
| Mean drop −1.51 °C · 6,108 actionable cells | derived via the dashboard's cooling model |

The canonical model is `random_80_20 | base | RandomForest` (R² 0.901,
RMSE 0.52 °C). The 0.938 figure belongs to the `base+spatial_lag` variant and is
labelled as such wherever it appears.

## Regenerating the screenshots

`assets/` holds captures of the live dashboard and the rendered diagram. To
refresh them, serve the project and re-run the capture script used to build
them (headless Chrome), or replace the PNGs by hand keeping the filenames:

```
assets/architecture.png    the diagram SVG, cropped
assets/dash-overview.png   whole study area, no selection
assets/dash-compare.png    split view with ecology pointers
assets/dash-charts.png     the four analytics charts
assets/dash-kpis.png       the KPI row
```

## Exporting to PDF / PowerPoint

Print the deck from Chrome (landscape, background graphics on, margins none) for
a PDF. The deck is a real HTML presentation rather than a `.pptx`; if a PowerPoint
file is required, the PDF imports cleanly as slide images.

## Diagram

`architecture.html` was built with the [diagram-design](https://github.com/cathrynlavery/diagram-design)
skill, skinned to this project's palette (deep navy paper, amber accent) rather
than the skill's shipped default. It passes the skill's `self_check.py` contract:
accessible `<title>`/`<desc>`, orthogonal connectors only, labels clear of their
strokes, and a bottom legend strip.
