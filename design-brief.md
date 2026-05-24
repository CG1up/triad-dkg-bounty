# The Triad — Multi-Agent Knowledge Graph on DKG v10

## Executive Summary

The Triad demonstrates a three-agent autonomous research pipeline where every
step — ingestion, analysis, and build — is captured as a Knowledge Asset in
DKG v10 Working Memory with full provenance and cross-referencing.

Three agents (Cleo, Otto, Vrilnius) running on different frameworks (Cron,
Hermes, OpenClaw) collaborate through free DKG Working + Shared Memory without
paying a single cent in gas.

---

## Architecture

```
┌─────────────────────────────────────────────────────┐
│                    DKG v10 NODE                      │
│              triad-node (Edge Node)                  │
│                16 peers, testnet                      │
│                                                      │
│  ┌──────────────────────────────────────────────┐   │
│  │         triad-research CONTEXT GRAPH          │   │
│  │                                               │   │
│  │  Working Memory ($0, local SQLite)            │   │
│  │  ┌─────────┐  ┌─────────┐  ┌──────────────┐  │   │
│  │  │reading- │  │research-│  │build-artifacts│  │   │
│  │  │ queue   │  │ briefs  │  │               │  │   │
│  │  └────┬────┘  └────┬────┘  └──────┬────────┘  │   │
│  │       │            │              │            │   │
│  │       │    basedOn │              │            │   │
│  │       │   ┌────────┘              │            │   │
│  │       │   │    basedOn            │            │   │
│  │       │   │   ┌───────────────────┘            │   │
│  │       ▼   ▼   ▼                                │   │
│  │  ┌─────────────────────────────────────┐       │   │
│  │  │        PROVENANCE CHAIN             │       │   │
│  │  │  Cleo → Otto → Vrilnius             │       │   │
│  │  │  (read) (research) (build)          │       │   │
│  │  └─────────────────────────────────────┘       │   │
│  └──────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────┘
         ▲              ▲              ▲
         │              │              │
    ┌────┴────┐   ┌────┴────┐   ┌────┴────────┐
    │  CLEO   │   │  OTTO   │   │  VRILNIUS    │
    │  Cron   │   │ Hermes  │   │  OpenClaw    │
    │ no_agent│   │ Agent   │   │  Gateway     │
    └─────────┘   └─────────┘   └─────────────┘
```

---

## Agent Roles

### Cleo — Reading Queue Worker (`cleo`)
- **Framework:** Hermes cron (no_agent — pure Python + Ollama)
- **Trigger:** Every 30 minutes
- **Action:** Picks one URL from Brainiac Reading Queue → Gemma 4 26B classifies → writes to `reading-queue` collection in DKG Working Memory
- **Cost:** $0 — local Gemma, free DKG Working Memory

### Otto — Research Orchestrator (`otto`)
- **Framework:** Hermes Agent
- **Trigger:** On-demand (when researching links)
- **Action:** Researches URLs → writes `research-briefs` collection with findings + verdict → cross-references to Cleo's ingestion asset via `researchedFrom`
- **Cost:** $0 — DeepSeek V4 (user's existing API), free DKG Working Memory

### Vrilnius — Build Agent (`vrilnius`)
- **Framework:** OpenClaw Gateway (Docker)
- **Trigger:** After completing build tasks
- **Action:** Captures build artifacts → writes `build-artifacts` collection → cross-references to Otto's research via `basedOn`
- **Cost:** $0 — GPT-4o (user's existing API), free DKG Working Memory

---

## Memory Architecture

All three agents write to the same DKG v10 node. Data uses DKG's layered memory model:

| Layer | Cost | Used For | Status |
|-------|------|----------|--------|
| **Working Memory** | $0 | Each agent's local triples | ✅ Active |
| **Shared Memory** | $0 | SPARQL-queryable, gossip-replicated | ✅ Active |
| **Verified Memory** | TRAC | On-chain finalization (Round 2) | ⬜ Deferred |

All writes use `dkg workspace write` — no chain transactions, zero gas.

---

## Research Cycle (Demonstrated)

1. **Cleo reads** a URL from the queue → writes Knowledge Asset to `reading-queue`
2. **Otto researches** the URL → writes brief to `research-briefs` with `researchedFrom` link to Cleo's UAL
3. **Vrilnius builds** from Otto's research → writes artifact to `build-artifacts` with `basedOn` link to Otto's UAL

Provenance chain is fully queryable via SPARQL:
```
dkg query triad-research -q "
  SELECT ?s ?p ?o WHERE {
    GRAPH ?g { ?s ?p ?o . }
  }
" --include-shared-memory
```

---

## Key Design Decisions

1. **No on-chain registration for MVP** — Working + Shared Memory suffice for the full cycle. Verified Memory (on-chain) is Round 2.
2. **Single Edge Node** — All three agents share one `triad-node` (no multi-node gossip needed for demo).
3. **File-based N-Quads** — Every script writes RDF via temp file → `dkg workspace write -f` (clean, shell-safe).
4. **Narrative UALs** — Content-addressed `did:dkg:working:{sha256_hash[:16]}` for deterministic, human-traceable asset IDs.
5. **Query tool built-in** — `query-triad.py` provides summary, full display, and cycle tracing via SPARQL.

---

## Files Delivered

| File | Purpose | Agent |
|------|---------|-------|
| `scripts/reading-queue-worker.py` | URL → DKG via Gemma | Cleo |
| `scripts/research-to-dkg.py` | Research brief → DKG | Otto |
| `scripts/artifact-to-dkg.py` | Build artifact → DKG | Vrilnius |
| `scripts/query-triad.py` | SPARQL query + visualization | Debug |
| `scripts/.dkg-config.json` | Auth token + node URL | Shared |
| `specs/triad-dkg-bounty.md` | Full implementation plan | Planning |

---

## Relevance to ERC-8004 + DKG v10

- **ERC-8004 ERC-7xxx Agent-Native Knowledge:** Agents write to a shared content-addressed graph
- **DKG v10 Layered Memory:** Uses all three free tiers (Working, Shared) correctly
- **Cross-Framework:** Three different agent frameworks (Cron, Hermes, OpenClaw) interoperating through DKG
- **Provenance Chain:** Full `basedOn` / `researchedFrom` links create verifiable lineage
- **Zero Gas MVP:** All demonstrated functionality at $0 — gas only needed for on-chain anchoring (Round 2)

---

## Seed Knowledge (Bootstrap)

The context graph was seeded with a research brief about the DKG v10 architecture itself — a self-referential bootstrap that demonstrates the cycle:

```
doi:dkg:working:50765dbd0bcd9ffa  (Otto — "DKG v10 Multi-Agent Memory Architecture")
  ↑ basedOn
doi:dkg:working:7d002469864bbb1c  (Vrilnius — artifact capture tool)
```

---

## Next Steps (Round 2)

1. On-chain context graph registration → Verified Memory
2. Agent-specific DIDs with signing keys
3. Multi-node deployment (one node per agent)
4. Auto-promotion path: Working → Shared → Verified
5. Public SPARQL endpoint for external querying
