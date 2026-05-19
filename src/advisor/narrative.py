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
        if hasattr(llm_agent, "generate_advisor_narrative"):
            result = await llm_agent.generate_advisor_narrative(  # type: ignore[attr-defined]
                features=features,
                pair=pair,
                levels=levels,
            )
            if result and len(result) == 3 and all(result):
                return result
    except Exception as exc:
        logger.warning("LLM narrative fallback: %s", exc)
    return default_narrative(features, pair=pair, levels=levels)
