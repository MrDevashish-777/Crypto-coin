# Crypto Trading Bot - Trading Strategies & Risk Management

## Table of Contents
1. [Strategy Framework](#strategy-framework)
2. [Built-in Strategies](#built-in-strategies)
3. [Risk Management System](#risk-management-system)
4. [Position Sizing Models](#position-sizing-models)
5. [TP/SL Calculation Methods](#tpsl-calculation-methods)
6. [Portfolio Management](#portfolio-management)
7. [Backtesting Framework](#backtesting-framework)
8. [Strategy Optimization](#strategy-optimization)

---

## Strategy Framework

### Base Strategy Architecture

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional, Tuple, List
import pandas as pd
import numpy as np

@dataclass
class Signal:
    symbol: str
    signal_type: str  # "BUY" or "SELL"
    entry_price: float
    take_profit: float
    stop_loss: float
    position_size: float
    confidence: float
    entry_time: datetime
    indicators: dict
    reasoning: str

class BaseStrategy(ABC):
    """Abstract base class for all trading strategies"""
    
    def __init__(self, name: str, parameters: dict):
        self.name = name
        self.parameters = parameters
        self.signals = []
    
    @abstractmethod
    def validate(self, data: pd.DataFrame) -> bool:
        """Check if strategy conditions are met"""
        pass
    
    @abstractmethod
    def generate_signal(self, data: pd.DataFrame) -> Optional[Signal]:
        """Generate a trading signal"""
        pass
    
    def backtest(
        self,
        historical_data: pd.DataFrame,
        initial_balance: float = 10000,
        risk_per_trade: float = 2.0
    ) -> dict:
        """Backtest strategy on historical data"""
        
        results = {
            "total_trades": 0,
            "winning_trades": 0,
            "losing_trades": 0,
            "total_pnl": 0,
            "win_rate": 0,
            "trades": []
        }
        
        # Implementation of backtesting logic
        return results
    
    def get_parameters_description(self) -> dict:
        """Return strategy parameters and description"""
        return {
            "name": self.name,
            "parameters": self.parameters,
            "description": self.__doc__
        }
```

### Strategy Registry

```python
class StrategyRegistry:
    """Registry for all available strategies"""
    
    def __init__(self):
        self._strategies = {}
    
    def register(self, name: str, strategy_class):
        """Register a new strategy"""
        self._strategies[name] = strategy_class
    
    def get_strategy(self, name: str, parameters: dict):
        """Get instantiated strategy"""
        if name not in self._strategies:
            raise ValueError(f"Strategy '{name}' not found")
        return self._strategies[name](parameters)
    
    def list_strategies(self) -> List[str]:
        """List all available strategies"""
        return list(self._strategies.keys())

# Global registry
strategy_registry = StrategyRegistry()
```

---

## Built-in Strategies

### 1. RSI Strategy (Momentum-Based)

**Theory:** Relative Strength Index identifies overbought/oversold conditions

**Parameters:**
```python
RSI_PARAMS = {
    "period": 14,              # RSI period
    "buy_threshold": 30,        # RSI < 30 = oversold (BUY)
    "sell_threshold": 70,       # RSI > 70 = overbought (SELL)
    "trend_confirmation": True, # Require trend confirmation
    "trend_period": 20         # SMA period for trend
}
```

**Implementation:**
```python
class RSIStrategy(BaseStrategy):
    """
    Simple RSI-based mean reversion strategy.
    
    BUY Signal:
    - RSI < buy_threshold (default: 30)
    - Price above SMA (uptrend confirmation)
    
    SELL Signal:
    - RSI > sell_threshold (default: 70)
    - Price below SMA (downtrend confirmation)
    """
    
    def __init__(self, parameters: dict):
        super().__init__("RSI", parameters)
        self.period = parameters.get("period", 14)
        self.buy_threshold = parameters.get("buy_threshold", 30)
        self.sell_threshold = parameters.get("sell_threshold", 70)
        self.trend_period = parameters.get("trend_period", 20)
    
    def validate(self, data: pd.DataFrame) -> bool:
        """Check minimum data requirements"""
        return len(data) >= max(self.period, self.trend_period)
    
    def generate_signal(self, data: pd.DataFrame) -> Optional[Signal]:
        """Generate BUY/SELL signal based on RSI"""
        
        if not self.validate(data):
            return None
        
        # Calculate indicators
        rsi = self._calculate_rsi(data['close'].values)
        sma = data['close'].rolling(self.trend_period).mean()
        
        current_price = data['close'].iloc[-1]
        current_rsi = rsi.iloc[-1]
        trend_line = sma.iloc[-1]
        
        # BUY signal
        if current_rsi < self.buy_threshold and current_price > trend_line:
            confidence = 1 - (current_rsi / self.buy_threshold)
            return Signal(
                symbol=data.get('symbol'),
                signal_type="BUY",
                entry_price=current_price,
                confidence=confidence,
                indicators={"rsi": current_rsi, "sma": trend_line},
                reasoning=f"RSI {current_rsi:.1f} < {self.buy_threshold}, Price above trend"
            )
        
        # SELL signal
        if current_rsi > self.sell_threshold and current_price < trend_line:
            confidence = (current_rsi - self.sell_threshold) / (100 - self.sell_threshold)
            return Signal(
                symbol=data.get('symbol'),
                signal_type="SELL",
                entry_price=current_price,
                confidence=confidence,
                indicators={"rsi": current_rsi, "sma": trend_line},
                reasoning=f"RSI {current_rsi:.1f} > {self.sell_threshold}, Price below trend"
            )
        
        return None
    
    @staticmethod
    def _calculate_rsi(prices, period=14):
        """Calculate RSI"""
        deltas = np.diff(prices)
        up = deltas.copy()
        up[up < 0] = 0
        down = -deltas.copy()
        down[down < 0] = 0
        
        up_avg = pd.Series(up).rolling(period).mean()
        down_avg = pd.Series(down).rolling(period).mean()
        
        rs = up_avg / down_avg
        return 100 - (100 / (1 + rs))
```

### 2. MACD Strategy (Trend-Following)

**Theory:** MACD identifies trend direction and momentum

**Parameters:**
```python
MACD_PARAMS = {
    "fast_period": 12,            # Fast EMA
    "slow_period": 26,            # Slow EMA
    "signal_period": 9,           # Signal line EMA
    "histogram_threshold": 0,     # Minimum histogram value
    "momentum_confirmation": True # Require increasing momentum
}
```

**Implementation:**
```python
class MACDStrategy(BaseStrategy):
    """
    MACD crossover strategy with momentum confirmation.
    
    BUY Signal:
    - MACD crosses above signal line
    - Histogram is positive and increasing
    - Momentum > threshold
    
    SELL Signal:
    - MACD crosses below signal line
    - Histogram is negative and decreasing
    """
    
    def __init__(self, parameters: dict):
        super().__init__("MACD", parameters)
        self.fast_period = parameters.get("fast_period", 12)
        self.slow_period = parameters.get("slow_period", 26)
        self.signal_period = parameters.get("signal_period", 9)
        self.histogram_threshold = parameters.get("histogram_threshold", 0)
    
    def validate(self, data: pd.DataFrame) -> bool:
        return len(data) >= self.slow_period + self.signal_period
    
    def generate_signal(self, data: pd.DataFrame) -> Optional[Signal]:
        if not self.validate(data):
            return None
        
        close_prices = data['close'].values
        
        # Calculate MACD
        macd, signal_line, histogram = self._calculate_macd(
            close_prices,
            self.fast_period,
            self.slow_period,
            self.signal_period
        )
        
        current_macd = macd[-1]
        current_signal = signal_line[-1]
        current_histogram = histogram[-1]
        prev_histogram = histogram[-2]
        
        # BUY signal: MACD crosses above signal
        if (macd[-2] <= signal_line[-2] and current_macd > current_signal and
            current_histogram > self.histogram_threshold and
            current_histogram > prev_histogram):
            
            confidence = min(1.0, abs(current_macd - current_signal) / current_macd)
            return Signal(
                symbol=data.get('symbol'),
                signal_type="BUY",
                entry_price=data['close'].iloc[-1],
                confidence=confidence,
                indicators={"macd": current_macd, "signal": current_signal, "histogram": current_histogram},
                reasoning="MACD crossed above signal line with positive momentum"
            )
        
        # SELL signal: MACD crosses below signal
        if (macd[-2] >= signal_line[-2] and current_macd < current_signal and
            current_histogram < self.histogram_threshold and
            current_histogram < prev_histogram):
            
            confidence = min(1.0, abs(current_signal - current_macd) / abs(current_signal))
            return Signal(
                symbol=data.get('symbol'),
                signal_type="SELL",
                entry_price=data['close'].iloc[-1],
                confidence=confidence,
                indicators={"macd": current_macd, "signal": current_signal, "histogram": current_histogram},
                reasoning="MACD crossed below signal line with negative momentum"
            )
        
        return None
    
    @staticmethod
    def _calculate_macd(prices, fast, slow, signal):
        """Calculate MACD"""
        ema_fast = pd.Series(prices).ewm(span=fast).mean()
        ema_slow = pd.Series(prices).ewm(span=slow).mean()
        
        macd_line = ema_fast - ema_slow
        signal_line = macd_line.ewm(span=signal).mean()
        histogram = macd_line - signal_line
        
        return macd_line.values, signal_line.values, histogram.values
```

### 3. Bollinger Bands Strategy (Mean Reversion)

**Theory:** Price bounces off Bollinger Bands when in mean reversion phase

**Parameters:**
```python
BBANDS_PARAMS = {
    "period": 20,                    # SMA period
    "std_dev": 2,                   # Standard deviation
    "rsi_confirmation": True,       # Use RSI for entry confirmation
    "rsi_period": 14,
    "rsi_lower": 30,               # RSI lower bound for buy
    "rsi_upper": 70                # RSI upper bound for sell
}
```

**Implementation:**
```python
class BollingerBandsStrategy(BaseStrategy):
    """
    Mean reversion strategy using Bollinger Bands with RSI confirmation.
    
    BUY Signal:
    - Price touches/breaks below lower band
    - RSI < 30 (oversold confirmation)
    - Momentum is low (histogram near zero)
    
    SELL Signal:
    - Price touches/breaks above upper band
    - RSI > 70 (overbought confirmation)
    - Divergence detected
    """
    
    def __init__(self, parameters: dict):
        super().__init__("Bollinger Bands", parameters)
        self.period = parameters.get("period", 20)
        self.std_dev = parameters.get("std_dev", 2)
        self.rsi_period = parameters.get("rsi_period", 14)
        self.rsi_lower = parameters.get("rsi_lower", 30)
        self.rsi_upper = parameters.get("rsi_upper", 70)
    
    def validate(self, data: pd.DataFrame) -> bool:
        return len(data) >= max(self.period, self.rsi_period) + 5
    
    def generate_signal(self, data: pd.DataFrame) -> Optional[Signal]:
        if not self.validate(data):
            return None
        
        # Calculate Bollinger Bands
        sma = data['close'].rolling(self.period).mean()
        std = data['close'].rolling(self.period).std()
        upper_band = sma + (self.std_dev * std)
        lower_band = sma - (self.std_dev * std)
        
        # Calculate RSI for confirmation
        rsi = self._calculate_rsi(data['close'].values[-self.rsi_period-5:])
        
        current_price = data['close'].iloc[-1]
        current_upper = upper_band.iloc[-1]
        current_lower = lower_band.iloc[-1]
        current_rsi = rsi.iloc[-1]
        band_width = current_upper - current_lower
        
        # Calculate position within bands (0-1, where 0 is lower, 1 is upper)
        position = (current_price - current_lower) / band_width if band_width > 0 else 0.5
        
        # BUY signal: Price at lower band + RSI oversold
        if position < 0.2 and current_rsi < self.rsi_lower:
            confidence = (self.rsi_lower - current_rsi) / self.rsi_lower
            return Signal(
                symbol=data.get('symbol'),
                signal_type="BUY",
                entry_price=current_price,
                confidence=confidence,
                indicators={
                    "bb_upper": current_upper,
                    "bb_middle": sma.iloc[-1],
                    "bb_lower": current_lower,
                    "rsi": current_rsi,
                    "position": position
                },
                reasoning=f"Price near lower band (pos: {position:.2f}), RSI oversold ({current_rsi:.1f})"
            )
        
        # SELL signal: Price at upper band + RSI overbought
        if position > 0.8 and current_rsi > self.rsi_upper:
            confidence = (current_rsi - self.rsi_upper) / (100 - self.rsi_upper)
            return Signal(
                symbol=data.get('symbol'),
                signal_type="SELL",
                entry_price=current_price,
                confidence=confidence,
                indicators={
                    "bb_upper": current_upper,
                    "bb_middle": sma.iloc[-1],
                    "bb_lower": current_lower,
                    "rsi": current_rsi,
                    "position": position
                },
                reasoning=f"Price near upper band (pos: {position:.2f}), RSI overbought ({current_rsi:.1f})"
            )
        
        return None
    
    @staticmethod
    def _calculate_rsi(prices, period=14):
        deltas = np.diff(prices)
        up = deltas.copy()
        up[up < 0] = 0
        down = -deltas.copy()
        down[down < 0] = 0
        
        up_avg = pd.Series(up).rolling(period).mean()
        down_avg = pd.Series(down).rolling(period).mean()
        
        rs = up_avg / down_avg
        return 100 - (100 / (1 + rs))
```

### 4. Combined Multi-Indicator Strategy

**The Best Approach: Requiring Multiple Confirmations**

```python
class CombinedStrategy(BaseStrategy):
    """
    Advanced strategy combining RSI, MACD, and Bollinger Bands.
    
    Requires multiple indicators to align for higher confidence signals.
    """
    
    def __init__(self, parameters: dict):
        super().__init__("Combined", parameters)
        
        # Initialize sub-strategies
        self.rsi_strategy = RSIStrategy(parameters.get("rsi", {}))
        self.macd_strategy = MACDStrategy(parameters.get("macd", {}))
        self.bb_strategy = BollingerBandsStrategy(parameters.get("bbands", {}))
        
        self.min_confirmations = parameters.get("min_confirmations", 2)  # Require 2+ indicators
    
    def generate_signal(self, data: pd.DataFrame) -> Optional[Signal]:
        """Generate signal only when multiple indicators align"""
        
        signals = []
        confidence_scores = []
        
        # Get signals from each strategy
        rsi_signal = self.rsi_strategy.generate_signal(data)
        macd_signal = self.macd_strategy.generate_signal(data)
        bb_signal = self.bb_strategy.generate_signal(data)
        
        # Collect signals
        for signal, weight in [(rsi_signal, 0.3), (macd_signal, 0.4), (bb_signal, 0.3)]:
            if signal is not None:
                signals.append(signal)
                confidence_scores.append(signal.confidence * weight)
        
        # Require minimum number of confirmations
        if len(signals) < self.min_confirmations:
            return None
        
        # All signals must agree on direction
        signal_types = [s.signal_type for s in signals]
        if not all(t == signal_types[0] for t in signal_types):
            return None
        
        # Generate combined signal
        combined_confidence = sum(confidence_scores) / len(confidence_scores)
        combined_indicators = {}
        
        for signal in signals:
            combined_indicators.update(signal.indicators)
        
        return Signal(
            symbol=data.get('symbol'),
            signal_type=signals[0].signal_type,
            entry_price=data['close'].iloc[-1],
            confidence=min(1.0, combined_confidence),
            indicators=combined_indicators,
            reasoning=f"{len(signals)} indicators aligned: {', '.join([s.name for s in signals])}"
        )
```

---

## Risk Management System

### Core Risk Management Logic

```python
class RiskManager:
    """Comprehensive risk management system"""
    
    def __init__(
        self,
        account_balance: float,
        risk_per_trade: float = 2.0,  # % of account
        daily_loss_limit: float = 5.0,  # % of account
        max_concurrent_positions: int = 5,
        max_correlation: float = 0.7,
        max_leverage: float = 1.0  # 1.0 = no leverage
    ):
        self.account_balance = account_balance
        self.risk_per_trade = risk_per_trade
        self.daily_loss_limit = daily_loss_limit
        self.max_concurrent_positions = max_concurrent_positions
        self.max_correlation = max_correlation
        self.max_leverage = max_leverage
        
        self.daily_loss = 0
        self.open_positions = []
    
    def validate_signal(self, signal: Signal) -> Tuple[bool, str]:
        """
        Validate signal against risk criteria
        
        Returns: (is_valid, reason_if_invalid)
        """
        
        # Check daily loss limit
        if self.daily_loss < -self.account_balance * (self.daily_loss_limit / 100):
            return False, f"Daily loss limit exceeded: ${abs(self.daily_loss):.2f}"
        
        # Check concurrent positions
        if len(self.open_positions) >= self.max_concurrent_positions:
            return False, f"Max concurrent positions ({self.max_concurrent_positions}) reached"
        
        # Check RR ratio
        rr_ratio = (signal.take_profit - signal.entry_price) / abs(
            signal.entry_price - signal.stop_loss
        )
        if rr_ratio < 1.5:
            return False, f"Risk/Reward ratio too low: {rr_ratio:.2f}"
        
        # Check correlation with open trades
        for open_signal in self.open_positions:
            if signal.signal_type == open_signal.signal_type:  # Same direction
                correlation = self._calculate_correlation(signal.symbol, open_signal.symbol)
                if correlation > self.max_correlation:
                    return False, f"High correlation ({correlation:.2f}) with {open_signal.symbol}"
        
        # Check leverage
        position_size = signal.position_size
        leverage = (position_size * signal.entry_price) / self.account_balance
        if leverage > self.max_leverage:
            return False, f"Leverage {leverage:.2f}x exceeds max {self.max_leverage}x"
        
        return True, ""
    
    def _calculate_correlation(self, symbol1: str, symbol2: str) -> float:
        """Calculate correlation between two assets"""
        # Implementation would fetch historical data and calculate correlation
        # For now, return placeholder
        return 0.5
```

---

## Position Sizing Models

### 1. Fixed Fractional Model

```python
class FixedFractionalPositionSizer:
    """
    Size positions as a fixed percentage of account balance.
    Most conservative approach.
    """
    
    def __init__(self, fraction: float = 0.05):  # 5% per trade
        self.fraction = fraction
    
    def calculate(self, account_balance: float, entry: float, sl: float) -> float:
        """
        Calculate position size
        
        Position Size = (Account * Fraction) / (Entry - SL)
        """
        risk_per_unit = abs(entry - sl)
        position_size = (account_balance * self.fraction) / risk_per_unit
        return position_size
```

**Pros:** Simple, predictable, conservative  
**Cons:** Doesn't adapt to volatility, may leave money on table

### 2. Risk-Based Model (Recommended)

```python
class RiskBasedPositionSizer:
    """
    Size positions based on acceptable dollar risk per trade.
    Adapts to volatility automatically.
    """
    
    def __init__(self, risk_percent: float = 2.0):  # 2% of account at risk
        self.risk_percent = risk_percent
    
    def calculate(
        self,
        account_balance: float,
        entry_price: float,
        stop_loss: float
    ) -> float:
        """
        Calculate position size based on risk
        
        Formula:
        Max Risk = Account Balance * Risk %
        Position Size = Max Risk / (Entry - SL)
        """
        max_risk = account_balance * (self.risk_percent / 100)
        risk_per_unit = abs(entry_price - stop_loss)
        
        if risk_per_unit == 0:
            return 0
        
        position_size = max_risk / risk_per_unit
        return position_size
    
    def example(self):
        """
        Example:
        - Account: $10,000
        - Risk per trade: 2% = $200
        - Entry: $100
        - SL: $98
        - Risk per unit: $2
        - Position size: $200 / $2 = 100 units = $10,000 notional
        """
        pass
```

### 3. Kelly Criterion Model

```python
class KellyCriterionPositionSizer:
    """
    Uses Kelly Criterion for optimal position sizing.
    Requires historical win rate and RR ratio data.
    """
    
    def calculate(
        self,
        account_balance: float,
        win_rate: float,      # 0.6 = 60%
        avg_win_rr: float,    # Average risk/reward ratio
        avg_loss_rr: float
    ) -> float:
        """
        Kelly Criterion: f* = (bp - q) / b
        where:
        f* = fraction of capital to risk
        b = ratio of win amount to loss amount
        p = probability of win
        q = probability of loss (1-p)
        """
        
        p = win_rate
        q = 1 - win_rate
        b = avg_win_rr / avg_loss_rr if avg_loss_rr != 0 else 0
        
        if (b - 1) <= 0:
            return 0
        
        kelly_fraction = (b * p - q) / b
        
        # Conservative: use half Kelly for lower volatility
        conservative_fraction = kelly_fraction / 2
        
        return account_balance * conservative_fraction
```

**Formula Explanation:**
- Kelly Criterion tells you the optimal fraction of capital to allocate
- Full Kelly can be aggressive, so traders typically use "half Kelly"
- Requires accurate historical data to work well

---

## TP/SL Calculation Methods

### 1. ATR-Based (Dynamic, Market-Adaptive)

```python
class ATRBasedTPSL:
    """
    Use Average True Range for dynamic TP/SL levels.
    Adapts to current market volatility.
    """
    
    def calculate(
        self,
        entry_price: float,
        atr: float,
        tp_multiplier: float = 2.0,
        sl_multiplier: float = 1.5,
        direction: Literal["BUY", "SELL"] = "BUY"
    ) -> Tuple[float, float]:
        """
        Calculate TP and SL based on ATR
        
        For BUY:
        - TP = Entry + (ATR * TP Multiplier)
        - SL = Entry - (ATR * SL Multiplier)
        
        For SELL:
        - TP = Entry - (ATR * TP Multiplier)
        - SL = Entry + (ATR * SL Multiplier)
        """
        
        if direction == "BUY":
            tp = entry_price + (atr * tp_multiplier)
            sl = entry_price - (atr * sl_multiplier)
        else:  # SELL
            tp = entry_price - (atr * tp_multiplier)
            sl = entry_price + (atr * sl_multiplier)
        
        return tp, sl
    
    def example(self):
        """
        High volatility (ATR = 500):
        - Entry: $1000
        - TP = 1000 + (500 * 2) = $2000 (100% profit)
        - SL = 1000 - (500 * 1.5) = $250 (25% loss)
        - RR ratio = 4:1
        
        Low volatility (ATR = 100):
        - Entry: $1000
        - TP = 1000 + (100 * 2) = $1200 (20% profit)
        - SL = 1000 - (100 * 1.5) = $850 (15% loss)
        - RR ratio = 1.33:1
        """
        pass
```

### 2. Percentage-Based (Simple, Consistent)

```python
class PercentageBasedTPSL:
    """
    Fixed percentage profit/loss targets.
    Simple and consistent, doesn't adapt to volatility.
    """
    
    def calculate(
        self,
        entry_price: float,
        tp_percent: float = 2.0,
        sl_percent: float = 1.0,
        direction: Literal["BUY", "SELL"] = "BUY"
    ) -> Tuple[float, float]:
        """
        Calculate TP and SL as percentage moves
        
        Example:
        - Entry: $100
        - TP: 2% → $102
        - SL: 1% → $99
        - RR ratio: 2:1
        """
        
        tp_amount = entry_price * (tp_percent / 100)
        sl_amount = entry_price * (sl_percent / 100)
        
        if direction == "BUY":
            tp = entry_price + tp_amount
            sl = entry_price - sl_amount
        else:  # SELL
            tp = entry_price - tp_amount
            sl = entry_price + sl_amount
        
        return tp, sl
```

### 3. Support/Resistance-Based (Technical)

```python
class SupportResistanceTPSL:
    """
    Set TP/SL based on identified support/resistance levels.
    Works well in range-bound markets.
    """
    
    def calculate(
        self,
        entry_price: float,
        support: float,
        resistance: float,
        direction: Literal["BUY", "SELL"] = "BUY"
    ) -> Tuple[float, float]:
        """
        For BUY:
        - TP = resistance level (or above)
        - SL = support level (or below)
        
        For SELL:
        - TP = support level (or below)
        - SL = resistance level (or above)
        """
        
        if direction == "BUY":
            tp = resistance
            sl = support
        else:  # SELL
            tp = support
            sl = resistance
        
        # Ensure SL is below entry for BUY, above for SELL
        if direction == "BUY":
            if sl >= entry_price:
                sl = entry_price * (1 - 0.01)  # 1% buffer
        else:
            if sl <= entry_price:
                sl = entry_price * (1 + 0.01)
        
        return tp, sl
    
    def example(self):
        """
        Scenario: Support at $95, Entry at $100, Resistance at $110
        
        BUY Setup:
        - TP = $110 (resistance)
        - SL = $95 (support)
        - RR = (110-100) / (100-95) = 2:1
        """
        pass
```

---

## Portfolio Management

### Multi-Position Management

```python
class PortfolioManager:
    """Manage multiple concurrent positions"""
    
    def __init__(self):
        self.positions = {}  # symbol -> position_info
    
    def add_position(self, symbol: str, signal: Signal):
        """Add new position"""
        self.positions[symbol] = {
            "symbol": symbol,
            "entry_price": signal.entry_price,
            "tp": signal.take_profit,
            "sl": signal.stop_loss,
            "size": signal.position_size,
            "direction": signal.signal_type,
            "entry_time": datetime.now(),
            "pnl": 0,
            "pnl_percent": 0
        }
    
    def update_position(self, symbol: str, current_price: float):
        """Update position P&L"""
        if symbol not in self.positions:
            return
        
        pos = self.positions[symbol]
        entry = pos['entry_price']
        size = pos['size']
        direction = pos['direction']
        
        if direction == "BUY":
            pnl = size * (current_price - entry)
            pnl_percent = ((current_price - entry) / entry) * 100
        else:  # SELL
            pnl = size * (entry - current_price)
            pnl_percent = ((entry - current_price) / entry) * 100
        
        pos['pnl'] = pnl
        pos['pnl_percent'] = pnl_percent
    
    def check_exits(self, symbol: str, current_price: float) -> Optional[str]:
        """Check if position should exit"""
        if symbol not in self.positions:
            return None
        
        pos = self.positions[symbol]
        
        # Check TP hit
        if pos['direction'] == "BUY" and current_price >= pos['tp']:
            return "TP"
        elif pos['direction'] == "SELL" and current_price <= pos['tp']:
            return "TP"
        
        # Check SL hit
        if pos['direction'] == "BUY" and current_price <= pos['sl']:
            return "SL"
        elif pos['direction'] == "SELL" and current_price >= pos['sl']:
            return "SL"
        
        return None
    
    def get_portfolio_metrics(self) -> dict:
        """Get portfolio-level metrics"""
        total_pnl = sum(pos['pnl'] for pos in self.positions.values())
        winning_positions = len([p for p in self.positions.values() if p['pnl'] > 0])
        losing_positions = len([p for p in self.positions.values() if p['pnl'] < 0])
        
        return {
            "total_positions": len(self.positions),
            "winning_positions": winning_positions,
            "losing_positions": losing_positions,
            "total_pnl": total_pnl,
            "win_rate": winning_positions / len(self.positions) if self.positions else 0
        }
```

---

## Backtesting Framework

### Backtest Engine

```python
class BacktestEngine:
    """Full backtesting simulation"""
    
    def __init__(
        self,
        strategy,
        initial_balance: float = 10000,
        risk_per_trade: float = 2.0
    ):
        self.strategy = strategy
        self.initial_balance = initial_balance
        self.current_balance = initial_balance
        self.risk_per_trade = risk_per_trade
        
        self.trades = []
        self.balance_history = [initial_balance]
    
    def backtest(self, historical_data: pd.DataFrame) -> dict:
        """Run backtest on historical data"""
        
        portfolio = PortfolioManager()
        
        for i in range(len(historical_data)):
            current_data = historical_data.iloc[:i+1]
            current_price = historical_data.iloc[i]['close']
            
            # Check exits for existing positions
            for symbol in list(portfolio.positions.keys()):
                exit_type = portfolio.check_exits(symbol, current_price)
                if exit_type:
                    self._close_position(portfolio, symbol, current_price, exit_type)
            
            # Generate new signal
            signal = self.strategy.generate_signal(current_data)
            if signal:
                # Calculate position size
                risk_amount = self.current_balance * (self.risk_per_trade / 100)
                position_size = risk_amount / abs(signal.entry_price - signal.stop_loss)
                
                signal.position_size = position_size
                portfolio.add_position(signal.symbol, signal)
                self.trades.append({
                    "entry_price": signal.entry_price,
                    "entry_time": current_data.index[-1],
                    "exit_price": None,
                    "exit_time": None,
                    "exit_type": None,
                    "pnl": None
                })
            
            # Update positions
            for symbol in portfolio.positions:
                portfolio.update_position(symbol, current_price)
            
            # Update balance
            total_pnl = sum(pos['pnl'] for pos in portfolio.positions.values())
            self.balance_history.append(self.current_balance + total_pnl)
        
        return self._generate_report()
    
    def _close_position(self, portfolio, symbol, exit_price, exit_type):
        """Close position and record trade"""
        pos = portfolio.positions[symbol]
        
        # Calculate realized P&L
        if pos['direction'] == "BUY":
            pnl = pos['size'] * (exit_price - pos['entry_price'])
        else:
            pnl = pos['size'] * (pos['entry_price'] - exit_price)
        
        self.current_balance += pnl
        
        # Remove position
        del portfolio.positions[symbol]
    
    def _generate_report(self) -> dict:
        """Generate backtest report"""
        balance_array = np.array(self.balance_history)
        returns = np.diff(balance_array) / balance_array[:-1]
        
        total_profit = self.current_balance - self.initial_balance
        total_return_pct = (total_profit / self.initial_balance) * 100
        
        winning_trades = [t for t in self.trades if t['pnl'] and t['pnl'] > 0]
        losing_trades = [t for t in self.trades if t['pnl'] and t['pnl'] <= 0]
        
        return {
            "initial_balance": self.initial_balance,
            "final_balance": self.current_balance,
            "total_profit": total_profit,
            "total_return_pct": total_return_pct,
            "total_trades": len(self.trades),
            "winning_trades": len(winning_trades),
            "losing_trades": len(losing_trades),
            "win_rate": len(winning_trades) / len(self.trades) if self.trades else 0,
            "avg_win": np.mean([t['pnl'] for t in winning_trades]) if winning_trades else 0,
            "avg_loss": np.mean([t['pnl'] for t in losing_trades]) if losing_trades else 0,
            "max_drawdown": self._calculate_max_drawdown(balance_array),
            "sharpe_ratio": self._calculate_sharpe_ratio(returns),
            "profit_factor": sum(t['pnl'] for t in winning_trades) / abs(sum(t['pnl'] for t in losing_trades)) if losing_trades else 0
        }
    
    @staticmethod
    def _calculate_max_drawdown(balance_array) -> float:
        """Calculate maximum drawdown percentage"""
        peak = balance_array[0]
        max_dd = 0
        
        for balance in balance_array:
            if balance > peak:
                peak = balance
            dd = (peak - balance) / peak
            max_dd = max(max_dd, dd)
        
        return max_dd * 100
    
    @staticmethod
    def _calculate_sharpe_ratio(returns, risk_free_rate=0.02) -> float:
        """Calculate Sharpe Ratio"""
        excess_returns = returns - (risk_free_rate / 252)  # Assuming daily returns
        return np.mean(excess_returns) / np.std(excess_returns) * np.sqrt(252) if len(returns) > 0 else 0
```

---

## Strategy Optimization

### Parameter Optimization

```python
class StrategyOptimizer:
    """Optimize strategy parameters using grid search or Bayesian optimization"""
    
    @staticmethod
    def grid_search(
        strategy_class,
        param_grid: dict,
        historical_data: pd.DataFrame,
        metric: str = "sharpe_ratio"
    ) -> dict:
        """
        Grid search over parameter combinations
        
        Example param_grid:
        {
            "period": [10, 14, 20],
            "buy_threshold": [20, 30, 40],
            "sell_threshold": [60, 70, 80]
        }
        """
        
        from itertools import product
        
        best_params = None
        best_score = -np.inf
        results = []
        
        # Generate all parameter combinations
        keys, values = zip(*param_grid.items())
        for combination in product(*values):
            params = dict(zip(keys, combination))
            
            # Create strategy with these params
            strategy = strategy_class(params)
            
            # Backtest
            backtest = BacktestEngine(strategy)
            report = backtest.backtest(historical_data)
            
            # Get metric
            score = report.get(metric, 0)
            
            results.append({
                "params": params,
                "score": score,
                "report": report
            })
            
            if score > best_score:
                best_score = score
                best_params = params
        
        return {
            "best_params": best_params,
            "best_score": best_score,
            "all_results": results
        }
```

---

## Summary Table: Strategy Characteristics

| Strategy | Best For | Pros | Cons |
|----------|----------|------|------|
| **RSI** | Mean Reversion | Simple, good for consolidations | Whipsaws in trends |
| **MACD** | Trend Following | Catches trends early | Lags in choppy markets |
| **Bollinger Bands** | Mean Reversion | Good S/R levels | Reduces to moving average |
| **Combined** | All Markets | Robust, fewer false signals | More complex |

## Key Metrics to Track

```python
TRADING_METRICS = {
    "win_rate": "% of winning trades",
    "profit_factor": "Sum wins / Sum losses",
    "sharpe_ratio": "Risk-adjusted returns",
    "max_drawdown": "Worst peak-to-trough loss",
    "recovery_factor": "Total profit / Max drawdown",
    "rr_ratio": "Average reward / Average risk",
    "avg_trade_duration": "Days in average trade",
    "best_trade": "Largest winning trade",
    "worst_trade": "Largest losing trade"
}

MINIMUM_ACCEPTABLE_METRICS = {
    "win_rate": 0.50,          # 50% wins minimum
    "profit_factor": 1.5,      # Profit/losses ratio
    "sharpe_ratio": 1.0,       # Risk-adjusted return
    "max_drawdown": -20.0,     # Max percentage loss
    "rr_ratio": 1.5            # Reward/Risk ratio
}
```

This comprehensive guide provides the foundation for building professional trading strategies with proper risk management.
