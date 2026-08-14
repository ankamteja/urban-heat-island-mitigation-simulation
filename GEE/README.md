# GEE (pointer)

The Earth Engine script lives with the module that owns it:

**[`../Remote Sensing & Data Engineering/GEE/urban_heat_analysis.js`](../Remote%20Sensing%20%26%20Data%20Engineering/GEE/urban_heat_analysis.js)**

## Why this folder is now just a pointer

This directory used to hold a second copy of `urban_heat_analysis.js`. The two
copies had drifted — 438 lines here against 605 lines in the Remote Sensing
module — and both claimed to contain the surface-reflectance rescale and the
WorldCover join.

**Which copy produced the committed `dataset.csv` could not be determined from
what was in the repository.** That ambiguity is the reason for the change: the
upstream stage of this project is the one place where a wrong script silently
biases every number downstream, so it must have exactly one definition.

The Remote Sensing copy was kept as canonical because it lives alongside the
module's `README.md`, `SPEC_AUDIT.md`, boundary asset and outputs. The copy that
was here remains in git history if it is ever needed.

## Running it

The script runs in the [Earth Engine Code Editor](https://code.earthengine.google.com/),
not locally. See [`../docs/03-remote-sensing.md`](../docs/03-remote-sensing.md)
for the full walkthrough, including which asset it expects and where the exports
land.
