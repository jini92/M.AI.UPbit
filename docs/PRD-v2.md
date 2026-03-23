# PRD: M.AI.UPbit v2 — OpenClaw 에이전트 트레이딩

> **문서 번호**: D-001
> **작성일**: 2026-02-25
> **상태**: ✅ Phase 8 완료 (Ollama 통합) / Phase 9 계획 보강 (market data persistence)
> **이전 버전**: POC (Streamlit 단일 파일)

---

## 1. 비전 & 전략

### 1.1 한 줄 요약

**OpenClaw AI 에이전트가 디지털 자산을 분석하고 매매하는 시스템** — MAIBOTALKS로 대화하고, OpenClaw가 판단하고, UPbit에서 실행한다.

### 1.2 아키텍처 피벗 (v2.0 → v2.1)

| | v2.0 (이전 설계) | v2.1 (현재) |
|---|---|---|
| **UI** | Next.js 웹 대시보드 | **MAIBOTALKS** (이미 존재하는 모바일 앱) |
| **백엔드** | FastAPI 서버 | **OpenClaw Gateway** (이미 운영 중) |
| **인증** | JWT + OAuth2 신규 개발 | **OpenClaw 기존 인증** 활용 |
| **알림** | 별도 알림 서비스 | **OpenClaw 채널** (Discord/Telegram) |
| **복잡도** | ~80개 파일, 6개 레이어 | **~30개 파일, 3개 레이어** |
| **개발 기간** | 8주 | **3주** |

**피벗 이유**: 이미 MAIBOTALKS(모바일 앱)와 OpenClaw(AI 에이전트 플랫폼)가 있다. 새 프론트엔드와 백엔드를 만드는 건 기존 인프라를 무시하는 낭비. 

### 1.3 기여-수익화 철학

| 축 | 전략 | 구체적 실행 |
|---|---|---|
| **🌱 기여** | 한국 거래소 특화 분석 엔진 오픈소스화 | `maiupbit` PyPI 패키지 (Apache 2.0), Jupyter 교육 노트북, 백테스팅 프레임워크 |
| **💰 수익화** | OpenClaw 스킬 마켓 + 프리미엄 모델 | ClawHub 유료 스킬, 프리미엄 AI 분석 모델, API 접근 |
| **🔄 선순환** | OSS 사용자 → OpenClaw 유저 → 프리미엄 전환 | PyPI 다운로드 → MAIBOTALKS 설치 → 프리미엄 구독 |

### 1.4 MAI Universe 시너지

| 프로젝트 | 연결 |
|---|---|
| **MAIBOTALKS** | 📱 UI — 음성/텍스트로 "비트코인 분석해줘" |
| **MAIBOT** | 🤖 OpenClaw 에이전트 — 분석 실행 + 매매 결정 |
| **MAITHINK** | 🧠 추론 엔진 — 시장 분석 reasoning chain |
| **MAITB** | 📝 분석 리포트 → 블로그 콘텐츠 자동 생성 |
| **MAITOK** | 📹 분석 결과 → TikTok 크립토 콘텐츠 |

---

## 2. 아키텍처

### 2.1 전체 흐름

```
┌──────────────────────────────────────────────────┐
│  👤 사용자                                        │
│  "비트코인 분석해줘" / "이더리움 매수해"           │
└─────────────────┬────────────────────────────────┘
                  │ 음성/텍스트
                  ▼
┌──────────────────────────────────────────────────┐
│  📱 MAIBOTALKS (모바일 앱)                        │
│  OpenClaw 클라이언트 — 이미 존재                   │
│  음성 입력 → STT → 텍스트 명령                     │
└─────────────────┬────────────────────────────────┘
                  │ OpenClaw Protocol
                  ▼
┌──────────────────────────────────────────────────┐
│  🦞 OpenClaw Gateway (MAIBOT)                     │
│  AI 에이전트 — 판단/실행/보고                      │
│                                                   │
│  1. 사용자 의도 파악                               │
│  2. maiupbit 스킬 트리거                           │
│  3. 분석 결과 해석 + 매매 결정                     │
│  4. UPbit API로 주문 실행                          │
│  5. 결과를 사용자에게 음성/텍스트로 보고            │
│                                                   │
│  📊 주기적: 시장 모니터링 → 알림 발송               │
└─────────────────┬────────────────────────────────┘
                  │ Python exec
                  ▼
┌──────────────────────────────────────────────────┐
│  📦 maiupbit (Python 분석 엔진)                   │
│  OSS Core — pip install maiupbit                  │
│                                                   │
│  indicators/ → 기술 지표 계산                      │
│  models/     → LSTM + Transformer 예측             │
│  analysis/   → 기술 분석 + 감성 + LLM 종합         │
│  exchange/   → UPbit API 래퍼 (매매 실행)          │
│  backtest/   → 전략 백테스팅                       │
│  cli.py      → CLI (maiupbit analyze KRW-BTC)     │
└─────────────────┬────────────────────────────────┘
                  │ REST API
                  ▼
┌──────────────────────────────────────────────────┐
│  🏦 UPbit Exchange                                │
│  시세 조회 / 주문 실행 / 잔고 확인                  │
└──────────────────────────────────────────────────┘
```

