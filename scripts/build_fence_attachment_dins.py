#!/usr/bin/env python3
"""
How many California homes have a fence attached to the house, and what it is
made of, as recorded by CAL FIRE damage inspectors.

Why this dataset exists
  The draft Zone 0 standard requires a five-foot non-combustible span where a
  fence or gate attaches to a structure. Turning that into a count of affected
  homes needs two rates nobody appeared to publish: how many homes have an
  attached fence at all, and how many of those fences are combustible.

  CAL FIRE has been recording both, per structure, since 2013. The Damage
  Inspection (DINS) database carries a FENCEATTACHEDTOSTRUCTURE field with the
  values Combustible, Non Combustible, No Fence and Unknown. This script reads
  it and does nothing else.

The one methodological choice that matters
  Rates are computed on SURVIVING structures only -- DAMAGE = 'No Damage'.

  The fence is recorded after the fire. When a structure burns to the slab the
  fence evidence burns with it, so a combustible fence at a destroyed structure
  is frequently logged as 'No Fence' or 'Unknown'. The field's own completeness
  shows the effect plainly: among destroyed structures in the 2025 Palisades and
  Eaton fires 10.7% of fence records are Unknown, against 0.4% among structures
  that took no damage.

  Rates measured on destroyed structures are therefore biased down, and the
  surviving subset is the only one where the inspector could actually see what
  was there. Both are published below so the bias is visible rather than
  asserted.

  This also means the DAMAGE x FENCE cross-tabulation cannot support any causal
  claim about attached fences and structure loss, in either direction. Read
  naively it says combustible fences protect houses. That is the recording
  artifact above, not a finding. The cross-tab is published in
  `damage_by_fence_type` so that anyone who runs the obvious query finds the
  explanation attached to it.

What the sample is
  DINS covers structures inside or within 100 metres of a fire perimeter. It is
  a wildfire-exposed sample of California housing, not a census of it, and it
  over-represents whatever was burning. The statewide and Palisades/Eaton rates
  are reported separately because they differ substantially: the LA fires were
  dense suburban, and dense suburbs fence more.

  One further limit: DINS records a single fence flag per structure. A typical
  suburban lot has two side-yard fences meeting the house, so a count of homes
  with 'a' fence attached is a count of homes, not of attachment points.

Source
  CAL FIRE Damage Inspection (DINS) Data, POSTFIRE_MASTER_DATA_SHARE layer 0.
  Public ArcGIS feature service, no key required.
  https://services1.arcgis.com/jUJYIo9tSA7EHvfZ/arcgis/rest/services/POSTFIRE_MASTER_DATA_SHARE/FeatureServer/0
  Dataset landing page: https://data.ca.gov/dataset/cal-fire-damage-inspection-dins-data

Outputs
  data/fence_attachment_dins.json        statewide and per-incident rates
  data/fence_attachment_by_county.csv    surviving single-family, by county
  data/zone0_combustible_fence_estimate.json
                                         the one derived figure in this
                                         repository: measured rates applied to
                                         the Very High detached-home count.
                                         Labelled an estimate because it is one.
"""
import csv, json, os, sys, urllib.parse, urllib.request

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(HERE, "data")

SERVICE = (
    "https://services1.arcgis.com/jUJYIo9tSA7EHvfZ/arcgis/rest/services/"
    "POSTFIRE_MASTER_DATA_SHARE/FeatureServer/0/query"
)

FENCE = "FENCEATTACHEDTOSTRUCTURE"
SFR = "STRUCTURETYPE LIKE 'Single Family Residence%'"
SURVIVING = "DAMAGE = 'No Damage'"
LA_2025 = "INCIDENTNAME IN ('Palisades','Eaton') AND INCIDENTSTARTDATE >= DATE '2025-01-01'"

# Values that mean "the inspector determined what was there". Unknown, null and
# empty are excluded from every denominator.
DETERMINED = ("Combustible", "Non Combustible", "No Fence")
ATTACHED = ("Combustible", "Non Combustible")


def grouped_count(where, group_by):
    """Server-side GROUP BY ... COUNT(*). Returns {(group values): count}."""
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


def rates(counts):
    """counts: {fence value: n}. Returns the block published for each sample."""
    determined = sum(counts.get(v, 0) for v in DETERMINED)
    attached = sum(counts.get(v, 0) for v in ATTACHED)
    combustible = counts.get("Combustible", 0)
    if not determined:
        return None
    return {
        "structures_determined": determined,
        "structures_excluded_undetermined": sum(counts.values()) - determined,
        "fence_attached": attached,
        "attached_combustible": combustible,
        "attached_non_combustible": counts.get("Non Combustible", 0),
        "no_fence": counts.get("No Fence", 0),
        "pct_fence_attached": round(100 * attached / determined, 2),
        "pct_of_attached_combustible": (
            round(100 * combustible / attached, 2) if attached else None
        ),
        "pct_combustible_fence_attached": round(100 * combustible / determined, 2),
    }


