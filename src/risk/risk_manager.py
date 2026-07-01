"""
Risk Management - Adaptive Position Sizing and TP/SL Calculations

All TP/SL calculations are MARKET-ADAPTIVE:
- Uses ATR (Average True Range) as the primary volatility measure
- Adjusts multipliers based on market regime (trending/ranging/volatile)
- Uses Fibonacci levels and Pivot Points as TP targets where available
- Enforces minimum Risk:Reward ratio before any signal is accepted
"""

from typing import Tuple, Optional, Dict, List
import math
import logging

logger = logging.getLogger(__name__)


class RiskManager:
    """
    Adaptive risk management system.

    Primary method: calculate_adaptive_tp_sl()
    - ATR-based distances scaled to market regime
    - R:R enforcement (minimum 1.5:1)
    - Fibonacci and Pivot Point level snapping
    """

    def __init__(
        self,
        portfolio_size: float = 10000.0,
        max_position_percent: float = 5.0,
        min_position_percent: float = 1.0,
        max_open_positions: int = 5,
        risk_per_trade_percent: float = 1.0,
        min_risk_reward: float = 1.5,
    ):
        self.portfolio_size = portfolio_size
        self.max_position_percent = max_position_percent
        self.min_position_percent = min_position_percent
        self.max_open_positions = max_open_positions
        self.risk_per_trade_percent = risk_per_trade_percent
        self.min_risk_reward = min_risk_reward

    # ====================================================================
    # PRIMARY: Adaptive ATR-Based TP/SL (Use This Always)
    # ====================================================================

    def calculate_adaptive_tp_sl(
        self,
        entry_price: float,
        atr: float,
        direction: str = "long",
        regime: str = "trending",
        fib_levels: Optional[Dict] = None,
        pivot_levels: Optional[Dict] = None,
        smc_data: Optional[Dict] = None,
        high_probability: bool = False,
        *,
        sl_volatility_scale: float = 1.0,
        tp_volatility_scale: float = 1.0,
    ) -> Tuple[float, float, Dict]:
        """
        Calculate TP and SL adaptively based on ATR and market regime.

        The regime determines the ATR multipliers:
        - 'trending': ATR TP × 2.5, SL × 1.6 (room to run, TP hit more)
        - 'ranging':  ATR TP × 1.5, SL × 1.1 (tight targets)
        - 'volatile': ATR TP × 1.8, SL × 0.9 (quick in-out)

        After ATR levels are set, the method attempts to snap to the nearest
        Fibonacci or Pivot Point level for a more natural price target.

        Args:
            entry_price: Entry price of the trade
            atr: Current ATR value (must not be zero)
            direction: 'long' or 'short'
            regime: 'trending', 'ranging', or 'volatile'
            fib_levels: Optional dict from FibonacciLevels.calculate_from_ohlc()
            pivot_levels: Optional dict from PivotPoints.calculate_classic()
            smc_data: Optional dict from SMC.calculate_from_ohlc()
            high_probability: If true, allows a lower minimum Risk:Reward (e.g. 1.2)

        Returns:
            (take_profit_price, stop_loss_price, metadata_dict)
        """
        if atr <= 0:
            logger.warning("ATR is zero or negative, falling back to 2%/1% static TP/SL")
            return self._static_fallback(entry_price, direction)

        # Step 1: Get regime multipliers
        tp_mult, sl_mult = self._get_regime_multipliers(regime)
        sl_mult *= max(1.0, sl_volatility_scale)
        tp_mult *= max(0.75, min(1.25, tp_volatility_scale))
        logger.debug(f"Regime={regime}: TP×{tp_mult}, SL×{sl_mult}")

        # Step 2: Calculate raw ATR-based levels
        if direction == "long":
            raw_tp = entry_price + (atr * tp_mult)
            raw_sl = entry_price - (atr * sl_mult)
        else:
            raw_tp = entry_price - (atr * tp_mult)
            raw_sl = entry_price + (atr * sl_mult)

        # Step 3: Try to snap TP to a nearby Fibonacci extension level (front-run slightly)
        tp = self._snap_to_fib_tp(raw_tp, entry_price, fib_levels, direction)

        # Step 4: Try to snap SL to a nearby Pivot/Fibonacci/SMC support level (with ATR buffer)
        sl = self._snap_to_support_sl(raw_sl, entry_price, fib_levels, pivot_levels, smc_data, direction, atr)

        # Step 5: Enforce minimum R:R ratio
        tp, sl = self._enforce_min_rr(entry_price, tp, sl, direction, high_probability)

        metadata = {
            "regime": regime,
            "atr": round(atr, 6),
            "atr_tp_mult": tp_mult,
            "atr_sl_mult": sl_mult,
            "raw_atr_tp": round(raw_tp, 6),
            "raw_atr_sl": round(raw_sl, 6),
            "final_tp": round(tp, 6),
            "final_sl": round(sl, 6),
            "rr_ratio": round(abs(tp - entry_price) / max(abs(sl - entry_price), 1e-9), 3),
            "fib_snap": tp != raw_tp,
            "pivot_snap": sl != raw_sl,
        }
        logger.info(
            f"Adaptive TP/SL [{direction}|{regime}] "
            f"Entry={entry_price:.4f} TP={tp:.4f} SL={sl:.4f} "
            f"R:R={metadata['rr_ratio']:.2f}"
        )
        return round(tp, 6), round(sl, 6), metadata

    # ====================================================================
    # MULTI-TP SUPPORT (Planitt)
    # ====================================================================
    def calculate_multi_tp_sl(
        self,
        entry_price: float,
        atr: float,
        direction: str,
        regime: str = "trending",
        *,
        strong_trend_for_tp3: bool = False,
    ) -> Tuple[float, float, float, float, Dict]:
        """
        Calculate (tp1, tp2, tp3, sl) with RR enforcement.

        Implementation:
        - Use calculate_adaptive_tp_sl() to get tp2 (moderate) and sl while enforcing min R:R.
        - Derive tp1/tp3 around the tp2 reward distance.
        """

        tp2, sl, meta = self.calculate_adaptive_tp_sl(
            entry_price=entry_price,
            atr=atr,
            direction=direction,
            regime=regime,
        )

        risk = abs(entry_price - sl)
        reward_mid = abs(tp2 - entry_price)
        if risk <= 0:
            # Degenerate fallback; still keep strict ordering by using fixed deltas.
            risk = max(abs(entry_price) * 0.01, 1e-6)
            reward_mid = risk * self.min_risk_reward

        # Conservative TP1: slightly less than tp2
        reward_tp1 = reward_mid * 0.75
        # TP3: aggressive only in strong trends; otherwise keep modestly above tp2.
        reward_tp3 = reward_mid * (1.45 if strong_trend_for_tp3 else 1.15)

        if direction == "long":
            tp1 = entry_price + reward_tp1
            tp3 = entry_price + reward_tp3
        else:
            tp1 = entry_price - reward_tp1
            tp3 = entry_price - reward_tp3

        # Ensure strict ordering for consumers that require tp1 < tp2 < tp3 (long).
        # For short, strict ordering is tp3 < tp2 < tp1.
        if direction == "long":
            if not (tp1 < tp2 < tp3):
                tp1 = entry_price + reward_mid * 0.65
                tp3 = entry_price + reward_mid * (1.50 if strong_trend_for_tp3 else 1.20)
        else:
            if not (tp3 < tp2 < tp1):
                tp1 = entry_price - reward_mid * 0.65
                tp3 = entry_price - reward_mid * (1.50 if strong_trend_for_tp3 else 1.20)

        rr2 = abs(tp2 - entry_price) / max(abs(entry_price - sl), 1e-9)
        multi_meta = {
            **meta,
            "tp1": round(tp1, 6),
            "tp2": round(tp2, 6),
            "tp3": round(tp3, 6),
            "sl": round(sl, 6),
            "rr_tp2": round(rr2, 3),
            "strong_trend_for_tp3": strong_trend_for_tp3,
        }
        return round(tp1, 6), round(tp2, 6), round(tp3, 6), round(sl, 6), multi_meta

    def _get_regime_multipliers(self, regime: str) -> Tuple[float, float]:
        """Get (tp_mult, sl_mult) for the given market regime."""
        multipliers = {
            "trending":    (2.5, 1.6),
            "trending_up": (2.5, 1.6),
            "trending_down": (2.5, 1.6),
            "ranging":     (1.4, 1.35),
            "volatile":    (1.6, 1.2),
            "choppy":      (1.3, 1.25),
        }
        return multipliers.get(regime, (2.2, 1.3))  # default if unknown

    def _snap_to_fib_tp(
        self,
        raw_tp: float,
        entry: float,
        fib_levels: Optional[Dict],
        direction: str,
        snap_tolerance_pct: float = 3.0,
    ) -> float:
        """Snap TP to the nearest Fibonacci extension level if within tolerance, and front-run it."""
        if not fib_levels or "extensions" not in fib_levels:
            return raw_tp

        ext = fib_levels.get("extensions", {})
        candidates = []
        for label, price in ext.items():
            if direction == "long" and price > entry:
                distance_pct = abs(price - raw_tp) / raw_tp * 100
                if distance_pct <= snap_tolerance_pct:
                    candidates.append((distance_pct, price))
            elif direction == "short" and price < entry:
                distance_pct = abs(price - raw_tp) / raw_tp * 100
                if distance_pct <= snap_tolerance_pct:
                    candidates.append((distance_pct, price))

        if candidates:
            best = min(candidates, key=lambda x: x[0])
            front_run_tp = best[1] * 0.995 if direction == "long" else best[1] * 1.005
            logger.debug(f"Snapped and front-run TP from {raw_tp:.4f} to {front_run_tp:.4f} (Original Fib: {best[1]:.4f})")
            return front_run_tp
        return raw_tp

    def _snap_to_support_sl(
        self,
        raw_sl: float,
        entry: float,
        fib_levels: Optional[Dict],
        pivot_levels: Optional[Dict],
        smc_data: Optional[Dict],
        direction: str,
        atr: float,
        snap_tolerance_pct: float = 2.0,
    ) -> float:
        """Snap SL to the nearest Fibonacci, Pivot, or SMC support level and add an ATR buffer."""
        candidates = []
        
        # Buffer to avoid stop hunts right at the structure
        buffer = atr * 0.3

        # Fib retracement levels as SL candidates
        if fib_levels and "retracements" in fib_levels:
            for label, price in fib_levels["retracements"].items():
                buffered_price = price - buffer if direction == "long" else price + buffer
                if direction == "long" and buffered_price < entry:
                    dist = abs(buffered_price - raw_sl) / raw_sl * 100
                    if dist <= snap_tolerance_pct:
                        candidates.append((dist, buffered_price))
                elif direction == "short" and buffered_price > entry:
                    dist = abs(buffered_price - raw_sl) / raw_sl * 100
                    if dist <= snap_tolerance_pct:
                        candidates.append((dist, buffered_price))

        # Pivot support levels as SL candidates
        if pivot_levels:
            for label, price in pivot_levels.items():
                if label.startswith("S") and direction == "long":
                    buffered_price = price - buffer
                    if buffered_price < entry:
                        dist = abs(buffered_price - raw_sl) / raw_sl * 100
                        if dist <= snap_tolerance_pct:
                            candidates.append((dist, buffered_price))
                elif label.startswith("R") and direction == "short":
                    buffered_price = price + buffer
                    if buffered_price > entry:
                        dist = abs(buffered_price - raw_sl) / raw_sl * 100
                        if dist <= snap_tolerance_pct:
                            candidates.append((dist, buffered_price))

        # SMC Support Levels (Order Blocks & FVGs) as SL candidates
        if smc_data:
            # Hide SL beyond the OB/FVG with buffer
            for ob in smc_data.get("order_blocks", []):
                if ob["type"] == "bullish" and direction == "long":
                    buffered_price = ob["bottom"] - buffer
                    if buffered_price < entry:
                        dist = abs(buffered_price - raw_sl) / raw_sl * 100
                        if dist <= snap_tolerance_pct:
                            candidates.append((dist, buffered_price))
                elif ob["type"] == "bearish" and direction == "short":
                    buffered_price = ob["top"] + buffer
                    if buffered_price > entry:
                        dist = abs(buffered_price - raw_sl) / raw_sl * 100
                        if dist <= snap_tolerance_pct:
                            candidates.append((dist, buffered_price))
            
            for fvg in smc_data.get("fvgs", []):
                if fvg["type"] == "bullish" and direction == "long":
                    buffered_price = fvg["bottom"] - buffer
                    if buffered_price < entry:
                        dist = abs(buffered_price - raw_sl) / raw_sl * 100
                        if dist <= snap_tolerance_pct:
                            candidates.append((dist, buffered_price))
                elif fvg["type"] == "bearish" and direction == "short":
                    buffered_price = fvg["top"] + buffer
                    if buffered_price > entry:
                        dist = abs(buffered_price - raw_sl) / raw_sl * 100
                        if dist <= snap_tolerance_pct:
                            candidates.append((dist, buffered_price))

        if candidates:
            best = min(candidates, key=lambda x: x[0])
            logger.debug(f"Snapped and buffered SL from {raw_sl:.4f} to support level {best[1]:.4f}")
            return best[1]
        return raw_sl

    def _enforce_min_rr(
        self,
        entry: float,
        tp: float,
        sl: float,
        direction: str,
        high_probability: bool = False,
    ) -> Tuple[float, float]:
        """
        Enforce minimum risk:reward ratio by widening TP if needed.
        Never widen SL — that increases risk.
        """
        risk = abs(entry - sl)
        reward = abs(tp - entry)

        if risk == 0:
            return tp, sl

        current_rr = reward / risk
        required_rr = 1.2 if high_probability else self.min_risk_reward

        if current_rr < required_rr:
            # Widen TP to meet minimum R:R
            required_reward = risk * required_rr
            if direction == "long":
                tp = entry + required_reward
            else:
                tp = entry - required_reward
            logger.debug(
                f"R:R was {current_rr:.2f}, adjusted TP to meet minimum {required_rr:.1f}:1"
            )
        return tp, sl

    def _static_fallback(self, entry_price: float, direction: str) -> Tuple[float, float, Dict]:
        """Emergency fallback when ATR is unavailable."""
        if direction == "long":
            tp = entry_price * 1.05
            sl = entry_price * 0.98
        else:
            tp = entry_price * 0.95
            sl = entry_price * 1.02
        return tp, sl, {"regime": "unknown", "atr": 0, "fallback": True}

    # ====================================================================
    # POSITION SIZING — Risk-Based (Fixed Fractional)
    # ====================================================================

    def calculate_position_size(
        self,
        entry_price: float,
        stop_loss_price: float,
        risk_percent: Optional[float] = None,
    ) -> Tuple[float, float]:
        """
        Calculate position size using fixed-fractional risk model.

        Risk Amount = Portfolio × risk_percent
        Quantity = Risk Amount / (entry - stop_loss)

        Args:
            entry_price: Trade entry price
            stop_loss_price: Stop loss price
            risk_percent: % of portfolio to risk (None = default)

        Returns:
            (quantity, position_value_usd)
        """
        if risk_percent is None:
            risk_percent = self.risk_per_trade_percent

        risk_amount = self.portfolio_size * (risk_percent / 100)
        price_diff = abs(entry_price - stop_loss_price)

        if price_diff == 0:
            position_value = self.portfolio_size * (self.min_position_percent / 100)
        else:
            quantity = risk_amount / price_diff
            position_value = quantity * entry_price

        # Clamp to min/max position percentages
        min_pos = self.portfolio_size * (self.min_position_percent / 100)
        max_pos = self.portfolio_size * (self.max_position_percent / 100)
        position_value = max(min_pos, min(position_value, max_pos))
        quantity = position_value / entry_price

        return round(quantity, 8), round(position_value, 2)

    def calculate_position_size_percent(
        self, entry_price: float, stop_loss_price: float
    ) -> float:
        """Return position size as percentage of portfolio (0-100)."""
        _, pos_value = self.calculate_position_size(entry_price, stop_loss_price)
        return round((pos_value / self.portfolio_size) * 100, 4)

    # ====================================================================
    # LEGACY: Simpler methods kept for backward compatibility
    # ====================================================================

    def calculate_take_profit_price(
        self,
        entry_price: float,
        risk_reward_ratio: float = 2.0,
        stop_loss_price: Optional[float] = None,
    ) -> float:
        """Calculate TP from R:R ratio (legacy method)."""
        if stop_loss_price is None:
            raise ValueError("stop_loss_price is required")
        risk = abs(entry_price - stop_loss_price)
        reward = risk * risk_reward_ratio
        if stop_loss_price < entry_price:
            return entry_price + reward
        else:
            return entry_price - reward

    def calculate_tp_sl_atr_based(
        self,
        entry_price: float,
        atr: float,
        direction: str = "long",
        atr_multiplier_tp: float = 2.0,
        atr_multiplier_sl: float = 1.0,
    ) -> Tuple[float, float]:
        """ATR-based TP/SL (legacy method — prefer calculate_adaptive_tp_sl)."""
        if direction == "long":
            return entry_price + atr * atr_multiplier_tp, entry_price - atr * atr_multiplier_sl
        else:
            return entry_price - atr * atr_multiplier_tp, entry_price + atr * atr_multiplier_sl

    def calculate_tp_sl_percent_based(
        self,
        entry_price: float,
        tp_percent: float = 5.0,
        sl_percent: float = 2.0,
        direction: str = "long",
    ) -> Tuple[float, float]:
        """Percent-based TP/SL (legacy fallback — prefer adaptive method)."""
        tp_dist = entry_price * (tp_percent / 100)
        sl_dist = entry_price * (sl_percent / 100)
        if direction == "long":
            return entry_price + tp_dist, entry_price - sl_dist
        else:
            return entry_price - tp_dist, entry_price + sl_dist

    def validate_risk(self, risk_reward_ratio: float, min_ratio: Optional[float] = None) -> bool:
        """Validate if risk/reward ratio is acceptable."""
        min_r = min_ratio if min_ratio is not None else self.min_risk_reward
        return risk_reward_ratio >= min_r
