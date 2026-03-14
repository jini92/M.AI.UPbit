# D011 — Newsletter Automation Pipeline Plan

**문서 ID**: D011
**작성일**: 2026-03-09
**상태**: 설계 완료 / 구현 예정
**목표**: 매주 월요일 07:00 KST 자동 발행

---

## 1. 개요

Substack 뉴스레터(AI Quant Letter)를 n8n 클라우드 워크플로를 통해 완전 자동화하는 파이프라인.
`maiupbit` 퀀트 엔진이 생성한 데이터를 HTML 포스트로 변환 후 Substack에 자동 발행한다.

| 항목 | 내용 |
|------|------|
| n8n 인스턴스 | https://mai-n8n.app.n8n.cloud |
| 발행 스케줄 | 매주 월요일 00:00 UTC (= 09:00 KST → 07:00 KST 타겟으로 조정 예정) |
| 대상 채널 | Substack — https://jinilee.substack.com |
| 데이터 소스 | `scripts/ci_weekly_report.py` |

---

## 2. 파이프라인 흐름

```
┌─────────────────────────────────────────────────────────────┐
│                    n8n Cloud Workflow                        │
│                                                             │
│  1. Schedule Trigger                                        │
│     └─ 매주 월요일 22:00 UTC (일요일 = 월요일 07:00 KST)       │
│            │                                                │
│  2. Execute Command Node                                    │
│     └─ python scripts/ci_weekly_report.py --format json    │
│            │                                                │
│  3. Parse JSON                                              │
│     └─ momentum_top5, factor_top5, season, signal 추출      │
│            │                                                │
│  4. Build HTML                                              │
│     └─ Function Node → Substack 포스트 HTML 생성             │
│            │                                                │
│  5. Substack API Call                                       │
│     └─ POST https://substack.com/api/v1/posts              │
│            │                                                │
│  6. Notify (선택)                                            │
│     └─ Discord DM → 발행 성공/실패 알림                       │
└─────────────────────────────────────────────────────────────┘
```

---

## 3. 각 단계 상세

### 3.1 Schedule Trigger

```json
{
  "rule": {
    "interval": [
      {
        "field": "cronExpression",
        "expression": "0 22 * * 0"
      }
    ]
  }
}
```

> 일요일 22:00 UTC = 월요일 07:00 KST

### 3.2 Execute Command Node

```bash
cd /path/to/M.AI.UPbit && python scripts/ci_weekly_report.py --format json
```

**ci_weekly_report.py 출력 예시**:
```json
{
  "date": "2026-03-09",
  "season": {
    "season": "Bullish",
    "month": 3,
    "halving_cycle": "mid_cycle",
    "day_post_halving": 689,
    "multiplier": 1.2
  },
  "momentum_top5": [
    {"rank": 1, "coin": "DOT", "score": -0.068},
    {"rank": 2, "coin": "BTC", "score": -0.116},
    {"rank": 3, "coin": "AVAX", "score": -0.153},
    {"rank": 4, "coin": "LINK", "score": -0.154},
    {"rank": 5, "coin": "ETH", "score": -0.158}
  ],
  "factor_top5": [
    {"rank": 1, "coin": "BTC", "score": 0.563},
    {"rank": 2, "coin": "AVAX", "score": 0.386},
    {"rank": 3, "coin": "DOT", "score": 0.155},
    {"rank": 4, "coin": "LINK", "score": 0.066},
    {"rank": 5, "coin": "ETH", "score": 0.035}
  ],
  "signal": "HOLD_CASH"
}
```

### 3.3 Build HTML (Function Node)

n8n Function Node에서 JSON → Substack HTML 변환:

```javascript
const data = $input.first().json;
const date = data.date;
const season = data.season;
const momentum = data.momentum_top5;
const factor = data.factor_top5;
const signal = data.signal;

const medalMap = { 1: '🥇', 2: '🥈', 3: '🥉' };

function momentumRows(list) {
  return list.map(r =>
    `<tr><td>${medalMap[r.rank] || r.rank}</td><td><strong>${r.coin}</strong></td><td>${r.score.toFixed(3)}</td></tr>`
  ).join('');
}

function factorRows(list) {
  return list.map(r =>
    `<tr><td>${r.rank}</td><td><strong>${r.coin}</strong></td><td>${r.score.toFixed(3)}</td></tr>`
  ).join('');
}

const signalColor = signal === 'HOLD_CASH' ? '#e74c3c' : '#27ae60';
const signalLabel = signal === 'HOLD_CASH' ? 'HOLD CASH' : 'INVEST';

const html = `
<h2>📅 Market Season</h2>
<table>
  <tr><th>Metric</th><th>Status</th></tr>
  <tr><td>Season</td><td>🟢 ${season.season} (Month ${season.month})</td></tr>
  <tr><td>Halving Cycle</td><td>${season.halving_cycle} (Day ${season.day_post_halving} post-halving)</td></tr>
  <tr><td>Multiplier</td><td>${season.multiplier}×</td></tr>
