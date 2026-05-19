# 🚀 START HERE - Crypto Trading Signal Server

Welcome! You have a complete, production-grade cryptocurrency trading signal server. This guide will get you running in 5 minutes.

---

## ⚡ 5-Minute Quick Start

### Step 1: Configure Environment (1 min)
```bash
cp .env.example .env
```

Edit `.env` and add your Binance API keys:
```env
BINANCE_API_KEY=your_key_here
BINANCE_API_SECRET=your_secret_here
```

Get keys from: https://www.binance.com/en/my/settings/api-management

### Step 2: Install Dependencies (2 mins)
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Step 3: Run Server (1 min)
```bash
python scripts/run_server.py
```

### Step 4: Test API (1 min)
Open in browser: **http://localhost:8000/api/docs**

You'll see interactive API documentation with a "Try it out" button.

---

## 🧪 First Test Signal

```bash
# Generate a BTC signal on 15-minute timeframe
curl -X POST "http://localhost:8000/api/v1/signals/generate?symbol=BTC&timeframe=15m&strategy=rsi"
```

You should get a JSON response with:
- Signal type (BUY/SELL)
- Entry price
- Take Profit level
- Stop Loss level
- Confidence score

---

## 📊 What's Running

When you start the server, you have:
- **FastAPI Server** on http://localhost:8000
- **API Documentation** on http://localhost:8000/api/docs
- **Binance Data Fetching** (real market data)
- **Technical Indicators** (RSI, MACD, Bollinger Bands, etc)
- **Signal Generation Engine**
- **Risk Management System**

---

## 📖 Next Steps

### To Understand the Architecture:
1. Read [PROJECT_OVERVIEW.md](PROJECT_OVERVIEW.md) (5 min)
2. Browse [IMPLEMENTATION_GUIDE.md](IMPLEMENTATION_GUIDE.md) (15 min)
3. Deep dive: [PROJECT_PLAN.md](PROJECT_PLAN.md) (1 hour)

### To Deploy with All Services:
```bash
docker-compose -f docker/docker-compose.yml up
```
This starts:
- API Server
- PostgreSQL Database
- Redis Cache
- Prometheus Monitoring

### To Run Tests:
```bash
pip install -r requirements-dev.txt
pytest
```

### To Customize:
Edit these files:
- `config/settings.py` - Application settings
- `config/constants.py` - Trading parameters
- `src/signals/strategies/*.py` - Trading strategies

---

## 🎯 Core Features Available Now

✅ **Real-time Signal Generation**
- Technical indicator analysis
- Automatic TP/SL calculation
- Risk management
- Multiple timeframes (1m to 1w)
- 10+ cryptocurrencies

✅ **RESTful API**
- Generate signals on demand
- Query historical signals
- Get supported symbols/timeframes
- Auto-documentation with Swagger

✅ **Technical Indicators**
- RSI (Relative Strength Index)
- MACD (Moving Average Convergence Divergence)
- Bollinger Bands
- Stochastic Oscillator
- ATR, EMA, SMA

✅ **Risk Management**
- Position sizing
- TP/SL calculation
- R:R ratio validation
- Portfolio limits

---

## 🔐 Security Features

- JWT authentication ready
- Input validation
- Rate limiting framework
- CORS protection
- Encrypted credentials

---

## ❓ Common Questions

**Q: Is this live trading?**
A: No, BINANCE_TESTNET=True by default. Change to False only when ready.

**Q: Do I need PostgreSQL?**
A: No, it's optional. In-memory caching works fine for testing.

**Q: How do I add more strategies?**
A: Create new files in `src/signals/strategies/` extending BaseStrategy.

**Q: Can I use my own LLM?**
A: Yes, configure OLLAMA_BASE_URL for local models.

**Q: How do I deploy?**
A: Use `docker-compose.yml` or see IMPLEMENTATION_GUIDE.md for K8s.

---

## 🆘 Troubleshooting

**"ModuleNotFoundError: No module named 'src'"**
- Make sure you're in the project root: `/Users/parthshende/Desktop/Crypto\ Bot`
- Try: `export PYTHONPATH=$PYTHONPATH:.`

**"Binance API connection failed"**
- Check API keys in .env
- Verify internet connection
- Binance might be blocking your IP

**"Database connection error"**
- PostgreSQL isn't needed initially
- System works with just Python and Binance API

---

## 📚 Documentation Map

| Document | Purpose | Time |
|----------|---------|------|
| **START_HERE.md** | This file - get running fast | 5 min |
| **PROJECT_OVERVIEW.md** | Feature overview | 10 min |
| **QUICK_START.md** | Detailed setup | 30 min |
| **IMPLEMENTATION_GUIDE.md** | Complete guide | 1 hour |
| **PROJECT_PLAN.md** | Deep architecture | 2 hours |
| **TRADING_STRATEGIES.md** | Strategy details | 1 hour |
| **API Docs** | http://localhost:8000/api/docs | 15 min |

---

## 🎉 You're All Set!

Your server is ready to:
1. ✅ Fetch real market data from Binance
2. ✅ Calculate technical indicators
3. ✅ Generate buy/sell signals
4. ✅ Manage risk with TP/SL
5. ✅ Provide REST API access
6. ✅ Log and monitor everything

**Next Action**: Run `python scripts/run_server.py` and check http://localhost:8000/api/docs

---

## 💡 Pro Tips

1. **Start with testnet** - BINANCE_TESTNET=True (default)
2. **Use 15m timeframe** - Most signals are generated here
3. **Check logs** - `tail -f logs/app.log` for debugging
4. **Use Swagger UI** - Interactive at /api/docs
5. **Test endpoints** - Try out button in Swagger UI

---

## 🚀 What to Do Now

Pick one:

### Option A: Just Try It (5 min)
```bash
python scripts/run_server.py
# Visit http://localhost:8000/api/docs
```

### Option B: Full Setup with Database (15 min)
```bash
docker-compose -f docker/docker-compose.yml up
# All services: API, DB, Redis, Prometheus
```

### Option C: Deep Dive (1 hour)
```bash
# Read documentation
cat PROJECT_OVERVIEW.md
cat IMPLEMENTATION_GUIDE.md
# Explore code
ls -la src/
# Run tests
pytest -v
```

---

**Happy trading! 🚀**

For detailed setup, see [IMPLEMENTATION_GUIDE.md](IMPLEMENTATION_GUIDE.md)
For architecture deep dive, see [PROJECT_PLAN.md](PROJECT_PLAN.md)
For API documentation, start the server and visit http://localhost:8000/api/docs