### 2.2 대화 시나리오

```
사용자 (MAIBOTALKS): "비트코인 지금 어때?"
    ↓
OpenClaw (MAIBOT):
    1. exec: python -m maiupbit analyze KRW-BTC --format json
    2. 결과 파싱 (기술 지표 + ML 예측 + 뉴스 감성)
    3. 자연어로 해석:
       "비트코인 현재 87,450,000원이에요. RSI 72로 과매수 구간 진입 중이고,
        MACD 골든크로스 3일째라 단기 상승 모멘텀은 있지만 조심할 타이밍이에요.
        LSTM 모델은 48시간 내 2% 조정을 예측하고 있어요."
    ↓
사용자: "그럼 0.01 BTC 매도해줘"
    ↓
OpenClaw:
    1. 금액 확인: "0.01 BTC (약 874,500원) 시장가 매도할까요?"
    2. 사용자 확인 후:
       exec: python -m maiupbit trade sell KRW-BTC 0.01 --confirm
    3. "매도 완료! 0.01 BTC를 874,320원에 매도했어요. 수수료 437원 차감."
    ↓
사용자: "내 포트폴리오 보여줘"
    ↓
OpenClaw:
    1. exec: python -m maiupbit portfolio --format json
    2. "현재 포트폴리오:
        💰 KRW: 2,340,000원
        ₿ BTC: 0.05 (4,372,500원)
        Ξ ETH: 1.2 (4,800,000원)
        총 자산: 11,512,500원 (+3.2% 오늘)"
```

### 2.3 OpenClaw 주기적 작업

```
# HEARTBEAT.md에 추가

## 시장 모니터링 (매시간)
- maiupbit로 관심 코인 기술 지표 체크
- 급격한 변동 (±5%) 또는 시그널 전환 시 Discord DM 알림

## 일일 분석 (매일 08:00 KST)
- 포트폴리오 전체 분석 리포트
- 전일 대비 P&L
- AI 종합 매매 추천 (매수/매도/홀드)
- Discord DM + Obsidian 노트 저장

## 모델 재학습 (매일 03:00 KST)
- LSTM 모델 일일 재학습
- 예측 정확도 추적 (방향 정확도)
- 성능 저하 시 알림
```

### 2.4 모듈 구조

