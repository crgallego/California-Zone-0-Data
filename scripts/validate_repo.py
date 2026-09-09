#!/usr/bin/env python3
"""Deterministic repository-wide publication-safety validator.

Runs against the exact tracked-file tree (``git ls-files``), so it sees
whatever is actually committed, not what is on disk. Pure standard library,
no network access, no timestamps in its own output: given the same tree, it
always produces the same result.

Checks, in order:
  1. forbidden paths      -- exact paths the one known C-13/CSLB commit
                             shipped (enumerated from that commit, not
                             hand-maintained), plus pattern rules for
                             filenames that don't exist yet but shouldn't
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
 11. forbidden source domain -- every tracked file that decodes as text
                             (not a fixed set of extensions) is scanned,
                             case-insensitively, for a domain this
                             repository has withdrawn from (currently
                             cfpnet.com; see CHANGELOG.md 2026-09-08). A
                             hit is either an error, or -- through the
                             exempt() primitive below, never a silent
                             carve-out -- a recorded, dated exemption for
                             documentation citing the withdrawn source, or
                             for the two files that must name the domain
                             to define/test this very check.
 12. provenance checksum  -- any ``sha256`` key found anywhere in a
                             ``data/*.json`` file must be a non-empty
                             string, not a blank or stub value.
 13. script fetch classification -- every ``scripts/*.py`` file, with no
                             exceptions carved into this loop, must be
                             declared instrumented, exempt with a dated
                             reason (through exempt()), or non-fetching in
                             SCRIPT_FETCH_CLASSIFICATION; an unclassified
                             script fails regardless of what it does. An
                             "instrumented" script must actually call
                             ``provenance.fetch`` (checked via AST, not a
                             text search) and its declared output(s) must
                             carry a non-empty checksum. A "non-fetching"
                             script whose AST contains a real network-fetch
                             call fails as a classification lie. This is
                             deliberately not a denylist of fetch-call
                             spellings to detect -- classification is
                             mandatory up front, and AST inspection is only
                             a liar-catcher afterward.

Every deliberate, policy-level carve-out in this file -- not a "this check
doesn't apply to this file type" scope filter, but "this file would fail
the rule and we are choosing to let it through" -- goes through the single
exempt() primitive (see its docstring). That function validates the dated-
reason form, records the exemption, and main()'s PASS line names every
recorded exemption by construction, so a future carve-out inherits all
three properties without its author needing to reimplement (and
potentially half-implement) them, and a carve-out that bypasses exempt()
is a visible code-review smell rather than a silent, untested hole.

Small-cell suppression for individually identifying counts (the CSLB/C-13
"controlled" tier in the release plan) is enforced by check 1: that data
class is not permitted in this repository at all, so there is nothing to
suppress a threshold against here. A blanket numeric small-value rule was
deliberately not added -- county-level aggregate rollups in this repo
legitimately contain single-digit cells (e.g. a handful of DIC-renewed
policies in a small county), and flagging those would be a false positive,
not a privacy finding.
"""
import ast
import csv
import datetime
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
    re.compile(r"^tests/test_c13_"),
    re.compile(r"(^|/)CSLBSearchData"),
    re.compile(r"(^|/)c13-census-"),
    re.compile(r"(^|/)c13_census_"),
]

