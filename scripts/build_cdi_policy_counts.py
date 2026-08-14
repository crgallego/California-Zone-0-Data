#!/usr/bin/env python3
"""
California Department of Insurance residential policy counts by county.

Why this dataset exists
  The FAIR Plan stock tells you who is already in the residual market. CDI
  publishes the flow that puts them there: new, renewed, and non-renewed
  homeowners policies in the voluntary market, plus new and renewed FAIR Plan
  and Difference-in-Conditions policies, for every county.

  This is not a count of homes dropped because of wildfire. CDI's own fact
  sheet says 75-80% of non-renewals are initiated by the policyholder
  (moves, company switches). The company-initiated share is the remaining
  20-25%, and the published tables do not split the two.

Source
  California Department of Insurance, Data and Analysis on Wildfires and
  Insurance.
  https://www.insurance.ca.gov/01-consumers/200-wrr/DataAnalysisOnWildfiresAndInsurance.cfm
  County table (report year 2024, calendar years 2020-2023):
    Residential-Insurance-Policy-Analysis-by-County-2020-to-2023-2.pdf
  Statewide 2015-2023 series and the 75-80% caveat:
    CDI-Fact-Sheet-Summary-on-Residential-Insurance-Policies-and-the-FAIR-Plan-v-011325-2.pdf
    published 2025-01-13.

Requires: pypdf.

Outputs
  data/cdi_policy_counts_by_county.csv
  data/cdi_policy_counts_state.json
"""
import csv, json, os, re, sys, urllib.request

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(HERE, "data")

PAGE = (
    "https://www.insurance.ca.gov/01-consumers/200-wrr/"
    "DataAnalysisOnWildfiresAndInsurance.cfm"
)
COUNTY_PDF = (
    "https://www.insurance.ca.gov/01-consumers/200-wrr/upload/"
    "Residential-Insurance-Policy-Analysis-by-County-2020-to-2023-2.pdf"
)
FACT_SHEET = (
    "https://www.insurance.ca.gov/01-consumers/200-wrr/upload/"
    "CDI-Fact-Sheet-Summary-on-Residential-Insurance-Policies-and-the-FAIR-Plan-v-011325-2.pdf"
)

RETRIEVED = "2026-08-14"
YEARS = [2023, 2022, 2021, 2020]
FIELDS = (
    "voluntary_new",
    "voluntary_renewed",
    "voluntary_nonrenewed",
    "fair_plan_new",
    "fair_plan_renewed",
    "dic_new",
    "dic_renewed",
)

CA = [
    "Alameda", "Alpine", "Amador", "Butte", "Calaveras", "Colusa",
    "Contra Costa", "Del Norte", "El Dorado", "Fresno", "Glenn", "Humboldt",
    "Imperial", "Inyo", "Kern", "Kings", "Lake", "Lassen", "Los Angeles",
    "Madera", "Marin", "Mariposa", "Mendocino", "Merced", "Modoc", "Mono",
    "Monterey", "Napa", "Nevada", "Orange", "Placer", "Plumas", "Riverside",
    "Sacramento", "San Benito", "San Bernardino", "San Diego", "San Francisco",
    "San Joaquin", "San Luis Obispo", "San Mateo", "Santa Barbara",
    "Santa Clara", "Santa Cruz", "Shasta", "Sierra", "Siskiyou", "Solano",
    "Sonoma", "Stanislaus", "Sutter", "Tehama", "Trinity", "Tulare",
    "Tuolumne", "Ventura", "Yolo", "Yuba",
]
UPPER = {c.upper(): c for c in CA}

# Published "State" line from the county PDF. County rows do not sum to this
# exactly — a small residual is not attributed to a named county. Use these
# figures for any statewide claim.
STATE_COUNTY_PDF = {
    2023: [724037, 7576693, 788485, 92447, 232507, 77386, 130342],
    2022: [933752, 7578931, 899690, 66120, 209011, 55986, 103376],
    2021: [1091089, 7514564, 1037767, 64866, 181941, 55369, 77187],
    2020: [1007422, 7572809, 898064, 73190, 148901, 52323, 51816],
}

