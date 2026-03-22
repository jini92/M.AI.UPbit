---
title: "Claude Code + MAIBOT + maiupbit: 3중 AI 체인으로 암호화폐 퀀트 엔진 완성하기"
subtitle: "코딩 에이전트, 오케스트레이터, 퀀트 CLI가 Discord DM 하나로 연결되는 풀스택 AI 개발 워크플로우"
date: 2026-03-20
series: "MAIJINI@openclaw 운영 노트"
tags: [Claude Code, MAIBOT, OpenClaw, Discord, AI 오케스트레이션, 퀀트, 암호화폐, maiupbit, 자동화, 빌드인퍼블릭]
language: ko
---

# Claude Code + MAIBOT + maiupbit: 3중 AI 체인으로 암호화폐 퀀트 엔진 완성하기

*단순히 "대화로 코딩"이 아니다. 대화가 코드가 되고, 코드가 실행되고, 결과가 다시 대화로 돌아오는 3계층 AI 파이프라인.*

---

## 핵심은 아키텍처다

이 글은 Claude Code로 커밋을 했다는 이야기가 아닙니다. 지난 10일간 실제로 만들어낸 것은 **3개의 AI 레이어가 Discord DM 하나를 통해 서로 대화하는 풀스택 개발 체인**입니다:

```
Claude Code <-> Discord DM <-> MAIBOT (OpenClaw/마이지니) <-> maiupbit CLI <-> UPbit 거래소
```

**레이어 1: Claude Code** — 코딩 에이전트. 코드베이스를 읽고, 구현하고, 테스트하고, 커밋합니다.

**레이어 2: MAIBOT (OpenClaw/마이지니)** — 오케스트레이터. Discord DM 메시지를 받아 Claude Code로 라우팅하고, 컨텍스트를 관리하고, 호스트 머신에서 도구를 실행합니다.

**레이어 3: maiupbit CLI** — 퀀트 실행 엔진. Click 기반 13개 서브커맨드로 UPbit API와 통신하고, 모멘텀 모델을 실행하고, 뉴스레터를 생성합니다. 모든 출력은 JSON입니다.

핵심 설계 원칙: **각 레이어는 위 레이어가 소비하기 좋게 설계되었다.** CLI가 JSON을 출력하는 이유는 MAIBOT이 기계 판독 가능한 결과를 필요로 하기 때문입니다. MAIBOT이 Discord를 경유하는 이유는 Claude Code가 대화를 통해 작동하기 때문입니다. 체인의 최상단은 대화이고 최하단은 계산입니다.

## 왜 3개 레이어인가

Claude Code가 직접 UPbit를 호출하면 안 되나? 각 레이어는 다른 문제를 풀기 때문입니다:

- **Claude Code**는 코드 이해와 생성에 탁월하지만, 지속되지 않습니다. 세션마다 처음부터 시작합니다. 주간 cron을 실행할 수 없습니다.
- **MAIBOT**은 24/7 지속됩니다. Windows PC에서 OpenClaw 게이트웨이로 상시 실행되며, 메모리, 브라우저, 파일, 스케줄링을 갖고 있습니다. 하지만 코딩 전문가는 아닙니다.
- **maiupbit CLI**는 도메인 로직을 캡슐화합니다. 듀얼 모멘텀 계산, 멀티팩터 스코어링, 포지션 사이징, 리스크 임계값 — 이것들은 결정론적이고 테스트 가능해야 합니다.

3계층 아키텍처 덕분에 각 컴포넌트가 가장 잘하는 일을 합니다. Claude Code가 CLI를 만들고, MAIBOT이 CLI를 실행하고, CLI가 수학을 돌립니다.

## 10일간 이 체인이 만든 것 (3월 10일~20일)

### 1. `cli/maiupbit.py` — 에이전트를 위해 설계된 CLI (375줄)

이것은 사람이 터미널에서 타이핑하려고 만든 CLI가 아닙니다. **MAIBOT이 호출하도록 설계된 CLI**입니다.

Docstring이 말해줍니다: **"MAIJini orchestration."**

13개 서브커맨드, 전부 JSON 기본 출력:

- `maiupbit quant` — 듀얼 모멘텀 + 멀티팩터 파이프라인
- `maiupbit newsletter` — 주간 AI 퀀트 레터 생성
- `maiupbit status` — 포트폴리오 상태 및 손익
- `maiupbit backtest` — 과거 전략 성과
- `maiupbit journal` — 일별 매매 판단 로그

왜 JSON인가? MAIBOT이 `maiupbit quant`를 호출하면 결과를 파싱하고, 매매 여부를 판단하고, 뉴스레터를 포맷하고, Discord로 보고해야 하기 때문입니다. 사람이 읽기 좋은 테이블은 에이전트에게는 쓸모없습니다.

실제 체인 동작 흐름:

1. Discord DM으로 MAIBOT에게 전송: "이번 주 퀀트 분석 돌려줘"
2. MAIBOT이 `maiupbit quant --output json` 호출
3. CLI가 UPbit 데이터 조회, 모멘텀 모델 실행, 구조화된 결과 반환
4. MAIBOT이 결과를 AI 퀀트 레터로 포맷
5. Discord에서 포맷된 뉴스레터 수신, Substack 발행 준비 완료

### 2. 체인 속의 로컬 LLM: Qwen3:8b + GPU 레이어 제어

퀀트 파이프라인에는 시장 분석 내러티브 생성용 로컬 LLM(Qwen3:8b, Ollama)이 포함됩니다. 레이어 3이 자체적인 AI 서브레이어를 호출하는 구조입니다 — CLI가 숫자 주위에 산문을 생성하기 위해 로컬 모델을 실행합니다.

문제: 8B 모델이 GPU 메모리를 전부 소모하고 CUDA fragmentation으로 야간 실행이 크래시.

체인 자체를 통해 발견한 해결책 (Claude Code가 Discord로 제안 → MAIBOT이 테스트):

```
OLLAMA_GPU_LAYERS=20
```

GPU 오프로딩 레이어를 20개로 제한해서 VRAM 여유를 확보. 이 환경변수 하나가 OOM 크래시를 해결했습니다.

### 3. 뉴스레터 자동화 파이프라인

AI 퀀트 레터의 자동화 아키텍처가 3개 레이어를 모두 활용합니다:

- **D010** — 콘텐츠 생성: maiupbit CLI가 퀀트 데이터 생성, Qwen3가 내러티브 작성, MAIBOT이 포맷
- **D011** — 배포: n8n 웹훅이 MAIBOT 트리거 → CLI 호출 → 포맷 → Substack API 발행
- **GitHub Actions** — 주간 cron 트리거

목표: **체인이 매주 자율 실행.** 퀀트 모델 → 시그널 → CLI → 뉴스레터 → 발행 → 소셜 포스팅까지 무인 자동화.

### 4. Regression Guard — 퀀트 지표 보호

Claude Code가 체인을 통해 새 기능을 만들 때 실수로 퀀트 파라미터를 변경할 수 있습니다. Regression guard가 보호합니다:

- 모멘텀 룩백 기간 / 스코어링 가중치 / 리스크 임계값 / 포지션 사이징 배수

Claude Code가 커밋 전에 테스트 스위트를 실행하며 자동으로 체크됩니다.

### 5. Trade Journal — 매매 판단 로그

CLI가 생성하고 MAIBOT이 저장하는 일별 BTC 판단 기록:

```
2026-03-18 | HOLD | BTC 모멘텀: -0.061, 임계값 미만
2026-03-19 | HOLD | Top 5 전체 양수 모멘텀 없음
2026-03-20 | HOLD | 3주 연속, 전체 스코어 음수
```

### 6. AI 퀀트 레터 #3

3호, 체인을 통해 완전히 생성됨:
- **시그널:** 현금 유지 (3주 연속)
- **1위:** ETH -0.057 (가장 덜 부정적)
- **괴리:** 멀티팩터 낙관적(ETH 0.554) vs 모멘텀(전체 음수)
- **해석:** 횡보 구간 — 하락 멈춤, 상승 아직

## AI 레이어링에서 배운 것

**1. 각 레이어를 위 레이어를 위해 설계하라.** CLI는 MAIBOT이 소비하기 때문에 JSON을 출력합니다. 모든 인터페이스는 소비자를 위해 설계됩니다.

**2. 오케스트레이션이 어려운 레이어다.** Claude Code는 강력하고, CLI는 단순합니다. 하지만 MAIBOT — 둘을 연결하고, 상태를 유지하고, 에러를 처리하고, 스케줄을 관리하는 중간 레이어 — 거기에 진짜 복잡성이 있습니다.

**3. 병목이 실행에서 사고로 이동했다.** 3개의 AI 레이어가 기계적 작업을 처리하니, 제한 요소는 "어떻게 구현하지?"가 아니라 "다음에 무엇을 만들지?"입니다.

**4. 로컬 LLM은 서브레이어로 자연스럽게 맞는다.** Qwen3:8b는 전체 파이프라인을 오케스트레이션할 만큼 똑똑하지 않지만, CLI 내부의 산문 생성기로는 완벽합니다.

## 다음 계획

- **무인 뉴스레터:** n8n + GitHub Actions로 주간 자율 발행 완성
- **실시간 매매 연동:** CLI 시그널 → UPbit API 페이퍼 트레이딩
- **멀티모델 앙상블:** Llama 3 추가, CLI 내부에서 Qwen3 교차 검증
- **음성 인터페이스:** 음성 명령 → OpenClaw → 전체 체인 트리거

---

*MAIJINI@openclaw 운영 노트 #2. [MAI Universe Letter](https://jinilee.substack.com)에서 대화가 코드가 되고, 코드가 실행되고, 결과가 대화로 돌아오는 AI 개발 파이프라인 구축기를 계속 공유합니다.*

*퀀트 엔진은 오픈소스입니다: [github.com/jini92/M.AI.UPbit](https://github.com/jini92/M.AI.UPbit)*