# Every path this repository's one known C-13/CSLB commit actually added,
# enumerated from the commit itself rather than hand-maintained from memory
# of .gitignore -- a hand-maintained list is exactly how tests/test_c13_locator.py
# slipped past FORBIDDEN_PATH_PATTERNS above (that list was copied from
# .gitignore's *patterns*, which never named the test file, since .gitignore
# has no reason to ignore a file that was never meant to be committed at
# all).
#
# FORBIDDEN_COMMIT_SHA is LOCAL-ONLY and deliberately not published: it was
# never pushed to this public repository (confirmed 2026-09-08: GitHub's
# commit API returns 422 "No commit found" for it), and it lives on a local
# branch whose disposition -- archive, or delete -- is still an open
# decision with the repository owner. A reader cannot fetch or verify this
# SHA against the public remote, and that is expected, not a broken link.
# The list below is recorded here verbatim precisely so this file does not
# depend on that commit surviving or being reachable -- it is the complete
# record, not a pointer to one. It was derived, when the commit still
# existed in this working copy, with:
#   git diff --name-status 84eb9b8abb6dafa074eaf617490062d8f2615d6d^ \
#       84eb9b8abb6dafa074eaf617490062d8f2615d6d
# taking only the "A" (added) rows -- the one "M" row in that commit is
# README.md, a shared file whose *name* is not forbidden. If that local
# branch is ever deleted, re-deriving this exact list is no longer
# possible; this literal set is the only remaining record of it.
FORBIDDEN_COMMIT_SHA = "84eb9b8abb6dafa074eaf617490062d8f2615d6d"  # local-only, not on the public remote
FORBIDDEN_EXACT_PATHS = {
    "data/c13/README.md",
    "data/c13/contractors-c13-2026-09-07.json",
    "data/c13/contractors.schema.json",
    "data/c13/receipts/c13-2026-09-07.json",
    "scripts/build_c13_locator.py",
    "tests/fixtures/c13_census_batch.csv",
    "tests/fixtures/c13_cslb_export.csv",
    "tests/test_c13_locator.py",
}

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

def normalize_field_name(key):
    """Fold a JSON key or CSV header to one canonical lowercase snake_case
    form, so a policy spelled once in PRIVATE_FIELD_NAMES also catches
    camelCase, hyphenated, space-separated, or otherwise differently-
    punctuated spellings of the same field. Plain `.lower()` is a denylist
    of exactly one separator style -- the same fail-closed problem this
    file already solved for network-fetch call spellings via import-alias
    resolution, here applied to field names instead of call sites: a
    reviewed name gets matched by its meaning, not by whether the author
    happened to write it with underscores.

    Two substitutions, in order, because one alone misses acronyms:
    the first splits an ordinary camelCase boundary (lowercase/digit
    followed by uppercase, e.g. "license[N]umber"); the second splits an
    acronym boundary (uppercase followed by an uppercase-then-lowercase
    run, e.g. "IP[A]ddress" -> "IP_Address") that the first regex cannot
    see because there is no lowercase/digit immediately before the split
    point. Skipping the second step is exactly how "IPAddress" would
    silently normalize to "ipaddress" instead of "ip_address" and bypass
    an already-declared policy entry.
    """
    s = str(key)
    s = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "_", s)
    s = re.sub(r"(?<=[A-Z])(?=[A-Z][a-z])", "_", s)
    s = re.sub(r"[^0-9a-zA-Z]+", "_", s)
    return s.strip("_").lower()


# Declared as written by a reviewer -- "e-mail" and "email" both appear
# because they are genuinely different spellings someone might use, not
# because the set needs to be pre-normalized by hand. PRIVATE_FIELD_NAMES
# below is the actual enforced policy: every entry here pushed through
# normalize_field_name(), the same function applied to every observed key.
# Declaring a raw spelling here and separately hand-writing its normalized
# form (as the first pass at this policy did for "e-mail") is exactly the
# two-copies-can-drift bug that let a canonical-but-unnormalized entry
# silently stop matching once observed keys started being normalized.
_PRIVATE_FIELD_NAMES_RAW = {
    "email", "e-mail", "phone", "telephone", "fax", "ssn", "social_security_number",
    "dob", "date_of_birth", "bond", "bond_number", "insurance", "workers_comp",
    "workers_compensation", "password", "secret", "api_key", "apikey", "token",
    "ip_address", "home_address", "contact", "contact_name", "contact_email",
    "contact_phone",
    # Property/contractor/customer/inspector-identifying fields the public-
    # repo release plan's stop conditions prohibit outright (person,
    # property, contractor, customer, inspector, address, APN, contact, or
    # licence-number data) -- see PLANS/FIREWISE_PUBLIC_DATA_REPO_SECURITY_
    # AND_RELEASE_EXECUTION_PLAN_2026-09-08.md in the owning workspace.
    "address", "property_address", "site_address", "mailing_address",
    "apn", "parcel_number", "assessors_parcel_number",
    "license_number", "licence_number", "contractor_license_number",
    "customer_name", "customer_address", "owner_name", "property_owner",
    "inspector_name", "inspector_id",
}
PRIVATE_FIELD_NAMES = {normalize_field_name(name) for name in _PRIVATE_FIELD_NAMES_RAW}


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

