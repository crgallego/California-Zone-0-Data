# California Zone 0 Data

Open data on California Fire Hazard Severity Zones, published by
[Firewise Fences, Inc.](https://www.firewisefences.com)

Every row in this repository is derived from a government source you can query
yourself. Nothing here is taken from secondary reporting, and if a number cannot
be traced to a primary source it is not in the dataset.

Two files are modelled rather than counted, and both say so on their face: the
detached single-family columns in the housing files, and
`zone0_combustible_fence_estimate.json`. Everything else is a count.

## Headline figure

**3,228,949 Californians live in a Very High Fire Hazard Severity Zone — 8.17%
of the state. Including High, 4,993,057, or 12.63%.**

Measured from Census 2020 block group centers of population against the CAL FIRE
statewide maps, retrieved 2026-08-14. All 58 counties are in
`data/population_by_fhsz_county.csv`. Method, limits and comparison to published
estimates: [METHODOLOGY.md](METHODOLOGY.md).

Zone 0 is still a draft statewide standard. These figures describe who lives in
the hazard zones it would apply to, not who is subject to a requirement today.

## What is in the first release

`data/population_by_fhsz_county.csv` — population by hazard tier for all 58
California counties, with the State and Local Responsibility Area split.
`data/population_by_fhsz_state.json` — the statewide totals.

`data/housing_by_fhsz_county.csv` — housing units and occupied housing units by
hazard tier, same 58 counties and same tier assignment, from the 2020 census
redistricting file. Includes an estimate of detached single-family units and
mobile homes, from ACS shares of units in structure.
`data/housing_by_fhsz_state.json` — the statewide totals and two rollups.

**1,345,820 housing units are in a Very High zone**, 1,179,193 of them occupied;
975,631 are detached single-family. Under the April 17, 2026 draft's scope — the
whole State Responsibility Area plus Very High in the Local Responsibility
Area — 1,727,936 housing units, of which 1,288,071 detached.

`data/fence_attachment_dins.json` — how many homes have a fence attached to the
house and what it is made of, from CAL FIRE's Damage Inspection (DINS) database,
which has recorded it per structure since 2013.
`data/fence_attachment_by_county.csv` — the same, for 49 counties.

Measured on **surviving** single-family structures, because at a destroyed
structure the fence burned before anyone could record it: **55.0% of homes
statewide have a fence attached to the house, and half of those fences are
combustible.** In the 2025 Palisades and Eaton fires it was 82.7% attached, 52.3%
of them combustible. County rates range from 7.0% to 50.5% combustible-and-
attached, so the county file matters more than the statewide one.

`data/zone0_combustible_fence_estimate.json` — the one derived figure here.
County-weighted, it puts **261,781 homes** in a Very High zone with a
combustible fence attached to the house: **1,308,905 feet, 248 miles** of
five-foot non-combustible span, if Zone 0 is adopted as drafted.

Do not cross damage against fence type to argue that attached fences cause
losses. The raw cross-tab appears to show the opposite, and both readings are
artifacts of when the fence gets recorded. METHODOLOGY.md explains why.

`data/fair_plan_by_county.csv` — California FAIR Plan policies in force and
insured exposure by county, fiscal years ending 2021–2025, from the
Association's published PDFs. County files mix residential, commercial, and
BOP. The last two columns join our Very High detached-home and combustible-
fence estimates for context only — a FAIR Plan policy is not a wood fence.
`data/fair_plan_state.json` — statewide residential rollup: **621,234
residential policies** and **$645.1 billion** of residential exposure as of
2025-09-30, up from 236,515 policies and $155.7 billion in 2021.

A later Association webpage snapshot (June 2026) puts all-lines PIF at 696,562
and exposure at $768 billion. That vintage has no county breakout and is kept
separate.

`data/cdi_policy_counts_by_county.csv` — California Department of Insurance
counts of new, renewed, and non-renewed voluntary-market homeowners policies,
plus new and renewed FAIR Plan and Difference-in-Conditions policies, for all
58 counties, calendar years 2020–2023. `data/cdi_policy_counts_state.json` —
the published statewide line and the 2015–2023 fact-sheet series.

A non-renewal is not a company drop. CDI's own fact sheet says 75–80% are
initiated by the policyholder. In 2023 the voluntary market recorded 788,485
non-renewals against 8.30 million new and renewed policies (9.5%). FAIR Plan
new-plus-renewed policies were 324,954, or 3.77% of the combined voluntary and
FAIR Plan flow, up from 1.6% in 2015. In the ten counties CDI ranks highest
for high-fire structures, that FAIR Plan share was 33.1%, and the residual
market in Tuolumne was almost as large as the voluntary market.

`data/fence_ignition_dins.json` — where the fire started **on** the structure,
as the inspector determined it at the scene. This is the one field in DINS that
speaks to consequence rather than incidence, and it is not distorted by
post-fire evidence loss, because 97% of these records are structures that
survived.

Among structures with a determined ignition point and a recorded fence
material, the fire started at the fence in **21.8%** of cases where that fence
was combustible, **3.2%** where it was non-combustible, and **0.5%** where there
was no fence — **6.7 times** and **41 times**. Across 30 separate incidents, the
attached fence is the fourth most common ignition point on a structure, above
the roof.

It is not a loss statistic. Of the 254 fence ignitions, 5 structures were
destroyed and 221 were recorded at 0–10% damage. The fence caught; the house
usually did not.

`data/compliance_forcing_functions.json` — the rules that are already in force,
quoted verbatim with their subdivisions. Not a measurement; a citation file.

The binding insurance regulation names the product. 10 CCR 2644.9 forbids an
admitted insurer from using a rating plan that does not reflect its mandatory
mitigation factors, and one of those factors is *"Incorporation of only
noncombustible materials into that portion of any improvements to the property
on which the Building Being Evaluated is located, **including fences and
gates**, which is situated within five (5) feet of the Building Being
Evaluated."* The same insurer must hand the policyholder their wildfire risk
score in writing, re-score within 30 days of a completed mitigation, and hear an
appeal. CDI's own FAQ: *"Your insurance company must give you a detailed
explanation for the score including how you can lower that score and how much
you could save."*

The California FAIR Plan puts it on its own discount sheet, applicable
2025-11-15: Immediate Surroundings discount 3 is *"only noncombustible materials
... including fences and gates, within 5 feet of the dwelling,"* and a separate
completion bonus requires all ten property-level criteria. A combustible fence
costs a policyholder both. Twelve discounts together reach at most **16.4%** off
the *wildfire portion* of a Dwelling Fire premium. No per-measure percentage is
published, by CDI or by the FAIR Plan.

Point of sale is a dated deadline that already exists. Civil Code 1102.19, in
force since 2021-07-01, requires a seller in a high or very high zone to hand the
buyer documentation of defensible space compliance, or sign an agreement putting
the buyer on a one-year clock. **1,577,667 housing units — 1,166,961 of them
detached — stand inside that trigger** (SRA High and Very High, plus LRA Very
High). Whether it also reaches LRA High, a designation that did not exist before
the 2025 maps and covers another 458,014 units, is an open legal question and is
recorded as open. Publish 1,577,667, not 2,035,681.

Civil Code 841 presumes the neighbor owes half. For a fence dividing two
properties, adjoining owners are *"presumed to be equally responsible for the
reasonable costs of construction, maintenance, or necessary replacement,"* after
30 days' written notice. The presumption is rebuttable, and it does not reach a
run that sits wholly on one owner's land — which is what an attached fence often
is.

`data/fire_risk_reduction_communities_2026.csv` — the Board of Forestry's 2026
Fire Risk Reduction Community List: **119 agencies**, 42 cities, 12 counties, 65
districts and departments, adopted by Resolution No. 2026-01 effective
2026-07-01. Being on it is one of the two ways a property earns the
community-level credit under 2644.9 and the FAIR Plan's Community discount.

It is not a list of jurisdictions with a Zone 0 ordinance or a fence rule, and it
should never be described as one.

`data/fhsz_by_community.csv` — Fire Hazard Severity Zone composition for 40
California communities. For each community it gives, per responsibility area and
per tier, the land area in square miles and the share of the municipal boundary
it covers.

Long format, one row per community × responsibility area × tier:

| Column | Meaning |
|---|---|
| `slug`, `place_name`, `geoid` | Community, and its Census GEOID |
| `boundary_source` | Which Census layer the boundary came from |
| `boundary_area_sq_mi` | Area of the full municipal boundary, measured geometrically |
| `census_land_area_sq_mi` | Census `AREALAND` for the same place, for reference |
| `responsibility_area` | `SRA`, `LRA`, or `NONE` |
| `fhsz_tier` | `Very High`, `High`, `Moderate`, `NonWildland`, or `No mapped FHSZ polygon` |
| `area_sq_mi`, `pct_of_boundary_area` | The measurement |
| `fhsz_layer`, `fhsz_layer_vintage` | Exact CAL FIRE layer and its published vintage |
| `retrieved` | Date the layer was queried |

`data/fhsz_by_community.json` — the same data, nested by community.

`data/point_checks.csv` — single-point lookups for places that are not Census
places (Los Angeles neighbourhoods, one Anaheim district) and for specific
sub-areas. Point checks describe one coordinate, not a community.

## Sources

| Dataset | Publisher | Vintage |
|---|---|---|
| [`FHSZSRA_23_3`](https://services1.arcgis.com/jUJYIo9tSA7EHvfZ/ArcGIS/rest/services/FHSZSRA_23_3/FeatureServer/0) | CAL FIRE, Office of the State Fire Marshal | State Responsibility Area maps effective 2024-04-01 |
| [`FHSALRA25_v1_All`](https://services1.arcgis.com/jUJYIo9tSA7EHvfZ/ArcGIS/rest/services/FHSALRA25_v1_All/FeatureServer/0) | CAL FIRE, Office of the State Fire Marshal | Local Responsibility Area map dated 2025-03-24, all rollout phases |
| [`Places_CouSub_ConCity_SubMCD`](https://tigerweb.geo.census.gov/arcgis/rest/services/TIGERweb/Places_CouSub_ConCity_SubMCD/MapServer) | US Census Bureau, TIGERweb | Incorporated Places and Census Designated Places |
| [Centers of Population by Block Group](https://www2.census.gov/geo/docs/reference/cenpop2020/blkgrp/CenPop2020_Mean_BG06.txt) | US Census Bureau | 2020 Census |
| [Redistricting Data (PL 94-171), California](https://www2.census.gov/programs-surveys/decennial/2020/data/01-Redistricting_File--PL_94-171/California/ca2020.pl.zip) | US Census Bureau | 2020 Census |
| [Table B25024, units in structure](https://www2.census.gov/programs-surveys/acs/summary_file/2024/table-based-SF/data/5YRData/acsdt5y2024-b25024.dat) | US Census Bureau | ACS 2020–2024 5-year |
| [`POSTFIRE_MASTER_DATA_SHARE`](https://services1.arcgis.com/jUJYIo9tSA7EHvfZ/arcgis/rest/services/POSTFIRE_MASTER_DATA_SHARE/FeatureServer/0) ([landing page](https://data.ca.gov/dataset/cal-fire-damage-inspection-dins-data)) | CAL FIRE | Damage Inspection (DINS), 2013–present |
| [FAIR Plan Key Statistics](https://www.cfpnet.com/key-statistics-data/) | California FAIR Plan Association | County PIF and TIV, FY ending 2025-09-30 |
| [Wildfire and insurance data](https://www.insurance.ca.gov/01-consumers/200-wrr/DataAnalysisOnWildfiresAndInsurance.cfm) | California Department of Insurance | County policy counts 2020–2023; fact sheet published 2025-01-13 |
| [10 CCR 2644.9, Safer from Wildfires](https://www.insurance.ca.gov/01-consumers/200-wrr/Safer-from-Wildfires.cfm) | California Department of Insurance | Regulation text and April 2023 consumer FAQ |
| [Wildfire Hardening Discounts](https://www.cfpnet.com/wp-content/uploads/2025/11/Discounts-for-Dwelling-Fire-Commercial-Policies-2025.11.15.pdf) | California FAIR Plan Association | Dwelling Fire and Commercial, applicable 2025-11-15 |
| [Fire Risk Reduction Community List](https://bof.fire.ca.gov/projects-and-programs/fire-risk-reduction-community-list) | Board of Forestry and Fire Protection | 2026 list, Resolution No. 2026-01, effective 2026-07-01 |
| [Civil Code 1102.19](https://leginfo.legislature.ca.gov/faces/codes_displaySection.xhtml?lawCode=CIV&sectionNum=1102.19.) and [Civil Code 841](https://leginfo.legislature.ca.gov/faces/codes_displaySection.xhtml?lawCode=CIV&sectionNum=841) | California Legislative Counsel | Operative 2021-07-01 and 2014-01-01 |

Retrieved 2026-08-14.

## Reproducing it

```
pip install shapely

# community composition
python scripts/build_fhsz_by_community.py < scripts/communities.tsv

# population by tier: download the statewide layers once, then classify
python scripts/fetch_statewide_fhsz.py
python scripts/build_population_by_fhsz.py
```

The population script also needs the Census centers of population file:

```
curl -O https://www2.census.gov/geo/docs/reference/cenpop2020/blkgrp/CenPop2020_Mean_BG06.txt
```

Housing units reuse the block-group assignments the population script writes, so
run that first, then:

```
curl -O https://www2.census.gov/programs-surveys/decennial/2020/data/01-Redistricting_File--PL_94-171/California/ca2020.pl.zip
unzip ca2020.pl.zip -d pl2020
curl -O https://www2.census.gov/programs-surveys/acs/summary_file/2024/table-based-SF/data/5YRData/acsdt5y2024-b25024.dat
python scripts/build_housing_by_fhsz.py

# insurance: FAIR Plan stock, then CDI flows
pip install pypdf cryptography
python scripts/build_fair_plan.py
python scripts/build_cdi_policy_counts.py

# rules already in force: the community list
pip install pypdf
python scripts/build_frrc_list.py
```

The FHSZ script queries the three services above directly. It has no private inputs,
no API keys, and no cached copies of the source data. If CAL FIRE republishes a
map, re-running it produces the updated numbers and the `retrieved` date moves.

See [METHODOLOGY.md](METHODOLOGY.md) for how boundaries are clipped, how
overlapping polygons are resolved, and what the numbers do not tell you.

## Scope

Population is statewide and covers all 58 counties. Community composition
covers the 40 communities that Firewise Fences already publishes research pages
for, so those pages can be checked against an independent measurement. The
intended scope is state, county and city level across California; the remaining
city coverage is the next release.

## What this is not

Firewise Fences is a fence company. This dataset is about fire hazard
designations, not about our products, and it makes no claim about where we
operate or what we sell.

Earlier releases said here that no public source measured how many homes have a
fence attached, and of what material. That was wrong: CAL FIRE's damage
inspectors have been recording it per structure since 2013, and the
`fence_attachment` files now publish what they recorded. The correction is left
visible rather than quietly removed.

What is still true is that those rates come from a wildfire-exposed sample
rather than a census of California homes, and that the single figure combining
them with the housing counts is an estimate and is labelled as one. Fire hazard
designations vary within a community and
change over time. **Do not use this dataset to determine the designation of a
specific parcel.** Use the
[official CAL FIRE FHSZ viewer](https://osfm.fire.ca.gov/what-we-do/community-wildfire-preparedness-and-mitigation/fire-hazard-severity-zones)
or your local fire authority.

## Licence

Data in `data/` is published under
[CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). Code in `scripts/` is
published under the MIT licence. Attribution: Firewise Fences, Inc. The
underlying CAL FIRE and US Census Bureau data remain the work of their
publishers.

## Corrections

If a number here is wrong, open an issue. Include the row and the primary source
that contradicts it, and it will be corrected or withdrawn.
