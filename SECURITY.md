# Security policy

This repository publishes aggregate, public-source wildfire and insurance
data for California's Zone 0 defensible-space effort. It is not a store for
personal, contractor, or licensee-level data, and it accepts no direct
commits or pushes to `main` outside of a reviewed pull request.

## What must never appear here

- Raw CSLB (Contractors State License Board) exports, C-13 contractor
  license-level records, or anything derived from them at individual-record
  grain. `.gitignore` and `scripts/validate_repo.py` both reject these paths;
  if either one is ever weakened, treat that as a security regression, not a
  cleanup.
- Personal contact fields: email, phone, address-of-a-person, SSN, date of
  birth, or similar. Government agency contacts published on an official
  public regulatory page (for example, an OAL rulemaking docket entry) are
  not personal data and are fine to retain with their source cited.
- Any credential, API key, token, or private key, in code, data, workflow
  logs, or Actions artifacts.
- Any binary, archive, spreadsheet, or database file. Only the plain-text
  formats the validator allows (`.csv`, `.tsv`, `.json`, `.md`, `.py`,
  `.yml`/`.yaml`, `.cff`, `.txt`) are accepted.

## Reporting a vulnerability or a data-exposure concern

Please use GitHub's private vulnerability reporting for this repository
(**Security** tab -> **Report a vulnerability**) rather than opening a public
issue. Private vulnerability reporting is enabled on this repository.

If the concern is a specific commit, branch, or artifact that may carry
private data, say so explicitly and do not paste the sensitive content back
into the report -- reference the ref/path/SHA instead.

## What happens on a confirmed finding

1. Containment first: automation affecting the exposed ref is frozen, and
   credentials are rotated if any were exposed.
2. A redacted, dated finding record is kept in this repository's owning
   workspace (not in this public repo).
3. Deleting a public ref, artifact, release, or history requires the
   repository owner's explicit approval -- closing a pull request or
   deleting a branch is not treated as proof that the underlying commits are
   unreachable, since GitHub can retain them elsewhere (forks, PR refs,
   cached clones) for a period.
4. A correction is published visibly. A materially wrong or improperly
   published dataset is never silently replaced.

## Supply-chain expectations

- GitHub Actions in this repository are pinned to a full commit SHA, not a
  mutable tag or branch.
- Workflows default to `permissions: contents: read`; a job is only granted
  more than that for an explicitly reviewed reason.
- Only GitHub-hosted runners are used. No self-hosted runner, and no
  privileged execution of untrusted pull request code (no `pull_request_target`
  running code from the incoming branch).
