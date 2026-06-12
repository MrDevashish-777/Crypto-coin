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
    MONGODB_MAX_POOL_SIZE: int = int(os.getenv("MONGODB_MAX_POOL_SIZE", "50"))
    MONGODB_MIN_POOL_SIZE: int = int(os.getenv("MONGODB_MIN_POOL_SIZE", "0"))
    MONGODB_SERVER_SELECTION_TIMEOUT_MS: int = int(os.getenv("MONGODB_SERVER_SELECTION_TIMEOUT_MS", "30000"))
    MONGODB_CONNECT_TIMEOUT_MS: int = int(os.getenv("MONGODB_CONNECT_TIMEOUT_MS", "20000"))
    MONGODB_SOCKET_TIMEOUT_MS: int = int(os.getenv("MONGODB_SOCKET_TIMEOUT_MS", "45000"))
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
    ADVISOR_STRICT_ALLOCATION: bool = os.getenv("ADVISOR_STRICT_ALLOCATION", "true").lower() == "true"
    ADVISOR_MIN_CONFIDENCE: float = float(os.getenv("ADVISOR_MIN_CONFIDENCE", "0.72"))
    ADVISOR_OUTPUT_DIR: str = os.getenv("ADVISOR_OUTPUT_DIR", "output/reports")
    ADVISOR_MIN_CONFLUENCE_HITS: int = int(os.getenv("ADVISOR_MIN_CONFLUENCE_HITS", "3"))
    ADVISOR_MIN_AGREEING_SOURCES: int = int(os.getenv("ADVISOR_MIN_AGREEING_SOURCES", "4"))
    ADVISOR_MIN_VOTE_MARGIN: float = float(os.getenv("ADVISOR_MIN_VOTE_MARGIN", "0.15"))
    ADVISOR_SYMBOL_COOLDOWN_HOURS: int = int(os.getenv("ADVISOR_SYMBOL_COOLDOWN_HOURS", "6"))
    ADVISOR_SCAN_TIMEFRAMES_RAW: str = os.getenv("ADVISOR_SCAN_TIMEFRAMES", "1h,4h,1d")
    ADVISOR_BACKTEST_QUALITY_GATE_ENABLED: bool = (
        os.getenv("ADVISOR_BACKTEST_QUALITY_GATE_ENABLED", "false").lower() == "true"
    )
    ADVISOR_BACKTEST_MIN_EXPECTANCY: float = float(
        os.getenv("ADVISOR_BACKTEST_MIN_EXPECTANCY", "0.0")
    )
    ADVISOR_QUALITY_TIER_A_MIN: float = float(os.getenv("ADVISOR_QUALITY_TIER_A_MIN", "0.88"))
    ADVISOR_QUALITY_TIER_B_MIN: float = float(os.getenv("ADVISOR_QUALITY_TIER_B_MIN", "0.78"))
    ADVISOR_MIN_COMPOSITE_SCORE: float = float(os.getenv("ADVISOR_MIN_COMPOSITE_SCORE", "0.82"))
    ADVISOR_MIN_MTF_SCORE: float = float(os.getenv("ADVISOR_MIN_MTF_SCORE", "0.75"))
    ADVISOR_PUBLISH_MIN_QUALITY_TIER: str = os.getenv("ADVISOR_PUBLISH_MIN_QUALITY_TIER", "B").upper()
    ADVISOR_MTF_SCORE_WEIGHT: float = float(os.getenv("ADVISOR_MTF_SCORE_WEIGHT", "0.20"))
    ADVISOR_BLOCK_NEGATIVE_BUCKETS: bool = (
        os.getenv("ADVISOR_BLOCK_NEGATIVE_BUCKETS", "true").lower() == "true"
    )
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
    PLANITT_TOUCH_TOLERANCE_PCT: float = float(os.getenv("PLANITT_TOUCH_TOLERANCE_PCT", "0.015"))
    PLANITT_ALLOW_VOLATILE_THROUGH_GATES: bool = (
        os.getenv("PLANITT_ALLOW_VOLATILE_THROUGH_GATES", "true").lower() == "true"
    )
    PLANITT_RELAX_SIDE_FROM_REGIME: bool = os.getenv("PLANITT_RELAX_SIDE_FROM_REGIME", "true").lower() == "true"
    PLANITT_REQUIRE_SWING_STRUCTURE: bool = os.getenv("PLANITT_REQUIRE_SWING_STRUCTURE", "false").lower() == "true"
    PLANITT_SWING_STRICT_ADX_MAX: float = float(os.getenv("PLANITT_SWING_STRICT_ADX_MAX", "26"))
    PLANITT_ALLOW_RANGING_WITH_DIRECTION: bool = (
        os.getenv("PLANITT_ALLOW_RANGING_WITH_DIRECTION", "true").lower() == "true"
    )
    PLANITT_RANGING_MIN_DI_SPREAD: float = float(os.getenv("PLANITT_RANGING_MIN_DI_SPREAD", "1.5"))
    PLANITT_RELAX_MOMENTUM: bool = os.getenv("PLANITT_RELAX_MOMENTUM", "true").lower() == "true"
    PLANITT_MIN_HITS_STRONG_ADX: int = int(os.getenv("PLANITT_MIN_HITS_STRONG_ADX", "2"))
    PLANITT_MTF_MIN_AGREEING: int = int(os.getenv("PLANITT_MTF_MIN_AGREEING", "2"))
    PLANITT_MTF_ALLOW_RANGING_HTF: bool = os.getenv("PLANITT_MTF_ALLOW_RANGING_HTF", "true").lower() == "true"
    PLANITT_ALLOW_TREND_CONTINUATION: bool = (
        os.getenv("PLANITT_ALLOW_TREND_CONTINUATION", "true").lower() == "true"
    )
    PLANITT_TREND_CONTINUATION_ADX: float = float(os.getenv("PLANITT_TREND_CONTINUATION_ADX", "22"))
    PLANITT_OPPOSING_PATTERN_VETO_STRENGTH: float = float(
        os.getenv("PLANITT_OPPOSING_PATTERN_VETO_STRENGTH", "0.70")
    )
    PLANITT_REQUIRE_MANDATORY_CATEGORIES: bool = (
        os.getenv("PLANITT_REQUIRE_MANDATORY_CATEGORIES", "true").lower() == "true"
    )
    PLANITT_ALLOW_REVERSAL_SETUPS: bool = (
        os.getenv("PLANITT_ALLOW_REVERSAL_SETUPS", "false").lower() == "true"
    )
    ENABLE_CANDLESTICK_PATTERNS: bool = os.getenv("ENABLE_CANDLESTICK_PATTERNS", "true").lower() == "true"
    PATTERN_MIN_STRENGTH: float = float(os.getenv("PATTERN_MIN_STRENGTH", "0.60"))
    PATTERN_AT_LEVEL_REQUIRED: bool = os.getenv("PATTERN_AT_LEVEL_REQUIRED", "true").lower() == "true"
    PATTERN_WEIGHT: float = float(os.getenv("PATTERN_WEIGHT", "0.06"))
    PATTERN_RISK_ADJUSTMENT_ENABLED: bool = os.getenv("PATTERN_RISK_ADJUSTMENT_ENABLED", "false").lower() == "true"

    # Nadaraya-Watson Envelope (LuxAlgo, non-repainting)
    ENABLE_NWE: bool = os.getenv("ENABLE_NWE", "true").lower() == "true"
    NWE_BANDWIDTH: float = float(os.getenv("NWE_BANDWIDTH", "8"))
    NWE_MULTIPLIER: float = float(os.getenv("NWE_MULTIPLIER", "3"))
    NWE_LOOKBACK: int = int(os.getenv("NWE_LOOKBACK", "500"))
    NWE_WEIGHT: float = float(os.getenv("NWE_WEIGHT", "0.10"))
    NWE_BAND_TOUCH_PCT: float = float(os.getenv("NWE_BAND_TOUCH_PCT", "0.003"))
    NWE_TP_SL_ENABLED: bool = os.getenv("NWE_TP_SL_ENABLED", "true").lower() == "true"
    NWE_TP_SL_MIN_CONFIDENCE: float = float(os.getenv("NWE_TP_SL_MIN_CONFIDENCE", "0.80"))
    NWE_SL_BUFFER_ATR_MULT: float = float(os.getenv("NWE_SL_BUFFER_ATR_MULT", "0.15"))

    # SOP trading parameters (env-configurable)
    SOP_MIN_SL_PCT: float = float(os.getenv("SOP_MIN_SL_PCT", "2.5"))
    SOP_MAX_SL_PCT: float = float(os.getenv("SOP_MAX_SL_PCT", "3.0"))
    SOP_MIN_RR: float = float(os.getenv("SOP_MIN_RR", "1.5"))
    SOP_HIGH_CONF_MIN_RR: float = float(os.getenv("SOP_HIGH_CONF_MIN_RR", "1.8"))
    SOP_HIGH_CONF_THRESHOLD: float = float(os.getenv("SOP_HIGH_CONF_THRESHOLD", "0.85"))
    SOP_HIGH_CONF_MIN_SOURCES: int = int(os.getenv("SOP_HIGH_CONF_MIN_SOURCES", "6"))
    SOP_LEVERAGED_SL_MIN: float = float(os.getenv("SOP_LEVERAGED_SL_MIN", "18.0"))
    SOP_LEVERAGED_SL_MAX: float = float(os.getenv("SOP_LEVERAGED_SL_MAX", "22.0"))

    # Risk defaults
    RISK_PER_TRADE_PERCENT: float = 1.0
    MIN_RISK_REWARD_RATIO: float = 1.5
    MAX_POSITION_SIZE: float = 0.05
    MIN_POSITION_SIZE: float = 0.01

    # Delta Exchange Execution
    DELTA_API_KEY: str = os.getenv("DELTA_API_KEY", "")
    DELTA_API_SECRET: str = os.getenv("DELTA_API_SECRET", "")
    DELTA_TESTNET: bool = os.getenv("DELTA_TESTNET", "true").lower() == "true"
    DELTA_EXECUTION_ENABLED: bool = os.getenv("DELTA_EXECUTION_ENABLED", "false").lower() == "true"
    DELTA_MAX_PORTFOLIO_RISK_PCT: float = float(os.getenv("DELTA_MAX_PORTFOLIO_RISK_PCT", "70.0"))

    # Trading universe
    SUPPORTED_CRYPTOS: list[str] = [
        "BTC", "ETH", "BNB", "SOL", "XRP", "ADA", "AVAX", "POL", "DOGE", "LINK",
    ]

    FASTAPI_CORS_ORIGINS_RAW: str = os.getenv("FASTAPI_CORS_ORIGINS", "*")
    FASTAPI_TRUSTED_HOSTS_RAW: str = os.getenv("FASTAPI_TRUSTED_HOSTS", "*")

    # Cloudinary Integration
    CLOUDINARY_URL: Optional[str] = os.getenv("CLOUDINARY_URL")

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