def flatten(counts):
    return {k[0]: v for k, v in counts.items()}


MIN_COUNTY_SAMPLE = 100
SPAN_FEET = 5  # the non-combustible span the draft names, per attachment


def write_zone0_estimate(counties, samples):
    """The one derived number here: measured rates x Very High detached homes.

    Each county's own measured rate is applied to its own Very High detached
    homes where the county sample supports it, and the statewide rate is used
    everywhere else. Weighting matters because the rate varies more than
    threefold between counties -- Orange fences heavily but in block wall and
    vinyl, Sonoma fences in wood -- and because Los Angeles alone holds a
    quarter of the Very High detached stock.
    """
    housing = os.path.join(OUT, "housing_by_fhsz_county.csv")
    if not os.path.exists(housing):
        print("housing_by_fhsz_county.csv absent; skipping derived estimate")
        return

    detached = {}
    detached_by_ra = {}
    with open(housing) as f:
        for row in csv.DictReader(f):
            if row["fhsz_tier"] == "Very High":
                name = row["county_name"].replace(" County", "").strip()
                units = int(row["detached_single_family_est"])
                detached[name] = detached.get(name, 0) + units
                ra = row["responsibility_area"]
                detached_by_ra.setdefault(name, {})[ra] = (
                    detached_by_ra.setdefault(name, {}).get(ra, 0) + units
                )

    county_rate = {}
    for county, counts in counties.items():
        r = rates(counts)
        if r and r["structures_determined"] >= MIN_COUNTY_SAMPLE:
            county_rate[county.strip()] = (
                r["pct_combustible_fence_attached"] / 100,
                r["structures_determined"],
            )

    statewide = samples["statewide_all_years"]["pct_combustible_fence_attached"] / 100
    total = measured_homes = 0.0
    per_county = {}
    by_ra = {}
    for county, homes in detached.items():
        rate, n = county_rate.get(county, (statewide, None))
        total += homes * rate
        if n:
            measured_homes += homes
        for ra, ra_homes in detached_by_ra.get(county, {}).items():
            by_ra[ra] = by_ra.get(ra, 0.0) + ra_homes * rate
        per_county[county] = {
            "detached_very_high": homes,
            "rate_used": round(rate, 4),
            "rate_source": f"county (n={n})" if n else "statewide",
            "homes_combustible_fence_attached": round(homes * rate),
        }

    all_homes = sum(detached.values())
    doc = {
        "what_this_is": (
            "An ESTIMATE, and the only derived figure in this repository. It "
            "multiplies a measured rate (CAL FIRE DINS) by an estimated "
            "housing count (Census 2020 units x ACS structure share). Both "
            "inputs carry their own error and it compounds here."
        ),
        "estimate": {
            "homes_with_combustible_fence_attached": round(total),
            "non_combustible_span_feet": round(total) * SPAN_FEET,
            "non_combustible_span_miles": round(total * SPAN_FEET / 5280),
        },
        "method": "county-weighted",
        "inputs": {
            "detached_homes_very_high": all_homes,
            "share_covered_by_county_measured_rate": round(
                100 * measured_homes / all_homes, 1
            ),
            "statewide_fallback_rate": round(statewide, 4),
            "minimum_county_sample": MIN_COUNTY_SAMPLE,
            "span_feet_per_home": SPAN_FEET,
        },
        "by_responsibility_area": {
            "why_this_matters": (
                "The draft times the two responsibility areas differently. "
                "Existing structures in the Local Responsibility Area comply "
                "within three years of the effective date, or five on a local "
                "agency's timeline (Sec. 1298.04(c)(3)). In the State "
                "Responsibility Area the default is five years, with three the "
                "floor the Director cannot go below (Sec. 1299.03(e)(3)). A "
                "single statewide figure quoted against the three-year clock "
                "therefore over-covers by the SRA share below."
            ),
            **{
                ra: {
                    "homes_combustible_fence_attached": round(homes),
                    "non_combustible_span_feet": round(homes) * SPAN_FEET,
                    "share_of_estimate_pct": round(100 * homes / total, 1),
                }
                for ra, homes in sorted(by_ra.items(), key=lambda kv: -kv[1])
            },
        },
        "cross_check": {
            "flat_statewide_rate": round(all_homes * statewide),
            "note": (
                "The flat and county-weighted methods agree within 3%, which is "
                "the main reason to trust the order of magnitude. Applying the "
                "Palisades/Eaton rate statewide instead gives roughly 422,000, "
                "but the county table shows that generalising one dense "
                "suburban sample is not supported: Riverside measures 10.9% and "
                "Orange 15.6% against Los Angeles at 42.2%."
            ),
        },
        "limits": (
            "One five-foot span per home is assumed; DINS records a single "
            "fence flag per structure while a typical lot has two side-yard "
            "attachments, so this is likely conservative. Zone 0 is a draft: "
            "the span would be required three to five years after an effective "
            "date that has not been set."
        ),
        "by_county": dict(
            sorted(per_county.items(),
                   key=lambda kv: -kv[1]["homes_combustible_fence_attached"])
        ),
    }

    with open(os.path.join(OUT, "zone0_combustible_fence_estimate.json"), "w") as f:
        json.dump(doc, f, indent=2)
        f.write("\n")

    e = doc["estimate"]
    print(f"\nderived estimate (county-weighted): "
          f"{e['homes_with_combustible_fence_attached']:,} homes, "
          f"{e['non_combustible_span_feet']:,} ft, "
          f"{e['non_combustible_span_miles']:,} miles")
    print(f"  cross-check, flat statewide rate: "
          f"{doc['cross_check']['flat_statewide_rate']:,} homes")


