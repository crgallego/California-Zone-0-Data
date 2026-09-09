<!--
Every pull request against this public repository must answer these before
review, per PLANS/FIREWISE_PUBLIC_DATA_REPO_SECURITY_AND_RELEASE_EXECUTION_PLAN_2026-09-08.md.
Delete this comment block before submitting.
-->

## What is this PR

<!-- One or two sentences: what changes, and why now. -->

## For a dataset change, answer all of these

- **Public question answered:**
- **Row grain:** (e.g. one row per county per year)
- **Counted / derived / modelled:**
- **Source(s) and retrieval date(s):**
- **Licence / redistribution basis:** (a public download does not by itself
  grant redistribution rights)
- **Source vintage:**
- **Privacy result:** (no person, contractor, customer, inspector, address,
  APN, contact, or licence-number field; no small cell below the approved
  threshold for any individually-identifying tier)
- **Reproduction command:**
- **Expected totals / sanity check:**
- **Limitations:**
- **Prohibited interpretations:** (what a reader must not conclude from this
  data)

## Validation

- [ ] `python3 scripts/validate_repo.py` passes locally
- [ ] The `validate` GitHub Actions check passes on this PR's exact head SHA
- [ ] For a generated file, the build was run twice and produced identical
      bytes (paste the diff command and its empty output)

## Stop conditions (do not open this PR if any is true)

- The branch is not descended from the current protected `main`.
- A source licence or redistribution right is unresolved.
- The output contains person, property, contractor, customer, inspector,
  address, APN, contact, licence-number, or unnecessary geocode data.
- A small cell violates the approved suppression threshold for an
  individually-identifying dataset.
- A workflow in this PR uses a mutable action reference, a self-hosted
  runner, broad write permission, or privileged execution of untrusted PR
  code.
