import hmac, hashlib, time, asyncio, aiohttp
from config.settings import settings

api_key = settings.DELTA_API_KEY
api_secret = settings.DELTA_API_SECRET

async def test_auth(ts, inc_qs):
    path = "/v2/wallet/balances"
    qs = "?asset_id=2"
    
    sig_data = "GET" + ts + path + (qs if inc_qs else "")
    sig = hmac.new(api_secret.encode('utf-8'), sig_data.encode('utf-8'), hashlib.sha256).hexdigest()
    
    headers = {"api-key": api_key, "signature": sig, "timestamp": ts}
    async with aiohttp.ClientSession() as session:
        async with session.get("https://testnet-api.delta.exchange" + path + qs, headers=headers) as r:
            print(f"TS_LEN: {len(ts)}, INC_QS: {inc_qs}, Auth: {r.status}, Res: {await r.text()}")

async def main():
    ts_ms = str(int(time.time() * 1000))
    ts_s = str(int(time.time()))
    
    await test_auth(ts_ms, True)
    await test_auth(ts_ms, False)
    await test_auth(ts_s, True)
    await test_auth(ts_s, False)

asyncio.run(main())
