from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator


class TakeProfit(BaseModel):
    """Planitt TP targets."""

    tp1: float = Field(..., gt=0)
    tp2: float = Field(..., gt=0)
    tp3: float = Field(..., gt=0)


class PlanittSignal(BaseModel):
    """
    Strict Planitt outbound contract.

    Note: backend will set `status` and handle expiry.
    """

    model_config = ConfigDict(extra="forbid")

    asset: str
    signal_type: Literal["BUY", "SELL"]
    entry_range: list[float] = Field(min_length=2, max_length=2)
    stop_loss: float
    take_profit: TakeProfit
    risk_reward_ratio: str
    confidence: int = Field(..., ge=1, le=100)
    timeframe: str
    strategy: str
    reason: str
    validity: str

    @field_validator("entry_range")
    @classmethod
    def _validate_entry_range_sorted(cls, v: list[float]) -> list[float]:
        if len(v) != 2:
            raise ValueError("entry_range must have exactly 2 values")
        a, b = v
        if a <= 0 or b <= 0:
            raise ValueError("entry_range values must be positive")
        return [min(a, b), max(a, b)]

    @model_validator(mode="after")
    def _validate_rr_and_levels(self) -> "PlanittSignal":
        # Confidence is already range-checked by conint.
        if not re.match(r"^1:\d+(\.\d+)?$", self.risk_reward_ratio.strip()):
            raise ValueError("risk_reward_ratio must match pattern '1:<number>'")

        entry_low, entry_high = self.entry_range
        tp1, tp2, tp3 = self.take_profit.tp1, self.take_profit.tp2, self.take_profit.tp3

        if self.signal_type == "BUY":
            if not (self.stop_loss < entry_low):
                raise ValueError("For BUY, stop_loss must be below entry_range")
            # Require TP levels above the entry range.
            if not (tp1 > entry_high and tp2 > entry_high and tp3 > entry_high):
                raise ValueError("For BUY, tp1/tp2/tp3 must be above entry_range")
            if not (tp1 < tp2 < tp3):
                raise ValueError("For BUY, tp1 < tp2 < tp3 is required")
        else:  # SELL
            if not (self.stop_loss > entry_high):
                raise ValueError("For SELL, stop_loss must be above entry_range")
            # Require TP levels below the entry range.
            if not (tp1 < entry_low and tp2 < entry_low and tp3 < entry_low):
                raise ValueError("For SELL, tp1/tp2/tp3 must be below entry_range")
            if not (tp3 < tp2 < tp1):
                raise ValueError("For SELL, tp3 < tp2 < tp1 is required")

        # Ensure RR is >= 1.5 at least against the moderate tp2.
        try:
            rr_num = float(self.risk_reward_ratio.split(":", 1)[1])
        except Exception as e:  # pragma: no cover
            raise ValueError("Unable to parse risk_reward_ratio") from e

        # Conservative check: tp2 distance to entry midpoint.
        entry_mid = (entry_low + entry_high) / 2.0
        risk = abs(entry_mid - self.stop_loss)
        reward = abs(tp2 - entry_mid)
        rr_actual = reward / max(risk, 1e-9)
        if rr_num < 1.0 or rr_actual < 1.0:
            raise ValueError("Risk/reward appears inconsistent with levels")

        return self

    @field_validator("confidence", mode="before")
    @classmethod
    def _normalize_confidence(cls, v: Any) -> int:
        if isinstance(v, bool):  # pragma: no cover
            raise ValueError("Invalid confidence type")
        if isinstance(v, int):
            return v
        if isinstance(v, float):
            if 0.0 <= v <= 1.0:
                return int(round(v * 100))
            return int(round(v))
        if isinstance(v, str):
            vv = v.strip()
            try:
                f = float(vv)
            except ValueError as e:  # pragma: no cover
                raise ValueError("confidence must be numeric") from e
            if 0.0 <= f <= 1.0:
                return int(round(f * 100))
            return int(round(f))
        raise ValueError("confidence must be a number")


class PlanittLLMDecision(BaseModel):
    """
    What the Ollama model should return.

    We keep numeric execution levels (entry_range/SL/TPs) computed deterministically in Python,
    but still require the LLM to be strict: ONLY JSON matching this schema, or exactly `NO TRADE`.
    """

    model_config = ConfigDict(extra="forbid")

    signal_type: Literal["BUY", "SELL"]
    confidence: int = Field(..., ge=1, le=100)
    strategy: str
    reason: str
    validity: str
    risk_reward_ratio: str

    @model_validator(mode="after")
    def _validate_rr_pattern(self) -> "PlanittLLMDecision":
        if not re.match(r"^1:\d+(\.\d+)?$", self.risk_reward_ratio.strip()):
            raise ValueError("risk_reward_ratio must match pattern '1:<number>'")
        return self

    @field_validator("confidence", mode="before")
    @classmethod
    def _normalize_confidence(cls, v: Any) -> int:
        """
        Accept either:
        - integer 1..100
        - float 0..1 (e.g. 0.82)
        - float 1..100
        """

        if isinstance(v, bool):  # pragma: no cover
            raise ValueError("Invalid confidence type")
        if isinstance(v, (int,)):
            return int(v)
        if isinstance(v, float):
            if 0.0 <= v <= 1.0:
                return int(round(v * 100))
            return int(round(v))
        if isinstance(v, str):
            vv = v.strip()
            try:
                f = float(vv)
            except ValueError as e:  # pragma: no cover
                raise ValueError("confidence must be numeric") from e
            if 0.0 <= f <= 1.0:
                return int(round(f * 100))
            return int(round(f))
        raise ValueError("confidence must be a number")


