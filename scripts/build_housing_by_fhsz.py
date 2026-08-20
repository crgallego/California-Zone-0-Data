#!/usr/bin/env python3
"""
California housing units in each Fire Hazard Severity Zone tier.

Method
  This script does no geometry. It reuses the block-group hazard assignments
  produced by build_population_by_fhsz.py -- each 2020 census block group placed
  in a tier by testing its Census center of population against the CAL FIRE
  statewide FHSZ layers -- and attaches housing counts to them. The tier
  assignment is therefore identical to the published population dataset, and the
  two files can be read side by side without reconciling two methods.

  Housing units and occupied housing units are 2020 census counts, complete
  enumerations rather than samples.

  Detached single-family and mobile-home counts are not collected by the
  decennial census. They are estimated by applying each block group's ACS share
  of units in structure to that block group's 2020 census housing-unit count.
  The share is measured; the vintage difference between the 2020 census count
  and the 2020-2024 ACS share is an approximation, and 129 block groups holding
  648 housing units between them have no ACS estimate and contribute zero.

Why housing units and not households
  Occupied units are the better answer to "how many families." Total housing
  units are the better answer to anything about the physical building stock: in
  the State Responsibility Area more than one housing unit in five is vacant or
  seasonal, and a seasonally occupied cabin has the same fence as any other.
  Both columns are published so the question decides the denominator.

Sources
  Housing units, occupied units, population
             : US Census Bureau, 2020 Census Redistricting Data (PL 94-171),
               California. Geographic header fields POP100 and HU100; occupied
               units from segment 2, table H1.
               https://www2.census.gov/programs-surveys/decennial/2020/data/01-Redistricting_File--PL_94-171/California/ca2020.pl.zip
  Units in structure
             : US Census Bureau, ACS 2020-2024 5-year, table B25024, block group.
               https://www2.census.gov/programs-surveys/acs/summary_file/2024/table-based-SF/data/5YRData/acsdt5y2024-b25024.dat
  Hazard tier: assignments from build_population_by_fhsz.py, which queries
               CAL FIRE / OSFM FHSZSRA_23_3 and FHSZLRA25_v1_All.

Inputs expected in $FHSZ_WORK_DIR (defaults to the repository root):
  data/population_by_fhsz_blockgroups.json   (build_population_by_fhsz.py)
  pl2020/cageo2020.pl, pl2020/ca000022020.pl (unzipped ca2020.pl.zip)
  acsdt5y2024-b25024.dat
"""
import csv, json, os, sys
from collections import defaultdict

TIER_RANK = {"Very High": 3, "High": 2, "Moderate": 1, "NonWildland": 0}
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WORK = os.environ.get("FHSZ_WORK_DIR", HERE)

# PL 94-171 geographic header, zero-indexed pipe-delimited field positions
G_SUMLEV, G_LOGRECNO, G_GEOCODE, G_NAME = 2, 7, 9, 87
G_POP100, G_HU100 = 90, 91

# Very High everywhere the draft reaches: the whole State Responsibility Area,
# where PRC 4291 applies across tiers, plus Very High in the Local
# Responsibility Area. See METHODOLOGY.md; this encodes the draft's scope
# language and is the one aggregate here that is an interpretation.
DRAFT_SCOPE = ("SRA Very High", "SRA High", "SRA Moderate", "LRA Very High")
VERY_HIGH = ("SRA Very High", "LRA Very High")


def load_census_housing():
    """Block-group housing counts and county names from the PL 94-171 header."""
    bgs, counties, by_logrecno = {}, {}, {}
    with open(f"{WORK}/pl2020/cageo2020.pl", encoding="latin-1") as f:
        for line in f:
            p = line.rstrip("\n").split("|")
            if p[G_SUMLEV] == "050":
                counties[p[G_GEOCODE][2:5]] = p[G_NAME]
            elif p[G_SUMLEV] == "150":
                rec = {"pop": int(p[G_POP100]), "hu": int(p[G_HU100])}
                bgs[p[G_GEOCODE]] = rec
                by_logrecno[p[G_LOGRECNO]] = rec

    with open(f"{WORK}/pl2020/ca000022020.pl", encoding="latin-1") as f:
        for line in f:
            p = line.rstrip("\n").split("|")
            rec = by_logrecno.get(p[4])
            if rec is None:
                continue
            total, occupied = int(p[-3]), int(p[-2])  # H1: total, occupied, vacant
            if total != rec["hu"]:
                raise SystemExit(f"H1 disagrees with HU100: {total} vs {rec['hu']}")
            rec["occ"] = occupied

    print(f"{len(bgs):,} block groups, {len(counties)} counties", file=sys.stderr)
    return bgs, counties


