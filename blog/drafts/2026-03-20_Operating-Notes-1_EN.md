---
title: "MAIJINI@openclaw Operating Notes #1 — Claude Code × Discord DM: Coding by Chat"
subtitle: "How I wired Claude Code into Discord DM and shipped a crypto quant engine through conversation alone."
date: 2026-03-20
series: "MAIJINI@openclaw Operating Notes"
tags: [maijini, openclaw, claude-code, discord, quant, maiupbit, build-in-public, ai-dev-workflow]
language: en
---

# MAIJINI@openclaw Operating Notes #1 — Claude Code × Discord DM: Coding by Chat

*Building a crypto quant engine through Discord conversations — no IDE required.*

---

## Why This Exists

I run 16 AI projects under the [MAI Universe](https://jinilee.substack.com) umbrella. The bottleneck was never ideas — it was execution speed. I needed a way to write code, commit, and ship while I was away from my desk, on my phone, or simply thinking out loud.

The answer: wire **Claude Code** (Anthropic's coding CLI) into **Discord DM** via [OpenClaw](https://openclaw.ai), my AI orchestration gateway. Now I type a request in Discord, Claude Code writes the code, and the commit lands on GitHub — all through a chat message.

This is the first operating note documenting what that workflow actually produced.

## The Setup: Claude Code × Discord DM

**OpenClaw** is an open-source AI gateway that connects LLMs to messaging platforms. I run it on my Windows PC as a persistent gateway. It receives Discord DM messages, routes them to Claude Code, and returns results — including file edits, git commits, and terminal output.

The key insight: **coding is a conversation.** When you can talk to your coding agent the same way you talk to a colleague on Discord, the friction between "thinking about code" and "shipping code" disappears.

Here is what a typical session looks like:

1. I send a Discord DM: *"Add a `status` subcommand to the CLI that shows current portfolio state"*
2. Claude Code reads the codebase, writes the implementation, runs tests
3. I get back a summary with the diff and test results
4. I say *"looks good, commit and push"*
5. Done. The code is on GitHub.

No IDE. No terminal. No context switching.

## What We Built in 10 Days (March 10–20)

### 1. `cli/maiupbit.py` — A Full Quant CLI (375 LOC)

The biggest single deliverable. A Click-based CLI with 13 subcommands:

- `maiupbit quant` — run the full dual-momentum + multi-factor pipeline
- `maiupbit newsletter` — generate the weekly AI Quant Letter
- `maiupbit status` — portfolio state and P&L
- `maiupbit backtest` — historical strategy performance
- `maiupbit journal` — daily trade decision log

Every command outputs JSON by default, making it pipeline-friendly for n8n workflows and GitHub Actions.

This entire CLI was written through Discord DM conversations with Claude Code. No file was opened in VS Code.

### 2. Local LLM Optimization: Qwen3:8b + GPU Layer Control

The quant pipeline uses a local LLM (Qwen3:8b via Ollama) for market analysis narrative. Problem: the 8B model was eating all GPU memory and causing CUDA fragmentation.

Solution discovered through conversation:

```
OLLAMA_GPU_LAYERS=20
```

By limiting GPU layer offloading to 20 (out of ~32), we keep enough VRAM headroom for other tasks while maintaining acceptable inference speed. This single environment variable eliminated the OOM crashes that had been killing overnight runs.

### 3. Newsletter Automation Pipeline

The AI Quant Letter now has a fully documented automation architecture:

- **D010** — Newsletter content generation pipeline (quant data → narrative → HTML)
- **D011** — Distribution pipeline (n8n webhook → Substack API → social media)
- **GitHub Actions** — Weekly cron trigger for the full pipeline

The goal: zero-touch weekly newsletter publication. Run the quant model, generate the letter, publish to Substack, post to social — all automated.

### 4. Regression Guard

Quant systems are fragile. Change one threshold and your backtest looks amazing but your live performance collapses.

We implemented a regression guard that protects critical parameters:

- Momentum lookback periods
- Scoring weights
- Risk thresholds
- Position sizing multipliers

Every parameter change now requires explicit justification and a before/after comparison. The guard runs as part of the test suite.

### 5. Trade Journal

A daily log of BTC hold/sell decisions with reasoning:

```
2026-03-18 | HOLD | BTC momentum: -0.061, below threshold
2026-03-19 | HOLD | No positive momentum in top 5
2026-03-20 | HOLD | 3rd consecutive week, all scores negative
```

Simple, but it creates accountability. When the model eventually signals a buy, we will have a complete record of every day it chose to wait.

### 6. AI Quant Letter #3

The third issue of our weekly crypto quant newsletter:

- **Signal:** Hold cash (3rd consecutive week)
- **Top coin:** ETH at -0.057 (least negative)
- **Divergence:** Multi-factor model is more optimistic (ETH 0.554) vs pure momentum (all negative)
- **Interpretation:** Consolidation phase — stopped falling, not yet rising

Read it: [AI Quant Letter #3](https://jinilee.substack.com)

## What I Learned

**1. Chat-driven development is real.** Not as a gimmick — as a practical workflow. The key is having an agent that understands your codebase context, not just generates snippets.

**2. The bottleneck moved.** It used to be "find time to sit at the IDE." Now it is "think clearly about what to build." The execution layer is nearly instant.

**3. Local LLMs need operational tuning.** Running Qwen3:8b on a consumer GPU is viable, but you need to manage VRAM like a shared resource. `OLLAMA_GPU_LAYERS` is the single most impactful config for stability.

**4. Quant discipline requires infrastructure.** It is easy to build a signal generator. It is hard to build the scaffolding that prevents you from breaking it — regression guards, trade journals, automated newsletters.

## What is Next

- **Zero-touch newsletter:** Complete the n8n + GitHub Actions pipeline so the weekly letter publishes without human intervention
- **Live trading integration:** Connect the signal output to UPbit API for paper trading
- **Multi-model ensemble:** Add a second local LLM (Llama 3) to cross-validate Qwen3 analysis
- **Voice interface:** Route voice commands through OpenClaw to trigger quant runs

---

*This is the first issue of MAIJINI@openclaw Operating Notes, part of the [MAI Universe Letter](https://jinilee.substack.com). Follow along as I build an AI-first development workflow — one Discord message at a time.*

*The quant engine is open source: [github.com/jini92/M.AI.UPbit](https://github.com/jini92/M.AI.UPbit)*
