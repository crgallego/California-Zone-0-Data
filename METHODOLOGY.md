# Methodology

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
