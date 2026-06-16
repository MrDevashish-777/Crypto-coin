from __future__ import annotations

"""Configuration settings for CoinDCX Futures Advisor."""

from pydantic import AliasChoices, Field
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
    MAX_WEEKLY_SIGNALS: int = int(os.getenv("MAX_WEEKLY_SIGNALS", "100"))
    MAX_DAILY_SIGNALS: int = int(os.getenv("MAX_DAILY_SIGNALS", "25"))
    MAX_PUBLISH_PER_SCAN: int = int(os.getenv("MAX_PUBLISH_PER_SCAN", "8"))
    ADVISOR_TARGET_DAILY_SIGNALS: int = int(os.getenv("ADVISOR_TARGET_DAILY_SIGNALS", "10"))
    MIN_WEEKLY_BTC_PCT: float = float(os.getenv("MIN_WEEKLY_BTC_PCT", "0.20"))
    MIN_WEEKLY_MAJORS_PCT: float = float(os.getenv("MIN_WEEKLY_MAJORS_PCT", "0.35"))
    ADVISOR_STRICT_ALLOCATION: bool = os.getenv("ADVISOR_STRICT_ALLOCATION", "true").lower() == "true"
    ADVISOR_MIN_CONFIDENCE: float = float(os.getenv("ADVISOR_MIN_CONFIDENCE", "0.75"))
    ADVISOR_OUTPUT_DIR: str = os.getenv("ADVISOR_OUTPUT_DIR", "output/reports")
    ADVISOR_MIN_CONFLUENCE_HITS: int = int(os.getenv("ADVISOR_MIN_CONFLUENCE_HITS", "4"))
    ADVISOR_MIN_AGREEING_SOURCES: int = int(os.getenv("ADVISOR_MIN_AGREEING_SOURCES", "5"))
    ADVISOR_MIN_VOTE_MARGIN: float = float(os.getenv("ADVISOR_MIN_VOTE_MARGIN", "0.18"))
    ADVISOR_SYMBOL_COOLDOWN_HOURS: int = int(os.getenv("ADVISOR_SYMBOL_COOLDOWN_HOURS", "2"))
    ADVISOR_ALLOW_MULTI_TF_PER_SYMBOL: bool = (
        os.getenv("ADVISOR_ALLOW_MULTI_TF_PER_SYMBOL", "true").lower() == "true"
    )
    ADVISOR_PUBLISH_PRIORITY_SYMBOLS_RAW: str = os.getenv(
        "ADVISOR_PUBLISH_PRIORITY_SYMBOLS",
        "SOL,XRP,ARB,INJ,TIA,LINK,ATOM,AVAX,UNI,FIL,ADA,OP,NEAR,SUI,SEI",
    )
    # Relaxed gates for BUY-only high-volume mode (SELL blocked separately)
    ADVISOR_BUY_MIN_CONFIDENCE: float = float(os.getenv("ADVISOR_BUY_MIN_CONFIDENCE", "0.68"))
    ADVISOR_BUY_MIN_COMPOSITE_SCORE: float = float(os.getenv("ADVISOR_BUY_MIN_COMPOSITE_SCORE", "0.74"))
    ADVISOR_BUY_MIN_MTF_SCORE: float = float(os.getenv("ADVISOR_BUY_MIN_MTF_SCORE", "0.60"))
    ADVISOR_BUY_MIN_CONFLUENCE_HITS: int = int(os.getenv("ADVISOR_BUY_MIN_CONFLUENCE_HITS", "3"))
    ADVISOR_BUY_MIN_AGREEING_SOURCES: int = int(os.getenv("ADVISOR_BUY_MIN_AGREEING_SOURCES", "2"))
    ADVISOR_BUY_MIN_VOTE_MARGIN: float = float(os.getenv("ADVISOR_BUY_MIN_VOTE_MARGIN", "0.08"))
    ADVISOR_BUY_PUBLISH_MIN_QUALITY_TIER: str = os.getenv(
        "ADVISOR_BUY_PUBLISH_MIN_QUALITY_TIER", "C"
    ).upper()
    ADVISOR_SCAN_TIMEFRAMES_RAW: str = Field(
        default="1h,4h,1d",
        validation_alias=AliasChoices("ADVISOR_SCAN_TIMEFRAMES", "ADVISOR_SCAN_TIMEFRAMES_RAW"),
    )
    ADVISOR_ALLOWED_DIRECTIONS_RAW: str = Field(
        default="ALL",
        validation_alias=AliasChoices("ADVISOR_ALLOWED_DIRECTIONS", "ADVISOR_ALLOWED_DIRECTIONS_RAW"),
    )
    ADVISOR_BLOCKED_TIMEFRAMES_RAW: str = Field(
        default="",
        validation_alias=AliasChoices("ADVISOR_BLOCKED_TIMEFRAMES", "ADVISOR_BLOCKED_TIMEFRAMES_RAW"),
    )
    ADVISOR_SYMBOL_ALLOWLIST_RAW: str = os.getenv("ADVISOR_SYMBOL_ALLOWLIST", "")
    ADVISOR_BLOCK_SWING_HORIZON: bool = (
        os.getenv("ADVISOR_BLOCK_SWING_HORIZON", "false").lower() == "true"
    )
    ADVISOR_USE_SOP_WEIGHTS: bool = os.getenv("ADVISOR_USE_SOP_WEIGHTS", "true").lower() == "true"
    SOP_WEIGHTS_PATH: str = os.getenv("SOP_WEIGHTS_PATH", "config/sop_crypto_weights.json")
    # SELL segment — stricter than SOP baseline (fixes shorts against bull HTF)
    ADVISOR_SELL_MIN_CONFIDENCE: float = float(os.getenv("ADVISOR_SELL_MIN_CONFIDENCE", "0.78"))
    ADVISOR_SELL_MIN_COMPOSITE_SCORE: float = float(os.getenv("ADVISOR_SELL_MIN_COMPOSITE_SCORE", "0.86"))
    ADVISOR_SELL_MIN_MTF_SCORE: float = float(os.getenv("ADVISOR_SELL_MIN_MTF_SCORE", "0.90"))
    ADVISOR_SELL_MIN_CONFLUENCE_HITS: int = int(os.getenv("ADVISOR_SELL_MIN_CONFLUENCE_HITS", "5"))
    ADVISOR_SELL_MIN_AGREEING_SOURCES: int = int(os.getenv("ADVISOR_SELL_MIN_AGREEING_SOURCES", "6"))
    ADVISOR_SELL_MIN_VOTE_MARGIN: float = float(os.getenv("ADVISOR_SELL_MIN_VOTE_MARGIN", "0.20"))
    ADVISOR_SELL_PUBLISH_MIN_QUALITY_TIER: str = os.getenv(
        "ADVISOR_SELL_PUBLISH_MIN_QUALITY_TIER", "B"
    ).upper()
    ADVISOR_SELL_MIN_ADX: float = float(os.getenv("ADVISOR_SELL_MIN_ADX", "26"))
    ADVISOR_SELL_ALLOW_RANGING: bool = os.getenv("ADVISOR_SELL_ALLOW_RANGING", "false").lower() == "true"
    ADVISOR_SELL_MIN_DI_SPREAD: float = float(os.getenv("ADVISOR_SELL_MIN_DI_SPREAD", "3.0"))
    ADVISOR_REQUIRE_BTC_BEAR_FOR_SELL: bool = (
        os.getenv("ADVISOR_REQUIRE_BTC_BEAR_FOR_SELL", "true").lower() == "true"
    )
    ADVISOR_REQUIRE_BTC_BULL_FOR_BUY: bool = (
        os.getenv("ADVISOR_REQUIRE_BTC_BULL_FOR_BUY", "false").lower() == "true"
    )
    ADVISOR_SELL_ALLOWED_TIMEFRAMES_RAW: str = Field(
        default="4h,1d",
        validation_alias=AliasChoices("ADVISOR_SELL_ALLOWED_TIMEFRAMES", "ADVISOR_SELL_ALLOWED_TIMEFRAMES_RAW"),
    )
    ADVISOR_BLOCK_VOLATILE_SELL: bool = os.getenv("ADVISOR_BLOCK_VOLATILE_SELL", "true").lower() == "true"
    ADVISOR_TIER_A_SELL_MIN_MTF: float = float(os.getenv("ADVISOR_TIER_A_SELL_MIN_MTF", "0.95"))
    # Swing / 4h / 1d segment — require reachable TP within SOP swing validity
    ADVISOR_SWING_MIN_CONFIDENCE: float = float(os.getenv("ADVISOR_SWING_MIN_CONFIDENCE", "0.75"))
    ADVISOR_SWING_MIN_COMPOSITE_SCORE: float = float(os.getenv("ADVISOR_SWING_MIN_COMPOSITE_SCORE", "0.82"))
    ADVISOR_SWING_MIN_MTF_SCORE: float = float(os.getenv("ADVISOR_SWING_MIN_MTF_SCORE", "0.85"))
    ADVISOR_SWING_MIN_AGREEING_SOURCES: int = int(os.getenv("ADVISOR_SWING_MIN_AGREEING_SOURCES", "5"))
    ADVISOR_LIVE_PERFORMANCE_GATE_ENABLED: bool = (
        os.getenv("ADVISOR_LIVE_PERFORMANCE_GATE_ENABLED", "true").lower() == "true"
    )
    ADVISOR_LIVE_MIN_BUCKET_TRADES: int = int(os.getenv("ADVISOR_LIVE_MIN_BUCKET_TRADES", "2"))
    ADVISOR_LIVE_MIN_BUCKET_EXPECTANCY: float = float(
        os.getenv("ADVISOR_LIVE_MIN_BUCKET_EXPECTANCY", "0.0")
    )
    ADVISOR_BACKTEST_QUALITY_GATE_ENABLED: bool = (
        os.getenv("ADVISOR_BACKTEST_QUALITY_GATE_ENABLED", "false").lower() == "true"
    )
    ADVISOR_BACKTEST_MIN_EXPECTANCY: float = float(
        os.getenv("ADVISOR_BACKTEST_MIN_EXPECTANCY", "0.0")
    )
    ADVISOR_QUALITY_TIER_A_MIN: float = float(os.getenv("ADVISOR_QUALITY_TIER_A_MIN", "0.88"))
    ADVISOR_QUALITY_TIER_B_MIN: float = float(os.getenv("ADVISOR_QUALITY_TIER_B_MIN", "0.78"))
    ADVISOR_MIN_COMPOSITE_SCORE: float = float(os.getenv("ADVISOR_MIN_COMPOSITE_SCORE", "0.80"))
    ADVISOR_MIN_MTF_SCORE: float = float(os.getenv("ADVISOR_MIN_MTF_SCORE", "0.70"))
    ADVISOR_PUBLISH_MIN_QUALITY_TIER: str = os.getenv("ADVISOR_PUBLISH_MIN_QUALITY_TIER", "B").upper()
    ADVISOR_MTF_SCORE_WEIGHT: float = float(os.getenv("ADVISOR_MTF_SCORE_WEIGHT", "0.20"))
    ADVISOR_BLOCK_NEGATIVE_BUCKETS: bool = (
        os.getenv("ADVISOR_BLOCK_NEGATIVE_BUCKETS", "true").lower() == "true"
    )
    ADVISOR_POSITIVE_BUCKETS_ONLY: bool = (
        os.getenv("ADVISOR_POSITIVE_BUCKETS_ONLY", "false").lower() == "true"
    )
    BACKTEST_RISK_PER_TRADE_PCT: float = float(os.getenv("BACKTEST_RISK_PER_TRADE_PCT", "1.0"))
    ADVISOR_REACHABILITY_GATE_ENABLED: bool = (
        os.getenv("ADVISOR_REACHABILITY_GATE_ENABLED", "true").lower() == "true"
    )
    ADVISOR_REACHABILITY_K: float = float(os.getenv("ADVISOR_REACHABILITY_K", "1.2"))
    ADVISOR_REACHABILITY_AUTO_SWING: bool = (
        os.getenv("ADVISOR_REACHABILITY_AUTO_SWING", "true").lower() == "true"
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
    SCAN_INTERVAL: int = int(os.getenv("SCAN_INTERVAL", "300"))
    ADVISOR_RECONCILE_INTERVAL: int = int(os.getenv("ADVISOR_RECONCILE_INTERVAL", "300"))
    ADVISOR_RECONCILE_ON_STARTUP: bool = (
        os.getenv("ADVISOR_RECONCILE_ON_STARTUP", "true").lower() == "true"
    )

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
            return ["15m", "1h"]
        blocked = set(self.advisor_blocked_timeframes)
        return [t.strip() for t in raw.split(",") if t.strip() and t.strip() not in blocked]

    @property
    def advisor_allowed_directions(self) -> frozenset[str]:
        raw = self.ADVISOR_ALLOWED_DIRECTIONS_RAW.strip()
        if not raw or raw.upper() == "ALL":
            return frozenset({"BUY", "SELL"})
        return frozenset(d.strip().upper() for d in raw.split(",") if d.strip())

    @property
    def advisor_blocked_timeframes(self) -> frozenset[str]:
        raw = self.ADVISOR_BLOCKED_TIMEFRAMES_RAW.strip()
        if not raw:
            return frozenset()
        return frozenset(t.strip() for t in raw.split(",") if t.strip())

    @property
    def advisor_symbol_allowlist(self) -> frozenset[str] | None:
        raw = self.ADVISOR_SYMBOL_ALLOWLIST_RAW.strip()
        if not raw:
            return None
        return frozenset(s.strip().upper() for s in raw.split(",") if s.strip())

    @property
    def advisor_publish_priority_symbols(self) -> list[str]:
        raw = self.ADVISOR_PUBLISH_PRIORITY_SYMBOLS_RAW.strip()
        if not raw:
            return []
        return [s.strip().upper() for s in raw.split(",") if s.strip()]

    @property
    def advisor_sell_allowed_timeframes(self) -> frozenset[str]:
        raw = self.ADVISOR_SELL_ALLOWED_TIMEFRAMES_RAW.strip()
        if not raw:
            return frozenset()
        return frozenset(t.strip() for t in raw.split(",") if t.strip())

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
