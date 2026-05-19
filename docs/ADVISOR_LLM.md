# Manual LLM prompts (outside the automated advisor)

The advisor bot computes **entry, SL, TP, and position risk in Python**. Ollama (Plutus) only writes the three narrative paragraphs in the PDF when `ENABLE_LLM_ANALYSIS=true`.

Use these templates in a separate chat session (e.g. `ollama run 0xroyce/plutus`) for ad-hoc research. They are **not** wired into the scanner.

> Education and research only — not financial advice.

---

## Market analysis

```
Analyze BTC/USDT current market:
- Price: [current price]
- Timeframe: [1H/4H/1D]
- Indicators: RSI=[value], MACD=[value], MA50=[value], MA200=[value]
- Volume: [current vs average]

Summarize trend and key levels. Do not invent prices not listed above.
Include risk warnings and DYOR reminder.
```

---

## Chart pattern check

```
I'm seeing [pattern name, e.g. bullish flag] on ETH/USDT 4H chart.
Current price: [price], Support: [level], Resistance: [level]

Is this a valid setup? What should I monitor? Analysis only — no guaranteed outcomes.
```

---

## Position size (use Python / risk manager for production)

```
Account size: $1000
I want to trade SOL/USDT at $150
Stop-loss: $145
Max risk per trade: 2%

Calculate position size and notional. Show the formula. Remind me leverage amplifies losses.
```

For programmatic sizing, see `src/risk/risk_manager.py`.

---

## Optional local model alias

```bash
ollama pull 0xroyce/plutus
ollama create cryptotradeai -f ollama/Modelfile
ollama run cryptotradeai
```

Runtime config (no alias required):

```env
LLM_PROVIDER=ollama
OLLAMA_MODEL=0xroyce/plutus
ENABLE_LLM_ANALYSIS=true
```

System prompt for automated PDF narratives: `config/prompts/advisor_narrative_system.md`
