import hmac, hashlib, time, asyncio, aiohttp
from config.settings import settings

api_key = settings.DELTA_API_KEY
api_secret = settings.DELTA_API_SECRET

async def test_india():
    ts = str(int(time.time()))
    path = "/v2/wallet/balances"
    qs = "?asset_id=2"
    
    # query string in payload? Let's include it first
    sig_data = "GET" + ts + path + qs
    sig = hmac.new(api_secret.encode('utf-8'), sig_data.encode('utf-8'), hashlib.sha256).hexdigest()
    
    headers = {"api-key": api_key, "signature": sig, "timestamp": ts}
    async with aiohttp.ClientSession() as session:
        # India testnet URL
        async with session.get("https://cdn-ind.testnet.deltaex.org" + path + qs, headers=headers) as r:
            print(f"Auth (with qs): {r.status}, Res: {await r.text()}")

    # Without qs
    sig_data = "GET" + ts + path
    sig = hmac.new(api_secret.encode('utf-8'), sig_data.encode('utf-8'), hashlib.sha256).hexdigest()
    headers = {"api-key": api_key, "signature": sig, "timestamp": ts}
    async with aiohttp.ClientSession() as session:
        async with session.get("https://cdn-ind.testnet.deltaex.org" + path + qs, headers=headers) as r:
            print(f"Auth (no qs): {r.status}, Res: {await r.text()}")

asyncio.run(test_india())
