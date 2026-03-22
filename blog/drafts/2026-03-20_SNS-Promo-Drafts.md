# SNS 홍보 초안 — 2026-03-20 (Updated: 3중 AI 체인 각도)

## X (Twitter) #1 — 기술 업그레이드 블로그용

MAIJINI@openclaw Operating Notes #2 — The Full-Stack AI Dev Chain

Not just "coding by chat." Three AI layers chained through a single Discord DM:

Claude Code (coding) -> MAIBOT/OpenClaw (orchestration) -> maiupbit CLI (execution) -> UPbit Exchange

The CLI outputs JSON because the orchestrator consumes it. The orchestrator routes through Discord because the coding agent works through conversation.

10 days, one thread:
- 375-line quant CLI (13 subcommands, all JSON output)
- GPU optimization (OLLAMA_GPU_LAYERS=20)
- Newsletter automation pipeline
- Regression guard

Conversation becomes code. Code becomes execution. Results flow back as conversation.

https://jinilee.substack.com/p/maijiniopenclaw-operating-notes-2

#BuildInPublic #ClaudeCode #OpenClaw #AIOrchestration #CryptoQuant

---

## X (Twitter) #2 — AI Quant Letter #3용

AI Quant Letter #3 — All Negative Momentum Scores, ETH Still Leads

3rd consecutive week: hold cash. Every coin in the top 5 is negative.

ETH at -0.057 is the least bad. Multi-factor model is more optimistic (0.554), suggesting consolidation — not collapse.

The system waits for math, not narratives.

Open source: pip install maiupbit

https://jinilee.substack.com/p/ai-quant-letter-3-all-negative-momentum

#CryptoQuant #AITrading #ETH #BTC #BuildInPublic

---

## LinkedIn — 3중 AI 체인 워크플로우

**Three AI layers, one Discord thread: How we built a full-stack crypto quant pipeline**

Over 10 days, we assembled a three-layer AI development chain through a single Discord DM conversation:

Layer 1: Claude Code — reads the codebase, writes implementations, commits code
Layer 2: MAIBOT (OpenClaw) — orchestrates 24/7, manages context, invokes tools
Layer 3: maiupbit CLI — runs quant models against UPbit Exchange, outputs JSON

The design principle: each layer is built for the layer above it. The CLI outputs JSON because the orchestrator needs machine-readable results. The orchestrator routes through Discord because the coding agent works through conversation.

What this produced:
- 375-line Click-based CLI with 13 subcommands (docstring: "MAIJini orchestration")
- Local LLM integration (Qwen3:8b with GPU layer control for stability)
- Automated weekly newsletter pipeline (n8n + GitHub Actions)
- Regression guard protecting quant parameters across coding sessions

The bottleneck moved from "how do I implement this?" to "what should we build next?" Three AI layers handling the mechanical work means the limiting factor is intent, not execution.

Full write-up: https://jinilee.substack.com/p/maijiniopenclaw-operating-notes-2
Quant engine (open source): https://github.com/jini92/M.AI.UPbit

#AIEngineering #BuildInPublic #AIOrchestration #QuantTrading #OpenSource