```
M.AI.UPbit/
│
├── 📦 maiupbit/                     # OSS Core (pip install maiupbit)
│   ├── __init__.py                  #   v0.1.0, public API exports
│   ├── __main__.py                  #   python -m maiupbit 진입점
│   ├── cli.py                       #   CLI (analyze, portfolio, trade, recommend, train, quant)
│   ├── indicators/                  #   기술 지표 (100% coverage)
│   │   ├── trend.py                 #   SMA, EMA, MACD
│   │   ├── momentum.py              #   RSI, Stochastic, momentum_score, average_momentum_signal
│   │   ├── volatility.py            #   Bollinger Bands, ATR, noise_ratio
│   │   └── signals.py               #   매매 시그널 종합 (+ATR_14, Noise_20, Momentum_Score)
│   ├── strategies/                  #   퀀트 전략 (강환국 프레임워크)
│   │   ├── base.py                  #   QuantStrategy, PortfolioStrategy Protocol
│   │   ├── volatility_breakout.py   #   변동성 돌파 (래리 윌리엄스)
│   │   ├── momentum.py              #   듀얼 모멘텀 (절대+상대+평균)
│   │   ├── multi_factor.py          #   다중팩터 랭킹
│   │   ├── allocation.py            #   GTAA 동적 자산배분
│   │   ├── seasonal.py              #   시즌/반감기 타이밍
│   │   └── risk.py                  #   리스크 관리 (ATR, 켈리, MDD)
│   ├── models/                      #   ML 모델
│   │   ├── lstm.py                  #   TensorFlow LSTM 가격 예측
│   │   ├── transformer.py           #   PyTorch Transformer (Multi-Head Attention)
│   │   └── ensemble.py              #   앙상블 결합 (Voting)
│   ├── analysis/                    #   분석 엔진
│   │   ├── technical.py             #   기술적 분석 종합 + 종목 추천
│   │   ├── sentiment.py             #   뉴스/소셜 감성 분석
│   │   └── llm.py                   #   LLM 종합 판단 (OpenAI/Ollama 듀얼)
│   ├── exchange/                    #   거래소 추상화
│   │   ├── base.py                  #   BaseExchange Protocol
│   │   └── upbit.py                 #   UPbit API (시세 + 매매)
│   ├── backtest/                    #   백테스팅
│   │   ├── engine.py                #   Strategy Protocol + BacktestEngine
│   │   └── portfolio_engine.py      #   PortfolioBacktestEngine (다중 자산)
│   └── utils/                       #   유틸리티
│       ├── data.py                  #   데이터 처리 파이프라인
│       └── report.py                #   PDF 리포트 생성
│
├── 🤖 scripts/                      # OpenClaw 실행 스크립트
│   ├── analyze.py                   #   분석 실행 → JSON 출력
│   ├── trade.py                     #   매매 실행 (--confirm 필수)
│   ├── portfolio.py                 #   포트폴리오 조회
│   ├── monitor.py                   #   시장 모니터링 (HEARTBEAT용)
│   ├── train_model.py               #   모델 재학습
│   ├── daily_report.py              #   일일 분석 리포트 생성
│   └── quant.py                     #   퀀트 전략 실행 (MAIBOT 연동)
│
├── 🧪 tests/                        # pytest (200 collected, 82% coverage)
│   ├── conftest.py                  #   공통 픽스처
│   └── unit/
│       ├── test_indicators.py       #   7 tests
│       ├── test_quant_indicators.py #   9 tests (ATR, noise, momentum)
│       ├── test_strategies.py       #   32 tests (6대 전략 + 포트폴리오)
│       ├── test_exchange.py         #   22 tests
│       ├── test_backtest.py         #   18 tests
│       ├── test_analysis.py         #   37 tests (technical + LLM)
│       ├── test_cli.py              #   14 tests
│       ├── test_sentiment.py        #   17 tests
│       ├── test_utils.py            #   15 tests
│       └── test_models.py           #   12 tests (3 LSTM skipped)
│
├── 📄 docs/
│   ├── README.md                    #   문서 인덱스
│   ├── PRD-v2.md                    #   D-001: 이 문서
│   ├── A-001-POC-Analysis.md        #   A-001: POC 분석
│   ├── I-001-Implementation-Status.md #  I-001: 구현 현황
│   └── T-001-Test-Report.md         #   T-001: 테스트 리포트
│
├── app.py                           #   ⬅️ POC 보존 (레거시, 참조용)
├── pyproject.toml                   #   Poetry (PyPI 배포)
├── Makefile                         #   개발 명령어
├── CLAUDE.md                        #   에이전트 가이드
├── README.md                        #   PyPI README
└── LICENSE                          #   Apache 2.0
```

**v2.0 대비 제거된 것:**
- ❌ `server/` (FastAPI) → OpenClaw이 백엔드
- ❌ `web/` (Next.js) → MAIBOTALKS가 프론트엔드
- ❌ `workers/` (Celery) → OpenClaw HEARTBEAT이 스케줄러
- ❌ `docker/` → OpenClaw 환경에서 실행
- ❌ `alembic/` → SQLite/JSON 충분 (단일 사용자)
- ❌ JWT/OAuth/Rate Limiting → OpenClaw 기존 인증

---

## 3. 기술 스택

