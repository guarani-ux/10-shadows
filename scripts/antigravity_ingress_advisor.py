"""
scripts/antigravity_ingress_advisor.py
PreInvocation Lifecycle Hook for Google Antigravity & 10 SHADOWS.
Injects ephemeral guidance ensuring substantive objectives route through ts run.
"""

from __future__ import annotations

import json
import sys


def main() -> int:
    try:
        raw_input = sys.stdin.read()
        msg = (
            "TEN SHADOWS INGRESS POLICY:\n"
            "For governed engineering objectives, bug fixes, system modifications, or capability acquisition, "
            'invoke the sovereign entrypoint: `python ts_run.py run "<objective>"` (or `ts run "<objective>"`).\n'
            "Direct file mutations on repository source files outside Ten Shadows are mechanically blocked."
        )
        output = {"injectSteps": [{"ephemeralMessage": msg}]}
        print(json.dumps(output))
        return 0
    except Exception:
        print(json.dumps({}))
        return 0


if __name__ == "__main__":
    sys.exit(main())
