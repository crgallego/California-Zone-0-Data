#!/usr/bin/env python3
"""
The 2026 Fire Risk Reduction Community List, parsed into rows.

Why this dataset exists
  Two of the other datasets in this repository say what the hazard is and who
  is paying for it. This one says who the counterparty is.

  Public Resources Code section 4290.1 directs the Board of Forestry and Fire
  Protection to maintain a list of local agencies that meet the state's best
  practices for local fire planning. The list matters for a reason that is not
  obvious from the statute: being on it is one of the two ways a homeowner
  earns the community-level wildfire mitigation credit that every admitted
  insurer is required to offer under 10 CCR 2644.9(d)(1), and it is one of the
  two ways a California FAIR Plan policyholder earns the Community discount.

  So this is a list of 119 named public agencies whose residents get an
  insurance credit for the agency's own fire-planning work. Every one of them
  has a fire-planning staff, a published plan, and a standing reason to talk
  about defensible space.

What this list is not
  It is not a list of jurisdictions that have adopted a Zone 0 ordinance.
  It is not a list of jurisdictions with a fence rule. Nothing on this list
  implies any local ordinance about fencing exists. Adopted local ordinance
  dates are a separate, unbuilt dataset.

Source
  California Board of Forestry and Fire Protection, 2026 Fire Risk Reduction
  Community List, adopted by Resolution No. 2026-01, effective 2026-07-01.
  Program page: https://bof.fire.ca.gov/projects-and-programs/fire-risk-reduction-community-list
  The PDF is served from the Board's CDN endpoint; URL below.

  The Board updates the list every two years. Re-run against the then-current
  PDF rather than assuming this file stays true.

Requires: pypdf

Outputs
  data/fire_risk_reduction_communities_2026.csv
"""
import csv, os, re, sys, urllib.request

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PDF_URL = (
    "https://34c031f8-c9fd-4018-8c5a-4159cdff6b0d-cdn-endpoint.azureedge.net/-/media/"
    "bof-website/projects-and-programs/fire-risk-reduction-community-list/"
    "07-01-2026-frrcl-and-bof-resolution-of-approval.pdf"
    "?rev=3428690de0414895a06fe75c4de609b7&hash=3B29D082C5B6ADEB36048F2EDB7C6D79"
)
UA = "firewise-frrcl/1.0 (+https://www.firewisefences.com)"

# The three headings the Board uses, in the order they appear.
HEADINGS = [
    ("CITY:", "city"),
    ("COUNTY:", "county"),
    ("NON-CITY/NON-COUNTY:", "special district or department"),
    ("NON-CITY/NON-COUNTY CONTINUED:", "special district or department"),
]
# Everything after this line is the adopting resolution, not the list.
STOP = "CALIFORNIA BOARD OF FORESTRY AND FIRE PROTECTION"


def pdf_text(path):
    from pypdf import PdfReader
    return "\n".join(p.extract_text() or "" for p in PdfReader(path).pages)


def parse(text):
    """Walk the text linearly, tracking the most recent heading.

    The Board sets the list in three columns, so page order interleaves the
    CITY/COUNTY column with the NON-CITY column. Bullets are joined across
    line wraps: a bullet runs until the next bullet, heading, or boilerplate.
    """
    rows, kind = [], None
    buf = None
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith(STOP):
            break
        matched = next((k for h, k in HEADINGS if line.startswith(h)), None)
        if matched:
            if buf:
                rows.append((kind, buf)); buf = None
            kind = matched
            line = line.split(":", 1)[1].strip()
            if not line:
                continue
        if line.startswith("•"):
            if buf:
                rows.append((kind, buf))
            buf = line.lstrip("•").strip()
        elif buf is not None and not line.startswith("The Board"):
            # a wrapped continuation of the bullet above
            buf = f"{buf} {line}".strip()
    if buf:
        rows.append((kind, buf))

    out, seen = [], set()
    for kind, name in rows:
        name = re.sub(r"\s+", " ", name).strip(" .")
        if not name or kind is None:
            continue
        if name in seen:
            continue
        seen.add(name)
        out.append({"agency": name, "agency_type": kind})
    return out


def main():
    work = os.environ.get("FRRCL_WORK_DIR", HERE)
    path = os.path.join(work, "frrcl_2026.pdf")
    if not os.path.exists(path):
        req = urllib.request.Request(PDF_URL, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=120) as r, open(path, "wb") as f:
            f.write(r.read())

    rows = parse(pdf_text(path))
    if not rows:
        sys.exit("parsed no agencies; the PDF layout probably changed")

    out = os.path.join(HERE, "data", "fire_risk_reduction_communities_2026.csv")
    with open(out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["agency", "agency_type"])
        w.writeheader()
        w.writerows(sorted(rows, key=lambda r: (r["agency_type"], r["agency"])))

    counts = {}
    for r in rows:
        counts[r["agency_type"]] = counts.get(r["agency_type"], 0) + 1
    print(f"{len(rows)} agencies -> {out}", file=sys.stderr)
    for k, v in sorted(counts.items()):
        print(f"  {k}: {v}", file=sys.stderr)


if __name__ == "__main__":
    main()
