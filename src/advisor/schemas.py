"""Advisor signal contract — SOP + chart guidelines."""

from __future__ import annotations  # noqa: I001

import re
import uuid
from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

TradeHorizon = Literal["intraday", "swing"]
Direction = Literal["BUY", "SELL"]


class AdvisorSignal(BaseModel):
    """Published advisor futures call matching SOP structure."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, validate_assignment=True)

    signal_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    pair: str
    symbol: str
    margin_currency: str
    direction: Direction
    trade_horizon: TradeHorizon
    timeframe: str

    entry_low: float = Field(..., gt=0)
    entry_high: float = Field(..., gt=0)
    stop_loss: float = Field(..., gt=0)
    target: float = Field(..., gt=0)

    sl_pct: float = Field(..., gt=0, description="Spot SL distance % from entry mid")
    tp_pct: float = Field(..., gt=0, description="Spot TP distance % from entry mid")
    leverage: float = Field(..., ge=2.0, description="SOP: 20 / sl_pct")
    risk_reward: str
    confidence: float = Field(..., ge=0.0, le=1.0)

    valid_until_ist: datetime
    generated_at: datetime
    live_price_at_signal: float = Field(..., gt=0)

    indicators: list[str] = Field(default_factory=list, max_length=2)
    setup_type: str
    confluence_hits: list[str] = Field(default_factory=list)

    reason_why_token: str
    reason_entry: str
    reason_monitor: str

    pdf_path: Optional[str] = None
    chart_path: Optional[str] = None

    @field_validator("indicators")
    @classmethod
    def _max_two_indicators(cls, v: list[str]) -> list[str]:
        return v[:2]

    @model_validator(mode="after")
    def _validate_levels(self) -> AdvisorSignal:
        low, high = sorted([self.entry_low, self.entry_high])
        object.__setattr__(self, "entry_low", low)
        object.__setattr__(self, "entry_high", high)

        entry_mid = (low + high) / 2.0
        width_pct = (high - low) / entry_mid * 100.0
        if not (0.5 <= width_pct <= 1.5):
            raise ValueError(f"entry band width {width_pct:.2f}% outside SOP 0.5-1.5%")

        if not (low <= self.live_price_at_signal <= high):
            raise ValueError("live price must be inside entry range at signal time")

        if self.direction == "BUY":
            if not (self.stop_loss < low and self.target > high):
                raise ValueError("BUY: SL below entry, target above entry")
        else:
            if not (self.stop_loss > high and self.target < low):
                raise ValueError("SELL: SL above entry, target below entry")

        if not re.match(r"^1:\d+(\.\d+)?$", self.risk_reward.strip()):
            raise ValueError("risk_reward must match 1:X")

        lev_expected = 20.0 / self.sl_pct
        if abs(self.leverage - lev_expected) > 0.5:
            raise ValueError("leverage must equal 20/sl_pct per SOP")

        return self

    def entry_range(self) -> list[float]:
        return [self.entry_low, self.entry_high]
