from __future__ import annotations

"""Configuration settings for Crypto Bot."""

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
        case_sensitive=True
    )

    # Application
    APP_NAME: str = "Crypto Trading Signal Server"
    APP_VERSION: str = "1.0.0"
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

    # API Keys & Credentials
    CRYPTO_SOURCE_API_KEY: str = os.getenv("CRYPTO_SOURCE_API_KEY", "")
    # Legacy Binance (deprecated — use CoinDCX)
    BINANCE_API_KEY: str = ""
    BINANCE_API_SECRET: str = ""
    BINANCE_TESTNET: bool = False

    # CoinDCX Futures advisor
    COINDCX_MARGIN_CURRENCIES_RAW: str = os.getenv("COINDCX_MARGIN_CURRENCIES", "USDT,INR")
    COINDCX_DEFAULT_MARGIN: str = os.getenv("COINDCX_DEFAULT_MARGIN", "USDT")
    MAX_WEEKLY_SIGNALS: int = int(os.getenv("MAX_WEEKLY_SIGNALS", "14"))
    MIN_WEEKLY_BTC_PCT: float = float(os.getenv("MIN_WEEKLY_BTC_PCT", "0.20"))
    MIN_WEEKLY_MAJORS_PCT: float = float(os.getenv("MIN_WEEKLY_MAJORS_PCT", "0.35"))
    ADVISOR_MIN_CONFIDENCE: float = float(os.getenv("ADVISOR_MIN_CONFIDENCE", "0.70"))
    ADVISOR_OUTPUT_DIR: str = os.getenv("ADVISOR_OUTPUT_DIR", "output/reports")
    ADVISOR_MIN_CONFLUENCE_HITS: int = int(os.getenv("ADVISOR_MIN_CONFLUENCE_HITS", "3"))
    CHART_RENDERER: str = os.getenv("CHART_RENDERER", "playwright")  # playwright | matplotlib
    ENABLE_PLANITT_BACKEND: bool = os.getenv("ENABLE_PLANITT_BACKEND", "false").lower() == "true"
    ENABLE_ADVISOR_SCANNER: bool = os.getenv("ENABLE_ADVISOR_SCANNER", "true").lower() == "true"
    ADVISOR_SCAN_TIMEFRAMES_RAW: str = os.getenv("ADVISOR_SCAN_TIMEFRAMES", "15m,1h,4h,1d")

    # LLM Configuration
    LLM_PROVIDER: str = "openai"  # openai, anthropic, local
    OPENAI_API_KEY: Optional[str] = None
    OPENAI_MODEL: str = "gpt-4o"
    ANTHROPIC_API_KEY: Optional[str] = None
    ANTHROPIC_MODEL: str = "claude-3-opus-20240229"
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "mistral"
    OLLAMA_REQUEST_TIMEOUT_SECONDS: int = int(os.getenv("OLLAMA_REQUEST_TIMEOUT_SECONDS", "120"))
    OLLAMA_MAX_RETRIES: int = int(os.getenv("OLLAMA_MAX_RETRIES", "1"))
    SIGNAL_VERIFICATION_ENABLED: bool = True
    SIGNAL_VERIFICATION_MODEL: str = "qwen2.5:3b"
    SIGNAL_VERIFICATION_TIMEOUT: int = 30
    TRANSFORMER_MODEL_PATH: str = "models/crypto-transformer"

    # JWT Authentication
    JWT_SECRET_KEY: str = os.getenv("JWT_SECRET_KEY", "your-secret-key-change-in-production")
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRATION_HOURS: int = 24

    # Trading Configuration
    TIMEFRAMES: list[str] = ["5m", "15m", "1h", "4h", "1d"]
    DEFAULT_TIMEFRAME: str = "15m"
    SUPPORTED_CRYPTOS: list[str] = [
        "BTC", "ETH", "BNB", "SOL", "XRP", "ADA", "AVAX", "POL", "DOGE", "LINK"
    ]
    SCALP_TIMEFRAMES: list[str] = ["5m", "15m"]
    SWING_TIMEFRAMES: list[str] = ["1h", "4h"]
    POSITION_TIMEFRAMES: list[str] = ["1d"]

    # Risk Management
    MAX_POSITION_SIZE: float = 0.05  # 5% of portfolio
    MIN_POSITION_SIZE: float = 0.01  # 1% of portfolio
    MAX_OPEN_POSITIONS: int = 5
    RISK_PER_TRADE_PERCENT: float = 1.0  # 1% portfolio risk per trade

    # Fallback static TP/SL (only used when ATR is unavailable)
    DEFAULT_STOP_LOSS_PERCENT: float = 2.0
    DEFAULT_TP_PERCENT: float = 5.0

    # === ADAPTIVE ATR-BASED TP/SL MULTIPLIERS ===
    # Trending markets: wider targets, room to run
    ATR_TP_MULTIPLIER_TRENDING: float = 3.0
    ATR_SL_MULTIPLIER_TRENDING: float = 1.5
    # Ranging markets: tighter targets, mean-reversion style
    ATR_TP_MULTIPLIER_RANGING: float = 1.8
    ATR_SL_MULTIPLIER_RANGING: float = 1.0
    # Volatile/choppy markets: very tight SL, moderate TP
    ATR_TP_MULTIPLIER_VOLATILE: float = 2.0
    ATR_SL_MULTIPLIER_VOLATILE: float = 0.8

    # === SIGNAL QUALITY CONTROLS ===
    MIN_RISK_REWARD_RATIO: float = 1.5       # Reject signals with R:R < 1.5
    MIN_CONFLUENCE_STRATEGIES: int = 2        # Minimum strategies that must agree
    ADX_TREND_THRESHOLD: float = 25.0        # ADX >= this = trending
    ADX_RANGING_THRESHOLD: float = 20.0      # ADX < this = ranging

    # === MULTI-TIMEFRAME ===
    MTF_PRIMARY_TIMEFRAME: str = "4h"        # Trend direction
    MTF_SECONDARY_TIMEFRAME: str = "1h"      # Trend confirmation
    MTF_ENTRY_TIMEFRAME: str = "15m"         # Entry timing

    # Signal Configuration
    MIN_SIGNAL_CONFIDENCE: float = 0.60
    ENABLE_LLM_ANALYSIS: bool = True
    LLM_ANALYSIS_THRESHOLD: float = 0.50
    SCAN_INTERVAL: int = 60  # seconds

    # --------------------------------------------------------------------
    # Planitt (recommended signals) - FastAPI processor -> NestJS backend
    # --------------------------------------------------------------------
    # NestJS backend public base URL (used by clients, if needed) or internal
    # base URL for service-to-service communication.
    PLANITT_BACKEND_BASE_URL: str = os.getenv("PLANITT_BACKEND_BASE_URL", "http://localhost:3000")
    # API key used by FastAPI processor to authenticate with NestJS internal endpoints.
    PLANITT_BACKEND_INTERNAL_API_KEY: str = os.getenv("PLANITT_BACKEND_INTERNAL_API_KEY", "")
    # API key used to protect Planitt processor endpoints on FastAPI (internal only).
    PLANITT_PROCESSOR_INTERNAL_API_KEY: str = os.getenv("PLANITT_PROCESSOR_INTERNAL_API_KEY", "change-me")
    # Only accept LLM decisions above this threshold.
    PLANITT_MIN_CONFIDENCE: int = int(os.getenv("PLANITT_MIN_CONFIDENCE", "70"))
    PLANITT_AUTO_PUBLISH_CONFIDENCE: float = float(os.getenv("PLANITT_AUTO_PUBLISH_CONFIDENCE", "0.80"))
    PLANITT_SIGNAL_COOLDOWN_CANDLES: int = int(os.getenv("PLANITT_SIGNAL_COOLDOWN_CANDLES", "2"))
    # Comma separated list of scan timeframes, ex: "5m,15m,1h"
    PLANITT_SCAN_TIMEFRAMES_RAW: str = os.getenv("PLANITT_SCAN_TIMEFRAMES", "")
    # Tunables for confluence pre-gates (helps reduce over-filtering in live markets)
    PLANITT_MIN_CONFLUENCE_HITS: int = int(os.getenv("PLANITT_MIN_CONFLUENCE_HITS", "2"))
    PLANITT_VOLUME_MULTIPLIER: float = float(os.getenv("PLANITT_VOLUME_MULTIPLIER", "1.2"))
    PLANITT_TOUCH_TOLERANCE_PCT: float = float(os.getenv("PLANITT_TOUCH_TOLERANCE_PCT", "0.01"))
    PLANITT_MIN_CANDLES: int = int(os.getenv("PLANITT_MIN_CANDLES", "205"))
    PLANITT_ADX_TREND_THRESHOLD: float = float(os.getenv("PLANITT_ADX_TREND_THRESHOLD", "20"))
    # When True, do not hard-reject VOLATILE regime (ATR spikes often coincide with real trends).
    PLANITT_ALLOW_VOLATILE_THROUGH_GATES: bool = (
        os.getenv("PLANITT_ALLOW_VOLATILE_THROUGH_GATES", "true").lower() == "true"
    )
    # When True, if 20/50/200 are not stacked but ADX+DI agree with trend regime, still pick a side.
    PLANITT_RELAX_SIDE_FROM_REGIME: bool = os.getenv("PLANITT_RELAX_SIDE_FROM_REGIME", "true").lower() == "true"
    PLANITT_REQUIRE_SWING_STRUCTURE: bool = os.getenv("PLANITT_REQUIRE_SWING_STRUCTURE", "false").lower() == "true"
    ENABLE_CANDLESTICK_PATTERNS: bool = os.getenv("ENABLE_CANDLESTICK_PATTERNS", "true").lower() == "true"
    PATTERN_MIN_STRENGTH: float = float(os.getenv("PATTERN_MIN_STRENGTH", "0.55"))
    PATTERN_WEIGHT: float = float(os.getenv("PATTERN_WEIGHT", "0.06"))
    PATTERN_RISK_ADJUSTMENT_ENABLED: bool = os.getenv("PATTERN_RISK_ADJUSTMENT_ENABLED", "false").lower() == "true"
    # Keep local auto generation enabled, disable on hosted ops services when needed.
    ENABLE_BACKGROUND_SCANNER: bool = os.getenv("ENABLE_BACKGROUND_SCANNER", "true").lower() == "true"
    FASTAPI_CORS_ORIGINS_RAW: str = os.getenv("FASTAPI_CORS_ORIGINS", "*")
    FASTAPI_TRUSTED_HOSTS_RAW: str = os.getenv("FASTAPI_TRUSTED_HOSTS", "*")

    # Logging
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    LOG_FILE: str = "logs/app.log"
    # Avoid file-lock contention on bind mounts during local Docker reload.
    LOG_TO_FILE: bool = os.getenv("LOG_TO_FILE", "false").lower() == "true"

    # Monitoring
    ENABLE_PROMETHEUS: bool = True
    PROMETHEUS_PORT: int = 9090
    ENABLE_SENTRY: bool = False
    SENTRY_DSN: Optional[str] = None

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
    """Get cached settings instance.

    In Docker bind-mount environments on macOS, reading `.env` can intermittently
    fail with OS-level file locking/deadlock errors. Allow disabling dotenv file
    parsing and rely on process environment only.
    """
    disable_dotenv = os.getenv("DISABLE_DOTENV", "false").lower() == "true"
    if disable_dotenv:
        return Settings(_env_file=None)
    return Settings()


# Export singleton
settings = get_settings()
