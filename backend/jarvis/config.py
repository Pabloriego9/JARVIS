import os
import sys
from dataclasses import dataclass, field
from pathlib import Path

from platformdirs import user_data_path


def openai_key():
    value = os.getenv("JARVIS_OPENAI_API_KEY_2") or os.getenv("JARVIS_OPENAI_API_KEY", "")
    if value or sys.platform != "win32":
        return value
    import keyring

    return keyring.get_password("JARVIS", "openai") or ""


@dataclass
class Settings:
    data_dir: Path = field(
        default_factory=lambda: Path(os.getenv("JARVIS_DATA_DIR") or user_data_path("JARVIS"))
    )
    model: str = field(default_factory=lambda: os.getenv("JARVIS_MODEL", "gpt-6-astra"))
    api_key: str = field(default_factory=openai_key, repr=False)
    provider: str = field(default_factory=lambda: os.getenv("JARVIS_PROVIDER", "openai"))
    gemini_key: str = field(default_factory=lambda: os.getenv("JARVIS_GEMINI_API_KEY", ""), repr=False)
    gemini_model: str = field(default_factory=lambda: os.getenv("JARVIS_GEMINI_MODEL", ""))
    reasoning: str = field(default_factory=lambda: os.getenv("JARVIS_REASONING_EFFORT", "medium"))
    max_output: int = field(default_factory=lambda: int(os.getenv("JARVIS_MAX_OUTPUT_TOKENS", "2048")))
    task_tokens: int = field(default_factory=lambda: int(os.getenv("JARVIS_TASK_TOKEN_LIMIT", "32000")))
    daily_tokens: int = field(default_factory=lambda: int(os.getenv("JARVIS_DAILY_TOKEN_LIMIT", "100000")))
    max_steps: int = field(default_factory=lambda: int(os.getenv("JARVIS_MAX_STEPS", "12")))
    timezone: str = field(
        default_factory=lambda: os.getenv("JARVIS_TIMEZONE", "America/Argentina/Buenos_Aires")
    )
    windows_executor: str = field(default_factory=lambda: os.getenv("JARVIS_WINDOWS_EXECUTOR", ""))
    mcp_enabled: bool = field(
        default_factory=lambda: os.getenv("JARVIS_MCP_ENABLED", "false").lower() == "true"
    )
    mcp_headless: bool = field(
        default_factory=lambda: os.getenv("JARVIS_MCP_HEADLESS", "false").lower() == "true"
    )

    def prepare(self):
        self.data_dir.mkdir(parents=True, exist_ok=True, mode=0o700)

    @property
    def effective_model(self):
        return self.gemini_model if self.provider == "gemini" else self.model
