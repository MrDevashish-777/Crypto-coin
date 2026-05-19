"""
LLM Agent for Market Analysis
Integrates with OpenAI, Anthropic, or local Ollama
"""

import asyncio
import logging
from typing import Optional, Dict, Any
from abc import ABC, abstractmethod
import httpx
import json
from openai import AsyncOpenAI
from anthropic import AsyncAnthropic

logger = logging.getLogger(__name__)


class LLMAgent(ABC):
    """Abstract base for LLM agents"""

    @abstractmethod
    async def analyze_market(self, market_data: Dict[str, Any], context: str = "") -> Dict[str, Any]:
        """Analyze market data with LLM"""
        pass

    @abstractmethod
    async def generate_signal_confidence(
        self,
        symbol: str,
        indicators: Dict[str, Any],
        price_action: str,
        context: str = ""
    ) -> float:
        """Generate confidence score for signal"""
        pass

    @abstractmethod
    async def analyze_news_sentiment(self, news_text: str) -> Dict[str, Any]:
        """Analyze the sentiment of a fundamental news headline/summary"""
        pass


class OpenAIAgent(LLMAgent):
    """OpenAI-based LLM agent"""

    def __init__(self, api_key: str, model: str = "gpt-4o"):
        """Initialize OpenAI agent"""
        self.client = AsyncOpenAI(api_key=api_key)
        self.model = model
        logger.info(f"OpenAI agent initialized with model: {model}")

    async def analyze_market(self, market_data: Dict[str, Any], context: str = "") -> Dict[str, Any]:
        """Analyze market with GPT"""
        prompt = f"""
        Analyze the following cryptocurrency market data and provide signal analysis.
        Use the provided context to learn from past successful trades.
        
        Historical Context:
        {context}
        
        Current Data:
        Symbol: {market_data.get('symbol')}
        Price: {market_data.get('price')}
        24h Change: {market_data.get('change_24h')}%
        Volume: {market_data.get('volume')}
        RSI: {market_data.get('rsi')}
        MACD: {market_data.get('macd')}
        
        Provide your analysis in JSON format with the following fields:
        - sentiment: "bullish", "bearish", or "neutral"
        - confidence: float between 0 and 1
        - risk_level: "low", "medium", or "high"
        - entry_points: list of suggested entry prices
        - take_profit: list of suggested take profit targets
        - stop_loss: suggested stop loss price
        - reasoning: brief explanation of your analysis
        """

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are the Lead Research Analyst for a professional crypto trading desk. Your role is to confirm or reject technical signals based on deep analysis of market data. You provide institutional-grade insights and clear reasoning for your stance."},
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"}
            )
            
            result = json.loads(response.choices[0].message.content)
            
            # Ensure result is a dictionary
            if isinstance(result, list) and result:
                result = result[0]
            elif not isinstance(result, dict):
                logger.warning(f"Unexpected LLM output type: {type(result)}")
                result = {"error": "Invalid LLM output format", "raw": str(result)}
                
            return result
        except Exception as e:
            logger.error(f"OpenAI analysis failed: {str(e)}")
            return {
                "sentiment": "neutral",
                "confidence": 0.0,
                "reasoning": f"Error: {str(e)}",
            }

    async def generate_signal_confidence(
        self,
        symbol: str,
        indicators: Dict[str, Any],
        price_action: str,
        context: str = ""
    ) -> float:
        """Generate confidence score"""
        analysis = await self.analyze_market({
            "symbol": symbol,
            **indicators,
            "price_action": price_action
        }, context=context)
        return float(analysis.get("confidence", 0.0))

    async def analyze_news_sentiment(self, news_text: str) -> Dict[str, Any]:
        """Analyze news sentiment with GPT"""
        prompt = f"""
        You are an expert crypto fundamental analyst. Analyze the following news and extract its market sentiment.
        
        News Text:
        {news_text}
        
        Provide your analysis in JSON format with exactly these fields:
        - sentiment: "bullish", "bearish", or "neutral"
        - confidence: float between 0.0 and 1.0 representing your certainty
        - reasoning: brief explanation of your analysis
        """
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a crypto sentiment analysis engine. Return strictly JSON."},
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"}
            )
            result = json.loads(response.choices[0].message.content)
            if isinstance(result, list) and result:
                result = result[0]
            elif not isinstance(result, dict):
                result = {"error": "Invalid format"}
            return result
        except Exception as e:
            logger.error(f"OpenAI news analysis failed: {str(e)}")
            return {"sentiment": "neutral", "confidence": 0.0, "reasoning": str(e)}

    async def generate_planitt_decision(
        self,
        *,
        market_data: Dict[str, Any],
        context: str = "",
    ) -> str:
        prompt = f"""
You are Planitt, a professional crypto signal desk.

Rules:
1) If confluence is weak/unclear, respond exactly: NO TRADE
2) Otherwise respond with ONLY strict JSON (no markdown/code fences) with keys:
   signal_type, confidence, strategy, reason, validity, risk_reward_ratio
3) signal_type must be BUY or SELL
4) confidence must be integer 1..100
5) validity format: 2-4 hours
6) risk_reward_ratio format: 1:2.0

Context:
{context}

Market input:
{market_data}
"""
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "Return ONLY JSON or NO TRADE."},
                    {"role": "user", "content": prompt},
                ],
            )
            content = (response.choices[0].message.content or "").strip()
            return content or "NO TRADE"
        except Exception as e:
            logger.error(f"OpenAI Planitt decision failed: {str(e)}")
            return "NO TRADE"


