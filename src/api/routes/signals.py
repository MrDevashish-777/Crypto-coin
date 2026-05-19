"""
Signal API Routes
Endpoints for signal generation and retrieval
"""

from fastapi import APIRouter, Depends, HTTPException, Query, Path
from typing import Optional
import logging
import asyncio
from src.signals.signal import TradingSignal, SignalResponse
from config.constants import CRYPTO_PAIRS, TIMEFRAMES
from config.settings import settings
from src.api.middleware.internal_api_key import require_internal_api_key
from src.planitt.processor import PlanittProcessor
from datetime import datetime, timedelta, timezone
from src.database.db import get_db
from src.planitt.mongo_collections import crypto_signal_find_filter, crypto_signals_collection
from src.planitt.persistence import close_completed_signals

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/v1/signals",
    tags=["signals"],
    dependencies=[Depends(require_internal_api_key)],
)

planitt_processor: Optional[PlanittProcessor] = None


async def get_planitt_processor() -> PlanittProcessor:
    """Get (singleton) Planitt processing pipeline."""
    global planitt_processor
    if planitt_processor is None:
        planitt_processor = PlanittProcessor()
    return planitt_processor


async def shutdown_planitt_processor() -> None:
    """Shutdown Planitt processor resources."""
    global planitt_processor
    if planitt_processor is not None:
        await planitt_processor.close()
        planitt_processor = None


def _parse_rr_ratio(value) -> float:
    """Parse risk-reward values like '1:2.0' or numeric forms."""
    if value is None:
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip()
    if not text:
        return 0.0
    if ":" in text:
        parts = text.split(":", 1)
        try:
            right = float(parts[1].strip())
            return right
        except Exception:
            return 0.0
    try:
        return float(text)
    except Exception:
        return 0.0


@router.get("/latest")
async def signals_latest(limit: int = 25):
    """
    Gateway-consumed endpoint:
    GET /api/v1/signals/latest?limit=...
    Returns { signals: [...], count: n } from MongoDB.
    """
    db = await get_db()
    coll = db[crypto_signals_collection()]
    query = crypto_signal_find_filter(
        {"status": "OPEN", "source_backend": "crypto_bot", "is_published": True}
    )
    cursor = coll.find(query).sort("timestamp", -1).limit(limit)
    docs = await cursor.to_list(limit)

    for d in docs:
        d.pop("_id", None)
        for k, v in list(d.items()):
            if isinstance(v, datetime):
                d[k] = v.isoformat()

    return {"signals": docs, "count": len(docs)}


@router.get("/history")
async def signals_history(limit: int = 100, days: int = 7):
    """
    Read historical signals using ISO string timestamps in MongoDB.
    Returns { signals: [...], count: n }.
    """
    db = await get_db()
    coll = db[crypto_signals_collection()]

    cutoff_dt = datetime.now(timezone.utc) - timedelta(days=days)
    query = crypto_signal_find_filter(
        {
            "status": "OPEN",
            "source_backend": "crypto_bot",
            "is_published": True,
            "timestamp": {"$gte": cutoff_dt},
        }
    )

    cursor = coll.find(query).sort("timestamp", -1).limit(limit)
    docs = await cursor.to_list(limit)

    for d in docs:
        d.pop("_id", None)
        for k, v in list(d.items()):
            if isinstance(v, datetime):
                d[k] = v.isoformat()

    return {"signals": docs, "count": len(docs)}


@router.get("", response_model=SignalResponse)
async def get_signals(
    symbol: Optional[str] = Query(None, description="Crypto symbol (BTC, ETH, etc)"),
    timeframe: Optional[str] = Query("15m", description="Timeframe (1m, 5m, 15m, 1h, 4h, 1d)"),
    limit: int = Query(10, description="Number of signals to return"),
):
    """
    Get recently generated signals from MongoDB.
    """
    try:
        db = await get_db()
        coll = db[crypto_signals_collection()]
        query: dict = {"source_backend": "crypto_bot"}
        if symbol:
            query["symbol"] = symbol
        if timeframe:
            query["timeframe"] = timeframe
        docs = await coll.find(crypto_signal_find_filter(query), {"_id": 0}).sort("timestamp", -1).limit(limit).to_list(limit)
        signals = docs

        return SignalResponse(
            success=True,
            data=signals,
            message=f"Retrieved {len(signals)} signals"
        )
    except Exception as e:
        logger.error(f"Error retrieving signals: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/generate", response_model=SignalResponse)
