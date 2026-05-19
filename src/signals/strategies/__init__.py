"""Trading strategies package — all 9 strategies"""

from src.signals.strategies.rsi_strategy import RSIStrategy
from src.signals.strategies.macd_strategy import MACDStrategy
from src.signals.strategies.bollinger_squeeze_strategy import BollingerSqueezeStrategy
from src.signals.strategies.ema_trend_strategy import EMATrendStrategy
from src.signals.strategies.supertrend_strategy import SupertrendStrategy
from src.signals.strategies.ichimoku_strategy import IchimokuStrategy
from src.signals.strategies.volume_breakout_strategy import VolumeBreakoutStrategy
from src.signals.strategies.stochastic_rsi_strategy import StochasticRSIStrategy
from src.signals.strategies.confluence_strategy import ConfluenceStrategy

__all__ = [
    "RSIStrategy", "MACDStrategy", "BollingerSqueezeStrategy", "EMATrendStrategy",
    "SupertrendStrategy", "IchimokuStrategy", "VolumeBreakoutStrategy",
    "StochasticRSIStrategy", "ConfluenceStrategy",
]
