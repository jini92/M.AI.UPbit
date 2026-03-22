---
title: "Claude Code × Discord DM으로 암호화폐 퀀트 엔진 개발하기 — MAIJINI 운영 노트 #1"
subtitle: "IDE 없이 Discord 대화만으로 퀀트 CLI, GPU 최적화, 뉴스레터 파이프라인을 만들어낸 10일의 기록"
date: 2026-03-20
series: "MAIJINI@openclaw 운영 노트"
tags: [Claude Code, Discord, AI 코딩, 퀀트, 암호화폐, maiupbit, OpenClaw, 자동화, 빌드인퍼블릭]
language: ko
---

# Claude Code × Discord DM으로 암호화폐 퀀트 엔진 개발하기 — MAIJINI 운영 노트 #1

*Discord 채팅으로 코드를 짜고 커밋하고 배포하는 AI 개발 워크플로우의 실전 기록*

---

## 왜 이걸 만들었나

저는 [MAI Universe](https://jinilee.substack.com)라는 이름으로 16개의 AI 프로젝트를 운영하고 있습니다. 항상 병목은 아이디어가 아니라 **실행 속도**였습니다. 책상 앞에 앉아서 IDE를 열어야만 코딩할 수 있다는 제약을 없애고 싶었습니다.

해결책: **Claude Code**(Anthropic의 코딩 CLI)를 **Discord DM**에 연결하는 것. [OpenClaw](https://openclaw.ai)라는 오픈소스 AI 게이트웨이를 통해 Discord 메시지를 Claude Code로 라우팅하면, 대화하듯 코드를 작성하고 즉시 GitHub에 커밋할 수 있습니다.

이 글은 그 워크플로우가 실제로 무엇을 만들어냈는지에 대한 첫 번째 운영 기록입니다.

## 구성: Claude Code × Discord DM × OpenClaw

**OpenClaw**은 LLM을 메시징 플랫폼에 연결하는 오픈소스 AI 게이트웨이입니다. Windows PC에서 상시 게이트웨이로 실행하고, Discord DM 메시지를 받아 Claude Code로 전달합니다. 코드 편집, git 커밋, 터미널 출력까지 모두 반환됩니다.

핵심 인사이트: **코딩은 대화다.** 동료에게 메시지 보내듯 코딩 에이전트에게 말하면, "코드를 생각하는 것"과 "코드를 배포하는 것" 사이의 마찰이 사라집니다.

실제 워크플로우:

1. Discord DM 전송: *"CLI에 status 서브커맨드 추가해줘, 현재 포트폴리오 상태 출력"*
2. Claude Code가 코드베이스를 읽고 구현
3. 차이점과 테스트 결과 요약 수신
4. *"좋아, 커밋하고 push해"*
5. 완료. 코드가 GitHub에 올라감.

IDE 없음. 터미널 없음. 컨텍스트 스위칭 없음.

## 10일간 만든 것 (3월 10일~20일)

### 1. `cli/maiupbit.py` — 퀀트 통합 CLI (375줄)

가장 큰 결과물입니다. Click 기반 CLI에 13개 서브커맨드를 탑재했습니다:

- `maiupbit quant` — 듀얼 모멘텀 + 멀티팩터 파이프라인 실행
- `maiupbit newsletter` — 주간 AI 퀀트 레터 생성
- `maiupbit status` — 포트폴리오 상태 및 손익
- `maiupbit backtest` — 과거 전략 성과 분석
- `maiupbit journal` — 일별 매매 판단 로그

모든 커맨드가 JSON 기본 출력으로, n8n 워크플로우나 GitHub Actions와 바로 연동됩니다.

이 전체 CLI가 Discord DM 대화로만 작성되었습니다. VS Code를 한 번도 열지 않았습니다.

### 2. 로컬 LLM 최적화: Qwen3:8b + GPU 레이어 제어

퀀트 파이프라인은 시장 분석 내러티브 생성에 로컬 LLM(Qwen3:8b, Ollama)을 사용합니다. 문제: 8B 모델이 GPU 메모리를 전부 소모하고 CUDA fragmentation을 일으켰습니다.

대화로 발견한 해결책:

```
OLLAMA_GPU_LAYERS=20
```

GPU 오프로딩 레이어를 20개(전체 ~32개 중)로 제한해서 다른 작업을 위한 VRAM 여유를 확보합니다. 이 환경변수 하나가 야간 실행을 죽이던 OOM 크래시를 해결했습니다.

### 3. 뉴스레터 자동화 파이프라인

AI 퀀트 레터의 자동화 아키텍처를 완성했습니다:

- **D010** — 뉴스레터 콘텐츠 생성 파이프라인 (퀀트 데이터 → 내러티브 → HTML)
- **D011** — 배포 파이프라인 (n8n 웹훅 → Substack API → 소셜 미디어)
- **GitHub Actions** — 주간 cron 트리거

목표: **무인 주간 뉴스레터 발행.** 퀀트 모델 실행 → 레터 생성 → Substack 발행 → 소셜 공유까지 완전 자동화.

### 4. Regression Guard — 퀀트 지표 보호

퀀트 시스템은 깨지기 쉽습니다. 임계값 하나만 바꿔도 백테스트는 멋져 보이지만 실전 성과가 무너집니다.

보호 대상 파라미터:
- 모멘텀 룩백 기간
- 스코어링 가중치
- 리스크 임계값
- 포지션 사이징 배수

모든 파라미터 변경에 명시적 정당화와 전후 비교가 필요합니다. 테스트 스위트의 일부로 실행됩니다.

### 5. Trade Journal — 매매 판단 로그

매일 BTC 보유/매도 판단과 근거를 기록합니다:

```
2026-03-18 | HOLD | BTC 모멘텀: -0.061, 임계값 미만
2026-03-19 | HOLD | Top 5 전체 양수 모멘텀 없음
2026-03-20 | HOLD | 3주 연속, 전체 스코어 음수
```

단순하지만 책임감을 만듭니다. 모델이 결국 매수 신호를 보낼 때, 기다린 모든 날의 기록이 있을 것입니다.

### 6. AI 퀀트 레터 #3

주간 암호화폐 퀀트 뉴스레터 3호:

- **시그널:** 현금 유지 (3주 연속)
- **1위 코인:** ETH -0.057 (가장 덜 부정적)
- **괴리:** 멀티팩터 모델은 낙관적(ETH 0.554) vs 순수 모멘텀(전체 음수)
- **해석:** 횡보 구간 — 하락 멈춤, 아직 상승 아님

## 배운 것

**1. 대화 기반 개발은 실용적이다.** 기믹이 아니라 실전 워크플로우로 동작합니다. 핵심은 코드 스니펫만 생성하는 게 아니라 코드베이스 전체 맥락을 이해하는 에이전트를 갖는 것입니다.

**2. 병목이 이동했다.** "IDE 앞에 앉을 시간을 찾는 것"에서 "무엇을 만들지 명확하게 생각하는 것"으로. 실행 레이어는 거의 즉각적입니다.

**3. 로컬 LLM은 운영 튜닝이 필요하다.** 소비자 GPU에서 Qwen3:8b 실행은 가능하지만, VRAM을 공유 자원으로 관리해야 합니다. `OLLAMA_GPU_LAYERS`가 안정성을 위한 가장 임팩트 있는 설정입니다.

**4. 퀀트 규율에는 인프라가 필요하다.** 신호 생성기를 만드는 건 쉽습니다. 그걸 깨뜨리지 않게 보호하는 인프라(regression guard, trade journal, 자동 뉴스레터)를 만드는 게 어렵습니다.

## 다음 계획

- **무인 뉴스레터:** n8n + GitHub Actions 파이프라인 완성으로 주간 레터 무인 발행
- **실시간 매매 연동:** 시그널 출력을 UPbit API 페이퍼 트레이딩에 연결
- **멀티모델 앙상블:** Llama 3 추가해서 Qwen3 분석 교차 검증
- **음성 인터페이스:** OpenClaw 음성 명령으로 퀀트 실행 트리거

---

*이 글은 MAIJINI@openclaw 운영 노트 시리즈 #1입니다. [MAI Universe Letter](https://jinilee.substack.com)에서 AI 기반 개발 워크플로우 구축 과정을 계속 공유합니다.*

*퀀트 엔진은 오픈소스입니다: [github.com/jini92/M.AI.UPbit](https://github.com/jini92/M.AI.UPbit)*