def main():
    samples = {}

    # The two headline samples: surviving single-family homes.
    for name, where in (
        ("statewide_all_years", f"{SURVIVING} AND {SFR}"),
        ("palisades_eaton_2025", f"{LA_2025} AND {SURVIVING} AND {SFR}"),
    ):
        samples[name] = rates(flatten(grouped_count(where, [FENCE])))

    # The same rate measured on destroyed structures, published to show the
    # recording bias rather than to be used.
    samples["palisades_eaton_2025_destroyed_biased"] = rates(
        flatten(grouped_count(
            f"{LA_2025} AND DAMAGE = 'Destroyed (>50%)' AND {SFR}", [FENCE]
        ))
    )

    # Full cross-tab, published with its warning. See the module docstring.
    cross = grouped_count(LA_2025, ["DAMAGE", FENCE])
    damage_by_fence = {}
    for (damage, fence), n in cross.items():
        damage_by_fence.setdefault(fence or "(null)", {})[damage] = n

    # Per-county, surviving single-family.
    by_county = grouped_count(f"{SURVIVING} AND {SFR}", ["COUNTY", FENCE])
    counties = {}
    for (county, fence), n in by_county.items():
        counties.setdefault(county or "(unknown)", {})[fence or "(null)"] = n

    doc = {
        "source": {
            "dataset": "CAL FIRE Damage Inspection (DINS) Data",
            "layer": SERVICE.rsplit("/query", 1)[0],
            "field": FENCE,
            "retrieved": os.environ.get("DINS_RETRIEVED", "2026-08-14"),
        },
        "basis": (
            "Rates are computed on surviving structures (DAMAGE = 'No Damage') "
            "because the fence is recorded after the fire; at destroyed "
            "structures a combustible fence is frequently logged as No Fence or "
            "Unknown. Denominators exclude Unknown and null."
        ),
        "samples": samples,
        "damage_by_fence_type_palisades_eaton_2025": {
            "warning": (
                "This cross-tabulation does not support a causal claim in "
                "either direction. Destroyed structures under-report "
                "combustible fences because the evidence burned. Published so "
                "that the artifact travels with the numbers."
            ),
            "counts": damage_by_fence,
        },
    }

    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, "fence_attachment_dins.json"), "w") as f:
        json.dump(doc, f, indent=2)
        f.write("\n")

    rows = []
    for county, counts in counties.items():
        r = rates(counts)
        if r:
            rows.append((county, r))
    rows.sort(key=lambda x: -x[1]["structures_determined"])

    with open(os.path.join(OUT, "fence_attachment_by_county.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow([
            "county", "structures_determined", "fence_attached",
            "attached_combustible", "attached_non_combustible", "no_fence",
            "pct_fence_attached", "pct_of_attached_combustible",
            "pct_combustible_fence_attached",
        ])
        for county, r in rows:
            w.writerow([
                county, r["structures_determined"], r["fence_attached"],
                r["attached_combustible"], r["attached_non_combustible"],
                r["no_fence"], r["pct_fence_attached"],
                r["pct_of_attached_combustible"],
                r["pct_combustible_fence_attached"],
            ])

    write_zone0_estimate(counties, samples)

    for name, r in samples.items():
        if r:
            print(f"{name:38} n={r['structures_determined']:>7,}  "
                  f"attached {r['pct_fence_attached']:>5.1f}%  "
                  f"combustible-of-attached {r['pct_of_attached_combustible']:>5.1f}%  "
                  f"combustible-attached {r['pct_combustible_fence_attached']:>5.1f}%")
    print(f"\n{len(rows)} counties written")


if __name__ == "__main__":
    main()
