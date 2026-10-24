import pandas as pd
from app.models import StrategySignal
from app.strategies.base import BaseStrategy


class OptionsVerticalSpreadStrategy(BaseStrategy):
    strategy_id = "options_vertical_spread"
    version = "1.0.0"
    description = "Defined-risk options vertical spread (Bull Call / Bear Put) with strict max-loss limits."
    category = "options"
    supported_regimes = ["trending_up", "trending_down"]

    def __init__(self, ema_period: int = 20, rsi_period: int = 14) -> None:
        self.ema_period = ema_period
        self.rsi_period = rsi_period
        self.parameters = {"ema_period": ema_period, "rsi_period": rsi_period}

    def generate(self, frame: pd.DataFrame, symbol: str, timeframe: str = "1d") -> StrategySignal:
        self.validate(frame)
        if len(frame) < self.ema_period + 5:
            return StrategySignal(
                strategy_id=self.strategy_id,
                strategy_version=self.version,
                symbol=symbol,
                timeframe=timeframe,
                timestamp=str(frame.timestamp.iloc[-1]),
                direction="flat",
                score=0.0,
                reason=f"Insufficient bars for warmup (need at least {self.ema_period + 5})",
            )

        df = frame.copy().reset_index(drop=True)
        close = df["close"]

        ema = close.ewm(span=self.ema_period, adjust=False).mean()
        delta = close.diff()
        gain = delta.clip(lower=0).rolling(window=self.rsi_period).mean()
        loss = (-delta.clip(upper=0)).rolling(window=self.rsi_period).mean()
        rs = gain / loss.replace(0, 1e-9)
        rsi = 100 - (100 / (1 + rs))

        curr_close = float(close.iloc[-1])
        curr_ema = float(ema.iloc[-1])
        curr_rsi = float(rsi.iloc[-1])

        # Step size estimation for ATM/OTM options (NSE Nifty style 50-step, BankNifty 100-step, stock 2.5%)
        strike_step = 50.0 if "NIFTY" in symbol.upper() else round(curr_close * 0.02, 1)
        atm_strike = round(curr_close / strike_step) * strike_step

        if curr_close > curr_ema and 50 < curr_rsi < 70:
            direction = "long"
            score = 0.82
            # Bull Call Spread: Buy ATM Call, Sell OTM Call (+1 strike)
            buy_strike = atm_strike
            sell_strike = atm_strike + strike_step
            stop = curr_close - strike_step
            target = curr_close + strike_step
            reason = f"Bull Call Spread: Buy {buy_strike:.0f} CE, Sell {sell_strike:.0f} CE (close > 20-EMA, RSI {curr_rsi:.1f})"
        elif curr_close < curr_ema and 30 < curr_rsi < 50:
            direction = "short"
            score = 0.82
            # Bear Put Spread: Buy ATM Put, Sell OTM Put (-1 strike)
            buy_strike = atm_strike
            sell_strike = atm_strike - strike_step
            stop = curr_close + strike_step
            target = curr_close - strike_step
            reason = f"Bear Put Spread: Buy {buy_strike:.0f} PE, Sell {sell_strike:.0f} PE (close < 20-EMA, RSI {curr_rsi:.1f})"
        else:
            direction = "flat"
            score = 0.0
            stop, target = None, None
            reason = "Market neutral; options vertical spread requires directional momentum"

        return StrategySignal(
            strategy_id=self.strategy_id,
            strategy_version=self.version,
            symbol=symbol,
            timeframe=timeframe,
            timestamp=str(frame.timestamp.iloc[-1]),
            direction=direction,
            score=score,
            reason=reason,
            suggested_stop=round(stop, 2) if stop else None,
            suggested_target=round(target, 2) if target else None,
            regime="options",
        )