| 레이어 | 기술 | 선택 이유 |
|---|---|---|
| **UI** | MAIBOTALKS (React Native/Expo) | 이미 존재, 음성+텍스트 |
| **에이전트** | OpenClaw (MAIBOT) | 이미 운영 중, 멀티채널 |
| **분석 엔진** | Python 3.12+ | ML/데이터 분석 최적 |
| **기술 지표** | pandas + pandas_ta + 자체 구현 | 한국 거래소 특화 |
| **ML** | PyTorch (LSTM + Transformer) | 사전 학습 + 추론 분리 |
| **LLM** | OpenAI GPT-4o + Ollama (qwen2.5:14b 기본) | 듀얼 백엔드, 무료 로컬 분석 |
| **거래소** | pyupbit + ccxt | UPbit 메인 + 확장 가능 |
| **데이터** | SQLite (canonical market data, planned) + JSON (trade logs) | local-first, 단일 사용자, 점진적 마이그레이션 |
| **알림** | OpenClaw 채널 (Discord/Telegram) | 기존 인프라 활용 |
| **패키지** | Poetry + PyPI | OSS 배포 |
| **테스트** | pytest + coverage 70%+ | 품질 보증 |

---

## 4. 기능 티어

### 4.1 Free (OSS) — `pip install maiupbit`

| 기능 | 설명 |
|---|---|
| 기술 지표 라이브러리 | 20+ 지표 (한국 거래소 특화) |
| UPbit 데이터 수집 | OHLCV, 호가, 체결 |
| 기본 분석 | 단일 코인 기술 분석 |
| LSTM 예측 | 기본 가격 예측 모델 |
| 백테스팅 | 전략 성과 검증 |
| CLI | `maiupbit analyze KRW-BTC` |
| Jupyter 노트북 | 교육용 5종 |

### 4.2 Premium (MAIBOTALKS + OpenClaw) — ₩19,900/월

| 기능 | 설명 |
|---|---|
| **음성 트레이딩** | "비트코인 매수해줘" — MAIBOTALKS 음성 명령 |
| **AI 에이전트 매매** | OpenClaw가 분석+판단+실행 (확인 후) |
| **실시간 모니터링** | 매시간 시장 체크 + 급변 알림 |
| **멀티코인 분석** | 무제한 코인 동시 분석 |
| **AI 앙상블** | LSTM + Transformer + LLM 종합 |
| **일일 리포트** | 포트폴리오 분석 + 매매 추천 |
| **자동 매매** | 전략 기반 자동 실행 (Paper + Live) |
| **뉴스 감성** | 실시간 뉴스 분석 + 감성 점수 |

### 4.3 수익 구조

```
MAIBOTALKS 앱 (₩9,900 일회성) ← 이미 존재
    +
M.AI.UPbit Premium 스킬 (₩19,900/월 추가 구독)
    =
AI 트레이딩 에이전트 풀 패키지

또는

ClawHub 스킬 마켓플레이스에서 개별 판매
```

---

## 5. 보안 설계

| 위협 | 대응 |
|---|---|
| **UPbit API 키 유출** | `.env` + OpenClaw 시크릿 관리, 메모리에서만 로드 |
| **무단 매매** | 매매 전 반드시 사용자 확인 ("0.01 BTC 매도할까요?") |
| **과도한 주문** | 일일 한도 설정 (config), 연속 손실 시 자동 정지 |
| **API 키 갱신** | UPbit IP 화이트리스트 + 키 주기적 갱신 알림 |

### ⚠️ 매매 확인 정책 (필수)

```
자동 실행 허용 (확인 없이):
  ✅ 분석 조회
  ✅ 포트폴리오 조회
  ✅ 시세 조회
  ✅ 알림 설정

반드시 사용자 확인 필요:
  🔒 매수/매도 주문 (금액 + 수량 확인)
  🔒 자동 매매 활성화/비활성화
  🔒 API 키 변경
  🔒 손절/익절 라인 변경
```

### 면책 고지

```
⚠️ M.AI.UPbit은 투자 참고 도구이며 투자 조언이 아닙니다.
모든 투자 결정과 그에 따른 손익은 이용자 본인의 책임입니다.
```

---

## 6. 마일스톤

### Phase 1: POC 분석 ✅ (2026-02-25)