async def generate_signal(
    symbol: str = Query(..., description="Crypto symbol (BTC, ETH, etc)"),
    timeframe: str = Query("15m", description="Timeframe"),
    strategy: str = Query("planitt", description="(Deprecated) strategy hint"),
):
    """
    Generate a trading signal for a symbol
    
    Query Parameters:
    - symbol: Cryptocurrency symbol (required)
    - timeframe: Analysis timeframe (default: 15m)
    - strategy: Strategy to use (default: rsi)
    """
    try:
        if symbol not in CRYPTO_PAIRS:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported symbol: {symbol}. Supported: {list(CRYPTO_PAIRS.keys())}",
            )
        if timeframe not in TIMEFRAMES:
            raise HTTPException(status_code=400, detail=f"Unsupported timeframe: {timeframe}")

        correlation_id = f"planitt-{int(datetime.utcnow().timestamp() * 1000)}-{symbol}"

        processor = await get_planitt_processor()
        payload = await processor.generate_and_forward(
            symbol=symbol,
            timeframe=timeframe,
            correlation_id=correlation_id,
        )

        if payload is None:
            return SignalResponse(success=False, message="NO TRADE - conditions unclear")

        await close_completed_signals(symbol, timeframe, float(payload["entry_range"][0]))

        return SignalResponse(
            success=True,
            data=payload,
            message=f"Signal emitted for {payload.get('asset')}",
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating signal: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/generate/popular", response_model=SignalResponse)
async def generate_popular_signals(
    timeframe: str = Query("15m", description="Timeframe"),
    limit: int = Query(10, description="How many popular coins to scan"),
):
    """
    Generate signals for a basket of popular coins.
    Persists emitted signals to MongoDB through the regular generate flow.
    """
    if timeframe not in TIMEFRAMES:
        raise HTTPException(status_code=400, detail=f"Unsupported timeframe: {timeframe}")

    symbols = list(CRYPTO_PAIRS.keys())[: max(1, min(limit, len(CRYPTO_PAIRS)))]
    emitted: list[dict] = []
    dropped: list[str] = []
    failed: list[dict] = []

    for symbol in symbols:
        try:
            result = await generate_signal(symbol=symbol, timeframe=timeframe, strategy="planitt")
            if result.success and isinstance(result.data, dict):
                emitted.append(result.data)
            else:
                dropped.append(symbol)
        except HTTPException as exc:
            failed.append({"symbol": symbol, "error": str(exc.detail)})
        except Exception as exc:  # pragma: no cover
            failed.append({"symbol": symbol, "error": str(exc)})
        await asyncio.sleep(0.05)

    return SignalResponse(
        success=True,
        data={
            "timeframe": timeframe,
            "requested_symbols": symbols,
            "emitted_count": len(emitted),
            "dropped_count": len(dropped),
            "failed_count": len(failed),
            "emitted": emitted,
            "dropped": dropped,
            "failed": failed,
        },
        message=f"Popular scan complete: emitted={len(emitted)} dropped={len(dropped)} failed={len(failed)}",
    )


@router.post("/generate/multi-horizon", response_model=SignalResponse)
async def generate_multi_horizon(symbol: str = Query(..., description="Crypto symbol")):
    """Generate signals for scalp, swing, and position horizons."""
    if symbol not in CRYPTO_PAIRS:
        raise HTTPException(status_code=400, detail=f"Unsupported symbol: {symbol}")

    processor = await get_planitt_processor()
    horizons = {
        "scalp": settings.SCALP_TIMEFRAMES,
        "swing": settings.SWING_TIMEFRAMES,
        "position": settings.POSITION_TIMEFRAMES,
    }
    emitted: dict[str, list[dict]] = {"scalp": [], "swing": [], "position": []}
    for horizon, timeframes in horizons.items():
        for timeframe in timeframes:
            corr = f"multi-{horizon}-{int(datetime.utcnow().timestamp() * 1000)}-{symbol}-{timeframe}"
            payload = await processor.generate_and_forward(symbol=symbol, timeframe=timeframe, correlation_id=corr)
            if isinstance(payload, dict):
                emitted[horizon].append(payload)
    return SignalResponse(success=True, data=emitted, message=f"Generated multi-horizon signals for {symbol}")


@router.get("/analyze/{symbol}", response_model=SignalResponse)
async def analyze_symbol(
    symbol: str,
    timeframe: str = Query("1h", description="Timeframe for analysis"),
):
    """
    Get deep AI analysis for a crypto symbol
    """
    if symbol not in CRYPTO_PAIRS:
        raise HTTPException(status_code=400, detail=f"Unsupported symbol: {symbol}")
    
    try:
        processor = await get_planitt_processor()
        corr = f"analyze-{int(datetime.utcnow().timestamp() * 1000)}-{symbol}-{timeframe}"
        payload = await processor.generate_and_forward(symbol=symbol, timeframe=timeframe, correlation_id=corr)
        if payload is None:
            return SignalResponse(success=False, data={"symbol": symbol, "timeframe": timeframe}, message="NO TRADE")
        return SignalResponse(success=True, data=payload, message=f"Analysis generated for {symbol}")
    except Exception as e:
        logger.error(f"Error analyzing symbol {symbol}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/symbols")
async def get_supported_symbols():
    """Get list of supported symbols"""
    data = {
        "symbols": list(CRYPTO_PAIRS.keys()),
        "count": len(CRYPTO_PAIRS)
    }
    return SignalResponse(
        success=True,
        data=data,
        message=f"Found {len(CRYPTO_PAIRS)} supported symbols"
    )


@router.get("/timeframes")
async def get_supported_timeframes():
    """Get list of supported timeframes"""
    data = {
        "timeframes": list(TIMEFRAMES.keys()),
        "count": len(TIMEFRAMES)
    }
    return SignalResponse(
        success=True,
        data=data,
        message=f"Found {len(TIMEFRAMES)} supported timeframes"
    )


@router.get("/strategies")
async def get_supported_strategies():
    """Get list of supported strategies"""
    data = {
        "strategies": ["planitt"],
        "descriptions": {
            "planitt": "Unified confluence + calibrated confidence pipeline",
        }
    }
    return SignalResponse(
        success=True,
        data=data,
        message="Available trading strategies"
    )


@router.get("/market/status", response_model=SignalResponse)
async def get_market_status():
    """Get real-time status of the crypto market"""
    try:
        db = await get_db()
        coll = db[crypto_signals_collection()]
        open_count = await coll.count_documents(
            crypto_signal_find_filter({"status": "OPEN", "source_backend": "crypto_bot"})
        )
        published_count = await coll.count_documents(
            crypto_signal_find_filter(
                {"status": "OPEN", "source_backend": "crypto_bot", "is_published": True}
            )
        )
        status = {"open_signals": open_count, "published_open_signals": published_count}
        return SignalResponse(
            success=True,
            data=status,
            message="Market status retrieved"
        )
    except Exception as e:
        logger.error(f"Error fetching market status: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{symbol}", response_model=SignalResponse)
async def get_signals_for_symbol(
    symbol: str = Path(..., description="Crypto symbol"),
    limit: int = Query(10, description="Number of results"),
):
    """Get signals for a specific symbol"""
    if symbol not in CRYPTO_PAIRS:
        raise HTTPException(status_code=400, detail=f"Unsupported symbol: {symbol}")

    try:
        db = await get_db()
        coll = db[crypto_signals_collection()]
        signals = await coll.find(
            crypto_signal_find_filter({"symbol": symbol, "source_backend": "crypto_bot"}),
            {"_id": 0},
        ).sort("timestamp", -1).limit(limit).to_list(limit)

        return SignalResponse(
            success=True,
            data={
                "symbol": symbol,
                "signals": signals,
                "count": len(signals)
            },
            message=f"Retrieved {len(signals)} signals for {symbol}"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching signals for {symbol}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
