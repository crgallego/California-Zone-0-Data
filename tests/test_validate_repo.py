#!/usr/bin/env python3
"""End-to-end regression tests for scripts/validate_repo.py.

Every case builds a real, throwaway git repository containing a COPY of
the validator (and its provenance.py helper), the fixture files for that
case, runs ``git add``, then invokes ``python3 scripts/validate_repo.py``
as a real subprocess inside that repository -- the same entry point CI
runs, with a real exit code and real stdout/stderr as the assertions.

This is deliberate, not incidental. An earlier version of this suite
called check_* functions directly, and every one of those tests kept
passing when a check's call site was commented out of main() -- calling
a function proves the function works, not that the entry point still
calls it. It also could not express "the exemption rules in this file
were edited," since an in-process monkeypatch of a Python constant is not
what a changed source file looks like. Building a real fixture tree and
running the real script is the only way to make both of those failure
shapes visible to a test.

One test per hole an independent review found and proved with an injected
case, plus the structural cases (entry-point wiring, sibling-name
patterns) that direct function calls could not express. Not a general
test framework for the validator.

Runs with the validator: ``python3 -m unittest tests/test_validate_repo.py``.
Stdlib only, no network access (subprocess and git are local-only).
"""
import ast
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REAL_SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"


class ValidatorWiringTests(unittest.TestCase):
    """Static check, not a fixture run: every check_* function defined in
    validate_repo.py must actually be called from main(). This is the
    permanent version of a proof done once by hand -- running the e2e
    suite against a copy of the validator with one check's call site
    commented out, and watching tests fail. That proved today's suite is
    sensitive to today's unwiring; it does not keep a *future* unwiring
    from passing silently if nobody repeats the experiment. Parsing
    main()'s own body for what it actually calls does not need repeating
    -- it runs every time this file runs.
    """

    def test_every_check_function_is_reachable_from_main(self):
        # Reachability, not "is a direct child of main()": some check_*
        # functions are top-level entry points main() calls directly
        # (check_json_files), and some are helpers a top-level check calls
        # internally (check_percent_value, called from check_csv_files and
        # from walk_json). Both must trace back to main() through some
        # call chain, or the function is either unwired or dead code --
        # either way, a check that cannot be reached from the entry point
        # is exactly the failure mode this test exists to catch.
        source = (REAL_SCRIPTS_DIR / "validate_repo.py").read_text(encoding="utf-8")
        tree = ast.parse(source, filename="validate_repo.py")

        defined_checks = set()
        call_graph = {}  # function name -> set of names it calls
        for node in tree.body:
            if isinstance(node, ast.FunctionDef):
                if node.name.startswith("check_"):
                    defined_checks.add(node.name)
                calls = set()
                for inner in ast.walk(node):
                    if isinstance(inner, ast.Call) and isinstance(inner.func, ast.Name):
                        calls.add(inner.func.id)
                call_graph[node.name] = calls

        self.assertIn("main", call_graph, "validate_repo.py must define main()")
        self.assertTrue(defined_checks, "expected at least one check_* function")

        reachable = set()
        frontier = ["main"]
        while frontier:
            name = frontier.pop()
            if name in reachable:
                continue
            reachable.add(name)
            frontier.extend(call_graph.get(name, ()))

        unreachable = defined_checks - reachable
        self.assertEqual(
            unreachable, set(),
            f"check_* function(s) defined but not reachable from main() "
            f"through any call chain: {sorted(unreachable)}",
        )


class ValidatorEndToEndTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.mkdtemp(prefix="validate_repo_e2e_")
        self.repo = Path(self._tmp)
        subprocess.run(["git", "init", "-q"], cwd=self.repo, check=True)
        (self.repo / "scripts").mkdir(parents=True, exist_ok=True)
        shutil.copy(REAL_SCRIPTS_DIR / "validate_repo.py", self.repo / "scripts" / "validate_repo.py")
        shutil.copy(REAL_SCRIPTS_DIR / "provenance.py", self.repo / "scripts" / "provenance.py")

    def tearDown(self):
        shutil.rmtree(self._tmp, ignore_errors=True)

    def write(self, rel_path, content):
        path = self.repo / rel_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    def edit_validator_source(self, old, new, count=1):
        """Simulate someone editing scripts/validate_repo.py itself inside
        the fixture repo -- the only way to express "a constant or
        mechanism in this file was changed," since an in-process
        monkeypatch of the imported module does not represent that.
        """
        vpath = self.repo / "scripts" / "validate_repo.py"
        text = vpath.read_text(encoding="utf-8")
        new_text = text.replace(old, new, count)
        self.assertNotEqual(new_text, text, f"edit did not match anything: {old!r}")
        vpath.write_text(new_text, encoding="utf-8")

    def run_validator(self):
        subprocess.run(["git", "add", "-A"], cwd=self.repo, check=True)
        return subprocess.run(
            [sys.executable, "scripts/validate_repo.py"],
            cwd=self.repo, capture_output=True, text=True,
        )

    def assertFails(self, result, needle):
        combined = result.stdout + result.stderr
        self.assertNotEqual(result.returncode, 0, f"expected failure, got PASS: {combined}")
        self.assertIn(needle, combined, f"expected {needle!r} in output: {combined}")

    def assertPasses(self, result):
        combined = result.stdout + result.stderr
        self.assertEqual(result.returncode, 0, f"expected PASS, got: {combined}")
        return combined

    # -- finding 1: an instrumented script's output can lose its checksum,
    #    and the check stayed silent since "non-empty when present" is
    #    satisfied by absence -----------------------------------------
    def test_instrumented_output_missing_checksum_fails(self):
        # SCRIPT_FETCH_CLASSIFICATION only evaluates a script that is
        # actually tracked in this fixture, so the "instrumented" entry
        # for build_cdi_policy_counts.py needs the file present (any
        # content -- classification keys off the path in `files`, not
        # what the script does) to exercise its output-checksum check.
        self.write("scripts/build_cdi_policy_counts.py", "import provenance\ndef go(): pass\n")
        self.write("data/cdi_policy_counts_state.json", '{"source": {"publisher": "CDI"}}')
        result = self.run_validator()
        self.assertFails(result, "missing-provenance-checksum")

    # -- finding 2: "uses provenance.fetch" was a substring match; a
    #    comment or an import-alias fetch style both slipped through -----
    def test_unclassified_script_fails_regardless_of_fetch_style(self):
        self.write(
            "scripts/build_new_fetch.py",
            "import urllib.request\n"
            "# later we will switch this to provenance.fetch\n"
            "def go():\n"
            "    return urllib.request.urlopen('https://example.com').read()\n",
        )
        result = self.run_validator()
        self.assertFails(result, "unclassified-script")
        self.assertIn("build_new_fetch.py", result.stdout + result.stderr)

    def test_import_alias_urlopen_is_not_silently_non_fetching(self):
        self.write(
            "scripts/build_alias_fetch.py",
            "from urllib.request import urlopen\n"
            "def go():\n"
            "    return urlopen('https://example.com').read()\n",
        )
        self.edit_validator_source(
            'SCRIPT_FETCH_CLASSIFICATION = {',
            'SCRIPT_FETCH_CLASSIFICATION = {\n'
            '    "scripts/build_alias_fetch.py": {"status": "non-fetching"},',
        )
        result = self.run_validator()
        self.assertFails(result, "classification-lie")

    # -- finding 3: an exemption's "reason" was a membership check, never
    #    read -- empty and undated strings both passed -------------------
    def test_empty_or_undated_fetch_exemption_reason_fails(self):
        self.write("scripts/build_empty_reason.py", "def go(): pass\n")
        self.write("scripts/build_undated.py", "def go(): pass\n")
        self.edit_validator_source(
            'SCRIPT_FETCH_CLASSIFICATION = {',
            'SCRIPT_FETCH_CLASSIFICATION = {\n'
            '    "scripts/build_empty_reason.py": {"status": "exempt", "reason": ""},\n'
            '    "scripts/build_undated.py": {"status": "exempt", "reason": "ok"},',
        )
        result = self.run_validator()
        combined = result.stdout + result.stderr
        self.assertFails(result, "exemption-not-dated")
        self.assertIn("build_empty_reason.py", combined)
        self.assertIn("build_undated.py", combined)

    # -- finding 3, second instance: a "frozen" self-exempt constant was
    #    watched by a test, but a second, unwatched literal a few lines
    #    away was what actually granted the skip. Fixed by deleting the
    #    special case entirely: every script, including the fetch helper
    #    and the validator, earns clearance through the one classification
    #    dict. A never-special-cased fetch script must still fail. ------
    def test_no_fetch_script_passes_by_special_case_no_matter_its_name(self):
        self.write(
            "scripts/build_whatever_new_script_shows_up.py",
            "import urllib.request\n"
            "def go():\n"
            "    return urllib.request.urlopen('https://example.com').read()\n",
        )
        result = self.run_validator()
        self.assertFails(result, "unclassified-script")
        self.assertIn("build_whatever_new_script_shows_up.py", result.stdout + result.stderr)

    def test_fetch_helper_and_validator_clear_only_through_classification(self):
        # The real provenance.py and validate_repo.py, unmodified, must
        # clear the gate and be named in the PASS line -- through
        # SCRIPT_FETCH_CLASSIFICATION, not a special case.
        result = self.run_validator()
        combined = self.assertPasses(result)
        self.assertIn("scripts/provenance.py", combined)

    # -- finding 3, domain-check instance: DOMAIN_CHECK_SELF_REFERENCE's
    #    reason values were never read, and the PASS line did not name
    #    domain exemptions, so a widening was invisible -------------------
    def test_empty_or_undated_domain_exemption_reason_fails(self):
        self.edit_validator_source(
            '"tests/test_validate_repo.py": "2026-09-08: regression-tests the domain denylist with literal fixtures",',
            '"tests/test_validate_repo.py": "2026-09-08: regression-tests the domain denylist with literal fixtures",\n'
            '    "scripts/build_widened.py": "",',
        )
        self.write("scripts/build_widened.py", "# cfpnet.com\n")
        result = self.run_validator()
        self.assertFails(result, "exemption-not-dated")

    def test_domain_self_reference_widening_to_unrelated_file_still_fails(self):
        # Grok's exact case: widen DOMAIN_CHECK_SELF_REFERENCE to an
        # unrelated file with a throwaway reason, and append the domain to
        # that file. Must fail on the reason, not pass silently.
        self.edit_validator_source(
            '"tests/test_validate_repo.py": "2026-09-08: regression-tests the domain denylist with literal fixtures",',
            '"tests/test_validate_repo.py": "2026-09-08: regression-tests the domain denylist with literal fixtures",\n'
            '    "scripts/build_housing_by_fhsz.py": "ok",',
        )
        self.write("scripts/build_housing_by_fhsz.py", "# https://www.CFPNET.COM/oops\n")
        result = self.run_validator()
        self.assertFails(result, "exemption-not-dated")
        self.assertIn("build_housing_by_fhsz.py", result.stdout + result.stderr)

    def test_uppercase_domain_reference_fails(self):
        self.write("scripts/build_upper_domain.py", "# https://www.CFPNET.COM/oops\n")
        result = self.run_validator()
        self.assertFails(result, "forbidden-source-domain")

    def test_domain_reference_inside_data_json_fails(self):
        self.write(
            "data/cdi_policy_counts_state.json",
            '{"source": {"page": "https://www.cfpnet.com/sneaky"}}',
        )
        result = self.run_validator()
        self.assertFails(result, "forbidden-source-domain")

    def test_domain_reference_in_a_text_file_of_any_extension_fails(self):
        # The scan used to be an extension allowlist (.py, data/*.json/csv/
        # tsv); a plain tracked .txt file with the domain passed. The scan
        # is now every tracked file that decodes as text.
        self.write("NOTES.txt", "See https://www.cfpnet.com/key-statistics-data/\n")
        result = self.run_validator()
        self.assertFails(result, "forbidden-source-domain")

    def test_non_utf8_file_is_named_not_silently_skipped(self):
        # Established empirically: a Latin-1-encoded file with one stray
        # non-ASCII byte carries the domain string right past the scan
        # (it cannot decode as UTF-8, so the scan cannot see inside it)
        # without tripping any other check either. That must still be
        # visible in a passing run, not just absent from the error list.
        (self.repo / "NOTES.txt").write_bytes(
            "# cfpnet.com note r\xe9sum\xe9\n".encode("latin-1")
        )
        result = self.run_validator()
        combined = self.assertPasses(result)
        self.assertIn("NOTES.txt", combined)
        self.assertIn("undecodable", combined)
        self.assertIn("NOTES.txt", result.stdout + result.stderr)

    def test_markdown_documentation_may_cite_the_domain_but_a_script_may_not(self):
        content = "See https://www.cfpnet.com/key-statistics-data/ for the withdrawn figures.\n"
        self.write("CHANGELOG.md", content)
        self.write("scripts/unrelated_script.py", "# " + content)
        result = self.run_validator()
        combined = result.stdout + result.stderr
        self.assertFails(result, "forbidden-source-domain")
        self.assertIn("unrelated_script.py", combined)
        self.assertNotIn("forbidden-source-domain: CHANGELOG.md", combined)

    # -- finding 5: the forbidden-path list was copied from .gitignore's
    #    patterns, so it never named the sibling test file that the C-13
    #    commit actually shipped -----------------------------------------
    def test_c13_exact_fixture_path_is_forbidden(self):
        self.write("tests/test_c13_locator.py", "def test_nothing(): pass\n")
        result = self.run_validator()
        self.assertFails(result, "forbidden-path")
        self.assertIn("test_c13_locator.py", result.stdout + result.stderr)

    def test_c13_sibling_named_file_is_forbidden_by_pattern_not_just_exact_list(self):
        # Not the exact file from commit 84eb9b8 -- a sibling name that
        # only the ^tests/test_c13_ pattern rule catches, proving the
        # pattern works independently of FORBIDDEN_EXACT_PATHS.
        self.write("tests/test_c13_other.py", "def test_nothing(): pass\n")
        result = self.run_validator()
        self.assertFails(result, "forbidden-path")
        self.assertIn("test_c13_other.py", result.stdout + result.stderr)

    # -- Luna's PR #5 HOLD, finding 1: network-fetch classification only
    #    recognized urlopen/requests.get,post/http.client -- a classified
    #    non-fetching script could still fetch via urllib.request.urlretrieve
    #    (or any alias/import form of an already-listed call) without
    #    tripping the liar-catcher --------------------------------------
    def test_classified_non_fetching_script_using_urlretrieve_is_a_lie(self):
        self.write(
            "scripts/build_retrieve_fetch.py",
            "import urllib.request\n"
            "def go():\n"
            "    urllib.request.urlretrieve('https://example.com', '/tmp/x')\n",
        )
        self.edit_validator_source(
            'SCRIPT_FETCH_CLASSIFICATION = {',
            'SCRIPT_FETCH_CLASSIFICATION = {\n'
            '    "scripts/build_retrieve_fetch.py": {"status": "non-fetching"},',
        )
        result = self.run_validator()
        self.assertFails(result, "classification-lie")
        self.assertIn("build_retrieve_fetch.py", result.stdout + result.stderr)

    def test_classified_non_fetching_script_using_aliased_urlretrieve_import_is_a_lie(self):
        # `from urllib.request import urlretrieve as get_file` -- a fresh
        # alias of an already-recognized call, not a new spelling that
        # needed its own denylist entry.
        self.write(
            "scripts/build_aliased_retrieve.py",
            "from urllib.request import urlretrieve as get_file\n"
            "def go():\n"
            "    get_file('https://example.com', '/tmp/x')\n",
        )
        self.edit_validator_source(
            'SCRIPT_FETCH_CLASSIFICATION = {',
            'SCRIPT_FETCH_CLASSIFICATION = {\n'
            '    "scripts/build_aliased_retrieve.py": {"status": "non-fetching"},',
        )
        result = self.run_validator()
        self.assertFails(result, "classification-lie")
        self.assertIn("build_aliased_retrieve.py", result.stdout + result.stderr)

    # -- Luna's PR #5 HOLD, finding 2: the private-field-name denylist did
    #    not include address/apn/license_number, so an allowlisted JSON
    #    output could carry property/contractor-identifying fields --------
    def test_property_and_licence_identifying_json_fields_fail(self):
        self.write(
            "data/fence_attachment_dins.json",
            '{"nested": {"address": "1 Main St", "apn": "123-45-678", '
            '"license_number": "C13-0000001"}}',
        )
        result = self.run_validator()
        combined = result.stdout + result.stderr
        self.assertFails(result, "private-field")
        self.assertIn("address", combined)
        self.assertIn("apn", combined)
        self.assertIn("license_number", combined)

    # -- Luna's PR #5 HOLD, finding 3: JSON percent/date checks only ran
    #    when the value was already the right type, so a wrong-typed value
    #    silently skipped the check instead of failing it -----------------
    def test_json_non_numeric_percent_value_fails(self):
        self.write("data/population_by_fhsz_state.json", '{"pct_value": "not-a-number"}')
        result = self.run_validator()
        self.assertFails(result, "percent-not-numeric")

    def test_json_date_like_string_that_is_not_a_real_date_fails(self):
        self.write("data/population_by_fhsz_state.json", '{"retrieved": "not-a-date-2026"}')
        result = self.run_validator()
        self.assertFails(result, "unparseable-date")

    def test_json_numeric_date_field_fails(self):
        self.write("data/population_by_fhsz_state.json", '{"date_submitted": 20260909}')
        result = self.run_validator()
        self.assertFails(result, "unparseable-date")

    # -- guard against the fix to finding 3 introducing a new false
    #    failure: PCT_FIELD_RE also matches "percentile", and the real CDI
    #    output has a percentile-named key whose value is a nested object,
    #    not a scalar -- that must still pass -----------------------------
    def test_percentile_named_object_field_is_not_treated_as_a_percent_value(self):
        self.write(
            "data/cdi_policy_counts_state.json",
            '{"counties_at_or_above_50th_percentile_high_fire_risk": {"Los Angeles": true}}',
        )
        result = self.run_validator()
        self.assertPasses(result)

if __name__ == "__main__":
    unittest.main()
