# START HERE — 5-minute bootstrap

> **Canonical documentation:** [README.md](README.md)

**CoinDCX Futures Advisor** — SOP-gated PDF signals, confluence engine, optional Plutus LLM narratives.

> **Disclaimer:** Education and research only — not financial advice.

---

## Prerequisites

- **Python 3.11+**
- **MongoDB** (`MONGODB_URI` in `.env`) — startup fails without it
- **Optional:** [Ollama](https://ollama.com/) when `ENABLE_LLM_ANALYSIS=true`

CoinDCX uses the public REST API — no exchange API key required.

---

## Quick start

### 1. Configure (~1 min)

```bash
cp .env.example .env
```

Edit `.env`:

```env
MONGODB_URI=mongodb://localhost:27017
PLANITT_PROCESSOR_INTERNAL_API_KEY=your-secret-key-here
```

### 2. Install (~2 min)

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

### 3. Ollama (optional, for LLM narratives)

```bash
ollama pull 0xroyce/plutus
```

### 4. Run (~1 min)

```bash
python scripts/run_server.py
```

- Swagger: http://localhost:8000/api/docs
- Health: http://localhost:8000/health

Protected routes need header `x-api-key` = `PLANITT_PROCESSOR_INTERNAL_API_KEY`.

---

## First signal

```bash
export API_KEY="your-planitt-processor-key"

curl -X POST "http://localhost:8000/api/v1/advisor/generate" \
  -H "Content-Type: application/json" \
  -H "x-api-key: $API_KEY" \
  -d '{"symbol": "BTC", "timeframe": "1h"}'
```

PDFs land in `output/reports/`.

**One-shot scan:**

```bash
python scripts/run_advisor_scan.py
```

---

## What's running

| Component | Role |
|-----------|------|
| **FastAPI** | Advisor API + optional news feed |
| **Advisor scanner** | Background scan when `ENABLE_BACKGROUND_SCANNER=true` |
| **CoinDCX** | Candles via [`src/data/data_fetcher.py`](src/data/data_fetcher.py) |
| **Confluence** | [`src/planitt/confluence.py`](src/planitt/confluence.py) |
| **Ollama** | Optional PDF narrative (Plutus) |
| **MongoDB** | Signal history |

---

## Customize

| Area | Location |
|------|----------|
| Settings | [`config/settings.py`](config/settings.py) |
| LLM system prompt | [`config/prompts/advisor_narrative_system.md`](config/prompts/advisor_narrative_system.md) |
| Symbols / timeframes | [`config/constants.py`](config/constants.py) |
| SOP gates | [`src/advisor/sop_gates.py`](src/advisor/sop_gates.py) |

Manual chat prompts (outside the bot): [docs/ADVISOR_LLM.md](docs/ADVISOR_LLM.md)

---

## Tests

```bash
pip install -r requirements-dev.txt
pytest tests/test_advisor_sop_gates.py tests/test_advisor_allocation.py tests/test_coindcx_client.py -q
```

---

## FAQ

**Do I need Binance API keys?**  
No. All market data comes from CoinDCX.

**Is this live trading?**  
No. Research signals and PDFs only.

**Why 422 on advisor generate?**  
SOP gates, weekly caps, or confluence rejected the setup. Check the API error body.

**LLM not changing PDF text?**  
Ensure Ollama is running, `ENABLE_LLM_ANALYSIS=true`, and `OLLAMA_MODEL=0xroyce/plutus`. On failure the bot uses a deterministic template.

---

For full detail, see [README.md](README.md).
