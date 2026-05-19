"""Generate mandatory 3-point reasoning (LLM optional, template fallback)."""

from __future__ import annotations

import logging

from src.planitt.confluence import ConfluenceFeatures

logger = logging.getLogger(__name__)


def default_narrative(features: ConfluenceFeatures, *, pair: str, levels: dict) -> tuple[str, str, str]:
    """Deterministic SOP narrative bullets."""
    side = features.side
    hits = ", ".join(features.confluence_hits[:5])
    why = (
        f"{pair} selected for relative strength: {hits}. "
        f"ADX {features.adx:.1f} with aligned EMA stack supports a {side} bias on {features.timeframe}."
        if features.adx
        else f"{pair} shows confluence on {features.timeframe}: {hits}."
    )
    entry = (
        f"Entry triggered on {features.setup_type.replace('_', ' ')}: price at "
        f"{features.price:.4f} with volume ratio {features.volume_ratio:.2f}x and "
        f"RSI {features.rsi:.1f} confirming {side} momentum."
    )
    monitor = (
        f"Watch reaction at target {levels['target']:.4f} and stop {levels['stop_loss']:.4f}. "
        f"If price rejects key level with rising volume against the trade, consider early exit."
    )
    return why, entry, monitor


async def generate_narrative(
    features: ConfluenceFeatures,
    *,
    pair: str,
    levels: dict,
    llm_agent: object | None = None,
) -> tuple[str, str, str]:
    """Return (why_token, entry_reason, monitor_tip)."""
    if llm_agent is None:
        return default_narrative(features, pair=pair, levels=levels)
    try:
        prompt = (
            f"Write 3 short paragraphs for a crypto futures {features.side} call on {pair}.\n"
            f"1) Why this token 2) Entry technical trigger 3) What to monitor after entry.\n"
            f"Setup: {features.setup_type}, hits: {features.confluence_hits}, "
            f"entry {levels['entry_low']}-{levels['entry_high']}, SL {levels['stop_loss']}, TP {levels['target']}.\n"
            "Keep each under 60 words. No invented prices."
        )
        if hasattr(llm_agent, "generate_text"):
            text = await llm_agent.generate_text(prompt)  # type: ignore[attr-defined]
            parts = [p.strip() for p in str(text).split("\n\n") if p.strip()]
            if len(parts) >= 3:
                return parts[0], parts[1], parts[2]
    except Exception as exc:
        logger.warning("LLM narrative fallback: %s", exc)
    return default_narrative(features, pair=pair, levels=levels)