# Fact sheet Appendix A, published 2025-01-13. 2020-2023 voluntary and FAIR
# Plan new/renewed/non-renewed match the county-PDF State line. Extra columns
# (FAIR Plan non-renewed/canceled, surplus lines) exist only here.
FACT_SHEET_APPENDIX_A = {
    2023: {
        "voluntary_new": 724037, "voluntary_renewed": 7576693,
        "voluntary_nonrenewed": 788485,
        "fair_plan_new": 92447, "fair_plan_renewed": 232507,
        "fair_plan_nonrenewed": 27198,
        "surplus_new": 25480, "surplus_renewed": 16034,
    },
    2022: {
        "voluntary_new": 933752, "voluntary_renewed": 7578931,
        "voluntary_nonrenewed": 899690,
        "fair_plan_new": 66120, "fair_plan_renewed": 209011,
        "fair_plan_nonrenewed": 34031,
        "surplus_new": 12257, "surplus_renewed": 12402,
    },
    2021: {
        "voluntary_new": 1091089, "voluntary_renewed": 7514564,
        "voluntary_nonrenewed": 1037767,
        "fair_plan_new": 64866, "fair_plan_renewed": 181941,
        "fair_plan_nonrenewed": 36132,
        "surplus_new": 14647, "surplus_renewed": 13770,
    },
    2020: {
        "voluntary_new": 1007422, "voluntary_renewed": 7572809,
        "voluntary_nonrenewed": 898064,
        "fair_plan_new": 73190, "fair_plan_renewed": 148901,
        "fair_plan_nonrenewed": 28262,
        "surplus_new": 13659, "surplus_renewed": 14119,
    },
    2019: {
        "voluntary_new": 1102130, "voluntary_renewed": 7540135,
        "voluntary_nonrenewed": 1022638,
        "fair_plan_new": 73557, "fair_plan_renewed": 116233,
        "fair_plan_nonrenewed": 25543,
        "surplus_new": 11912, "surplus_renewed": 9620,
    },
    2018: {
        "voluntary_new": 979638, "voluntary_renewed": 7546700,
        "voluntary_nonrenewed": 914187,
        "fair_plan_new": 23049, "fair_plan_renewed": 117398,
        "fair_plan_nonrenewed": 22154,
        "surplus_new": 8247, "surplus_renewed": 11547,
    },
    2017: {
        "voluntary_new": 978576, "voluntary_renewed": 7510275,
        "voluntary_nonrenewed": 918092,
        "fair_plan_new": 22017, "fair_plan_renewed": 118295,
        "fair_plan_nonrenewed": 21740,
        "surplus_new": 6660, "surplus_renewed": 11034,
    },
    2016: {
        "voluntary_new": 966610, "voluntary_renewed": 7476478,
        "voluntary_nonrenewed": 916751,
        "fair_plan_new": 22643, "fair_plan_renewed": 118549,
        "fair_plan_nonrenewed": 21979,
        "surplus_new": 7431, "surplus_renewed": 9213,
    },
    2015: {
        "voluntary_new": 944639, "voluntary_renewed": 7412985,
        "voluntary_nonrenewed": 899581,
        "fair_plan_new": 22740, "fair_plan_renewed": 118651,
        "fair_plan_nonrenewed": 20944,
        "surplus_new": 6503, "surplus_renewed": 7881,
    },
}

# Fact sheet footnotes. Used to label groups, not to invent county lists.
TOP10_HIGH_FIRE = [
    "Tuolumne", "Trinity", "Nevada", "Mariposa", "Plumas",
    "Alpine", "Calaveras", "Sierra", "Amador", "El Dorado",
]
DISTRESSED_P50 = [
    "Alpine", "Amador", "Butte", "Calaveras", "Del Norte", "El Dorado",
    "Humboldt", "Lake", "Lassen", "Madera", "Marin", "Mariposa",
    "Mendocino", "Modoc", "Mono", "Monterey", "Napa", "Nevada", "Placer",
    "Plumas", "San Luis Obispo", "Santa Cruz", "Shasta", "Sierra",
    "Siskiyou", "Tehama", "Trinity", "Tuolumne", "Ventura",
]


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "California-Zone-0-Data/1"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return r.read()


def pdf_text(raw):
    try:
        from pypdf import PdfReader
    except ImportError:
        sys.exit("pypdf is required: pip install pypdf")
    import io
    reader = PdfReader(io.BytesIO(raw))
    return "\n".join((p.extract_text() or "") for p in reader.pages)


def parse_county_pdf(text):
    rows = {}
    current = None
    for ln in text.splitlines():
        ln = ln.strip()
        m = re.match(r"^([A-Z][A-Z ]+[A-Z])\s+(202[0-3])\s+(.+)$", ln)
        if m and m.group(1) in UPPER:
            current = UPPER[m.group(1)]
            nums = [int(x.replace(",", "")) for x in re.findall(r"\d[\d,]*", m.group(3))]
            if len(nums) != 7:
                sys.exit(f"bad county line for {current}: {ln}")
            rows[(current, int(m.group(2)))] = nums
            continue
        m = re.match(r"^(202[0-3])\s+(.+)$", ln)
        if m and current:
            year = int(m.group(1))
            nums = [int(x.replace(",", "")) for x in re.findall(r"\d[\d,]*", m.group(2))]
            if len(nums) == 7 and (current, year) not in rows:
                rows[(current, year)] = nums
            continue
        if ln.startswith("State 2023"):
            current = None
    missing = [(c, y) for c in CA for y in YEARS if (c, y) not in rows]
    if missing:
        sys.exit(f"county parse incomplete: {missing[:8]}")
    return rows


