"""M.AI.UPbit CLI"""
import argparse
import json
import sys
import os
from dotenv import load_dotenv


def cmd_analyze(args):
    """코인 분석 실행"""
    from maiupbit.exchange.upbit import UPbitExchange
    from maiupbit.analysis.technical import TechnicalAnalyzer
    from maiupbit.indicators import trend, momentum, volatility, signals

    exchange = UPbitExchange()
    # 데이터 수집
    daily = exchange.get_ohlcv(args.symbol, "day", count=args.days)
    hourly = exchange.get_ohlcv(args.symbol, "minute60", count=args.days * 24)

    if daily is None or hourly is None:
        print(json.dumps({"error": f"Failed to fetch data for {args.symbol}"}))
        sys.exit(1)

    # 기술 지표 계산
    for df in [daily, hourly]:
        df['SMA_10'] = trend.sma(df['close'], 10)
        df['EMA_10'] = trend.ema(df['close'], 10)
        df['RSI_14'] = momentum.rsi(df['close'], 14)
        macd_line, signal_line, histogram = trend.macd(df['close'])
        df['MACD'] = macd_line
        df['Signal_Line'] = signal_line
        df['MACD_Histogram'] = histogram
        upper, middle, lower = volatility.bollinger_bands(df['close'])
        df['Upper_Band'] = upper
        df['Middle_Band'] = middle
        df['Lower_Band'] = lower
        stoch_k, stoch_d = momentum.stochastic(df['high'], df['low'], df['close'])
        df['STOCHk'] = stoch_k
        df['STOCHd'] = stoch_d

    # 기술 분석
    analyzer = TechnicalAnalyzer(exchange)
    result = analyzer.analyze(args.symbol, daily)

    # 현재가 추가
    result['current_price'] = exchange.get_current_price(args.symbol)

    if args.format == 'json':
        print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    else:
        print(f"=== {args.symbol} 분석 결과 ===")
        print(f"현재가: {result['current_price']:,.0f}")
        print(f"추천: {result.get('recommendation', 'N/A')}")
        print(f"RSI: {result.get('indicators', {}).get('rsi', 'N/A')}")
        print(f"MACD 시그널: {result.get('signals', {}).get('macd', 'N/A')}")


def cmd_portfolio(args):
    """포트폴리오 조회"""
    from maiupbit.exchange.upbit import UPbitExchange

    access_key = os.getenv("UPBIT_ACCESS_KEY")
    secret_key = os.getenv("UPBIT_SECRET_KEY")

    if not access_key or not secret_key:
        print(json.dumps({"error": "UPBIT_ACCESS_KEY and UPBIT_SECRET_KEY required"}))
        sys.exit(1)

    exchange = UPbitExchange(access_key=access_key, secret_key=secret_key)
    portfolio = exchange.get_portfolio()

    if args.format == 'json':
        print(json.dumps(portfolio, ensure_ascii=False, indent=2, default=str))
    else:
        print("=== 포트폴리오 ===")
        for asset in portfolio.get('assets', []):
            print(f"  {asset['symbol']}: {asset['quantity']:.8f} ({asset['value']:,.0f} KRW)")
        print(f"  총 자산: {portfolio.get('total_value', 0):,.0f} KRW")


def cmd_trade(args):
    """매매 실행"""
    from maiupbit.exchange.upbit import UPbitExchange

    access_key = os.getenv("UPBIT_ACCESS_KEY")
    secret_key = os.getenv("UPBIT_SECRET_KEY")

    if not access_key or not secret_key:
        print(json.dumps({"error": "UPBIT_ACCESS_KEY and UPBIT_SECRET_KEY required"}))
        sys.exit(1)

    exchange = UPbitExchange(access_key=access_key, secret_key=secret_key)

    if not args.confirm:
        price = exchange.get_current_price(args.symbol)
        print(f"⚠️ {args.action.upper()} {args.amount} {args.symbol} @ ~{price:,.0f}")
        print("실행하려면 --confirm 플래그를 추가하세요.")
        sys.exit(0)

    if args.action == 'buy':
        result = exchange.buy_market(args.symbol, args.amount)
    elif args.action == 'sell':
        result = exchange.sell_market(args.symbol, args.amount)
    else:
        print(json.dumps({"error": f"Unknown action: {args.action}"}))
        sys.exit(1)

    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))


def cmd_recommend(args):
    """종목 추천"""
    from maiupbit.exchange.upbit import UPbitExchange
    from maiupbit.analysis.technical import TechnicalAnalyzer

    exchange = UPbitExchange()
    analyzer = TechnicalAnalyzer(exchange)

    if args.method == 'trend':
        results = analyzer.recommend_by_trend(top_n=args.top)
    else:
        results = analyzer.recommend_by_performance(top_n=args.top, days=args.days)

    if args.format == 'json':
        print(json.dumps(results, ensure_ascii=False, indent=2, default=str))
    else:
        print(f"=== 추천 종목 (Top {args.top}) ===")
        for i, r in enumerate(results, 1):
            print(f"  {i}. {r['symbol']}: {r['reason']}")


