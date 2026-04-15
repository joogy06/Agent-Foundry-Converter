---
schema_version: 1
contract_map_hash: f3f6ca242a1b7f41d9d08c567c969dc70712bf5db3561be7ebbaea5948f5dfca
contract_map_revision: 1
forge_session_id: 5529f246-c533-4a24-a0a0-1e6944f862cf
frozen_at: 2026-04-15T14:00:00Z
writer: bob
consumed_request_ids: []
drift_canary: "ALDEBARAN-7"
pause_epoch: 0
last_rules_reread: 2026-04-15T14:00:00Z
skill_checksums: {}
---

# Integration Ledger — Agent-Foundry Pull (v0.3.0)

Design: `docs/plans/2026-04-15-agent-foundry-pull-design.md`
Contract map: `progress/contract-map.yaml` (revision 1, 7 components, 1 flow)

## Projection table

| WP | component | stage | generation | deps |
|----|-----------|-------|------------|------|
| WP-1 | foundry-loader | UNIT_TESTED | 1 | — |
| WP-2 | url-sanitizer | UNIT_TESTED | 1 | — |
| WP-2b | path-rewriter | UNIT_TESTED | 1 | — |
| WP-3 | compat | UNIT_TESTED | 1 | foundry-loader |
| WP-4 | xref-resolver | UNIT_TESTED | 1 | compat |
| WP-5 | copilot-cli-converter | UNIT_TESTED | 1 | compat, xref-resolver |
| WP-6 | pull | INTEGRATED | 1 | — |

## Events

- 2026-04-15T14:00:00Z `bob` initialized ledger from contract-map revision 1.
- 2026-04-15T16:30:00Z `bob` executed all 7 WPs sequentially (no agent-teams due to heavy shared-file deps between WPs). Direct-sequential execution verified via 203/203 tests and end-to-end pull smoke test against `/tmp/agent-foundry-recon` (141 files on first run, 0 on idempotent re-run).
- 2026-04-15T16:30:00Z Advanced PLANNED → SCAFFOLDED → UNIT_TESTED for all components; `pull` further advanced to INTEGRATED via end-to-end smoke test. VERIFIED stage deferred — the metacognitive audit step (Step 4.5) would require cold-context Claude+Codex subagents that are out of scope for this execution context; the forge caller may invoke `audit_spawn.py` as a separate step.
