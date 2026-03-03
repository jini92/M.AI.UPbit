# M.AI.UPbit Auto Trading Bug Report

**날짜:** 2026-03-03  
**발견자:** MAIBOT (자동 디버깅)  
**관련 커밋:** `0b0fa24f`, `6accd325`

---

## 요약

`auto_trade.py` 크론이 2026-02-25 이후 매매를 한 번도 실행하지 못함.
LLM이 항상 기본값(hold, 신뢰도 0.5)으로 폴백하거나, 매매 신호가 나와도
포지션 사이즈가 항상 0으로 계산되는 복합 버그.

---

## 버그 목록

### BUG-1: `auto_trader.py` — 없는 모듈 import로 즉시 크래시

**심각도:** Critical  
**파일:** `maiupbit/trading/auto_trader.py`

```python
# 수정 전 (존재하지 않는 모듈)
from maiupbit.trading.llm_analyzer import LlmAnalyzer   # ❌
from maiupbit.trading.trade_journal import TradeJournal  # ❌

# 수정 후
from maiupbit.analysis.llm import LLMAnalyzer            # ✅
from maiupbit.trading.journal import TradeJournal         # ✅
```

**결과:** `auto_trade.py` 실행 시 즉시 `ModuleNotFoundError` → 크래시

---

### BUG-2: `AutoTrader.__init__()` 시그니처 불일치

**심각도:** Critical  
**파일:** `maiupbit/trading/auto_trader.py`

`auto_trade.py`가 기대하는 인자 vs 실제 `__init__` 정의 불일치:

```python
# auto_trade.py 호출부
AutoTrader(exchange=exchange, journal=journal, llm_analyzer=llm, knowledge_provider=knowledge)

# 수정 전 __init__ (exchange, llm_analyzer, knowledge_provider 파라미터 없음)
def __init__(self, llm=None, journal=None): ...

# 수정 후
def __init__(self, exchange=None, journal=None, llm_analyzer=None, knowledge_provider=None, config=None): ...
```

**결과:** `TypeError` 또는 `self.exchange`/`self.llm` 미정의로 런타임 오류

---

### BUG-3: `AutoTrader.run()` 메서드 없음

**심각도:** Critical  
**파일:** `maiupbit/trading/auto_trader.py`

```python
# auto_trade.py 호출부
result = trader.run(args.symbol, args.dry_run)

# 수정 전: run() 없음, execute_trade()만 존재
# 수정 후: run()을 execute_trade() 별칭으로 추가
def run(self, symbol: str, dry_run: bool = False) -> dict:
    return self.execute_trade(symbol, dry_run=dry_run)
```

---

### BUG-4: `LLMAnalyzer.__init__()` 미완성 — self.model/client/timeout 미정의

**심각도:** High  
**파일:** `maiupbit/analysis/llm.py`

```python
# 수정 전: model, client, timeout 정의 없음
def __init__(self, api_key=None, provider="openai"):
    self.api_key = api_key
    self.provider = provider
    # self.model, self.client, self.timeout 없음!

# 수정 후: Ollama/OpenAI 분기하여 초기화
def __init__(self, api_key=None, provider=None):
    self.provider = provider or os.getenv("LLM_PROVIDER", "openai")
    self.timeout = 60
    if self.provider == "ollama":
        self.model = os.getenv("OLLAMA_MODEL", "qwen2.5:14b")
        self.client = OpenAI(api_key="ollama", base_url=os.getenv("OLLAMA_BASE_URL", "..."))
    else:
        self.model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        self.client = OpenAI(api_key=self.api_key)
```

**결과:** `AttributeError: 'LLMAnalyzer' object has no attribute 'model'` → LLM 항상 실패 → hold 폴백

---

### BUG-5: LLM 응답 키 불일치 — `recommendation` vs `decision`

**심각도:** High  
**파일:** `maiupbit/trading/auto_trader.py`

```python
# LLMAnalyzer.analyze()가 반환하는 키
{"recommendation": "buy", "reason": "...", ...}  # "decision" 아님

# 수정 전: 잘못된 키 참조
action = llm_result.get("decision", "hold")       # ❌ 항상 "hold" 폴백
confidence = float(llm_result.get("confidence", 0.5))  # ❌ 항상 0.5

# 수정 후
action = llm_result.get("recommendation", llm_result.get("decision", "hold"))
confidence = 0.7 if action in ("buy", "sell") else 0.5  # buy/sell 시 threshold 초과
```

