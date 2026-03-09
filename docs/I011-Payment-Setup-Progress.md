# I011 — Payment Setup Progress

**Document type**: Implementation Record
**Date**: 2026-03-09
**Status**: 🔄 In Progress
**Author**: Jini Lee

---

## Overview

This document tracks the progress of payment integration required to enable paid subscription tiers on the **AI Quant Letter** Substack publication. The target flow is:

```
Wise USD Account → Stripe Bank Account → Substack Paid Subscriptions
```

---

## 1. GitHub Repository — Public Conversion

| Field | Value |
|-------|-------|
| **Repository** | https://github.com/jini92/M.AI.UPbit |
| **Action** | Converted from private to public |
| **Date** | 2026-03-09 |
| **Status** | ✅ Complete |

**Rationale**: Public repository is required for open-source credibility and to support the Apache 2.0 positioning of `maiupbit`. The newsletter's "How This Works" section links directly to the repo — readers must be able to access it.

---

## 2. Stripe Account

| Field | Value |
|-------|-------|
| **Account ID** | `acct_1T91OdEwpGlYdv9S` |
| **Account type** | US individual account |
| **Status** | ⏸️ On hold |
| **Blocker** | SSN (Social Security Number) required for US individual account |

### Issue

Stripe US accounts require a Social Security Number (SSN) for identity verification. As a non-US resident, this requirement cannot be satisfied with existing identification documents.

### Resolution Path

1. Open Wise USD account (see Section 3)
2. Evaluate whether Wise Business account enables non-SSN Stripe verification
3. Alternative: Consider Stripe account registration in a supported country (Singapore, etc.)

---

## 3. Wise Account

| Field | Value |
|-------|-------|
| **Service URL** | https://wise.com |
| **Account type** | USD personal account |
| **Application date** | 2026-03-09 |
| **Status** | 🔄 Under Wise review |
| **Expected resolution** | 2–3 business days from application date |

### Purpose

Wise provides a USD-denominated bank account (with US routing + account number) for non-US residents. This account will be linked to Stripe as the payout destination, bypassing the SSN requirement.

### Expected Account Details After Approval

- USD routing number (ABA)
- USD account number
- Account holder: Jini Lee
- Currency: USD

---

## 4. Next Steps

### Immediate (awaiting Wise approval)

```
[ ] Wise USD account approved
[ ] Record Wise routing number + account number
[ ] Log in to Stripe (acct_1T91OdEwpGlYdv9S)
[ ] Navigate to: Settings → Bank accounts → Add your bank
[ ] Enter Wise USD account details
[ ] Complete Stripe verification (micro-deposit or instant)
```

### After Stripe Verification

```
[ ] Log in to Substack (jinilee.substack.com)
[ ] Navigate to: Settings → Payments
[ ] Connect Stripe account (acct_1T91OdEwpGlYdv9S)
[ ] Enable paid subscriptions
[ ] Configure subscription tiers (see below)
[ ] Publish first paid-only content
```

---

## 5. Subscription Tier Configuration

| Tier | Monthly Price | Annual Price | Access |
|------|--------------|--------------|--------|
| **Free** | $0 | $0 | All signals, 1-week publication delay |
| **Basic** | $4.9 | ~$49 | Immediate access, same content as free |
| **Pro** | $9.9 | ~$99 | Immediate access + strategy deep-dives + backtest reports |

### Free Tier Strategy

The 1-week delay on the free tier creates urgency without restricting access entirely. Weekly signals have a 5–7 day actionable window, so the delay meaningfully reduces the signal's value for free subscribers.

---

## 6. Revenue Projection (Conservative)

| Metric | Assumption | Monthly Revenue |
|--------|-----------|-----------------|
| 100 free subscribers | $0/month | $0 |
| 10 Basic subscribers | $4.9/month | $49 |
| 5 Pro subscribers | $9.9/month | $49.50 |
| **Total** | | **~$98.50/month** |

> Target: Break even on infrastructure costs (n8n Cloud ~$20/month, Ollama hosting ~$30/month) within 3 months.

---

## 7. Status Timeline

| Date | Event | Status |
|------|-------|--------|
| 2026-03-09 | GitHub repo converted to public | ✅ |
| 2026-03-09 | Stripe account created (`acct_1T91OdEwpGlYdv9S`) | ✅ |
| 2026-03-09 | Wise USD account application submitted | ✅ |
| 2026-03-11 (est.) | Wise account approved | ⏳ Pending |
| TBD | Stripe bank account linked (Wise USD) | ⏳ Pending |
| TBD | Substack paid subscriptions activated | ⏳ Pending |

---

## 8. Related Documents

- [D010-Substack-Newsletter-Channel-Setup.md](D010-Substack-Newsletter-Channel-Setup.md) — Channel setup
- [I010-First-Newsletter-Publication.md](I010-First-Newsletter-Publication.md) — First issue record
- [I012-Newsletter-Automation-Plan.md](I012-Newsletter-Automation-Plan.md) — Automation pipeline
