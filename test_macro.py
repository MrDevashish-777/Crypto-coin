import asyncio
from src.advisor.macro_calendar import macro_calendar

async def test():
    is_blackout, reason = await macro_calendar.is_blackout_active()
    print(f"Blackout: {is_blackout}, Reason: {reason}")
    print(f"Events loaded: {len(macro_calendar._events)}")
    for ev in macro_calendar._events:
        print(f"{ev['time_utc']} - {ev['title']}")

asyncio.run(test())
