#!/usr/bin/env python3
"""
Vrilnius → DKG Working Memory writer.

Captures build artifacts from OpenClaw workspace and writes them
to the triad-research context graph as Knowledge Assets.

Usage:
  python3 artifact-to-dkg.py --type code --project "triad-demo" \\
    --summary "Built DKG artifact capture tool" \\
    --path "/home/otto/code/triad/vrilnius/artifact-to-dkg.py" \\
    [--based-on "did:dkg:working:50765dbd0bcd9ffa"]
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
DKG_CONFIG_PATH = Path(os.path.expanduser("~/.hermes/scripts/.dkg-config.json"))
DKG_CONTEXT_GRAPH = "triad-research"
DKG_COLLECTION = "build-artifacts"
DKG_AGENT = "vrilnius"
DKG_MODEL = "gpt-4o"
DKG_CLI = "dkg"

VALID_TYPES = {"code", "spec", "config", "doc"}


def load_config():
    """Load DKG auth config from file or env."""
    config = {}
    if DKG_CONFIG_PATH.exists():
        config = json.loads(DKG_CONFIG_PATH.read_text())
    return (
        config.get("auth_token", os.environ.get("DKG_AUTH_TOKEN", "")),
        config.get("dkg_node_url", "http://127.0.0.1:9200"),
    )


def resolve_path(path_str):
    """Resolve path, supporting ~ expansion."""
    return str(Path(os.path.expanduser(path_str)).resolve())


def build_nquads(ual, artifact_type, project, summary, path_str, based_on):
    """Build N-Quads representation of a build artifact."""
    timestamp = datetime.now(timezone.utc).isoformat()
    resolved_path = resolve_path(path_str)

    safe_summary = summary.replace('"', '\\"')
    safe_project = project.replace('"', '\\"')

    cross_ref_quads = ""
    if based_on and based_on.startswith("did:dkg:working:"):
        cross_ref_quads += (
            f'<{ual}> <http://triad/ns/basedOn> <{based_on}> .\n'
        )

    nquads = f"""<{ual}> <http://www.w3.org/1999/02/22-rdf-syntax-ns#type> <http://triad/ns/KnowledgeAsset> .
<{ual}> <http://triad/ns/collection> "{DKG_COLLECTION}" .
<{ual}> <http://triad/ns/artifactType> "{artifact_type}" .
<{ual}> <http://triad/ns/project> "{safe_project}" .
<{ual}> <http://triad/ns/summary> "{safe_summary}" .
<{ual}> <http://triad/ns/filePath> "{resolved_path}" .
<{ual}> <http://triad/ns/status> "draft" .
<{ual}> <http://triad/ns/provenanceAgent> "{DKG_AGENT}" .
<{ual}> <http://triad/ns/provenanceModel> "{DKG_MODEL}" .
<{ual}> <http://triad/ns/provenanceTimestamp> "{timestamp}" .
{cross_ref_quads}"""
    return nquads


def write_to_dkg(nquads, auth_token):
    """Write N-Quads to DKG Working Memory."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.nq', delete=False) as f:
        f.write(nquads)
        tmp_path = f.name

    try:
        result = subprocess.run(
            [DKG_CLI, "workspace", "write", DKG_CONTEXT_GRAPH, "-f", tmp_path],
            capture_output=True, text=True, timeout=15,
            env={**os.environ, "DKG_AUTH_TOKEN": auth_token}
        )
        return result
    finally:
        os.unlink(tmp_path)


def main():
    parser = argparse.ArgumentParser(
        description="Vrilnius: Write build artifact to DKG Working Memory"
    )
    parser.add_argument("--type", required=True, dest="artifact_type",
                        choices=sorted(VALID_TYPES),
                        help="Artifact type (code, spec, config, doc)")
    parser.add_argument("--project", required=True, help="Project name")
    parser.add_argument("--summary", required=True, help="What was built")
    parser.add_argument("--path", required=True, help="File path in workspace")
    parser.add_argument("--based-on", default="",
                        help="DKG UAL of the research this implements")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print N-Quads without writing")
    parser.add_argument("--json", action="store_true",
                        help="Output machine-readable JSON")

    args = parser.parse_args()

    if args.artifact_type not in VALID_TYPES:
        print(f"ERROR: Invalid type '{args.artifact_type}'", file=sys.stderr)
        sys.exit(1)

    auth_token, node_url = load_config()
    if not auth_token:
        print("ERROR: No DKG auth token configured", file=sys.stderr)
        sys.exit(1)

    # Generate UAL from the file path (deterministic per artifact)
    resolved_path = resolve_path(args.path)
    asset_id = hashlib.sha256(resolved_path.encode()).hexdigest()[:16]
    ual = f"did:dkg:working:{asset_id}"

    nquads = build_nquads(
        ual, args.artifact_type, args.project,
        args.summary, args.path, args.based_on
    )

    if args.dry_run:
        print(nquads)
        return

    result = write_to_dkg(nquads, auth_token)

    if result.returncode == 0:
        name_match = re.search(r'Assertion name:\s+(\S+)', result.stdout)
        assertion_name = name_match.group(1) if name_match else "unknown"

        if args.json:
            print(json.dumps({
                "status": "ok",
                "ual": ual,
                "assertion": assertion_name,
                "based_on": args.based_on or None,
                "collection": DKG_COLLECTION
            }))
        else:
            print(f"✅ DKG: {ual}")
            print(f"   Assertion: {assertion_name}")
            print(f"   Collection: {DKG_COLLECTION}")
            print(f"   File: {resolved_path}")
            if args.based_on:
                print(f"   Based on: {args.based_on}")
    else:
        if args.json:
            print(json.dumps({"status": "error", "message": result.stderr[:200]}))
        else:
            print(f"❌ DKG write failed: {result.stderr[:200]}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
