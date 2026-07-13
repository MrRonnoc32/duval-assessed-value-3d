"""
Build a compact parcels.json for the 3D deck.gl viz.

Inputs:
  - DCPAO pipe-delimited file (640MB). Row type 00001 → STRAP (field 2),
    assessed value SOH_VAL (field 23).
  - Parcel polygon shapefile (~400k parcels, EPSG:2236 / Florida East ftUS).

Output:
  - parcels.json — { "parcels": [ { "v": <assessed_value>,
                                    "a": <acres>,
                                    "u": <dor_use_code, 4-char string>,
                                    "p": [[[lng,lat], ...], ...] }, ... ] }
"""

import json
import os
import sys
import time
from osgeo import ogr, osr

ogr.UseExceptions()
osr.UseExceptions()

DCPAO_FILE = "/Users/conor/Downloads/jacksonville/property-pao/DCPAO REAL ESTATE PIPE DELIMITED TEXT CERTIFIED AS OF 10-13-25.txt"
SHAPEFILE = "/Users/conor/Downloads/jacksonville/property-pao/Parcel/Parcel_Polygons.shp"
OUTPUT_JSON = "/Users/conor/Taxable Value 3d plot/parcels.json"

# Tolerance for polygon simplification, in source units (US feet).
# 3 ft is well under a typical parcel boundary detail level.
SIMPLIFY_TOL_FT = 3.0

# Skip parcels with assessed value <= this threshold (keeps the viz uncluttered).
MIN_VALUE = 0  # set to 1000 etc. to skip vacant/exempt; 0 keeps everything


def load_value_index(path):
    """Stream DCPAO file, return dict[STRAP] -> (assessed_value, dor_code)."""
    idx = {}
    t0 = time.time()
    with open(path, "r", encoding="latin-1", errors="replace") as f:
        for i, line in enumerate(f):
            if not line.startswith("00001|"):
                continue
            parts = line.rstrip("\n").split("|")
            if len(parts) < 23:
                continue
            strap = parts[1]
            try:
                v = int(float(parts[22]))  # SOH_VAL (field 23, 1-indexed)
            except ValueError:
                continue
            dor = (parts[12] or "").strip()  # DOR_CD (field 13, 1-indexed)
            idx[strap] = (v, dor)
            if i and i % 1_000_000 == 0:
                print(f"  scanned {i:>9,} lines, {len(idx):>7,} parcels  ({time.time()-t0:.1f}s)")
    print(f"  done: {len(idx):,} STRAP→(value,dor) entries in {time.time()-t0:.1f}s")
    return idx


def make_transformer(src_layer):
    src = src_layer.GetSpatialRef()
    dst = osr.SpatialReference()
    dst.ImportFromEPSG(4326)
    # GDAL >= 3 uses authority-compliant axis order (lat,lng) for 4326 by default.
    dst.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
    src.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
    return osr.CoordinateTransformation(src, dst)


def ring_to_coords(ring):
    """Extract (lng, lat) list, rounding to 6 decimals (~11cm)."""
    out = []
    for i in range(ring.GetPointCount()):
        x, y, *_ = ring.GetPoint(i)
        out.append([round(x, 6), round(y, 6)])
    return out


