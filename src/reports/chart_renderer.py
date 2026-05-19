"""Render advisor chart with Entry / SL / TP (matplotlib or Playwright + Lightweight Charts)."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from config.settings import settings
from src.advisor.schemas import AdvisorSignal
from src.data.models import CandleList

logger = logging.getLogger(__name__)

CHART_HTML_TEMPLATE = """<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <script src="https://unpkg.com/lightweight-charts@5.0.0/dist/lightweight-charts.standalone.production.js"></script>
  <style>
    body {{ margin: 0; background: #111315; font-family: system-ui, sans-serif; }}
    #wrap {{ position: relative; width: 1200px; height: 640px; }}
    #chart {{ width: 1200px; height: 580px; }}
    #brand {{ position: absolute; top: 8px; left: 12px; color: #00d09c; font-weight: 700; font-size: 14px; z-index: 2; }}
    #meta {{ position: absolute; top: 8px; right: 12px; color: #8f9aa8; font-size: 12px; z-index: 2; }}
  </style>
</head>
<body>
  <div id="wrap">
    <div id="brand">CoinDCX Futures</div>
    <div id="meta">{pair} · {timeframe} · {direction}</div>
    <div id="chart"></div>
  </div>
  <script>
    const candles = {candles_json};
    const ema50 = {ema_json};
    const levels = {levels_json};
    const chart = LightweightCharts.createChart(document.getElementById('chart'), {{
      layout: {{ background: {{ color: '#111315' }}, textColor: '#8f9aa8' }},
      grid: {{ vertLines: {{ color: 'rgba(143,154,168,0.12)' }}, horzLines: {{ color: 'rgba(143,154,168,0.12)' }} }},
      width: 1200, height: 580,
    }});
    const series = chart.addSeries(LightweightCharts.CandlestickSeries, {{
      upColor: '#00d09c', downColor: '#eb5757', borderVisible: false,
      wickUpColor: '#00d09c', wickDownColor: '#eb5757',
    }});
    series.setData(candles);
    if (ema50.length) {{
      const emaLine = chart.addSeries(LightweightCharts.LineSeries, {{ color: '#f59e0b', lineWidth: 2 }});
      emaLine.setData(ema50);
    }}
    function addHLine(price, color, title) {{
      series.createPriceLine({{ price, color, lineWidth: 2, lineStyle: 2, axisLabelVisible: true, title }});
    }}
    addHLine(levels.entry_low, '#60a5fa', 'Entry Low');
    addHLine(levels.entry_high, '#60a5fa', 'Entry High');
    addHLine(levels.stop_loss, '#eb5757', 'SL');
    addHLine(levels.target, '#00d09c', 'TP');
    chart.timeScale().fitContent();
  </script>
</body>
</html>
"""


def _prepare_chart_series(
    candle_list: CandleList,
    indicators: list[str],
) -> tuple[list[dict], list[dict]]:
    from src.indicators.ema import EMA

    candles_out: list[dict] = []
    for c in candle_list.candles[-120:]:
        candles_out.append({
            "time": c.timestamp // 1000,
            "open": c.open,
            "high": c.high,
            "low": c.low,
            "close": c.close,
        })

    ema_out: list[dict] = []
    if any("EMA" in i.upper() for i in indicators):
        ema = EMA(period=50)
        ema.calculate(candle_list.closes)
        vals = ema.values
        start = len(candle_list.closes) - len(vals)
        subset = candle_list.candles[-120:]
        for i, c in enumerate(subset):
            idx = start + (len(candle_list.candles) - len(subset) + i)
            if idx < len(vals) and vals[idx] is not None:
                ema_out.append({"time": c.timestamp // 1000, "value": float(vals[idx])})

    return candles_out, ema_out


def render_chart_matplotlib(
    signal: AdvisorSignal,
    candle_list: CandleList,
    output_path: Path,
) -> Path:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Rectangle

    candles = candle_list.candles[-80:]
    if not candles:
        raise ValueError("No candles for chart")

    fig, ax = plt.subplots(figsize=(12, 6.4), facecolor="#111315")
    ax.set_facecolor("#111315")
    ax.tick_params(colors="#8f9aa8")
    for spine in ax.spines.values():
        spine.set_color("#333")

    width = 0.6
    for i, c in enumerate(candles):
        color = "#00d09c" if c.close >= c.open else "#eb5757"
        ax.plot([i, i], [c.low, c.high], color=color, linewidth=1)
        bottom = min(c.open, c.close)
        height = abs(c.close - c.open) or (c.high - c.low) * 0.05
        ax.add_patch(Rectangle((i - width / 2, bottom), width, height, facecolor=color, edgecolor=color))

    ax.axhline(signal.entry_low, color="#60a5fa", linestyle="--", linewidth=1.5, label="Entry Low")
    ax.axhline(signal.entry_high, color="#60a5fa", linestyle="--", linewidth=1.5, label="Entry High")
    ax.axhline(signal.stop_loss, color="#eb5757", linestyle="-", linewidth=2, label="SL")
    ax.axhline(signal.target, color="#00d09c", linestyle="-", linewidth=2, label="TP")

    ax.set_title(
        f"CoinDCX Futures · {signal.pair} · {signal.direction} · {signal.timeframe}",
        color="#e5e7eb",
        fontsize=12,
        pad=12,
    )
    ax.legend(loc="upper left", facecolor="#1a1d21", edgecolor="#333", labelcolor="#ccc", fontsize=8)
    ax.set_xlim(-1, len(candles))
    fig.tight_layout()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=120, facecolor="#111315")
    plt.close(fig)
    return output_path


def _build_html(signal: AdvisorSignal, candle_list: CandleList) -> str:
    candles, ema = _prepare_chart_series(candle_list, signal.indicators)
    levels = {
        "entry_low": signal.entry_low,
        "entry_high": signal.entry_high,
        "stop_loss": signal.stop_loss,
        "target": signal.target,
    }
    return CHART_HTML_TEMPLATE.format(
        pair=signal.pair,
        timeframe=signal.timeframe,
        direction=signal.direction,
        candles_json=json.dumps(candles),
        ema_json=json.dumps(ema),
        levels_json=json.dumps(levels),
    )


async def render_chart_playwright(
    signal: AdvisorSignal,
    candle_list: CandleList,
    output_path: Path,
) -> Path:
    from playwright.async_api import async_playwright

    html = _build_html(signal, candle_list)
    html_path = output_path.with_suffix(".html")
    html_path.write_text(html, encoding="utf-8")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(viewport={"width": 1200, "height": 640})
        await page.goto(html_path.as_uri())
        await page.wait_for_timeout(1500)
        await page.screenshot(path=str(output_path), full_page=True)
        await browser.close()
    return output_path


async def render_advisor_chart(
    signal: AdvisorSignal,
    candle_list: CandleList,
    output_dir: Path,
) -> Path:
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    safe_pair = signal.pair.replace("/", "-").replace(" ", "_")
    out = output_dir / f"{ts}_{safe_pair}_{signal.direction}.png"

    if settings.CHART_RENDERER.lower() == "playwright":
        try:
            return await render_chart_playwright(signal, candle_list, out)
        except Exception as exc:
            logger.warning("Playwright chart failed, using matplotlib: %s", exc)
    return render_chart_matplotlib(signal, candle_list, out)
