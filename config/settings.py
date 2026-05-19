from __future__ import annotations

"""Configuration settings for CoinDCX Futures Advisor."""

from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache
from pathlib import Path
from typing import Optional
import os


class Settings(BaseSettings):
    """Main application settings"""

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
        case_sensitive=True,
    )

    # Application
    APP_NAME: str = "CoinDCX Futures Advisor"
    APP_VERSION: str = "2.0.0"
    DEBUG: bool = False
    ENV: str = os.getenv("ENV", "development")

    # Server
    SERVER_HOST: str = "0.0.0.0"
    SERVER_PORT: int = 8000
    WORKERS: int = 4

    # Database
    MONGODB_URI: str = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
    MONGODB_DB_NAME: str = os.getenv("MONGODB_DB_NAME", "planitt")
    UNIFIED_COLLECTIONS_ENABLED: bool = (
        os.getenv("UNIFIED_COLLECTIONS_ENABLED", "true").strip().lower() == "true"
    )

    # API protection (header x-api-key on /api/v1/advisor/*)
    PLANITT_PROCESSOR_INTERNAL_API_KEY: str = os.getenv("PLANITT_PROCESSOR_INTERNAL_API_KEY", "change-me")
    CRYPTO_SOURCE_API_KEY: str = os.getenv("CRYPTO_SOURCE_API_KEY", "")

    # CoinDCX Futures advisor
    COINDCX_MARGIN_CURRENCIES_RAW: str = os.getenv("COINDCX_MARGIN_CURRENCIES", "USDT,INR")
    COINDCX_DEFAULT_MARGIN: str = os.getenv("COINDCX_DEFAULT_MARGIN", "USDT")
    MAX_WEEKLY_SIGNALS: int = int(os.getenv("MAX_WEEKLY_SIGNALS", "14"))
    MIN_WEEKLY_BTC_PCT: float = float(os.getenv("MIN_WEEKLY_BTC_PCT", "0.20"))
    MIN_WEEKLY_MAJORS_PCT: float = float(os.getenv("MIN_WEEKLY_MAJORS_PCT", "0.35"))
    ADVISOR_MIN_CONFIDENCE: float = float(os.getenv("ADVISOR_MIN_CONFIDENCE", "0.70"))
    ADVISOR_OUTPUT_DIR: str = os.getenv("ADVISOR_OUTPUT_DIR", "output/reports")
    ADVISOR_MIN_CONFLUENCE_HITS: int = int(os.getenv("ADVISOR_MIN_CONFLUENCE_HITS", "3"))
    ADVISOR_SCAN_TIMEFRAMES_RAW: str = os.getenv("ADVISOR_SCAN_TIMEFRAMES", "15m,1h,4h,1d")
    CHART_RENDERER: str = os.getenv("CHART_RENDERER", "matplotlib")  # matplotlib | playwright

    # LLM (optional narrative for PDFs)
    LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "ollama")
    OPENAI_API_KEY: Optional[str] = None
    OPENAI_MODEL: str = "gpt-4o"
    ANTHROPIC_API_KEY: Optional[str] = None
    ANTHROPIC_MODEL: str = "claude-3-opus-20240229"
    OLLAMA_BASE_URL: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    OLLAMA_MODEL: str = os.getenv("OLLAMA_MODEL", "0xroyce/plutus")
    OLLAMA_REQUEST_TIMEOUT_SECONDS: int = int(os.getenv("OLLAMA_REQUEST_TIMEOUT_SECONDS", "120"))
    OLLAMA_MAX_RETRIES: int = int(os.getenv("OLLAMA_MAX_RETRIES", "1"))
    ENABLE_LLM_ANALYSIS: bool = os.getenv("ENABLE_LLM_ANALYSIS", "true").lower() == "true"
    ADVISOR_LLM_SYSTEM_PROMPT_PATH: Optional[str] = os.getenv("ADVISOR_LLM_SYSTEM_PROMPT_PATH")

    # Background scanner
    ENABLE_BACKGROUND_SCANNER: bool = os.getenv("ENABLE_BACKGROUND_SCANNER", "true").lower() == "true"
    SCAN_INTERVAL: int = int(os.getenv("SCAN_INTERVAL", "900"))

    # Confluence engine tunables (used by src/planitt/confluence.py)
    PLANITT_MIN_CANDLES: int = int(os.getenv("PLANITT_MIN_CANDLES", "205"))
    PLANITT_ADX_TREND_THRESHOLD: float = float(os.getenv("PLANITT_ADX_TREND_THRESHOLD", "20"))
    PLANITT_VOLUME_MULTIPLIER: float = float(os.getenv("PLANITT_VOLUME_MULTIPLIER", "1.2"))
    PLANITT_TOUCH_TOLERANCE_PCT: float = float(os.getenv("PLANITT_TOUCH_TOLERANCE_PCT", "0.01"))
    PLANITT_ALLOW_VOLATILE_THROUGH_GATES: bool = (
        os.getenv("PLANITT_ALLOW_VOLATILE_THROUGH_GATES", "true").lower() == "true"
    )
    PLANITT_RELAX_SIDE_FROM_REGIME: bool = os.getenv("PLANITT_RELAX_SIDE_FROM_REGIME", "true").lower() == "true"
    PLANITT_REQUIRE_SWING_STRUCTURE: bool = os.getenv("PLANITT_REQUIRE_SWING_STRUCTURE", "false").lower() == "true"
    ENABLE_CANDLESTICK_PATTERNS: bool = os.getenv("ENABLE_CANDLESTICK_PATTERNS", "true").lower() == "true"
    PATTERN_MIN_STRENGTH: float = float(os.getenv("PATTERN_MIN_STRENGTH", "0.55"))
    PATTERN_WEIGHT: float = float(os.getenv("PATTERN_WEIGHT", "0.06"))
    PATTERN_RISK_ADJUSTMENT_ENABLED: bool = os.getenv("PATTERN_RISK_ADJUSTMENT_ENABLED", "false").lower() == "true"

    # Risk defaults
    RISK_PER_TRADE_PERCENT: float = 1.0
    MIN_RISK_REWARD_RATIO: float = 1.5
    MAX_POSITION_SIZE: float = 0.05
    MIN_POSITION_SIZE: float = 0.01

    # Trading universe
    SUPPORTED_CRYPTOS: list[str] = [
        "BTC", "ETH", "BNB", "SOL", "XRP", "ADA", "AVAX", "POL", "DOGE", "LINK",
    ]

    FASTAPI_CORS_ORIGINS_RAW: str = os.getenv("FASTAPI_CORS_ORIGINS", "*")
    FASTAPI_TRUSTED_HOSTS_RAW: str = os.getenv("FASTAPI_TRUSTED_HOSTS", "*")

    # Logging
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    LOG_FILE: str = "logs/app.log"
    LOG_TO_FILE: bool = os.getenv("LOG_TO_FILE", "false").lower() == "true"

    # Monitoring
    ENABLE_PROMETHEUS: bool = True

    @property
    def coindcx_margin_currencies_list(self) -> list[str]:
        return [c.strip().upper() for c in self.COINDCX_MARGIN_CURRENCIES_RAW.split(",") if c.strip()]

    @property
    def advisor_scan_timeframes(self) -> list[str]:
        raw = self.ADVISOR_SCAN_TIMEFRAMES_RAW.strip()
        if not raw:
            return ["15m", "1h", "4h", "1d"]
        return [t.strip() for t in raw.split(",") if t.strip()]

    @property
    def advisor_output_path(self) -> Path:
        return Path(self.ADVISOR_OUTPUT_DIR)


@lru_cache()
def get_settings() -> Settings:
    disable_dotenv = os.getenv("DISABLE_DOTENV", "false").lower() == "true"
    if disable_dotenv:
        return Settings(_env_file=None)
    return Settings()


settings = get_settings()
