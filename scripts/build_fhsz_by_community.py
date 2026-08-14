#!/usr/bin/env python3
"""
FHSZ composition by community boundary.

For each community, clips the authoritative CAL FIRE FHSZ polygons to the
official Census TIGERweb boundary and reports the share of land area in each
Fire Hazard Severity Zone tier, separately for State Responsibility Area (SRA)
and Local Responsibility Area (LRA).

Sources
  Boundaries : US Census Bureau TIGERweb, Places_CouSub_ConCity_SubMCD
  FHSZ SRA   : CAL FIRE / OSFM FHSZSRA_23_3     (SRA maps effective 2024-04-01)
  FHSZ LRA   : CAL FIRE / OSFM FHSZLRA25_v1_All (LRA map dated 2025-03-24)

Area method
  Geometries are in EPSG:4326. Areas are computed on a local equal-area
  approximation: longitude scaled by cos(centroid latitude), then planar area
  times (111,320 m/deg)^2. Error is well under 1% at city scale and cancels in
  the percentage shares reported here.
"""
import json, math, sys, urllib.parse, urllib.request
from shapely.geometry import shape, Polygon, MultiPolygon
from shapely.ops import unary_union
from shapely.affinity import scale as shp_scale

TIGER = "https://tigerweb.geo.census.gov/arcgis/rest/services/TIGERweb/Places_CouSub_ConCity_SubMCD/MapServer"
LAYERS = {
    "SRA": "https://services1.arcgis.com/jUJYIo9tSA7EHvfZ/ArcGIS/rest/services/FHSZSRA_23_3/FeatureServer/0/query",
    "LRA": "https://services1.arcgis.com/jUJYIo9tSA7EHvfZ/ArcGIS/rest/services/FHSALRA25_v1_All/FeatureServer/0/query",
}
UA = "firewise-fhsz-verification/1.0 (+https://www.firewisefences.com)"
DEG_M = 111320.0
TIER_ORDER = ["Very High", "High", "Moderate", "NonWildland"]


def req(url, params, post=False):
    data = urllib.parse.urlencode(params).encode()
    if post:
        r = urllib.request.Request(url, data=data, headers={"User-Agent": UA})
    else:
        r = urllib.request.Request(url + "?" + data.decode(), headers={"User-Agent": UA})
    with urllib.request.urlopen(r, timeout=180) as resp:
        return json.load(resp)


def esri_to_shapely(geom):
    """Esri polygon rings -> shapely (multi)polygon, honouring ring orientation."""
    raw_rings = [r for r in geom["rings"] if len(r) >= 4]
    outers, holes = [], []
    for raw in raw_rings:
        # Esri convention: outer rings are clockwise. With s = sum((x2-x1)(y2+y1)),
        # clockwise yields s > 0.
        (outers if signed_area(raw) > 0 else holes).append(Polygon(raw))
    if not outers:
        outers, holes = [Polygon(r) for r in raw_rings], []
    poly = unary_union([p.buffer(0) for p in outers])
    if holes:
        poly = poly.difference(unary_union([h.buffer(0) for h in holes]))
    return poly


def signed_area(ring):
    s = 0.0
    for (x1, y1), (x2, y2) in zip(ring, ring[1:]):
        s += (x2 - x1) * (y2 + y1)
    return s


def eq_area(geom, lat):
    return shp_scale(geom, xfact=math.cos(math.radians(lat)), yfact=1.0,
                     origin=(0, 0)).area * DEG_M * DEG_M


def tiger_boundary(name):
    for layer, kind in ((4, "Incorporated Place"), (5, "Census Designated Place")):
        d = req(f"{TIGER}/{layer}/query", {
            "where": f"STATE='06' AND BASENAME='{name}'",
            "outFields": "GEOID,NAME,BASENAME,AREALAND", "returnGeometry": "true",
            "outSR": "4326", "f": "json"})
        feats = d.get("features") or []
        if feats:
            f = feats[0]
            return esri_to_shapely(f["geometry"]), kind, f["attributes"]
    return None


def fhsz_features(url, boundary):
    minx, miny, maxx, maxy = boundary.bounds
    env = {"xmin": minx, "ymin": miny, "xmax": maxx, "ymax": maxy,
           "spatialReference": {"wkid": 4326}}
    out, offset = [], 0
    while True:
        d = req(url, {
            "geometry": json.dumps(env), "geometryType": "esriGeometryEnvelope",
            "inSR": "4326", "spatialRel": "esriSpatialRelIntersects",
            "outFields": "FHSZ_Description,SRA", "returnGeometry": "true",
            "outSR": "4326", "geometryPrecision": "6",
            "resultOffset": str(offset), "resultRecordCount": "1000", "f": "json",
        }, post=True)
        if "error" in d:
            raise RuntimeError(d["error"])
        feats = d.get("features", [])
        out += feats
        if not d.get("exceededTransferLimit") or not feats:
            break
        offset += len(feats)
    return out


def compose(name):
    hit = tiger_boundary(name)
    if not hit:
        return None
    boundary, kind, attrs = hit
    lat = boundary.centroid.y
    # Percentages are of the full municipal boundary area (land + inland/coastal
    # water inside the boundary), measured geometrically from the same polygon the
    # FHSZ layers are clipped to, so tier shares are internally consistent.
    land = eq_area(boundary, lat)
    rec = {"query_name": name, "census_name": attrs["NAME"], "geoid": attrs["GEOID"],
           "boundary_source": f"US Census TIGERweb {kind}",
           "boundary_area_sqmi": round(land / 2_589_988.0, 3),
           "census_land_area_sqmi": round(float(attrs["AREALAND"]) / 2_589_988.0, 3),
           "responsibility_areas": {}}
    for ra, url in LAYERS.items():
        parts = {}
        for f in fhsz_features(url, boundary):
            g = esri_to_shapely(f["geometry"]).buffer(0)
            clipped = g.intersection(boundary)
            if clipped.is_empty:
                continue
            parts.setdefault(f["attributes"]["FHSZ_Description"], []).append(clipped)
        # Dissolve within each tier, then make tiers mutually exclusive with the
        # more hazardous tier taking precedence where the published layers overlap.
        merged = {t: unary_union(v).buffer(0) for t, v in parts.items()}
        out, claimed = {}, None
        for t in TIER_ORDER:
            if t not in merged:
                continue
            g = merged[t] if claimed is None else merged[t].difference(claimed)
            claimed = merged[t] if claimed is None else unary_union([claimed, merged[t]])
            if g.is_empty:
                continue
            a = eq_area(g, lat)
            if 100.0 * a / land >= 0.05:
                out[t] = {"sq_mi": round(a / 2_589_988.0, 3),
                          "pct_of_boundary_area": round(100.0 * a / land, 2),
                          "pct_of_census_land": round(100.0 * a / float(attrs["AREALAND"]), 2)}
        rec["responsibility_areas"][ra] = out
    return rec


if __name__ == "__main__":
    results = []
    for line in sys.stdin.read().splitlines():
        if not line.strip():
            continue
        slug, name = line.split("\t")
        try:
            r = compose(name)
        except Exception as e:
            r = {"query_name": name, "error": repr(e)}
        r = r or {"query_name": name, "error": "no census boundary"}
        r["slug"] = slug
        results.append(r)
        print(json.dumps(r), flush=True)
    with open("data/fhsz_by_community.json", "w") as f:
        json.dump(results, f, indent=2)
