# Zone 0 rulemaking status

What: the live status of the Zone 0 defensible-space emergency rulemaking
(14 CCR §§ 1298.01-1298.04, amending §§ 1299.01-1299.03), scraped daily from
the Office of Administrative Law's "Emergency Regulations Under Review" table.

Why: every count in this repository — people, housing units, fences — is
scoped to the hazard zones this rule would apply to, and the rule has no
effective date yet. That condition is now data, not prose, and it is checked
every day rather than once.

## Files

`data/zone0_rulemaking_status.json` — current-state summary. `status` is
either `under_review` (still listed on OAL's page) or `check_required` (the
package left that page, meaning OAL acted or the agency withdrew it — see
below). `checked` is the UTC timestamp of the last scrape.

`data/zone0_rulemaking_timeline.csv` — one row per dated event: `event`,
`date` (ISO 8601, blank if not yet known), `detail`, `source_url`. Seeded once
from the Board of Forestry vote and OAL submission; `oal_decision`,
`sos_filing`, and `effective_date` rows are filled in by hand once known
(the OAL page does not carry the outcome itself, see below).

`data/status/zone0_rulemaking_raw.json` — the git-scrape target. Overwritten
every run by `scripts/build_zone0_rulemaking_status.py`; `.github/workflows/
refresh-status.yml` commits it only when its content changes, so the commit
history of this one file is the changelog of the rulemaking.

## Known limitation

OAL only lists a package on the Under Review table while it is pending. Once
OAL approves it, disapproves it, or the agency withdraws it, the row
disappears and this page stops saying anything about it. When the scrape
script observes that, it sets `status` to `check_required` rather than
guessing at an outcome — the actual decision, effective date, and Secretary
of State filing date have to be confirmed against another source (e.g. the
Board of Forestry's own postings at bof.fire.ca.gov, which returned HTTP 403
to automated fetch as of 2026-08-29 and has to be checked by hand) and
entered into the timeline CSV.

## Source

Office of Administrative Law, Emergency Regulations Under Review.
https://oal.ca.gov/emergency_regulations/emergency_regulations_under_review/
Retrieved and re-checked daily; see `checked` in the status JSON for the most
recent successful check.
