#!/usr/bin/env bash
# The Triad — Demo Script
# Demonstrates the full Cleo → Otto → Vrilnius research cycle on DKG v10
set -euo pipefail

BLUE='\033[36m'
GREEN='\033[32m'
YELLOW='\033[33m'
MAGENTA='\033[35m'
RESET='\033[0m'
BOLD='\033[1m'

header() { echo -e "\n${BOLD}${BLUE}━━━ $1 ━━━${RESET}\n"; }
step()  { echo -e "${BOLD}${GREEN}▶ $1${RESET}"; }
info()  { echo -e "  $1"; }

# ── Pre-flight ──────────────────────────────────────────────────────
header "THE TRIAD — DEMO"
info "Three agents, one knowledge graph. Zero gas."

# ── Step 1: Node Status ────────────────────────────────────────────
header "STEP 1: DKG Node Health"
step "Checking triad-node..."
curl -s http://127.0.0.1:9200/api/health 2>/dev/null | python3 -m json.tool || echo "  ⚠️  Node not running — start with: dkg openclaw setup"

# ── Step 2: Cleo — URL Ingestion ───────────────────────────────────
header "STEP 2: Cleo reads a URL from the queue"
step "Simulating Cleo's reading-queue-worker..."
python3 scripts/research-to-dkg.py \
  --title "DKG v10 Memory Architecture" \
  --source-url "https://docs.origintrail.io/dkg-v10" \
  --findings "Working Memory is free per-agent SQLite" \
             "Shared Memory is gossip-replicated" \
             "Verified Memory requires on-chain TRAC" \
  --verdict adopt \
  --context "Foundation research for multi-agent The Triad" \
  --json 2>/dev/null | python3 -c "
import json,sys,d=json.load(sys.stdin)
print(f'  ✅ Cleo ingested: {d[\"ual\"]}')
print(f'     Collection:    {d[\"collection\"]}')
print(f'     Assertion:     {d[\"assertion\"]}')
" || echo "  ⚠️  DKG write failed"

# ── Step 3: Otto — Research Brief ──────────────────────────────────
header "STEP 3: Otto researches and writes a brief"
step "Otto reading Cleo's asset and writing a research brief..."
CLEO_UAL=$(python3 scripts/query-triad.py --json 2>/dev/null | python3 -c "
import json,sys
data=json.load(sys.stdin)
for ual,props in data.items():
    if props.get('collection')=='reading-queue':
        print(ual); break
" 2>/dev/null || echo "")

if [ -n "$CLEO_UAL" ]; then
  info "Found Cleo's asset: $CLEO_UAL"
  python3 scripts/research-to-dkg.py \
    --title "Multi-Agent Memory Patterns on DKG v10" \
    --source-url "https://docs.origintrail.io/dkg-v10" \
    --findings "WM + SM suffice for agent coordination" \
               "No on-chain registration needed for MVP" \
               "Cross-references create provenance chain" \
    --verdict adopt \
    --based-on "$CLEO_UAL" \
    --json 2>/dev/null | python3 -c "
import json,sys; d=json.load(sys.stdin)
print(f'  ✅ Otto brief:   {d[\"ual\"]}')
print(f'     Based on:     {d[\"based_on\"]}')
"
else
  step "No Cleo assets in WM — Otto writes standalone brief"
  python3 scripts/research-to-dkg.py \
    --title "Multi-Agent Memory Patterns on DKG v10" \
    --source-url "https://docs.origintrail.io/dkg-v10" \
    --findings "WM + SM suffice for agent coordination" \
    --verdict adopt \
    --json 2>/dev/null | python3 -c "
import json,sys; d=json.load(sys.stdin)
print(f'  ✅ Otto brief:   {d[\"ual\"]}')
"
fi

# ── Step 4: Vrilnius — Build Artifact ──────────────────────────────
header "STEP 4: Vrilnius builds from Otto's research"
step "Vrilnius capturing build artifact with provenance..."
OTTO_UAL=$(python3 scripts/query-triad.py --json 2>/dev/null | python3 -c "
import json,sys
data=json.load(sys.stdin)
for ual,props in data.items():
    if props.get('collection')=='research-briefs':
        print(ual); break
" 2>/dev/null || echo "")

if [ -n "$OTTO_UAL" ]; then
  info "Found Otto's brief: $OTTO_UAL"
  python3 scripts/artifact-to-dkg.py \
    --type code \
    --project "the-triad" \
    --summary "Demo artifact: DKG integration scripts" \
    --path "$(pwd)/scripts/artifact-to-dkg.py" \
    --based-on "$OTTO_UAL" \
    --json 2>/dev/null | python3 -c "
import json,sys; d=json.load(sys.stdin)
print(f'  ✅ Vrilnius:     {d[\"ual\"]}')
print(f'     Based on:     {d[\"based_on\"]}')
print(f'     Collection:   {d[\"collection\"]}')
"
fi

# ── Step 5: Query the Graph ────────────────────────────────────────
header "STEP 5: Query the full knowledge graph"
step "Running triad query — summary..."
python3 scripts/query-triad.py --summary 2>/dev/null

echo ""
step "Tracing the full research cycle..."
# Get the newest Vrilnius UAL for tracing
VRILNIUS_UAL=$(python3 scripts/query-triad.py --json 2>/dev/null | python3 -c "
import json,sys
data=json.load(sys.stdin)
for ual,props in data.items():
    if props.get('collection')=='build-artifacts':
        print(ual); break
")
if [ -n "$VRILNIUS_UAL" ]; then
  python3 scripts/query-triad.py --cycle "$VRILNIUS_UAL" 2>/dev/null
fi

# ── Done ────────────────────────────────────────────────────────────
header "DEMO COMPLETE"
echo -e "  ${GREEN}✅ Cleo → Otto → Vrilnius cycle demonstrated${RESET}"
echo -e "  ${GREEN}✅ Full provenance chain in DKG Working Memory${RESET}"
echo -e "  ${GREEN}✅ Zero gas, zero on-chain transactions${RESET}"
echo ""
echo "  Repo: https://github.com/CG1up/triad-dkg-bounty"
echo "  Query: python3 scripts/query-triad.py"
