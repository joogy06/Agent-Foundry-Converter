<!-- tk:pull-managed-begin v0.3.0 -->
## Agent-Foundry payload (managed by transfer-kit pull)

This repository can pull the upstream `joogy06/agent-foundry` skills
(and degraded agents) into the GitHub Copilot (VS Code) layout:

```bash
transfer-kit pull https://github.com/joogy06/agent-foundry \
  --target copilot --tier standard --output .
```

Skills land in `.github/instructions/`, agents in `.github/agents/`.
Re-running with identical inputs is a no-op.

Note: bob / alf / pa orchestration primitives are Claude-specific;
on this host they run as prose-only agents (no Task tool, no hooks).
<!-- tk:pull-managed-end -->