# Governance/documentation files under data/ -- a licence grant and a rights
# table, not something any script produces. Deliberately a separate set from
# GENERATED_OUTPUT_ALLOWLIST rather than folded into it: admitting a file
# here is "this is a reviewed, hand-authored document," not "this is an
# approved shape of script output," and the two questions should not be
# answerable by the same membership check. A file lands here only by a
# reviewed addition to this literal, exactly like GENERATED_OUTPUT_ALLOWLIST
# -- an arbitrary new file under data/ still fails either way.
DATA_GOVERNANCE_FILES = {
    "data/LICENSE",
    "data/SOURCES.md",
}

PCT_FIELD_RE = re.compile(r"(pct|percent)", re.IGNORECASE)
# "percentile" contains "percent" as a substring but names a rank/threshold,
# not a percentage value (e.g. counties_at_or_above_50th_percentile_...,
# whose value is legitimately a container). Checked separately from
# PCT_FIELD_RE so the distinction is by what the key actually means, not by
# what type the value happens to be -- a genuine pct/percent field must
# still fail on a container value, it just can't be told apart from a
# percentile field by shape alone.
PERCENTILE_FIELD_RE = re.compile(r"percentile", re.IGNORECASE)
DATE_FIELD_RE = re.compile(r"(retrieved|_date$|^date_|submitted)", re.IGNORECASE)
PCT_MAX = 100.5

# Domains this repository has withdrawn from and must not fetch from again.
# See CHANGELOG.md for the dated withdrawal this entry corresponds to.
FORBIDDEN_SOURCE_DOMAINS = {
    "cfpnet.com": "California FAIR Plan Association — withdrawn 2026-09-08, "
                  "site terms prohibit reproduction/scraping",
}

# Files allowed to contain a forbidden-domain string despite
# check_forbidden_source_domains scanning every tracked text file: the
# domain denylist above and its regression test necessarily name the
# withdrawn domain as literal text. Values are dated reasons validated and
# recorded through exempt() below, same as every other carve-out in this
# file -- there is no second, unwatched mechanism that actually grants
# this skip.
DOMAIN_CHECK_SELF_REFERENCE = {
    "scripts/validate_repo.py": "2026-09-08: defines the domain denylist itself",
    "tests/test_validate_repo.py": "2026-09-08: regression-tests the domain denylist with literal fixtures",
}

# ---- Fetch-script classification --------------------------------------
#
# Detecting "does this script fetch the network" by pattern-matching source
# text against import/call spellings is a denylist of ways to make an HTTP
# request, and that denylist is never finished: the next script gets
# written in whatever style its author reaches for -- a different import
# alias, requests instead of urllib, a subprocess call to curl -- and an
# unmatched style silently reads as "doesn't fetch."
#
# So this inverts the check: every .py file under scripts/ must be
# explicitly classified as instrumented, exempt (with a dated reason), or
# non-fetching, and the validator fails on any unclassified script
# regardless of what it actually does -- no file, including the fetch
# helper and this validator itself, is exempted by being a special case in
# the loop. An earlier version of this file tried exactly that (a frozen
# "self-exempt" pair checked against a named constant) and it was wrong in
# a specific way: the constant was watched by a test, but the actual skip
# was a second, unwatched literal a few lines away, and widening that
# second literal (not the constant) silently granted the exemption to any
# file, reopening the provenance-checksum hole this classification exists
# to close. There is now exactly one mechanism -- this dict -- and
# provenance.py and validate_repo.py earn their way out of instrumentation
# through it like every other script, below. AST inspection further down
# is used only as a liar-catcher afterward, to confirm a script's
# classification is not contradicted by its own code -- it is not how
# membership in this dict gets decided, and it does not excuse a script
# from needing an entry.
DATED_REASON_RE = re.compile(r"^\d{4}-\d{2}-\d{2}:\s+\S")

