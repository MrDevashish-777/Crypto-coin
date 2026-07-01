# START HERE — 5-minute bootstrap

> **Canonical documentation:** [README.md](README.md)

**CoinDCX Futures Advisor** — SOP-gated PDF signals, confluence engine, optional Plutus LLM narratives.

> **Disclaimer:** Education and research only — not financial advice.

---

## Prerequisites

- **Python 3.11+** (on Mac mini M4 use Homebrew `python@3.12` — not macOS `/usr/bin/python3` 3.9)
- **MongoDB** (`MONGODB_URI` in `.env`) — startup fails without it
- **Optional:** [Ollama](https://ollama.com/) when `ENABLE_LLM_ANALYSIS=true` (native arm64 + Metal on M4)

**Mac mini M4:** full guide → [docs/MAC_MINI_M4.md](docs/MAC_MINI_M4.md)

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

On **Mac mini M4**, prefer Homebrew Python (arm64):

```bash
# once (MongoDB needs a tap first — see docs/MAC_MINI_M4.md)
brew tap mongodb/brew
brew install python@3.12 mongodb-community@8.0 ollama
brew services start mongodb-community@8.0
brew services start ollama

/opt/homebrew/bin/python3.12 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip setuptools wheel
pip install -r requirements.txt
python scripts/check_mac_setup.py
```

Other platforms:

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

Start the API server:
```bash
python scripts/run_server.py
```

In a separate terminal, start the background workers (scanner, RL optimizer):
```bash
python scripts/run_workers.py
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
| **FastAPI** | Advisor API + optional news feed (`scripts/run_server.py`) |
| **Advisor workers** | Background scan + RL weight tuning (`scripts/run_workers.py`) |
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

**Port 8000 in use**  
Another app (often **Docker**) is bound to 8000. Either stop it (`docker ps` then `docker stop <id>`) or set `SERVER_PORT=8001` in `.env` and use http://localhost:8001.

---

For full detail, see [README.md](README.md).
