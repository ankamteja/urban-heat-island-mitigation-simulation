# 09 — Automated data refresh

How the satellite data keeps itself current, and the one-time setup needed to
switch it on.

---

## First, the honest framing

**There is no live satellite temperature, and there cannot be.** Landsat 8
passes over Guwahati roughly every 16 days, mid-morning. Nothing in this design
— or any design — can show you the city's surface temperature right now from
Landsat.

What this *does* give you is the useful version of "real-time": **the site
always shows the freshest scene available, with nobody remembering to do
anything.** That is what fixes the failure this project actually had, where a
deployment served a snapshot for weeks after better data existed.

If you want a number that genuinely changes minute to minute, that is a
different variable — current air temperature from a weather station — and a
different feature. It is worth adding, but it must be labelled as air
temperature, not confused with land surface temperature.

---

## What runs, and when

`.github/workflows/refresh-data.yml`, on the 1st of each month at 03:00 UTC, or
whenever you trigger it manually from the Actions tab.

```
backend/refresh_dataset.py          re-measures every cell from Earth Engine
        ↓
preprocess.py → tier_and_recommend.py → export_grid_geojson.py
        ↓
member3_decision_support.py
        ↓
pytest tests/                       refuses to commit a bad refresh
        ↓
git commit && git push
        ↓
Vercel redeploys automatically on the push
```

Manual trigger: **Actions → refresh-data → Run workflow**. It takes a `days`
window and a `dry_run` flag — use `dry_run` the first time so you can read the
report without committing anything.

---

## The design decision that makes this safe

`backend/refresh_dataset.py` **does not regenerate the grid.**

The Code Editor script builds its grid with
`ee.Image.random().reduceToVectors(scale: 100)` and takes `grid_id` from the
resulting feature ids. Those ids depend on how the vectoriser segments the
raster — and `grid_id` is the join key for `preprocessed.csv`, `tiered.csv`,
`grid.geojson`, all three Decision-Support outputs, and every integration test.

So the refresh reads the existing cell polygons and ids straight out of the
committed `dataset.csv` and recomputes the measured bands over exactly those
geometries. Cell count, ids and shapes are stable across every run **by
construction**. Only the measurements move.

This is why the job can run unattended. A refresh that regenerated the grid
could silently invalidate every downstream join, and no test would necessarily
catch it.

The measurement formulas are identical to the Code Editor script — same C2 L2
rescale, same cloud masking, same median composite, same Heat_Risk definition.
`preprocess.py` re-verifies the Heat_Risk identity to ~1e-15 on every run, so a
formula drift fails loudly.

---

## One-time setup

Three steps. Only you can do the first two — they involve creating a Google
Cloud account and handling a private key, which is yours to hold.

### 1. Create a service account and register it with Earth Engine

1. In the [Google Cloud console](https://console.cloud.google.com/), select the
   project that owns the Earth Engine assets (the boundary asset the original
   script references lives under `projects/urban-heat-guwahati`).
2. Enable the **Earth Engine API** for that project.
3. **IAM & Admin → Service Accounts → Create service account.** Name it
   something like `uhi-refresh`. It needs no project IAM roles.
4. On the new account, **Keys → Add key → Create new key → JSON**. A `.json`
   file downloads. **This is a credential — treat it like a password.**
5. Register the service account with Earth Engine at
   [signup.earthengine.google.com/#!/service_accounts](https://signup.earthengine.google.com/#!/service_accounts),
   using the account's email (`uhi-refresh@<project>.iam.gserviceaccount.com`).
6. Grant that email **read access to the boundary asset** in the Earth Engine
   Code Editor (Assets → the asset → Share), or the job cannot see it.

### 2. Add the key as a repository secret

**Settings → Secrets and variables → Actions → New repository secret**

- Name: `EE_SERVICE_ACCOUNT_JSON`
- Value: the entire contents of the downloaded JSON file

Paste it yourself. It must never be committed to the repository, pasted into an
issue, or sent through chat — a service-account key grants API access under your
Google Cloud project until it is revoked.

If it ever leaks: delete the key in the Cloud console (**Service Accounts →
Keys → Delete**) and create a new one. Deleting the key is instant and total.

### 3. Test it before trusting it

Actions → **refresh-data** → **Run workflow** → set `dry_run` to `true`.

The log will print the number of scenes found, the per-chunk measurement
progress, and a change report — mean and maximum LST shift versus the committed
data, and the new NDVI range. Nothing is written.

If that looks sane, run it again with `dry_run` false.

---

## Running it locally

```bash
pip install earthengine-api
export EE_SERVICE_ACCOUNT_JSON="$(cat ~/Downloads/uhi-refresh-key.json)"
python backend/refresh_dataset.py --dry-run
```

The script writes the key to a private temp file only for the duration of
Earth Engine's initialisation, then deletes it. It is never logged.

---

## What can go wrong

| Symptom | Cause and fix |
|---|---|
| `EE_SERVICE_ACCOUNT_JSON is not set` | The secret is missing, or you are running locally without exporting it. |
| `No Landsat scenes between ... under 20% cloud` | The window is too short or the season too cloudy. Re-run with a larger `days`. Guwahati's monsoon can obscure months at a time. |
| `N cells have no measurement` | Those cells were cloud-masked in every scene in the window. Widen `days`. The script refuses to write a partially-null dataset rather than propagate NaN. |
| `Refreshed NDVI looks uncorrected` | The surface-reflectance rescale went missing from `build_imagery()`. A guard, not an expected failure. |
| Asset permission errors | The service account was never granted read access to the boundary asset — step 1.6. |
| Tests fail in the workflow | The refresh produced data that violates a contract or a safety rule. **Nothing is committed.** Read the failure; the data is telling you something real. |

---

## Cost

Earth Engine is free for research and non-commercial use, which this is. The
monthly job makes roughly 20 chunked requests. Nothing here approaches a paid
tier. Watch the Cloud console quotas if you increase the schedule frequency.

---

## If you later want genuinely live numbers

Add a serverless function that queries a weather API for Guwahati's current air
temperature, humidity and wind, and show it as a separate readout beside the
satellite layer. That updates by the minute and is honest, because it is clearly
a different measurement.

What it must not do is blend into the LST colour scale or the "after
intervention" figures. Air temperature and land surface temperature are
different quantities — see [08 — Limitations](./08-limitations.md#4-land-surface-temperature-is-not-air-temperature).
