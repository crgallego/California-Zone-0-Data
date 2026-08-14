#!/usr/bin/env python3
"""
Year the housing stock was built, in the same Fire Hazard Severity Zone
assignments as the housing file, plus year-built on the DINS structures
that already carry a fence-material record.

Why this dataset exists
  Zone 0 is a retrofit rule. Chapter 7A of the California Building Code
  (now relocated into the California Wildland-Urban Interface Code) is a
  new-construction rule for the building, effective on permit applications
  in 2008. Neither is a census of how old the houses already standing in
  the hazard zones are. ACS table B25034 answers that for the stock.
  DINS YEARBUILT answers it on the same surviving houses whose fence
  material we already publish, and can be cut at 2008 because it is a
  year, not a decade.

The ACS cut that is honest
  B25034 buckets 2000-2009 as one cell. Chapter 7A begins in 2008. The
  script therefore does NOT publish an ACS "built before Chapter 7A"
  count. It publishes:

    pre-2000          definitely before 7A
    2000-2009         straddles the rule; do not split it
    2010 or later     after 7A
    pre-2010          the clean ACS sentence: built before the 2010s

  DINS can be cut at 2008. That cut is labelled as parcel year-built on a
  wildfire-exposed sample, not as a census of the zone.

Chapter 7A is not a fence rule
  7A (CBC 701A.3 / current OSFM application date 2008-07-01 for the WUI
  code) governs the building and listed accessory structures that need a
  permit. It is not a statewide requirement to replace an attached wood
  fence. A house built in 2015 can still have a combustible fence. The
  DINS cross-tab is there to test whether the fence mix actually moved
  after 2008, not to imply that 7A required it to.

Sources
  Year structure built
             : US Census Bureau, ACS 2020-2024 5-year, table B25034,
               block group.
               https://www2.census.gov/programs-surveys/acs/summary_file/2024/table-based-SF/data/5YRData/acsdt5y2024-b25034.dat
               Columns: B25034_001 total; _002 2020 or later; _003 2010-2019;
               _004 2000-2009; _005 1990-1999; _006 1980-1989; _007 1970-1979;
               _008 1960-1969; _009 1950-1959; _010 1940-1949; _011 1939 or earlier.
  Housing units
             : US Census Bureau, 2020 Census Redistricting Data (PL 94-171),
               same files as build_housing_by_fhsz.py.
  Hazard tier: assignments from build_population_by_fhsz.py
  Year built (parcel) and fence
             : CAL FIRE DINS, POSTFIRE_MASTER_DATA_SHARE, YEARBUILT and
               FENCEATTACHEDTOSTRUCTURE. Surviving single-family only,
               same basis as fence_attachment_dins.json.

Inputs expected in $FHSZ_WORK_DIR (defaults to the repository root):
  data/population_by_fhsz_blockgroups.json
  pl2020/cageo2020.pl, pl2020/ca000022020.pl
  acsdt5y2024-b25034.dat

Outputs are always written next to this script's repository, not to WORK.
"""
import csv, json, os, sys, urllib.parse, urllib.request
from collections import defaultdict
from datetime import date

TIER_RANK = {"Very High": 3, "High": 2, "Moderate": 1, "NonWildland": 0}
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WORK = os.environ.get("FHSZ_WORK_DIR", HERE)
OUT = os.path.join(HERE, "data")

G_SUMLEV, G_LOGRECNO, G_GEOCODE, G_NAME = 2, 7, 9, 87
G_POP100, G_HU100 = 90, 91

DRAFT_SCOPE = ("SRA Very High", "SRA High", "SRA Moderate", "LRA Very High")
VERY_HIGH = ("SRA Very High", "LRA Very High")
POS_TRIGGER = ("SRA Very High", "SRA High", "LRA Very High")  # Civil Code 1102.19 surviving number

