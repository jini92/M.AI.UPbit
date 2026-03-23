#!/usr/bin/env python3
"""Quant strategy execution script — MAIBOT (OpenClaw) integration.

Usage:
    python scripts/quant.py momentum [--symbols KRW-BTC,KRW-ETH] [--top 5] [--days 400]
    python scripts/quant.py breakout KRW-BTC [--k 0.5] [--days 60]
    python scripts/quant.py factor [--symbols KRW-BTC,KRW-ETH] [--top 5]
    python scripts/quant.py allocate [--symbols KRW-BTC,KRW-ETH]
    python scripts/quant.py season
    python scripts/quant.py backtest momentum [--symbols KRW-BTC,KRW-ETH] [--days 365]
"""
import argparse
import json
import sys
import time
from datetime import datetime

from dotenv import load_dotenv


DEFAULT_SYMBOLS = [
    "KRW-BTC", "KRW-ETH", "KRW-XRP", "KRW-SOL", "KRW-ADA",
    "KRW-DOGE", "KRW-AVAX", "KRW-DOT", "KRW-LINK",
]


def _fetch_multi_ohlcv(exchange, symbols: list[str], days: int) -> dict:
    """Fetch multiple coin OHLCV (rate limit handling)."""
    data = {}
    for symbol in symbols:
        df = exchange.get_ohlcv(symbol, "day", count=days)
        if df is not None and len(df) > 0:
            data[symbol] = df
        time.sleep(0.1)  # UPbit rate limit
    return data


def cmd_momentum(args):
    """Dual momentum ranking."""
    from maiupbit.services import create_exchange
    from maiupbit.strategies.momentum import DualMomentumStrategy, DualMomentumConfig

    exchange = create_exchange()
    symbols = args.symbols.split(",") if args.symbols else DEFAULT_SYMBOLS
    data = _fetch_multi_ohlcv(exchange, symbols, args.days)

    if not data:
        print(json.dumps({"error": "Data fetch failed"}))
        sys.exit(1)

    strategy = DualMomentumStrategy(DualMomentumConfig(top_n=args.top))
    rankings = strategy.rank_coins(data)
    allocations = strategy.allocate(data)

    result = {
        "command": "momentum",
        "rankings": rankings,
        "allocations": allocations,
        "coins_analyzed": len(data),
    }
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))


def cmd_breakout(args):
    """Volatility breakout signal."""
    from maiupbit.services import create_exchange
    from maiupbit.strategies.volatility_breakout import (
        VolatilityBreakoutStrategy,
        VolatilityBreakoutConfig,
    )

    exchange = create_exchange()
    data = exchange.get_ohlcv(args.symbol, "day", count=args.days)

    if data is None or len(data) == 0:
        print(json.dumps({"error": f"{args.symbol} data fetch failed"}))
        sys.exit(1)

    config = VolatilityBreakoutConfig(k=args.k)
    strategy = VolatilityBreakoutStrategy(config)
    sig = strategy.signal(data)

    optimal_k = VolatilityBreakoutStrategy.find_optimal_k(data)
    best_k = max(optimal_k, key=optimal_k.get) if optimal_k else args.k

    result = {
        "command": "breakout",
        "symbol": args.symbol,
        "signal": sig,
        "signal_text": {1: "Buy", -1: "Sell", 0: "Hold"}.get(sig, "Hold"),
        "k": args.k,
        "optimal_k": best_k,
        "k_performance": optimal_k,
        "current_price": float(data["close"].iloc[-1]),
    }
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))


def cmd_factor(args):
    """Multi-factor ranking."""
    from maiupbit.services import create_exchange
    from maiupbit.strategies.multi_factor import MultiFactorStrategy, MultiFactorConfig

    exchange = create_exchange()
    symbols = args.symbols.split(",") if args.symbols else DEFAULT_SYMBOLS
    data = _fetch_multi_ohlcv(exchange, symbols, args.days)

    if not data:
        print(json.dumps({"error": "Data fetch failed"}))
        sys.exit(1)

    strategy = MultiFactorStrategy(MultiFactorConfig(top_n=args.top))
    rankings = strategy.rank_coins(data)
    allocations = strategy.allocate(data)

    result = {
        "command": "factor",
        "rankings": rankings,
        "allocations": allocations,
        "coins_analyzed": len(data),
    }
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))