def load_unit_shares():
    """ACS share of units that are 1-unit detached / mobile home, per block group."""
    shares = {}
    with open(f"{WORK}/acsdt5y2024-b25024.dat") as f:
        f.readline()
        for line in f:
            if not line.startswith("1500000US06"):
                continue
            p = line.rstrip("\n").split("|")
            total, detached, mobile = int(p[1]), int(p[3]), int(p[19])
            if total > 0:
                shares[p[0][9:]] = (detached / total, mobile / total)
    print(f"unit-in-structure shares for {len(shares):,} block groups", file=sys.stderr)
    return shares


def main():
    assignments = json.load(open(f"{WORK}/data/population_by_fhsz_blockgroups.json"))
    census, counties = load_census_housing()
    shares = load_unit_shares()

    FIELDS = ("housing_units", "occupied", "detached", "mobile", "population")
    state = defaultdict(lambda: defaultdict(float))
    county = defaultdict(lambda: defaultdict(lambda: defaultdict(float)))
    unshared = {"block_groups": 0, "housing_units": 0}

    for row in assignments:
        geoid, tier = row["geoid"], row["assignment"]
        rec = census[geoid]
        d_share, m_share = shares.get(geoid, (0.0, 0.0))
        if geoid not in shares:
            unshared["block_groups"] += 1
            unshared["housing_units"] += rec["hu"]
        if rec["pop"] != row["population"]:
            raise SystemExit(f"population disagrees for {geoid}")
        vals = {"housing_units": rec["hu"], "occupied": rec["occ"],
                "detached": rec["hu"] * d_share, "mobile": rec["hu"] * m_share,
                "population": rec["pop"]}
        for k, v in vals.items():
            state[tier][k] += v
            county[geoid[2:5]][tier][k] += v

    tiers = sorted(state, key=lambda a: (-TIER_RANK.get(a.split(" ", 1)[-1], -1), a))

    with open(f"{WORK}/data/housing_by_fhsz_county.csv", "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["county_fips", "county_name", "responsibility_area", "fhsz_tier",
                    "housing_units", "occupied_housing_units",
                    "detached_single_family_est", "mobile_homes_est", "population",
                    "pct_of_county_housing_units"])
        for fips in sorted(county):
            total = sum(v["housing_units"] for v in county[fips].values())
            for tier in tiers:
                v = county[fips].get(tier)
                if not v or not (v["housing_units"] or v["population"]):
                    continue
                ra, name = tier.split(" ", 1) if " " in tier else ("NONE", tier)
                w.writerow([fips, counties[fips], ra, name,
                            int(v["housing_units"]), int(v["occupied"]),
                            round(v["detached"]), round(v["mobile"]),
                            int(v["population"]),
                            round(100 * v["housing_units"] / total, 2) if total else ""])

    def rollup(keys):
        return {k: round(sum(state[t][k] for t in keys)) for k in FIELDS}

    totals = {k: round(sum(v[k] for v in state.values())) for k in FIELDS}
    json.dump({
        "state": {t: {k: round(state[t][k]) for k in FIELDS} for t in tiers},
        "totals": totals,
        "aggregates": {
            "very_high": rollup(VERY_HIGH),
            "draft_scope": rollup(DRAFT_SCOPE),
        },
        "aggregate_basis": {
            "very_high": "Very High Fire Hazard Severity Zone, both responsibility areas",
            "draft_scope": "the whole State Responsibility Area plus Very High in the "
                           "Local Responsibility Area; an interpretation of the August 19, "
                           "2026 final draft's scope, not a mapped category",
        },
        "block_groups_without_acs_structure_estimate": unshared,
    }, open(f"{WORK}/data/housing_by_fhsz_state.json", "w"), indent=2)

    print(f"\nHousing units {totals['housing_units']:,}   "
          f"occupied {totals['occupied']:,}   detached {totals['detached']:,}")
    for tier in tiers:
        v = state[tier]
        print(f"  {tier:24s} hu {v['housing_units']:>10,.0f}  occ {v['occupied']:>10,.0f}  "
              f"det {v['detached']:>10,.0f}  pop {v['population']:>11,.0f}")
    for name, agg in (("Very High", rollup(VERY_HIGH)), ("Draft scope", rollup(DRAFT_SCOPE))):
        print(f"\n{name}: {agg['housing_units']:,} housing units, "
              f"{agg['occupied']:,} occupied, {agg['detached']:,} detached, "
              f"{agg['population']:,} people")


if __name__ == "__main__":
    main()
