#!/usr/bin/env python3
"""
California FAIR Plan policies in force and insured exposure, by county.

Why this dataset exists
  Zone 0 is a draft building rule. The insurance market is already moving.
  The California FAIR Plan is the residual fire insurer of last resort, and it
  publishes policies-in-force and total insured value by county every fiscal
  year. Those are counts a reporter can check, and they are the pressure behind
  a lot of the fence conversation.

  This script does not claim that a FAIR Plan policy is a combustible fence,
  or that a FAIR Plan home sits in a Very High Fire Hazard Severity Zone.
  FAIR Plan is a county-wide residual market. Wildfire is why it has grown;
  it is not the only reason a policy is written.

Source
  California FAIR Plan Association, Key Statistics & Data.
  https://www.cfpnet.com/key-statistics-data/
  County PDFs as of fiscal year-end 2025 (2025-09-30), posted 2025-11-14:
    CFP-5-yr-PIF-County-FY25-All-251114.pdf
    CFP-5-yr-TIV-County-FY25-All-251114.pdf
  Those county files mix residential, commercial, and BOP.
  Residential-only statewide totals come from the first "Total" line of:
    CFP-5-yr-PIF-Zip-FY25-DWE-251114.pdf
    CFP-5-yr-TIV-Zip-FY25-DWE-251114.pdf

  The Association's webpage also posts a later statewide snapshot (June 2026)
  that is not broken out by county. That snapshot is recorded separately and
  is not used to overwrite the county table.

Requires: pypdf (and cryptography, for these encrypted PDFs).

Outputs
  data/fair_plan_by_county.csv
  data/fair_plan_state.json
"""
import csv, json, os, re, sys, urllib.request

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(HERE, "data")

BASE = "https://www.cfpnet.com/wp-content/uploads/2025/11/"
PIF_COUNTY = BASE + "CFP-5-yr-PIF-County-FY25-All-251114.pdf"
TIV_COUNTY = BASE + "CFP-5-yr-TIV-County-FY25-All-251114.pdf"
PIF_DWE = BASE + "CFP-5-yr-PIF-Zip-FY25-DWE-251114.pdf"
TIV_DWE = BASE + "CFP-5-yr-TIV-Zip-FY25-DWE-251114.pdf"
STATS_PAGE = "https://www.cfpnet.com/key-statistics-data/"

AS_OF = "2025-09-30"
RETRIEVED = "2026-08-14"
YEARS = [2025, 2024, 2023, 2022, 2021]

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


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "California-Zone-0-Data/1"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return r.read()


def pdf_text(raw):
    try:
        from pypdf import PdfReader
    except ImportError:
        sys.exit("pypdf is required: pip install pypdf cryptography")
    import io
    reader = PdfReader(io.BytesIO(raw))
    if reader.is_encrypted:
        reader.decrypt("")
    return "\n".join((p.extract_text() or "") for p in reader.pages)


def parse_pif(text):
    rows = {}
    for line in text.splitlines():
        line = line.strip()
        name = next((c for c in sorted(CA, key=len, reverse=True)
                     if line.startswith(c + " ")), None)
        if not name:
            continue
        rest = line[len(name):]
        counts = [int(n.replace(",", ""))
                  for _, n in re.findall(r"(-?\d+)%\s+(-?[\d,]+)", rest)
                  if n not in ("", "-")]
        if len(counts) == 4:
            tail = re.search(r"(\d[\d,]*)\s*$", rest)
            if tail:
                counts.append(int(tail.group(1).replace(",", "")))
        if len(counts) >= 5:
            rows[name] = counts[:5]
    return rows


def parse_tiv(text):
    rows = {}
    for line in text.splitlines():
        line = line.strip()
        name = next((c for c in sorted(CA, key=len, reverse=True)
                     if line.startswith(c + " ")), None)
        if not name:
            continue
        rest = line[len(name):]
        amts = [int(x.replace(",", "")) for x in re.findall(r"([\d,]+)\$", rest)]
        if len(amts) >= 5:
            rows[name] = amts[:5]
    return rows


def first_total_line(text):
    for line in text.splitlines():
        if line.startswith("Total"):
            return line
    return ""


def parse_dwe_pif_total(text):
    m = re.search(
        r"Total\s+(\d+)%\s+([\d,]+)\s+(\d+)%\s+([\d,]+)\s+(\d+)%\s+([\d,]+)"
        r"\s+(\d+)%\s+([\d,]+)\s+([\d,]+)",
        first_total_line(text),
    )
    if not m:
        sys.exit("could not parse residential PIF total")
    g = m.groups()
    return {
        "yoy_growth_pct": int(g[0]),
        "by_year": {
            "2025": int(g[1].replace(",", "")),
            "2024": int(g[3].replace(",", "")),
            "2023": int(g[5].replace(",", "")),
            "2022": int(g[7].replace(",", "")),
            "2021": int(g[8].replace(",", "")),
        },
    }


def parse_dwe_tiv_total(text):
    m = re.search(
        r"Total\s+(\d+)%\s+([\d,]+)\s+(\d+)%\s+([\d,]+)\s+(\d+)%\s+([\d,]+)"
        r"\s+(\d+)%\s+([\d,]+)\s+([\d,]+)",
        first_total_line(text),
    )
    if not m:
        sys.exit("could not parse residential exposure total")
    g = m.groups()
    return {
        "yoy_growth_pct": int(g[0]),
        "by_year": {
            "2025": int(g[1].replace(",", "")),
            "2024": int(g[3].replace(",", "")),
            "2023": int(g[5].replace(",", "")),
            "2022": int(g[7].replace(",", "")),
            "2021": int(g[8].replace(",", "")),
        },
    }


