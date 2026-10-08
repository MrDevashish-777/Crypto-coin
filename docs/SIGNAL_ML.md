# Signal ML Rankers (SOP-safe)

Per-(timeframe, direction) HistGradientBoosting models score win probability
**after** confluence + SOP hard gates. They never set entry/SL/TP/leverage/validity.

## What stays hard (always)
- Intraday / swing only (no scalping / long-term)
- R:R ≥ 1.5, SL 2.5–3%, leverage = 20/SL%, leveraged SL 18–22%
- Entry width 0.5–1.5%, live price in band
- One entry / one SL / one TP
- Validity windows (IST)
- CoinDCX futures, top mcap, BTC≥20%, majors 35–40%
- Macro blackout, Friday slowdown, consecutive SL pause
- Live bucket WR ≥ 65% when enabled

## What ML does
1. **Ranks** publish candidates (`ADVISOR_ML_RANK_WEIGHT`)
2. **Optional soft gate** only if `soft_gate_eligible=true` (OOS WR ≥ 65%)

## Train
```bash
source .venv/bin/activate
pip install scikit-learn joblib
python scripts/train_signal_models.py --symbols BTC,ETH,SOL,XRP,AVAX,ATOM --timeframes 15m,1h --months 3 --step 4
```

Artifacts: `config/ml_models/*.joblib`, `config/ml_models/manifest.json`

## Retrain cadence
Weekly or after ≥50 new closed trades. Soft gate stays off until a segment ships with OOS WR ≥ 65%.