def main():
    load_dotenv()

    parser = argparse.ArgumentParser(prog='maiupbit', description='AI 디지털 자산 분석 엔진')
    subparsers = parser.add_subparsers(dest='command', help='Available commands')

    # analyze
    p_analyze = subparsers.add_parser('analyze', help='코인 분석')
    p_analyze.add_argument('symbol', help='종목 코드 (예: KRW-BTC)')
    p_analyze.add_argument('--days', type=int, default=30, help='분석 기간 (일)')
    p_analyze.add_argument('--format', choices=['json', 'text'], default='text')
    p_analyze.set_defaults(func=cmd_analyze)

    # portfolio
    p_portfolio = subparsers.add_parser('portfolio', help='포트폴리오 조회')
    p_portfolio.add_argument('--format', choices=['json', 'text'], default='text')
    p_portfolio.set_defaults(func=cmd_portfolio)

    # trade
    p_trade = subparsers.add_parser('trade', help='매매 실행')
    p_trade.add_argument('action', choices=['buy', 'sell'])
    p_trade.add_argument('symbol', help='종목 코드')
    p_trade.add_argument('amount', type=float, help='수량')
    p_trade.add_argument('--confirm', action='store_true', help='매매 확인')
    p_trade.add_argument('--format', choices=['json', 'text'], default='json')
    p_trade.set_defaults(func=cmd_trade)

    # recommend
    p_recommend = subparsers.add_parser('recommend', help='종목 추천')
    p_recommend.add_argument('--method', choices=['trend', 'performance'], default='performance')
    p_recommend.add_argument('--top', type=int, default=5, help='추천 개수')
    p_recommend.add_argument('--days', type=int, default=7, help='분석 기간')
    p_recommend.add_argument('--format', choices=['json', 'text'], default='text')
    p_recommend.set_defaults(func=cmd_recommend)

    # quant
    p_quant = subparsers.add_parser('quant', help='퀀트 전략')
    quant_sub = p_quant.add_subparsers(dest='quant_command', help='퀀트 전략 명령어')

    p_q_mom = quant_sub.add_parser('momentum', help='듀얼 모멘텀 랭킹')
    p_q_mom.add_argument('--symbols', help='종목 코드 (콤마 구분)')
    p_q_mom.add_argument('--top', type=int, default=5)
    p_q_mom.add_argument('--days', type=int, default=400)
    p_q_mom.add_argument('--format', choices=['json', 'text'], default='text')

    p_q_brk = quant_sub.add_parser('breakout', help='변동성 돌파')
    p_q_brk.add_argument('symbol', help='종목 코드')
    p_q_brk.add_argument('--k', type=float, default=0.5)
    p_q_brk.add_argument('--days', type=int, default=60)
    p_q_brk.add_argument('--format', choices=['json', 'text'], default='text')

    p_q_fac = quant_sub.add_parser('factor', help='다중팩터 랭킹')
    p_q_fac.add_argument('--symbols', help='종목 코드 (콤마 구분)')
    p_q_fac.add_argument('--top', type=int, default=5)
    p_q_fac.add_argument('--days', type=int, default=200)
    p_q_fac.add_argument('--format', choices=['json', 'text'], default='text')

    p_q_alloc = quant_sub.add_parser('allocate', help='GTAA 자산배분')
    p_q_alloc.add_argument('--symbols', help='종목 코드 (콤마 구분)')
    p_q_alloc.add_argument('--days', type=int, default=400)
    p_q_alloc.add_argument('--format', choices=['json', 'text'], default='text')

    p_q_season = quant_sub.add_parser('season', help='시즌 정보')
    p_q_season.add_argument('--format', choices=['json', 'text'], default='text')

    p_q_bt = quant_sub.add_parser('backtest', help='전략 백테스트')
    p_q_bt.add_argument('strategy', choices=['momentum', 'breakout', 'factor', 'allocate'])
    p_q_bt.add_argument('--symbols', help='종목 코드 (콤마 구분)')
    p_q_bt.add_argument('--days', type=int, default=365)
    p_q_bt.add_argument('--format', choices=['json', 'text'], default='text')

    p_quant.set_defaults(func=cmd_quant)

    # train
    p_train = subparsers.add_parser('train', help='모델 학습')
    p_train.add_argument('symbol', nargs='?', default='KRW-BTC', help='종목 코드')
    p_train.add_argument('--model', choices=['transformer', 'lstm'], default='transformer', help='모델 타입')
    p_train.add_argument('--days', type=int, default=90, help='학습 데이터 기간 (일)')
    p_train.add_argument('--epochs', type=int, default=50, help='학습 에포크')
    p_train.set_defaults(func=cmd_train)

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(0)

    args.func(args)


