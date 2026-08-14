#!/usr/bin/env python3
"""Download the statewide CAL FIRE FHSZ polygons, paged, to local GeoJSON-ish JSON."""
import json, sys, urllib.parse, urllib.request

UA = "firewise-fhsz-verification/1.0 (+https://www.firewisefences.com)"
SERVICES = {
    "SRA": "https://services1.arcgis.com/jUJYIo9tSA7EHvfZ/ArcGIS/rest/services/FHSZSRA_23_3/FeatureServer/0/query",
    "LRA": "https://services1.arcgis.com/jUJYIo9tSA7EHvfZ/ArcGIS/rest/services/FHSALRA25_v1_All/FeatureServer/0/query",
}


def page(url, offset, n=500):
    body = urllib.parse.urlencode({
        "where": "1=1", "outFields": "FHSZ_Description", "returnGeometry": "true",
        "outSR": "4326", "geometryPrecision": "5",
        "resultOffset": str(offset), "resultRecordCount": str(n), "f": "json",
    }).encode()
    req = urllib.request.Request(url, data=body, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=300) as r:
        return json.load(r)


for ra, url in SERVICES.items():
    feats, off = [], 0
    while True:
        d = page(url, off)
        if "error" in d:
            print(ra, "ERROR", d["error"], file=sys.stderr); break
        f = d.get("features", [])
        feats += f
        print(f"{ra} {len(feats)}", file=sys.stderr, flush=True)
        if not d.get("exceededTransferLimit") or not f:
            break
        off += len(f)
    json.dump(feats, open(f"/Users/litbox/.buzz/.scratch/fhsz_{ra}_statewide.json", "w"))
    print(ra, "saved", len(feats), file=sys.stderr)