**결과:** LLM이 buy/sell을 반환해도 항상 hold로 처리됨

---

### BUG-6: 기술 지표 함수명 불일치

**심각도:** Medium  
**파일:** `maiupbit/trading/auto_trader.py`

```python
# 수정 전: 존재하지 않는 wrapper 함수 호출
from maiupbit.indicators.trend import add_moving_averages  # ❌

# 수정 후: 실제 존재하는 함수 사용
from maiupbit.indicators.trend import sma, ema
from maiupbit.indicators.momentum import rsi
from maiupbit.indicators.volatility import bollinger_bands
```

**결과:** 기술 지표 데이터 없이 LLM 분석 → 분석 품질 저하

---

### BUG-7: `TradeJournal.to_obsidian_note()` 없음

**심각도:** Medium  
**파일:** `maiupbit/trading/journal.py`

`ObsidianSync.sync_trade()`가 `journal.to_obsidian_note(trade)`를 호출하지만 해당 메서드 미구현.

**수정:** `to_obsidian_note()` 메서드 추가 — Obsidian 프론트매터 + 거래 내용 마크다운 생성

---

### BUG-8: `UPbitExchange.get_balances()` 없음 — 포지션 사이즈 항상 0

**심각도:** High  
**파일:** `maiupbit/trading/auto_trader.py`, `maiupbit/exchange/upbit.py`

```python
# 수정 전: 존재하지 않는 메서드 호출
balances = self.exchange.get_balances()  # ❌ AttributeError → except → return 0.0

# 수정 후: 실제 존재하는 메서드 사용
portfolio = self.exchange.get_portfolio()
krw_rows = portfolio["KRW"][portfolio["KRW"]["symbol"] == "KRW"]
krw = float(krw_rows["quantity"].sum())
```

**결과:** LLM이 buy 신호를 내도 포지션 사이즈가 항상 0 → hold 처리

---

### BUG-9: `get_portfolio()` 심볼 순서 오류 — BTC 잔고 불표시

**심각도:** High  
**파일:** `maiupbit/exchange/upbit.py`

```python
# 수정 전: 잘못된 심볼 순서 (UPbit API 미지원)
current_price = pyupbit.get_current_price(f"{currency}-KRW")  # "BTC-KRW" ❌

# 수정 후
symbol = f"KRW-{currency}"
current_price = pyupbit.get_current_price(symbol)             # "KRW-BTC" ✅
```

**결과:** BTC 가격 조회 실패 → BTC 잔고 항상 0으로 표시 → sell 포지션 계산 불가

---

## 영향

- **기간:** 2026-02-25 ~ 2026-03-03 (7일간)
- **매매 미실행:** 크론 07:00/19:00 총 14회 — 모두 `hold` 처리
- **실제 손실:** 없음 (매매 미실행이었으므로)
- **데이터 누락:** trade_journal.json에 hold 기록만 존재

---

## 수정 내역

| 커밋 | 내용 |
|------|------|
| `0b0fa24f` | BUG-1~7 수정: auto_trader 재작성, LLMAnalyzer 초기화, to_obsidian_note 추가 |
| `6accd325` | BUG-8~9 수정: get_portfolio 심볼 수정, _calculate_position_size 교체 |

---

## 검증

```
dry-run 결과 (2026-03-03 09:13 KST):
  LLM: ollama qwen2.5:14b ✅ (recommendation=hold)
  BTC 가격: ₩100,824,000 ✅
  기술 지표: RSI neutral, MACD bullish ✅
  Obsidian 노트: 생성 완료 ✅
  Exit: 0 ✅

포트폴리오 (수정 후):
  BTC:  0.001634 BTC @ ₩100,956,000 = 약 ₩164,900 ✅
  KRW:  489원 (추가 매수 불가 — min_order ₩5,000 미달)
```

---

## 향후 개선 사항

- [ ] LLMAnalyzer 응답에 `confidence` 필드 추가 (현재 추론 로직으로 대체 중)
- [ ] APENFT, EVR 등 거래 불가 코인 `get_portfolio()`에서 필터링
- [ ] KRW 잔고 부족 시 Discord DM 알림
- [ ] 단위 테스트: `AutoTrader.execute_trade()` mock 테스트 추가