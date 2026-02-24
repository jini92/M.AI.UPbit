# T-001: 테스트 리포트 — maiupbit v0.1.0

> **문서 번호**: T-001
> **작성일**: 2026-02-25
> **최종 업데이트**: 2026-02-25 (Phase 7 퀀트 전략 추가)
> **프레임워크**: pytest + coverage
> **목표 커버리지**: 70%
> **달성 커버리지**: 81.02%

---

## 1. 테스트 요약

| 항목 | 수치 |
|---|---|
| 수집 테스트 | 192 |
| 통과 | 189 |
| 스킵 | 3 (LSTM — TensorFlow 미설치) |
| 실패 | 0 |
| 실행 시간 | 6.76s |
| 총 커버리지 | **81.02%** |
| 목표 대비 | ✅ +11.02%p 초과 |

## 2. 모듈별 커버리지 상세

### Tier 1: 완벽 (100%)

| 모듈 | Stmts | Miss | Coverage |
|---|---|---|---|
| `__init__.py` | 1 | 0 | 100% |
| `analysis/__init__.py` | 4 | 0 | 100% |
| `analysis/sentiment.py` | 75 | 0 | 100% |
| `backtest/__init__.py` | 3 | 0 | 100% |
| `backtest/engine.py` | 34 | 0 | 100% |
| `exchange/__init__.py` | 3 | 0 | 100% |
| `exchange/base.py` | 15 | 0 | 100% |
| `indicators/__init__.py` | 5 | 0 | 100% |
| `indicators/momentum.py` | 38 | 0 | 100% |
| `indicators/signals.py` | 35 | 0 | 100% |
| `indicators/trend.py` | 13 | 0 | 100% |
| `indicators/volatility.py` | 22 | 0 | 100% |
| `strategies/__init__.py` | 8 | 0 | 100% |
| `utils/__init__.py` | 3 | 0 | 100% |
| `utils/report.py` | 59 | 0 | 100% |

### Tier 2: 양호 (80~99%)

| 모듈 | Stmts | Miss | Coverage | 미커버 라인 |
|---|---|---|---|---|
| `strategies/multi_factor.py` | 66 | 1 | 98% | L99 |
| `backtest/portfolio_engine.py` | 66 | 2 | 97% | L85, L107 |
| `strategies/seasonal.py` | 56 | 2 | 96% | L80, L146 |
| `strategies/allocation.py` | 42 | 3 | 93% | L60, L67, L83 |
| `strategies/base.py` | 12 | 1 | 92% | L61 |
| `strategies/momentum.py` | 52 | 4 | 92% | L59-61, L135 |
| `strategies/risk.py` | 89 | 9 | 90% | L68-175 |
| `strategies/volatility_breakout.py` | 71 | 7 | 90% | L65-133 |
| `models/transformer.py` | 129 | 2 | 98% | L186, L361 |
| `exchange/upbit.py` | 155 | 13 | 92% | L106-111, L127-128, L150-153, L363-364 |
| `models/ensemble.py` | 39 | 4 | 90% | L124-126, L129 |
| `utils/data.py` | 20 | 2 | 90% | L55-56 |
| `analysis/technical.py` | 163 | 18 | 89% | L57-71, L150, L238, L311, L361, L366, L371-373 |
| `models/__init__.py` | 10 | 2 | 80% | L21-22 |

### Tier 3: 개선 필요 (< 80%)

| 모듈 | Stmts | Miss | Coverage | 원인 | 개선 계획 |
|---|---|---|---|---|---|
| `cli.py` | 311 | 171 | 45% | quant/train 핸들러 미테스트 | CLI 통합 테스트 보강 |
| `analysis/llm.py` | 36 | 22 | 39% | 외부 LLM API 의존 | mock LLM 응답 테스트 |
| `models/lstm.py` | 64 | 57 | 11% | TensorFlow 미설치 | `@pytest.mark.skipif` 유지, CI에서 별도 실행 |
| `__main__.py` | 3 | 3 | 0% | 진입점 (실행 테스트만 필요) | 통합 테스트에서 커버 |

## 3. 테스트 파일별 분포

| 테스트 파일 | 테스트 수 | 커버 모듈 |
|---|---|---|
| `test_strategies.py` | 32 | strategies/*, backtest/portfolio_engine.py |
| `test_analysis.py` | 29 | technical.py, llm.py |
| `test_exchange.py` | 22 | upbit.py, base.py |
| `test_backtest.py` | 18 | engine.py |
| `test_sentiment.py` | 17 | sentiment.py |
| `test_utils.py` | 15 | data.py, report.py |
| `test_cli.py` | 14 | cli.py |
| `test_models.py` | 12 (3 skip) | transformer.py, lstm.py, ensemble.py |
| `test_quant_indicators.py` | 9 | ATR, noise_ratio, momentum_score, add_all_signals |
| `test_indicators.py` | 7 | trend.py, momentum.py, volatility.py, signals.py |

## 4. 스킵된 테스트

| 테스트 | 사유 | 해결 방안 |
|---|---|---|
| `test_models.py::test_lstm_*` (3건) | `@pytest.mark.skipif(no tensorflow)` | TensorFlow 설치 환경에서 실행 |

## 5. 실행 방법

```bash
# 기본 실행
cd C:\TEST\M.AI.UPbit
python -m pytest

# 커버리지 포함
python -m pytest --cov=maiupbit --cov-report=term-missing

# HTML 리포트
python -m pytest --cov=maiupbit --cov-report=html

# 특정 모듈만
python -m pytest tests/unit/test_models.py -v

# 마커 기반 (LSTM 포함 — TF 필요)
python -m pytest -m "not skipif"
```

## 6. CI/CD 연동

```toml
# pyproject.toml
[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = ["--strict-markers", "-v"]

[tool.coverage.run]
source = ["maiupbit"]

[tool.coverage.report]
fail_under = 70.0
```

## 7. 개선 로드맵

| 우선순위 | 대상 | 현재 | 목표 | 방법 |
|---|---|---|---|---|
| 🔴 높음 | `analysis/llm.py` | 39% | 70%+ | mock LLM response 테스트 |
| 🟡 중간 | `cli.py` | 70% | 85%+ | train 서브커맨드 테스트 추가 |
| 🟢 낮음 | `models/lstm.py` | 11% | 70%+ | TF CI 환경 구성 |
| 🟢 낮음 | 통합 테스트 | 0 | 5+ | scripts/ 엔드투엔드 |

---

_Last updated: 2026-02-25_
_Author: MAIBOT_