def cmd_allocate(args):
    """GTAA asset allocation."""
    from maiupbit.services import create_exchange
    from maiupbit.strategies.allocation import GTAAStrategy
    from maiupbit.strategies.seasonal import SeasonalFilter
    from maiupbit.strategies.risk import RiskManager

    exchange = create_exchange()
    symbols = args.symbols.split(",") if args.symbols else DEFAULT_SYMBOLS
    data = _fetch_multi_ohlcv(exchange, symbols, args.days)

    if not data:
        print(json.dumps({"error": "Data fetch failed"}))
        sys.exit(1)

    gtaa = GTAAStrategy()
    seasonal = SeasonalFilter()
    risk_manager = RiskManager()

    allocations = gtaa.allocate(data)
    season_info = seasonal.get_season_info()
    adjusted_allocations = seasonal.adjust_allocations(allocations)
    final_allocations = risk_manager.apply_equal_weight_constraint(adjusted_allocations)

    result = {
        "command": "allocate",
        "symbols": list(data.keys()),
        "raw_allocations": allocations,
        "season_adjusted": adjusted_allocations,
        "final_allocations": final_allocations,
        "season": season_info["season"],
        "halving_phase": season_info["halving_phase"],
        "multiplier": season_info["multiplier"],
    }
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))


def cmd_season(args):
    """Season information."""
    from maiupbit.strategies.seasonal import SeasonalFilter

    seasonal = SeasonalFilter()
    season_info = seasonal.get_season_info()

    result = {
        "command": "season",
        "season_info": season_info,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))


def cmd_backtest(args):
    """Strategy backtesting."""
    from maiupbit.services import create_exchange
    from maiupbit.strategies.momentum import DualMomentumStrategy
    from maiupbit.strategies.volatility_breakout import VolatilityBreakoutStrategy
    from maiupbit.strategies.multi_factor import MultiFactorStrategy
    from maiupbit.strategies.allocation import GTAAStrategy

    exchange = create_exchange()
    symbols = args.symbols.split(",") if args.symbols else DEFAULT_SYMBOLS
    data = _fetch_multi_ohlcv(exchange, symbols, args.days)

    if not data:
        print(json.dumps({"error": "Data fetch failed"}))
        sys.exit(1)

    if args.strategy == "momentum":
        strategy = DualMomentumStrategy()
    elif args.strategy == "breakout":
        strategy = VolatilityBreakoutStrategy()
    elif args.strategy == "factor":
        strategy = MultiFactorStrategy()
    elif args.strategy == "allocate":
        strategy = GTAAStrategy()
    else:
        print(json.dumps({"error": f"Unknown strategy: {args.strategy}"}))
        sys.exit(1)

    if args.strategy in ["momentum", "breakout"]:
        bt_result = backtest_single_strategy(strategy, data)
    elif args.strategy == "factor":
        bt_result = backtest_factor_strategy(strategy, data)
    elif args.strategy == "allocate":
        bt_result = backtest_allocation_strategy(strategy, data)

    result = {
        "command": "backtest",
        "strategy": args.strategy,
        "symbols": list(data.keys()),
        "total_return": bt_result["total_return"],
        "sharpe_ratio": bt_result["sharpe_ratio"],
        "max_drawdown": bt_result["max_drawdown"],
    }
    if args.strategy == "allocate":
        result.update({
            "num_rebalances": bt_result["num_rebalances"],
            "final_equity": bt_result["final_equity"],
            "per_asset_return": bt_result["per_asset_return"],
        })
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))


def backtest_single_strategy(strategy, data):
    """Backtest single-symbol strategy across multiple coins."""
    import numpy as np
    initial_capital = 1_000_000.0
    all_returns = []

    for symbol, df in data.items():
        if len(df) < 30:
            continue
        capital = initial_capital
        in_position = False
        buy_price = 0.0
        for j in range(30, len(df)):
            window = df.iloc[:j + 1]
            sig = strategy.signal(window)
            price = df.iloc[j]["close"]
            if sig == 1 and not in_position:
                buy_price = price
                in_position = True
            elif sig == -1 and in_position:
                capital *= price / buy_price
                in_position = False
        ret = (capital - initial_capital) / initial_capital * 100
        all_returns.append(ret)

    if not all_returns:
        return {"total_return": 0, "sharpe_ratio": 0, "max_drawdown": 0}
    avg_ret = round(np.mean(all_returns), 2)
    sharpe = round(np.mean(all_returns) / max(np.std(all_returns), 0.01), 2)
    mdd = round(min(all_returns), 2)
    return {"total_return": avg_ret, "sharpe_ratio": sharpe, "max_drawdown": mdd}


def backtest_factor_strategy(strategy, data):
    """Backtest multi-factor ranking strategy."""
    import numpy as np
    rankings = strategy.rank_coins(data)
    allocations = strategy.allocate(data)
    if not allocations:
        return {"total_return": 0, "sharpe_ratio": 0, "max_drawdown": 0}

    # Simple: equal-weight return of selected coins over period
    returns = []
    for symbol, weight in allocations.items():
        if symbol in data and len(data[symbol]) >= 30:
            df = data[symbol]
            ret = (df["close"].iloc[-1] / df["close"].iloc[-30] - 1) * 100 * weight
            returns.append(ret)
    total_ret = round(sum(returns), 2)
    sharpe = round(total_ret / max(abs(total_ret), 0.01), 2) if returns else 0
    mdd = round(min(returns), 2) if returns else 0
    return {"total_return": total_ret, "sharpe_ratio": sharpe, "max_drawdown": mdd}


