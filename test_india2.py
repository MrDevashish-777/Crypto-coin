import asyncio
from src.execution.delta_client import DeltaClient
from config.settings import settings

async def main():
    client = DeltaClient(settings.DELTA_API_KEY, settings.DELTA_API_SECRET, True)
    try:
        products = await client.get_products()
        for p in products:
            if '-' not in p['symbol']:
                print(p['symbol'], p['id'])
    finally:
        await client.close()

asyncio.run(main())
