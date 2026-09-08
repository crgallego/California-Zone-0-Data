#!/usr/bin/env python3
"""Deterministic repository-wide publication-safety validator.

Runs against the exact tracked-file tree (``git ls-files``), so it sees
whatever is actually committed, not what is on disk. Pure standard library,
no network access, no timestamps in its own output: given the same tree, it
always produces the same result.

Checks, in order:
  1. forbidden paths      -- private C-13/CSLB inputs must never be tracked
  2. file-type allowlist  -- rejects unexpected binaries, archives,
                             spreadsheets, and databases by extension
  3. binary content       -- rejects a disguised binary hiding behind an
                             allowed text extension (NUL-byte check)
  4. JSON validity        -- every ``.json`` file parses
  5. CSV validity         -- every ``.csv``/``.tsv`` file has consistent
                             column counts
  6. private-field names  -- rejects known-private header/key names
                             (email, phone, ssn, bond, insurance, ...)
  7. percent range        -- any ``pct``/``percent`` field must be numeric
                             and within [0, 100.5]
  8. date plausibility    -- any ``retrieved``/``*_date``/``date_*``/
                             ``submitted`` field must look like a real date
  9. generated-output allowlist -- every file under ``data/`` must be on the
                             approved output list
 10. fhsz join            -- fhsz_by_community.csv and .json describe the
                             same set of community slugs
 11. forbidden source domain -- no script may reference a source domain
                             this repository has withdrawn from (currently
                             cfpnet.com; see CHANGELOG.md 2026-09-08)
 12. provenance checksum  -- any ``sha256`` key found anywhere in a
                             ``data/*.json`` file must be a non-empty
                             string, not a blank or stub value.
 13. fetch provenance coverage -- every script that performs a network
                             fetch must either use ``provenance.fetch`` or
                             be named on the dated exception list in this
                             file. Checks 12 and 13 together are what keep
                             partial provenance coverage honest: 12 alone
                             would be silently satisfied by a fetch script
                             that records no checksum at all, so 13 is the
                             check that makes an un-instrumented fetch
                             script fail loudly instead of passing by
                             omission.

Small-cell suppression for individually identifying counts (the CSLB/C-13
"controlled" tier in the release plan) is enforced by check 1: that data
class is not permitted in this repository at all, so there is nothing to
suppress a threshold against here. A blanket numeric small-value rule was
deliberately not added -- county-level aggregate rollups in this repo
legitimately contain single-digit cells (e.g. a handful of DIC-renewed
policies in a small county), and flagging those would be a false positive,
not a privacy finding.
"""
import csv
import json
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

FORBIDDEN_PATH_PATTERNS = [
    re.compile(r"^data/c13/"),
    re.compile(r"^scripts/build_c13_locator\.py$"),
    re.compile(r"^tests/fixtures/c13_.*\.csv$"),
    re.compile(r"(^|/)CSLBSearchData"),
    re.compile(r"(^|/)c13-census-"),
    re.compile(r"(^|/)c13_census_"),
]

ALLOWED_EXTENSIONS = {".md", ".py", ".yml", ".yaml", ".json", ".csv", ".tsv", ".cff", ".txt"}
ALLOWED_EXACT_NAMES = {"LICENSE", ".gitignore", "CODEOWNERS"}

DENIED_EXTENSION_EXPLANATIONS = {
    ".xlsx": "spreadsheet",
    ".xls": "spreadsheet",
    ".zip": "archive",
    ".tar": "archive",
    ".gz": "archive",
    ".7z": "archive",
    ".rar": "archive",
    ".db": "database",
    ".sqlite": "database",
    ".sqlite3": "database",
    ".parquet": "database-like binary",
}

PRIVATE_FIELD_NAMES = {
    "email", "e-mail", "phone", "telephone", "fax", "ssn", "social_security_number",
    "dob", "date_of_birth", "bond", "bond_number", "insurance", "workers_comp",
    "workers_compensation", "password", "secret", "api_key", "apikey", "token",
    "ip_address", "home_address", "contact", "contact_name", "contact_email",
    "contact_phone",
}

