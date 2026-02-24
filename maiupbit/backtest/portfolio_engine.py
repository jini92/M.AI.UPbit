"""포트폴리오 백테스트 엔진.

PortfolioStrategy 기반 다중 자산 백테스트를 실행합니다.
주기적 리밸런싱으로 자산배분 전략을 검증합니다.
"""
from __future__ import annotations

import pandas as pd


class PortfolioBacktestEngine:
    """포트폴리오 백테스트 엔진.

    Usage:
        engine = PortfolioBacktestEngine(initial_capital=10_000_000)
        result = engine.run(data, strategy, rebalance_days=7)
    """

    def __init__(self, initial_capital: float = 10_000_000) -> None:
        self.initial_capital = initial_capital

    def run(
        self,
        data: dict[str, pd.DataFrame],
        strategy,
        rebalance_days: int = 7,
    ) -> dict:
        """포트폴리오 백테스트 실행.

        Args:
            data: {symbol: OHLCV DataFrame} 딕셔너리.
            strategy: PortfolioStrategy 구현체 (allocate() 메서드 필요).
            rebalance_days: 리밸런싱 주기 (일).

        Returns:
            dict: {total_return, sharpe_ratio, max_drawdown, equity_curve,
                   allocation_history, per_asset_return, num_rebalances}.
        """
        # 공통 날짜 인덱스 생성
        common_dates = None
        for symbol, df in data.items():
            if common_dates is None:
                common_dates = set(df.index)
            else:
                common_dates &= set(df.index)

        if not common_dates:
            return self._empty_result()

        dates = sorted(common_dates)

        holdings: dict[str, float] = {}  # symbol -> quantity
        cash = self.initial_capital

        equity_curve = []
        allocation_history = []
        days_since_rebalance = rebalance_days  # 첫날 리밸런싱

        for date in dates:
            days_since_rebalance += 1

            # 리밸런싱
            if days_since_rebalance >= rebalance_days:
                # 현재 포트폴리오 가치 계산
                total_value = cash
                for symbol, qty in holdings.items():
                    price = data[symbol].loc[date, "close"]
                    total_value += qty * price

                # 전량 매도
                cash = total_value
                holdings = {}

                # 새 배분 산출
                data_up_to = {
                    s: df.loc[:date] for s, df in data.items()
                }
                allocations = strategy.allocate(data_up_to, date)

                # 매수
                for symbol, weight in allocations.items():
                    if symbol not in data or weight <= 0:
                        continue
                    invest_amount = total_value * weight
                    price = data[symbol].loc[date, "close"]
                    if price > 0:
                        holdings[symbol] = invest_amount / price
                        cash -= invest_amount

                allocation_history.append({
                    "date": date,
                    "allocations": allocations.copy(),
                })
                days_since_rebalance = 0

            # 일일 포트폴리오 가치
            portfolio_value = cash
            for symbol, qty in holdings.items():
                price = data[symbol].loc[date, "close"]
                portfolio_value += qty * price

            equity_curve.append({"date": date, "value": portfolio_value})

        if not equity_curve:
            return self._empty_result()

        equity_series = pd.Series(
            [e["value"] for e in equity_curve],
            index=[e["date"] for e in equity_curve],
        )

        # 수익률 계산
        total_return = (
            (equity_series.iloc[-1] - self.initial_capital)
            / self.initial_capital
            * 100
        )

        # 샤프 비율 (365일 기준, 암호화폐)
        returns = equity_series.pct_change().dropna()
        sharpe = float(
            (returns.mean() / returns.std() * (365**0.5))
            if len(returns) > 1 and returns.std() > 0
            else 0
        )

        # MDD
        peak = equity_series.cummax()
        drawdown = (equity_series - peak) / peak
        mdd = float(drawdown.min() * 100)

        # 자산별 수익률
        per_asset_return = {}
        for symbol, df in data.items():
            if dates[0] in df.index and dates[-1] in df.index:
                start_price = df.loc[dates[0], "close"]
                end_price = df.loc[dates[-1], "close"]
                if start_price > 0:
                    per_asset_return[symbol] = round(
                        (end_price - start_price) / start_price * 100, 2
                    )

        return {
            "total_return": round(total_return, 2),
            "sharpe_ratio": round(sharpe, 2),
            "max_drawdown": round(mdd, 2),
            "final_equity": round(equity_series.iloc[-1], 0),
            "num_rebalances": len(allocation_history),
            "equity_curve": equity_series,
            "allocation_history": allocation_history,
            "per_asset_return": per_asset_return,
        }

    def _empty_result(self) -> dict:
        """빈 결과 반환."""
        return {
            "total_return": 0.0,
            "sharpe_ratio": 0.0,
            "max_drawdown": 0.0,
            "final_equity": self.initial_capital,
            "num_rebalances": 0,
            "equity_curve": pd.Series(dtype=float),
            "allocation_history": [],
            "per_asset_return": {},
        }
