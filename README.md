# California Zone 0 Data

Open data on California Fire Hazard Severity Zones, published by
[Firewise Fences, Inc.](https://www.firewisefences.com)

Every row in this repository is derived from a government source you can query
yourself. Nothing here is a company estimate, a model output, or a figure taken
from secondary reporting. If a number cannot be traced to a primary source, it
is not in the dataset.

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
```

The script queries the three services above directly. It has no private inputs,
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
operate or what we sell. Nothing here counts fences. The housing file counts
housing units in hazard zones; how many of those have a fence, of what material,
attached to the building, is not measured by any public source we know of and is
not estimated here. Fire hazard designations vary within a community and
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