def rate(numer, denom):
    if not denom:
        return None
    return round(100.0 * numer / denom, 2)


def pack(nums):
    return dict(zip(FIELDS, nums))


def add_rows(rows, counties, year):
    out = [0] * 7
    for c in counties:
        for i, n in enumerate(rows[(c, year)]):
            out[i] += n
    return out


def main():
    raw = fetch(COUNTY_PDF)
    rows = parse_county_pdf(pdf_text(raw))

    # Pin the published State line and the fact-sheet high-fire rollups.
    for year, expected in STATE_COUNTY_PDF.items():
        got = pack(expected)
        if got["voluntary_nonrenewed"] != expected[2]:
            sys.exit("internal state table corrupted")
    top10_2023 = add_rows(rows, TOP10_HIGH_FIRE, 2023)
    if top10_2023[:5] != [7791, 124537, 21599, 17038, 48351]:
        sys.exit(f"top-10 2023 mismatch: {top10_2023}")
    p50_2023 = add_rows(rows, DISTRESSED_P50, 2023)
    if p50_2023[:5] != [78509, 988119, 110845, 37431, 82844]:
        sys.exit(f"p50 2023 mismatch: {p50_2023}")

    estimate_path = os.path.join(OUT, "zone0_combustible_fence_estimate.json")
    estimate = json.load(open(estimate_path)) if os.path.exists(estimate_path) else {}
    by_county_est = estimate.get("by_county", {})

    fair_path = os.path.join(OUT, "fair_plan_by_county.csv")
    fair_pif = {}
    if os.path.exists(fair_path):
        with open(fair_path) as f:
            for rec in csv.DictReader(f):
                fair_pif[rec["county"]] = int(rec["pif_2025"])

    csv_path = os.path.join(OUT, "cdi_policy_counts_by_county.csv")
    csv_fields = (
        ["county", "year"]
        + list(FIELDS)
        + [
            "voluntary_nonrenewal_rate_cdi_pct",
            "fair_plan_new_plus_renewed",
            "fair_plan_share_of_new_plus_renewed_pct",
            "detached_very_high_est",
            "homes_combustible_fence_attached_est",
            "fair_plan_pif_all_lines_2025",
        ]
    )
    with open(csv_path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=csv_fields)
        w.writeheader()
        for county in CA:
            fence = by_county_est.get(county, {})
            for year in YEARS:
                nums = rows[(county, year)]
                rec = pack(nums)
                vol = rec["voluntary_new"] + rec["voluntary_renewed"]
                fp = rec["fair_plan_new"] + rec["fair_plan_renewed"]
                w.writerow({
                    "county": county,
                    "year": year,
                    **rec,
                    "voluntary_nonrenewal_rate_cdi_pct": rate(
                        rec["voluntary_nonrenewed"], vol
                    ),
                    "fair_plan_new_plus_renewed": fp,
                    "fair_plan_share_of_new_plus_renewed_pct": rate(fp, vol + fp),
                    "detached_very_high_est": fence.get("detached_very_high", ""),
                    "homes_combustible_fence_attached_est": fence.get(
                        "homes_combustible_fence_attached", ""
                    ),
                    "fair_plan_pif_all_lines_2025": fair_pif.get(county, ""),
                })

    residual = {}
    for year, published in STATE_COUNTY_PDF.items():
        summed = add_rows(rows, CA, year)
        residual[str(year)] = {
            field: published[i] - summed[i] for i, field in enumerate(FIELDS)
        }

    def group_block(counties, year=2023):
        nums = add_rows(rows, counties, year)
        rec = pack(nums)
        vol = rec["voluntary_new"] + rec["voluntary_renewed"]
        fp = rec["fair_plan_new"] + rec["fair_plan_renewed"]
        return {
            "counties": counties,
            "year": year,
            **rec,
            "voluntary_nonrenewal_rate_cdi_pct": rate(rec["voluntary_nonrenewed"], vol),
            "fair_plan_new_plus_renewed": fp,
            "fair_plan_share_of_new_plus_renewed_pct": rate(fp, vol + fp),
        }

    def statewide_year(year):
        rec = pack(STATE_COUNTY_PDF[year])
        vol = rec["voluntary_new"] + rec["voluntary_renewed"]
        fp = rec["fair_plan_new"] + rec["fair_plan_renewed"]
        return {
            **rec,
            "voluntary_nonrenewal_rate_cdi_pct": rate(rec["voluntary_nonrenewed"], vol),
            "fair_plan_new_plus_renewed": fp,
            "fair_plan_share_of_new_plus_renewed_pct": rate(fp, vol + fp),
        }

    highlights_2023 = []
    for county in CA:
        rec = pack(rows[(county, 2023)])
        vol = rec["voluntary_new"] + rec["voluntary_renewed"]
        fp = rec["fair_plan_new"] + rec["fair_plan_renewed"]
        highlights_2023.append({
            "county": county,
            **rec,
            "voluntary_nonrenewal_rate_cdi_pct": rate(rec["voluntary_nonrenewed"], vol),
            "fair_plan_new_plus_renewed": fp,
            "fair_plan_share_of_new_plus_renewed_pct": rate(fp, vol + fp),
            "detached_very_high_est": by_county_est.get(county, {}).get(
                "detached_very_high"
            ),
            "fair_plan_pif_all_lines_2025": fair_pif.get(county),
        })

    state = {
        "source": {
            "publisher": "California Department of Insurance",
            "page": PAGE,
            "county_pdf": COUNTY_PDF,
            "fact_sheet_pdf": FACT_SHEET,
            "county_table_report_year": 2024,
            "county_table_calendar_years": YEARS,
            "fact_sheet_published": "2025-01-13",
            "retrieved": RETRIEVED,
        },
        "what_this_is": (
            "Annual counts of new, renewed, and non-renewed residential "
            "policies in the voluntary market, plus new and renewed FAIR Plan "
            "and Difference-in-Conditions policies, by county. Coverage is "
            "homeowners, dwelling-fire (not contents-only), landlord/BOP of "
            "four units or fewer, and mobile homes — about 98-99% of the "
            "homeowners market. HO-4 and HO-6 are excluded."
        ),
        "what_this_is_not": (
            "A non-renewal is not a company drop. CDI's January 13, 2025 fact "
            "sheet states that past research shows 75-80% of non-renewals are "
            "initiated by the policyholder (buying or selling a home, or "
            "changing company). The remaining 20-25% are company-initiated, "
            "for reasons that include wildfire risk, claims history, and "
            "carriers exiting the market. The published tables do not split "
            "those two. Do not write that N homeowners were dropped. The "
            "CDI non-renewal rate here is their published ratio: non-renewed "
            "divided by (new + renewed). A FAIR Plan new-or-renewed count is "
            "a flow in that calendar year, not the same thing as the FAIR Plan "
            "Association's policies-in-force stock."
        ),
        "statewide_from_county_pdf": {
            str(year): statewide_year(year) for year in YEARS
        },
        "statewide_from_fact_sheet_appendix_a": {
            str(year): rec for year, rec in FACT_SHEET_APPENDIX_A.items()
        },
        "county_sum_residual_vs_published_state_line": {
            "note": (
                "The 58 named counties do not sum to the published State line. "
                "The residual is in the source, not a parse error: the same "
                "county rows reproduce CDI's own top-10 and 50th-percentile "
                "appendices exactly. Use the published State line for "
                "statewide claims."
            ),
            "by_year": residual,
        },
        "groups_defined_by_cdi_fact_sheet": {
            "top10_highest_share_of_structures_at_high_fire_risk": group_block(
                TOP10_HIGH_FIRE
            ),
            "counties_at_or_above_50th_percentile_high_fire_risk": group_block(
                DISTRESSED_P50
            ),
        },
        "top_counties_2023_by_voluntary_nonrenewal_rate": sorted(
            highlights_2023,
            key=lambda r: r["voluntary_nonrenewal_rate_cdi_pct"],
            reverse=True,
        )[:10],
        "top_counties_2023_by_fair_plan_share": sorted(
            highlights_2023,
            key=lambda r: r["fair_plan_share_of_new_plus_renewed_pct"],
            reverse=True,
        )[:10],
    }

    json_path = os.path.join(OUT, "cdi_policy_counts_state.json")
    with open(json_path, "w") as f:
        json.dump(state, f, indent=2)
        f.write("\n")

    s2023 = statewide_year(2023)
    print(f"wrote {csv_path} ({len(CA) * len(YEARS)} rows)")
    print(f"wrote {json_path}")
    print(
        f"2023 voluntary non-renewals: {s2023['voluntary_nonrenewed']:,} "
        f"({s2023['voluntary_nonrenewal_rate_cdi_pct']}% of new+renewed)"
    )
    print(
        f"2023 FAIR Plan new+renewed: {s2023['fair_plan_new_plus_renewed']:,} "
        f"({s2023['fair_plan_share_of_new_plus_renewed_pct']}% of vol+FAIR flow)"
    )


if __name__ == "__main__":
    main()
