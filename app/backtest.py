import math
from dataclasses import asdict, dataclass, field
from typing import Any
import numpy as np
import pandas as pd
from app.strategies.base import BaseStrategy


@dataclass
class BacktestResult:
    trades: int
    wins: int
    losses: int
    win_rate: float
    gross_pnl: float
    estimated_costs: float
    net_pnl: float
    profit_factor: float | None

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class DetailedTrade:
    trade_id: int
    symbol: str
    direction: str
    entry_time: str
    entry_price: float
    exit_time: str
    exit_price: float
    quantity: int
    gross_pnl: float
    fees: float
    net_pnl: float
    return_pct: float
    exit_reason: str

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ComprehensiveBacktestMetrics:
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate_pct: float
    gross_pnl: float
    total_fees: float
    net_pnl: float
    profit_factor: float | None
    expectancy: float
    average_trade_pnl: float
    average_win: float
    average_loss: float
    win_loss_ratio: float
    max_drawdown_amount: float
    max_drawdown_pct: float
    sharpe_ratio: float
    sortino_ratio: float
    cagr_pct: float
    equity_curve: list[dict[str, Any]]
    monthly_returns: dict[str, float]
    trades_log: list[DetailedTrade]

    def to_dict(self) -> dict:
        d = asdict(self)
        d["trades_log"] = [t.to_dict() if hasattr(t, "to_dict") else t for t in self.trades_log]
        return d


def calculate_indian_market_charges(
    turnover_buy: float,
    turnover_sell: float,
    is_delivery: bool = False,
    brokerage_rate: float = 20.0,
) -> float:
    """Calculate realistic Indian market statutory taxes & charges.
    
    Includes: Brokerage, STT, Exchange transaction charges, SEBI turnover fees, GST (18%), Stamp duty.
    """
    total_turnover = turnover_buy + turnover_sell
    if total_turnover <= 0:
        return 0.0

    brokerage = min(brokerage_rate * 2, total_turnover * 0.0003)

    # STT: 0.1% on delivery both ways, or 0.025% on intraday equity sell
    stt = (turnover_sell * 0.001 if is_delivery else turnover_sell * 0.00025)

    # Exchange transaction fee: NSE ~0.00345%
    exchange_charges = total_turnover * 0.0000345

    # SEBI turnover fee: ₹10 per crore (0.0001%)
    sebi_charges = total_turnover * 0.000001

    # GST: 18% on (brokerage + exchange charges + sebi charges)
    gst = (brokerage + exchange_charges + sebi_charges) * 0.18

    # Stamp duty: 0.015% on buy side (delivery), 0.003% on intraday buy
    stamp_duty = turnover_buy * (0.00015 if is_delivery else 0.00003)

    return round(brokerage + stt + exchange_charges + sebi_charges + gst + stamp_duty, 2)


def run_backtest(
    frame: pd.DataFrame,
    strategy: BaseStrategy,
    symbol: str = "TEST",
    timeframe: str = "1d",
    cost_bps_per_side: float = 5.0,
) -> BacktestResult:
    """Long/short single-position research backtest.
    
    Preserved for exact backwards compatibility.
    """
    strategy.validate(frame)
    data = frame.sort_values("timestamp").reset_index(drop=True).copy()
    position = 0
    entry = 0.0
    pnl_values: list[float] = []
    cost_values: list[float] = []
    for i in range(30, len(data) - 1):
        history = data.iloc[: i + 1]
        signal = strategy.generate(history, symbol, timeframe)
        wanted = 1 if signal.direction == "long" else -1 if signal.direction == "short" else 0
        next_open = float(data.open.iloc[i + 1])
        if wanted != position:
            if position != 0:
                pnl = position * (next_open - entry)
                pnl_values.append(pnl)
                cost_values.append((abs(entry) + abs(next_open)) * cost_bps_per_side / 10_000)
            position = wanted
            entry = next_open if position else 0.0
    if position != 0 and len(data):
        final_close = float(data.close.iloc[-1])
        pnl_values.append(position * (final_close - entry))
        cost_values.append((abs(entry) + abs(final_close)) * cost_bps_per_side / 10_000)
    wins = sum(p > 0 for p in pnl_values)
    losses = sum(p <= 0 for p in pnl_values)
    gross = sum(pnl_values)
    costs = sum(cost_values)
    gross_wins = sum(p for p in pnl_values if p > 0)
    gross_losses = abs(sum(p for p in pnl_values if p < 0))
    pf = gross_wins / gross_losses if gross_losses > 0 else (None if not gross_wins else float("inf"))
    return BacktestResult(len(pnl_values), wins, losses, wins / len(pnl_values) if pnl_values else 0.0, gross, costs, gross - costs, pf)


