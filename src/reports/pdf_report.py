"""Generate SOP-compliant advisor PDF reports."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_JUSTIFY, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer

from config.settings import settings
from src.advisor.schemas import AdvisorSignal
from src.data.models import CandleList
from src.reports.chart_renderer import render_advisor_chart

logger = logging.getLogger(__name__)

DISCLAIMER = (
    "Trading signals are for informational purposes only and do not constitute "
    "investment advice. Always perform your own due diligence before making investment decisions."
)


async def generate_advisor_pdf(
    signal: AdvisorSignal,
    candle_list: CandleList,
) -> tuple[Path, Path]:
    """Render chart PNG and multi-section PDF; return (pdf_path, chart_path)."""
    out_dir = settings.advisor_output_path
    charts_dir = out_dir / "charts"
    charts_dir.mkdir(parents=True, exist_ok=True)
    out_dir.mkdir(parents=True, exist_ok=True)

    chart_path = await render_advisor_chart(signal, candle_list, charts_dir)

    ts = signal.generated_at.strftime("%Y%m%d")
    safe_pair = signal.pair.replace("/", "-")
    pdf_name = f"{ts}_{safe_pair}_{signal.direction}_{signal.signal_id[:8]}.pdf"
    pdf_path = out_dir / pdf_name

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "AdvisorTitle",
        parent=styles["Heading1"],
        fontSize=16,
        spaceAfter=8,
        textColor=colors.HexColor("#111315"),
    )
    body_style = ParagraphStyle(
        "AdvisorBody",
        parent=styles["BodyText"],
        fontSize=10,
        leading=14,
        alignment=TA_JUSTIFY,
    )
    section_style = ParagraphStyle(
        "AdvisorSection",
        parent=styles["Heading2"],
        fontSize=12,
        spaceBefore=10,
        spaceAfter=4,
        textColor=colors.HexColor("#00a67e"),
    )

    story: list = []
    story.append(Paragraph(f"CoinDCX Futures — {signal.pair}", title_style))
    story.append(Spacer(1, 4 * mm))

    if chart_path.exists():
        img = Image(str(chart_path), width=170 * mm, height=95 * mm)
        story.append(img)
        story.append(Spacer(1, 6 * mm))

    card = (
        f"<b>Direction:</b> {signal.direction} &nbsp;|&nbsp; "
        f"<b>Horizon:</b> {signal.trade_horizon} &nbsp;|&nbsp; "
        f"<b>TF:</b> {signal.timeframe}<br/>"
        f"<b>Entry:</b> {signal.entry_low:,.4f} – {signal.entry_high:,.4f} &nbsp;|&nbsp; "
        f"<b>SL:</b> {signal.stop_loss:,.4f} &nbsp;|&nbsp; <b>TP:</b> {signal.target:,.4f}<br/>"
        f"<b>SL%:</b> {signal.sl_pct:.2f}% &nbsp;|&nbsp; <b>TP%:</b> {signal.tp_pct:.2f}% &nbsp;|&nbsp; "
        f"<b>Leverage:</b> {signal.leverage:.1f}x &nbsp;|&nbsp; <b>R:R:</b> {signal.risk_reward}<br/>"
        f"<b>Confidence:</b> {signal.confidence * 100:.0f}% &nbsp;|&nbsp; "
        f"<b>Valid until (IST):</b> {signal.valid_until_ist.strftime('%d %b %Y %H:%M')}<br/>"
        f"<b>Live price at signal:</b> {signal.live_price_at_signal:,.4f} &nbsp;|&nbsp; "
        f"<b>Generated (UTC):</b> {signal.generated_at.strftime('%Y-%m-%d %H:%M')}"
    )
    story.append(Paragraph(card, body_style))
    story.append(Spacer(1, 6 * mm))

    story.append(Paragraph("1 – Why this token?", section_style))
    story.append(Paragraph(signal.reason_why_token, body_style))
    story.append(Paragraph("2 – Entry reason (technical trigger)", section_style))
    story.append(Paragraph(signal.reason_entry, body_style))
    story.append(Paragraph("3 – What to monitor after entry", section_style))
    story.append(Paragraph(signal.reason_monitor, body_style))
    story.append(Spacer(1, 8 * mm))
    story.append(Paragraph(f"<i>{DISCLAIMER}</i>", body_style))

    doc = SimpleDocTemplate(
        str(pdf_path),
        pagesize=A4,
        topMargin=15 * mm,
        bottomMargin=15 * mm,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
    )
    doc.build(story)
    logger.info("Advisor PDF written: %s", pdf_path)
    return pdf_path, chart_path