GENERATED_OUTPUT_ALLOWLIST = {
    "data/cdi_policy_counts_by_county.csv",
    "data/cdi_policy_counts_state.json",
    "data/fence_attachment_by_county.csv",
    "data/fence_attachment_dins.json",
    "data/fence_ignition_dins.json",
    "data/fhsz_by_community.csv",
    "data/fhsz_by_community.json",
    "data/housing_by_fhsz_county.csv",
    "data/housing_by_fhsz_state.json",
    "data/point_checks.csv",
    "data/population_by_fhsz_county.csv",
    "data/population_by_fhsz_state.json",
    "data/zone0_combustible_fence_estimate.json",
}

PCT_FIELD_RE = re.compile(r"(pct|percent)", re.IGNORECASE)
DATE_FIELD_RE = re.compile(r"(retrieved|_date$|^date_|submitted)", re.IGNORECASE)
PCT_MAX = 100.5

# Domains this repository has withdrawn from and must not fetch from again.
# See CHANGELOG.md for the dated withdrawal this entry corresponds to.
FORBIDDEN_SOURCE_DOMAINS = {
    "cfpnet.com": "California FAIR Plan Association — withdrawn 2026-09-08, "
                  "site terms prohibit reproduction/scraping",
}

# Every script that performs a network fetch must either use
# provenance.fetch (so its source is checksummed and drift-checked) or be
# named here with a dated reason. A fetch script that is neither fails
# check_fetch_provenance_coverage -- "non-empty when present" alone would be
# satisfied by silence, so this is the check that keeps an un-instrumented
# fetch script visible instead of quietly exempt by omission.
NETWORK_FETCH_MARKERS = (
    "urllib.request.urlopen",
    "urllib.request.Request",
    "requests.get(",
    "requests.post(",
    "http.client.",
)
PROVENANCE_MARKER = "provenance.fetch"
FETCH_PROVENANCE_SELF_EXEMPT = {"scripts/provenance.py", "scripts/validate_repo.py"}
FETCH_PROVENANCE_EXCEPTIONS = {
    "scripts/build_fence_attachment_dins.py": (
        "2026-09-08: makes many small server-side aggregate queries against "
        "the DINS ArcGIS feature service rather than fetching one discrete "
        "file; a single sha256 of \"the downloaded bytes\" does not map onto "
        "this control flow without a larger redesign than porting the call "
        "site."
    ),
    "scripts/build_fhsz_by_community.py": (
        "2026-09-08: queries CAL FIRE FHSZ feature services live, paginated "
        "per community boundary; same shape of problem as the DINS scripts "
        "above, not yet designed."
    ),
    "scripts/fetch_statewide_fhsz.py": (
        "2026-09-08: its output file is read directly by "
        "build_population_by_fhsz.py as a bare feature list; wrapping it in "
        "a provenance envelope means updating both files together and "
        "proving it with a full, network- and geometry-heavy pipeline run, "
        "which was not verified end-to-end in this pass."
    ),
}


def tracked_files():
    out = subprocess.run(
        ["git", "ls-files"], cwd=REPO_ROOT, capture_output=True, text=True, check=True
    ).stdout
    return [line for line in out.splitlines() if line]


def check_forbidden_paths(files, errors):
    for f in files:
        for pat in FORBIDDEN_PATH_PATTERNS:
            if pat.search(f):
                errors.append(f"forbidden-path: {f} matches private C-13/CSLB pattern {pat.pattern}")


def check_extensions(files, errors):
    for f in files:
        name = Path(f).name
        if name in ALLOWED_EXACT_NAMES:
            continue
        ext = Path(f).suffix.lower()
        if ext in ALLOWED_EXTENSIONS:
            continue
        explain = DENIED_EXTENSION_EXPLANATIONS.get(ext, "unexpected/unrecognized file type")
        errors.append(f"unexpected-file-type: {f} ({explain})")


