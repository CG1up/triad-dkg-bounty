# The Triad — DKG v10 Bounty Spec

> **Submission for:** OriginTrail DKG v10 Round 1 Bounty
> **Target tier:** Flagship (8,000–10,000 TRAC)
> **Target demo:** Multi-agent reference architecture showing Working Memory + Shared Memory across Hermes Agent, OpenClaw, and a curator agent
> **Status:** Spec — not yet started

---

## 1. Executive Summary

**The Triad** is a forkable reference architecture demonstrating three autonomous agent types coordinating through DKG v10's Working Memory and Shared Memory layers:

| Agent | Platform | Role | DKG Interaction |
|-------|----------|------|-----------------|
| **Otto** | Hermes Agent | Researcher — analyzes links, writes briefs, saves findings | Deposits research artifacts to Working Memory; reads Shared Memory for prior work |
| **Vrilnius** | OpenClaw | Builder — implements from research, produces code/artifacts | Reads research from Working Memory; deposits build artifacts; reads Shared Memory for team context |
| **Cleo** | Cron-only Hermes instance | Curator — ingests RSS/feeds, categorizes, maintains knowledge base | Deposits classified links to Working Memory; promotes curated entries to Shared Memory |

The architecture demonstrates the full Working → Shared → (prepares for) Verified gradient, with explicit promotion paths documented for each agent. It is designed to be forked and adapted by any team running Hermes, OpenClaw, or comparable agents.

---

## 2. Architecture

```
                         ┌──────────────────────────────────┐
                         │         DKG v10 Node              │
                         │  (local/testnet, port 9200)       │
                         │                                  │
                         │  ┌────────────────────────────┐  │
                         │  │     Working Memory         │  │
                         │  │  (per-agent private layer) │  │
                         │  │                            │  │
                         │  │  Otto: research briefs     │  │
                         │  │  Vrilnius: build artifacts │  │
                         │  │  Cleo: curated links       │  │
                         │  └──────────────┬─────────────┘  │
                         │                 │                 │
                         │  ┌──────────────▼─────────────┐  │
                         │  │     Shared Memory           │  │
                         │  │  (gossip-replicated,        │  │
                         │  │   multi-agent scratchpad)   │  │
                         │  │                            │  │
                         │  │  • Research queue          │  │
                         │  │  • Cross-referenced        │  │
                         │  │    knowledge base          │  │
                         │  │  • Team context graph      │  │
                         │  └──────────────┬─────────────┘  │
                         │                 │                 │
                         │  ┌──────────────▼─────────────┐  │
                         │  │  Promotion Path →          │  │
                         │  │  Verified Memory (R2)      │  │
                         └──────────────────────────────────┘
                                      │
                    ┌─────────────────┼─────────────────────┐
                    │                 │                      │
              ┌─────▼─────┐   ┌──────▼──────┐   ┌─────────▼─────┐
              │  Otto      │   │  Vrilnius   │   │   Cleo        │
              │ (Hermes)   │   │ (OpenClaw)  │   │   (Cron)      │
              │ Researcher │   │  Builder    │   │   Curator     │
              └───────────┘   └─────────────┘   └───────────────┘
```

### 2.1 Data Flow

**Research Cycle:**

1. **Cleo** picks a URL from the reading queue, categorizes it via Gemma 4, writes to **Working Memory** as a Knowledge Asset with tags (category, confidence, source)
2. **Otto** detects new entries in Working Memory (or is prompted to research), reads the link, performs deep analysis, writes a research brief back to **Working Memory** with provenance
3. **Vrilnius** reads Otto's research from **Shared Memory** (promoted by workflow), implements or builds from findings, deposits artifacts to **Working Memory**
4. **Cleo** curates the full cycle — deposits a summary entry to **Shared Memory** linking the research brief + build artifact as a Knowledge Collection

**Promotion to Verified Memory (Round 2 ready):**

- Every Knowledge Asset carries a `status` tag: `draft → reviewed → attested`
- Assets with `status: attested` by multiple agents are promotion candidates for Round 2's Verified Memory
- The promotion path is documented per asset type in the data model

---

## 3. Components

### 3.1 DKG v10 Node (Infrastructure)

**What:** A local DKG v10 testnet node running on port 9200.

**Setup:**
```
dkg openclaw setup --name triad-node --port 9200
```

