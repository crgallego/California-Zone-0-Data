#!/usr/bin/env python3
"""Regression tests for scripts/validate_repo.py.

One test per hole an independent review actually found and proved with an
injected case -- not a general test framework for the validator. Each test
builds the minimal synthetic tree needed to reproduce its specific finding,
points validate_repo.REPO_ROOT at it, and asserts the check that should
catch it does. Every one of these failed to catch its case before the fix
that accompanies this file; they exist so a future change (including an
accidental one, like a stray ``git checkout --`` undoing a fix) cannot
silently remove the catch and have every other check still report PASS,
because a check that is not there cannot fail.

Runs with the validator: ``python3 -m unittest tests/test_validate_repo.py``.
Stdlib only, no network access.
"""
import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))
import validate_repo  # noqa: E402


class ValidateRepoRegressionTests(unittest.TestCase):
    def setUp(self):
        self._real_repo_root = validate_repo.REPO_ROOT
        self._tmp = tempfile.mkdtemp(prefix="validate_repo_test_")
        validate_repo.REPO_ROOT = Path(self._tmp)

    def tearDown(self):
        validate_repo.REPO_ROOT = self._real_repo_root
        shutil.rmtree(self._tmp, ignore_errors=True)

    def _write(self, rel_path, content):
        path = validate_repo.REPO_ROOT / rel_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return rel_path

    # -- finding 1: an instrumented script's output can lose its checksum
    #    and check_provenance_checksums stays silent, since "non-empty when
    #    present" is satisfied by absence --------------------------------
    def test_instrumented_output_missing_checksum_fails(self):
        self._write(
            "data/cdi_policy_counts_state.json",
            json.dumps({"source": {"publisher": "CDI"}}),  # no county_pdf_provenance at all
        )
        errors = []
        exempt = validate_repo.check_script_fetch_classification(
            ["scripts/build_cdi_policy_counts.py"], errors
        )
        self.assertTrue(
            any("missing-provenance-checksum" in e for e in errors),
            f"expected a missing-provenance-checksum error, got: {errors}",
        )

    # -- finding 2: "uses provenance.fetch" as a substring match is
    #    satisfied by a comment, and a bare `urlopen` (import-alias style)
    #    was invisible to the old marker list -----------------------------
    def test_unclassified_new_script_fails_regardless_of_fetch_style(self):
        self._write(
            "scripts/build_new_fetch.py",
            "import urllib.request\n"
            "# later we will switch this to provenance.fetch\n"
            "def go():\n"
            "    return urllib.request.urlopen('https://example.com').read()\n",
        )
        errors = []
        validate_repo.check_script_fetch_classification(["scripts/build_new_fetch.py"], errors)
        self.assertTrue(
            any("unclassified-script" in e and "build_new_fetch.py" in e for e in errors),
            f"expected unclassified-script, got: {errors}",
        )

    def test_import_alias_urlopen_is_not_silently_non_fetching(self):
        self._write(
            "scripts/build_alias_fetch.py",
            "from urllib.request import urlopen\n"
            "def go():\n"
            "    return urlopen('https://example.com').read()\n",
        )
        # If a future change ever mis-classifies this as non-fetching, the
        # AST liar-catcher (not a text search) must still catch it.
        validate_repo.SCRIPT_FETCH_CLASSIFICATION["scripts/build_alias_fetch.py"] = {"status": "non-fetching"}
        try:
            errors = []
            validate_repo.check_script_fetch_classification(["scripts/build_alias_fetch.py"], errors)
            self.assertTrue(
                any("classification-lie" in e for e in errors),
                f"expected a classification-lie error, got: {errors}",
            )
        finally:
            del validate_repo.SCRIPT_FETCH_CLASSIFICATION["scripts/build_alias_fetch.py"]

    # -- finding 3: an exemption's "reason" was a membership check, not a
    #    dated policy -- empty and undated strings both passed ------------
    def test_empty_or_undated_exempt_reason_fails(self):
        validate_repo.SCRIPT_FETCH_CLASSIFICATION["scripts/build_empty_reason.py"] = {
            "status": "exempt", "reason": "",
        }
        validate_repo.SCRIPT_FETCH_CLASSIFICATION["scripts/build_undated.py"] = {
            "status": "exempt", "reason": "ok",
        }
        self._write("scripts/build_empty_reason.py", "def go(): pass\n")
        self._write("scripts/build_undated.py", "def go(): pass\n")
        try:
            errors = []
            validate_repo.check_script_fetch_classification(
                ["scripts/build_empty_reason.py", "scripts/build_undated.py"], errors
            )
            self.assertTrue(
                any("exception-not-dated" in e and "build_empty_reason.py" in e for e in errors),
                f"expected exception-not-dated for the empty reason, got: {errors}",
            )
            self.assertTrue(
                any("exception-not-dated" in e and "build_undated.py" in e for e in errors),
                f"expected exception-not-dated for the undated reason, got: {errors}",
            )
        finally:
            del validate_repo.SCRIPT_FETCH_CLASSIFICATION["scripts/build_empty_reason.py"]
            del validate_repo.SCRIPT_FETCH_CLASSIFICATION["scripts/build_undated.py"]

    # -- finding 3, second instance: an earlier fix checked a named
    #    "frozen" constant, but a second, unwatched literal a few lines
    #    away was what actually granted the skip -- widening that second
    #    literal (not the constant) silently exempted any script, reopening
    #    finding 1. The fix removed the special case entirely: there is now
    #    exactly one mechanism (SCRIPT_FETCH_CLASSIFICATION), so there is no
    #    constant to watch and no second literal to find. These tests
    #    assert on validator *output* for a constructed tree, not on the
    #    value of any module-level constant -- "is this dict still equal to
    #    that literal" only proves a variable has not moved; it was never
    #    the question that mattered. -------------------------------------
    def test_no_fetch_script_can_pass_unclassified_no_matter_its_name(self):
        # Stands in for "someone finds a third way to skip classification":
        # whatever the mechanism, an unclassified script that actually
        # fetches must fail. This name was never special-cased by anything
        # in this file, which is the point.
        self._write(
            "scripts/build_whatever_new_script_shows_up.py",
            "import urllib.request\n"
            "def go():\n"
            "    return urllib.request.urlopen('https://example.com').read()\n",
        )
        errors = []
        validate_repo.check_script_fetch_classification(
            ["scripts/build_whatever_new_script_shows_up.py"], errors
        )
        self.assertTrue(
            any(
                "unclassified-script" in e and "build_whatever_new_script_shows_up.py" in e
                for e in errors
            ),
            f"expected unclassified-script, got: {errors}",
        )

    def test_fetch_helper_and_validator_pass_only_through_real_classification(self):
        # Copies the actual scripts/provenance.py and scripts/validate_repo.py
        # source into the synthetic tree and runs the real check against
        # them -- proving they clear the gate because they are correctly
        # classified in SCRIPT_FETCH_CLASSIFICATION (provenance.py: exempt,
        # it is the helper; validate_repo.py: non-fetching, confirmed by
        # the same AST check every other script gets), not because either
        # filename is special-cased in the loop.
        real_scripts_dir = Path(validate_repo.__file__).resolve().parent
        for name in ("provenance.py", "validate_repo.py"):
            self._write(f"scripts/{name}", (real_scripts_dir / name).read_text(encoding="utf-8"))
        errors = []
        exempt = validate_repo.check_script_fetch_classification(
            ["scripts/provenance.py", "scripts/validate_repo.py"], errors
        )
        self.assertEqual(errors, [], f"expected no errors, got: {errors}")
        self.assertIn("scripts/provenance.py", exempt)

    # -- finding 4: the forbidden-domain check was case-sensitive and
    #    scanned only .py files, missing an uppercase spelling and a data
    #    file citing the domain as if it were a legitimate source ---------
    def test_uppercase_domain_reference_fails(self):
        self._write("scripts/build_upper_domain.py", "# https://www.CFPNET.COM/oops\n")
        errors = []
        validate_repo.check_forbidden_source_domains(["scripts/build_upper_domain.py"], errors)
        self.assertTrue(
            any("forbidden-source-domain" in e for e in errors),
            f"expected forbidden-source-domain for uppercase domain, got: {errors}",
        )

    def test_domain_reference_inside_data_json_fails(self):
        self._write(
            "data/cdi_policy_counts_state.json",
            json.dumps({"source": {"page": "https://www.cfpnet.com/sneaky"}}),
        )
        errors = []
        validate_repo.check_forbidden_source_domains(["data/cdi_policy_counts_state.json"], errors)
        self.assertTrue(
            any("forbidden-source-domain" in e for e in errors),
            f"expected forbidden-source-domain for the data-file reference, got: {errors}",
        )

    def test_domain_self_reference_is_exempt_only_by_exact_name_not_by_type(self):
        # The domain check's own tooling (validate_repo.py, its test file)
        # must reference the withdrawn domain without failing. A third
        # .py file with the identical content must still fail -- the
        # exemption is scoped to those exact two filenames in
        # DOMAIN_CHECK_SELF_REFERENCE, not to "any script."
        content = "FORBIDDEN_SOURCE_DOMAINS = {'cfpnet.com': 'withdrawn'}\n"
        self._write("scripts/validate_repo.py", content)
        self._write("scripts/some_other_script.py", content)
        errors = []
        validate_repo.check_forbidden_source_domains(
            ["scripts/validate_repo.py", "scripts/some_other_script.py"], errors
        )
        self.assertTrue(
            any("some_other_script.py" in e for e in errors),
            f"expected the unrelated script to fail, got: {errors}",
        )
        self.assertFalse(
            any("scripts/validate_repo.py" in e for e in errors),
            f"validate_repo.py should be exempt by name, got: {errors}",
        )

    def test_markdown_documentation_may_cite_the_domain_but_a_script_may_not(self):
        # The .md carve-out is a type-based exemption, not a specific-file
        # one -- proving the boundary sits exactly at file extension, not
        # somewhere broader, since the identical content in a script
        # (which is in scope for this check) must still fail.
        content = "# See https://www.cfpnet.com/key-statistics-data/ for the withdrawn figures.\n"
        self._write("CHANGELOG.md", content)
        self._write("scripts/unrelated_script.py", content)
        errors = []
        validate_repo.check_forbidden_source_domains(["CHANGELOG.md", "scripts/unrelated_script.py"], errors)
        self.assertFalse(
            any("CHANGELOG.md" in e for e in errors),
            f"a .md file should be exempt, got: {errors}",
        )
        self.assertTrue(
            any("unrelated_script.py" in e for e in errors),
            f"a script with the same content should still fail, got: {errors}",
        )

    # -- finding 5: the forbidden-path list was copied from .gitignore's
    #    patterns rather than derived from what the C-13 commit actually
    #    shipped, so it never named tests/test_c13_locator.py -------------
    def test_c13_test_fixture_path_is_forbidden(self):
        self._write("tests/test_c13_locator.py", "def test_nothing(): pass\n")
        errors = []
        validate_repo.check_forbidden_paths(["tests/test_c13_locator.py"], errors)
        self.assertTrue(
            any("forbidden-path" in e and "test_c13_locator.py" in e for e in errors),
            f"expected forbidden-path for the C-13 test fixture, got: {errors}",
        )


if __name__ == "__main__":
    unittest.main()
