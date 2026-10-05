"""Environment-based configuration for VoiceLedger.

No secrets are committed anywhere. Every sensitive or deployment-specific
value comes from an environment variable with a safe development default.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Config:
    """Runtime configuration loaded from the environment."""

    # Bearer <redacted> required on every /mcp request. Change in production.
    api_token: str = field(default_factory=lambda: os.environ.get("API_TOKEN", "demo-token-change-me"))
    # SQLite database path.
    db_path: str = field(default_factory=lambda: os.environ.get("LEDGER_DB", "data/ledger.db"))
    # Amazon Bedrock settings (AWS Builder mini challenge). Optional:
    # when unset or unreachable, brain.py falls back to offline rules.
    bedrock_model_id: str = field(default_factory=lambda: os.environ.get("BEDROCK_MODEL_ID", ""))
    bedrock_region: str = field(default_factory=lambda: os.environ.get("BEDROCK_REGION", "ap-south-1"))
    # Display currency (default INR for an India-based user).
    currency: str = field(default_factory=lambda: os.environ.get("CURRENCY", "INR"))
    # Host/port for the HTTP server.
    host: str = field(default_factory=lambda: os.environ.get("HOST", "127.0.0.1"))
    port: int = field(default_factory=lambda: int(os.environ.get("PORT", "8000")))


def load_config() -> Config:
    return Config()