# ACS B25034 estimate columns (1-indexed in the table; file is GEO_ID then
# interleaved estimate/moe). Index in the estimate-only list:
BUCKETS = (
    ("built_2020_or_later", 1),
    ("built_2010_to_2019", 2),
    ("built_2000_to_2009", 3),
    ("built_1990_to_1999", 4),
    ("built_1980_to_1989", 5),
    ("built_1970_to_1979", 6),
    ("built_1960_to_1969", 7),
    ("built_1950_to_1959", 8),
    ("built_1940_to_1949", 9),
    ("built_1939_or_earlier", 10),
)
PRE_2000 = (
    "built_1990_to_1999", "built_1980_to_1989", "built_1970_to_1979",
    "built_1960_to_1969", "built_1950_to_1959", "built_1940_to_1949",
    "built_1939_or_earlier",
)
PRE_2010 = PRE_2000 + ("built_2000_to_2009",)
POST_2010 = ("built_2010_to_2019", "built_2020_or_later")

SERVICE = (
    "https://services1.arcgis.com/jUJYIo9tSA7EHvfZ/arcgis/rest/services/"
    "POSTFIRE_MASTER_DATA_SHARE/FeatureServer/0/query"
)
FENCE = "FENCEATTACHEDTOSTRUCTURE"
SFR = "STRUCTURETYPE LIKE 'Single Family Residence%'"
SURVIVING = "DAMAGE = 'No Damage'"
DETERMINED = ("Combustible", "Non Combustible", "No Fence")
YEAR_MIN, YEAR_MAX = 1800, 2026


def load_census_housing():
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
            total, occupied = int(p[-3]), int(p[-2])
            if total != rec["hu"]:
                raise SystemExit(f"H1 disagrees with HU100: {total} vs {rec['hu']}")
            rec["occ"] = occupied
    print(f"{len(bgs):,} block groups, {len(counties)} counties", file=sys.stderr)
    return bgs, counties


def load_year_shares():
    """Per-block-group ACS shares of housing units by year-built bucket."""
    shares, raw_totals = {}, {}
    mismatches = 0
    with open(f"{WORK}/acsdt5y2024-b25034.dat") as f:
        f.readline()
        for line in f:
            if not line.startswith("1500000US06"):
                continue
            p = line.rstrip("\n").split("|")
            estimates = [int(p[i]) for i in range(1, len(p), 2)]
            total = estimates[0]
            parts = estimates[1:]
            if total != sum(parts):
                mismatches += 1
            if total <= 0:
                continue
            geoid = p[0][9:]
            shares[geoid] = {name: parts[idx - 1] / total for name, idx in BUCKETS}
            raw_totals[geoid] = total
    if mismatches:
        raise SystemExit(f"B25034 parts did not sum to total in {mismatches} rows")
    print(f"year-built shares for {len(shares):,} block groups", file=sys.stderr)
    return shares


def rollup_cuts(bucket_counts):
    pre2000 = sum(bucket_counts[k] for k in PRE_2000)
    mid = bucket_counts["built_2000_to_2009"]
    post = sum(bucket_counts[k] for k in POST_2010)
    pre2010 = pre2000 + mid
    total = pre2010 + post
    def pct(n):
        return round(100 * n / total, 2) if total else None
    return {
        "housing_units": round(total),
        "pre_2000": round(pre2000),
        "built_2000_to_2009": round(mid),
        "pre_2010": round(pre2010),
        "built_2010_or_later": round(post),
        "pct_pre_2000": pct(pre2000),
        "pct_2000_to_2009": pct(mid),
        "pct_pre_2010": pct(pre2010),
        "pct_2010_or_later": pct(post),
        "buckets": {k: round(bucket_counts[k]) for k, _ in BUCKETS},
    }


