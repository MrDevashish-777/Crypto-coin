import asyncio
from src.database.db import get_db
from src.planitt.mongo_collections import crypto_signals_collection

async def main():
    db = await get_db()
    coll = db[crypto_signals_collection()]
    docs = await coll.find({"status": "OPEN", "source_backend": "coindcx_advisor"}).to_list(1000)
    print(f"Total open signals: {len(docs)}")
    for d in docs:
        print(f"{d.get('symbol')} | {d.get('direction')} | generated_at: {d.get('generated_at')}")

asyncio.run(main())
