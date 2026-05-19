"""Load versioned LLM prompt templates from config/prompts/."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

_PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"
_DEFAULT_ADVISOR_SYSTEM = _PROMPTS_DIR / "advisor_narrative_system.md"


@lru_cache(maxsize=8)
def load_prompt(name: str) -> str:
    """Load a prompt file by stem name (e.g. advisor_narrative_system)."""
    path = _PROMPTS_DIR / f"{name}.md"
    if not path.is_file():
        raise FileNotFoundError(f"Prompt not found: {path}")
    return path.read_text(encoding="utf-8").strip()


def load_advisor_narrative_system(*, override_path: str | None = None) -> str:
    """Return advisor narrative system prompt, optionally from a custom path."""
    if override_path:
        custom = Path(override_path)
        if custom.is_file():
            return custom.read_text(encoding="utf-8").strip()
    return load_prompt("advisor_narrative_system")