def build_acs(assignments, census, counties, shares):
    state = defaultdict(lambda: defaultdict(float))
    county = defaultdict(lambda: defaultdict(lambda: defaultdict(float)))
    unshared = {"block_groups": 0, "housing_units": 0}

    for row in assignments:
        geoid, tier = row["geoid"], row["assignment"]
        rec = census[geoid]
        if rec["pop"] != row["population"]:
            raise SystemExit(f"population disagrees for {geoid}")
        sh = shares.get(geoid)
        if sh is None:
            unshared["block_groups"] += 1
            unshared["housing_units"] += rec["hu"]
            continue
        for name, _ in BUCKETS:
            n = rec["hu"] * sh[name]
            state[tier][name] += n
            county[geoid[2:5]][tier][name] += n

    tiers = sorted(state, key=lambda a: (-TIER_RANK.get(a.split(" ", 1)[-1], -1), a))

    def pack(src):
        return rollup_cuts({k: src.get(k, 0.0) for k, _ in BUCKETS})

    with open(os.path.join(OUT, "year_built_by_fhsz_county.csv"), "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow([
            "county_fips", "county_name", "responsibility_area", "fhsz_tier",
            "housing_units", "pre_2000", "built_2000_to_2009", "pre_2010",
            "built_2010_or_later", "pct_pre_2000", "pct_pre_2010",
            "pct_2010_or_later",
        ] + [name for name, _ in BUCKETS])
        for fips in sorted(county):
            for tier in tiers:
                v = county[fips].get(tier)
                if not v:
                    continue
                cuts = pack(v)
                if not cuts["housing_units"]:
                    continue
                ra, name = tier.split(" ", 1) if " " in tier else ("NONE", tier)
                w.writerow([
                    fips, counties[fips], ra, name,
                    cuts["housing_units"], cuts["pre_2000"],
                    cuts["built_2000_to_2009"], cuts["pre_2010"],
                    cuts["built_2010_or_later"], cuts["pct_pre_2000"],
                    cuts["pct_pre_2010"], cuts["pct_2010_or_later"],
                ] + [cuts["buckets"][b] for b, _ in BUCKETS])

    by_tier = {t: pack(state[t]) for t in tiers}

    def sum_tiers(keys):
        acc = defaultdict(float)
        for t in keys:
            for k, _ in BUCKETS:
                acc[k] += state[t][k]
        return pack(acc)

    totals = sum_tiers(tiers)
    doc = {
        "what_this_is": (
            "Year structure built for California housing units, using the same "
            "block-group Fire Hazard Severity Zone assignments as "
            "housing_by_fhsz_*. ACS B25034 decade shares are applied to each "
            "block group's 2020 census housing-unit count. The 2000-2009 "
            "bucket straddles Chapter 7A (2008) and is not split."
        ),
        "source": {
            "year_built": (
                "US Census Bureau, ACS 2020-2024 5-year, table B25034, "
                "block group"
            ),
            "housing_units": (
                "US Census Bureau, 2020 Census Redistricting Data (PL 94-171)"
            ),
            "hazard_tier": "data/population_by_fhsz_blockgroups.json",
            "chapter_7a_application": (
                "California Building Code Chapter 7A / current California "
                "Wildland-Urban Interface Code: new buildings with a building-"
                "permit application on or after 2008-07-01 in a Fire Hazard "
                "Severity Zone or designated WUI area (SRA new buildings "
                "were brought in as of 2008-01-01). OSFM, Building in the "
                "Wildland; 2022 CBC 701A.3.1."
            ),
            "retrieved": os.environ.get("YEAR_BUILT_RETRIEVED", str(date.today())),
        },
        "state": by_tier,
        "totals": totals,
        "aggregates": {
            "very_high": sum_tiers(VERY_HIGH),
            "draft_scope": sum_tiers(DRAFT_SCOPE),
            "point_of_sale_trigger": sum_tiers(POS_TRIGGER),
        },
        "aggregate_basis": {
            "very_high": "Very High Fire Hazard Severity Zone, both responsibility areas",
            "draft_scope": (
                "the whole State Responsibility Area plus Very High in the "
                "Local Responsibility Area; an interpretation of the April 17, "
                "2026 draft's scope, not a mapped category"
            ),
            "point_of_sale_trigger": (
                "SRA High and Very High plus LRA Very High — the housing "
                "count that survives the Civil Code 1102.19 responsibility-"
                "area question in compliance_forcing_functions.json. Joined "
                "here so age and the point-of-sale clock can be read together. "
                "Not a claim that 1102.19 is a fence rule."
            ),
        },
        "cuts": {
            "pre_2000": "ACS buckets 1939-or-earlier through 1990-1999. Definitely before Chapter 7A.",
            "built_2000_to_2009": "Straddles the 2008 Chapter 7A start. Do not split this cell.",
            "pre_2010": "Everything ACS can put before the 2010s. The clean ACS sentence.",
            "built_2010_or_later": "After Chapter 7A. Still not a fence-rule cohort.",
        },
        "block_groups_without_acs_year_built": unshared,
        "what_this_is_not": (
            "Not a count of houses built under a fence clause. Chapter 7A is "
            "a new-construction standard for the building, not a statewide "
            "requirement to replace an attached wood fence. Not a count of "
            "houses that owe Zone 0 today. The 2000-2009 ACS bucket is not "
            "a Chapter 7A cohort."
        ),
    }
    with open(os.path.join(OUT, "year_built_by_fhsz_state.json"), "w") as f:
        json.dump(doc, f, indent=2)
        f.write("\n")
    return doc