def check_no_binary_content(files, errors):
    for f in files:
        name = Path(f).name
        ext = Path(f).suffix.lower()
        if name not in ALLOWED_EXACT_NAMES and ext not in ALLOWED_EXTENSIONS:
            continue  # already flagged by check_extensions
        path = REPO_ROOT / f
        try:
            data = path.read_bytes()
        except OSError:
            continue
        if b"\x00" in data:
            errors.append(f"binary-content: {f} contains a NUL byte despite an allowed text extension")


def check_percent_value(source, where, value, errors):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        errors.append(f"percent-not-numeric: {source}{where} = {value!r}")
        return
    if value < 0 or value > PCT_MAX:
        errors.append(f"percent-out-of-range: {source}{where} = {value}")


def check_date_value(source, where, value, errors):
    if not isinstance(value, str):
        return
    if not re.match(r"^\d{4}-\d{2}-\d{2}", value) and not re.search(r"(19|20)\d{2}", value):
        errors.append(f"unparseable-date: {source}{where} = {value!r}")


def walk_json(source, node, errors, path_hint=""):
    if isinstance(node, dict):
        for key, value in node.items():
            key_l = str(key).lower()
            here = f"{path_hint}/{key}"
            if key_l in PRIVATE_FIELD_NAMES:
                errors.append(f"private-field: {source}{here} is a disallowed private-field name")
            if PCT_FIELD_RE.search(key_l) and isinstance(value, (int, float)) and not isinstance(value, bool):
                check_percent_value(source, here, value, errors)
            if DATE_FIELD_RE.search(key_l):
                check_date_value(source, here, value, errors)
            walk_json(source, value, errors, here)
    elif isinstance(node, list):
        for i, item in enumerate(node):
            walk_json(source, item, errors, f"{path_hint}[{i}]")


def check_json_files(files, errors):
    for f in files:
        if not f.endswith(".json"):
            continue
        path = REPO_ROOT / f
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            errors.append(f"invalid-json: {f}: {exc}")
            continue
        walk_json(f, doc, errors)


def check_csv_files(files, errors):
    for f in files:
        if not (f.endswith(".csv") or f.endswith(".tsv")):
            continue
        delimiter = "\t" if f.endswith(".tsv") else ","
        path = REPO_ROOT / f
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            errors.append(f"unreadable-csv: {f}: {exc}")
            continue
        rows = list(csv.reader(text.splitlines(), delimiter=delimiter))
        if not rows:
            errors.append(f"empty-csv: {f}")
            continue
        header = rows[0]
        width = len(header)
        for lineno, row in enumerate(rows[1:], start=2):
            if len(row) != width:
                errors.append(f"ragged-row: {f}:{lineno} has {len(row)} fields, header has {width}")

        header_l = [h.strip().lower() for h in header]
        for h in header_l:
            if h in PRIVATE_FIELD_NAMES:
                errors.append(f"private-field: {f} header {h!r} is a disallowed private-field name")

        for col_idx, col_name in enumerate(header_l):
            is_pct = bool(PCT_FIELD_RE.search(col_name))
            is_date = bool(DATE_FIELD_RE.search(col_name))
            if not (is_pct or is_date):
                continue
            for lineno, row in enumerate(rows[1:], start=2):
                if col_idx >= len(row):
                    continue
                raw = row[col_idx].strip()
                if raw == "":
                    continue
                if is_pct:
                    try:
                        v = float(raw)
                    except ValueError:
                        errors.append(f"percent-not-numeric: {f}:{lineno} {col_name}={raw!r}")
                    else:
                        if v < 0 or v > PCT_MAX:
                            errors.append(f"percent-out-of-range: {f}:{lineno} {col_name}={raw!r}")
                if is_date:
                    if not re.match(r"^\d{4}-\d{2}-\d{2}", raw) and not re.search(r"(19|20)\d{2}", raw):
                        errors.append(f"unparseable-date: {f}:{lineno} {col_name}={raw!r}")


