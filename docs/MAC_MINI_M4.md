# Mac mini M4 (Apple Silicon) setup

This advisor stack can run **natively on Apple Silicon** (M1/M2/M3/M4) or as a unique Docker stack that sits beside other containers — see [DOCKER.md](DOCKER.md).

| Component | Mac M4 status |
|-----------|----------------|
| Python (FastAPI, pandas, indicators) | Native **arm64** wheels |
| Charts (`CHART_RENDERER=matplotlib`) | Native — **recommended on Mac** |
| Ollama + Plutus | Native arm64 with **Metal** GPU |
| MongoDB | Homebrew or MongoDB Atlas |
| CoinDCX API | HTTPS only — works everywhere |

---

## Recommended stack on Mac mini M4

1. **Python 3.11 or 3.12** (arm64) — avoid the old macOS system Python 3.9
2. **MongoDB** — local via Homebrew or Atlas in the cloud
3. **Ollama** — for optional PDF narratives (`0xroyce/plutus`, ~5.7 GB download)
4. **`CHART_RENDERER=matplotlib`** — default; do not use Playwright unless you install Chromium separately

Typical RAM: **8 GB minimum**, **16 GB+ recommended** when Ollama (Plutus) runs alongside MongoDB and the scanner.

---

## One-time install (Homebrew)

Install [Homebrew](https://brew.sh/) if needed.

**MongoDB is not in default Homebrew** — add MongoDB’s tap first, then install each package (do not combine in one line until the tap exists):

```bash
# 1) MongoDB tap (required once)
brew tap mongodb/brew

# 2) Install separately (if one fails, the others can still succeed)
brew install python@3.12
brew install mongodb-community@8.0
brew install ollama

# 3) Start services
brew services start mongodb-community@8.0
brew services start ollama
```

If you prefer **no local MongoDB**, use [MongoDB Atlas](https://www.mongodb.com/cloud/atlas) — set in `.env`:

```env
MONGODB_URI=mongodb+srv://USER:PASS@cluster....mongodb.net/?retryWrites=true&w=majority
MONGODB_DB_NAME=CryptoCoins
```

In Atlas: **Network Access** → allow your IP (or `0.0.0.0/0` for dev). No local `brew install mongodb-community` needed.

**Service name note:** After installing `mongodb-community@8.0`, `brew services list` may show `mongodb-community@8.0`. If `brew services start mongodb-community` fails, use the versioned name from `brew services list`.

Verify architecture:

```bash
uname -m          # expect: arm64
python3 --version # expect: 3.11+ from Homebrew, not 3.9.x from /usr/bin
which python3     # expect: /opt/homebrew/bin/python3 or similar
```

---

## Project setup

```bash
cd "/path/to/Crypto Coins"
cp .env.example .env
```

Edit `.env` for Mac local defaults:

```env
MONGODB_URI=mongodb://localhost:27017
MONGODB_DB_NAME=planitt
CHART_RENDERER=matplotlib
LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=0xroyce/plutus
ENABLE_LLM_ANALYSIS=true
PLANITT_PROCESSOR_INTERNAL_API_KEY=your-secret-key-here
```

Remove any legacy **`DATABASE_URL`** (PostgreSQL) lines — the advisor uses **MongoDB only**.

```bash
source .venv/bin/activate
pip install --upgrade pip setuptools wheel
pip install -r requirements.txt
```

Pull the LLM model (first run may take several minutes):

```bash
ollama pull 0xroyce/plutus
```

Optional alias with repo Modelfile:

```bash
ollama create cryptotradeai -f ollama/Modelfile
```

---

## Run and verify

```bash
source .venv/bin/activate
python scripts/check_mac_setup.py   # optional preflight
python scripts/run_server.py
```

- Health: http://localhost:8000/health  
- API docs: http://localhost:8000/api/docs  

Generate one signal:

```bash
export API_KEY="same-as-PLANITT_PROCESSOR_INTERNAL_API_KEY"

curl -X POST "http://localhost:8000/api/v1/advisor/generate" \
  -H "Content-Type: application/json" \
  -H "x-api-key: $API_KEY" \
  -d '{"symbol": "BTC", "timeframe": "1h"}'
```

PDF output: `output/reports/`

---

## Mac-specific tuning

| Goal | Setting |
|------|---------|
| Less CPU when idle | `ENABLE_BACKGROUND_SCANNER=false` — use API/CLI scans only |
| Faster scans, no LLM wait | `ENABLE_LLM_ANALYSIS=false` — template narratives |
| Lighter LLM | Smaller Ollama model (narratives only; not required for levels) |
| Remote MongoDB | `MONGODB_URI` → Atlas connection string |
| Keep Mac awake for scanner | System Settings → Energy → prevent sleep on power adapter |

Ollama on M4 uses Apple Metal automatically; no CUDA or NVIDIA drivers.

---

## Troubleshooting (Mac)

**`ModuleNotFoundError` after pip install**  
Use the venv Python: `source .venv/bin/activate` then `which python` should point inside `.venv`.

**`No available formula with the name "mongodb-community"`**  
Run `brew tap mongodb/brew` first, then `brew install mongodb-community@8.0`.

**MongoDB connection refused**  
`brew services start mongodb-community@8.0` (or the name shown in `brew services list`) or fix `MONGODB_URI` for Atlas.

**Ollama / Plutus slow or timing out**  
First pull must finish: `ollama list` should show `0xroyce/plutus`. Increase `OLLAMA_REQUEST_TIMEOUT_SECONDS=180` in `.env` if needed. Narratives fall back to templates if Ollama is down.

**Charts fail**  
Keep `CHART_RENDERER=matplotlib`. Playwright needs `pip install playwright && playwright install chromium` — optional, not required on Mac.

**Wrong Python (3.9 from `/usr/bin`)**  
Create venv with Homebrew: `/opt/homebrew/bin/python3.12 -m venv .venv`

**Port 8000 in use**  
Set `SERVER_PORT=8001` in `.env`.

---

## What you do not need on Mac mini

- Docker / docker-compose for 24/7 — optional; see [DOCKER.md](DOCKER.md) if you want a unique stack beside other containers
- NestJS or Next.js admin
- Binance API keys
- PostgreSQL / `DATABASE_URL`
- Playwright (unless you explicitly want it)
