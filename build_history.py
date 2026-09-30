"""Build historical map assets from annual NAL CSVs and parcel boundaries.

Run with Python and pyshp, shapely, pyproj installed. Inputs remain untouched.
"""
import argparse, csv, gzip, json, pathlib, collections, time
import shapefile
from shapely.geometry import shape
from pyproj import CRS, Transformer

def write(path, obj):
    with gzip.open(path, 'wt', encoding='utf-8', compresslevel=6) as f:
        json.dump(obj, f, separators=(',', ':'), allow_nan=False)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--source', type=pathlib.Path, required=True)
    ap.add_argument('--output', type=pathlib.Path, default=pathlib.Path(__file__).parent/'data')
    args = ap.parse_args(); args.output.mkdir(exist_ok=True, parents=True)
    history = [collections.defaultdict(list) for _ in range(128)]
    manifest = {'years': [], 'value_fields': ['AV_NSD', 'JV'], 'history_shards': 128,
                'area': 'polygon area in source CRS, converted to acres',
                'comparison': 'matching parcel IDs; IDs do not guarantee unchanged boundaries'}
    for year in range(2015, 2026):
        t = time.time(); values = {}; counts = collections.Counter()
        csv_path = args.source/'Data'/f'{year}F'/f'NAL_{year}_26Duval_F.csv'
        with csv_path.open(encoding='utf-8-sig', newline='') as f:
            for row in csv.DictReader(f):
                try:
                    pid = row['PARCEL_ID'].strip()
                    v, j = int(row['AV_NSD']), int(row['JV'])
                    if not pid or v <= 0 or j <= 0 or float(row['LND_SQFOOT']) <= 0:
                        counts['zero_or_missing'] += 1; continue
                    # NAL DOR_UC is a two-digit code; original UI expects four digits.
                    values[pid] = (v, j, f"{int(row['DOR_UC']):02d}00")
                except (ValueError, KeyError): counts['invalid_value'] += 1
        folder = {2015: 'Duval_pin (1)', 2016: 'Duval_pin (2)', 2017: 'Duval_pin (3)'}.get(year, f'duval_{year}pin' if year != 2018 else 'duval_2018pin.shp')
        shp = next((args.source/'Shp files'/folder).glob('*.shp'))
        crs = CRS.from_wkt(shp.with_suffix('.prj').read_text())
        transform = Transformer.from_crs(crs, 4326, always_xy=True)
        metres = crs.axis_info[0].unit_conversion_factor
        grouped = collections.defaultdict(list)
        reader = shapefile.Reader(str(shp))
        for sr in reader.iterShapeRecords():
            pid = str(sr.record['PARCELNO']).strip()
            if pid not in values: counts['unmatched_geometry'] += 1; continue
            try:
                geom = shape(sr.shape.__geo_interface__)
                if geom.is_empty or not geom.is_valid or geom.area <= 0:
                    counts['invalid_geometry'] += 1; continue
                grouped[pid].append(geom)
            except (ValueError, TypeError): counts['invalid_geometry'] += 1
        parcels=[]; total=0; hist_count=0
        for pid, geoms in grouped.items():
            v,j,u=values[pid]
            # Multiple geometry records share one value and a combined acreage.
            area=sum(g.area for g in geoms)*metres*metres/4046.8564224
            if area<=0: continue
            a=round(area,6)
            if a<=0: continue
            polygons=[]
            for geom in geoms:
                simp=geom.simplify(3*0.3048006096/metres,preserve_topology=True)
                for poly in ([simp] if simp.geom_type=='Polygon' else simp.geoms):
                    rings=[]
                    for ring in [poly.exterior, *poly.interiors]:
                        x,y=transform.transform(*zip(*ring.coords))
                        coords=[[round(lng,6),round(lat,6)] for lng,lat in zip(x,y)]
                        if len(coords)>=4: rings.append(coords)
                    if rings: polygons.append(rings)
            if not polygons: continue
            for rings in polygons: parcels.append({'i':pid,'v':v,'j':j,'a':a,'u':u,'p':rings})
            history[int(pid[:-1])%128][pid].append([year,v,j,a,u])
            hist_count+=1; total+=v
        file=f'parcels-{year}.json.gz'; write(args.output/file, {'year':year,'parcels':parcels})
        manifest['years'].append({'year':year,'file':file,'parcels':hist_count,'polygons':len(parcels),
                                  'assessed_total':total,'skipped':dict(counts),
                                  'unmatched_values':len(values.keys()-grouped.keys())})
        print(f'{year}: {hist_count:,} parcels, {len(parcels):,} polygons, {(args.output/file).stat().st_size/1e6:.1f} MB compressed, {time.time()-t:.1f}s',flush=True)
    for n, shard in enumerate(history): write(args.output/f'history-{n}.json.gz', shard)
    (args.output/'manifest.json').write_text(json.dumps(manifest,indent=2))
    print('Complete.',flush=True)

if __name__=='__main__': main()
