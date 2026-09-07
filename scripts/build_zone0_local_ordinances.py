#!/usr/bin/env python3
"""
Local Zone 0 / defensible-space ordinance tracker, for the 40 communities
already in fhsz_by_community.csv.

Why this dataset exists
  No public dataset tracks which California local agencies have adopted their
  own Zone 0, ember-resistant-zone, or fence-material rules, or which have
  used the LRA five-year compliance option at 14 CCR 1298.04. The state rule
  in data/zone0_rulemaking_status.json has no effective date; some of these
  40 places already have their own defensible-space or fire-resistant-
  landscaping ordinances in force today, independent of that state timeline.
  This is the one dataset in this repository that is hand-researched rather
  than counted from a government table, because no single government source
  publishes it -- see docs/zone0_local_ordinances.md for the research method
  and its limits.

How this script works
  The join key (slug, geoid, jurisdiction) comes from data/fhsz_by_community.csv,
  so every community that repo already covers gets a row here, whether or not
  it has been researched yet. Actual findings -- authority, dates, scope,
  whether fences are named, source -- live in
  scripts/zone0_local_ordinances_findings.json, keyed by slug, and are merged
  onto the skeleton. A community with no entry in that file gets
  status="not_yet_researched" and every other field blank. This keeps the
  generated CSV a pure function of its two inputs: re-running this script
  never loses a finding and never invents one.

Per-row fields
  slug, jurisdiction, geoid, status, authority, adopted_date, effective_date,
  scope, fences_named, source_url, retrieved, last_reviewed, note

  status is one of: not_yet_researched, no_known_ordinance, adopted.

Outputs
  data/zone0_local_ordinances.csv
"""
import csv
import json
import os

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(HERE, "data")
SCRIPTS = os.path.join(HERE, "scripts")

FHSZ_CSV = os.path.join(DATA, "fhsz_by_community.csv")
FINDINGS_JSON = os.path.join(SCRIPTS, "zone0_local_ordinances_findings.json")
OUT_CSV = os.path.join(DATA, "zone0_local_ordinances.csv")

FIELDS = [
    "slug",
    "jurisdiction",
    "geoid",
    "status",
    "authority",
    "adopted_date",
    "effective_date",
    "scope",
    "fences_named",
    "source_url",
    "retrieved",
    "last_reviewed",
    "note",
]

EMPTY_FINDING = {
    "status": "not_yet_researched",
    "authority": "",
    "adopted_date": "",
    "effective_date": "",
    "scope": "",
    "fences_named": "",
    "note": "",
    "source_url": "",
    "retrieved": "",
}


def load_communities():
    seen = {}
    with open(FHSZ_CSV, newline="") as f:
        for row in csv.DictReader(f):
            seen.setdefault(row["slug"], (row["place_name"], row["geoid"]))
    return seen


def main():
    communities = load_communities()
    with open(FINDINGS_JSON) as f:
        findings = json.load(f)

    unknown = set(findings) - set(communities)
    if unknown:
        raise SystemExit(
            f"findings file has slugs not in fhsz_by_community.csv: {sorted(unknown)}"
        )

    rows = []
    for slug in sorted(communities):
        jurisdiction, geoid = communities[slug]
        finding = findings.get(slug, EMPTY_FINDING)
        row = {"slug": slug, "jurisdiction": jurisdiction, "geoid": geoid}
        row.update({k: finding.get(k, EMPTY_FINDING[k]) for k in EMPTY_FINDING})
        row.setdefault("last_reviewed", finding.get("retrieved", ""))
        rows.append(row)

    with open(OUT_CSV, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        for row in rows:
            w.writerow(row)

    researched = sum(1 for r in rows if r["status"] != "not_yet_researched")
    print(f"wrote {OUT_CSV} ({len(rows)} communities, {researched} researched)")


if __name__ == "__main__":
    main()
