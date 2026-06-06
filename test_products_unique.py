import asyncio
from src.execution.delta_client import DeltaClient
from config.settings import settings

async def main():
    client = DeltaClient(settings.DELTA_API_KEY, settings.DELTA_API_SECRET, True)
    try:
        products = await client.get_products()
        symbols = set()
        for p in products:
            sym = p.get('symbol', '')
            if sym.endswith('USD'):
                base = sym[:-3]
                symbols.add(base)
            elif sym.endswith('USDT'):
                base = sym[:-4]
                symbols.add(base)
        print("Unique base symbols on Delta Testnet:", sorted(list(symbols)))
    finally:
        await client.close()

asyncio.run(main())
