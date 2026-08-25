"""
Minimal Capability Forge (v0.1)
"""

import os
import sys

# Ensure self-aliasing for both Forge and forge
self_mod = sys.modules.get(__name__)
if self_mod:
    sys.modules["forge"] = self_mod
    sys.modules["Forge"] = self_mod

from .forge import ForgeEngine, run

__all__ = ["ForgeEngine", "run"]
