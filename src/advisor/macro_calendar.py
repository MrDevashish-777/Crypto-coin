"""Macroeconomic news calendar checking via ForexFactory."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone
import xml.etree.ElementTree as ET
from typing import Optional

import aiohttp
from dateutil import parser
from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)

FF_XML_URL = "https://nfs.faireconomy.media/ff_calendar_thisweek.xml"
CACHE_TTL_SECONDS = 3600  # 1 hour

class MacroCalendar:
    """Fetches and caches high-impact macro news events."""
    
    _instance: Optional[MacroCalendar] = None
    
    def __init__(self) -> None:
        self._events: list[dict] = []
        self._last_fetch: Optional[datetime] = None
        self._lock = asyncio.Lock()
        # Blackout period around high impact USD news (e.g. 60 mins before, 60 mins after)
        self.blackout_before_mins = 60
        self.blackout_after_mins = 60

    @classmethod
    def get_instance(cls) -> MacroCalendar:
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    async def _fetch_xml(self) -> str:
        """Fetch XML from ForexFactory."""
        async with aiohttp.ClientSession() as session:
            # ForexFactory blocks some default user agents, so we set a custom one
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
            async with session.get(FF_XML_URL, headers=headers, timeout=15) as response:
                if response.status != 200:
                    raise RuntimeError(f"FF Calendar returned {response.status}")
                return await response.text()

    async def _update_cache_if_needed(self) -> None:
        """Update internal cache if it's older than CACHE_TTL_SECONDS."""
        now = datetime.now(timezone.utc)
        if self._last_fetch and (now - self._last_fetch).total_seconds() < CACHE_TTL_SECONDS:
            return

        async with self._lock:
            # Double check inside lock
            if self._last_fetch and (now - self._last_fetch).total_seconds() < CACHE_TTL_SECONDS:
                return
            
            try:
                xml_data = await self._fetch_xml()
                root = ET.fromstring(xml_data)
                events = []
                
                for event in root.findall('event'):
                    impact = event.findtext('impact', '').strip().upper()
                    country = event.findtext('country', '').strip().upper()
                    date_str = event.findtext('date', '').strip()
                    time_str = event.findtext('time', '').strip()
                    title = event.findtext('title', '').strip()
                    
                    if impact == "HIGH" and country == "USD":
                        # FF XML format: date: MM-DD-YYYY, time: 08:30am (Eastern Time generally, wait, FF XML doesn't provide tz in the feed directly, but standard is Eastern)
                        # Actually, ForexFactory XML time is EST/EDT by default unless logged in (which we aren't).
                        # We will use dateutil parser and assume US/Eastern
                        dt_str = f"{date_str} {time_str}"
                        # Some events are "All Day" or "Tentative" where time isn't strict
                        if "All Day" in time_str or "Tentative" in time_str:
                            continue
                            
                        try:
                            # Parse as naive, then assign US/Eastern
                            dt_naive = parser.parse(dt_str)
                            dt_aware = dt_naive.replace(tzinfo=ZoneInfo("US/Eastern"))
                            dt_utc = dt_aware.astimezone(timezone.utc)
                            
                            events.append({
                                "title": title,
                                "time_utc": dt_utc
                            })
                        except Exception as e:
                            logger.warning("Failed to parse FF time %s: %s", dt_str, e)
                
                self._events = events
                self._last_fetch = now
                logger.info("Updated macro calendar cache. Found %d high-impact USD events.", len(self._events))
            except Exception as e:
                logger.error("Failed to update macro calendar: %s", e)
                # If we fail, we just don't blackout rather than crashing

    async def is_blackout_active(self, now: Optional[datetime] = None) -> tuple[bool, str]:
        """Check if `now` is within a blackout window of any high impact news."""
        await self._update_cache_if_needed()
        
        current_time = now or datetime.now(timezone.utc)
        
        for ev in self._events:
            ev_time: datetime = ev["time_utc"]
            window_start = ev_time - timedelta(minutes=self.blackout_before_mins)
            window_end = ev_time + timedelta(minutes=self.blackout_after_mins)
            
            if window_start <= current_time <= window_end:
                return True, f"High-impact macro event: {ev['title']} at {ev_time.strftime('%Y-%m-%d %H:%M UTC')}"
                
        return False, ""

macro_calendar = MacroCalendar.get_instance()
