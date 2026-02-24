# M.AI.UPbit — Claude Agent Guidelines

## 프로젝트 개요

**M.AI.UPbit**는 MAIBOT(OpenClaw)에 직접 물려서 구동되는 AI 디지털 자산 트레이딩 에이전트입니다.

- **GitHub**: https://github.com/jini92/M.AI.UPbit
- **언어**: Python 3.12+
- **상태**: v2.1 리팩토링 진행중

### 아키텍처 (v2.1 — OpenClaw 에이전트형)

```
👤 사용자 → 📱 MAIBOTALKS(앱) → 🦞 MAIBOT(OpenClaw) → 📦 maiupbit(엔진) → 🏦 UPbit
```

- **Streamlit/FastAPI/Next.js 없음** — MAI Universe 기존 인프라 활용
- MAIBOT이 `scripts/*.py`를 exec로 직접 호출
- 결과를 자연어로 해석하여 사용자에게 응답

### 핵심 기능
- `maiupbit/` — OSS 분석 엔진 (PyPI 패키지)
- 기술 지표: SMA, EMA, RSI, MACD, Bollinger, Stochastic
- ML: LSTM 가격 예측 (사전 학습 모델)
- LLM: Claude/GPT-4o 종합 분석 (buy/sell/hold)
- 뉴스 감성 분석 (Google RSS + BeautifulSoup)
- UPbit API 매매 실행 (확인 후)
- CLI: `maiupbit analyze KRW-BTC`
- 백테스팅 프레임워크

---

## 기술 스택

| 분류 | 기술 |
|------|------|
| 언어 | Python 3.10+ |
| 웹 서버 | Flask, Flask-CORS |
| 거래소 API | pyupbit (UPbit), pyjwt (JWT 인증) |
| AI / LLM | OpenAI API (GPT) |
| 머신러닝 | TensorFlow, scikit-learn, numpy |
| 데이터 분석 | pandas, pandas_ta |
| 시각화 | matplotlib, plotly, Streamlit |
| 스케줄링 | schedule |
| 웹 스크래핑 | beautifulsoup4, lxml, feedparser |
| 리포트 | reportlab (PDF) |
| 환경 변수 | python-dotenv |
| HTTP | requests |

---

## 아키텍처

```
UPbit API
    │
    ▼
데이터 수집 (pyupbit)
    │  - 실시간 시세, OHLCV
    │  - 주문/잔고 (JWT 인증)
    ▼
데이터 처리 (pandas / pandas_ta)
    │  - 기술적 지표 계산 (RSI, MACD, BB 등)
    │  - 뉴스/RSS 스크래핑
    ▼
AI 분석 (OpenAI API / TensorFlow)
    │  - 시장 상황 분석
    │  - 예측 모델 (ML)
    ▼
출력 / 시각화
    ├── Flask REST API  (app.py)
    ├── Streamlit 대시보드
    ├── matplotlib / plotly 차트
    └── PDF 리포트 (reportlab)
```

---

## 프로젝트 구조

```
M.AI.UPbit/
├── app.py              # Flask 메인 앱 (API 엔드포인트)
├── config.py           # 설정 (DEBUG = False)
├── requirements.txt    # Python 의존성
├── instructions.md     # 프로젝트 지침서
├── .env                # 환경 변수 (git 제외)
├── .env.example        # 환경 변수 예시 (git 포함)
└── docs/               # 문서 폴더
```

---

## 개발 명령어

### 환경 설정

```bash
# 의존성 설치
pip install -r requirements.txt

# 가상환경 사용 (권장)
python -m venv venv
source venv/bin/activate      # macOS/Linux
venv\Scripts\activate         # Windows
pip install -r requirements.txt
```

### 실행

```bash
# Flask API 서버 실행
python app.py

# Streamlit 대시보드 실행
streamlit run dashboard.py

# 스케줄러 실행 (백그라운드 분석)
python scheduler.py
```

### 개발 / 디버깅

```bash
# Flask 개발 모드 (DEBUG)
FLASK_DEBUG=1 python app.py

# 환경 변수 확인
python -c "from dotenv import dotenv_values; print(dotenv_values('.env'))"
```

