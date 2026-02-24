# A-001: POC 분석 — app.py Streamlit 모놀리스

> **문서 번호**: A-001
> **작성일**: 2026-02-25
> **상태**: ✅ 완료
> **입력**: `app.py` (800+ LOC Streamlit 단일 파일)
> **출력**: 아키텍처 피벗 결정 (v2.0 → v2.1)

---

## 1. POC 개요

| 항목 | 내용 |
|---|---|
| 파일 | `app.py` (800+ LOC) |
| 프레임워크 | Streamlit |
| 시작일 | 2024 |
| 커밋 수 | 36 (Initial commit ~ `403ad17d`) |
| 주요 기능 | UPbit OHLCV 수집, 기술 지표, LSTM 예측, GPT-4o 분석, 매수/매도, 포트폴리오, PDF 리포트 |

## 2. 기존 함수 분석

### 데이터 수집 (Exchange)

| 함수 | LOC | 역할 | v2.1 매핑 |
|---|---|---|---|
| `fetch_data()` | ~20 | pyupbit로 OHLCV 수집 | `exchange/upbit.py → get_ohlcv()` |
| `fetch_portfolio_data()` | ~30 | 잔고 조회 + 현재가 | `exchange/upbit.py → get_portfolio()` |
| `get_market_info()` | ~10 | 마켓 목록 | `exchange/upbit.py → get_markets()` |
| `get_current_status()` | ~15 | 현재가 + 변동률 | `exchange/upbit.py → get_ticker()` |
| `execute_buy()` | ~15 | 시장가 매수 | `exchange/upbit.py → buy()` |
| `execute_sell()` | ~15 | 시장가 매도 | `exchange/upbit.py → sell()` |

### 기술 지표 (Indicators)

| 함수 | LOC | 역할 | v2.1 매핑 |
|---|---|---|---|
| `add_indicators()` | ~40 | SMA/EMA/RSI/MACD/BB 일괄 계산 | `indicators/trend.py`, `momentum.py`, `volatility.py` |
| `generate_macd_signal()` | ~10 | MACD 매매 시그널 | `indicators/signals.py` |
| `add_signals()` | ~20 | RSI/BB/SMA/MACD 종합 시그널 | `indicators/signals.py` |

### ML 모델 (Models)

| 함수 | LOC | 역할 | v2.1 매핑 |
|---|---|---|---|
| `prepare_data()` | ~30 | 스케일링 + 시퀀스 생성 | `utils/data.py` |
| `train_lstm()` | ~40 | Keras LSTM 학습 | `models/lstm.py → LSTMPredictor` |
| `predict_prices()` | ~25 | 가격 예측 | `models/lstm.py → predict()` |

### 분석 (Analysis)

| 함수 | LOC | 역할 | v2.1 매핑 |
|---|---|---|---|
| `analyze_data_with_gpt4()` | ~60 | GPT-4o 종합 분석 | `analysis/llm.py → LLMAnalyzer` |
| `get_coin_news()` | ~20 | Naver 뉴스 수집 | `analysis/sentiment.py → SentimentAnalyzer` |
| `recommend_symbols*()` | ~40 | 종목 추천 | `analysis/technical.py → recommend()` |

### UI/리포트 (제거됨)

| 함수 | LOC | 역할 | v2.1 |
|---|---|---|---|
| `display_dashboard()` | ~100 | Streamlit 대시보드 | ❌ MAIBOTALKS 대체 |
| `generate_report()` | ~50 | PDF 리포트 | `utils/report.py` |
| `select_symbols()` | ~20 | Streamlit 셀렉터 | ❌ 음성/텍스트 명령 대체 |
| `set_environment_variables()` | ~10 | 환경변수 UI | ❌ .env + OpenClaw 대체 |
| `main()` | ~80 | Streamlit 진입점 | ❌ CLI/에이전트 대체 |

## 3. 문제점 분석

### 3.1 아키텍처 문제

- **모놀리스**: 800+ LOC 단일 파일, 관심사 분리 없음
- **Streamlit 종속**: UI/로직/데이터 뒤섞임, 헤드리스 실행 불가
- **테스트 불가**: 함수 간 강결합, 모킹 어려움
- **재사용 불가**: 다른 프로젝트에서 지표/모델 임포트 불가

### 3.2 코드 품질

- **타입 힌트 부재**: 함수 시그니처에 타입 없음
- **에러 처리 미흡**: try-except 없이 API 호출
- **하드코딩**: API 키, 모델 파라미터, 마켓 목록이 코드에 박힘
- **테스트 0건**: 단위/통합 테스트 없음

### 3.3 기능 갭

- **Transformer 모델 부재**: LSTM 단일 모델
- **백테스팅 미구현**: 전략 검증 수단 없음
- **감성 분석 미흡**: 뉴스 수집만, 분석 없음
- **포트폴리오 추적**: 이력 저장 없음

## 4. 피벗 결정

### v2.0 설계 (폐기)

```
Next.js → FastAPI → Celery → PostgreSQL → Redis → Docker
```

- 예상 80개 파일, 8주 소요
- MAIBOTALKS, OpenClaw과 중복 인프라

### v2.1 설계 (채택)

```
MAIBOTALKS(UI) → OpenClaw(에이전트) → maiupbit(엔진) → UPbit
```

- 30개 파일, 3주 소요
- 기존 인프라 100% 활용
- **80% 코드 감소**

### 피벗 근거

1. **MAIBOTALKS 이미 존재** — 음성/텍스트 UI, 모바일 앱, 인증 완비
2. **OpenClaw 이미 운영** — AI 에이전트, 크론, 멀티채널 알림
3. **중복 인프라 낭비** — 같은 기능을 다시 만드는 것은 비효율
4. **OSS + Premium 모델** — PyPI 코어 + MAIBOTALKS 프리미엄 조합

---

_Created: 2026-02-25_
_Author: MAIBOT_