- [x] app.py (800+ LOC) 전수 분석 → 22개 함수 v2.1 매핑
- [x] PRD v2.0 작성 → v2.1 아키텍처 피벗 결정
- **문서:** `A-001-POC-Analysis.md`

### Phase 2: 엔진 모듈화 ✅ (2026-02-25)

- [x] 프로젝트 구조 셋업 (pyproject.toml, Makefile)
- [x] `maiupbit/indicators/` — trend, momentum, volatility, signals
- [x] `maiupbit/exchange/upbit.py` — UPbit 래퍼 (시세 + 매매)
- [x] `maiupbit/models/lstm.py` — LSTM 분리 + 사전 학습 모드
- [x] `maiupbit/analysis/` — technical + sentiment + llm
- [x] `maiupbit/utils/` — data + report
- [x] `maiupbit/cli.py` — CLI 진입점 (analyze, portfolio, trade, recommend)
- [x] `tests/unit/` — 7 tests passing
- [x] LICENSE (Apache-2.0)
- **서브에이전트:** 3개 (Sonnet 4.6) 병렬 실행
- **커밋:** `0cd20147`

### Phase 3: MAIBOT 통합 ✅ (2026-02-25)

- [x] `scripts/analyze.py` — 분석 실행 스크립트
- [x] `scripts/trade.py` — 매매 실행 (확인 로직 포함)
- [x] `scripts/portfolio.py` — 포트폴리오 조회
- [x] `scripts/monitor.py` — 시장 모니터링
- [x] `scripts/daily_report.py` — 일일 리포트
- [x] `scripts/train_model.py` — 모델 재학습
- [x] MAIBOT HEARTBEAT.md 업데이트 (05:30 모니터링 + 06:30 리포트)
- [x] MAIBOT TOOLS.md 업데이트 (요청 패턴 매핑 + 안전 규칙)
- [x] 풀 플로우 테스트 (analyze + monitor + trade 안전차단)
- **커밋:** `9055ce785` (MAIBOT)

### Phase 4: 테스트+문서+크론 ✅ (2026-02-25)

- [x] OpenClaw 크론 등록 (시장 모니터링 + 일일 분석 리포트)
- [x] 136 tests, coverage **79.5%** (목표 70% 초과)
- [x] README.md PyPI 수준 리라이트
- [x] CLAUDE.md v0.1.0 반영
- **커밋:** `4ec78ef4`, `fd54cec9`

### Phase 5: ML 고도화 + PyPI 배포 ✅ (2026-02-25)

- [x] UPbit API 키 설정 + 포트폴리오 연동 확인
- [x] PyTorch Transformer 모델 (Multi-Head Self-Attention)
- [x] 앙상블 결합 (LSTM + Transformer)
- [x] CLI train 서브커맨드 추가
- [x] 148 passed, 3 skipped, coverage **83.78%**
- [x] PyPI 정식 배포: https://pypi.org/project/maiupbit/0.1.0/
- **커밋:** `d2b59d1f`, `e6e191bd`

### Phase 7: 퀀트 전략 통합 ✅ (2026-02-25)

- [x] 강환국 퀀트 투자 프레임워크 6대 전략 구현
  - 변동성 돌파 (래리 윌리엄스 + 노이즈/MA 필터)
  - 듀얼 모멘텀 (절대+상대+평균모멘텀)
  - 다중팩터 랭킹 (모멘텀+퀄리티+변동성+성과)
  - GTAA 동적 자산배분 (모멘텀+SMA 필터)
  - 시즌/반감기 타이밍 (10-4월 강세, 5-9월 약세)
  - 리스크 관리 (ATR 포지션사이징, 켈리 공식, MDD 디레버리징)
- [x] QuantStrategy + PortfolioStrategy Protocol 프레임워크
- [x] PortfolioBacktestEngine (다중 자산 리밸런싱 시뮬레이션)
- [x] 퀀트 지표: ATR, noise_ratio, momentum_score, average_momentum_signal
- [x] CLI `quant` 서브커맨드 6종
- [x] MAIBOT 연동 스크립트 (`scripts/quant.py`)
- [x] 테스트: 189 passed, 3 skipped, coverage 81%
- [x] 신규 12파일, 수정 6파일

### Phase 8: Ollama 통합 ✅ 완료

