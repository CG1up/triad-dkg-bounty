#!/usr/bin/env python3
"""
Triad Context Graph Query Tool.

Queries the triad-research Working Memory and displays
the full research cycle: Cleo → Otto → Vrilnius.

Usage:
  python3 query-triad.py                  # Show all assertions
  python3 query-triad.py --agent otto     # Filter by agent
  python3 query-triad.py --cycle <ual>    # Trace a full research cycle
  python3 query-triad.py --summary        # Summary counts only
"""

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

DKG_CONFIG_PATH = Path(os.path.expanduser("~/.hermes/scripts/.dkg-config.json"))
DKG_CONTEXT_GRAPH = "triad-research"

AGENT_COLORS = {
    "cleo": "\033[35m",      # magenta
    "otto": "\033[36m",      # cyan
    "vrilnius": "\033[33m",  # yellow
    "reset": "\033[0m",
}

COLLECTION_NAMES = {
    "reading-queue": "Cleo — Reading Queue",
    "research-briefs": "Otto — Research Briefs",
    "build-artifacts": "Vrilnius — Build Artifacts",
}


def load_config():
    config = {}
    if DKG_CONFIG_PATH.exists():
        config = json.loads(DKG_CONFIG_PATH.read_text())
    return config.get("auth_token", os.environ.get("DKG_AUTH_TOKEN", ""))


def sparql(query, auth_token):
    result = subprocess.run(
        ["dkg", "query", DKG_CONTEXT_GRAPH,
         "-q", query, "--include-shared-memory"],
        capture_output=True, text=True, timeout=15,
        env={**os.environ, "DKG_AUTH_TOKEN": auth_token}
    )
    if result.returncode != 0:
        print(f"SPARQL error: {result.stderr[:200]}", file=sys.stderr)
        sys.exit(1)
    return json.loads(result.stdout)


def parse_bindings(bindings):
    """Parse SPARQL JSON bindings into a dict keyed by subject UAL."""
    assets = {}
    for b in bindings:
        # Handle both {"value": "..."} and direct string formats
        s = b["s"]["value"] if isinstance(b["s"], dict) else b["s"]
        p = b["p"]["value"] if isinstance(b["p"], dict) else b["p"]
        o = b["o"]["value"] if isinstance(b["o"], dict) else b["o"]
        # Strip quotes from strings
        o = o.strip('"')
        if s not in assets:
            assets[s] = {}
        short_p = p.replace("http://triad/ns/", "").replace(
            "http://www.w3.org/1999/02/22-rdf-syntax-ns#", "rdf:")
        assets[s][short_p] = o
    return assets


def color_agent(agent_name):
    c = AGENT_COLORS.get(agent_name, "")
    r = AGENT_COLORS["reset"]
    return f"{c}{agent_name}{r}"


def show_all(assets):
    if not assets:
        print("No assets in Working Memory yet.")
        return

    by_collection = {}
    for ual, props in assets.items():
        col = props.get("collection", "unknown")
        by_collection.setdefault(col, []).append((ual, props))

    for col, items in by_collection.items():
        label = COLLECTION_NAMES.get(col, col)
        agent_name = col.split("-")[0] if "-" in col else "unknown"
        print(f"\n{'='*60}")
        print(f"  {label}")
        print(f"{'='*60}")

        for ual, props in items:
            title = props.get("title", props.get("summary", ual))[:60]
            agent = props.get("provenanceAgent", "unknown")
            status = props.get("status", "?")
            verdict = props.get("verdict", "")
            artifact_type = props.get("artifactType", "")
            based_on = props.get("basedOn", "")

            print(f"\n  [{color_agent(agent)}] {title}")
            print(f"    UAL:  {ual}")
            print(f"    Status: {status}", end="")
            if verdict:
                print(f"  |  Verdict: {verdict}", end="")
            if artifact_type:
                print(f"  |  Type: {artifact_type}", end="")
            print()

            if based_on:
                print(f"    🔗 basedOn → {based_on}")

            if "sourceUrl" in props:
                print(f"    📎 {props['sourceUrl'][:80]}")

    print(f"\n{'='*60}")
    print(f"  Total: {len(assets)} Knowledge Assets in Working Memory")
    print(f"{'='*60}")


