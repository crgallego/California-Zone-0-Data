#!/usr/bin/env python3
"""
Zone 0 emergency rulemaking status, scraped from the Office of Administrative
Law's "Emergency Regulations Under Review" table.

Why this dataset exists
  Every headline figure in this repository counts people or homes in a hazard
  zone the draft rule would apply to. The rule itself has no effective date.
  That condition used to live only in README/METHODOLOGY prose, which goes
  stale silently. This script turns OAL's own table into data, and is meant
  to run daily (see .github/workflows/refresh-status.yml): it overwrites
  data/status/zone0_rulemaking_raw.json every run, and a workflow commits it
  only when the content changed, so the git log of that one file becomes the
  changelog of a live rulemaking (git-scraping, see Simon Willison, 2020).

  This script does not track the rule's outcome. OAL lists a package on this
  page only while it is under review; once OAL acts (approve, disapprove, or
  the agency withdraws it), the row disappears from this table and this page
  no longer says what happened. When that happens the script sets status to
  "check_required" rather than guessing — the decision, Secretary of State
  filing date, and effective date have to be confirmed by hand at that point
  (e.g. against the Board of Forestry's own postings) and entered into
  data/zone0_rulemaking_timeline.csv.

Source
  Office of Administrative Law, Emergency Regulations Under Review.
  https://oal.ca.gov/emergency_regulations/emergency_regulations_under_review/
  Table id "tablepress-115", columns: Date Submitted to OAL, OAL File Number,
  Agency, Subject of Rulemaking, CCR Title(s) and Section(s) Affected,
  Contact Person.

  OAL's own text on the same page: "OAL must allow five calendar days for
  public comments after posting a notice of the filing... Unless otherwise
  indicated below, notice... is posted on this site the day the emergency
  action is filed with OAL." Submitted August 28, 2026 + 5 calendar days =
  comment close September 2, 2026.

Fixed facts (not on the OAL page, carried from the Board of Forestry's own
public record and the original research pass of 2026-09-07):
  - Board of Forestry final-draft vote: 2026-08-19.

Outputs
  data/status/zone0_rulemaking_raw.json   -- git-scrape target, overwritten
                                              every run
  data/zone0_rulemaking_status.json       -- current-state summary
  data/zone0_rulemaking_timeline.csv      -- one row per dated event
"""
import csv
import json
import os
import re
import sys
import urllib.request
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(HERE, "data")
STATUS_DIR = os.path.join(DATA, "status")

SOURCE_URL = "https://oal.ca.gov/emergency_regulations/emergency_regulations_under_review/"
AGENCY = "Board of Forestry and Fire Protection"
SUBJECT_MATCH = "Zone 0 Defensible Space"

BOF_VOTE_DATE = "2026-08-19"

RAW_PATH = os.path.join(STATUS_DIR, "zone0_rulemaking_raw.json")
STATUS_PATH = os.path.join(DATA, "zone0_rulemaking_status.json")
TIMELINE_PATH = os.path.join(DATA, "zone0_rulemaking_timeline.csv")

TIMELINE_FIELDS = ["event", "date", "detail", "source_url"]


