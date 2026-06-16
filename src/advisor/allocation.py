"""Weekly/daily signal quota and token allocation (SOP §4, §8)."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from config.constants import MAJOR_SYMBOLS
from config.settings import settings

logger = logging.getLogger(__name__)


@dataclass
class WeeklyAllocationTracker:
    """In-memory publish counters; hydrate from DB on startup if needed."""

    published: list[dict[str, str]] = field(default_factory=list)

    def _week_start(self, now: datetime | None = None) -> datetime:
        now = now or datetime.now(timezone.utc)
        return now - timedelta(days=7)

    def _day_start(self, now: datetime | None = None) -> datetime:
        now = now or datetime.now(timezone.utc)
        return now - timedelta(hours=24)

    def recent_publishes(self, now: datetime | None = None) -> list[dict[str, str]]:
        cutoff = self._week_start(now)
        return [p for p in self.published if datetime.fromisoformat(p["at"]) >= cutoff]

    def recent_daily_publishes(self, now: datetime | None = None) -> list[dict[str, str]]:
        cutoff = self._day_start(now)
        return [p for p in self.published if datetime.fromisoformat(p["at"]) >= cutoff]

    def hydrate(self, records: list[dict[str, str]]) -> None:
        self.published = list(records)

    def record(self, symbol: str, *, at: datetime | None = None, timeframe: str | None = None) -> None:
        ts = (at or datetime.now(timezone.utc)).isoformat()
        entry: dict[str, str] = {"symbol": symbol.upper(), "at": ts}
        if timeframe:
            entry["timeframe"] = timeframe
        self.published.append(entry)

    def can_publish(self, symbol: str, now: datetime | None = None) -> tuple[bool, str | None]:
        now_ts = now or datetime.now(timezone.utc)
        recent = self.recent_publishes(now_ts)
        daily = self.recent_daily_publishes(now_ts)

        if len(daily) >= settings.MAX_DAILY_SIGNALS:
            return False, "daily_cap_reached"

        if len(recent) >= settings.MAX_WEEKLY_SIGNALS:
            return False, "weekly_cap_reached"

        sym = symbol.upper()
        cooldown_hours = max(settings.ADVISOR_SYMBOL_COOLDOWN_HOURS, 0)
        if cooldown_hours > 0:
            cooldown_cutoff = now_ts - timedelta(hours=cooldown_hours)
            if any(
                p.get("symbol") == sym and datetime.fromisoformat(p["at"]) >= cooldown_cutoff
                for p in recent
            ):
                return False, f"duplicate_symbol_cooldown_{cooldown_hours}h"

        n = len(recent)
        if n > 0 and settings.ADVISOR_STRICT_ALLOCATION:
            btc_count = sum(1 for p in recent if p["symbol"] == "BTC")
            majors_count = sum(1 for p in recent if p["symbol"] in MAJOR_SYMBOLS)
            projected_n = n + 1
            min_btc = int(projected_n * settings.MIN_WEEKLY_BTC_PCT)
            if sym == "BTC" and btc_count + 1 < min_btc and len(recent) >= settings.MAX_WEEKLY_SIGNALS - 2:
                pass
            elif projected_n >= 5:
                if btc_count / projected_n < settings.MIN_WEEKLY_BTC_PCT - 0.05 and sym != "BTC":
                    if btc_count < min_btc:
                        return False, "btc_allocation_deficit"
                if (majors_count + (1 if sym in MAJOR_SYMBOLS else 0)) / projected_n < settings.MIN_WEEKLY_MAJORS_PCT - 0.05:
                    if sym not in MAJOR_SYMBOLS and majors_count < int(projected_n * settings.MIN_WEEKLY_MAJORS_PCT):
                        return False, "majors_allocation_deficit"

        return True, None

    def daily_publish_count(self, now: datetime | None = None) -> int:
        return len(self.recent_daily_publishes(now))

    def daily_slots_remaining(self, now: datetime | None = None) -> int:
        return max(0, settings.MAX_DAILY_SIGNALS - self.daily_publish_count(now))