def cmd_quant(args):
    """퀀트 전략 실행"""
    import time
    from datetime import datetime

    if not hasattr(args, 'quant_command') or not args.quant_command:
        print("Usage: maiupbit quant {momentum|breakout|factor|allocate|season|backtest}")
        sys.exit(0)

    DEFAULT_SYMBOLS = [
        "KRW-BTC", "KRW-ETH", "KRW-XRP", "KRW-SOL", "KRW-ADA",
        "KRW-DOGE", "KRW-AVAX", "KRW-DOT", "KRW-MATIC", "KRW-LINK",
    ]

    def fetch_multi(exchange, symbols, days):
        data = {}
        for s in symbols:
            df = exchange.get_ohlcv(s, "day", count=days)
            if df is not None and len(df) > 0:
                data[s] = df
            time.sleep(0.1)
        return data

    if args.quant_command == 'season':
        from maiupbit.strategies.seasonal import SeasonalFilter
        info = SeasonalFilter().get_season_info()
        if args.format == 'json':
            print(json.dumps(info, ensure_ascii=False, indent=2, default=str))
        else:
            print(f"=== 시즌 정보 ===")
            print(f"  월: {info['month']}월 ({info['season']})")
            print(f"  비중 배수: {info['multiplier']}")
            print(f"  반감기 단계: {info['halving_phase']}")
            if info['next_halving']:
                print(f"  다음 반감기: {info['next_halving']} (D-{info['days_to_next_halving']})")
        return

    from maiupbit.exchange.upbit import UPbitExchange
    exchange = UPbitExchange()

    if args.quant_command == 'momentum':
        from maiupbit.strategies.momentum import DualMomentumStrategy, DualMomentumConfig
        symbols = args.symbols.split(",") if args.symbols else DEFAULT_SYMBOLS
        data = fetch_multi(exchange, symbols, args.days)
        if not data:
            print(json.dumps({"error": "데이터 조회 실패"}))
            sys.exit(1)
        strategy = DualMomentumStrategy(DualMomentumConfig(top_n=args.top))
        rankings = strategy.rank_coins(data)
        allocations = strategy.allocate(data)
        if args.format == 'json':
            print(json.dumps({"rankings": rankings, "allocations": allocations}, ensure_ascii=False, indent=2))
        else:
            print(f"=== 듀얼 모멘텀 랭킹 (Top {args.top}) ===")
            for r in rankings[:args.top]:
                print(f"  {r['rank']}. {r['symbol']}: score={r['score']:.6f}, signal={r['avg_signal']:.2f}")

    elif args.quant_command == 'breakout':
        from maiupbit.strategies.volatility_breakout import VolatilityBreakoutStrategy, VolatilityBreakoutConfig
        data = exchange.get_ohlcv(args.symbol, "day", count=args.days)
        if data is None:
            print(json.dumps({"error": f"{args.symbol} 데이터 조회 실패"}))
            sys.exit(1)
        config = VolatilityBreakoutConfig(k=args.k)
        strategy = VolatilityBreakoutStrategy(config)
        sig = strategy.signal(data)
        sig_text = {1: "매수", -1: "매도", 0: "관망"}.get(sig, "관망")
        optimal = VolatilityBreakoutStrategy.find_optimal_k(data)
        if args.format == 'json':
            print(json.dumps({"symbol": args.symbol, "signal": sig, "signal_text": sig_text, "optimal_k": optimal}, ensure_ascii=False, indent=2, default=str))
        else:
            print(f"=== {args.symbol} 변동성 돌파 ===")
            print(f"  시그널: {sig_text} (k={args.k})")
            best_k = max(optimal, key=optimal.get) if optimal else args.k
            print(f"  최적 k: {best_k}")

    elif args.quant_command == 'factor':
        from maiupbit.strategies.multi_factor import MultiFactorStrategy, MultiFactorConfig
        symbols = args.symbols.split(",") if args.symbols else DEFAULT_SYMBOLS
        data = fetch_multi(exchange, symbols, args.days)
        if not data:
            print(json.dumps({"error": "데이터 조회 실패"}))
            sys.exit(1)
        strategy = MultiFactorStrategy(MultiFactorConfig(top_n=args.top))
        rankings = strategy.rank_coins(data)
        if args.format == 'json':
            print(json.dumps({"rankings": rankings}, ensure_ascii=False, indent=2))
        else:
            print(f"=== 다중팩터 랭킹 (Top {args.top}) ===")
            for r in rankings[:args.top]:
                print(f"  {r['rank']}. {r['symbol']}: score={r['composite_score']:.4f}")

    elif args.quant_command == 'allocate':
        from maiupbit.strategies.allocation import GTAAStrategy
        from maiupbit.strategies.seasonal import SeasonalFilter
        from maiupbit.strategies.risk import RiskManager
        symbols = args.symbols.split(",") if args.symbols else DEFAULT_SYMBOLS
        data = fetch_multi(exchange, symbols, args.days)
        if not data:
            print(json.dumps({"error": "데이터 조회 실패"}))
            sys.exit(1)
        alloc = GTAAStrategy().allocate(data)
        alloc = SeasonalFilter().adjust_allocations(alloc, datetime.now())
        alloc = RiskManager().apply_equal_weight_constraint(alloc)
        cash = round(1.0 - sum(alloc.values()), 4)
        if args.format == 'json':
            print(json.dumps({"allocations": alloc, "cash_ratio": cash}, ensure_ascii=False, indent=2))
        else:
            print("=== GTAA 자산배분 ===")
            for s, w in sorted(alloc.items(), key=lambda x: -x[1]):
                print(f"  {s}: {w*100:.1f}%")
            print(f"  현금: {cash*100:.1f}%")

    elif args.quant_command == 'backtest':
        from maiupbit.backtest.engine import BacktestEngine
        from maiupbit.backtest.portfolio_engine import PortfolioBacktestEngine
        symbols = args.symbols.split(",") if args.symbols else DEFAULT_SYMBOLS[:5]
        data = fetch_multi(exchange, symbols, args.days)
        if not data:
            print(json.dumps({"error": "데이터 조회 실패"}))
            sys.exit(1)

        if args.strategy == 'breakout':
            from maiupbit.strategies.volatility_breakout import VolatilityBreakoutStrategy
            symbol = symbols[0]
            engine = BacktestEngine(initial_capital=10_000_000)
            result = engine.run(data[symbol], VolatilityBreakoutStrategy())
        else:
            if args.strategy == 'momentum':
                from maiupbit.strategies.momentum import DualMomentumStrategy
                strat = DualMomentumStrategy()
            elif args.strategy == 'factor':
                from maiupbit.strategies.multi_factor import MultiFactorStrategy
                strat = MultiFactorStrategy()
            else:
                from maiupbit.strategies.allocation import GTAAStrategy
                strat = GTAAStrategy()
            engine = PortfolioBacktestEngine(initial_capital=10_000_000)
            result = engine.run(data, strat, rebalance_days=7)

        out = {k: v for k, v in result.items() if k not in ('equity_curve', 'allocation_history', 'trades')}
        if args.format == 'json':
            print(json.dumps(out, ensure_ascii=False, indent=2, default=str))
        else:
            print(f"=== {args.strategy} 백테스트 결과 ===")
            print(f"  수익률: {result['total_return']:.2f}%")
            print(f"  샤프비율: {result['sharpe_ratio']:.2f}")
            print(f"  MDD: {result['max_drawdown']:.2f}%")
            print(f"  최종자산: {result['final_equity']:,.0f}")