def fetch(url):
    req = urllib.request.Request(
        url, headers={"User-Agent": "California-Zone-0-Data/1"}
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read().decode("utf-8", errors="replace")


def strip_tags(s):
    return re.sub(r"<[^>]*>", " ", s).strip()


def parse_row(html):
    """Return the OAL table row matching AGENCY + SUBJECT_MATCH, or None."""
    rows = re.findall(r"<tr[^>]*>(.*?)</tr>", html, re.S)
    for row in rows:
        cells = re.findall(r"<td[^>]*>(.*?)</td>", row, re.S)
        if len(cells) != 6:
            continue
        cells = [strip_tags(c) for c in cells]
        date_submitted, file_number, agency, subject, ccr, contact = cells
        if agency.strip() == AGENCY and SUBJECT_MATCH in subject:
            return {
                "date_submitted_to_oal": date_submitted.strip(),
                "oal_file_number": file_number.strip(),
                "agency": agency.strip(),
                "subject": subject.strip(),
                "ccr_sections_affected": ccr.strip(),
                "contact": re.sub(r"\s+", " ", contact).strip(),
            }
    return None


def comment_close_date(date_submitted):
    """OAL allows 5 calendar days for comment after posting."""
    from datetime import timedelta

    for fmt in ("%B %d, %Y",):
        try:
            d = datetime.strptime(date_submitted, fmt)
            return (d + timedelta(days=5)).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return ""


def load_existing_timeline():
    if not os.path.exists(TIMELINE_PATH):
        return []
    with open(TIMELINE_PATH, newline="") as f:
        return list(csv.DictReader(f))


def write_timeline(rows):
    with open(TIMELINE_PATH, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=TIMELINE_FIELDS)
        w.writeheader()
        for r in rows:
            w.writerow(r)


def seed_timeline(row, checked):
    date_submitted_iso = ""
    try:
        date_submitted_iso = datetime.strptime(
            row["date_submitted_to_oal"], "%B %d, %Y"
        ).strftime("%Y-%m-%d")
    except ValueError:
        pass
    comment_close = comment_close_date(row["date_submitted_to_oal"])
    return [
        {
            "event": "bof_final_draft_vote",
            "date": BOF_VOTE_DATE,
            "detail": "Board of Forestry and Fire Protection approves the final draft of Zone 0 (Sections 1298.01-1298.04, amending 1299.01-1299.03).",
            "source_url": "https://bof.fire.ca.gov/",
        },
        {
            "event": "oal_submission",
            "date": date_submitted_iso,
            "detail": f"Filed with OAL as emergency rulemaking, file {row['oal_file_number']}.",
            "source_url": SOURCE_URL,
        },
        {
            "event": "comment_period_close",
            "date": comment_close,
            "detail": "Five calendar days for public comment after OAL posting, per OAL's own emergency-rulemaking process notice.",
            "source_url": SOURCE_URL,
        },
        {
            "event": "oal_decision",
            "date": "",
            "detail": "Not yet decided as of last check. Update when the package leaves the OAL Under Review table.",
            "source_url": SOURCE_URL,
        },
        {
            "event": "sos_filing",
            "date": "",
            "detail": "Secretary of State filing date, once approved.",
            "source_url": "",
        },
        {
            "event": "effective_date",
            "date": "",
            "detail": "Statewide effective date, once filed.",
            "source_url": "",
        },
    ]


def main():
    checked = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    html = fetch(SOURCE_URL)
    row = parse_row(html)

    os.makedirs(STATUS_DIR, exist_ok=True)
    raw = {
        "source_url": SOURCE_URL,
        "checked": checked,
        "found_in_under_review_table": row is not None,
        "row": row,
    }
    with open(RAW_PATH, "w") as f:
        json.dump(raw, f, indent=2, sort_keys=True)
        f.write("\n")

    existing_timeline = load_existing_timeline()

    if row is None:
        status = {
            "status": "check_required",
            "note": (
                "The Zone 0 package is no longer listed in OAL's Under Review "
                "table. This means OAL acted (approved or disapproved) or the "
                "agency withdrew it -- this page does not say which. Confirm "
                "against the Board of Forestry's own postings and file the "
                "outcome in data/zone0_rulemaking_timeline.csv before trusting "
                "this repo's headline figures again."
            ),
            "source_url": SOURCE_URL,
            "checked": checked,
        }
        if not existing_timeline:
            sys.exit(
                "Zone 0 row not found on first run and no existing timeline -- "
                "seed data/zone0_rulemaking_timeline.csv by hand before automating."
            )
        write_timeline(existing_timeline)
    else:
        status = {
            "status": "under_review",
            "oal_file_number": row["oal_file_number"],
            "agency": row["agency"],
            "subject": row["subject"],
            "ccr_sections_affected": row["ccr_sections_affected"],
            "date_submitted_to_oal": row["date_submitted_to_oal"],
            "decision": None,
            "effective_date": None,
            "source_url": SOURCE_URL,
            "checked": checked,
        }
        if not existing_timeline:
            write_timeline(seed_timeline(row, checked))
        else:
            write_timeline(existing_timeline)

    with open(STATUS_PATH, "w") as f:
        json.dump(status, f, indent=2, sort_keys=True)
        f.write("\n")

    print(f"wrote {RAW_PATH}")
    print(f"wrote {STATUS_PATH} (status={status['status']})")
    print(f"wrote {TIMELINE_PATH}")


if __name__ == "__main__":
    main()
