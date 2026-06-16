"""Advisor API — CoinDCX futures PDF signal generation."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from config.constants import CRYPTO_PAIRS, TIMEFRAMES
from config.settings import settings
from src.advisor.processor import AdvisorProcessor
from src.api.middleware.internal_api_key import require_internal_api_key
logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/v1/advisor",
    tags=["advisor"],
)

_advisor_processor: Optional[AdvisorProcessor] = None


async def get_advisor_processor() -> AdvisorProcessor:
    global _advisor_processor
    if _advisor_processor is None:
        _advisor_processor = AdvisorProcessor()
    return _advisor_processor


async def shutdown_advisor_processor() -> None:
    global _advisor_processor
    if _advisor_processor is not None:
        await _advisor_processor.close()
        _advisor_processor = None


class GenerateRequest(BaseModel):
    symbol: str = Field(..., min_length=2, max_length=12)
    timeframe: str = Field(default="1h")
    margin_currency: str | None = None
    force: bool = False


@router.post("/generate", dependencies=[Depends(require_internal_api_key)])
async def generate_advisor_signal(body: GenerateRequest):
    """Generate one SOP-compliant signal + PDF for symbol/timeframe."""
    if body.symbol.upper() not in CRYPTO_PAIRS:
        raise HTTPException(400, f"Unsupported symbol: {body.symbol}")
    if body.timeframe not in TIMEFRAMES:
        raise HTTPException(400, f"Unsupported timeframe: {body.timeframe}")

    proc = await get_advisor_processor()
    if body.margin_currency:
        proc.margin_currency = body.margin_currency.upper()
        proc.data_fetcher.margin_currency = proc.margin_currency

    result = await proc.generate_signal(
        body.symbol.upper(),
        body.timeframe,
        force=body.force,
    )
    if not result.get("ok"):
        raise HTTPException(422, detail=result.get("reject_reason", "rejected"))
    return result


@router.post("/scan", dependencies=[Depends(require_internal_api_key)])
async def scan_advisor_universe(
    margin_currency: str | None = Query(None),
):
    """Scan configured universe; publish up to weekly cap."""
    proc = await get_advisor_processor()
    if margin_currency:
        proc.margin_currency = margin_currency.upper()
    results = await proc.scan_universe()
    published = sum(1 for r in results if r.get("phase") == "publish" and r.get("ok"))
    return {"scanned": len(results), "published": published, "results": results}


@router.get("/reports/latest", dependencies=[Depends(require_internal_api_key)])
async def list_latest_reports(limit: int = Query(20, ge=1, le=50)):
    """List recent PDF files from output directory."""
    out = settings.advisor_output_path
    if not out.exists():
        return {"reports": [], "count": 0}
    pdfs = sorted(out.glob("*.pdf"), key=lambda p: p.stat().st_mtime, reverse=True)[:limit]
    return {
        "reports": [{"name": p.name, "path": str(p)} for p in pdfs],
        "count": len(pdfs),
    }


@router.get("/reports/{filename}")
async def download_report(filename: str):
    """Download a generated PDF by filename."""
    safe = Path(filename).name
    path = settings.advisor_output_path / safe
    if not path.is_file():
        raise HTTPException(404, "Report not found")
    return FileResponse(path, media_type="application/pdf", filename=safe)


@router.get("/health", dependencies=[Depends(require_internal_api_key)])
async def advisor_health():
    proc = await get_advisor_processor()
    ok = await proc.data_fetcher.test_connection()
    recent = proc.allocation.recent_publishes()
    daily = proc.allocation.recent_daily_publishes()
    return {
        "coindcx": ok,
        "weekly_published": len(recent),
        "weekly_cap": settings.MAX_WEEKLY_SIGNALS,
        "daily_published": len(daily),
        "daily_cap": settings.MAX_DAILY_SIGNALS,
        "daily_target": settings.ADVISOR_TARGET_DAILY_SIGNALS,
        "margin": proc.margin_currency,
    }