---

## 환경 설정 (.env)

프로젝트 루트에 `.env` 파일을 생성하세요 (`.gitignore`에 포함 필수):

```env
# UPbit API
UPBIT_ACCESS_KEY=your_upbit_access_key
UPBIT_SECRET_KEY=your_upbit_secret_key

# OpenAI API
OPENAI_API_KEY=your_openai_api_key

# Flask
FLASK_SECRET_KEY=your_flask_secret_key
FLASK_ENV=development

# 기타 설정
LOG_LEVEL=INFO
```

> ⚠️ `.env` 파일은 절대 git에 커밋하지 마세요.

---

## 코드 규칙

### Python 스타일
- **PEP 8** 준수
- **Type hints** 권장 (Python 3.10+)
- 함수/클래스 docstring 작성 권장
- 최대 줄 길이: 120자

### 예시

```python
from typing import Optional
import pandas as pd


def get_ohlcv(ticker: str, interval: str = "day", count: int = 200) -> Optional[pd.DataFrame]:
    """
    UPbit에서 OHLCV 데이터를 조회합니다.

    Args:
        ticker: 종목 코드 (예: "KRW-BTC")
        interval: 봉 단위 ("day", "minute1", "minute60" 등)
        count: 조회할 봉 개수

    Returns:
        OHLCV DataFrame 또는 None (오류 시)
    """
    import pyupbit
    return pyupbit.get_ohlcv(ticker, interval=interval, count=count)
```

### 파일 구조 규칙
- API 엔드포인트: `app.py` 또는 `routes/` 폴더
- 비즈니스 로직: 별도 모듈로 분리
- 설정값: `config.py` 또는 `.env`로 관리 (하드코딩 금지)
- API 키: 반드시 `.env`에서 로드

### 보안
- API 키는 환경 변수로만 관리
- UPbit 주문 기능 사용 시 IP 화이트리스트 확인
- JWT 토큰 만료 시간 준수 (UPbit: 10분)

---

## 주요 라이브러리 사용법

### pyupbit

```python
import pyupbit

# 시세 조회 (인증 불필요)
price = pyupbit.get_current_price("KRW-BTC")
ohlcv = pyupbit.get_ohlcv("KRW-BTC", interval="day", count=30)

# 잔고 조회 (API 키 필요)
upbit = pyupbit.Upbit(access_key, secret_key)
balances = upbit.get_balances()
```

### OpenAI

```python
from openai import OpenAI

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
response = client.chat.completions.create(
    model="gpt-4o",
    messages=[{"role": "user", "content": "BTC 시장 분석..."}]
)
```

---

## 현재 상태 & 로드맵

- **v1 (POC)**: Streamlit 단일 파일 (`app.py`, 800+ LOC) — 레거시, 참조용 보존
- **v2.1 (Production)**: OpenClaw 에이전트형 (`docs/PRD-v2.md`)

### v2.1 마일스톤
- Phase 1: Core 리팩토링 → `maiupbit/` PyPI 패키지 추출 (진행중)
- Phase 2: OpenClaw 통합 → `scripts/` → MAIBOT exec 연결
- Phase 3: Intelligence 고도화 → Transformer + 앙상블 + 교육 노트북 + PyPI 배포

### MAI Universe 연결
- **MAIBOTALKS**: 📱 UI (음성/텍스트)
- **MAIBOT**: 🤖 오케스트레이터 (분석+매매 실행)
- **MAITHINK**: 🧠 추론 엔진 공유
- **MAITB**: 📝 분석 → 블로그 자동 생성
- **MAITOK**: 📹 분석 → TikTok 콘텐츠
- **MAISECONDBRAIN**: 📊 시장 지식 → 지식그래프

## 참고 링크

- [UPbit Open API 문서](https://docs.upbit.com/)
- [pyupbit GitHub](https://github.com/sharebook-kr/pyupbit)
- [OpenAI API 문서](https://platform.openai.com/docs)
- [pandas_ta 문서](https://github.com/twopirllc/pandas-ta)
- [Streamlit 문서](https://docs.streamlit.io/)
- [PRD v2](docs/PRD-v2.md)
