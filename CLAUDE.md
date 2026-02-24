# M.AI.UPbit — Agent Guidelines

## 프로젝트 개요

**maiupbit** — AI 디지털 자산 분석 엔진 (Apache-2.0 OSS, PyPI 패키지).
MAIBOT(OpenClaw) 에이전트에서 직접 호출하여 사용.

- **GitHub**: https://github.com/jini92/M.AI.UPbit
- **로컬**: `C:\TEST\M.AI.UPbit`
- **버전**: v0.1.0
- **Python**: 3.10+

### 아키텍처

```
👤 사용자 → 📱 MAIBOTALKS(앱) → 🦞 MAIBOT(OpenClaw) → 📦 maiupbit(엔진) → 🏦 UPbit
```

- **Streamlit/FastAPI/Next.js 없음** — MAI Universe 기존 인프라 활용
- MAIBOT이 `scripts/*.py`를 exec로 직접 호출
- 결과를 자연어로 해석하여 사용자에게 응답

---

## 프로젝트 구조

```
M.AI.UPbit/
├── maiupbit/                   # 📦 OSS 패키지 (PyPI)
│   ├── __init__.py             # v0.1.0
│   ├── cli.py                  # CLI (analyze, portfolio, trade, recommend)
│   ├── indicators/             # 기술 지표
│   │   ├── trend.py            # SMA, EMA, MACD
│   │   ├── momentum.py         # RSI, Stochastic, momentum_score, average_momentum_signal
│   │   ├── volatility.py       # Bollinger Bands, ATR, noise_ratio
│   │   └── signals.py          # 시그널 종합 (+ATR_14, Noise_20, Momentum_Score)
│   ├── models/                 # ML 모델
│   │   ├── lstm.py             # LSTM 가격 예측
│   │   └── ensemble.py         # 앙상블 (Voting)
│   ├── analysis/               # 분석 엔진
│   │   ├── technical.py        # 기술 분석 + 종목 추천
│   │   ├── llm.py              # LLM 종합 분석 (OpenAI/Ollama 듀얼)
│   │   └── sentiment.py        # 뉴스 감성 분석
│   ├── exchange/               # 거래소 연동
│   │   ├── base.py             # BaseExchange Protocol
│   │   └── upbit.py            # UPbit API (pyupbit 래핑)
│   ├── strategies/             # 퀀트 전략 (강환국 프레임워크)
│   │   ├── base.py             # QuantStrategy, PortfolioStrategy Protocol
│   │   ├── volatility_breakout.py # 변동성 돌파
│   │   ├── momentum.py         # 듀얼 모멘텀
│   │   ├── multi_factor.py     # 다중팩터 랭킹
│   │   ├── allocation.py       # GTAA 자산배분
│   │   ├── seasonal.py         # 시즌/반감기 타이밍
│   │   └── risk.py             # 리스크 관리
│   ├── backtest/               # 백테스팅
│   │   ├── engine.py           # Strategy Protocol + BacktestEngine
│   │   └── portfolio_engine.py # PortfolioBacktestEngine
│   └── utils/                  # 유틸리티
│       ├── data.py             # 데이터 파이프라인
│       └── report.py           # PDF 리포트 생성
├── scripts/                    # 🦞 OpenClaw 연동 스크립트
│   ├── analyze.py              # 코인 분석 (인증 불필요)
│   ├── monitor.py              # 시장 모니터링 (5코인)
│   ├── daily_report.py         # 일일 리포트
│   ├── portfolio.py            # 포트폴리오 조회 (API 키 필요)
│   ├── trade.py                # 매매 실행 (--confirm 필수)
│   ├── train_model.py          # LSTM 모델 학습
│   └── quant.py                # 퀀트 전략 실행 (MAIBOT 연동)
├── tests/                      # 테스트
│   ├── conftest.py
│   └── unit/
│       ├── test_indicators.py  # 지표 단위 테스트 (7 tests)
│       ├── test_quant_indicators.py # 퀀트 지표 테스트 (9 tests)
│       └── test_strategies.py  # 전략 + 포트폴리오 테스트 (32 tests)
├── app.py                      # ⚠️ 레거시 POC (참조용, 수정 금지)
├── pyproject.toml              # 패키지 설정
├── Makefile                    # 개발 명령어
├── docs/PRD-v2.md              # PRD v2.1 아키텍처 문서
└── LICENSE                     # Apache-2.0
```

---

## 개발 명령어

```bash
# 의존성 설치
pip install -e .              # 기본 (indicators, exchange, CLI)
pip install -e ".[ml]"        # + LSTM/TensorFlow
pip install -e ".[all]"       # + dev 도구 (pytest, ruff)

# 테스트
pytest tests/ -v
pytest tests/ -v --cov=maiupbit --cov-report=term-missing  # coverage

# 린트
ruff check maiupbit/ scripts/ tests/

# CLI
python -m maiupbit analyze KRW-BTC --format json
python -m maiupbit recommend --method performance --top 5
python -m maiupbit quant momentum --top 5 --format json
python -m maiupbit quant breakout KRW-BTC --k 0.5
python -m maiupbit quant factor --top 5
python -m maiupbit quant allocate
python -m maiupbit quant season
python -m maiupbit quant backtest momentum --days 365
```

