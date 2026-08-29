import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Universal namespace alias: Forge <-> forge
try:
    import Forge

    sys.modules["forge"] = Forge
    import Forge.adapters

    sys.modules["forge.adapters"] = Forge.adapters
    import Forge.adapters.actions

    sys.modules["forge.adapters.actions"] = Forge.adapters.actions
    import Forge.adapters.model

    sys.modules["forge.adapters.model"] = Forge.adapters.model
    import Forge.core

    sys.modules["forge.core"] = Forge.core
    import Forge.core.authorize

    sys.modules["forge.core.authorize"] = Forge.core.authorize
    import Forge.core.build

    sys.modules["forge.core.build"] = Forge.core.build
    import Forge.core.direct

    sys.modules["forge.core.direct"] = Forge.core.direct
    import Forge.core.evaluate

    sys.modules["forge.core.evaluate"] = Forge.core.evaluate
    import Forge.core.execute

    sys.modules["forge.core.execute"] = Forge.core.execute
    import Forge.core.learn

    sys.modules["forge.core.learn"] = Forge.core.learn
    import Forge.core.normalize

    sys.modules["forge.core.normalize"] = Forge.core.normalize
    import Forge.core.route

    sys.modules["forge.core.route"] = Forge.core.route
    import Forge.core.schema

    sys.modules["forge.core.schema"] = Forge.core.schema
    import Forge.core.store

    sys.modules["forge.core.store"] = Forge.core.store
    import Forge.forge

    sys.modules["forge.forge"] = Forge.forge
except Exception:
    pass