def show_cycle(ual, auth_token):
    """Trace a full research cycle: find what this links to and what links to it."""

    def safe_val(b, key):
        """Extract value from binding, handling both formats."""
        v = b.get(key, "")
        return v["value"] if isinstance(v, dict) else v

    # Find the asset's properties
    q = f"SELECT ?p ?o WHERE {{ GRAPH ?g {{ <{ual}> ?p ?o . }} }}"
    r = sparql(q, auth_token)
    if not r.get("bindings"):
        print(f"No asset found for UAL: {ual}")
        return

    props = {}
    for b in r["bindings"]:
        p = safe_val(b, "p").replace("http://triad/ns/", "")
        o = safe_val(b, "o").strip('"')
        props[p] = o

    agent = props.get("provenanceAgent", "unknown")
    col = props.get("collection", "unknown")
    title = props.get("title", props.get("summary", ual))[:60]
    based_on = props.get("basedOn", "")

    print(f"\n{'='*60}")
    print(f"  Research Cycle Trace")
    print(f"{'='*60}")
    print(f"\n  🎯 [{color_agent(agent)}] {title}")
    print(f"     UAL:    {ual}")
    print(f"     Collection: {col}")
    print(f"     Status: {props.get('status', '?')}")

    if based_on:
        print(f"\n  ⬆️  Based on: {based_on}")
        q2 = f"SELECT ?p ?o WHERE {{ GRAPH ?g {{ <{based_on}> ?p ?o . }} }}"
        r2 = sparql(q2, auth_token)
        up = {}
        for b in r2.get("bindings", []):
            p = safe_val(b, "p").replace("http://triad/ns/", "")
            o = safe_val(b, "o").strip('"')
            up[p] = o
        if up:
            up_agent = up.get("provenanceAgent", "?")
            up_title = up.get("title", up.get("summary", "?"))[:60]
            up_verdict = up.get("verdict", "")
            print(f"     → [{color_agent(up_agent)}] {up_title}")
            if up_verdict:
                print(f"       Verdict: {up_verdict}")

    # Find children (what links TO this)
    q3 = f"""
    SELECT ?s WHERE {{
      GRAPH ?g {{
        ?s <http://triad/ns/basedOn> <{ual}> .
      }}
    }}
    """
    r3 = sparql(q3, auth_token)
    children = [safe_val(b, "s") for b in r3.get("bindings", [])]
    if children:
        print(f"\n  ⬇️  Built upon by:")
        for child_ual in children:
            q4 = f"SELECT ?p ?o WHERE {{ GRAPH ?g {{ <{child_ual}> ?p ?o . }} }}"
            r4 = sparql(q4, auth_token)
            cp = {}
            for b in r4.get("bindings", []):
                p = safe_val(b, "p").replace("http://triad/ns/", "")
                o = safe_val(b, "o").strip('"')
                cp[p] = o
            c_agent = cp.get("provenanceAgent", "?")
            c_title = cp.get("title", cp.get("summary", "?"))[:60]
            c_type = cp.get("artifactType", "")
            print(f"     → [{color_agent(c_agent)}] {c_title}")
            if c_type:
                print(f"       Type: {c_type}")

    print()


def show_summary(assets):
    """Show summary counts by agent and collection."""
    if not assets:
        print("No assets in Working Memory.")
        return

    by_agent = {}
    by_collection = {}
    cross_refs = 0

    for ual, props in assets.items():
        agent = props.get("provenanceAgent", "unknown")
        col = props.get("collection", "unknown")
        by_agent[agent] = by_agent.get(agent, 0) + 1
        by_collection[col] = by_collection.get(col, 0) + 1
        if props.get("basedOn"):
            cross_refs += 1

    print(f"\n  The Triad — DKG Working Memory")
    print(f"  {'─'*35}")
    print(f"\n  By Agent:")
    for agent in ["cleo", "otto", "vrilnius"]:
        count = by_agent.get(agent, 0)
        print(f"    {color_agent(agent):>20}  {count} assets")

    print(f"\n  By Collection:")
    for col, label in COLLECTION_NAMES.items():
        count = by_collection.get(col, 0)
        print(f"    {label:<35} {count}")

    print(f"\n  Cross-references: {cross_refs}")
    print(f"  Total assets:     {len(assets)}")
    print()


def main():
    parser = argparse.ArgumentParser(
        description="Triad Context Graph Query Tool"
    )
    parser.add_argument("--agent", choices=["cleo", "otto", "vrilnius"],
                        help="Filter by agent")
    parser.add_argument("--cycle", help="Trace full research cycle for a UAL")
    parser.add_argument("--summary", action="store_true",
                        help="Summary counts only")
    parser.add_argument("--json", action="store_true",
                        help="Output raw JSON")

    args = parser.parse_args()
    auth_token = load_config()

    if not auth_token:
        print("ERROR: No DKG auth token configured", file=sys.stderr)
        sys.exit(1)

    if args.cycle:
        show_cycle(args.cycle, auth_token)
        return

    # Fetch all assets
    query = """
    SELECT ?s ?p ?o WHERE {
      GRAPH ?g {
        ?s ?p ?o .
        FILTER(STRSTARTS(STR(?s), "did:dkg:working:"))
      }
    }
    """
    result = sparql(query, auth_token)
    assets = parse_bindings(result.get("bindings", []))

    if args.agent:
        assets = {ual: props for ual, props in assets.items()
                  if props.get("provenanceAgent") == args.agent}

    if args.json:
        print(json.dumps(assets, indent=2))
        return

    if args.summary:
        show_summary(assets)
    else:
        show_all(assets)


if __name__ == "__main__":
    main()