def main():
    pif = parse_pif(pdf_text(fetch(PIF_COUNTY)))
    tiv = parse_tiv(pdf_text(fetch(TIV_COUNTY)))
    if set(pif) != set(CA) or set(tiv) != set(CA):
        sys.exit(f"county parse incomplete: pif={len(pif)} tiv={len(tiv)}")
    pif_sum = sum(v[0] for v in pif.values())
    tiv_sum = sum(v[0] for v in tiv.values())
    if pif_sum != 642010 or tiv_sum != 693964308706:
        sys.exit(f"county totals do not match published: pif={pif_sum} tiv={tiv_sum}")

    dwe_pif = parse_dwe_pif_total(pdf_text(fetch(PIF_DWE)))
    dwe_tiv = parse_dwe_tiv_total(pdf_text(fetch(TIV_DWE)))
    if dwe_pif["by_year"]["2025"] != 621234:
        sys.exit(f"residential PIF mismatch: {dwe_pif}")
    if dwe_tiv["by_year"]["2025"] != 645115692650:
        sys.exit(f"residential TIV mismatch: {dwe_tiv}")

    estimate_path = os.path.join(OUT, "zone0_combustible_fence_estimate.json")
    estimate = json.load(open(estimate_path)) if os.path.exists(estimate_path) else {}
    by_county = estimate.get("by_county", {})

    csv_path = os.path.join(OUT, "fair_plan_by_county.csv")
    fields = (
        ["county"]
        + [f"pif_{y}" for y in YEARS]
        + [f"exposure_{y}" for y in YEARS]
        + [
            "detached_very_high_est",
            "homes_combustible_fence_attached_est",
            "note",
        ]
    )
    with open(csv_path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for county in CA:
            fence = by_county.get(county, {})
            w.writerow({
                "county": county,
                **{f"pif_{y}": pif[county][i] for i, y in enumerate(YEARS)},
                **{f"exposure_{y}": tiv[county][i] for i, y in enumerate(YEARS)},
                "detached_very_high_est": fence.get("detached_very_high", ""),
                "homes_combustible_fence_attached_est": fence.get(
                    "homes_combustible_fence_attached", ""
                ),
                "note": (
                    "PIF and exposure are county-wide FAIR Plan residual-market "
                    "totals (residential + commercial + BOP), not FHSZ-restricted. "
                    "The last two columns are from zone0_combustible_fence_estimate.json "
                    "and are context only."
                ),
            })

    state = {
        "source": {
            "publisher": "California FAIR Plan Association",
            "page": STATS_PAGE,
            "county_pif_pdf": PIF_COUNTY,
            "county_exposure_pdf": TIV_COUNTY,
            "residential_pif_pdf": PIF_DWE,
            "residential_exposure_pdf": TIV_DWE,
            "county_table_as_of": AS_OF,
            "retrieved": RETRIEVED,
        },
        "what_this_is": (
            "FAIR Plan is California's residual fire insurer of last resort. "
            "County files mix residential, commercial, and business-owners policies. "
            "Residential-only statewide totals are taken from the dwelling ZIP rollups. "
            "None of these figures is a count of homes in Very High Fire Hazard "
            "Severity Zones, and none is a count of combustible fences."
        ),
        "county_table_all_lines": {
            "as_of": AS_OF,
            "policies_in_force": pif_sum,
            "total_insured_exposure_usd": tiv_sum,
            "pif_by_year": {
                str(y): sum(pif[c][i] for c in CA) for i, y in enumerate(YEARS)
            },
            "exposure_by_year_usd": {
                str(y): sum(tiv[c][i] for c in CA) for i, y in enumerate(YEARS)
            },
            "yoy_pif_growth_pct_2025": 39,
            "yoy_exposure_growth_pct_2025": 52,
        },
        "statewide_residential": {
            "as_of": AS_OF,
            "policies_in_force": dwe_pif["by_year"]["2025"],
            "total_insured_exposure_usd": dwe_tiv["by_year"]["2025"],
            "pif_by_year": dwe_pif["by_year"],
            "exposure_by_year_usd": dwe_tiv["by_year"],
            "yoy_pif_growth_pct_2025": dwe_pif["yoy_growth_pct"],
            "yoy_exposure_growth_pct_2025": dwe_tiv["yoy_growth_pct"],
        },
        "later_statewide_snapshot_not_in_county_table": {
            "as_of": "2026-06",
            "source": STATS_PAGE,
            "retrieved": RETRIEVED,
            "total_pif_all_lines": 696562,
            "total_exposure_usd": 768_000_000_000,
            "written_premium_usd": 2_040_000_000,
            "note": (
                "Read from the Association webpage narrative on 2026-08-14. "
                "No county breakout at this vintage. Do not mix with the "
                "2025-09-30 county table."
            ),
        },
        "top_counties_by_pif_2025": [
            {"county": c, "pif": pif[c][0], "exposure_usd": tiv[c][0]}
            for c in sorted(CA, key=lambda x: pif[x][0], reverse=True)[:10]
        ],
    }
    json_path = os.path.join(OUT, "fair_plan_state.json")
    with open(json_path, "w") as f:
        json.dump(state, f, indent=2)
        f.write("\n")
    print(f"wrote {csv_path} ({len(CA)} counties)")
    print(f"wrote {json_path}")
    print(f"residential PIF 2025-09-30: {dwe_pif['by_year']['2025']:,}")
    print(f"residential exposure 2025-09-30: ${dwe_tiv['by_year']['2025']:,}")


if __name__ == "__main__":
    main()