class AnthropicAgent(LLMAgent):
    """Anthropic Claude-based LLM agent"""

    def __init__(self, api_key: str, model: str = "claude-3-opus-20240229"):
        """Initialize Anthropic agent"""
        self.client = AsyncAnthropic(api_key=api_key)
        self.model = model
        logger.info(f"Anthropic agent initialized with model: {model}")

    async def analyze_market(self, market_data: Dict[str, Any], context: str = "") -> Dict[str, Any]:
        """Analyze market with Claude"""
        prompt = f"Analyze this crypto data (context provided for memory): {json.dumps(market_data)}\nContext: {context}"
        
        try:
            response = await self.client.messages.create(
                model=self.model,
                max_tokens=1024,
                system="You are the Lead Research Analyst for a professional crypto trading desk. Confirm or reject signals with institutional-grade reasoning. Output ONLY valid JSON.",
                messages=[{"role": "user", "content": prompt}]
            )
            # Claude 3 returns a list of content blocks
            content = response.content[0].text
            result = json.loads(content)
            
            # Ensure result is a dictionary
            if isinstance(result, list) and result:
                result = result[0]
            elif not isinstance(result, dict):
                result = {"error": "Invalid format"}
                
            return result
        except Exception as e:
            logger.error(f"Anthropic analysis failed: {str(e)}")
            return {"sentiment": "neutral", "confidence": 0.0}

    async def generate_signal_confidence(
        self,
        symbol: str,
        indicators: Dict[str, Any],
        price_action: str,
        context: str = ""
    ) -> float:
        """Generate confidence score"""
        analysis = await self.analyze_market({"symbol": symbol, **indicators}, context=context)
        return float(analysis.get("confidence", 0.0))

    async def analyze_news_sentiment(self, news_text: str) -> Dict[str, Any]:
        """Analyze news sentiment with Claude"""
        prompt = f"""
        You are an expert crypto fundamental analyst. Analyze the following news and extract its market sentiment.
        
        News Text:
        {news_text}
        
        Provide your analysis in strictly valid JSON format with exactly these fields:
        - sentiment: "bullish", "bearish", or "neutral"
        - confidence: float between 0.0 and 1.0 representing your certainty
        - reasoning: brief explanation of your analysis
        """
        try:
            response = await self.client.messages.create(
                model=self.model,
                max_tokens=512,
                system="You are a crypto sentiment analysis engine. Return strictly JSON.",
                messages=[{"role": "user", "content": prompt}]
            )
            content = response.content[0].text
            result = json.loads(content)
            if isinstance(result, list) and result:
                result = result[0]
            elif not isinstance(result, dict):
                result = {"error": "Invalid format"}
            return result
        except Exception as e:
            logger.error(f"Anthropic news analysis failed: {str(e)}")
            return {"sentiment": "neutral", "confidence": 0.0, "reasoning": str(e)}

    async def generate_planitt_decision(
        self,
        *,
        market_data: Dict[str, Any],
        context: str = "",
    ) -> str:
        prompt = f"""
You are Planitt, a professional crypto signal desk.

Rules:
1) If confluence is weak/unclear, respond exactly: NO TRADE
2) Otherwise respond with ONLY strict JSON (no markdown/code fences) with keys:
   signal_type, confidence, strategy, reason, validity, risk_reward_ratio
3) signal_type must be BUY or SELL
4) confidence must be integer 1..100
5) validity format: 2-4 hours
6) risk_reward_ratio format: 1:2.0

Context:
{context}

Market input:
{market_data}
"""
        try:
            response = await self.client.messages.create(
                model=self.model,
                max_tokens=512,
                system="Return ONLY JSON or NO TRADE.",
                messages=[{"role": "user", "content": prompt}],
            )
            content = response.content[0].text.strip() if response.content else ""
            return content or "NO TRADE"
        except Exception as e:
            logger.error(f"Anthropic Planitt decision failed: {str(e)}")
            return "NO TRADE"


