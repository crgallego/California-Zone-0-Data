# Methodology

Five datasets, five different measurements. Read the section for the one you are
using — they do not share error bars, and two of them are estimates rather than
counts.

---

# Population by Fire Hazard Severity Zone

`data/population_by_fhsz_county.csv`, `data/population_by_fhsz_state.json`

## The measurement

Every 2020 census block group in California is represented by its official
Census Bureau **center of population** — the population-weighted centroid, not
the geographic one. Each center is tested against the statewide CAL FIRE FHSZ
polygons, and the block group's entire 2020 population is assigned to the tier
its center falls in. Where a point falls inside overlapping polygons, the more
hazardous tier wins.

25,607 block groups. The assigned populations sum to 39,538,223, which is the
2020 census count for California exactly.

## What this method does and does not do

This is **center assignment, not areal apportionment**. A block group that
straddles a zone boundary is counted whole, on whichever side its population
center sits.

- At **state and county scale** the errors are two-sided and largely cancel.
- For an **individual block group** they do not cancel at all.
- The method is **coarsest exactly where hazard is highest**: rural and montane
  block groups are geographically large, so one point stands in for a lot of
  ground. Treat county figures for sparsely populated counties as the roughest
  in the table.

Block groups are the finest geography for which the Census Bureau publishes
centers of population. There is no block-level equivalent, so this is the limit
of the method without moving to areal apportionment against block geometry.

## Sanity check against published figures

No state agency publishes this number. The figures in circulation come from
newsrooms:

| Source | Figure |
|---|---|
| This dataset | 4,993,057 in Very High or High, 12.63% |
| Washington Post analysis, 2025 | ~5.1 million, "1 in 8 Californians" |
| CalMatters, 2025 | ~3.7 million in high or very high under CAL FIRE's direct management |

The Post figure and this one agree closely, which is reassuring but not
independent confirmation — a similar method against the same source maps should
land in a similar place. The CalMatters figure is scoped to State Responsibility
Area land, a narrower question; the comparable number here is 1,476,121.

## Caveat on Zone 0

Zone 0 — the ember-resistant zone within 0–5 feet of a structure — is a
**draft** statewide standard, not an adopted regulation, as of the retrieval
date. These population figures describe **who lives in the hazard zones the
standard would apply to**, not who is currently subject to a requirement. Any
public use of these numbers should keep that distinction intact.

---

# Housing units by Fire Hazard Severity Zone

`data/housing_by_fhsz_county.csv`, `data/housing_by_fhsz_state.json`

## The measurement

This dataset adds no geometry. It reuses the block-group tier assignments from
the population dataset above — each block group placed by its Census center of
population — and attaches housing counts to them. The tier assignment is
therefore identical to the population file, and the two can be read side by side
without reconciling two methods. Every limit of the population method applies
here unchanged.

**Housing units** and **occupied housing units** are 2020 census counts, from
the PL 94-171 redistricting file. They are complete enumerations, not samples.
The state totals are 14,392,140 housing units and 13,475,623 occupied.

## Housing units or occupied units

Occupied units are the better answer to "how many households." Total housing
units are the better answer to anything about the physical building stock, and
the gap between them is not evenly spread:

| | Housing units | Occupied | Vacant or seasonal |
|---|---|---|---|
| SRA Very High | 456,674 | 356,897 | 21.8% |
| LRA Very High | 889,146 | 822,296 | 7.5% |
| California | 14,392,140 | 13,475,623 | 6.4% |

More than one housing unit in five in the State Responsibility Area's Very High
zone is vacant or seasonally occupied — the mountain second-home stock. Those
buildings have the same roof, the same siding and the same fence as any other.
Both columns are published so the question can pick its own denominator.

## Detached single-family and mobile homes are estimates, not counts

The decennial census does not ask what kind of building a housing unit is. These
two columns are the only modelled figures in this repository and are named
`_est` for that reason.

Each block group's ACS 2020–2024 share of units in structure is applied to that
block group's 2020 census housing-unit count. So the **share is measured** — a
five-year ACS estimate with its own sampling error — and what is assumed is only
that the share holds across the block group. Two consequences to keep:

- The ACS share and the census count are different vintages. Housing built or
  demolished between them is attributed at the older mix.
- 129 block groups holding 648 housing units between them have no ACS
  units-in-structure estimate and contribute zero detached units. They are
  overwhelmingly group-quarters block groups: 115,055 people, 648 housing units.
  The effect on any detached figure is under 0.01%.

Statewide, 57.1% of California housing units are detached single-family. In the
Very High zone it is 72.5%. The hazard zones are more single-family than the
state is, which is why a per-home statement behaves differently there than a
statewide average would suggest.