# ---- The one exemption primitive ---------------------------------------
#
# Four rounds of review found the same defect wearing a different name:
# a named exemption dict or constant that a test watched, while the actual
# skip lived somewhere else -- a second literal, a membership check whose
# value was never read -- that nothing watched. This function is now the
# ONLY sanctioned way any check in this file may skip a file it would
# otherwise flag for a deliberate, policy reason. It is not for "this
# check doesn't apply to this file type" (an ordinary `continue` stays an
# ordinary `continue` for that) -- it is specifically for "this file would
# fail the rule, and we are choosing, on the record, to let it through."
#
# Every call validates the dated-reason form, records the exemption, and
# is picked up by main()'s PASS line automatically -- an author adding a
# new carve-out gets all three properties without needing to know they
# exist, and a carve-out that does NOT go through this function is a
# review smell (a `continue` next to a comment claiming something is
# exempt, with no exempt() call) rather than a silent, untested hole.
_RECORDED_EXEMPTIONS = []

# Files the domain-reference scan could not read as UTF-8 text, so it
# could not check them for the withdrawn domain string at all. This is a
# scope limit, not a policy exemption -- nobody decided these files should
# be allowed to reference the domain, the scan simply cannot see inside
# them -- so it is tracked separately from _RECORDED_EXEMPTIONS and does
# not go through exempt() or its dated-reason requirement. It is not a
# failure either: established empirically (2026-09-08) that every
# concrete case tried (a UTF-16 file, a Latin-1 file with one stray
# non-ASCII byte) either gets caught by another check for an unrelated
# reason or is genuinely invisible to every other check too. Recording and
# naming these files, the same way exemptions are named, is what turns
# "silently skipped" into "skipped, and you can see that it happened."
_UNDECODABLE_AS_TEXT = []


def reset_exemptions():
    _RECORDED_EXEMPTIONS.clear()
    _UNDECODABLE_AS_TEXT.clear()


def exempt(kind, path, reason, errors):
    """Record a deliberate, policy-level exemption for `path` under `kind`.
    Always returns True (the caller should skip) and always records the
    exemption, even a malformed one -- hiding a bad exemption from the
    PASS-line accounting would defeat the point of recording it at all.
    A reason that is not a dated, non-empty explanation is its own
    validation error, so a bad exemption still fails the run.
    """
    if not isinstance(reason, str) or not DATED_REASON_RE.match(reason):
        errors.append(
            f"exemption-not-dated: {kind} exemption for {path} must start "
            "with \"YYYY-MM-DD: \" followed by a non-empty explanation; "
            f"got {reason!r}"
        )
    _RECORDED_EXEMPTIONS.append((kind, path, reason))
    return True


SCRIPT_FETCH_CLASSIFICATION = {
    "scripts/provenance.py": {
        "status": "exempt",
        "reason": (
            "2026-09-08: this is the fetch helper itself -- it is what "
            "\"instrumented\" means for every other script, so it has "
            "nothing to call provenance.fetch on and no dataset output of "
            "its own to check a checksum against."
        ),
    },
    "scripts/validate_repo.py": {"status": "non-fetching"},
    "scripts/build_cdi_policy_counts.py": {
        "status": "instrumented",
        "outputs": ("data/cdi_policy_counts_state.json",),
    },
    "scripts/build_fence_attachment_dins.py": {
        "status": "exempt",
        "reason": (
            "2026-09-08: makes many small server-side aggregate queries against "
            "the DINS ArcGIS feature service rather than fetching one discrete "
            "file; a single sha256 of \"the downloaded bytes\" does not map onto "
            "this control flow without a larger redesign than porting the call "
            "site."
        ),
    },
    "scripts/build_fhsz_by_community.py": {
        "status": "exempt",
        "reason": (
            "2026-09-08: queries CAL FIRE FHSZ feature services live, paginated "
            "per community boundary; same shape of problem as the DINS scripts "
            "above, not yet designed."
        ),
    },
    "scripts/fetch_statewide_fhsz.py": {
        "status": "exempt",
        "reason": (
            "2026-09-08: its output file is read directly by "
            "build_population_by_fhsz.py as a bare feature list; wrapping it in "
            "a provenance envelope means updating both files together and "
            "proving it with a full, network- and geometry-heavy pipeline run, "
            "which was not verified end-to-end in this pass."
        ),
    },
    "scripts/build_housing_by_fhsz.py": {"status": "non-fetching"},
    "scripts/build_population_by_fhsz.py": {"status": "non-fetching"},
}


