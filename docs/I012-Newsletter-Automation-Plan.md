# I012 — Newsletter Automation Plan

**Document type**: Implementation Record / Architecture Plan
**Date**: 2026-03-09
**Status**: IMPLEMENTED (deployed 2026-03-09)
**Author**: Jini Lee

---

## Overview

This document describes the planned n8n automation pipeline that will replace the manual newsletter publication process with a fully automated weekly workflow. Once deployed, every Monday at 07:00 KST the pipeline will generate quant signals, format them as a Substack post, publish via API, and notify via Discord — with zero manual intervention.

---

## 1. Infrastructure

| Component | URL / Reference | Status |
|-----------|----------------|--------|
| **n8n Cloud** | https://mai-n8n.app.n8n.cloud | ✅ Active |
| **Substack Publication** | https://jinilee.substack.com | ✅ Active |
| **GitHub Actions** | `.github/workflows/weekly-report.yml` | ✅ Existing |
| **maiupbit** | PyPI / `scripts/quant.py` | ✅ Active |

---

## 2. Pipeline Architecture

### Schedule

| Setting | Value |
|---------|-------|
| **Target publish time** | Monday 07:00 KST |
| **UTC equivalent** | Monday 00:00 UTC (KST = UTC+7 in Vietnam / UTC+9 in Korea) |
| **Cron expression** | `0 0 * * 1` |

### Pipeline Stages

```
┌─────────────────────────────────────────────────────────────┐
│                   n8n Weekly Pipeline                        │
│                                                             │
│  1. Schedule Trigger (Monday 00:00 UTC)                     │
│       ↓                                                     │
│  2. Execute ci_weekly_report.py                             │
│     → Generate quant data (momentum, factor, season)        │
│       ↓                                                     │
│  3. Format Node                                             │
│     → Transform JSON → Substack post format (HTML/Markdown) │
│       ↓                                                     │
│  4. HTTP Request → Substack API                             │
│     → Create draft post via REST API                        │
│       ↓                                                     │
│  5. HTTP Request → Substack API                             │
│     → Publish post (set status: published)                  │
│       ↓                                                     │
│  6. Discord DM                                              │
│     → Notify Jini: "Issue #N published → [URL]"            │
└─────────────────────────────────────────────────────────────┘
```

---

## 3. Node Configuration Details

### Node 1: Schedule Trigger

```json
{
  "type": "n8n-nodes-base.scheduleTrigger",
  "parameters": {
    "rule": {
      "interval": [{ "field": "cronExpression", "expression": "0 0 * * 1" }]
    }
  }
}
```

### Node 2: Execute Command (ci_weekly_report.py)

```json
{
  "type": "n8n-nodes-base.executeCommand",
  "parameters": {
    "command": "cd /opt/maiupbit && python scripts/ci_weekly_report.py --format json --output /tmp/weekly_signals.json"
  }
}
```

**Script responsibilities**:
- Run `maiupbit quant momentum --top 5`
- Run `maiupbit quant factor --top 5`
- Run `maiupbit quant season`
- Aggregate results into structured JSON
- Write to `/tmp/weekly_signals.json`

### Node 3: Format Node (Code)

```javascript
// Transform quant JSON into Substack-compatible HTML
const data = JSON.parse($input.first().json.stdout);
const issueNumber = data.issue_number;
const weekDate = data.week_date;

const title = `AI Quant Letter #${issueNumber} — Weekly UPbit Crypto Signals`;
const subtitle = `Dual Momentum + Multi-Factor Rankings powered by maiupbit (open-source, Apache 2.0)`;

// Build HTML body from quant data
const body = buildNewsletterHTML(data);

return [{ json: { title, subtitle, body, issueNumber } }];
```

### Node 4 & 5: HTTP Request → Substack API

**Endpoint**: `POST https://jinilee.substack.com/api/v1/posts`

**Headers**:
```
Cookie: substack.lli=<session_cookie>
Content-Type: application/json
```

**Request body**:
```json
{
  "draft_title": "{{ $json.title }}",
  "draft_subtitle": "{{ $json.subtitle }}",
  "draft_body": "{{ $json.body }}",
  "audience": "everyone",
  "section_chosen": 0,
  "tags": [{ "name": "crypto" }]
}
```

> **Authentication**: The `substack.lli` session cookie is extracted from the browser session (OpenClaw) and stored as an n8n credential. Session cookies expire periodically and must be refreshed manually.

### Node 6: Discord DM Notification

```json
{
  "type": "n8n-nodes-base.discord",
  "parameters": {
    "operation": "sendMessage",
    "channelId": "{{ $env.DISCORD_JINI_DM_CHANNEL }}",
    "content": "✅ AI Quant Letter #{{ $json.issueNumber }} published!\n📎 https://jinilee.substack.com/p/ai-quant-letter-{{ $json.issueNumber }}-weekly-upbit-crypto"
  }
}
```

---

## 4. Substack API Reference

| Method | Endpoint | Purpose |
|--------|----------|---------|
| `POST` | `/api/v1/posts` | Create new post (draft or published) |
| `PUT` | `/api/v1/posts/{id}` | Update existing post |
| `GET` | `/api/v1/posts` | List posts |

