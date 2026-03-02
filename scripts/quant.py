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
    "KRW-DOGE", "KRW-AVAX", "KRW-DOT", "KRW-MATIC", "KRW-LINK",
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
    from maiupbit.exchange.upbit import UPbitExchange
    from maiupbit.strategies.momentum import DualMomentumStrategy, DualMomentumConfig

    exchange = UPbitExchange()
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
    from maiupbit.exchange.upbit import UPbitExchange
    from maiupbit.strategies.volatility_breakout import (
        VolatilityBreakoutStrategy,
        VolatilityBreakoutConfig,
    )

    exchange = UPbitExchange()
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
    from maiupbit.exchange.upbit import UPbitExchange
    from maiupbit.strategies.multi_factor import MultiFactorStrategy, MultiFactorConfig

    exchange = UPbitExchange()
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
    from maiupbit.exchange.upbit import UPbitExchange
    from maiupbit.strategies.allocation import GTAAStrategy
    from maiupbit.strategies.seasonal import SeasonalFilter
    from maiupbit.strategies.risk import RiskManager

    exchange = UPbitExchange()
    symbols = args.symbols.split(",") if args.symbols else DEFAULT_SYMBOLS
    data = _fetch_multi_ohlcv(exchange, symbols, args.days)

    if not data:
        print(json.dumps({"error": "Data fetch failed"}))
        sys.exit(1)

    gtaa = GTAAStrategy()
    seasonal = SeasonalFilter()
    risk_manager = RiskManager()

    allocations = gtaa.allocate(data)
    rebalance_days = 7
    final_allocations = seasonal.rebalance(allocations, rebalance_days=rebalance_days)
    optimized_allocations = risk_manager.optimize(final_allocations)

    result = {
        "command": "allocate",
        "symbols": list(data.keys()),
        "final_allocations": optimized_allocations,
        "rebalances": len(final_allocations),
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
    from maiupbit.exchange.upbit import UPbitExchange
    from maiupbit.strategies.momentum import DualMomentumStrategy
    from maiupbit.strategies.volatility_breakout import VolatilityBreakoutStrategy
    from maiupbit.strategies.multi_factor import MultiFactorStrategy
    from maiupbit.strategies.allocation import GTAAStrategy

    exchange = UPbitExchange()
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
    """Backtest single strategy."""
    pass


def backtest_factor_strategy(strategy, data):
    """Backtest factor strategy."""
    pass


def backtest_allocation_strategy(strategy, data):
    """Backtest allocation strategy."""
    pass


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