## The `draft_scope` aggregate is an interpretation

`data/housing_by_fhsz_state.json` publishes two rollups. `very_high` is a mapped
category and needs no explanation.

`draft_scope` is the whole State Responsibility Area — all tiers — plus Very
High in the Local Responsibility Area. That follows the April 17, 2026 draft's
own scope language: in the LRA the requirements attach to Very High, while in
the SRA defensible space applies under PRC 4291 across tiers. It is a reading of
a draft that is still in rulemaking and it is not a CAL FIRE category. If the
scope language changes before adoption, this aggregate changes with it and the
tier rows underneath it do not.

## What these numbers are not

They are a count of **housing units in hazard zones**. They are not a count of
fences, of homes with fences, or of combustible fences.

An earlier version of this section said no public dataset counts residential
fences. That was wrong, and it is worth saying so plainly rather than quietly
deleting it. CAL FIRE's Damage Inspection database has recorded, per structure,
whether a fence was attached and whether it was combustible, on every structure
it has inspected since 2013. See **Fence attachment** below. The rate no longer
has to be assumed, and this repository no longer assumes it.

What remains true is the warning that followed: multiplying a housing count by
an assumed fence rate produces a figure whose accuracy is entirely the accuracy
of the assumption. That is why the fence rates are measured and published
separately, and why the single figure that combines them is labelled an
estimate.

---

# FHSZ composition by community

`data/fhsz_by_community.csv`, `data/fhsz_by_community.json`

## The measurement

For each community:

1. **Boundary.** Fetch the official boundary polygon from US Census TIGERweb,
   `Places_CouSub_ConCity_SubMCD`. Incorporated Places are tried first, then
   Census Designated Places. The Census GEOID is recorded so the boundary used
   is unambiguous.

2. **Fire hazard polygons.** Query both CAL FIRE FHSZ feature services for every
   polygon intersecting the boundary's envelope, with geometry, in EPSG:4326.
   Results are paged until the service reports no further records.

3. **Clip.** Intersect each hazard polygon with the boundary polygon. Anything
   outside the community is discarded. This is the step that keeps a hazard zone
   on adjacent unincorporated land from being attributed to the city.

4. **Dissolve and de-overlap.** Union all clipped polygons within a tier, then
   subtract the more hazardous tiers, in the order Very High → High → Moderate →
   NonWildland. The published layers do overlap in places; without this step the
   shares for some communities sum to more than 100%. After it, each square mile
   is counted once, under the most hazardous tier that covers it.

5. **Area.** Longitude is scaled by the cosine of the boundary centroid's
   latitude, planar area is taken, and the result multiplied by
   (111,320 m/degree)². At city scale the error is well under 1%, and it largely
   cancels in the percentage shares.

## Denominators

`pct_of_boundary_area` is the share of the **full municipal boundary polygon**,
which is the same polygon the hazard zones were clipped to. That keeps the
percentages internally consistent and additive.

For most communities the boundary is almost entirely land and the distinction
does not matter. For two kinds of place it matters a great deal:

- **Coastal cities.** Malibu's Census boundary is 99.4 sq mi, of which only
  19.8 sq mi is land; the rest is ocean. Very High covers 18.1 sq mi, which is
  18% of the boundary but about 91% of the land.
- **Cities containing large water bodies.** Lake Elsinore's boundary includes the
  lake, and the published layers classify the water surface.

`census_land_area_sq_mi` is included on every row so either denominator can be
used. **`area_sq_mi` is the figure to quote when in doubt** — it needs no
denominator at all.

## `No mapped FHSZ polygon`

Every community has a row for the share of its boundary covered by no polygon in
either layer. For most cities this is a fraction of a percent.

Where it is large, there are two different explanations, and they should not be
confused.

**Water accounts for the coastal cases.** Malibu's residual is 81.8% and its
boundary is 80.0% water. Santa Barbara: 48.0% residual, 48.1% water. Montecito:
46.4% residual, 46.5% water. The hazard layers stop at the shoreline, so the
residual is the ocean inside the municipal boundary. Nothing unexplained.

**The mountain communities are a genuine gap.** These boundaries are almost
entirely dry land, and a large share still carries no polygon in either layer:

| Community | No mapped FHSZ | Water share of boundary |
|---|---|---|
| Idyllwild-Pine Cove | 40.3% | 0.3% |
| Crestline | 39.6% | 1.1% |
| Running Springs | 31.5% | 0.5% |
| Lake Arrowhead | 30.6% | 6.7% |
| Silverado | 28.3% | 0.3% |
| Modjeska | 23.3% | 0.2% |