> **Note**: Substack does not publish an official public API. The `/api/v1/posts` endpoint is reverse-engineered from the Substack web editor. Behavior may change without notice.

**Authentication method**: Session cookie (`substack.lli`) extracted from authenticated browser session.

---

## 5. GitHub Actions Integration

The existing `.github/workflows/weekly-report.yml` workflow can serve as the data generation layer, with n8n consuming its artifacts:

```yaml
# .github/workflows/weekly-report.yml (existing)
name: Weekly Quant Report
on:
  schedule:
    - cron: '0 22 * * 0'  # Sunday 22:00 UTC = Monday 07:00 KST
  workflow_dispatch:

jobs:
  generate-report:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Install maiupbit
        run: pip install -e .
      - name: Generate weekly signals
        run: python scripts/ci_weekly_report.py --format json > weekly_signals.json
      - name: Upload artifact
        uses: actions/upload-artifact@v4
        with:
          name: weekly-signals
          path: weekly_signals.json
```

**Integration option**: n8n can trigger GitHub Actions via API and download the artifact, or the two systems can run independently with n8n handling the Substack API call directly.

---

## 6. Error Handling

| Failure Point | Detection | Recovery Action |
|--------------|-----------|-----------------|
| Script execution fails | Non-zero exit code | Discord alert → manual run |
| Substack API returns 4xx | HTTP status check | Retry once → Discord alert |
| Session cookie expired | 401 response | Discord alert → manual cookie refresh |
| Discord notification fails | n8n error log | Silent fail (not blocking) |

---

## 7. Implementation Checklist

### Phase 1: Script Preparation

```
[ ] Create scripts/ci_weekly_report.py
    - Aggregates quant signals into structured JSON
    - Outputs: issue_number, week_date, season, momentum_top5, factor_top5, summary
[ ] Test script locally: python scripts/ci_weekly_report.py --format json
[ ] Verify JSON schema matches n8n Format Node expectations
```

### Phase 2: n8n Pipeline

```
[ ] Create new workflow in n8n Cloud
[ ] Add Schedule Trigger node (cron: 0 0 * * 1)
[ ] Add Execute Command node
[ ] Add Code/Function node for formatting
[ ] Add HTTP Request node (Substack create post)
[ ] Add HTTP Request node (Substack publish)
[ ] Add Discord node (notification)
[ ] Store substack.lli cookie as n8n credential
[ ] Test with manual trigger
[ ] Activate workflow
```

### Phase 3: Validation

```
[ ] Run full pipeline in test mode (draft post, not published)
[ ] Verify post formatting in Substack editor
[ ] Run live once (confirm Issue #2 publishes correctly)
[ ] Monitor for 4 consecutive successful runs
```

---

## 8. Related Documents

- [D010-Substack-Newsletter-Channel-Setup.md](D010-Substack-Newsletter-Channel-Setup.md) — Channel setup
- [I010-First-Newsletter-Publication.md](I010-First-Newsletter-Publication.md) — First issue (manual)
- [I011-Payment-Setup-Progress.md](I011-Payment-Setup-Progress.md) — Payment integration
- [../blog/README.md](../blog/README.md) — Operations guide

---

## 9. Implementation Record (2026-03-09)

The GitHub Actions-based pipeline (not n8n) was implemented as the primary automation path.

### Files Created

| File | Purpose |
|------|---------|
| `scripts/generate_newsletter_html.py` | Converts quant data dict to styled HTML newsletter |
| `scripts/publish_newsletter.py` | End-to-end publishing pipeline (data → HTML → Substack → Discord) |

### Workflow Modified

`.github/workflows/weekly-report.yml` — Added `Publish newsletter to Substack` step before the commit step.

### Actual Pipeline Flow

```
[Every Monday 07:00 KST / Sunday 22:00 UTC]
GitHub Actions (weekly-report.yml)
  |
  +-- scripts/ci_weekly_report.py       -> JSON quant data (stdout)
  |
  +-- scripts/publish_newsletter.py
        |
        +-- _run_ci_report()            -> parse JSON from ci_weekly_report.py
        +-- _generate_html()            -> generate_newsletter_html.py -> HTML body
        +-- _publish_to_substack()      -> POST /api/v1/posts
        +-- _notify_discord()           -> Discord webhook embed
```

### Required GitHub Secrets

| Secret | Description |
|--------|-------------|
| `SUBSTACK_COOKIE` | substack.lli JWT cookie value |
| `SUBSTACK_URL` | e.g. `https://jinilee.substack.com` |
| `DISCORD_WEBHOOK` | Discord webhook URL (optional, for notifications) |

### Newsletter Sections

1. Market Season Analysis — current season, score, signal, halving info
2. Dual Momentum TOP 5 — momentum score + buy/sell signal per coin
3. Multi-Factor Ranking TOP 5 — combined factor ranking
4. GTAA Asset Allocation — weight bar chart per asset
5. Weekly Signal Summary — overall buy/sell/neutral signal

### Issue Numbering

`issue_number = len(blog/published/*) + 2`
(Offset of 2 accounts for Issue #1 published manually.)
