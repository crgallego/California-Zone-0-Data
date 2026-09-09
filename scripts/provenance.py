"""Shared fetch-with-checksum helper.

Every build script that pulls from the network should record, for each
source it fetches, the exact URL, a retrieval timestamp, and the sha256 of
the bytes it received -- not just "we downloaded something from here on
this date." Two runs agreeing is stability, not proof that the source
hasn't changed; a checksum is the difference between the two.

``fetch`` performs the request and returns the raw bytes plus that
provenance record. ``check_unchanged`` compares a freshly computed
checksum against the one recorded in a previously-generated output file,
and exits loudly on a mismatch rather than letting the build silently
absorb a changed upstream source. A source change is a fact a person
should see and decide about -- it may be a correction worth publishing,
or a source that can no longer be trusted -- not something a re-run
quietly folds in.
"""
import hashlib
import json
import os
import sys
import urllib.request
from datetime import datetime, timezone


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def utcnow_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def fetch(url, *, data=None, headers=None, timeout=300):
    """Fetch ``url`` and return ``(raw_bytes, provenance_dict)``.

    ``provenance_dict`` has ``url``, ``retrieved`` (UTC, second precision),
    and ``sha256`` of exactly the bytes returned. This function does not
    compare against any prior value -- call ``check_unchanged`` for that.
    """
    req = urllib.request.Request(url, data=data, headers=headers or {})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        raw = r.read()
    return raw, {
        "url": url,
        "retrieved": utcnow_iso(),
        "sha256": sha256_bytes(raw),
    }


def check_unchanged(provenance, recorded_path, key_path):
    """Compare a freshly fetched ``provenance["sha256"]`` against the value
    recorded in ``recorded_path`` (a previously-generated JSON output) the
    last time this exact source was built.

    ``key_path`` is a sequence of keys locating the prior provenance block
    inside that JSON document, e.g. ``("source",)`` for a top-level
    ``source`` object, or ``("sources", "county_pdf")`` for a nested one.

    Does nothing on a first run (no recorded file yet) or if the prior
    file has no matching block or no recorded checksum -- there is nothing
    to compare against. Exits the process on a mismatch.
    """
    if not os.path.exists(recorded_path):
        return
    try:
        with open(recorded_path, encoding="utf-8") as f:
            prior = json.load(f)
    except (OSError, json.JSONDecodeError):
        return

    block = prior
    for key in key_path:
        if not isinstance(block, dict):
            return
        block = block.get(key)
    if not isinstance(block, dict):
        return

    prior_sha = block.get("sha256")
    if prior_sha and prior_sha != provenance["sha256"]:
        sys.exit(
            f"provenance mismatch: {provenance['url']}\n"
            f"  previously recorded sha256: {prior_sha}\n"
            f"  just fetched sha256:        {provenance['sha256']}\n"
            "The upstream source has changed since the last build. This "
            "may be a correction worth publishing, or a source that can "
            "no longer be trusted -- a person decides, not this script. "
            f"Delete or update {recorded_path} to accept the new source "
            "and re-run, or investigate the change first."
        )
