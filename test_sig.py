import hmac, hashlib, time, asyncio, aiohttp
from config.settings import settings

api_key = settings.DELTA_API_KEY
api_secret = settings.DELTA_API_SECRET

async def test_ts(is_ms):
    ts = str(int(time.time() * 1000)) if is_ms else str(int(time.time()))
    path = "/v2/wallet/balances"
    qs = "?asset_id=2"
    sig_data = "GET" + ts + path + qs
    sig = hmac.new(api_secret.encode('utf-8'), sig_data.encode('utf-8'), hashlib.sha256).hexdigest()
    
    headers = {"api-key": api_key, "signature": sig, "timestamp": ts}
    async with aiohttp.ClientSession() as session:
        async with session.get("https://testnet-api.delta.exchange" + path + qs, headers=headers) as r:
            body = await r.text()
            print(f"MS: {is_ms}, TS: {ts}, Auth: {r.status}, Res: {body[:100]}")

async def main():
    await test_ts(True)
    await test_ts(False)

asyncio.run(main())
