"""
Walk-forward backtesting utilities for the autonomous model suite.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

import numpy as np
import pandas as pd

from .models import AutonomousModelSuite


@dataclass
class BacktestResult:
    strategy_name: str
    annualized_return: float
    sharpe_ratio: float
    max_drawdown: float
    win_rate: float
    turnover: float
    equity_curve: list[dict[str, Any]]
    start_date: Optional[pd.Timestamp] = None
    end_date: Optional[pd.Timestamp] = None


def _max_drawdown(equity: pd.Series) -> float:
    rolling_max = equity.cummax()
    drawdown = equity / rolling_max - 1
    return float(drawdown.min()) if not equity.empty else 0.0


def run_walk_forward_backtest(
    feature_frames: dict[str, pd.DataFrame],
    model_suite: AutonomousModelSuite,
    rebalance_step: int = 5,
    selection_count: int = 5,
) -> Optional[BacktestResult]:
    dataset = pd.concat(
        [frame.assign(symbol=symbol) for symbol, frame in feature_frames.items() if not frame.empty],
        ignore_index=True,
    )
    if dataset.empty or "target_return_30d" not in dataset.columns:
        return None

    base_predictions = model_suite._base_prediction_frame(dataset)
    meta_predictions, _ = model_suite._meta_predict_frame(dataset, base_predictions)
    dataset = pd.concat([dataset.reset_index(drop=True), meta_predictions.reset_index(drop=True)], axis=1)
    dataset = dataset.dropna(subset=["meta_return_30d", "target_return_30d"])
    if dataset.empty:
        return None

    dates = sorted(pd.to_datetime(dataset["date"]).dropna().unique())
    equity = 1.0
    curve: list[dict[str, Any]] = []
    realized_returns: list[float] = []
    turnover = 0.0

    for position, rebalance_date in enumerate(dates[::rebalance_step]):
        day_slice = dataset[pd.to_datetime(dataset["date"]) == rebalance_date].copy()
        if day_slice.empty:
            continue
        selected = day_slice.sort_values("meta_return_30d", ascending=False).head(selection_count)
        picks = selected[selected["meta_return_30d"] > 0]
        if picks.empty:
            curve.append({"date": pd.Timestamp(rebalance_date).isoformat(), "equity": equity})
            continue
        realized = picks["target_return_30d"].mean() / 100.0
        realized_returns.append(realized)
        turnover += len(picks)
        equity *= 1 + realized
        curve.append({"date": pd.Timestamp(rebalance_date).isoformat(), "equity": round(equity, 6)})

    if not curve:
        return None

    equity_series = pd.Series(
        [point["equity"] for point in curve],
        index=pd.to_datetime([point["date"] for point in curve], format="ISO8601"),
    )
    returns = pd.Series(realized_returns)
    annualized_return = float((equity_series.iloc[-1] ** (252 / max(len(curve), 1))) - 1) if len(curve) > 1 else 0.0
    sharpe_ratio = float(np.sqrt(252 / max(rebalance_step, 1)) * returns.mean() / max(returns.std(ddof=0), 1e-9)) if not returns.empty else 0.0
    win_rate = float((returns > 0).mean() * 100) if not returns.empty else 0.0

    return BacktestResult(
        strategy_name="Autonomous Ensemble Top Picks",
        annualized_return=round(annualized_return * 100, 2),
        sharpe_ratio=round(sharpe_ratio, 3),
        max_drawdown=round(_max_drawdown(equity_series) * 100, 2),
        win_rate=round(win_rate, 2),
        turnover=round(turnover, 2),
        equity_curve=curve,
        start_date=pd.to_datetime(curve[0]["date"]),
        end_date=pd.to_datetime(curve[-1]["date"]),
    )