def grouped_count(where, group_by):
    params = {
        "where": where,
        "groupByFieldsForStatistics": ",".join(group_by),
        "outStatistics": json.dumps(
            [{"statisticType": "count", "onStatisticField": "OBJECTID",
              "outStatisticFieldName": "n"}]
        ),
        "f": "json",
    }
    url = SERVICE + "?" + urllib.parse.urlencode(params)
    with urllib.request.urlopen(url, timeout=180) as r:
        payload = json.load(r)
    if "error" in payload:
        sys.exit(f"DINS query failed: {payload['error']}")
    out = {}
    for feature in payload["features"]:
        a = feature["attributes"]
        key = tuple(a[g] if a[g] is not None else "" for g in group_by)
        out[key] = out.get(key, 0) + a["n"]
    return out


def era_of(year):
    if year < 2000:
        return "pre_2000"
    if year < 2008:
        return "2000_to_2007"
    if year < 2010:
        return "2008_to_2009"
    if year < 2020:
        return "2010_to_2019"
    return "2020_or_later"


def fence_rates(counts):
    determined = sum(counts.get(v, 0) for v in DETERMINED)
    attached = counts.get("Combustible", 0) + counts.get("Non Combustible", 0)
    comb = counts.get("Combustible", 0)
    if not determined:
        return None
    return {
        "structures_determined": determined,
        "fence_attached": attached,
        "attached_combustible": comb,
        "attached_non_combustible": counts.get("Non Combustible", 0),
        "no_fence": counts.get("No Fence", 0),
        "pct_fence_attached": round(100 * attached / determined, 2),
        "pct_of_attached_combustible": (
            round(100 * comb / attached, 2) if attached else None
        ),
        "pct_combustible_fence_attached": round(100 * comb / determined, 2),
    }


