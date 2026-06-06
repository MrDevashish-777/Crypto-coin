"""Async HTTP Client for Delta Exchange REST API."""

import hmac
import hashlib
import time
import json
import logging
from typing import Any, Optional, Dict
import aiohttp

logger = logging.getLogger(__name__)

class DeltaClientError(Exception):
    pass

class DeltaClient:
    def __init__(self, api_key: str, api_secret: str, testnet: bool = True):
        self.api_key = api_key
        self.api_secret = api_secret
        self.testnet = testnet
        self.base_url = "https://cdn-ind.testnet.deltaex.org" if testnet else "https://api.india.delta.exchange"
        self._session: Optional[aiohttp.ClientSession] = None

    async def _init_session(self):
        if self._session is None:
            self._session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=10.0),
                headers={"Accept": "application/json", "Content-Type": "application/json"}
            )

    def _generate_signature(self, method: str, path: str, query_string: str, payload: str, timestamp: str) -> str:
        signature_data = method + timestamp + path + query_string + payload
        signature = hmac.new(
            self.api_secret.encode('utf-8'),
            signature_data.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        return signature

    async def _request(self, method: str, endpoint: str, params: Optional[Dict] = None, data: Optional[Dict] = None) -> Any:
        await self._init_session()
        
        path = endpoint
        query_string = ""
        if params:
            import urllib.parse
            query_string = "?" + urllib.parse.urlencode(params)
            
        payload = json.dumps(data) if data else ""
        timestamp = str(int(time.time()))
        
        signature = self._generate_signature(method, path, query_string, payload, timestamp)
        
        headers = {
            "api-key": self.api_key,
            "signature": signature,
            "timestamp": timestamp
        }
        
        url = f"{self.base_url}{path}{query_string}"
        
        async with self._session.request(method, url, headers=headers, data=payload if data else None) as response:
            body = await response.json()
            if not body.get("success", True):
                error_msg = body.get("error", {}).get("message", "Unknown Delta API error")
                raise DeltaClientError(f"Delta API error {response.status}: {error_msg} - {body}")
            return body.get("result", body)

    async def close(self):
        if self._session:
            await self._session.close()
            self._session = None

    async def get_products(self) -> list:
        """Fetch all available products to map symbols to product_id."""
        return await self._request("GET", "/v2/products")

    async def get_wallet_balances(self) -> list:
        """Fetch wallet balance."""
        return await self._request("GET", "/v2/wallet/balances")

    async def place_order(self, product_id: int, size: float, side: str, order_type: str = "market_order", stop_price: Optional[str] = None, limit_price: Optional[str] = None, bracket_sl_price: Optional[str] = None, bracket_tp_price: Optional[str] = None) -> dict:
        """Place an order (buy/sell). side is 'buy' or 'sell'."""
        data = {
            "product_id": product_id,
            "size": size,
            "side": side,
            "order_type": order_type
        }
        if stop_price:
            data["stop_price"] = stop_price
        if limit_price:
            data["limit_price"] = limit_price
        if bracket_sl_price:
            data["bracket_stop_loss_price"] = bracket_sl_price
        if bracket_tp_price:
            data["bracket_take_profit_price"] = bracket_tp_price
            
        return await self._request("POST", "/v2/orders", data=data)