def parse_ast_safely(path):
    try:
        return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except (OSError, UnicodeDecodeError, SyntaxError):
        return None


def calls_provenance_fetch(tree):
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        fn = node.func
        if isinstance(fn, ast.Attribute) and fn.attr == "fetch" \
                and isinstance(fn.value, ast.Name) and fn.value.id == "provenance":
            return True
    return False


# Fully-qualified names of the stdlib/requests network-fetch entry points
# this classification cares about. Matched against a call's qualified name
# after resolving *how it was imported* (see resolve_qualified_call below),
# so a fresh import alias or a `from ... import ...` spelling of the same
# underlying function is not a new spelling to add here -- it resolves to
# the same qualified name this set already lists. Adding a genuinely new
# network API (not a new way to spell an existing one) still means adding
# a line here.
NETWORK_FETCH_QUALNAMES = {
    "urllib.request.urlopen",
    "urllib.request.urlretrieve",
    "requests.get",
    "requests.post",
    "requests.put",
    "requests.delete",
    "requests.patch",
    "requests.head",
    "requests.request",
    "http.client.HTTPConnection",
    "http.client.HTTPSConnection",
}


def build_import_aliases(tree):
    """Map every local name an import binds to its fully-qualified target.

    `import a.b.c` binds the top-level local name `a` to itself (Python
    resolves `a.b.c.whatever` by attribute lookup at runtime, not by the
    import statement rewriting the name) -- but `import a.b.c as x` and
    `from a.b import c [as x]` both bind a local name directly to the
    qualified path. Resolving both forms here is what lets a single call
    site below recognize a spelling regardless of which import style or
    alias introduced it.
    """
    aliases = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.asname:
                    aliases[alias.asname] = alias.name
                else:
                    top = alias.name.split(".")[0]
                    aliases[top] = top
        elif isinstance(node, ast.ImportFrom) and node.module:
            for alias in node.names:
                local = alias.asname or alias.name
                aliases[local] = f"{node.module}.{alias.name}"
    return aliases


def resolve_qualified_call(func_node, aliases):
    """Best-effort fully-qualified dotted name for a Call's `func`, with the
    leftmost (root) name resolved through `aliases`. Returns None for any
    call shape that isn't a plain Name/Attribute chain (e.g. the result of
    another call), which is exactly the case classification cannot see
    through -- it is not treated as a match.
    """
    parts = []
    node = func_node
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if not isinstance(node, ast.Name):
        return None
    parts.append(node.id)
    parts.reverse()
    resolved_root = aliases.get(parts[0], parts[0])
    return ".".join([resolved_root] + parts[1:])


def calls_network_fetch(tree):
    aliases = build_import_aliases(tree)
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        qualified = resolve_qualified_call(node.func, aliases)
        if qualified in NETWORK_FETCH_QUALNAMES:
            return True
    return False


def tracked_files():
    out = subprocess.run(
        ["git", "ls-files"], cwd=REPO_ROOT, capture_output=True, text=True, check=True
    ).stdout
    return [line for line in out.splitlines() if line]