def build_dins():
    where = f"{SURVIVING} AND {SFR}"
    raw = grouped_count(where, ["YEARBUILT", FENCE])
    undetermined_year = 0
    valid_n = 0
    by_era = defaultdict(lambda: defaultdict(int))
    by_year_valid = defaultdict(int)
    pre2008_fence = defaultdict(int)
    post2008_fence = defaultdict(int)

    for (year, fence), n in raw.items():
        try:
            y = int(year) if year != "" else None
        except (TypeError, ValueError):
            y = None
        if y is None or y < YEAR_MIN or y > YEAR_MAX:
            undetermined_year += n
            continue
        valid_n += n
        by_year_valid[y] += n
        era = era_of(y)
        by_era[era][fence or "(blank)"] += n
        if y < 2008:
            pre2008_fence[fence or "(blank)"] += n
        else:
            post2008_fence[fence or "(blank)"] += n

    eras = ("pre_2000", "2000_to_2007", "2008_to_2009", "2010_to_2019", "2020_or_later")
    by_era_out = {}
    for era in eras:
        rec = dict(by_era[era])
        rec["n"] = sum(rec.values())
        rec["rates"] = fence_rates(
            {k: v for k, v in rec.items() if k != "n"}
        )
        by_era_out[era] = rec

    pre = fence_rates(pre2008_fence)
    post = fence_rates(post2008_fence)
    overall = fence_rates(
        {k: pre2008_fence[k] + post2008_fence[k] for k in set(pre2008_fence) | set(post2008_fence)}
    )

    pre2008_n = sum(pre2008_fence.values())
    post2008_n = sum(post2008_fence.values())
    pre2010_n = pre2008_n + sum(by_era["2008_to_2009"].values())

    doc = {
        "what_this_is": (
            "Parcel year-built and attached-fence material on surviving "
            "single-family structures in CAL FIRE DINS. Same survival filter "
            "as fence_attachment_dins.json. Year 0, null, and years outside "
            f"{YEAR_MIN}-{YEAR_MAX} are treated as undetermined."
        ),
        "source": {
            "dataset": "CAL FIRE Damage Inspection (DINS) Data",
            "layer": SERVICE.rsplit("/query", 1)[0],
            "fields": ["YEARBUILT", FENCE],
            "retrieved": os.environ.get("DINS_RETRIEVED", str(date.today())),
        },
        "sample": {
            "filter": "DAMAGE = 'No Damage' AND STRUCTURETYPE LIKE 'Single Family Residence%'",
            "structures": valid_n + undetermined_year,
            "year_determined": valid_n,
            "year_undetermined": undetermined_year,
            "pct_year_determined": (
                round(100 * valid_n / (valid_n + undetermined_year), 2)
                if valid_n + undetermined_year else None
            ),
        },
        "cuts": {
            "pre_2008": {
                "structures": pre2008_n,
                "pct_of_year_determined": (
                    round(100 * pre2008_n / valid_n, 2) if valid_n else None
                ),
                "fence": pre,
            },
            "2008_or_later": {
                "structures": post2008_n,
                "pct_of_year_determined": (
                    round(100 * post2008_n / valid_n, 2) if valid_n else None
                ),
                "fence": post,
            },
            "pre_2010": {
                "structures": pre2010_n,
                "pct_of_year_determined": (
                    round(100 * pre2010_n / valid_n, 2) if valid_n else None
                ),
            },
        },
        "by_era": by_era_out,
        "overall_year_determined": overall,
        "what_this_is_not": (
            "Not a census of California housing. DINS is a wildfire-exposed "
            "sample. YEARBUILT is a parcel field, not an inspector "
            "observation of the fence. A post-2008 house with a combustible "
            "fence is legal under Chapter 7A; this table does not say otherwise."
        ),
    }
    with open(os.path.join(OUT, "year_built_dins.json"), "w") as f:
        json.dump(doc, f, indent=2)
        f.write("\n")
    return doc


def main():
    assignments = json.load(open(f"{WORK}/data/population_by_fhsz_blockgroups.json"))
    census, counties = load_census_housing()
    shares = load_year_shares()
    acs = build_acs(assignments, census, counties, shares)

    vh = acs["aggregates"]["very_high"]
    print(f"\nACS Very High: {vh['housing_units']:,} units")
    print(f"  pre-2000            {vh['pre_2000']:>10,}   {vh['pct_pre_2000']}%")
    print(f"  2000-2009           {vh['built_2000_to_2009']:>10,}   {vh['pct_2000_to_2009']}%")
    print(f"  pre-2010            {vh['pre_2010']:>10,}   {vh['pct_pre_2010']}%")
    print(f"  2010 or later       {vh['built_2010_or_later']:>10,}   {vh['pct_2010_or_later']}%")
    pos = acs["aggregates"]["point_of_sale_trigger"]
    print(f"\nACS point-of-sale trigger (SRA H/VH + LRA VH): {pos['housing_units']:,}")
    print(f"  pre-2010            {pos['pre_2010']:>10,}   {pos['pct_pre_2010']}%")

    print("\nquerying DINS YEARBUILT x fence …", file=sys.stderr)
    dins = build_dins()
    s = dins["sample"]
    pre = dins["cuts"]["pre_2008"]
    post = dins["cuts"]["2008_or_later"]
    print(f"\nDINS surviving SFR: {s['structures']:,}  year determined {s['year_determined']:,} "
          f"({s['pct_year_determined']}%)")
    print(f"  pre-2008            {pre['structures']:>10,}   {pre['pct_of_year_determined']}%")
    if pre["fence"]:
        print(f"    combustible attached {pre['fence']['pct_combustible_fence_attached']}%")
    print(f"  2008 or later       {post['structures']:>10,}   {post['pct_of_year_determined']}%")
    if post["fence"]:
        print(f"    combustible attached {post['fence']['pct_combustible_fence_attached']}%")


if __name__ == "__main__":
    main()
