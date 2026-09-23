"""Configuration is read once when the app is created, never from request input."""
from dataclasses import dataclass, field
import json
import os
from pathlib import Path
from typing import Dict, Optional, Tuple

ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class Settings:
    data_dir: Path = ROOT / "data" / "career_quest_dataset"
    runtime_state_path: Optional[Path] = ROOT / ".runtime" / "state.json"
    auth_disabled: bool = False
    hr_token: Optional[str] = None
    employee_tokens: Dict[str, str] = field(default_factory=dict)
    upload_max_bytes: int = 10 * 1024 * 1024
    recommendation_timeout_seconds: float = 9.0
    cors_origins: Tuple[str, ...] = (
        "http://localhost:5173", "http://127.0.0.1:5173",
        "http://localhost:3000", "http://127.0.0.1:3000",
    )

    def __post_init__(self):
        if self.hr_token is not None and (
            not isinstance(self.hr_token, str) or not self.hr_token
            or any(character.isspace() for character in self.hr_token)
        ):
            raise ValueError("HR_API_TOKEN must be a nonempty token without whitespace")
        if not isinstance(self.employee_tokens, dict) or any(
            not isinstance(token, str) or not token.strip()
            or any(character.isspace() for character in token)
            or not isinstance(employee_id, str) or not employee_id.strip()
            for token, employee_id in self.employee_tokens.items()
        ):
            raise ValueError("EMPLOYEE_TOKENS_JSON must map nonempty tokens to employee IDs")
        if self.hr_token and self.hr_token in self.employee_tokens:
            raise ValueError("HR and employee tokens must be different")
        if self.upload_max_bytes <= 0 or self.recommendation_timeout_seconds <= 0:
            raise ValueError("Upload size and recommendation timeout must be positive")
        if self.runtime_state_path is not None:
            source_files = {Path(self.data_dir).resolve() / name for name in (
                "employees.json", "skills.json", "events.json", "activity_history.csv"
            )}
            if Path(self.runtime_state_path).resolve() in source_files:
                raise ValueError("Runtime state must not overwrite an official dataset file")

    @classmethod
    def from_env(cls):
        raw_auth = os.getenv("CAREER_QUEST_AUTH_DISABLED", "false").lower()
        if raw_auth not in {"true", "false", "1", "0", "yes", "no"}:
            raise ValueError("CAREER_QUEST_AUTH_DISABLED must be true or false")
        try:
            tokens = json.loads(os.getenv("EMPLOYEE_TOKENS_JSON", "{}"))
        except json.JSONDecodeError as exc:
            raise ValueError("EMPLOYEE_TOKENS_JSON is not valid JSON") from exc
        raw_state = os.getenv("CAREER_QUEST_STATE_PATH")
        state_path = (ROOT / ".runtime" / "state.json" if raw_state is None else
                      Path(raw_state).expanduser() if raw_state.strip() else None)
        defaults = cls()
        origins = os.getenv("CAREER_QUEST_CORS_ORIGINS")
        return cls(
            data_dir=Path(os.getenv("CAREER_QUEST_DATA_DIR", str(defaults.data_dir))).expanduser(),
            runtime_state_path=state_path,
            auth_disabled=raw_auth in {"true", "1", "yes"},
            hr_token=os.getenv("HR_API_TOKEN") or None,
            employee_tokens=tokens,
            upload_max_bytes=int(os.getenv("CAREER_QUEST_UPLOAD_MAX_BYTES", str(defaults.upload_max_bytes))),
            recommendation_timeout_seconds=float(os.getenv("CAREER_QUEST_RECOMMENDATION_TIMEOUT", "9")),
            cors_origins=tuple(origin.strip() for origin in origins.split(",") if origin.strip())
            if origins is not None else defaults.cors_origins,
        )