def main():
    print("Loading assessed values from DCPAO…")
    values = load_value_index(DCPAO_FILE)

    print("Opening shapefile…")
    ds = ogr.Open(SHAPEFILE)
    layer = ds.GetLayer(0)
    n = layer.GetFeatureCount()
    print(f"  {n:,} parcels")

    transform = make_transformer(layer)

    strap_idx = layer.GetLayerDefn().GetFieldIndex("STRAP")
    acres_idx = layer.GetLayerDefn().GetFieldIndex("ACRES")

    out_parcels = []
    matched = 0
    skipped_no_value = 0
    skipped_low = 0
    skipped_bad_geom = 0
    t0 = time.time()

    for i in range(n):
        feat = layer.GetFeature(i) if False else layer.GetNextFeature()
        if feat is None:
            continue
        strap = feat.GetField(strap_idx)
        if not strap:
            continue
        entry = values.get(strap)
        if entry is None:
            skipped_no_value += 1
            continue
        v, dor = entry
        if v <= MIN_VALUE:
            skipped_low += 1
            continue
        acres = feat.GetField(acres_idx)
        try:
            acres = float(acres) if acres is not None else 0.0
        except (TypeError, ValueError):
            acres = 0.0
        # Round to 4 decimals — sub-thousandth-acre precision is meaningless here.
        acres = round(acres, 4)

        geom = feat.GetGeometryRef()
        if geom is None or geom.IsEmpty():
            skipped_bad_geom += 1
            continue

        # Simplify in source units (feet), then reproject.
        try:
            simp = geom.SimplifyPreserveTopology(SIMPLIFY_TOL_FT)
            if simp is None or simp.IsEmpty():
                simp = geom
        except Exception:
            simp = geom

        simp = simp.Clone()
        simp.Transform(transform)

        # Flatten MULTIPOLYGON into list of polygons; each polygon is list of rings.
        gtype = simp.GetGeometryName()
        rings_list = []  # list of [outer_ring, hole1, hole2, ...]

        if gtype == "POLYGON":
            polys = [simp]
        elif gtype == "MULTIPOLYGON":
            polys = [simp.GetGeometryRef(j) for j in range(simp.GetGeometryCount())]
        else:
            skipped_bad_geom += 1
            continue

        for poly in polys:
            rings = []
            for r in range(poly.GetGeometryCount()):
                ring = poly.GetGeometryRef(r)
                coords = ring_to_coords(ring)
                if len(coords) >= 4:
                    rings.append(coords)
            if rings:
                rings_list.append(rings)

        if not rings_list:
            skipped_bad_geom += 1
            continue

        # deck.gl PolygonLayer accepts polygons with holes as [outer, hole1, ...].
        # For MULTIPOLYGON, emit one record per sub-polygon — they share the attrs.
        for rings in rings_list:
            out_parcels.append({"v": v, "a": acres, "u": dor, "p": rings})
        matched += 1

        if matched and matched % 50_000 == 0:
            dt = time.time() - t0
            rate = matched / dt
            eta = (n - i) / rate if rate > 0 else 0
            print(f"  matched {matched:>7,}/{i:>7,}  ({rate:.0f}/s, eta {eta:.0f}s)")

    print(f"Matched: {matched:,}  no-value: {skipped_no_value:,}  "
          f"below-min: {skipped_low:,}  bad-geom: {skipped_bad_geom:,}")
    print(f"Total polygon records in output: {len(out_parcels):,}")

    # Stats for the viz (so the legend / scale can be set client-side).
    def percentiles(xs):
        xs = sorted(xs)
        pct = lambda q: xs[int(q * (len(xs) - 1))]
        return {
            "count": len(xs),
            "min": xs[0], "max": xs[-1],
            "p50": pct(0.50), "p90": pct(0.90), "p99": pct(0.99),
        }

    stats = {
        "value":     percentiles([p["v"] for p in out_parcels]),
        "acres":     percentiles([p["a"] for p in out_parcels if p["a"] > 0]),
        "per_acre":  percentiles([p["v"] / p["a"] for p in out_parcels if p["a"] > 0]),
    }
    print("Stats:", json.dumps(stats, indent=2, default=str))

    print(f"Writing {OUTPUT_JSON}…")
    with open(OUTPUT_JSON, "w") as f:
        json.dump({"stats": stats, "parcels": out_parcels}, f, separators=(",", ":"))
    size_mb = os.path.getsize(OUTPUT_JSON) / 1e6
    print(f"  wrote {size_mb:.1f} MB")


if __name__ == "__main__":
    main()