This handles: node initialisation, OpenClaw adapter wiring, testnet TRAC faucet funding.

**Data directory:** `~/.dkg/` (auto-created)

**Persistence:** Knowledge Assets survive node restart. Node data is committed to Docker volumes.

---

### 3.2 Cleo — Reading Queue → Working Memory (Hermes Cron)

**File:** `cleo/reading-queue-worker.py`

**What it does:** A no_agent cron script that runs every 30 minutes:

1. Checks `~/Brainiac/Reading List/New Batches/` for unprocessed batch files
2. Extracts the first URL from the oldest batch
3. Calls Gemma 4 26B via Ollama for category + summary
4. **PUBLISHES** a Knowledge Asset to Working Memory via DKG HTTP API:
   ```json
   {
     "ual": "did:dkg:working:{hash}",
     "collection": "reading-queue",
     "content": {
       "title": "<from source>",
       "url": "<the link>",
       "summary": "<Gemma-generated summary>",
       "category": "<from Gemma>"
     },
     "status": "draft",
     "provenance": {
       "agent": "cleo",
       "source": "ollama:gemma4:26b",
       "timestamp": "<ISO>"
     }
   }
   ```
5. Removes the URL from the batch file
6. If batch is empty, moves to Processed Batches/

**Deposit to:** Working Memory (Cleo's private layer)
**Interface:** DKG Node HTTP API (port 9200, bearer token)
**Existing:** Already running as a no_agent cron — we add the DKG write path

**Effort:** ~0.5 day (wrap existing pipeline)

---

### 3.3 Otto — Research Loop → Working + Shared Memory (Hermes Agent)

**File:** `otto/research-to-dkg.py` (Hermes tool or skill)

**What it does:**

When Otto researches a link (via "look into this" or reference-scan):

1. Fetches the source via web_extract/fallback chain
2. Extracts key insights, cross-references against project context
3. **PUBLISHES** a Knowledge Asset to Working Memory:
   ```json
   {
     "ual": "did:dkg:working:{hash}",
     "collection": "research-briefs",
     "content": {
       "title": "<research topic>",
       "source_url": "<original link>",
       "key_findings": ["<bullet 1>", "<bullet 2>"],
       "source_context": "<from Otto's analysis>",
       "verdict": "adopt|learn|watch|ignore"
     },
     "status": "draft",
     "provenance": {
       "agent": "otto",
       "model": "deepseek-v4-flash",
       "source_sources": ["<url>"],
       "timestamp": "<ISO>"
     }
   }
   ```
4. If the research pertains to an active team project, also writes a **reference entry** to Shared Memory via `dkg publish --shared` pointing to the Working Memory asset

**Deposit to:** Working Memory (Otto's private layer) + Shared Memory (team-visible references)
**Interface:** `dkg publish` CLI (subprocess) or Node HTTP API
**Trigger:** Usually manual ("look into this"), but could be cron-driven

**Effort:** ~1.5 days (build DKG integration tool, wire into reference-scan workflow)

---

### 3.4 Vrilnius — OpenClaw Artifact → Working Memory (OpenClaw Agent)

**File:** `vrilnius/artifact-to-dkg.js` or OpenClaw plugin

**What it does:**

When Vrilnius completes a build artifact (code, implementation, analysis):

1. Captures the artifact from OpenClaw workspace
2. **PUBLISHES** a Knowledge Asset to Working Memory:
   ```json
   {
     "ual": "did:dkg:working:{hash}",
     "collection": "build-artifacts",
     "content": {
       "type": "code|spec|config|doc",
       "project": "<project name>",
       "summary": "<what was built>",
       "path": "<file path in workspace>"
     },
     "status": "draft",
     "provenance": {
       "agent": "vrilnius",
       "based_on": "<UAL of the research it implemented>",
       "timestamp": "<ISO>"
   }
   ```
3. If the artifact references a research UAL, adds an edge linking the two in the Context Graph

**Deposit to:** Working Memory (Vrilnius's private layer)
**Interface:** `dkg openclaw` adapter or direct HTTP API
**Integration point:** OpenClaw gateway post-processing hook

**Effort:** ~2 days (build the OpenClaw artifact capture + DKG publish)

---

### 3.5 Context Graph — Connecting the Agents

The Context Graph is the **Shared Memory substrate** that ties the three agents together:

```
[Cleo: reading-queue/url-123]
    │ "researched_by"
    ▼
[Otto: research-brief/analysis-456]
    │ "implemented_by"
    ▼
[Vrilnius: build-artifacts/build-789]
```

A **Knowledge Collection** "Triad Research Cycle #1" groups all three into a single navigable unit.

**Method:** Agents write contextual `←` and `→` relationships when depositing:
- Otto links his brief back to Cleo's original URL entry
- Vrilnius links his build artifact to the research brief
- Cleo (in promotion step) creates the Knowledge Collection grouping them

---

## 4. Data Model

### 4.1 Knowledge Asset Schema (shared across agents)

```json
{
  "ual": "did:dkg:working:<sha256-of-content>",
  "collection": "<agent-specific-collection-name>",
  "context_graph": "triad-research",
  "content": {
    "title": "...",
    // agent-specific payload
  },
  "metadata": {
    "v10_memory_layer": "working",
    "status": "draft",
    "tags": ["hermes", "openclaw", "research"],
    "confidence": 0.85
  },
  "provenance": {
    "agent": "otto|vrilnius|cleo",
    "source_type": "web_extract|ollama|code|spec",
    "timestamp": "2026-05-22T...",
    "sources": ["<original URLs>"],
    "model": "deepseek-v4-flash|gemma4:26b|gpt-4o"
  },
  "promotion_path": {
    "next_layer": "shared",
    "trigger": "peer_endorsement",
    "required_signals": ["peer_verified:ot metric:0.8"]
  }
}
```

### 4.2 Collection Types

| Collection | Agent | Layer | Promotion Trigger |
|------------|-------|-------|-------------------|
| `reading-queue` | Cleo | Working → Shared | After categorization by Gemma + Otto review |
| `research-briefs` | Otto | Working → Shared | After Vrilnius builds from the research |
| `build-artifacts` | Vrilnius | Working | Archived + linked to research brief |
| `triad-cycles` | Cleo (promotion) | Shared (Knowledge Collection) | After full cycle completes |

### 4.3 Status Gradient

```
draft (Working)
  └─→ reviewed (Working, peer-tagged by another agent)
       └─→ attested (Shared, endorsed by at least one peer)
            └─→ verified (Verified Memory, Round 2 — on-chain anchoring)
```

---

## 5. Implementation Phases

### Phase 1: Infrastructure (Day 1)

- [ ] Run `dkg openclaw setup` to provision DKG node
- [ ] Verify node status, API access, testnet TRAC balance
- [ ] Create Context Graph `triad-research`
- [ ] Generate API tokens for each agent
- [ ] Write auth/config management for Hermes + OpenClaw

### Phase 2: Cleo → DKG Integration (Day 1-2)

- [ ] Modify `reading-queue-worker.py` to add DKG publish path
- [ ] Keep existing markdown write as fallback
- [ ] Test: run cron, verify Knowledge Asset appears in DKG
- [ ] Add query: read back from Working Memory on next cycle
- [ ] Write Cleo-specific integration tests

### Phase 3: Otto → DKG Integration (Day 2-3)

- [ ] Build `research-to-dkg.sh` utility (wraps `dkg publish` HTTP API)
- [ ] Wire into reference-scan workflow as post-processing hook
- [ ] Add Shared Memory deposit for team-visible entries
- [ ] Test: research a link, verify Working + Shared deposits
- [ ] Write Otto-specific integration tests

### Phase 4: Vrilnius → DKG Integration (Day 3-4)

- [ ] Build artifact capture script (watches OpenClaw workspace for new files)
- [ ] Or use OpenClaw gateway's existing artifact hooks
- [ ] Publish to Working Memory with provenance linking to research UALs
- [ ] Test: Vrilnius builds something, verify artifact in DKG
- [ ] Write Vrilnius-specific integration tests

### Phase 5: Context Graph + Promotion Path (Day 4)

- [ ] Wire Knowledge Collection creation when full cycles complete
- [ ] Build a query script: "show me the full research cycle for topic X"
- [ ] Document promotion path per asset type
- [ ] Test SPARQL query across the Context Graph

### Phase 6: Submission Package (Day 4-5)

- [ ] Write design brief (1-3 pages in project repo)
- [ ] Record demo walk-through (showing all 3 agents depositing + cross-linking)
- [ ] Write tests (against local DKG node)
- [ ] Write security notes
- [ ] Publish npm package with provenance
- [ ] Open PR against `OriginTrail/dkg-integrations`
- [ ] Tag `cfi-dkgv10-r1`

---

## 6. Demo Script

The demo should show:

1. **Cleo picks a URL** → DKG Working Memory gets a new Knowledge Asset
2. **Otto researches it** → DKG Working Memory gets a research brief, linked to Cleo's entry
3. **Vrilnius builds from it** → DKG Working Memory gets a build artifact, linked to Otto's brief
4. **Query** across the Context Graph showing the full cycle as a Knowledge Collection
5. **Promotion path** — show how assets in Working Memory are tagged for Shared Memory promotion

**Format:** Recorded walk-through with splitscreen:
- Left: terminal showing agent actions
- Right: DKG dashboard showing assets appearing in real-time

---

## 7. Scoring Self-Assessment

| Criterion | How We Score | Our Evidence |
|-----------|-------------|-------------|
| **1. LLM-Wiki fit** | 9/10 — Directly maps to Karpathy's vision: agents researching, curating, building, compounding knowledge | Research Log, Brainiac vault, Cleo reading queue |
| **2. Adoption potential** | 9/10 — Three named priority platforms in one submission. Forkable template. Credible first user (us) | Running Hermes + OpenClaw + Cleo today |
| **3. v10 memory model fidelity** | 9/10 — Correct Working vs Shared use. No Verified Memory. Conversational consensus. No UI buttons | Architecture respects all v10 design principles |
| **4. Forward-compatibility** | 8/10 — Explicit promotion paths. Data shaped for oracle consumption. Round 2 natural extension | Documented in data model |
| **5. Agent surface** | 9/10 — All three are agents. No UI. Cron-driven, CLI-driven, conversation-driven | Three agent types, zero UI |
| **6. Engineering quality** | 8/10 — Standalone repos. Integration tests. npm-provenance. Clean dependencies | (assuming we deliver this) |
| **7. Documentation** | 8/10 — Design brief, in-repo docs, onboarding for fork | (assuming we deliver this) |

**Estimated tier:** Flagship (8,000-10,000 TRAC / $3,400-4,300)

---

## 8. What You Need From Your End

| Item | Status | Action |
|------|--------|--------|
| DKG v10 CLI | ✅ Installed (v10.0.0-rc.6-dev) | Already have it |
| npm + Node | ✅ Available (npm 10.9.7) | Already have it |
| OpenClaw | ✅ Running (Vrilnius) | Already have it |
| Hermes Agent | ✅ Running (Otto) | Already have it |
| Cleo | ✅ Running (cron) | Already have it |
| DKG v10 node | ❌ Not started | Run `dkg openclaw setup` — testnet faucet funds it |
| TRAC wallet | ❌ Needed for node funding | Testnet faucet auto-funds (no real $) |
| npm account | ❌ Needed for package publish | Free npm account required |
| GitHub repo | ❌ Needed | Will create `CG1up/the-triad` |

**Total external cost:** $0 (testnet faucet, free npm, free GitHub)

---

## 9. Effort Summary

| Phase | Effort | What |
|-------|--------|------|
| 1. Infrastructure | 0.5 day | DKG node setup, config, auth tokens |
| 2. Cleo → DKG | 0.5 day | Modify existing cron |
| 3. Otto → DKG | 1.5 days | Build research-to-DKG tool + wire into workflow |
| 4. Vrilnius → DKG | 2 days | Build artifact capture + publish |
| 5. Context Graph | 1 day | Wire cross-linking + query tool |
| 6. Submission | 1 day | Design brief, demo, PR |
| **Total** | **~6.5 days** | Realistically 5-7 calendar days |

---

## 10. Risk Register

| Risk | Likelihood | Mitigation |
|------|-----------|------------|
| DKG testnet faucet down | Medium | Can manually fund; testnet TRAC is free |
| OpenClaw adapter incomplete | Low | `dkg openclaw setup` is a first-party command |
| npm publish CI issues | Low | Use GitHub Actions with `--provenance` |
| Demo recording complexity | Medium | Script demo steps first, rehearse, record |
| OriginTrail changes scoring criteria | Low | Spec adheres to documented criteria |
| Someone else ships OpenClaw adapter first | Low | We move fast — first to spec means first to PR |