def backtest_allocation_strategy(strategy, data):
    """Backtest GTAA allocation strategy with periodic rebalancing."""
    import numpy as np
    import pandas as pd
    initial_capital = 1_000_000.0
    capital = initial_capital
    rebalance_interval = 7
    num_rebalances = 0
    equity_curve = [capital]
    per_asset_return = {}

    # Find common date range
    min_len = min(len(df) for df in data.values())
    if min_len < 60:
        return {"total_return": 0, "sharpe_ratio": 0, "max_drawdown": 0,
                "num_rebalances": 0, "final_equity": capital, "per_asset_return": {}}

    current_alloc = {}
    for day in range(60, min_len, rebalance_interval):
        sliced = {s: df.iloc[:day] for s, df in data.items()}
        new_alloc = strategy.allocate(sliced)
        if new_alloc != current_alloc:
            current_alloc = new_alloc
            num_rebalances += 1

        # Calculate period return
        period_return = 0.0
        end = min(day + rebalance_interval, min_len)
        for sym, weight in current_alloc.items():
            if sym in data and end <= len(data[sym]):
                p_start = data[sym]["close"].iloc[day]
                p_end = data[sym]["close"].iloc[end - 1]
                ret = (p_end / p_start - 1) * weight
                period_return += ret
                per_asset_return[sym] = per_asset_return.get(sym, 0) + ret * 100
        capital *= (1 + period_return)
        equity_curve.append(capital)

    total_ret = round((capital - initial_capital) / initial_capital * 100, 2)
    eq = pd.Series(equity_curve)
    peak = eq.cummax()
    dd = ((eq - peak) / peak).min()
    daily_rets = eq.pct_change().dropna()
    sharpe = round(float(daily_rets.mean() / max(daily_rets.std(), 1e-6) * np.sqrt(52)), 2)
    per_asset_return = {k: round(v, 2) for k, v in per_asset_return.items()}
    return {"total_return": total_ret, "sharpe_ratio": sharpe,
            "max_drawdown": round(float(dd) * 100, 2),
            "num_rebalances": num_rebalances, "final_equity": round(capital, 0),
            "per_asset_return": per_asset_return}


def main():
    load_dotenv()

    parser = argparse.ArgumentParser(
        prog="quant", description="Quant strategy execution"
    )
    subparsers = parser.add_subparsers(dest="command", help="Strategy commands")

    # momentum
    p_mom = subparsers.add_parser("momentum", help="Dual momentum ranking")
    p_mom.add_argument("--symbols", help="Ticker codes (comma-separated)")
    p_mom.add_argument("--top", type=int, default=5, help="Top N")
    p_mom.add_argument("--days", type=int, default=400, help="Data period")
    p_mom.set_defaults(func=cmd_momentum)

    # breakout
    p_brk = subparsers.add_parser("breakout", help="Volatility breakout signal")
    p_brk.add_argument("symbol", help="Ticker code")
    p_brk.add_argument("--k", type=float, default=0.5, help="K value")
    p_brk.add_argument("--days", type=int, default=60, help="Data period")
    p_brk.set_defaults(func=cmd_breakout)

    # factor
    p_fac = subparsers.add_parser("factor", help="Multi-factor ranking")
    p_fac.add_argument("--symbols", help="Ticker codes (comma-separated)")
    p_fac.add_argument("--top", type=int, default=5, help="Top N")
    p_fac.add_argument("--days", type=int, default=200, help="Data period")
    p_fac.set_defaults(func=cmd_factor)

    # allocate
    p_alloc = subparsers.add_parser("allocate", help="GTAA asset allocation")
    p_alloc.add_argument("--symbols", help="Ticker codes (comma-separated)")
    p_alloc.add_argument("--days", type=int, default=400, help="Data period")
    p_alloc.set_defaults(func=cmd_allocate)

    # season
    p_season = subparsers.add_parser("season", help="Season information")
    p_season.set_defaults(func=cmd_season)

    # backtest
    p_bt = subparsers.add_parser("backtest", help="Strategy backtesting")
    p_bt.add_argument(
        "strategy",
        choices=["momentum", "breakout", "factor", "allocate"],
        help="Strategy",
    )
    p_bt.add_argument("--symbols", help="Ticker codes (comma-separated)")
    p_bt.add_argument("--days", type=int, default=365, help="Data period")
    p_bt.set_defaults(func=cmd_backtest)

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(0)

    args.func(args)


if __name__ == "__main__":
    main()