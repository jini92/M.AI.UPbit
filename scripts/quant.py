#!/usr/bin/env python3
"""퀀트 전략 실행 스크립트 — MAIBOT(OpenClaw) 연동.

사용:
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
    """다중 코인 OHLCV 조회 (rate limit 대응)."""
    data = {}
    for symbol in symbols:
        df = exchange.get_ohlcv(symbol, "day", count=days)
        if df is not None and len(df) > 0:
            data[symbol] = df
        time.sleep(0.1)  # UPbit rate limit
    return data


def cmd_momentum(args):
    """듀얼 모멘텀 랭킹."""
    from maiupbit.exchange.upbit import UPbitExchange
    from maiupbit.strategies.momentum import DualMomentumStrategy, DualMomentumConfig

    exchange = UPbitExchange()
    symbols = args.symbols.split(",") if args.symbols else DEFAULT_SYMBOLS
    data = _fetch_multi_ohlcv(exchange, symbols, args.days)

    if not data:
        print(json.dumps({"error": "데이터 조회 실패"}))
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
    """변동성 돌파 시그널."""
    from maiupbit.exchange.upbit import UPbitExchange
    from maiupbit.strategies.volatility_breakout import (
        VolatilityBreakoutStrategy,
        VolatilityBreakoutConfig,
    )

    exchange = UPbitExchange()
    data = exchange.get_ohlcv(args.symbol, "day", count=args.days)

    if data is None or len(data) == 0:
        print(json.dumps({"error": f"{args.symbol} 데이터 조회 실패"}))
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
        "signal_text": {1: "매수", -1: "매도", 0: "관망"}.get(sig, "관망"),
        "k": args.k,
        "optimal_k": best_k,
        "k_performance": optimal_k,
        "current_price": float(data["close"].iloc[-1]),
    }
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))


def cmd_factor(args):
    """다중팩터 랭킹."""
    from maiupbit.exchange.upbit import UPbitExchange
    from maiupbit.strategies.multi_factor import MultiFactorStrategy, MultiFactorConfig

    exchange = UPbitExchange()
    symbols = args.symbols.split(",") if args.symbols else DEFAULT_SYMBOLS
    data = _fetch_multi_ohlcv(exchange, symbols, args.days)

    if not data:
        print(json.dumps({"error": "데이터 조회 실패"}))
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
    """GTAA 자산배분."""
    from maiupbit.exchange.upbit import UPbitExchange
    from maiupbit.strategies.allocation import GTAAStrategy
    from maiupbit.strategies.seasonal import SeasonalFilter
    from maiupbit.strategies.risk import RiskManager

    exchange = UPbitExchange()
    symbols = args.symbols.split(",") if args.symbols else DEFAULT_SYMBOLS
    data = _fetch_multi_ohlcv(exchange, symbols, args.days)

    if not data:
        print(json.dumps({"error": "데이터 조회 실패"}))
        sys.exit(1)

    gtaa = GTAAStrategy()
    seasonal = SeasonalFilter()
    risk = RiskManager()

    allocations = gtaa.allocate(data)
    allocations = seasonal.adjust_allocations(allocations, datetime.now())
    allocations = risk.apply_equal_weight_constraint(allocations)

    total_invested = sum(allocations.values())

    result = {
        "command": "allocate",
        "allocations": allocations,
        "cash_ratio": round(1.0 - total_invested, 4),
        "season_info": seasonal.get_season_info(),
        "coins_analyzed": len(data),
    }
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))


def cmd_season(args):
    """시즌 정보."""
    from maiupbit.strategies.seasonal import SeasonalFilter

    seasonal = SeasonalFilter()
    info = seasonal.get_season_info()

    result = {
        "command": "season",
        **info,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))


def cmd_backtest(args):
    """전략 백테스트."""
    from maiupbit.exchange.upbit import UPbitExchange
    from maiupbit.backtest.engine import BacktestEngine
    from maiupbit.backtest.portfolio_engine import PortfolioBacktestEngine

    exchange = UPbitExchange()
    symbols = args.symbols.split(",") if args.symbols else DEFAULT_SYMBOLS[:5]
    data = _fetch_multi_ohlcv(exchange, symbols, args.days)

    if not data:
        print(json.dumps({"error": "데이터 조회 실패"}))
        sys.exit(1)

    strategy_name = args.strategy

    if strategy_name == "breakout":
        from maiupbit.strategies.volatility_breakout import VolatilityBreakoutStrategy

        symbol = symbols[0]
        if symbol not in data:
            print(json.dumps({"error": f"{symbol} 데이터 없음"}))
            sys.exit(1)

        engine = BacktestEngine(initial_capital=10_000_000)
        strategy = VolatilityBreakoutStrategy()
        bt_result = engine.run(data[symbol], strategy)

        result = {
            "command": "backtest",
            "strategy": strategy_name,
            "symbol": symbol,
            "total_return": bt_result["total_return"],
            "sharpe_ratio": bt_result["sharpe_ratio"],
            "max_drawdown": bt_result["max_drawdown"],
            "num_trades": bt_result["num_trades"],
            "final_equity": bt_result["final_equity"],
        }
    else:
        # 포트폴리오 전략 백테스트
        if strategy_name == "momentum":
            from maiupbit.strategies.momentum import DualMomentumStrategy
            strategy = DualMomentumStrategy()
        elif strategy_name == "factor":
            from maiupbit.strategies.multi_factor import MultiFactorStrategy
            strategy = MultiFactorStrategy()
        elif strategy_name == "allocate":
            from maiupbit.strategies.allocation import GTAAStrategy
            strategy = GTAAStrategy()
        else:
            print(json.dumps({"error": f"알 수 없는 전략: {strategy_name}"}))
            sys.exit(1)

        engine = PortfolioBacktestEngine(initial_capital=10_000_000)
        bt_result = engine.run(data, strategy, rebalance_days=7)

        result = {
            "command": "backtest",
            "strategy": strategy_name,
            "symbols": list(data.keys()),
            "total_return": bt_result["total_return"],
            "sharpe_ratio": bt_result["sharpe_ratio"],
            "max_drawdown": bt_result["max_drawdown"],
            "num_rebalances": bt_result["num_rebalances"],
            "final_equity": bt_result["final_equity"],
            "per_asset_return": bt_result["per_asset_return"],
        }

    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))


def main():
    load_dotenv()

    parser = argparse.ArgumentParser(
        prog="quant", description="강환국 퀀트 전략 실행"
    )
    subparsers = parser.add_subparsers(dest="command", help="전략 명령어")

    # momentum
    p_mom = subparsers.add_parser("momentum", help="듀얼 모멘텀 랭킹")
    p_mom.add_argument("--symbols", help="종목 코드 (콤마 구분)")
    p_mom.add_argument("--top", type=int, default=5, help="상위 N개")
    p_mom.add_argument("--days", type=int, default=400, help="데이터 기간")
    p_mom.set_defaults(func=cmd_momentum)

    # breakout
    p_brk = subparsers.add_parser("breakout", help="변동성 돌파 시그널")
    p_brk.add_argument("symbol", help="종목 코드")
    p_brk.add_argument("--k", type=float, default=0.5, help="k 값")
    p_brk.add_argument("--days", type=int, default=60, help="데이터 기간")
    p_brk.set_defaults(func=cmd_breakout)

    # factor
    p_fac = subparsers.add_parser("factor", help="다중팩터 랭킹")
    p_fac.add_argument("--symbols", help="종목 코드 (콤마 구분)")
    p_fac.add_argument("--top", type=int, default=5, help="상위 N개")
    p_fac.add_argument("--days", type=int, default=200, help="데이터 기간")
    p_fac.set_defaults(func=cmd_factor)

    # allocate
    p_alloc = subparsers.add_parser("allocate", help="GTAA 자산배분")
    p_alloc.add_argument("--symbols", help="종목 코드 (콤마 구분)")
    p_alloc.add_argument("--days", type=int, default=400, help="데이터 기간")
    p_alloc.set_defaults(func=cmd_allocate)

    # season
    p_season = subparsers.add_parser("season", help="시즌 정보")
    p_season.set_defaults(func=cmd_season)

    # backtest
    p_bt = subparsers.add_parser("backtest", help="전략 백테스트")
    p_bt.add_argument(
        "strategy",
        choices=["momentum", "breakout", "factor", "allocate"],
        help="전략",
    )
    p_bt.add_argument("--symbols", help="종목 코드 (콤마 구분)")
    p_bt.add_argument("--days", type=int, default=365, help="데이터 기간")
    p_bt.set_defaults(func=cmd_backtest)

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(0)

    args.func(args)


if __name__ == "__main__":
    main()