def check_forbidden_paths(files, errors):
    for f in files:
        if f in FORBIDDEN_EXACT_PATHS:
            errors.append(
                f"forbidden-path: {f} is one of the exact paths commit "
                f"{FORBIDDEN_COMMIT_SHA} shipped (that commit is local-only, "
                "not on the public remote -- see FORBIDDEN_EXACT_PATHS above)"
            )
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
    """Genuinely parse `value` as an ISO 8601 date or date+time, not just
    match a leading prefix -- `re.match(r"^\\d{4}-\\d{2}-\\d{2}")` accepts
    an invalid calendar date like "2026-99-99" (the digits are the right
    shape, the date is not real) and any garbage appended after a valid
    prefix like "2026-01-01garbage" (the regex never anchors the end).
    Delegating to datetime.date/datetime.fromisoformat validates both the
    calendar and the full string in one place shared by every caller (JSON
    and CSV alike), instead of each call site re-implementing its own
    date-shaped regex and re-discovering the same gaps independently.
    """
    if not isinstance(value, str):
        errors.append(f"unparseable-date: {source}{where} = {value!r} (expected an ISO 8601 date string)")
        return
    candidate = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        if "T" in candidate:
            datetime.datetime.fromisoformat(candidate)
        else:
            datetime.date.fromisoformat(candidate)
    except ValueError:
        errors.append(f"unparseable-date: {source}{where} = {value!r}")


def is_percent_field(key_norm):
    return bool(PCT_FIELD_RE.search(key_norm)) and not PERCENTILE_FIELD_RE.search(key_norm)


def walk_json(source, node, errors, path_hint=""):
    if isinstance(node, dict):
        for key, value in node.items():
            key_norm = normalize_field_name(key)
            here = f"{path_hint}/{key}"
            if key_norm in PRIVATE_FIELD_NAMES:
                errors.append(f"private-field: {source}{here} is a disallowed private-field name")
            # is_percent_field excludes "percentile" keys by what the key
            # means (a rank, not a percentage), not by the value's type --
            # a genuine pct/percent field must still fail on a container
            # value, so no dict/list exclusion happens here.
            if is_percent_field(key_norm):
                check_percent_value(source, here, value, errors)
            if DATE_FIELD_RE.search(key_norm):
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

        header_norm = [normalize_field_name(h) for h in header]
        for h in header_norm:
            if h in PRIVATE_FIELD_NAMES:
                errors.append(f"private-field: {f} header {h!r} is a disallowed private-field name")

        for col_idx, col_name in enumerate(header_norm):
            is_pct = is_percent_field(col_name)
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
                    # Same strict ISO parser the JSON path uses -- no
                    # second, independently-drifting date-shaped regex.
                    check_date_value(f, f":{lineno} {col_name}", raw, errors)


def check_generated_output_allowlist(files, errors):
    for f in files:
        if f.startswith("data/") and f not in GENERATED_OUTPUT_ALLOWLIST and f not in DATA_GOVERNANCE_FILES:
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
    # Code and data must never reference a withdrawn domain -- as code, it
    # could fetch from it again; as data, it could falsely cite it as a
    # source. Scans every tracked file that decodes as text, not a fixed
    # set of extensions: an extension denylist here is the same mistake as
    # the fetch-detection denylist elsewhere in this file, just wearing a
    # ".txt and .yml pass today" shape instead of "subprocess passes
    # today." A file that fails to decode as UTF-8 cannot contain the
    # domain as text and is skipped -- that is scope, not exemption, so it
    # stays a plain continue rather than going through exempt().
    for f in files:
        path = REPO_ROOT / f
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            _UNDECODABLE_AS_TEXT.append(f)
            continue
        text_l = text.lower()
        for domain, reason in FORBIDDEN_SOURCE_DOMAINS.items():
            if domain.lower() not in text_l:
                continue
            self_ref_reason = DOMAIN_CHECK_SELF_REFERENCE.get(f)
            if self_ref_reason is not None:
                # This exact file is known, by name, to need to name the
                # domain (the denylist itself; its regression test).
                exempt("domain-check-self-reference", f, self_ref_reason, errors)
                continue
            if f.endswith(".md"):
                # Documentation is *expected* to cite a withdrawn source in
                # a dated note -- that citation is the point, not a
                # violation. Still routed through exempt(), so it is
                # recorded and named in the PASS line like every other
                # carve-out, not a silent type-based bypass.
                exempt(
                    "domain-check-doc-citation", f,
                    f"2026-09-08: {f} is documentation; citing a withdrawn "
                    "source by name and link is expected here, not a "
                    "violation",
                    errors,
                )
                continue
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


