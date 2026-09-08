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
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REAL_SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"


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

if __name__ == "__main__":
    unittest.main()