@dataclass(frozen=True)
class PlanittParseResult:
    """Result of parsing an Ollama response (signal or decision)."""

    model: Optional[Any]
    dropped_reason: Optional[str] = None


_JSON_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.IGNORECASE | re.DOTALL)


def _extract_json_candidate(raw: str) -> str:
    raw = raw.strip()
    if not raw:
        return raw

    # Remove code fences if present.
    m = _JSON_FENCE_RE.search(raw)
    if m:
        return m.group(1).strip()

    # Some models wrap JSON in a larger message; best-effort locate first/last braces.
    if "{" in raw and "}" in raw:
        start = raw.find("{")
        end = raw.rfind("}")
        if start != -1 and end != -1 and end > start:
            return raw[start : end + 1]

    return raw


def parse_planitt_llm_output(raw: Any) -> PlanittParseResult:
    """
    Parse Ollama output into a strict PlanittSignal.

    Contract:
    - If the model returns NO TRADE, return (model=None, dropped_reason="no_trade")
    - Otherwise, the model must return strict JSON matching PlanittSignal.
    """

    if raw is None:
        return PlanittParseResult(model=None, dropped_reason="empty_output")

    raw_str = str(raw).strip()
    if not raw_str:
        return PlanittParseResult(model=None, dropped_reason="empty_output")

    if raw_str.upper() == "NO TRADE" or "NO TRADE" in raw_str.upper():
        return PlanittParseResult(model=None, dropped_reason="no_trade")

    # Best-effort JSON extraction and strict validation.
    candidate = _extract_json_candidate(raw_str)
    try:
        data = json.loads(candidate)
    except json.JSONDecodeError as e:
        return PlanittParseResult(model=None, dropped_reason=f"invalid_json: {e}")

    try:
        model = PlanittSignal.model_validate(data)
    except ValidationError as e:
        return PlanittParseResult(model=None, dropped_reason=f"schema_validation_failed: {e.errors()}")

    return PlanittParseResult(model=model)


def parse_planitt_llm_decision(raw: Any) -> PlanittParseResult:
    """
    Parse Ollama decision output into (model=PlanittLLMDecision) semantics.

    Reuses PlanittParseResult.model type but stores PlanittLLMDecision.
    """

    if raw is None:
        return PlanittParseResult(model=None, dropped_reason="empty_output")

    raw_str = str(raw).strip()
    if not raw_str:
        return PlanittParseResult(model=None, dropped_reason="empty_output")

    if raw_str.upper() == "NO TRADE" or "NO TRADE" in raw_str.upper():
        return PlanittParseResult(model=None, dropped_reason="no_trade")

    candidate = _extract_json_candidate(raw_str)
    try:
        data = json.loads(candidate)
    except json.JSONDecodeError as e:
        return PlanittParseResult(model=None, dropped_reason=f"invalid_json: {e}")

    try:
        model = PlanittLLMDecision.model_validate(data)
    except ValidationError as e:
        return PlanittParseResult(model=None, dropped_reason=f"schema_validation_failed: {e.errors()}")

    return PlanittParseResult(model=model)


_VALIDITY_RE = re.compile(
    r"(?P<min>\d+(?:\.\d+)?)\s*-\s*(?P<max>\d+(?:\.\d+)?)\s*(?P<unit>hour|hours|minute|minutes|day|days)",
    re.IGNORECASE,
)
_VALIDITY_SINGLE_RE = re.compile(
    r"(?P<value>\d+(?:\.\d+)?)\s*(?P<unit>hour|hours|minute|minutes|day|days)",
    re.IGNORECASE,
)


def validity_to_max_ttl_seconds(validity: str) -> Optional[int]:
    """
    Convert a validity string (e.g. "2-4 hours") into a TTL in seconds.

    We use the *maximum* duration to avoid expiring slightly early.
    """

    if not validity:
        return None

    v = validity.strip().lower()
    m = _VALIDITY_RE.search(v)
    if m:
        max_val = float(m.group("max"))
        unit = m.group("unit")
    else:
        m2 = _VALIDITY_SINGLE_RE.search(v)
        if not m2:
            return None
        max_val = float(m2.group("value"))
        unit = m2.group("unit")

    if unit.startswith("hour"):
        return int(max_val * 3600)
    if unit.startswith("minute"):
        return int(max_val * 60)
    if unit.startswith("day"):
        return int(max_val * 86400)
    return None


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def compute_expires_at(created_at: datetime, validity: str) -> Optional[datetime]:
    ttl_seconds = validity_to_max_ttl_seconds(validity)
    if ttl_seconds is None:
        return None
    return created_at + timedelta(seconds=ttl_seconds)

