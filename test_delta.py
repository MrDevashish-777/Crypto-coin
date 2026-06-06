import asyncio
from src.execution.delta_client import DeltaClient

async def main():
    client = DeltaClient("dummy", "dummy", True)
    try:
        products = await client.get_products()
        for p in products:
            if 'BTC' in p['symbol'] or 'ETH' in p['symbol'] or 'XRP' in p['symbol'] or 'ADA' in p['symbol']:
                print(p['symbol'])
    finally:
        await client.close()

asyncio.run(main())
