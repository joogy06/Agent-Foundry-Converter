<!-- tk:pull-managed-begin v0.3.0 -->
## Agent-Foundry payload (managed by transfer-kit pull)

This project can pull the upstream `joogy06/agent-foundry` skills and
agent prompts into the GitHub Copilot CLI layout via
`transfer-kit pull`.

### How to refresh the payload

```bash
transfer-kit pull https://github.com/joogy06/agent-foundry \
  --target copilot-cli --tier standard --output .
```

Flags you may want:

* `--tier minimal|standard|full` — how much of the upstream payload to
  import. `standard` is the default; `minimal` drops anything classified
  as `degraded`; `full` additionally includes docs-only meta files.
* `--ref <branch|tag|sha>` — pin to a specific upstream ref for
  reproducibility. Production deployments should pin to a SHA.
* `--force` / `--preserve` — conflict policy when re-pulling over
  hand-edited files. Default aborts with a conflict report.
* `--dry-run` — show what would change without touching the filesystem.

### What gets written

* `AGENTS.md` — root-level agent bootstrap file.
* `.github/agents/*.agent.md` — per-agent prompts (bob, alf, pa, wiki).
* `.github/instructions/*.instructions.md` — skills.
* `docs/agent-foundry/_meta/` — reference copies of the upstream meta
  scripts. `gates_g2_shim.py` in that directory is the runtime schema
  validator (G1/G3 gates are Claude-specific and are NOT ported).
* `.mcp.json` — MCP server configuration (workspace-scoped).
* `DEPENDENCIES.md` — rendered dependency docs with compat annotations.

The re-pull is idempotent: identical inputs against the same output
directory write zero files.

### Schema validation

When a host agent wants to validate a contract-map.yaml locally, run:

```bash
python3 docs/agent-foundry/_meta/gates_g2_shim.py G2 progress/contract-map.yaml
```

Exit codes: 0 = pass, 2 = schema violation, 3 = environment error.
<!-- tk:pull-managed-end -->
