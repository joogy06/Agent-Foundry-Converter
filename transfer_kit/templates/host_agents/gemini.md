<!-- tk:pull-managed-begin v0.3.0 -->
## Agent-Foundry payload (managed by transfer-kit pull)

This project can pull the upstream `joogy06/agent-foundry` skills into
the Gemini CLI layout:

```bash
transfer-kit pull https://github.com/joogy06/agent-foundry \
  --target gemini --tier standard --output ~
```

Skills land in `~/.gemini/skills/<name>/SKILL.md`, agents in
`~/.gemini/agents/`, meta files in `~/.gemini/_meta/` as reference docs.
The G2 schema validator (`gates_g2_shim.py`) is portable and usable
from Gemini CLI directly.

Note: bob / alf / pa orchestration primitives are Claude-specific;
on Gemini CLI they are prose-only agents.
<!-- tk:pull-managed-end -->
