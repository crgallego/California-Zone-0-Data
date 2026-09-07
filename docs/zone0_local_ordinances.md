# Local Zone 0 / defensible-space ordinance tracker

What: `data/zone0_local_ordinances.csv` — one row per community in
`fhsz_by_community.csv` (40 rows, joined on `slug`/`geoid`), tracking whether
that local agency has adopted its own Zone 0, ember-resistant-zone, or
fence-material rule, independent of the state rulemaking's own timeline.

Why: no public dataset tracks this. The statewide Zone 0 rule
(`data/zone0_rulemaking_status.json`) has no effective date yet, but several
of these places already have their own defensible-space or fire-resistant-
landscaping ordinances in force today — a homeowner or a reporter in one of
these 40 places needs to know that regardless of what OAL decides.

## Columns

| Column | Meaning |
|---|---|
| `slug` / `geoid` | Join key, from `fhsz_by_community.csv` |
| `jurisdiction` | Place name |
| `status` | `not_yet_researched`, `no_known_ordinance`, or `adopted` |
| `authority` | Ordinance number and/or municipal code chapter/section |
| `adopted_date` / `effective_date` | ISO 8601, blank if not applicable |
| `scope` | What the ordinance covers (citywide, a specific buffer distance, etc.) |
| `fences_named` | Whether the ordinance specifically names fences, walls, or hedges |
| `source_url` | Primary source — a city page, PDF ordinance, or codified chapter |
| `retrieved` / `last_reviewed` | When the finding was checked |
| `note` | Caveats, related ordinances checked and ruled out, open questions |

## Method

Codified municipal code text is reachable, when the library site itself
blocks automated fetches, through Municode's underlying JSON API
(`api.municode.com/Jobs/latest/<productId>` -> jobId ->
`CodesContent?jobId=...&nodeId=...`) or through public code mirrors
(ecode360.com, qcode.us) that several of these cities use instead. County
fire codes apply for the unincorporated communities on this list (Altadena,
Crestline, Idyllwild, Lake Arrowhead, Modjeska Canyon, Montecito, Running
Springs, Santa Ynez, Silverado, Topanga, Trabuco Canyon) and are not yet
covered by this method — the same finding structure applies, but the source
is a county fire code or county fire protection district, not a city
municipal code.

## Current coverage

As of this dataset's first release, **2 of 40** communities have been
researched: Malibu (`adopted` — Ordinance No. 361, Fire-Resistant
Landscaping) and Rancho Cucamonga (`no_known_ordinance` — checked its fence
chapter and the fire district's FHSZ-designation ordinance; neither
addresses fence material). The remaining 38 are `not_yet_researched`, not
"no ordinance exists" — the tracker only reports what has actually been
checked. Findings live in `scripts/zone0_local_ordinances_findings.json`,
keyed by slug; `scripts/build_zone0_local_ordinances.py` regenerates the CSV
from that file plus `fhsz_by_community.csv` and never invents a value for a
community that has not been checked.

Cadence: quarterly, plus event-driven when the statewide Zone 0 status
moves (see `data/zone0_rulemaking_status.json`).
