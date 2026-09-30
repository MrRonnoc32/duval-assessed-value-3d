"""Verify generated assets and their parcel histories without modifying them."""
import pathlib, json, gzip, math

root=pathlib.Path(__file__).parent/'data'
manifest=json.loads((root/'manifest.json').read_text())
assert [x['year'] for x in manifest['years']]==list(range(2015,2026))
samples=[]
for entry in manifest['years']:
    with gzip.open(root/entry['file'],'rt') as f: data=json.load(f)
    assert data['year']==entry['year']
    parcels=data['parcels']; assert len(parcels)==entry['polygons']
    unique={}
    for d in parcels:
        assert d['v']>0 and d['j']>0 and d['a']>0
        assert len(d['u'])==4 and d['u'].isdigit()
        assert d['i'].endswith('R') and d['i'][:-1].isdigit()
        signature=(d['v'],d['j'],d['a'],d['u'])
        if d['i'] in unique: assert unique[d['i']]==signature
        unique[d['i']]=signature
        for ring in d['p']:
            assert len(ring)>=4 and ring[0]==ring[-1]
            for lng,lat in ring:
                assert math.isfinite(lng) and math.isfinite(lat)
                assert -83<lng<-80 and 29<lat<32
    assert len(unique)==entry['parcels']
    assert sum(v[0] for v in unique.values())==entry['assessed_total']
    for d in parcels[::max(1,len(parcels)//100)]:
        samples.append((entry['year'],d['i'],[d['v'],d['j'],d['a'],d['u']]))
    print(f"{entry['year']}: counts, unique totals, values, categories and coordinates passed",flush=True)
for shard in range(128):
    with gzip.open(root/f'history-{shard}.json.gz','rt') as f: history=json.load(f)
    for pid, rows in history.items():
        assert int(pid[:-1])%128==shard
        years=[r[0] for r in rows]
        assert years==sorted(set(years))
    for year,pid,values in samples:
        if int(pid[:-1])%128==shard:
            assert next(r[1:] for r in history[pid] if r[0]==year)==values
print(f"All history shards and {len(samples)} map-to-history samples passed.",flush=True)
