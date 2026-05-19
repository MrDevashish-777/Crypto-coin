from __future__ import annotations

import os
from datetime import datetime, timezone
from uuid import uuid4

from dotenv import load_dotenv
from pymongo import MongoClient


def main() -> None:
    load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "..", "..", ".env"), override=False)
    load_dotenv(override=False)
    mongo_uri = os.environ.get("MONGODB_URI")
    db_name = os.environ.get("MONGODB_DB_NAME", "planitt")
    if not mongo_uri:
        raise RuntimeError("MONGODB_URI is required")

    client = MongoClient(mongo_uri)
    db = client[db_name]
    run_id = f"crypto-{uuid4().hex}"
    now = datetime.now(timezone.utc)

    crypto_news = list(
        db["news"].find({"is_published": True, "asset_class": "CRYPTO"}).sort("published_at", -1).limit(150)
    )
    crypto_signals = list(
        db["signals"]
        .find({"is_published": True, "asset_class": "CRYPTO"})
        .sort([("generated_at", -1), ("timestamp", -1)])
        .limit(200)
    )
    etf_rows = []
    ipo_rows = []
    for row in crypto_news[:50]:
        symbol = str(row.get("symbol") or "CRYPTO-ETF")
        etf_rows.append(
            {
                "name": row.get("title") or symbol,
                "symbol": symbol,
                "price": float(row.get("sentiment_score") or 0.0),
                "aumCr": float(row.get("relevance_score") or 0.0) * 100,
                "source": "crypto_bot",
                "generated_at": now,
                "as_of": now,
                "pipeline_run_id": run_id,
            }
        )
    for row in crypto_news[:25]:
        ipo_rows.append(
            {
                "name": row.get("title") or "Crypto Listing",
                "band": row.get("band") or "NA",
                "size": row.get("issue_size") or "NA",
                "gmp": float(row.get("sentiment_score") or 0.0),
                "sub": row.get("subscription") or "NA",
                "openDate": row.get("published_at") or now,
                "source": "crypto_bot",
                "generated_at": now,
                "as_of": now,
                "pipeline_run_id": run_id,
            }
        )

    for row in etf_rows:
        db["market_etf_feed"].update_one({"symbol": row["symbol"]}, {"$set": row}, upsert=True)
    for row in ipo_rows:
        db["market_ipo_feed"].update_one({"name": row["name"], "openDate": row["openDate"]}, {"$set": row}, upsert=True)

    # Produce crypto-backed stocks-style snapshots for cross-asset dashboards.
    crypto_snapshots = []
    for row in crypto_signals:
        symbol = str(row.get("symbol") or "").upper()
        if not symbol:
            continue
        snapshot = {
            "symbol": symbol,
            "name": row.get("display_name") or symbol,
            "sector": "Crypto",
            "ltp": float(row.get("entry_price") or 0.0),
            "changePct": float(row.get("pnl_r_multiple") or 0.0),
            "volume": float(row.get("confidence_score") or 0.0) * 100,
            "marketCapCr": float(row.get("risk_reward_ratio") or 0.0),
            "high52w": row.get("high_52w"),
            "low52w": row.get("low_52w"),
            "source": "crypto_bot",
            "generated_at": row.get("generated_at") or now,
            "as_of": row.get("timestamp") or now,
            "pipeline_run_id": run_id,
        }
        crypto_snapshots.append(snapshot)
        db["market_stocks_snapshots"].update_one(
            {"symbol": snapshot["symbol"], "as_of": snapshot["as_of"]},
            {"$set": snapshot},
            upsert=True,
        )
        db["market_stock_details"].update_one({"symbol": snapshot["symbol"]}, {"$set": snapshot}, upsert=True)

    print(
        f"published etf_rows={len(etf_rows)} ipo_rows={len(ipo_rows)} "
        f"crypto_snapshots={len(crypto_snapshots)} run_id={run_id}"
    )


if __name__ == "__main__":
    main()

