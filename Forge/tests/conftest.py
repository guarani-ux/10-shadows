import os
import sys
import tempfile
from pathlib import Path

import pytest

# Ensure forge root is on sys.path
FORGE_ROOT = Path(__file__).parent.parent
if str(FORGE_ROOT.parent) not in sys.path:
    sys.path.insert(0, str(FORGE_ROOT.parent))

from forge.adapters.actions import SandboxFileAdapter
from forge.adapters.model import MockModelAdapter
from forge.core.store import ForgeStore


@pytest.fixture
def temp_dir():
    with tempfile.TemporaryDirectory() as td:
        yield Path(td)


@pytest.fixture
def test_store(temp_dir):
    db_path = temp_dir / "test_forge.db"
    return ForgeStore(db_path)


@pytest.fixture
def mock_model():
    return MockModelAdapter()


@pytest.fixture
def sandbox_adapter(temp_dir):
    sandbox_path = temp_dir / "sandbox"
    return SandboxFileAdapter(sandbox_path)