</table>

<h2>🏆 Dual Momentum TOP 5</h2>
<table>
  <tr><th>Rank</th><th>Coin</th><th>Score</th></tr>
  ${momentumRows(momentum)}
</table>
<p style="color:${signalColor}"><strong>Signal: ${signalLabel}</strong></p>

<h2>📊 Multi-Factor TOP 5</h2>
<table>
  <tr><th>Rank</th><th>Coin</th><th>Score</th></tr>
  ${factorRows(factor)}
</table>

<hr>
<p><em>⚠️ For informational purposes only, not investment advice</em><br>
<em>Open source (Apache 2.0): <a href="https://github.com/jini92/M.AI.UPbit">github.com/jini92/M.AI.UPbit</a></em></p>
`;

return [{ json: { title: `AI Quant Letter — ${date}`, body_html: html } }];
```

### 3.4 Substack API Call (HTTP Request Node)

Substack는 공식 공개 API를 제공하지 않으므로 **비공식 내부 API**를 활용한다.

```
Method: POST
URL: https://substack.com/api/v1/posts
Headers:
  Content-Type: application/json
  Cookie: substack.sid=<세션_쿠키>
Body (JSON):
{
  "type": "newsletter",
  "title": "{{ $json.title }}",
  "body_html": "{{ $json.body_html }}",
  "audience": "everyone",
  "draft": false
}
```

> **세션 쿠키 관리** — 아래 4절 참고

### 3.5 Discord 알림 (선택)

발행 성공/실패 결과를 Discord DM으로 수신:

```
성공: ✅ AI Quant Letter 발행 완료 — https://jinilee.substack.com/p/...
실패: ❌ 뉴스레터 발행 실패 — 수동 확인 필요 (Error: {error_message})
```

---

## 4. Substack 세션 쿠키 관리

### 현황

| 항목 | 상태 |
|------|------|
| 세션 쿠키 (`substack.sid`) | 확보 완료 (2026-03-09) |
| 유효 기간 | 약 30일 (Substack 정책에 따라 변동) |
| 갱신 방법 | 수동 로그인 후 브라우저 개발자 도구에서 복사 |

### 쿠키 갱신 절차

1. 브라우저에서 https://substack.com 로그인
2. 개발자 도구 (F12) → Application → Cookies → `substack.com`
3. `substack.sid` 값 복사
4. n8n → Credentials → HTTP Header Auth 또는 Custom Auth → Cookie 값 업데이트

### 갱신 주기

- **권장**: 월 1회 정기 갱신 (매월 1일)
- **트리거**: 발행 실패 Discord 알림 수신 시 즉시 갱신
- **장기 계획**: Substack이 공식 API를 제공할 경우 OAuth 방식으로 전환

---

## 5. GitHub Actions 연동

기존 `.github/workflows/weekly-report.yml`이 이미 존재하며, n8n과의 역할 분리:

| 도구 | 역할 |
|------|------|
| **GitHub Actions** | `ci_weekly_report.py` 실행 → JSON 산출물 생성 → Artifact 저장 |
| **n8n** | GitHub Actions Artifact 다운로드 → HTML 변환 → Substack 발행 |

### 연동 방안 (선택 A — n8n이 직접 실행)

서버에 SSH 접근이 가능한 경우: n8n Execute Command Node가 직접 Python 스크립트 실행.

### 연동 방안 (선택 B — GitHub Actions → n8n Webhook)

```yaml
# .github/workflows/weekly-report.yml 추가 step 예시
- name: Trigger n8n webhook
  run: |
    curl -X POST ${{ secrets.N8N_WEBHOOK_URL }} \
      -H "Content-Type: application/json" \
      -d @report_output.json
```

n8n Webhook Trigger → 이후 HTML 변환 + Substack 발행 단계 실행.

---

## 6. 구현 로드맵

| 단계 | 작업 | 상태 |
|------|------|------|
| 1 | Substack 채널 개설 + 첫 수동 발행 | ✅ 완료 (2026-03-09) |
| 2 | `ci_weekly_report.py` JSON 출력 확인 | 진행 중 |
| 3 | n8n HTML Builder Function Node 작성 | 예정 |
| 4 | n8n Substack API Node 연결 + 테스트 | 예정 |
| 5 | Schedule Trigger 활성화 + 1회 자동 발행 검증 | 예정 |
| 6 | Discord 알림 Node 추가 | 예정 |
| 7 | Stripe 연동 후 유료 tier 활성화 | Wise 계좌 발급 후 진행 |

---

## 7. 관련 문서

| 문서 | 링크 |
|------|------|
| Substack 채널 설정 | [D010-Substack-Newsletter-Channel.md](D010-Substack-Newsletter-Channel.md) |
| 블로그 운영 가이드 | [../blog/README.md](../blog/README.md) |
| 콘텐츠 채널 전략 | [content-strategy.md](content-strategy.md) |
| PRD v2.1 | [PRD-v2.md](PRD-v2.md) |