def cmd_train(args):
    """모델 학습"""
    from maiupbit.exchange.upbit import UPbitExchange

    exchange = UPbitExchange()
    hourly = exchange.get_ohlcv(args.symbol, 'minute60', count=args.days * 24)

    if hourly is None or len(hourly) == 0:
        print(json.dumps({"error": f"Failed to fetch data for {args.symbol}"}))
        sys.exit(1)

    close_data = hourly['close'].values
    model_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'models')
    os.makedirs(model_dir, exist_ok=True)

    if args.model == 'transformer':
        try:
            from maiupbit.models.transformer import TransformerPredictor
            lookback = min(168, len(close_data) // 3)
            predictor = TransformerPredictor(lookback=lookback)
            result = predictor.train(close_data, epochs=args.epochs)
            model_path = os.path.join(model_dir, f'{args.symbol.replace("-", "_").lower()}_transformer.pt')
            predictor.save(model_path)
        except ImportError:
            print(json.dumps({"error": "torch not installed. Run: pip install maiupbit[transformer]"}))
            sys.exit(1)
    else:
        try:
            from maiupbit.models.lstm import LSTMPredictor
            predictor = LSTMPredictor(lookback=720)
            result = predictor.train(close_data, epochs=args.epochs)
            model_path = os.path.join(model_dir, f'{args.symbol.replace("-", "_").lower()}_lstm.h5')
            predictor.save(model_path)
        except ImportError:
            print(json.dumps({"error": "tensorflow not installed. Run: pip install maiupbit[lstm]"}))
            sys.exit(1)

    print(json.dumps({
        "status": "success",
        "symbol": args.symbol,
        "model": args.model,
        "path": model_path,
        "result": result,
    }, ensure_ascii=False, indent=2, default=str))


if __name__ == '__main__':
    main()