def check_generated_output_allowlist(files, errors):
    for f in files:
        if f.startswith("data/") and f not in GENERATED_OUTPUT_ALLOWLIST:
            errors.append(f"generated-output-not-allowlisted: {f} is under data/ but not on the approved output allowlist")


def check_fhsz_join(errors):
    csv_path = REPO_ROOT / "data/fhsz_by_community.csv"
    json_path = REPO_ROOT / "data/fhsz_by_community.json"
    if not csv_path.exists() or not json_path.exists():
        return
    with open(csv_path, newline="", encoding="utf-8") as fh:
        csv_slugs = {row["slug"] for row in csv.DictReader(fh)}
    with open(json_path, encoding="utf-8") as fh:
        json_slugs = set(json.load(fh).keys())
    missing_in_json = csv_slugs - json_slugs
    missing_in_csv = json_slugs - csv_slugs
    if missing_in_json:
        errors.append(f"join-mismatch: slugs in fhsz_by_community.csv but not .json: {sorted(missing_in_json)}")
    if missing_in_csv:
        errors.append(f"join-mismatch: slugs in fhsz_by_community.json but not .csv: {sorted(missing_in_csv)}")


def check_forbidden_source_domains(files, errors):
    for f in files:
        if not f.endswith(".py") or f == "scripts/validate_repo.py":
            continue  # this file's own denylist necessarily names the domain
        path = REPO_ROOT / f
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        for domain, reason in FORBIDDEN_SOURCE_DOMAINS.items():
            if domain in text:
                errors.append(f"forbidden-source-domain: {f} references {domain} ({reason})")


def collect_sha256_values(node, source, path_hint, out):
    if isinstance(node, dict):
        for key, value in node.items():
            here = f"{path_hint}/{key}"
            if key == "sha256":
                out.append((source, here, value))
            collect_sha256_values(value, source, here, out)
    elif isinstance(node, list):
        for i, item in enumerate(node):
            collect_sha256_values(item, source, f"{path_hint}[{i}]", out)


def check_provenance_checksums(files, errors):
    for f in files:
        if not (f.startswith("data/") and f.endswith(".json")):
            continue
        path = REPO_ROOT / f
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            continue  # already reported by check_json_files
        found = []
        collect_sha256_values(doc, f, "", found)
        for source, where, value in found:
            if not isinstance(value, str) or not value.strip():
                errors.append(f"empty-provenance-checksum: {source}{where} is present but empty")


def check_fetch_provenance_coverage(files, errors):
    for f in files:
        if not f.startswith("scripts/") or not f.endswith(".py"):
            continue
        if f in FETCH_PROVENANCE_SELF_EXEMPT:
            continue
        path = REPO_ROOT / f
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        if not any(marker in text for marker in NETWORK_FETCH_MARKERS):
            continue  # not a fetch script at all
        if PROVENANCE_MARKER in text:
            continue  # instrumented
        if f in FETCH_PROVENANCE_EXCEPTIONS:
            continue  # explicit, dated, reasoned exception
        errors.append(
            f"fetch-without-provenance: {f} performs a network fetch but "
            "does not use provenance.fetch and is not on the dated "
            "exception list in scripts/validate_repo.py"
        )


def main():
    errors = []
    files = tracked_files()

    check_forbidden_paths(files, errors)
    check_extensions(files, errors)
    check_no_binary_content(files, errors)
    check_json_files(files, errors)
    check_csv_files(files, errors)
    check_generated_output_allowlist(files, errors)
    check_fhsz_join(errors)
    check_forbidden_source_domains(files, errors)
    check_provenance_checksums(files, errors)
    check_fetch_provenance_coverage(files, errors)

    if errors:
        print(f"FAIL: {len(errors)} validation error(s)", file=sys.stderr)
        for e in sorted(errors):
            print(f"  - {e}", file=sys.stderr)
        return 1

    print(f"PASS: {len(files)} tracked files validated, 0 errors")
    return 0


if __name__ == "__main__":
    sys.exit(main())