**We have not confirmed why.** A plausible explanation is Federal Responsibility
Area land — every community in that table adjoins the San Bernardino or
Cleveland National Forest — which CAL FIRE does not classify in either of these
layers. That is an inference, not a finding. It is recorded here as an open
question rather than published as a fact. Until it is confirmed against a
primary source, read those rows as *no polygon in these two layers*, which is
all the measurement supports.

## What the numbers do not tell you

- **They are not parcel-level.** A community that is 70% Very High still contains
  parcels that are not. The reverse also holds.
- **They reflect the state maps only.** A local agency can adopt a designation
  broader than the state's recommended map. Malibu is the clearest case: the
  city's own council report states the entire city is Very High, while clipping
  the state LRA layer to the Census boundary returns about 91% of land. The
  local adoption is the operative designation; the layer is not wrong, it is
  answering a different question. **Where a local record and a state layer
  disagree, the local record governs and this dataset records the discrepancy
  rather than resolving it silently.**
- **They are dated.** The `retrieved` column is the date the layers were queried.
  CAL FIRE republishes; local agencies adopt. Re-run the script.
- **Boundaries move.** Annexation changes a city's polygon. The Census GEOID and
  vintage identify exactly which boundary produced each number.

## Known limitations

- Three communities that Firewise Fences publishes pages for are not Census
  places and so have no boundary-based row: Brentwood and Pacific Palisades
  (neighbourhoods of Los Angeles) and Anaheim Hills (a district of Anaheim).
  They appear in `point_checks.csv` as single-coordinate lookups, which describe
  one point and should not be read as describing a neighbourhood.
- Ring orientation in the source geometry is interpreted by the Esri convention
  that outer rings are clockwise. Malformed polygons are repaired with a zero
  buffer, which can shift an edge by a negligible amount.
- Tiers covering less than 0.05% of a boundary are dropped as noise.

---

# Fence attachment

`data/fence_attachment_dins.json`, `data/fence_attachment_by_county.csv`,
`data/zone0_combustible_fence_estimate.json`

## The measurement

CAL FIRE's Damage Inspection (DINS) database records, for every structure it
inspects, a field named `FENCEATTACHEDTOSTRUCTURE` with the values
**Combustible**, **Non Combustible**, **No Fence** and **Unknown**. Inspectors
have been filling it in since 2013. It is an open ArcGIS feature service, no key
required, and `scripts/build_fence_attachment_dins.py` is the whole method.

This is the rate the draft Zone 0 fence clause turns on, and it does not have to
be assumed.

## Surviving structures only

Rates here are computed on structures recorded as **No Damage**.

The fence is inspected after the fire. When a structure burns to the slab the
fence evidence burns with it, so a combustible fence at a destroyed structure is
frequently recorded as `No Fence` or `Unknown`. The field's own completeness
shows it: in the 2025 Palisades and Eaton fires, **10.7%** of fence records at
destroyed structures are `Unknown`, against **0.4%** at structures that took no
damage.

Measured both ways on the same two fires, single-family homes:

| Subset | Fence attached | Of attached, combustible |
|---|---|---|
| Surviving (used) | 82.7% | 52.3% |
| Destroyed (biased low) | 72.5% | 41.6% |

Both are published so the bias is visible rather than asserted. Denominators
exclude `Unknown` and null throughout.

## The cross-tabulation that looks like a finding and is not

Damage against fence type, 2025 Palisades and Eaton, all structure types:

| Fence at structure | Share destroyed |
|---|---|
| Combustible | 40.0% |
| Non-combustible | 52.1% |
| No fence | 59.8% |
| Unknown | 94.3% |

Read at face value this says a combustible fence protects a house. **It does
not.** It is the recording artifact above: the structures whose combustible
fences burned away are disproportionately the destroyed ones, and they are
counted in the `No Fence` and `Unknown` rows.

**DINS cannot support a causal claim about attached fences and structure loss in
either direction.** It supports incidence and materials. The cross-tab is
published in `fence_attachment_dins.json` rather than omitted, because anyone
who finds this field will run this query, and the artifact should travel with
the numbers.

## What the sample is

DINS covers structures inside or within 100 metres of a fire perimeter. It is a
**wildfire-exposed sample of California housing, not a census of it**, and it
over-represents whatever happened to burn.

The rate varies more than threefold by county, which is why the county table
exists and why the derived estimate is county-weighted:

| County | Fence attached | Of attached, combustible | Combustible and attached |
|---|---|---|---|
| Orange | 87.2% | 17.9% | 15.6% |
| Los Angeles | 81.2% | 52.0% | 42.2% |
| Sonoma | 56.0% | 90.3% | 50.5% |
| Plumas | 17.7% | 39.6% | 7.0% |

