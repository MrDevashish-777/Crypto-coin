import asyncio, aiohttp, time, hmac, hashlib, json
from config.settings import settings

async def main():
    api_key = settings.DELTA_API_KEY
    api_secret = settings.DELTA_API_SECRET
    ts = str(int(time.time()))
    path = "/v2/orders/leverage"
    payload = json.dumps({"product_id": 84, "leverage": "20"})
    
    sig_data = "POST" + ts + path + payload
    sig = hmac.new(api_secret.encode('utf-8'), sig_data.encode('utf-8'), hashlib.sha256).hexdigest()
    
    headers = {"api-key": api_key, "signature": sig, "timestamp": ts, "Content-Type": "application/json"}
    async with aiohttp.ClientSession() as session:
        async with session.post("https://cdn-ind.testnet.deltaex.org" + path, data=payload, headers=headers) as r:
            print(f"Auth: {r.status}, Res: {await r.text()}")

asyncio.run(main())
