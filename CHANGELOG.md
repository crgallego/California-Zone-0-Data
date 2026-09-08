# Changelog

## 2026-09-08 — Withdrew California FAIR Plan Association county/statewide files

**Removed:** `data/fair_plan_by_county.csv`, `data/fair_plan_state.json`,
`scripts/build_fair_plan.py`.

**Why:** these files republished California FAIR Plan Association
policies-in-force and insured-exposure figures — 58 counties × 5 fiscal
years, parsed from PDFs at cfpnet.com — and the script that produced them
downloaded those PDFs programmatically. The source site's terms of use
state that a visitor may not "modify, copy, distribute, transmit, display,
perform, reproduce, publish, license, create derivative works from,
transfer, or sell or re-sell any information... obtained from this
Website," and separately prohibit accessing the site via "data mining,
robots, spiders, scrapers or similar data gathering." This repository does
not publish data, or a tool for acquiring it, against a source's explicit
terms. The figures themselves were accurate as published and are unchanged;
they remain available directly from the Association at
[cfpnet.com/key-statistics-data](https://www.cfpnet.com/key-statistics-data/).

**What was not removed:** `data/cdi_policy_counts_by_county.csv` and
`data/cdi_policy_counts_state.json` keep their California Department of
Insurance–sourced **flow** counts of new and renewed FAIR Plan policies
(`fair_plan_new`, `fair_plan_renewed`, `fair_plan_new_plus_renewed`,
`fair_plan_share_of_new_plus_renewed_pct`, and the top-10-by-share ranking).
CDI is a public agency and was never the source of the withdrawn files; flow
(policies written in a calendar year) and stock (policies in force as of a
fiscal year-end) are different measurements, not two views of the same
number, and `METHODOLOGY.md` documents the distinction.

**Also removed:** the `fair_plan_pif_all_lines_2025` column from
`data/cdi_policy_counts_by_county.csv` and the matching key from
`data/cdi_policy_counts_state.json`. That column joined in the withdrawn
Association PIF figure for context; with the source file gone, the join has
nothing to point at. `scripts/build_cdi_policy_counts.py` no longer reads
`fair_plan_by_county.csv` or writes that column. Every other column in both
files is unchanged — verified by re-running the script and diffing the
output against the pre-withdrawal files field-by-field.
