# M.AI.UPbit

[![PyPI version](https://img.shields.io/pypi/v/maiupbit.svg)](https://pypi.org/project/maiupbit/)
[![Python](https://img.shields.io/pypi/pyversions/maiupbit.svg)](https://pypi.org/project/maiupbit/)
[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](LICENSE)
[![Tests](https://img.shields.io/badge/coverage-70%25%2B-brightgreen.svg)](tests/)
[![Newsletter](https://img.shields.io/badge/📬%20AI%20Quant%20Letter-Subscribe-orange)](https://jinilee.substack.com)

> **AI-powered cryptocurrency analysis engine for Korean exchanges**
>
> UPbit API 키 없이도 시세 조회·기술 지표·AI 분석을 즉시 사용할 수 있는 Python 패키지

---




## 📊 Weekly Quant Signal (Auto-Updated)

| 항목 | 현황 |
|------|------|
| 업데이트 | 2026-03-22 |
| 매매 시그널 | ![signal](https://img.shields.io/badge/Signal-CASH-red) |
| 시즌 | ![season](https://img.shields.io/badge/Season-bullish-brightgreen) |
| 모멘텀 1위 | N/A |

> 🤖 [maiupbit](https://pypi.org/project/maiupbit/) 엔진 자동 생성 · [뉴스레터 구독](#newsletter)

## Features

| 기능 | 설명 |
|------|------|
| 📊 **기술 지표** | SMA, EMA, RSI, MACD, Bollinger Bands, Stochastic (pandas-ta 기반) |
| 🤖 **LSTM 예측** | TensorFlow/Keras 사전 학습 모델로 단기 가격 방향 예측 |
| 🧠 **GPT-4o 분석** | OpenAI API로 시장 상황 종합 분석 → buy / sell / hold 판단 |
| 📰 **뉴스 감성 분석** | Google RSS + BeautifulSoup으로 실시간 뉴스 감성 스코어링 |
| 🔁 **백테스팅** | 전략 성과를 과거 데이터로 시뮬레이션 |
| ⚡ **CLI** | `maiupbit analyze KRW-BTC` — 터미널에서 즉시 분석 |

> **인증 불필요:** 시세 조회·기술 분석·AI 분석은 UPbit API 키 없이 동작합니다.
> 포트폴리오 조회 및 매매 실행만 API 키가 필요합니다.

---

## Quick Start

```bash
pip install maiupbit
```

```python
from maiupbit.exchange.upbit import UPbitExchange
from maiupbit.analysis.technical import TechnicalAnalyzer

exchange = UPbitExchange()                     # API 키 불필요
analyzer = TechnicalAnalyzer(exchange)
result   = analyzer.analyze("KRW-BTC")        # 기술 지표 + 매매 신호
print(result["recommendation"])               # → "buy" / "sell" / "hold"
```

LSTM + GPT-4o 분석까지 원한다면:

```python
from maiupbit.analysis.llm import LLMAnalyzer

llm = LLMAnalyzer()                            # OPENAI_API_KEY 환경 변수 필요
report = llm.analyze("KRW-BTC", result)
print(report["summary"])
```

---

## CLI Usage

```bash
# 코인 분석 (API 키 불필요)
maiupbit analyze KRW-BTC
maiupbit analyze KRW-ETH --days 60 --format json

# 포트폴리오 조회 (API 키 필요)
maiupbit portfolio
maiupbit portfolio --format json

# 매매 실행 (API 키 필요 + --confirm 필수)
maiupbit trade buy  KRW-BTC 50000             # ⚠️ 미리보기만 출력
maiupbit trade buy  KRW-BTC 50000 --confirm   # ✅ 실제 매수 실행
maiupbit trade sell KRW-ETH 0.1   --confirm   # ✅ 실제 매도 실행

# 종목 추천 (API 키 불필요)
maiupbit recommend --method performance --top 5 --format json
maiupbit recommend --method trend --top 3
```

> **⚠️ 안전 규칙:** `trade` 커맨드는 `--confirm` 플래그 없이 절대 매매를 실행하지 않습니다.
> 미리보기를 확인한 뒤 명시적으로 `--confirm`을 추가하세요.

---

## OpenClaw / MAIBOT Integration

`scripts/` 는 MAIBOT(OpenClaw)이 `exec`로 직접 호출하는 래퍼 스크립트입니다.
패키지 설치 없이 `python scripts/*.py` 형태로 바로 사용할 수 있습니다.

```bash
# 비트코인 분석 (인증 불필요)
python scripts/analyze.py KRW-BTC

# 시장 모니터링 — 5개 코인 급등/급락/RSI 이상 감지 (인증 불필요)
python scripts/monitor.py

# 일일 리포트 생성 (인증 불필요, 포트폴리오는 키 필요)
python scripts/daily_report.py

# 포트폴리오 조회 (API 키 필요)
python scripts/portfolio.py

# 매매 미리보기 → 확인 후 실행 (API 키 필요)
python scripts/trade.py buy KRW-BTC 50000
python scripts/trade.py buy KRW-BTC 50000 --confirm

# LSTM 모델 학습 (GPU 권장)
python scripts/train_model.py KRW-BTC
```

전체 아키텍처:

```
👤 사용자
  └─▶ 📱 MAIBOTALKS (앱)
        └─▶ 🦞 MAIBOT (OpenClaw 에이전트)
              └─▶ 📦 maiupbit (분석 엔진)
                    └─▶ 🏦 UPbit API
```

MAIBOT은 분석 결과를 자연어로 해석해 MAIBOTALKS를 통해 사용자에게 전달합니다.
별도 웹 서버나 UI 없이 MAI Universe 인프라를 그대로 활용합니다.

---

## Architecture

```
M.AI.UPbit/
├── maiupbit/                  # PyPI 패키지 (핵심 엔진)
│   ├── exchange/
│   │   ├── base.py            # 거래소 추상 인터페이스
│   │   └── upbit.py           # UPbit API 래퍼 (pyupbit)
│   ├── indicators/
│   │   ├── trend.py           # SMA, EMA, MACD
│   │   ├── momentum.py        # RSI, Stochastic
│   │   ├── volatility.py      # Bollinger Bands, ATR
│   │   └── signals.py         # 복합 매매 신호
│   ├── analysis/
│   │   ├── technical.py       # 기술적 분석 종합 + 추천
│   │   ├── llm.py             # GPT-4o 시장 분석
│   │   └── sentiment.py       # 뉴스 감성 분석
│   ├── models/
│   │   ├── lstm.py            # LSTM 가격 예측 모델
│   │   └── ensemble.py        # 앙상블 (LSTM + 기술 지표)
│   ├── backtest/
│   │   └── engine.py          # 백테스팅 프레임워크
│   ├── utils/
│   │   ├── data.py            # 데이터 전처리 유틸
│   │   └── report.py          # PDF 리포트 생성 (reportlab)
│   └── cli.py                 # CLI 진입점 (maiupbit 커맨드)
├── scripts/                   # MAIBOT exec 래퍼
│   ├── analyze.py
│   ├── monitor.py
│   ├── daily_report.py
│   ├── portfolio.py
│   ├── trade.py
│   └── train_model.py
├── models/                    # 학습된 모델 파일 (.h5 / .keras)
├── tests/
│   └── unit/
│       └── test_indicators.py
├── docs/
│   └── PRD-v2.md
└── pyproject.toml
```

---

## 환경 설정

`.env.example`을 복사해 `.env`를 생성하세요:

```bash
cp .env.example .env
```

```env
# 시세 조회·분석에는 불필요 — 포트폴리오·매매에만 사용
UPBIT_ACCESS_KEY=your_upbit_access_key
UPBIT_SECRET_KEY=your_upbit_secret_key

# GPT-4o 분석에 필요
OPENAI_API_KEY=your_openai_api_key
```

> `.env` 파일은 절대 git에 커밋하지 마세요.

---

## Contributing

1. 이 저장소를 fork 합니다.
2. feature 브랜치를 생성합니다: `git checkout -b feat/your-feature`
3. 변경 후 테스트를 실행합니다:

```bash
pip install -e ".[dev]"
pytest --cov=maiupbit tests/
```

4. PR을 생성합니다. 커버리지가 70% 미만이면 CI가 실패합니다.

코드 스타일: `ruff check . && ruff format .`

---

## License

Apache License 2.0 — [LICENSE](LICENSE) 참고

---

## Newsletter

**AI Quant Letter** — Weekly UPbit crypto quant signals, auto-generated by this engine.

- **Substack**: https://jinilee.substack.com
- **Latest issue**: https://jinilee.substack.com/p/ai-quant-letter-1-weekly-upbit-crypto
- **Auto-generated by**: maiupbit (this repo, Apache 2.0)

Every Monday: Dual Momentum rankings, Multi-Factor rankings, Seasonal filter analysis — all computed by `maiupbit` with zero manual intervention. Free to read, open-source to reproduce.

---

## Links

- **GitHub**: https://github.com/jini92/M.AI.UPbit
- **Issues**: https://github.com/jini92/M.AI.UPbit/issues
- **PyPI**: https://pypi.org/project/maiupbit/
- **Newsletter**: [AI Quant Letter](https://jinilee.substack.com) — Weekly UPbit quant signals
- **Latest Issue**: [AI Quant Letter #1 — Weekly UPbit Crypto Signals](https://jinilee.substack.com/p/ai-quant-letter-1-weekly-upbit-crypto)
- **UPbit Open API**: https://docs.upbit.com/

---

*Powered by [MAIBOT](https://github.com/jini92) · Part of the MAI Universe ecosystem*
