"""Weekly/daily signal quota and token allocation (SOP §4, §8)."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

from config.constants import LOW_CAP_SYMBOLS, MAJOR_SYMBOLS
from config.settings import settings

logger = logging.getLogger(__name__)

_ALLOC_TOLERANCE = 0.04


@dataclass(frozen=True)
class AllocationStats:
    total: int
    btc: int
    majors: int
    btc_pct: float
    majors_pct: float

    @property
    def needs_btc(self) -> bool:
        return self.btc_pct < settings.MIN_WEEKLY_BTC_PCT - _ALLOC_TOLERANCE

    @property
    def needs_majors(self) -> bool:
        return self.majors_pct < settings.MIN_WEEKLY_MAJORS_PCT - _ALLOC_TOLERANCE

    @property
    def majors_over_cap(self) -> bool:
        return self.majors_pct > settings.MAX_WEEKLY_MAJORS_PCT + _ALLOC_TOLERANCE


def weekly_allocation_stats(recent: list[dict[str, str]]) -> AllocationStats:
    n = len(recent)
    if n == 0:
        return AllocationStats(total=0, btc=0, majors=0, btc_pct=0.0, majors_pct=0.0)
    btc = sum(1 for p in recent if p["symbol"] == "BTC")
    majors = sum(1 for p in recent if p["symbol"] in MAJOR_SYMBOLS)
    return AllocationStats(
        total=n,
        btc=btc,
        majors=majors,
        btc_pct=btc / n,
        majors_pct=majors / n,
    )


def projected_stats(recent: list[dict[str, str]], symbol: str) -> AllocationStats:
    projected = list(recent) + [{"symbol": symbol.upper(), "at": datetime.now(timezone.utc).isoformat()}]
    return weekly_allocation_stats(projected)


def filter_publish_queue(
    publish_order: list[tuple[Any, ...]],
    stats: AllocationStats,
) -> tuple[list[tuple[Any, ...]], str | None]:
    """Restrict publish attempts when weekly BTC/majors mix is off SOP targets."""
    if not settings.ADVISOR_STRICT_ALLOCATION or stats.total < 3:
        return publish_order, None
    if stats.majors_over_cap:
        filtered = [item for item in publish_order if item[1] not in MAJOR_SYMBOLS]
        return filtered, "alts_only_majors_over_cap"
    if stats.needs_btc or stats.needs_majors:
        filtered = [item for item in publish_order if item[1] in MAJOR_SYMBOLS]
        return filtered, "majors_only_allocation_deficit"
    return publish_order, None


def majors_rank_boost(symbol: str, stats: AllocationStats) -> float:
    """Soft ranking boost when weekly majors/BTC share is below SOP targets."""
    sym = symbol.upper()
    boost = 0.0
    if sym in MAJOR_SYMBOLS:
        if stats.needs_majors:
            boost += 0.22
        elif stats.majors_over_cap:
            boost -= 0.18
    if sym == "BTC" and stats.needs_btc:
        boost += 0.14
    elif sym == "BTC" and stats.btc_pct >= settings.MIN_WEEKLY_BTC_PCT + _ALLOC_TOLERANCE:
        boost -= 0.05
    return boost


def is_scannable_symbol(symbol: str) -> tuple[bool, str | None]:
    sym = symbol.upper()
    if settings.ADVISOR_BLOCK_LOW_CAP_SYMBOLS and sym in LOW_CAP_SYMBOLS:
        return False, f"low_cap_blocked_{sym}"
    return True, None


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

    def stats(self, now: datetime | None = None) -> AllocationStats:
        return weekly_allocation_stats(self.recent_publishes(now))

    def can_publish(
        self,
        symbol: str,
        now: datetime | None = None,
        *,
        timeframe: str | None = None,
    ) -> tuple[bool, str | None]:
        now_ts = now or datetime.now(timezone.utc)
        recent = self.recent_publishes(now_ts)
        daily = self.recent_daily_publishes(now_ts)

        if len(daily) >= settings.MAX_DAILY_SIGNALS:
            return False, "daily_cap_reached"

        if len(recent) >= settings.MAX_WEEKLY_SIGNALS:
            return False, "weekly_cap_reached"

        sym = symbol.upper()
        ok_universe, universe_reason = is_scannable_symbol(sym)
        if not ok_universe:
            return False, universe_reason

        cooldown_hours = max(
            {
                "15m": settings.ADVISOR_SYMBOL_COOLDOWN_HOURS_15M,
                "4h": settings.ADVISOR_SYMBOL_COOLDOWN_HOURS_4H,
                "1d": settings.ADVISOR_SYMBOL_COOLDOWN_HOURS_1D,
            }.get(timeframe or "", settings.ADVISOR_SYMBOL_COOLDOWN_HOURS),
            0,
        )
        if cooldown_hours > 0:
            cooldown_cutoff = now_ts - timedelta(hours=cooldown_hours)
            if any(
                p.get("symbol") == sym and datetime.fromisoformat(p["at"]) >= cooldown_cutoff
                for p in recent
            ):
                return False, f"duplicate_symbol_cooldown_{cooldown_hours}h"

        if settings.ADVISOR_STRICT_ALLOCATION and len(recent) >= 3:
            projected = projected_stats(recent, sym)
            is_major = sym in MAJOR_SYMBOLS

            if is_major and projected.majors_pct > settings.MAX_WEEKLY_MAJORS_PCT + _ALLOC_TOLERANCE:
                return False, "majors_allocation_cap"

            if not is_major:
                if projected.needs_btc:
                    return False, "btc_allocation_deficit"
                if projected.needs_majors:
                    return False, "majors_allocation_deficit"

        return True, None

    def daily_publish_count(self, now: datetime | None = None) -> int:
        return len(self.recent_daily_publishes(now))

    def daily_slots_remaining(self, now: datetime | None = None) -> int:
        return max(0, settings.MAX_DAILY_SIGNALS - self.daily_publish_count(now))

    def allocation_summary(self, now: datetime | None = None) -> dict[str, Any]:
        stats = self.stats(now)
        return {
            "total_weekly": stats.total,
            "btc_count": stats.btc,
            "majors_count": stats.majors,
            "btc_pct": round(stats.btc_pct * 100, 1),
            "majors_pct": round(stats.majors_pct * 100, 1),
            "targets": {
                "btc_min_pct": round(settings.MIN_WEEKLY_BTC_PCT * 100, 1),
                "majors_min_pct": round(settings.MIN_WEEKLY_MAJORS_PCT * 100, 1),
                "majors_max_pct": round(settings.MAX_WEEKLY_MAJORS_PCT * 100, 1),
            },
        }