class AdvancedBacktestEngine:
    """Production-grade event-driven backtester with Indian transaction taxes, stops, slippage and metrics."""

    def __init__(
        self,
        initial_capital: float = 1_000_000.0,
        slippage_bps: float = 3.0,
        enable_statutory_charges: bool = True,
        risk_per_trade_pct: float = 1.0,
    ) -> None:
        self.initial_capital = initial_capital
        self.slippage_bps = slippage_bps
        self.enable_statutory_charges = enable_statutory_charges
        self.risk_per_trade_pct = risk_per_trade_pct

    def run(
        self,
        frame: pd.DataFrame,
        strategy: BaseStrategy,
        symbol: str = "NIFTY",
        timeframe: str = "1d",
        warmup_bars: int = 30,
    ) -> ComprehensiveBacktestMetrics:
        strategy.validate(frame)
        df = frame.sort_values("timestamp").reset_index(drop=True).copy()

        capital = self.initial_capital
        position_qty = 0  # positive for long, negative for short
        entry_price = 0.0
        entry_time = ""
        stop_loss: float | None = None
        take_profit: float | None = None

        trades_list: list[DetailedTrade] = []
        equity_history: list[dict[str, Any]] = []
        daily_returns: list[float] = []
        monthly_returns: dict[str, float] = {}

        equity_history.append({"timestamp": str(df["timestamp"].iloc[0]), "equity": capital, "drawdown_pct": 0.0})
        peak_capital = capital

        for i in range(warmup_bars, len(df) - 1):
            curr_bar = df.iloc[i]
            next_bar = df.iloc[i + 1]
            curr_ts = str(curr_bar["timestamp"])
            next_open = float(next_bar["open"])
            next_high = float(next_bar["high"])
            next_low = float(next_bar["low"])

            # 1. Check existing position stop loss or take profit within next bar range
            if position_qty != 0:
                is_long = position_qty > 0
                exit_price = None
                exit_reason = ""

                if is_long:
                    if stop_loss and next_low <= stop_loss:
                        # Slippage on stop hit
                        slip = stop_loss * (self.slippage_bps / 10_000.0)
                        exit_price = max(0.01, min(stop_loss - slip, next_open))
                        exit_reason = "STOP_LOSS"
                    elif take_profit and next_high >= take_profit:
                        slip = take_profit * (self.slippage_bps / 10_000.0)
                        exit_price = max(0.01, take_profit - slip)
                        exit_reason = "TAKE_PROFIT"
                else:
                    if stop_loss and next_high >= stop_loss:
                        slip = stop_loss * (self.slippage_bps / 10_000.0)
                        exit_price = stop_loss + slip
                        exit_reason = "STOP_LOSS"
                    elif take_profit and next_low <= take_profit:
                        slip = take_profit * (self.slippage_bps / 10_000.0)
                        exit_price = take_profit + slip
                        exit_reason = "TAKE_PROFIT"

                if exit_price is not None:
                    # Close trade
                    gross_pnl = (exit_price - entry_price) * position_qty
                    turnover_buy = (entry_price if is_long else exit_price) * abs(position_qty)
                    turnover_sell = (exit_price if is_long else entry_price) * abs(position_qty)
                    fees = (
                        calculate_indian_market_charges(turnover_buy, turnover_sell)
                        if self.enable_statutory_charges
                        else (turnover_buy + turnover_sell) * (self.slippage_bps / 10_000.0)
                    )
                    net_pnl = gross_pnl - fees
                    capital += net_pnl
                    pct = (net_pnl / (entry_price * abs(position_qty))) * 100.0 if entry_price > 0 else 0.0

                    trades_list.append(
                        DetailedTrade(
                            trade_id=len(trades_list) + 1,
                            symbol=symbol,
                            direction="LONG" if is_long else "SHORT",
                            entry_time=entry_time,
                            entry_price=round(entry_price, 2),
                            exit_time=str(next_bar["timestamp"]),
                            exit_price=round(exit_price, 2),
                            quantity=abs(position_qty),
                            gross_pnl=round(gross_pnl, 2),
                            fees=round(fees, 2),
                            net_pnl=round(net_pnl, 2),
                            return_pct=round(pct, 2),
                            exit_reason=exit_reason,
                        )
                    )
                    position_qty = 0
                    entry_price = 0.0
                    stop_loss, take_profit = None, None

            # 2. Strategy evaluation up to time t
            history = df.iloc[: i + 1]
            signal = strategy.generate(history, symbol, timeframe)
            wanted_dir = signal.direction

            # Execute signal change at next bar open with slippage
            if wanted_dir != ("long" if position_qty > 0 else ("short" if position_qty < 0 else "flat")):
                # Close any opposite active position
                if position_qty != 0:
                    is_long = position_qty > 0
                    slip = next_open * (self.slippage_bps / 10_000.0)
                    exit_price = next_open - slip if is_long else next_open + slip
                    gross_pnl = (exit_price - entry_price) * position_qty
                    turnover_buy = (entry_price if is_long else exit_price) * abs(position_qty)
                    turnover_sell = (exit_price if is_long else entry_price) * abs(position_qty)
                    fees = (
                        calculate_indian_market_charges(turnover_buy, turnover_sell)
                        if self.enable_statutory_charges
                        else (turnover_buy + turnover_sell) * (self.slippage_bps / 10_000.0)
                    )
                    net_pnl = gross_pnl - fees
                    capital += net_pnl
                    pct = (net_pnl / (entry_price * abs(position_qty))) * 100.0 if entry_price > 0 else 0.0

                    trades_list.append(
                        DetailedTrade(
                            trade_id=len(trades_list) + 1,
                            symbol=symbol,
                            direction="LONG" if is_long else "SHORT",
                            entry_time=entry_time,
                            entry_price=round(entry_price, 2),
                            exit_time=str(next_bar["timestamp"]),
                            exit_price=round(exit_price, 2),
                            quantity=abs(position_qty),
                            gross_pnl=round(gross_pnl, 2),
                            fees=round(fees, 2),
                            net_pnl=round(net_pnl, 2),
                            return_pct=round(pct, 2),
                            exit_reason="SIGNAL_REVERSAL",
                        )
                    )
                    position_qty = 0
                    entry_price = 0.0
                    stop_loss, take_profit = None, None

                # Open new position
                if wanted_dir in ("long", "short"):
                    is_long = wanted_dir == "long"
                    slip = next_open * (self.slippage_bps / 10_000.0)
                    fill_price = next_open + slip if is_long else next_open - slip
                    
                    # Risk-adjusted quantity sizing
                    risk_amount = capital * (self.risk_per_trade_pct / 100.0)
                    sl_dist = abs(fill_price - (signal.suggested_stop or fill_price * 0.98))
                    sl_dist = max(sl_dist, fill_price * 0.005)  # min 0.5% stop distance
                    qty = int(risk_amount // sl_dist)
                    
                    # Cap by max 25% single trade capital allocation
                    max_cap_qty = int((capital * 0.25) // fill_price)
                    qty = max(1, min(qty, max_cap_qty))

                    position_qty = qty if is_long else -qty
                    entry_price = fill_price
                    entry_time = str(next_bar["timestamp"])
                    stop_loss = signal.suggested_stop
                    take_profit = signal.suggested_target

            # Update equity
            curr_equity = capital
            if position_qty != 0:
                unrealized = (next_open - entry_price) * position_qty
                curr_equity += unrealized

            peak_capital = max(peak_capital, curr_equity)
            dd_pct = (peak_capital - curr_equity) / peak_capital if peak_capital > 0 else 0.0
            equity_history.append({
                "timestamp": str(next_bar["timestamp"]),
                "equity": round(curr_equity, 2),
                "drawdown_pct": round(dd_pct * 100, 2),
            })

            # Track month return
            month_key = str(next_bar["timestamp"])[:7]
            monthly_returns[month_key] = monthly_returns.get(month_key, 0.0)

        # Close remaining open position at end of backtest
        if position_qty != 0:
            final_bar = df.iloc[-1]
            final_close = float(final_bar["close"])
            is_long = position_qty > 0
            gross_pnl = (final_close - entry_price) * position_qty
            turnover_buy = (entry_price if is_long else final_close) * abs(position_qty)
            turnover_sell = (final_close if is_long else entry_price) * abs(position_qty)
            fees = (
                calculate_indian_market_charges(turnover_buy, turnover_sell)
                if self.enable_statutory_charges
                else (turnover_buy + turnover_sell) * (self.slippage_bps / 10_000.0)
            )
            net_pnl = gross_pnl - fees
            capital += net_pnl
            pct = (net_pnl / (entry_price * abs(position_qty))) * 100.0 if entry_price > 0 else 0.0

            trades_list.append(
                DetailedTrade(
                    trade_id=len(trades_list) + 1,
                    symbol=symbol,
                    direction="LONG" if is_long else "SHORT",
                    entry_time=entry_time,
                    entry_price=round(entry_price, 2),
                    exit_time=str(final_bar["timestamp"]),
                    exit_price=round(final_close, 2),
                    quantity=abs(position_qty),
                    gross_pnl=round(gross_pnl, 2),
                    fees=round(fees, 2),
                    net_pnl=round(net_pnl, 2),
                    return_pct=round(pct, 2),
                    exit_reason="BACKTEST_END",
                )
            )

        # Performance summary metrics
        total_trades = len(trades_list)
        wins = [t for t in trades_list if t.net_pnl > 0]
        losses = [t for t in trades_list if t.net_pnl <= 0]
        win_count = len(wins)
        loss_count = len(losses)
        win_rate = (win_count / total_trades * 100.0) if total_trades > 0 else 0.0

        gross_pnl = sum(t.gross_pnl for t in trades_list)
        total_fees = sum(t.fees for t in trades_list)
        net_pnl = sum(t.net_pnl for t in trades_list)

        sum_wins = sum(t.net_pnl for t in wins)
        sum_losses = abs(sum(t.net_pnl for t in losses))
        profit_factor = round(sum_wins / sum_losses, 2) if sum_losses > 0 else (None if not sum_wins else float("inf"))

        avg_trade = net_pnl / total_trades if total_trades > 0 else 0.0
        avg_win = sum_wins / win_count if win_count > 0 else 0.0
        avg_loss = sum_losses / loss_count if loss_count > 0 else 0.0
        win_loss_ratio = round(avg_win / avg_loss, 2) if avg_loss > 0 else 0.0

        # Expectancy = (Win% * AvgWin) - (Loss% * AvgLoss)
        win_prob = win_count / total_trades if total_trades > 0 else 0.0
        loss_prob = loss_count / total_trades if total_trades > 0 else 0.0
        expectancy = (win_prob * avg_win) - (loss_prob * avg_loss)

        # Drawdown
        equities = [h["equity"] for h in equity_history]
        max_dd_amount = 0.0
        max_dd_pct = 0.0
        running_peak = self.initial_capital
        for eq in equities:
            if eq > running_peak:
                running_peak = eq
            dd_amt = running_peak - eq
            dd_pct = (dd_amt / running_peak) * 100.0 if running_peak > 0 else 0.0
            if dd_amt > max_dd_amount:
                max_dd_amount = dd_amt
            if dd_pct > max_dd_pct:
                max_dd_pct = dd_pct

        # Returns timeseries for Sharpe & Sortino (annualized 252 days)
        eq_series = pd.Series(equities)
        returns = eq_series.pct_change().dropna()
        risk_free_daily = 0.065 / 252.0  # 6.5% risk-free rate proxy
        excess_returns = returns - risk_free_daily
        
        sharpe = 0.0
        sortino = 0.0
        if len(returns) > 5 and returns.std() > 0:
            sharpe = round(float(np.sqrt(252) * excess_returns.mean() / returns.std()), 2)
            downside = returns[returns < 0]
            if len(downside) > 0 and downside.std() > 0:
                sortino = round(float(np.sqrt(252) * excess_returns.mean() / downside.std()), 2)

        # CAGR
        days = max(1, len(df))
        years = days / 252.0
        cagr = ((capital / self.initial_capital) ** (1.0 / max(years, 0.1)) - 1.0) * 100.0

        return ComprehensiveBacktestMetrics(
            total_trades=total_trades,
            winning_trades=win_count,
            losing_trades=loss_count,
            win_rate_pct=round(win_rate, 2),
            gross_pnl=round(gross_pnl, 2),
            total_fees=round(total_fees, 2),
            net_pnl=round(net_pnl, 2),
            profit_factor=profit_factor,
            expectancy=round(expectancy, 2),
            average_trade_pnl=round(avg_trade, 2),
            average_win=round(avg_win, 2),
            average_loss=round(avg_loss, 2),
            win_loss_ratio=win_loss_ratio,
            max_drawdown_amount=round(max_dd_amount, 2),
            max_drawdown_pct=round(max_dd_pct, 2),
            sharpe_ratio=sharpe,
            sortino_ratio=sortino,
            cagr_pct=round(cagr, 2),
            equity_curve=equity_history,
            monthly_returns=monthly_returns,
            trades_log=trades_list,
        )

    def walk_forward_validation(
        self,
        frame: pd.DataFrame,
        strategy: BaseStrategy,
        symbol: str = "NIFTY",
        train_split: float = 0.70,
    ) -> dict[str, Any]:
        """Chronological split between in-sample training and out-of-sample testing."""
        split_idx = int(len(frame) * train_split)
        in_sample = frame.iloc[:split_idx].copy()
        out_of_sample = frame.iloc[split_idx:].copy()

        in_sample_metrics = self.run(in_sample, strategy, symbol)
        out_sample_metrics = self.run(out_of_sample, strategy, symbol)

        return {
            "in_sample": in_sample_metrics.to_dict(),
            "out_of_sample": out_sample_metrics.to_dict(),
            "degradation_pct": round(
                ((out_sample_metrics.win_rate_pct - in_sample_metrics.win_rate_pct) / max(in_sample_metrics.win_rate_pct, 1e-4)) * 100.0,
                2,
            ),
        }
