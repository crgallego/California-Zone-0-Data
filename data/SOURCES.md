# Data sources and rights basis

One row per published dataset or dataset group under `data/` -- not
literally one row per file. `data/LICENSE` (the CC BY 4.0 grant text) and
this file itself are governance documents, not published datasets: they
describe the table below and are deliberately not rows in it.
This table is what `README.md` and the closing scope note in `data/LICENSE`
point to for what is actually being licensed and what is not. See
`data/LICENSE` for what Firewise's own CC BY 4.0 grant covers, and why it
does not extend to third-party facts.

| File(s) | Publisher | Public agency or private body | Source | Vintage / retrieved | Rights basis |
|---|---|---|---|---|---|
| `population_by_fhsz_county.csv`, `population_by_fhsz_state.json` | US Census Bureau (centers of population) + CAL FIRE/OSFM (FHSZ SRA/LRA polygons) | Census: public, federal, public domain (17 U.S.C. § 105). FHSZ: public, CA state, Creative Commons Attribution -- confirmed directly against California's official open-data catalogue listing for the [Fire Hazard Severity Zone Viewer](https://lab.data.ca.gov/dataset/fire-hazard-severity-zone-viewer) (organization CAL FIRE, licence "Creative Commons Attribution"). The catalogue does not identify a numbered CC BY version, so "Creative Commons Attribution" (unversioned) is the primary-source-safe statement; a CAL FIRE FRAP mirror on Data Basin labels the same layer CC BY 3.0 and may be cited as corroboration, not as the originating agency's own publication | Census: `https://www2.census.gov/geo/docs/reference/cenpop2020/blkgrp/CenPop2020_Mean_BG06.txt`. FHSZ: `FHSZSRA_23_3`, `FHSZLRA25_v1_All` feature services | 2020 census; SRA map effective 2024-04-01, LRA map dated 2025-03-24 | Census data is US federal public domain. FHSZ carries a CC BY attribution obligation, satisfied by citing CAL FIRE/OSFM by name with the map vintage (see `README.md`'s Sources table). Firewise's tier-assignment method and compilation are the CC BY (Firewise) contribution |
| `housing_by_fhsz_county.csv`, `housing_by_fhsz_state.json` | US Census Bureau (PL 94-171, ACS 2020-2024) + same FHSZ layers | Census: public domain. FHSZ: CC BY | PL 94-171 CA redistricting file; ACS 5-year table B25024 | 2020 census; ACS 2020-2024 | Same basis as above; Firewise's ACS-share modeling (labeled `_est`) is the Firewise contribution |
| `fhsz_by_community.csv`, `fhsz_by_community.json` | US Census TIGERweb (boundaries) + FHSZ feature services | Census: public domain. FHSZ: CC BY | TIGERweb `Places_CouSub_ConCity_SubMCD`; `FHSZSRA_23_3`, `FHSZLRA25_v1_All` | boundary vintage per GEOID; `retrieved` per row | Same basis; Firewise's clip/dissolve/area method is the Firewise contribution |
| `fence_attachment_dins.json`, `fence_attachment_by_county.csv` | CAL FIRE Damage Inspection (DINS) | Public, CA state, Creative Commons Attribution -- confirmed directly at `https://data.ca.gov/dataset/cal-fire-damage-inspection-dins-data` | Open ArcGIS feature service (`POSTFIRE_MASTER_DATA_SHARE`), no key required | recorded since 2013; queried per script run | CC BY attribution obligation satisfied by naming CAL FIRE DINS and the dataset landing page (see `README.md`'s Sources table); Firewise's surviving-structures method and cross-tab annotation are the Firewise contribution |
| `zone0_combustible_fence_estimate.json` | Firewise Fences, Inc. (derived, from DINS + Census/ACS above) | Firewise's own derived output over CC BY / public-domain inputs | Derived; see rows above | derived 2026 | Fully Firewise's own modeled output; CC BY (Firewise) applies, and the CC BY attribution obligation for DINS still flows through since DINS is an input |
| `fence_ignition_dins.json` | CAL FIRE DINS | Public, CA state, CC BY (same basis as fence attachment) | Same ArcGIS feature service | recorded since 2013 | Same as the fence-attachment row above |
| `cdi_policy_counts_by_county.csv`, `cdi_policy_counts_state.json` | California Department of Insurance | Public, CA state agency. CDI's official [Website Privacy Policy](https://www.insurance.ca.gov/privacy-policy/index.cfm), under Ownership, states that CDI website information and content is considered public domain unless otherwise indicated and may be distributed or copied as permitted by law; it separately excludes content not owned or created by CDI (which requires permission from its owning source) and does not authorize use of CDI's logos, emblems, or seals | `DataAnalysisOnWildfiresAndInsurance.cfm`; Jan 13 2025 fact sheet | report year 2024 (CY 2020-2023); retrieved 2026-08-14 | This repository republishes only CDI's own published aggregate counts and figures from the source above, under CDI's public-domain Ownership policy, plus Firewise's rate calculations and reconciliation as the Firewise (CC BY) contribution -- not any third-party-owned or third-party-expressive material, and no CDI branding. The `fair_plan_*` flow columns in these files (`fair_plan_new`, `fair_plan_renewed`, and related fields) are CDI's own published counts, not the California FAIR Plan Association's -- see the note on the withdrawn dataset below |
| `point_checks.csv` | Mixed, per row -- see `point_source` column: Firewise Fences, Inc. (own/chosen coordinates) for most rows; OpenStreetMap contributors, via Nominatim, for 4 rows; CAL FIRE/OSFM (FHSZ) for every row's cross-check result | Firewise: own content. The 4 rows with `point_source` = `OpenStreetMap Nominatim` are © [OpenStreetMap contributors](https://www.openstreetmap.org/copyright), licensed under the [Open Database License (ODbL) v1.0](https://opendatacommons.org/licenses/odbl/1-0/); Nominatim's own [usage policy](https://operations.osmfoundation.org/policies/nominatim/) additionally requires visible attribution for any public use of its results. FHSZ result columns: same CC BY basis as the FHSZ rows above | `firewisefences.com/service-areas/...` (Firewise rows); OpenStreetMap Nominatim geocoding (4 rows identified in `point_source`); FHSZ layers above | per-row `retrieved` | Firewise's own coordinates are published/chosen as stated per row. The 4 OpenStreetMap-derived coordinates are reproduced here as individual geocoded facts, attributed to OpenStreetMap contributors as required by ODbL and by Nominatim's usage policy; Firewise does not own, and does not purport to relicense, these 4 coordinate values -- they remain ODbL-licensed OpenStreetMap data, and ODbL's share-alike terms for a produced database built from OSM data apply to this file's inclusion of them, not just its attribution. FHSZ result columns carry the same CC BY basis as the FHSZ rows above |

## Withdrawn: California FAIR Plan Association data

`fair_plan_by_county.csv` and `fair_plan_state.json` were published in this
repository and withdrawn 2026-09-08. They republished California FAIR Plan
Association policies-in-force and insured-exposure figures parsed from PDFs
at cfpnet.com. The Association's own terms of use prohibit reproducing,
distributing, or scraping information obtained from its website, and this
repository does not publish data against a source's explicit terms. See
`CHANGELOG.md` for the dated withdrawal entry. There is no row for these
files above because they no longer exist in this repository; the figures
remain available directly from the Association at
[cfpnet.com/key-statistics-data](https://www.cfpnet.com/key-statistics-data/).

This withdrawal does not affect `cdi_policy_counts_by_county.csv`'s
`fair_plan_*` columns (see that row above) -- those are California
Department of Insurance flow counts, a public agency source never drawn from
cfpnet.com, measuring a different thing (new/renewed policies per calendar
year, not policies-in-force as of a fiscal year-end).

## Pending (not yet built)

CDI's ZIP-level fire-risk/loss/premium dataset (mandated by Ins. Code § 929)
is the next dataset in the release plan. It will get its own row here, with
its own source decision record, once it is actually built and published --
not before.
