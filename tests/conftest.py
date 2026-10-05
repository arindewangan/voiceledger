"""Shared pytest fixtures for VoiceLedger."""

from __future__ import annotations

import os
import sys

import pytest

# Make the project root importable so `import server...` works.
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

os.environ.setdefault("API_TOKEN", "test-token")
os.environ.setdefault("BEDROCK_MODEL_ID", "")

from server.brain import Brain  # noqa: E402
from server.ledger import Ledger  # noqa: E402


@pytest.fixture()
def ledger(tmp_path):
    db = Ledger(str(tmp_path / "test.db"))
    yield db
    db.close()


@pytest.fixture()
def brain() -> Brain:
    return Brain(model_id="")  # offline-only brain for tests
