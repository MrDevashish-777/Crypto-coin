import asyncio
import logging
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from datetime import datetime, timezone
from config.settings import settings
from src.database.db import get_db
from src.planitt.mongo_collections import crypto_signals_collection

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def cleanup_duplicates():
    db = await get_db()
    coll = db[crypto_signals_collection()]
    
    # Get all open advisor signals
    cursor = coll.find({"status": "OPEN", "source_backend": "coindcx_advisor"})
    open_docs = await cursor.to_list(1000)
    
    # Group by symbol
    by_symbol = {}
    for doc in open_docs:
        sym = doc.get("symbol", "").upper()
        if sym not in by_symbol:
            by_symbol[sym] = []
        by_symbol[sym].append(doc)
        
    expired_count = 0
    now = datetime.now(timezone.utc).isoformat()
    
    for sym, docs in by_symbol.items():
        if len(docs) > 1:
            logger.info(f"Symbol {sym} has {len(docs)} OPEN signals. Cleaning up older ones...")
            
            # Sort by generated_at descending (newest first)
            def get_timestamp(d):
                ts_str = d.get("generated_at", "")
                try:
                    return datetime.fromisoformat(ts_str.replace("Z", "+00:00")).timestamp()
                except ValueError:
                    return 0
                    
            docs.sort(key=get_timestamp, reverse=True)
            
            # Keep index 0 open, mark rest as EXPIRED
            for old_doc in docs[1:]:
                sig_id = old_doc.get("signal_id")
                await coll.update_one(
                    {"signal_id": sig_id},
                    {
                        "$set": {
                            "status": "EXPIRED",
                            "outcome": "expired",
                            "closed_at": now,
                            "closure_reason": "duplicate_cleanup"
                        }
                    }
                )
                logger.info(f" -> Marked signal {sig_id} as EXPIRED")
                expired_count += 1

    logger.info(f"Cleanup complete. Set {expired_count} duplicate signals to EXPIRED.")

if __name__ == "__main__":
    asyncio.run(cleanup_duplicates())