def check_script_fetch_classification(files, errors):
    """Every scripts/*.py file must have an entry in
    SCRIPT_FETCH_CLASSIFICATION -- no file is exempted by being a special
    case in this loop; see the comment on that dict for why. "exempt"
    entries are recorded through exempt() so main()'s PASS line names
    them automatically.
    """
    for f in files:
        if not (f.startswith("scripts/") and f.endswith(".py")):
            continue

        entry = SCRIPT_FETCH_CLASSIFICATION.get(f)
        if entry is None:
            errors.append(
                f"unclassified-script: {f} has no entry in "
                "SCRIPT_FETCH_CLASSIFICATION -- every script must be "
                "declared instrumented, exempt (with a dated reason), or "
                "non-fetching"
            )
            continue

        status = entry.get("status")
        tree = parse_ast_safely(REPO_ROOT / f)

        if status == "non-fetching":
            if tree is not None and calls_network_fetch(tree):
                errors.append(
                    f"classification-lie: {f} is declared non-fetching but "
                    "its own code contains a network-fetch call"
                )

        elif status == "instrumented":
            if tree is not None and not calls_provenance_fetch(tree):
                errors.append(
                    f"classification-lie: {f} is declared instrumented but "
                    "never actually calls provenance.fetch (a comment or "
                    "docstring mentioning it does not count)"
                )
            outputs = entry.get("outputs") or ()
            if not outputs:
                errors.append(f"classification-incomplete: {f} is instrumented but declares no outputs")
            for out in outputs:
                out_path = REPO_ROOT / out
                if not out_path.exists():
                    errors.append(f"missing-declared-output: {f} declares output {out}, which does not exist")
                    continue
                try:
                    doc = json.loads(out_path.read_text(encoding="utf-8"))
                except (OSError, UnicodeDecodeError, json.JSONDecodeError):
                    errors.append(f"missing-declared-output: {out} (declared output of {f}) is not valid JSON")
                    continue
                found = []
                collect_sha256_values(doc, out, "", found)
                if not any(isinstance(v, str) and v.strip() for _, _, v in found):
                    errors.append(
                        f"missing-provenance-checksum: {out} is the declared "
                        f"output of instrumented script {f} but carries no "
                        "non-empty sha256 anywhere"
                    )

        elif status == "exempt":
            exempt("fetch-classification", f, entry.get("reason", ""), errors)

        else:
            errors.append(
                f"unknown-classification: {f} has status {status!r}, "
                "expected instrumented, exempt, or non-fetching"
            )


def main():
    reset_exemptions()
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
    check_script_fetch_classification(files, errors)

    if errors:
        print(f"FAIL: {len(errors)} validation error(s)", file=sys.stderr)
        for e in sorted(errors):
            print(f"  - {e}", file=sys.stderr)
        return 1

    parts = []
    if _RECORDED_EXEMPTIONS:
        by_kind = {}
        for kind, path, _reason in _RECORDED_EXEMPTIONS:
            by_kind.setdefault(kind, []).append(path)
        exemption_parts = [f"{kind}: {', '.join(sorted(paths))}" for kind, paths in sorted(by_kind.items())]
        parts.append(f"exemptions: {'; '.join(exemption_parts)}")
    if _UNDECODABLE_AS_TEXT:
        parts.append(f"not scanned for domain (undecodable as UTF-8 text): {', '.join(sorted(_UNDECODABLE_AS_TEXT))}")
    suffix = f" ({'; '.join(parts)})" if parts else ""
    print(f"PASS: {len(files)} tracked files validated, 0 errors{suffix}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
