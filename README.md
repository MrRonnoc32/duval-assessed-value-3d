# Duval historical parcel map

Historical extension of the original Duval 3D map, covering 2015–2025.

[Open the live map](https://mrronnoc32.github.io/duval-assessed-value-3d/).

## Use

Serve this directory with `python3 -m http.server 8765`, then open
http://localhost:8765/. Choose a year on the bottom timeline, or press play.
Compare years colors the ending year's polygons by percentage or dollar change
against a selected baseline. Heights always represent the ending year's value.
Click a polygon for the parcel's annual value history.

Value fields are explicitly labeled: `AV_NSD` or `JV`. They come from the annual
NAL files and are not asserted to be identical to the original map's `SOH_VAL`.
Total and per-acre views share fixed height and gradient scales across years.
All amounts are nominal dollars. Basemap imagery is current imagery supplied by
the existing tile service, not historical imagery.

## Build

Install `pyshp`, `shapely`, and `pyproj` in a Python environment, then run:

```sh
python build_history.py --source '/path/to/2025-09'
```

The source directory must contain `Data` and `Shp files`. Generic boundary names
are mapped to 2015 and 2016 based on their metadata dates. Preliminary 2026 is
excluded. Input files remain untouched. `data/manifest.json` records annual
counts and omissions. Annual compressed JSON and 128 compressed parcel-history
shards let the browser load only the selected years and clicked parcel histories.
Requires a browser supporting `DecompressionStream` and WebGL.

## Mapping rules

- Join CSV `PARCEL_ID` to shapefile `PARCELNO` as strings, preserving leading zeros.
- Omit nonpositive values or source land area, unmatched records, and invalid or
  empty geometry. These omissions apply to the map and its parcel histories.
- Acreage comes from polygon area in the source CRS converted to acres, with a
  combined acreage for IDs that have multiple geometry records. A repeated ID
  gets one history entry; each polygon part uses the parcel's total value.
- Simplify boundaries by three US survey feet with topology preservation, then
  transform to WGS84 and round coordinates to six decimals.
- Category codes come from each year's `DOR_UC`, using the existing broad buckets.
- Comparisons follow matching IDs. Splits, mergers and boundary changes are not
  reconciled. Missing baseline IDs are gray and show “No matching parcel”.
- Baseline category filters use the ending year's land use. Missing history is
  shown as a dash, never as a zero. Zero denominators are never compared.

GitHub Pages publishes this static site from the root of `main`. The original
`parcels.json` is retained for reference but the historical page does not load it.
