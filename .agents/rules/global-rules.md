# TEN SHADOWS — WORKSPACE RULES

Canonical system rules, cognitive axioms, and workflow protocols are defined in [AGENTS.md](../../AGENTS.md).

## Mandatory Execution Entrypoint
For all governed objectives, capability acquisition, and codebase modifications, use the sovereign entrypoint:
`python ts_run.py run "<objective>"` or `ts run "<objective>"`.

Direct modifications outside Ten Shadows are mechanically intercepted and blocked by the `.agents/hooks.json` lifecycle execution gate.
