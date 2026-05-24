# Security Notes

## Threat Model

The Triad operates on a single-machine local DKG Edge Node. All three agents
share the same node, context graph, and auth token. This is appropriate for a
single-developer demo but would need hardening for multi-user deployment.

## Current State

| Concern | Assessment | Mitigation |
|---------|-----------|------------|
| Auth token exposure | `.dkg-config.json` excluded from git via `.gitignore` | Token lives on local filesystem only |
| Node access | HTTP API on `127.0.0.1:9200` — localhost only | No external exposure by default |
| Context graph privacy | Public access policy on `triad-research` | Acceptable for testnet — data is non-sensitive |
| Agent wallets | Custodial mode — single node controls all keys | Acceptable for single-developer setup |
| Cron script | Runs as system user, reads Brainiac files | Same trust domain as all other agent operations |
| OpenClaw workspace | Bind-mounted to host filesystem | Same trust domain — all agents on one machine |

## Round 2 Hardening

1. **Per-agent DIDs** — Each agent (Cleo, Otto, Vrilnius) gets its own DID with signing key
2. **Auth token rotation** — Per-agent tokens instead of shared master token
3. **Access policy** — Context graph set to `restricted` with agent whitelist
4. **Multi-node** — Each agent on its own Edge Node for fault isolation
5. **On-chain anchoring** — Verified Memory for tamper-proof audit trail
6. **Input validation** — URL/content sanitization before RDF ingestion

## Dependency Notes

- **dkg CLI (v10.0.0-rc.9)** — Official OriginTrail tooling, trust inherited from org
- **Ollama (Gemma 4 26B)** — Local model, no network egress for Cleo's classification
- **Subprocess calls** — All DKG writes use `subprocess.run()` with explicit args (no shell=True)
- **N-Quads temp files** — Written via `tempfile.NamedTemporaryFile(delete=False)`, cleaned in `finally` block

## Verification

```bash
# Confirm .dkg-config.json is not in git
git ls-files scripts/.dkg-config.json  # should return nothing

# Confirm no API keys in committed files
grep -r "AUf4" $(git ls-files) || echo "No keys found"

# Confirm no shell injection vectors
grep -r "shell=True" $(git ls-files) || echo "No shell=True found"
```