Orange County fences heavily and fences in block wall and vinyl. Sonoma fences
in wood. Plumas largely does not fence. A single statewide rate hides all of
this, and generalising the dense-suburban Los Angeles rate to the state is not
supported by the other counties.

DINS also records **one fence flag per structure**. A typical suburban lot has
two side-yard fences meeting the house, so a count of homes with a fence
attached is a count of homes, not of attachment points.

## The one derived estimate

`data/zone0_combustible_fence_estimate.json` is the only modelled output in this
repository, and it is labelled as one. It applies each county's measured rate to
that county's Very High detached-home count where the county sample reaches 100
determined structures, and the statewide rate elsewhere — 70.8% of the homes are
covered by a county-measured rate.

**261,781 homes with a combustible fence attached to the house; 1,308,905 feet
of five-foot span; 248 miles.**

Cross-checked against a flat statewide rate, which gives 268,590 homes. The two
methods agree within 3%, and that agreement is the main reason to trust the
order of magnitude. Applying the Palisades/Eaton rate statewide instead would
give roughly 422,000 homes; the county table is why that is not published.

Two error sources compound here: the housing input is itself an ACS-derived
estimate, and the rate is measured on a wildfire-exposed sample. The one-span-
per-home assumption runs the other way and is probably conservative.

### Split by responsibility area, because the clocks differ

| | Homes | Feet | Share |
|---|---|---|---|
| Local Responsibility Area | 175,505 | 877,525 | 67.0% |
| State Responsibility Area | 86,276 | 431,380 | 33.0% |

The draft times the two differently. LRA existing structures comply **within
three years** of the effective date, or five on a local agency's timeline
(§ 1298.04(c)(3)). SRA existing structures get **five years by default**, with
three the floor the Director cannot go below (§ 1299.03(e)(3)).

A single statewide figure quoted against the three-year clock therefore
over-covers by the SRA third. Published in `by_responsibility_area` so the
proportion is checkable rather than asserted.

Zone 0 remains a draft. This is a count of homes the clause would reach, not of
homes that owe anything today.

---

# Where the fire started on the structure

`data/fence_ignition_dins.json`

## Why this is different from everything above

The attachment rates answer "how many." This answers "so what," and it is the
only thing in DINS that does.

`WHEREFIRESTARTEDONSTRUCTURE` is the inspector's determination of which part of
the building the fire started at. It is a direct observation written down at the
scene, not an inference drawn from a cross-tabulation, and that is what makes it
usable where the damage cross-tab is not.

Critically, it is **not** wrecked by post-fire evidence loss. 97% of the
fence-ignition records are structures that were **not** destroyed, so the fence
was still standing when the inspector looked at it.

## The measurement

Among structures where an ignition point on the building was determined, and the
fence material was recorded:

| Fence at the structure | Structures | Fire started at the fence | Share |
|---|---|---|---|
| **Combustible** | 983 | 214 | **21.8%** |
| Non-combustible | 988 | 32 | 3.2% |
| No fence | 1,508 | 8 | 0.5% |

A combustible attached fence is the ignition point **6.7 times** as often as a
non-combustible one, and **41 times** as often as no fence at all.

Ranked against every other recorded ignition point on a structure, the attached
fence is **fourth of nine**, above the roof:

| Ignition point | Records | Share |
|---|---|---|
| Siding | 1,485 | 42.3% |
| Window | 715 | 20.4% |
| Eaves | 298 | 8.5% |
| **Attached fence** | **254** | **7.2%** |
| Deck, elevated | 220 | 6.3% |
| Roof | 213 | 6.1% |
| Attached patio cover / carport | 173 | 4.9% |
| Deck, on grade | 127 | 3.6% |
| Vent | 19 | 0.5% |

The 254 fence ignitions are spread across **30 separate incidents** — Eaton 80,
Palisades 74, Camp 21, Carr 18, Woolsey 12, and 25 more. This is not one
anomalous fire.

## What it does not say

**It is not a loss statistic.** Of the 254 structures where the fire started at
the attached fence, **5 were destroyed** and 221 were recorded as Affected
(0–10% damage). The fence caught; the house mostly did not. Saying "a fence
burned down N houses" is not supported and should not be written.

**It is a small and non-random subset.** Only 3,504 of roughly 132,000 DINS
records carry a determined ignition point. An inspector may more readily
attribute ignition to a visibly burned fence line than to siding, which would
inflate the fence count. The comparison *between materials* is drawn inside that
same subset, which is what keeps it meaningful — but the absolute 7.2% share
should not be read as "7.2% of California structure fires start at a fence."

**It is about attachment, not fences generally.** The field records ignition at
an *attached* fence, which is the thing the draft Zone 0 clause addresses.