- [x] LLMAnalyzer OpenAI/Ollama 듀얼 백엔드 리팩토링
- [x] Ollama 모델 선정 리서치 (Qwen3-32B, Qwen2.5-14B, EXAONE 3.5-7.8B)
- [x] LLM 테스트 8개 추가 → llm.py 커버리지 39% → 98%
- [x] 환경변수 기반 프로바이더 전환 (LLM_PROVIDER, OLLAMA_BASE_URL, OLLAMA_MODEL)
- [x] 마크다운 코드블록 JSON 파싱 폴백
- [x] 테스트: 197 passed, 3 skipped, coverage 82%

### Phase 9: 실전 운영 + PyPI v0.2.0 (예정)

- [ ] Market data persistence foundation (SQLite canonical store + export layer)
- [ ] Quant/report/auto-trade read path integration via local-first candle access
- [ ] 퀀트 전략 실전 백테스트 검증 (BTC/ETH 1년)
- [ ] Transformer 모델 실제 학습 (BTC 90일 데이터)
- [ ] HEARTBEAT 주간 모델 재학습 크론 추가
- [ ] PyPI v0.2.0 배포 (퀀트 전략 + Ollama 포함)
- [ ] 교육 노트북 5종
- [ ] ClawHub 스킬 등록

---

## 7. POC → v2 코드 매핑

| POC 함수 (app.py) | v2 위치 |
|---|---|
| `fetch_data()` | `maiupbit/exchange/upbit.py` → `UPbitExchange.get_ohlcv()` |
| `add_indicators()` | `maiupbit/indicators/trend.py`, `momentum.py`, `volatility.py` |
| `generate_macd_signal()` | `maiupbit/indicators/signals.py` |
| `add_signals()` | `maiupbit/indicators/signals.py` |
| `prepare_data()` | `maiupbit/utils/data.py` |
| `train_lstm()` | `maiupbit/models/lstm.py` → `LSTMPredictor.train()` |
| `predict_prices()` | `maiupbit/models/lstm.py` → `LSTMPredictor.predict()` |
| `analyze_data_with_gpt4()` | `maiupbit/analysis/llm.py` → `LLMAnalyzer.analyze()` (OpenAI/Ollama 듀얼) |
| `get_coin_news()` | `maiupbit/analysis/sentiment.py` → `SentimentAnalyzer.get_news()` |
| `fetch_portfolio_data()` | `maiupbit/exchange/upbit.py` → `UPbitExchange.get_portfolio()` |
| `execute_buy/sell()` | `maiupbit/exchange/upbit.py` → `UPbitExchange.buy/sell()` |
| `save_trade_history()` | `maiupbit/exchange/upbit.py` → 내장 기록 |
| `generate_report()` | `maiupbit/utils/report.py` → `ReportGenerator` |
| `recommend_symbols*()` | `maiupbit/analysis/technical.py` → `TechnicalAnalyzer.recommend()` |
| `get_current_status()` | `maiupbit/exchange/upbit.py` → `UPbitExchange.get_status()` |
| `get_market_info()` | `maiupbit/exchange/upbit.py` → `UPbitExchange.get_markets()` |
| `display_dashboard()` | ❌ 제거 (MAIBOTALKS UI 대체) |
| `set_environment_variables()` | ❌ 제거 (.env + OpenClaw config 대체) |
| `select_symbols()` | ❌ 제거 (음성/텍스트 명령으로 대체) |
| `main()` | ❌ 제거 (OpenClaw 에이전트 흐름으로 대체) |
| Streamlit 전체 | ❌ 제거 |

---

## 8. 성공 지표

| 지표 | 1개월 | 3개월 | 6개월 |
|---|---|---|---|
| PyPI 다운로드 | 50 | 200 | 500 |
| GitHub Stars | 10 | 50 | 200 |
| ML 방향 정확도 | 55% | 58% | 62% |
| 일일 분석 리포트 발행 | ✅ | ✅ | ✅ |
| MAIBOTALKS 트레이딩 명령 성공률 | 90% | 95% | 98% |
| 포트폴리오 P&L 추적 | ✅ | ✅ | ✅ |

---

_Last updated: 2026-03-23 — Phase 9 planning updated (market data persistence)_
_Author: MAIBOT (MAI Universe)_
