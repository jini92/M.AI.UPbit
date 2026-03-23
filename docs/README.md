# M.AI.UPbit Documentation

Naming convention: **A** (Analysis) / **D** (Design) / **I** (Implementation) / **O** (Operation) / **T** (Test) + sequence number.

---

## Document Index

### Analysis

| ID | Title | Status | Last Updated |
|---|---|---|---|
| **A-001** | [POC Analysis — app.py Streamlit Monolith](A-001-POC-Analysis.md) | ✅ Complete | 2026-02-25 |
| **A-002** | [Market Data Accumulation Gap Analysis](A-002-Market-Data-Accumulation-Analysis.md) | ✅ Complete | 2026-03-23 |

### Design

| ID | Title | Status | Last Updated |
|---|---|---|---|
| **D-001** | [PRD v2.1](PRD-v2.md) | ✅ Phase 9 planning updated | 2026-03-23 |
| **D-002** | [Live Trading Flywheel](D-002-LiveTrading-Flywheel.md) | 🟡 Draft + addendum | 2026-03-23 |
| **D-003** | [Market Data Accumulation Architecture](D-003-Market-Data-Accumulation-Architecture.md) | ✅ Implemented | 2026-03-23 |
| **D010** | [Substack Newsletter Channel](D010-Substack-Newsletter-Channel.md) | ✅ Complete | 2026-03-09 |
| **D010-Setup** | [Substack Newsletter Channel Setup](D010-Substack-Newsletter-Channel-Setup.md) | ✅ Complete | 2026-03-09 |
| **D011** | [Newsletter Automation Plan](D011-Newsletter-Automation-Plan.md) | ✅ Complete | 2026-03-09 |

### Implementation / Progress

| ID | Title | Status | Last Updated |
|---|---|---|---|
| **I-001** | [Implementation Status — maiupbit v0.1.0](I-001-Implementation-Status.md) | ✅ Phase 8 complete | 2026-02-25 |
| **I-002** | [Market Data Persistence Implementation](I-002-Market-Data-Persistence-Implementation.md) | ✅ Complete | 2026-03-23 |
| **I010** | [First Newsletter Publication](I010-First-Newsletter-Publication.md) | ✅ Complete | 2026-03-09 |
| **I011** | [Payment Setup Progress](I011-Payment-Setup-Progress.md) | 🟡 In progress | 2026-03-09 |
| **I012** | [Newsletter Automation Plan](I012-Newsletter-Automation-Plan.md) | ✅ Complete | 2026-03-09 |
| **I013** | [Security Incident — API Key Exposure](I013-Security-Incident-API-Key-Exposure.md) | ✅ Documented | 2026-03-09 |

### Operation

| ID | Title | Status | Last Updated |
|---|---|---|---|
| **O-001** | [Operation Plan](O-001-Operation-Plan.md) | ✅ Active | 2026-02-25 |
| — | [Content Strategy](content-strategy.md) | ✅ Active | 2026-03-09 |

### Test

| ID | Title | Status | Last Updated |
|---|---|---|---|
| **T-001** | [Test Report — 82% Coverage](T-001-Test-Report.md) | ✅ Above target | 2026-02-25 |
| **T-002** | [Market Data Persistence Validation](T-002-Market-Data-Persistence-Validation.md) | ✅ Pass (scoped) | 2026-03-23 |

---

## Current Focus

```text
maiupbit v0.1.0  |  PyPI ✅  |  Apache-2.0
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Market data persistence: COMPLETE (6 phases)
117 scoped tests passing | 65 new tests added
Next: operational backfill + PyPI v0.2.0
```

### Market data persistence initiative (reading order)

1. `A-002-Market-Data-Accumulation-Analysis.md` — gap analysis
2. `D-003-Market-Data-Accumulation-Architecture.md` — target architecture
3. `I-002-Market-Data-Persistence-Implementation.md` — implementation record
4. `T-002-Market-Data-Persistence-Validation.md` — validation report

---

_Managed by MAIBOT_
