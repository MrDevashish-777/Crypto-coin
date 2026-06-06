"""Delta Exchange Execution Engine."""

import logging
import asyncio
from typing import Optional
from config.settings import settings
from src.advisor.schemas import AdvisorSignal
from src.execution.delta_client import DeltaClient

logger = logging.getLogger(__name__)

class ExecutionEngine:
    def __init__(self):
        self.enabled = settings.DELTA_EXECUTION_ENABLED
        if not self.enabled:
            self.client = None
            return
            
        self.client = DeltaClient(
            api_key=settings.DELTA_API_KEY,
            api_secret=settings.DELTA_API_SECRET,
            testnet=settings.DELTA_TESTNET
        )
        self.products_cache: Optional[list] = None

    async def _ensure_products(self):
        if self.products_cache is None:
            self.products_cache = await self.client.get_products()

    def _get_product_info(self, symbol: str) -> Optional[dict]:
        """Find the product info matching the symbol."""
        targets = (f"{symbol}USD", f"{symbol}USDT", f"{symbol}_USDT")
        for p in self.products_cache:
            if p.get('symbol') in targets:
                return p
        return None

    async def _get_usdt_balance(self) -> float:
        try:
            balances = await self.client.get_wallet_balances() 
            for b in balances:
                sym = b.get("asset_symbol", "")
                if sym in ("USD", "USDT"):
                    return float(b.get("balance", 0.0))
            return 100.0 # Default demo balance
        except Exception as e:
            logger.warning("Could not fetch wallet balance, defaulting to $100: %s", e)
            return 100.0

    async def execute_signal(self, signal: AdvisorSignal):
        if not self.enabled or not self.client:
            return

        try:
            logger.info("Preparing to execute signal for %s", signal.symbol)
            await self._ensure_products()
            
            product_info = self._get_product_info(signal.symbol)
            if not product_info:
                logger.warning("Token %s is not supported on Delta Exchange Testnet. Trade not placed.", signal.symbol)
                return

            product_id = product_info['id']
            contract_value = float(product_info.get('contract_value', 0.001))
            tick_size = float(product_info.get('tick_size', 0.1))
            
            balance = await self._get_usdt_balance()
            logger.info("Delta Wallet Balance: $%.2f", balance)

            # Sizing logic
            max_portfolio_risk_pct = settings.DELTA_MAX_PORTFOLIO_RISK_PCT / 100.0 # max 0.70
            
            # Dynamic lot size based on confidence.
            # e.g. confidence 0.85 -> uses 85% of the max allowed risk (which is 70% of account).
            # So 0.85 * 0.70 = 59.5% of account balance used as margin.
            margin_to_use = balance * max_portfolio_risk_pct * signal.confidence
            
            # Use the exchange's default leverage for margin calculation if we aren't setting it
            exchange_leverage = float(product_info.get('default_leverage', 10.0))
            
            # If the calculated margin_to_use * exchange_leverage gives the notional
            notional_position = margin_to_use * exchange_leverage
            
            # Convert notional to contracts
            live_price = signal.live_price_at_signal
            size_in_contracts = int(notional_position / (live_price * contract_value))
            
            if size_in_contracts < 1:
                size_in_contracts = 1
                
            side = "buy" if signal.direction.lower() == "long" else "sell"

            logger.info("Placing order for %s: %s %d contracts (Margin: $%.2f)", 
                        signal.symbol, side.upper(), size_in_contracts, margin_to_use)

            # Round SL and TP to tick size
            def round_tick(val):
                return round(val / tick_size) * tick_size
                
            sl_price = round_tick(signal.stop_loss)
            tp_price = round_tick(signal.target)

            # Place Market Order
            order_res = await self.client.place_order(
                product_id=product_id,
                size=size_in_contracts,
                side=side,
                order_type="market_order",
                bracket_sl_price=str(sl_price),
                bracket_tp_price=str(tp_price)
            )
            logger.info("Market Order with Bracket placed: %s", order_res)

        except Exception as e:
            logger.exception("Failed to execute signal on Delta Exchange: %s", e)

    async def close(self):
        if self.client:
            await self.client.close()

# Singleton instance
executor = ExecutionEngine()
