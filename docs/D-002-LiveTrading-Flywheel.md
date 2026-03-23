# D-002 — 라이브 트레이딩 플라이휠 설계

> **문서 유형:** D (Design) — 설계 문서  
> **프로젝트:** M.AI.UPbit  
> **작성일:** 2026-02-25  
> **상태:** Draft → 지니님 확인 대기  
> **작성자:** MAIBOT

---

## Addendum (2026-03-23)

This flywheel remains valid, but the architecture now explicitly distinguishes between:

- **market data accumulation** (canonical candle store), and
- **trade record accumulation** (`trade_journal.json`, performance tracking, Obsidian/Mnemo sync).

The detailed storage architecture is now specified in `D-003-Market-Data-Accumulation-Architecture.md`.

---

## 1. 핵심 컨셉: 데이터 → 지식 → 수익 선순환

```
  ┌─────────────────────────────────────────────────────┐
  │                  🔄 FLYWHEEL                         │
  │                                                      │
  │  ① TRADE (자동매매)                                  │
  │    매일 07:00 분석 → 매매 결정 → 실행                │
  │         │                                            │
  │         ▼                                            │
  │  ② RECORD (기록)                                     │
  │    거래 로그 + 시장 스냅샷 + 분석 근거                │
  │         │                                            │
  │         ▼                                            │
  │  ③ LEARN (Obsidian → Mnemo 지식그래프)               │
  │    거래 노트 → 볼트 → daily_enrich → 그래프 축적     │
  │         │                                            │
  │         ▼                                            │
  │  ④ IMPROVE (지식 기반 분석 강화)                     │
  │    KnowledgeProvider가 과거 매매 패턴 검색           │
  │    "지난달 RSI 30 이하에서 매수했을 때 수익률?"      │
  │    → LLM 컨텍스트에 주입 → 더 나은 분석             │
  │         │                                            │
  │         ▼                                            │
  │  ⑤ PROVE (트랙레코드)                               │
  │    수익률 대시보드 + 성과 리포트 자동 생성           │
  │    → MAIBOTALKS Premium 마케팅 자산                  │
  │         │                                            │
  │         ▼                                            │
  │  ⑥ MONETIZE (수익화)                                │
  │    Premium 구독자: 실전 검증된 AI 매매 시그널        │
  │    → 구독 수익 → 운용 자산 증가 → ① 로 복귀        │
  │                                                      │
  └─────────────────────────────────────────────────────┘
```

## 2. 데이터 흐름 상세

### 2.1 ① TRADE — 자동매매 엔진

```
[매일 07:00 KST 크론]

Step 1: 데이터 수집
  - UPbit API → 가격, 거래량, 호가
  - 기술지표 계산 (RSI, MACD, BB, Stoch, SMA, EMA)

Step 2: 퀀트 전략 분석
  - 시즌 필터 (할빙 사이클)
  - 변동성 돌파 시그널
  - 듀얼 모멘텀 스코어

Step 3: Mnemo 지식 조회 ← ④에서 축적된 지식
  - 과거 유사 시장 상황 검색
  - 이전 매매 결과 패턴 조회
  - 외부 수집 뉴스/분석 컨텍스트

Step 4: LLM 종합 분석
  - Ollama qwen2.5:14b (기본) / GPT-4o (프리미엄)
  - 기술지표 + 퀀트 + 지식 컨텍스트 → 매매 결정
  - 출력: {decision, confidence, reason, risk_params}

Step 5: 매매 실행
  - confidence >= threshold → 실행
  - 포지션 사이징 (Kelly, ATR 기반)
  - 실행 → UPbit API
```

### 2.2 ② RECORD — 구조화된 거래 기록

```python
# trade_journal.json (기존 trade_history.json 확장)
{
  "id": "2026-02-25-001",
  "timestamp": "2026-02-25T07:00:05+09:00",
  "symbol": "KRW-BTT",
  "action": "sell",
  "volume": 11000000,
  "price": 0.000481,
  "total_krw": 5291,
  "fee": 2.64,
  
  # 분석 근거 (핵심!)
  "analysis": {
    "rsi": 38.5,
    "macd_signal": "bullish",
    "stoch_k": 7.5,
    "bb_position": "lower",
    "quant_score": 0.5,
    "llm_decision": "sell",
    "llm_confidence": 0.65,
    "llm_reason": "Stoch 극단적 과매도이나 모멘텀 음수 지속",
    "knowledge_hits": 3,
    "knowledge_summary": "과거 유사 패턴에서 반등 확률 40%"
  },
  
  # 사후 평가 (다음날 기록)
  "outcome": {
    "price_after_24h": null,  # 다음날 채움
    "pnl_percent": null,
    "was_correct": null
  }
}
```

### 2.3 ③ LEARN — Obsidian → Mnemo 지식화

```
[매일 05:00 KST — daily_enrich 크론]

1. trade_journal.json → Obsidian 노트 자동 생성
   경로: 01.PROJECT/16.M.AI.UPbit/trades/2026-02-25.md
   
   내용:
   ---
   tags: [maiupbit, trade, BTT, sell]
   date: 2026-02-25
   symbol: KRW-BTT
   action: sell
   pnl: +2.3%
   ---
   
   ## 매매 기록
   - 매도: BTT 11,000,000개 @ ₩0.000481
   - RSI: 38.5 (과매도 근접)
   - LLM 판단: sell (confidence 65%)
   
   ## 사후 분석
   - 24h 후 가격: ₩0.000475 (-1.2%)
   - 판단 정확도: ✅ 올바른 매도
   
   ## 배운 점
   - Stoch K < 10 구간에서의 매도는 리스크 있음
   - 하지만 모멘텀 음수 + 전체 시장 약세에서는 유효

2. Mnemo daily_enrich가 이 노트를 자동 파싱
   → 그래프 노드: trade_2026-02-25_BTT_sell
   → 엣지: related_to → BTT 분석 노트들
   → 임베딩: 매매 컨텍스트 벡터화

3. 시간이 지나면 축적:
   "BTT를 RSI 30 이하에서 매도한 기록 5건"
   "그 중 3건이 올바른 판단 (60% 정확도)"
   "평균 수익률: +1.8%"
```

