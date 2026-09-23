"""Presentation/API settings, independent from the deterministic scoring policy."""

from dataclasses import dataclass
from math import isfinite


SUPPORTED_LANGUAGES = ("kk", "ru", "en")
DEFAULT_LANGUAGE = "ru"
WORDING_VARIANTS = ("direct", "coaching")


@dataclass(frozen=True)
class ExplanationConfig:
    model: str = "gpt-4.1-mini"
    timeout_seconds: float = 3.0
    max_output_tokens: int = 4096
    max_payload_bytes: int = 65536

    def __post_init__(self):
        if not isinstance(self.model, str) or not self.model.strip() or len(self.model) > 200:
            raise ValueError("model must be a nonempty model identifier")
        if any(character.isspace() for character in self.model):
            raise ValueError("model must not contain whitespace")
        if (isinstance(self.timeout_seconds, bool)
                or not isinstance(self.timeout_seconds, (int, float))
                or not isfinite(self.timeout_seconds) or not 0 < self.timeout_seconds <= 10):
            raise ValueError("timeout_seconds must be finite, positive and at most 10")
        for name in ("max_output_tokens", "max_payload_bytes"):
            if type(getattr(self, name)) is not int or getattr(self, name) <= 0:
                raise ValueError(name + " must be a positive integer")


DEFAULT_EXPLANATION_CONFIG = ExplanationConfig()