### Makefile 단축

```bash
make install    # pip install -e .
make dev        # pip install -e ".[all]"
make test       # pytest + coverage
make lint       # ruff check
make analyze    # KRW-BTC 분석
make monitor    # 시장 모니터링
make report     # 일일 리포트
make train      # LSTM 학습
```

---

## 환경 설정 (.env)

```env
# 시세 조회/분석은 키 없이도 가능
# 포트폴리오 조회 + 매매 실행 시 필요:
UPBIT_ACCESS_KEY=your_key
UPBIT_SECRET_KEY=your_secret

# LLM 분석 — OpenAI 또는 Ollama 선택
LLM_PROVIDER=ollama              # "openai" (기본) 또는 "ollama"
OPENAI_API_KEY=your_openai_key   # OpenAI 사용 시
OLLAMA_BASE_URL=http://localhost:11434/v1  # Ollama 기본값
OLLAMA_MODEL=qwen2.5:14b         # Ollama 모델 (권장: qwen2.5:14b, qwen3:32b)
```

### Ollama 설정 가이드

```bash
# Ollama 설치 후 모델 다운로드
ollama pull qwen2.5:14b    # 12GB GPU (기본 추천)
ollama pull qwen3:32b      # 24GB GPU (최고 성능)
ollama pull exaone3.5:7.8b # 8GB GPU (한국어 특화)
```

---

## 코드 규칙

- **Type hints** 필수 (모든 함수/메서드)
- **Docstring** 필수 (Google 스타일)
- 최대 줄 길이: 120자
- Streamlit import 금지 (새 코드에서)
- `app.py`는 레거시 참조용 — **수정 금지**
- 외부 API 호출은 테스트에서 반드시 mock

### 매매 안전 규칙 ⚠️

- `trade.py`는 `--confirm` 없이 절대 실행 금지
- MAIBOT이 호출할 때도 미리보기만 보여주고 사용자 확인 후 --confirm
- API 키 없으면 에러 반환 (자동 실패)

---

## MAIBOT 연동 (Phase 3 완료 ✅)

### 크론 스케줄
- **05:30 KST** — 시장 모니터링 (`scripts/monitor.py`) → 이상 시 Discord DM
- **06:30 KST** — 일일 분석 리포트 (`scripts/daily_report.py`) → Obsidian + Discord DM

### 지니님 요청 매핑
| 요청 | 실행 |
|---|---|
| "비트코인 분석해줘" | `python scripts/analyze.py KRW-BTC` |
| "시장 상황 알려줘" | `python scripts/monitor.py` |
| "포트폴리오 보여줘" | `python scripts/portfolio.py` |
| "비트코인 5만원 사줘" | `python scripts/trade.py buy KRW-BTC 50000` (미리보기) |
| "리포트 만들어줘" | `python scripts/daily_report.py` |
| "모멘텀 좋은 코인 알려줘" | `python scripts/quant.py momentum` |
| "비트코인 변동성 돌파 시그널" | `python scripts/quant.py breakout KRW-BTC` |
| "퀀트 랭킹 보여줘" | `python scripts/quant.py factor` |
| "자산배분 추천해줘" | `python scripts/quant.py allocate` |
| "지금 시즌 어때?" | `python scripts/quant.py season` |
| "모멘텀 전략 백테스트 해봐" | `python scripts/quant.py backtest momentum` |

---

## 로드맵

- [x] Phase 1: POC 분석 + PRD v2.1
- [x] Phase 2: maiupbit v0.1.0 모듈화 (41파일, 3,854 LOC)
- [x] Phase 3: MAIBOT 연동 (HEARTBEAT + TOOLS + 크론)
- [x] Phase 4: 테스트 보강 (79.5% coverage) + README + PyPI
- [x] Phase 5: Transformer 모델 + PyPI 배포
- [x] Phase 7: 강환국 퀀트 전략 6종 + PortfolioBacktestEngine (189 tests, 81% cov)
- [ ] Phase 8: 실전 백테스트 검증 + PyPI v0.2.0 + Jupyter 교육

---

## MAI Universe 연결

| 프로젝트 | 역할 |
|---|---|
| **MAIBOTALKS** | 📱 UI (음성/텍스트 대화 → 매매 지시) |
| **MAIBOT** | 🦞 오케스트레이터 (scripts/ 호출 + 결과 해석) |
| **MAITHINK** | 🧠 추론 엔진 공유 |
| **MAITB** | 📝 분석 → 블로그 콘텐츠 |
| **MAISECONDBRAIN** | 📊 시장 지식 → 지식그래프 |

## 참고 링크

- [UPbit Open API](https://docs.upbit.com/)
- [pyupbit GitHub](https://github.com/sharebook-kr/pyupbit)
- [OpenAI API](https://platform.openai.com/docs)
- [PRD v2.1](docs/PRD-v2.md)