### 2.4 ④ IMPROVE — 지식 기반 분석 강화

```
[다음날 07:00 TRADE 시]

KnowledgeProvider.search_for_coin("BTT") 
→ Mnemo가 과거 매매 노트 검색
→ "최근 5건의 BTT 매매에서 RSI < 35일 때 매수하면 3일 내 +2.8% 평균 수익"
→ LLM 컨텍스트에 주입

LLM이 받는 컨텍스트:
[Market Data] RSI=32, MACD=bullish, ...
[Quant Signal] momentum=-0.24, season=bullish
[Knowledge Context from Mnemo SecondBrain]
  - 과거 BTT RSI<35 매수 → 3일 평균 +2.8% (5건)
  - 최근 전체 시장 약세에서 BTT 반등 패턴: 짧은 반등 후 재하락
  - 관련 분석: "chatGPT를 이용한 퀀트 투자 솔루션" (볼트 노트)

→ LLM: "RSI 과매도이나, 과거 데이터에서 반등 지속성이 낮으므로
         소량 매수(10%) 후 추가 하락 시 추가 매수 권고"
```

### 2.5 ⑤ PROVE — 성과 트래킹

```
[매주 월요일 07:00 KST]

자동 생성:
1. Obsidian 주간 리포트
   - 01.PROJECT/16.M.AI.UPbit/reports/2026-W09.md
   - 주간 수익률, 승률, 샤프비율, MDD
   
2. Discord DM 주간 브리핑
   "이번 주: 매매 5건, 승률 60%, 수익률 +1.2%"

3. 성과 대시보드 (Obsidian)
   - _PERFORMANCE_DASHBOARD.md
   - 누적 수익률 차트 (ASCII/Mermaid)
   - 전략별 성과 비교
   - AI 정확도 추이
```

### 2.6 ⑥ MONETIZE — 프리미엄 전환

```
[누적 3개월 트랙레코드 → MAIBOTALKS Premium]

무료 사용자가 보는 것:
  "AI 분석: BTC 매수 추천" (결과만)

프리미엄 사용자가 보는 것:
  "AI 분석: BTC 매수 추천
   - 기술지표: RSI 28 (과매도), MACD 골든크로스
   - 퀀트: 모멘텀 양전환, 시즌 bullish
   - 지식그래프: 과거 유사 패턴 7건 중 5건 상승 (71%)
   - 실전 트랙레코드: 3개월 +12.5%, 샤프비율 1.8
   - 자동 매매 실행 (알림 → 원클릭)"
```

## 3. 구현 모듈

### 3.1 신규 모듈

| 모듈 | 경로 | 역할 |
|------|------|------|
| AutoTrader | `maiupbit/trading/auto_trader.py` | 자동매매 오케스트레이터 |
| TradeJournal | `maiupbit/trading/journal.py` | 구조화된 거래 기록 |
| OutcomeTracker | `maiupbit/trading/outcome.py` | 사후 평가 (24h/48h/7d) |
| ObsidianSync | `maiupbit/integrations/obsidian.py` | 거래→Obsidian 노트 생성 |
| PerformanceTracker | `maiupbit/trading/performance.py` | 수익률/승률/샤프비율 |

### 3.2 스크립트

| 스크립트 | 크론 | 역할 |
|----------|------|------|
| `scripts/auto_trade.py` | 매일 07:00 | 분석→매매→기록 |
| `scripts/evaluate_trades.py` | 매일 07:30 | 전일 매매 사후 평가 |
| `scripts/sync_obsidian.py` | 매일 05:30 | 거래기록→Obsidian 노트 |
| `scripts/weekly_performance.py` | 매주 월 08:00 | 주간 성과 리포트 |

### 3.3 OpenClaw 크론

| 시각 | 작업 | 의존 |
|------|------|------|
| 05:00 | Mnemo daily_enrich (기존) | - |
| 05:30 | sync_obsidian.py | 거래 노트 → 볼트 |
| 06:30 | daily_report.py (기존) | 시장 분석 |
| 07:00 | **auto_trade.py** (신규) | 분석+매매 |
| 07:30 | evaluate_trades.py | 전일 사후 평가 |

## 4. 리스크 관리

| 규칙 | 값 | 설명 |
|------|-----|------|
| 최대 1회 매매 비중 | 전체 자산 10% | ~₩15,000 |
| 일일 최대 매매 횟수 | 2회 (07:00 + 19:00) | 데이터 축적 + 수수료 균형 |
| 최대 손실 한도 | -5%/일 | 초과 시 매매 중단 |
| 최소 confidence | 0.6 | LLM 확신도 60% 미만 → skip |
| 수수료 고려 | 왕복 0.1% | 예상 수익 > 0.3% 이상일 때만 |

## 5. 성공 지표 (KPI)

| 지표 | 1개월 목표 | 3개월 목표 |
|------|-----------|-----------|
| 매매 횟수 | 20+ 건 | 60+ 건 |
| AI 정확도 | 50%+ | 55%+ |
| 누적 수익률 | ±0% (검증) | +5% |
| 지식그래프 노드 | +20 (매매) | +60 |
| LLM 분석 품질 | 기본 | 지식 강화 효과 측정 |
