from __future__ import annotations

from pathlib import Path


def test_dedup_key_is_stable_per_asset_timeframe() -> None:
    text = (Path(__file__).resolve().parents[1] / "src" / "planitt" / "processor.py").read_text(
        encoding="utf-8"
    )
    assert 'return f"{asset}:{timeframe}"' in text
