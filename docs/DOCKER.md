# Docker 24/7 — CoinDCX Futures Advisor

Unique Compose stack that runs **beside other Docker projects**. It does not use host ports `8000` or `27017`.

| Resource | Name |
|----------|------|
| Compose project | `coindcx-advisor` |
| Image | `coindcx-futures-advisor:24x7` |
| API | `coindcx-advisor-api` → http://localhost:18080 |
| Workers | `coindcx-advisor-workers` (scan + reconcile + live WR buckets) |
| Mongo | `coindcx-advisor-mongo` (internal network only) |
| Network | `coindcx-advisor-net` |

## Start (alongside other stacks)

```bash
cd "/path/to/Crypto Coins"

# Optional: set a real API key in this project's .env (compose interpolates it)
# PLANITT_PROCESSOR_INTERNAL_API_KEY=your-secret-key-here

docker compose -p coindcx-advisor up -d --build
```

- Health: http://localhost:18080/health
- API docs: http://localhost:18080/api/docs
- Protected routes need header `x-api-key` = `PLANITT_PROCESSOR_INTERNAL_API_KEY`

```bash
docker compose -p coindcx-advisor ps
docker compose -p coindcx-advisor logs -f workers
```

## Accuracy profile baked into this image

`docker/docker.env` is the 65% win-rate profile:

- Live bucket WR floor **65%** (n≥2)
- Positive expectancy / backtest quality gates
- Ablation disables: CCI, Williams %R, stochastic, Heikin Ashi, candlestick, Bollinger
- ML ranker **off** until a model has OOS WR ≥ 65%
- LLM narratives off (levels do not need Ollama)
- Friday 18:00 IST–Sunday publish pause; consecutive SL pause

Workers refresh live buckets from closed Mongo trades on startup and every reconcile cycle. If Mongo has no closed trades yet, the seeded `config/live_bucket_expectancy.json` is kept.

## Stop / restart

```bash
docker compose -p coindcx-advisor stop      # keep volumes
docker compose -p coindcx-advisor up -d
docker compose -p coindcx-advisor down      # stop containers; volumes remain
```

Named volumes (`coindcx_advisor_mongo_data`, reports, logs, data) survive `down`. Add `-v` only if you intend to wipe Mongo history.

## Optional: expose Mongo on the host

Uncomment `ports: ["27018:27017"]` under `mongo` in `docker-compose.yml` (27018 avoids clashing with other Mongo containers).

## Optional: Ollama narratives

Default is `ENABLE_LLM_ANALYSIS=false`. To attach a host Ollama later, set in `docker-compose.override.yml`:

```yaml
services:
  api:
    extra_hosts:
      - "host.docker.internal:host-gateway"
    environment:
      ENABLE_LLM_ANALYSIS: "true"
      OLLAMA_BASE_URL: http://host.docker.internal:11434
  workers:
    extra_hosts:
      - "host.docker.internal:host-gateway"
    environment:
      ENABLE_LLM_ANALYSIS: "true"
      OLLAMA_BASE_URL: http://host.docker.internal:11434
```

## Atlas instead of local Mongo

Override `MONGODB_URI` on `api` and `workers`, and do not start the `mongo` service:

```bash
MONGODB_URI="mongodb+srv://USER:PASS@cluster/..." \
  docker compose -p coindcx-advisor up -d --build api workers
```

Remove `depends_on: mongo` via `docker-compose.override.yml` if you go this route.