class OllamaAgent(LLMAgent):
    """Local Ollama-based LLM agent"""

    def __init__(self, base_url: str = "http://localhost:11434", model: str = "mistral"):
        """Initialize Ollama agent"""
        self.base_url = base_url
        # Ollama commonly expects fully-qualified model names like `mistral:latest`.
        # If the caller provides `mistral`, normalize to `mistral:latest`.
        self.model = model if ":" in model else f"{model}:latest"
        logger.info(f"Ollama agent initialized with model: {model} at {base_url}")

    async def analyze_market(self, market_data: Dict[str, Any], context: str = "") -> Dict[str, Any]:
        """Analyze market with local LLM"""
        prompt = f"""
        Analyze the following cryptocurrency market data and provide signal analysis.
        Use the provided context to learn from past successful trades.
        
        Historical Context:
        {context}
        
        Current Data:
        Symbol: {market_data.get('symbol')}
        Price: {market_data.get('price')}
        24h Change: {market_data.get('change_24h')}%
        Volume: {market_data.get('volume')}
        RSI: {market_data.get('rsi')}
        MACD: {market_data.get('macd')}
        
        Provide your analysis in JSON format with the following fields:
        - sentiment: "bullish", "bearish", or "neutral"
        - confidence: float between 0 and 1
        - risk_level: "low", "medium", or "high"
        - entry_points: list of suggested entry prices
        - take_profit: list of suggested take profit targets
        - stop_loss: suggested stop loss price
        - reasoning: brief explanation of your analysis
        """
        
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    f"{self.base_url}/api/chat",
                    json={
                        "model": self.model,
                        "messages": [
                            {
                                "role": "user",
                                "content": f"You are a lead crypto research analyst. Always respond in JSON format.\n\n{prompt}"
                            }
                        ],
                        "stream": False,
                        "format": "json"
                    },
                    timeout=60.0
                )
                response.raise_for_status()
                result = response.json()
                content = result.get("message", {}).get("content", "{}")
                parsed = json.loads(content)
                
                # Ensure it is a dictionary
                if isinstance(parsed, list) and parsed:
                    parsed = parsed[0]
                elif not isinstance(parsed, dict):
                    parsed = {"error": "Invalid format"}
                    
                return parsed
            except Exception as e:
                logger.error(f"Ollama analysis failed: {str(e)}")
                return {"sentiment": "neutral", "confidence": 0.0}

    async def generate_planitt_decision(
        self,
        *,
        market_data: Dict[str, Any],
        context: str = "",
    ) -> str:
        """
        Generate a strict Planitt decision for trading signals.

        Output contract (STRICT):
        - Either the literal string: "NO TRADE"
        - Or JSON matching the PlanittLLMDecision schema:
          {
            "signal_type":"BUY"|"SELL",
            "confidence": 1..100,
            "strategy":"string",
            "reason":"string",
            "validity":"2-4 hours",
            "risk_reward_ratio":"1:<number>"
          }

        We compute TP/SL/entry_range deterministically in Python later; the model only decides
        whether to trade and provides human-readable strategy/reasoning.
        """

        decision_prompt = f"""
You are Planitt, a professional crypto signal desk that ONLY recommends trades when strong confluence exists.

You must obey the following rules:
1. If conditions are unclear, weak trend, or confluence is insufficient, respond with exactly:
NO TRADE
2. Otherwise respond with ONLY strict JSON (no markdown, no code fences) with EXACTLY these keys:
   signal_type, confidence, strategy, reason, validity, risk_reward_ratio
3. signal_type must be "BUY" or "SELL".
4. confidence must be an integer between 1 and 100. Use >70 only when confluence is strong.
5. validity must be exactly "2-4 hours".
6. risk_reward_ratio must be a string like "1:2.1" (1:<number>).
7. reason must be a short single line (<=80 chars). No newlines.
8. strategy must be a short slug (snake_case).

Level consistency guidance (use if helpful, but do not output numeric levels here):
- For BUY: stop_loss must be below entry, take profits above entry.
- For SELL: stop_loss above entry, take profits below entry.

Return ONLY JSON or ONLY NO TRADE.

Context (recent successful patterns, may be empty):
{context}

Market input (pre-gates already validated confluence candidates):
{market_data}
"""

        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "user",
                    "content": decision_prompt,
                },
            ],
            "stream": False,
            # Keep responses short and predictable for strict parsing.
            "format": "json",
            "options": {
                "temperature": 0.1,
                # Enough tokens to output a complete strict JSON object, but not too many.
                "num_predict": 140,
            },
        }

        from config.settings import settings

        timeout_seconds = float(getattr(settings, "OLLAMA_REQUEST_TIMEOUT_SECONDS", 120))
        max_retries = max(0, int(getattr(settings, "OLLAMA_MAX_RETRIES", 1)))
        timeout = httpx.Timeout(connect=5.0, read=timeout_seconds, write=10.0, pool=5.0)

        async with httpx.AsyncClient(timeout=timeout) as client:
            for attempt in range(max_retries + 1):
                try:
                    response = await client.post(
                        f"{self.base_url}/api/chat",
                        json=payload,
                    )
                    response.raise_for_status()
                    result = response.json()
                    content = result.get("message", {}).get("content", "").strip()
                    return content
                except httpx.ReadTimeout as e:
                    if attempt >= max_retries:
                        logger.error(
                            "Ollama Planitt decision timeout after retries: model=%s timeout=%ss error=%r",
                            self.model,
                            timeout_seconds,
                            e,
                        )
                        return "NO TRADE"
                    backoff_seconds = min(2.0, 0.5 * (attempt + 1))
                    logger.warning(
                        "Ollama Planitt decision timed out, retrying: attempt=%s/%s backoff=%ss",
                        attempt + 1,
                        max_retries + 1,
                        backoff_seconds,
                    )
                    await asyncio.sleep(backoff_seconds)
                except Exception as e:
                    logger.error(
                        "Ollama Planitt decision failed: type=%s error=%r",
                        type(e).__name__,
                        e,
                    )
                    return "NO TRADE"

    async def generate_signal_confidence(
        self,
        symbol: str,
        indicators: Dict[str, Any],
        price_action: str,
        context: str = ""
    ) -> float:
        """Generate confidence score"""
        analysis = await self.analyze_market({"symbol": symbol, **indicators}, context=context)
        return float(analysis.get("confidence", 0.0))

    async def analyze_news_sentiment(self, news_text: str) -> Dict[str, Any]:
        """Analyze news sentiment with local LLM"""
        prompt = f"""
        You are an expert crypto fundamental analyst. Analyze the following news and extract its market sentiment.
        
        News Text:
        {news_text}
        
        Provide your analysis in JSON format with exactly these fields:
        - sentiment: "bullish", "bearish", or "neutral"
        - confidence: float between 0.0 and 1.0 representing your certainty
        - reasoning: brief explanation of your analysis
        """
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    f"{self.base_url}/api/chat",
                    json={
                        "model": self.model,
                        "messages": [
                            {
                                "role": "user",
                                "content": f"You are a crypto sentiment analysis engine. Always respond in JSON format.\n\n{prompt}"
                            }
                        ],
                        "stream": False,
                        "format": "json"
                    },
                    timeout=60.0
                )
                response.raise_for_status()
                result = response.json()
                content = result.get("message", {}).get("content", "{}")
                parsed = json.loads(content)
                if isinstance(parsed, list) and parsed:
                    parsed = parsed[0]
                elif not isinstance(parsed, dict):
                    parsed = {"error": "Invalid format"}
                return parsed
            except Exception as e:
                logger.error(f"Ollama news analysis failed: {str(e)}")
                return {"sentiment": "neutral", "confidence": 0.0, "reasoning": str(e)}


class LLMAgentFactory:
    """Factory for creating LLM agents"""

    @staticmethod
    def create_agent(
        provider: str,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        base_url: Optional[str] = None,
    ) -> LLMAgent:
        """Create LLM agent based on provider"""
        if provider == "openai":
            if not api_key:
                logger.warning("OpenAI API key not provided, using empty key (API calls will fail)")
            return OpenAIAgent(api_key or "", model or "gpt-4o")
        elif provider == "anthropic":
            if not api_key:
                logger.warning("Anthropic API key not provided, using empty key (API calls will fail)")
            return AnthropicAgent(api_key or "", model or "claude-3-opus-20240229")
        elif provider == "ollama":
            if not base_url:
                base_url = "http://localhost:11434"
                logger.info(f"Ollama base_url not provided, using default: {base_url}")
            return OllamaAgent(base_url, model or "mistral")
        elif provider == "transformer":
            from src.llm.transformer_agent import TransformerAgent
            from config.settings import settings
            return TransformerAgent(model_path=settings.TRANSFORMER_MODEL_PATH)
        else:
            raise ValueError(f"Unknown provider: {provider}")
