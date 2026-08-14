#!/usr/bin/env python3
"""
California population living in each Fire Hazard Severity Zone tier.

Method
  Every 2020 census block group in California is represented by its official
  Census Bureau *center of population* -- the population-weighted centroid, not
  the geographic one. Each center is tested against the statewide CAL FIRE FHSZ
  polygons and the block group's entire 2020 population is assigned to the tier
  its center falls in.

  This is a center-assignment method, not an areal apportionment. A block group
  that straddles a tier boundary is counted whole, on the side its population
  centre sits. Errors cancel in aggregate at state and county scale; they do not
  cancel for an individual block group.

Sources
  Population : US Census Bureau, Centers of Population by Block Group, 2020
               https://www2.census.gov/geo/docs/reference/cenpop2020/blkgrp/CenPop2020_Mean_BG06.txt
  FHSZ SRA   : CAL FIRE / OSFM FHSZSRA_23_3     (SRA maps effective 2024-04-01)
  FHSZ LRA   : CAL FIRE / OSFM FHSZLRA25_v1_All (LRA map dated 2025-03-24)
"""
import csv, json, os, sys
from collections import defaultdict
from shapely.geometry import Point, Polygon
from shapely.ops import unary_union
from shapely.strtree import STRtree

TIER_RANK = {"Very High": 3, "High": 2, "Moderate": 1, "NonWildland": 0}
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WORK = os.environ.get("FHSZ_WORK_DIR", HERE)


def signed_area(ring):
    return sum((x2 - x1) * (y2 + y1) for (x1, y1), (x2, y2) in zip(ring, ring[1:]))


def esri_to_shapely(geom):
    raw = [r for r in geom["rings"] if len(r) >= 4]
    outers = [Polygon(r) for r in raw if signed_area(r) > 0]
    holes = [Polygon(r) for r in raw if signed_area(r) <= 0]
    if not outers:
        outers, holes = [Polygon(r) for r in raw], []
    poly = unary_union([p.buffer(0) for p in outers])
    if holes:
        poly = poly.difference(unary_union([h.buffer(0) for h in holes]))
    return poly


def load(ra):
    feats = json.load(open(f"{WORK}/fhsz_{ra}_statewide.json"))
    geoms, tiers = [], []
    for f in feats:
        try:
            g = esri_to_shapely(f["geometry"])
        except Exception:
            continue
        if g.is_empty:
            continue
        geoms.append(g)
        tiers.append(f["attributes"]["FHSZ_Description"])
    print(f"{ra}: {len(geoms)} polygons", file=sys.stderr)
    return geoms, tiers, STRtree(geoms)


def main():
    layers = {ra: load(ra) for ra in ("SRA", "LRA")}

    rows = list(csv.DictReader(open(f"{WORK}/CenPop2020_Mean_BG06.txt", encoding="utf-8-sig")))
    print(f"{len(rows)} block groups", file=sys.stderr)

    state = defaultdict(int)
    county = defaultdict(lambda: defaultdict(int))
    detail = []
    for i, r in enumerate(rows):
        pop = int(r["POPULATION"])
        pt = Point(float(r["LONGITUDE"]), float(r["LATITUDE"]))
        best_tier, best_ra = None, None
        for ra, (geoms, tiers, tree) in layers.items():
            for idx in tree.query(pt):
                if not geoms[idx].contains(pt):
                    continue
                t = tiers[idx]
                if best_tier is None or TIER_RANK.get(t, -1) > TIER_RANK.get(best_tier, -1):
                    best_tier, best_ra = t, ra
        key = f"{best_ra} {best_tier}" if best_tier else "No mapped FHSZ polygon"
        state[key] += pop
        county[r["COUNTYFP"]][key] += pop
        detail.append({"geoid": r["STATEFP"] + r["COUNTYFP"] + r["TRACTCE"] + r["BLKGRPCE"],
                       "population": pop, "assignment": key})
        if i % 2500 == 0:
            print(f"  {i}/{len(rows)}", file=sys.stderr, flush=True)

    json.dump({"state": dict(state), "county": {k: dict(v) for k, v in county.items()}},
              open(f"{WORK}/data/population_by_fhsz_raw.json", "w"), indent=2)
    json.dump(detail, open(f"{WORK}/data/population_by_fhsz_blockgroups.json", "w"))
    total = sum(state.values())
    print(f"\nTotal population {total:,}")
    for k, v in sorted(state.items(), key=lambda kv: -kv[1]):
        print(f"  {k:32s} {v:>12,}  {100*v/total:5.2f}%")


if __name__ == "__main__":
    main()
