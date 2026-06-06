import asyncio
from src.execution.delta_client import DeltaClient
from config.settings import settings

async def main():
    client = DeltaClient(settings.DELTA_API_KEY, settings.DELTA_API_SECRET, True)
    try:
        products = await client.get_products()
        symbols = [p.get('symbol') for p in products]
        print("Available symbols on Delta:", symbols)
    finally:
        await client.close()

asyncio.run(main())
