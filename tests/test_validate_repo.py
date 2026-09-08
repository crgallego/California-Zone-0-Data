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

    def test_self_exempt_widening_fails(self):
        original = validate_repo.FETCH_PROVENANCE_SELF_EXEMPT
        validate_repo.FETCH_PROVENANCE_SELF_EXEMPT = frozenset(
            original | {"scripts/build_sneaky.py"}
        )
        self._write(
            "scripts/build_sneaky.py",
            "import urllib.request\n"
            "def go():\n"
            "    return urllib.request.urlopen('https://example.com').read()\n",
        )
        try:
            errors = []
            validate_repo.check_script_fetch_classification(["scripts/build_sneaky.py"], errors)
            self.assertTrue(
                any("self-exempt-widened" in e for e in errors),
                f"expected self-exempt-widened, got: {errors}",
            )
            self.assertTrue(
                any("unclassified-script" in e and "build_sneaky.py" in e for e in errors),
                f"widening self-exempt must not itself grant the exemption; got: {errors}",
            )
        finally:
            validate_repo.FETCH_PROVENANCE_SELF_EXEMPT = original

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
