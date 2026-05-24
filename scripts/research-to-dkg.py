#!/usr/bin/env python3
"""
Otto → DKG Working Memory writer.

Publishes research briefs to the triad-research context graph.
Call this after researching a link to persist findings to DKG.

Usage:
  python3 research-to-dkg.py --title "Agent Memory" \\
    --source-url "https://example.com/article" \\
    --findings "Finding 1" "Finding 2" \\
    --verdict adopt \\
    [--context "Additional context string"]
"""

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path


# ── Config ─────────────────────────────────────────────────────────
DKG_CONFIG_PATH = Path(__file__).parent / ".dkg-config.json"
DKG_CONTEXT_GRAPH = "triad-research"
DKG_COLLECTION = "research-briefs"
DKG_AGENT = "otto"
DKG_MODEL = os.environ.get("HERMES_MODEL", "deepseek-v4-flash")

VALID_VERDICTS = {"adopt", "learn", "watch", "ignore"}


def load_config():
    """Load DKG auth config from file or env."""
    config = {}
    if DKG_CONFIG_PATH.exists():
        config = json.loads(DKG_CONFIG_PATH.read_text())
    auth_token = config.get("auth_token", os.environ.get("DKG_AUTH_TOKEN", ""))
    node_url = config.get("dkg_node_url", "http://127.0.0.1:9200")
    return auth_token, node_url


def build_nquads(ual, title, source_url, findings, verdict, context, source_refs):
    """Build N-Quads representation of a research brief."""
    timestamp = datetime.now(timezone.utc).isoformat()
    findings_str = " | ".join(findings) if findings else ""
    source_refs_str = " | ".join(source_refs) if source_refs else source_url
    context_str = (context or "").replace('"', '\\"')

    safe_title = (title or source_url[:60]).replace('"', '\\"')

    # If there's a source_ref pointing to a Cleo asset, include bidirectional link
    cross_ref_quads = ""
    if source_refs:
        for ref in source_refs:
            if ref.startswith("did:dkg:working:"):
                cross_ref_quads += (
                    f'<{ual}> <http://triad/ns/researchedFrom> <{ref}> .\n'
                )

    nquads = f"""<{ual}> <http://www.w3.org/1999/02/22-rdf-syntax-ns#type> <http://triad/ns/KnowledgeAsset> .
<{ual}> <http://triad/ns/collection> "{DKG_COLLECTION}" .
<{ual}> <http://triad/ns/title> "{safe_title}" .
<{ual}> <http://triad/ns/sourceUrl> "{source_url}" .
<{ual}> <http://triad/ns/keyFindings> "{findings_str}" .
<{ual}> <http://triad/ns/verdict> "{verdict}" .
<{ual}> <http://triad/ns/context> "{context_str}" .
<{ual}> <http://triad/ns/sourceRefs> "{source_refs_str}" .
<{ual}> <http://triad/ns/status> "draft" .
<{ual}> <http://triad/ns/provenanceAgent> "{DKG_AGENT}" .
<{ual}> <http://triad/ns/provenanceModel> "{DKG_MODEL}" .
<{ual}> <http://triad/ns/provenanceTimestamp> "{timestamp}" .
{cross_ref_quads}"""
    return nquads


def write_to_dkg(nquads, auth_token):
    """Write N-Quads to DKG Working Memory via dkg workspace write."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.nq', delete=False) as f:
        f.write(nquads)
        tmp_path = f.name

    try:
        result = subprocess.run(
            ["dkg", "workspace", "write", DKG_CONTEXT_GRAPH, "-f", tmp_path],
            capture_output=True, text=True, timeout=15,
            env={**os.environ, "DKG_AUTH_TOKEN": auth_token}
        )
        return result
    finally:
        os.unlink(tmp_path)


def main():
    parser = argparse.ArgumentParser(
        description="Otto: Write research brief to DKG Working Memory"
    )
    parser.add_argument("--title", required=True, help="Research topic title")
    parser.add_argument("--source-url", required=True, help="Primary source URL")
    parser.add_argument("--findings", nargs="+", default=[],
                        help="Key findings (one per arg)")
    parser.add_argument("--verdict", required=True,
                        choices=sorted(VALID_VERDICTS),
                        help="Research verdict")
    parser.add_argument("--context", default="", help="Additional context/analysis")
    parser.add_argument("--source-refs", nargs="*", default=[],
                        help="DKG UAL references (e.g., from Cleo)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print N-Quads without writing")
    parser.add_argument("--json", action="store_true",
                        help="Output machine-readable JSON")

    args = parser.parse_args()

    if args.verdict not in VALID_VERDICTS:
        print(f"ERROR: Invalid verdict '{args.verdict}'. Use: {', '.join(sorted(VALID_VERDICTS))}", file=sys.stderr)
        sys.exit(1)

    auth_token, node_url = load_config()
    if not auth_token:
        print("ERROR: No DKG auth token. Set DKG_AUTH_TOKEN env or create .dkg-config.json", file=sys.stderr)
        sys.exit(1)

    # Generate UAL
    asset_id = hashlib.sha256(args.source_url.encode()).hexdigest()[:16]
    ual = f"did:dkg:working:{asset_id}"

    # Build N-Quads
    nquads = build_nquads(
        ual, args.title, args.source_url,
        args.findings, args.verdict, args.context,
        args.source_refs
    )

    if args.dry_run:
        print(nquads)
        return

    # Write to DKG
    result = write_to_dkg(nquads, auth_token)

    if result.returncode == 0:
        name_match = re.search(r'Assertion name:\s+(\S+)', result.stdout)
        assertion_name = name_match.group(1) if name_match else "unknown"

        if args.json:
            print(json.dumps({
                "status": "ok",
                "ual": ual,
                "assertion": assertion_name,
                "collection": DKG_COLLECTION
            }))
        else:
            print(f"✅ DKG: {ual}")
            print(f"   Assertion: {assertion_name}")
            print(f"   Collection: {DKG_COLLECTION}")
    else:
        if args.json:
            print(json.dumps({"status": "error", "message": result.stderr[:200]}))
        else:
            print(f"❌ DKG write failed: {result.stderr[:200]}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
