# The Triad — Multi-Agent Knowledge Graph on DKG v10

**ERC-8004 / DKG v10 Bounty Submission — Flagship Tier**

Three autonomous agents (Cleo, Otto, Vrilnius) running on different frameworks
collaborate through DKG v10 Working + Shared Memory. Zero gas, full provenance,
cross-referenced knowledge graph.

## Quick Start

```bash
# Prerequisites: DKG v10 node running, dkg CLI installed
pip install -r requirements.txt  # if any

# Test each agent's DKG integration
python3 scripts/research-to-dkg.py --dry-run --title "Test" --source-url "https://example.com" --findings "Test" --verdict adopt
python3 scripts/artifact-to-dkg.py --dry-run --type code --project "test" --summary "Test" --path "/tmp/test"

# Query the knowledge graph
python3 scripts/query-triad.py --summary
python3 scripts/query-triad.py --cycle "did:dkg:working:<ual>"
```

## Architecture

```
Cleo (Cron) ──reads──▶ reading-queue ──researchedFrom──▶ Otto (Hermes)
                                                              │
                                                        research-briefs
                                                              │
                                                          basedOn
                                                              ▼
                                                     Vrilnius (OpenClaw)
                                                              │
                                                      build-artifacts
```

## Agent Roles

| Agent | Framework | Trigger | Collection |
|-------|-----------|---------|------------|
| **Cleo** | Hermes cron (no_agent) | Every 30 min | `reading-queue` |
| **Otto** | Hermes Agent | On-demand research | `research-briefs` |
| **Vrilnius** | OpenClaw Gateway | After builds | `build-artifacts` |

## Memory Layers Used

| Layer | Cost | Status |
|-------|------|--------|
| Working Memory | $0 (local SQLite) | ✅ Active |
| Shared Memory | $0 (gossip + SPARQL) | ✅ Active |
| Verified Memory | TRAC (on-chain) | ⬜ Round 2 |

## Files

- `design-brief.md` — Full submission design brief
- `scripts/reading-queue-worker.py` — Cleo: URL → DKG via Gemma 4
- `scripts/research-to-dkg.py` — Otto: Research brief → DKG
- `scripts/artifact-to-dkg.py` — Vrilnius: Build artifact → DKG
- `scripts/query-triad.py` — SPARQL query tool with cycle tracing
- `specs/triad-dkg-bounty.md` — Original implementation plan

## Provenance Chain

Every Knowledge Asset is content-addressed (`did:dkg:working:{sha256_hash}`)
and linked via `basedOn` / `researchedFrom` — creating a verifiable lineage
from ingestion → research → build.

## License

MIT
