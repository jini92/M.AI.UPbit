# -*- coding: utf-8 -*-
"""
tests.unit.test_models
~~~~~~~~~~~~~~~~~~~~~~~

maiupbit.models 패키지 단위 테스트.

포함 내용:
- TransformerPredictor (PyTorch) — 전체 테스트
- LSTMPredictor (TensorFlow/Keras) — tensorflow 미설치 시 skip
- EnsemblePredictor — TransformerPredictor 2개로 앙상블 테스트
"""

from __future__ import annotations

import os
import tempfile

import numpy as np
import pytest

# ---------------------------------------------------------------------------
# TensorFlow 가용성 체크 (LSTM skip 조건)
# ---------------------------------------------------------------------------
try:
    import tensorflow as _tf  # noqa: F401

    HAS_TENSORFLOW = True
except ImportError:
    HAS_TENSORFLOW = False

# ---------------------------------------------------------------------------
# 테스트용 상수
# ---------------------------------------------------------------------------
LOOKBACK = 30          # 빠른 실행을 위해 작은 값 사용
DATA_SIZE = 100        # 테스트 데이터 포인트 수
EPOCHS = 5             # 빠른 학습을 위해 최소 에포크
BATCH_SIZE = 8
NUM_PREDS = 10


def _make_price_data(n: int = DATA_SIZE, seed: int = 42) -> np.ndarray:
    """테스트용 가상 가격 배열 생성.

    Args:
        n: 데이터 포인트 수.
        seed: 랜덤 시드.

    Returns:
        shape (n,) float64 배열 — 양수 가격 데이터.
    """
    rng = np.random.default_rng(seed)
    prices = 50000 + np.cumsum(rng.standard_normal(n) * 500)
    return prices.astype(np.float64)


# ===========================================================================
# TransformerPredictor 테스트
# ===========================================================================

class TestTransformerPredictor:
    """TransformerPredictor 단위 테스트."""

    def test_train_returns_loss_dict(self) -> None:
        """학습 후 반환값이 loss, epochs 키를 가진 딕셔너리인지 확인."""
        from maiupbit.models.transformer import TransformerPredictor

        predictor = TransformerPredictor(lookback=LOOKBACK)
        data = _make_price_data()

        result = predictor.train(data, epochs=EPOCHS, batch_size=BATCH_SIZE)

        assert isinstance(result, dict), "반환값이 dict이어야 합니다."
        assert "loss" in result, "'loss' 키가 있어야 합니다."
        assert "epochs" in result, "'epochs' 키가 있어야 합니다."
        assert isinstance(result["loss"], float), "loss는 float이어야 합니다."
        assert result["loss"] >= 0.0, "loss는 음수가 될 수 없습니다."
        assert result["epochs"] == EPOCHS, f"epochs 값이 {EPOCHS}이어야 합니다."

    def test_predict_returns_list(self) -> None:
        """예측 결과가 올바른 타입/길이의 리스트인지 확인."""
        from maiupbit.models.transformer import TransformerPredictor

        predictor = TransformerPredictor(lookback=LOOKBACK)
        data = _make_price_data()
        predictor.train(data, epochs=EPOCHS, batch_size=BATCH_SIZE)

        preds = predictor.predict(data, num_predictions=NUM_PREDS)

        assert isinstance(preds, list), "예측 결과가 list이어야 합니다."
        assert len(preds) == NUM_PREDS, f"예측 길이가 {NUM_PREDS}이어야 합니다."
        assert all(isinstance(p, float) for p in preds), "모든 예측값이 float이어야 합니다."
        # 예측값이 합리적인 범위인지 검사 (0 이상)
        assert all(p > 0 for p in preds), "가격 예측값은 양수여야 합니다."

    def test_predict_without_train_raises(self) -> None:
        """학습 전 predict() 호출 시 RuntimeError 발생 확인."""
        from maiupbit.models.transformer import TransformerPredictor

        predictor = TransformerPredictor(lookback=LOOKBACK)
        data = _make_price_data()

        with pytest.raises(RuntimeError, match="train"):
            predictor.predict(data, num_predictions=NUM_PREDS)

    def test_save_and_load(self) -> None:
        """save() 후 load()한 모델이 동일한 예측값을 반환하는지 확인."""
        from maiupbit.models.transformer import TransformerPredictor

        data = _make_price_data()

        # 원본 모델 학습 및 예측
        predictor_orig = TransformerPredictor(lookback=LOOKBACK)
        predictor_orig.train(data, epochs=EPOCHS, batch_size=BATCH_SIZE)
        preds_orig = predictor_orig.predict(data, num_predictions=NUM_PREDS)

        with tempfile.TemporaryDirectory() as tmpdir:
            model_path = os.path.join(tmpdir, "transformer_test.pt")

            # 저장
            predictor_orig.save(model_path)
            assert os.path.exists(model_path), "모델 파일이 저장되어야 합니다."

            # 로드 후 예측
            predictor_loaded = TransformerPredictor()
            predictor_loaded.load(model_path)
            preds_loaded = predictor_loaded.predict(data, num_predictions=NUM_PREDS)

        # 예측값 비교 (동일 가중치이므로 동일해야 함)
        assert len(preds_orig) == len(preds_loaded), "예측 길이가 동일해야 합니다."
        for i, (a, b) in enumerate(zip(preds_orig, preds_loaded)):
            assert abs(a - b) < 1e-3, (
                f"[{i}] 원본({a:.4f})과 로드({b:.4f}) 예측이 다릅니다."
            )

    def test_custom_hyperparams(self) -> None:
        """d_model, nhead, num_layers 커스터마이징 후 학습/예측이 동작하는지 확인."""
        from maiupbit.models.transformer import TransformerPredictor

        predictor = TransformerPredictor(
            lookback=LOOKBACK,
            d_model=32,     # 작은 d_model
            nhead=2,        # 헤드 수 커스터마이징
            num_layers=1,   # 단층 Encoder
        )
        data = _make_price_data()

        result = predictor.train(data, epochs=EPOCHS, batch_size=BATCH_SIZE)
        preds = predictor.predict(data, num_predictions=NUM_PREDS)

        assert "loss" in result, "학습 결과에 loss가 있어야 합니다."
        assert len(preds) == NUM_PREDS, f"예측 길이가 {NUM_PREDS}이어야 합니다."

    def test_train_raises_when_data_too_short(self) -> None:
        """데이터 길이가 lookback 이하일 때 ValueError 발생 확인."""
        from maiupbit.models.transformer import TransformerPredictor

        predictor = TransformerPredictor(lookback=LOOKBACK)
        short_data = _make_price_data(n=LOOKBACK)  # lookback과 동일 (<=)

        with pytest.raises(ValueError):
            predictor.train(short_data, epochs=EPOCHS)

    def test_load_nonexistent_path_raises(self) -> None:
        """존재하지 않는 경로 로드 시 FileNotFoundError 발생 확인."""
        from maiupbit.models.transformer import TransformerPredictor

        predictor = TransformerPredictor()
        with pytest.raises(FileNotFoundError):
            predictor.load("/nonexistent/path/model.pt")


# ===========================================================================
# LSTMPredictor 테스트 (TensorFlow 없으면 skip)
# ===========================================================================

class TestLSTMPredictor:
    """LSTMPredictor 단위 테스트 (tensorflow 설치된 환경에서만 실행)."""

    @pytest.mark.skipif(not HAS_TENSORFLOW, reason="tensorflow not installed")
    def test_train_returns_loss_dict(self) -> None:
        """LSTM 학습 후 반환값 확인."""
        from maiupbit.models.lstm import LSTMPredictor

        predictor = LSTMPredictor(lookback=LOOKBACK)
        data = _make_price_data()
        result = predictor.train(data, epochs=EPOCHS, batch_size=BATCH_SIZE)

        assert isinstance(result, dict)
        assert "loss" in result
        assert "epochs" in result

    @pytest.mark.skipif(not HAS_TENSORFLOW, reason="tensorflow not installed")
    def test_predict_returns_list(self) -> None:
        """LSTM 예측 결과가 올바른 타입/길이의 리스트인지 확인."""
        from maiupbit.models.lstm import LSTMPredictor

        predictor = LSTMPredictor(lookback=LOOKBACK)
        data = _make_price_data()
        predictor.train(data, epochs=EPOCHS, batch_size=BATCH_SIZE)
        preds = predictor.predict(data, num_predictions=NUM_PREDS)

        assert isinstance(preds, list)
        assert len(preds) == NUM_PREDS

    @pytest.mark.skipif(not HAS_TENSORFLOW, reason="tensorflow not installed")
    def test_predict_without_train_raises(self) -> None:
        """LSTM 학습 전 predict() 호출 시 RuntimeError 발생 확인."""
        from maiupbit.models.lstm import LSTMPredictor

        predictor = LSTMPredictor(lookback=LOOKBACK)
        data = _make_price_data()

        with pytest.raises(RuntimeError):
            predictor.predict(data)


# ===========================================================================
# EnsemblePredictor 테스트 (TransformerPredictor 2개)
# ===========================================================================

class TestEnsemblePredictor:
    """EnsemblePredictor 단위 테스트 (TransformerPredictor 기반)."""

    def _make_trained_transformer(
        self,
        lookback: int = LOOKBACK,
        d_model: int = 32,
        nhead: int = 2,
        num_layers: int = 1,
        seed: int = 42,
    ):
        """학습된 TransformerPredictor 인스턴스를 생성하는 헬퍼."""
        from maiupbit.models.transformer import TransformerPredictor

        predictor = TransformerPredictor(
            lookback=lookback, d_model=d_model, nhead=nhead, num_layers=num_layers
        )
        data = _make_price_data(seed=seed)
        predictor.train(data, epochs=EPOCHS, batch_size=BATCH_SIZE)
        return predictor

    def test_ensemble_predict_returns_mean_std_models(self) -> None:
        """TransformerPredictor 2개로 앙상블 예측 결과 구조 확인."""
        from maiupbit.models.ensemble import EnsemblePredictor

        t1 = self._make_trained_transformer(seed=42)
        t2 = self._make_trained_transformer(seed=99)

        ensemble = EnsemblePredictor(models=[t1, t2])
        data = _make_price_data()

        result = ensemble.predict(data, num_predictions=NUM_PREDS)

        assert isinstance(result, dict), "앙상블 결과가 dict이어야 합니다."
        assert "mean" in result, "'mean' 키가 있어야 합니다."
        assert "std" in result, "'std' 키가 있어야 합니다."
        assert "models" in result, "'models' 키가 있어야 합니다."

        assert len(result["mean"]) == NUM_PREDS, f"mean 길이가 {NUM_PREDS}이어야 합니다."
        assert len(result["std"]) == NUM_PREDS, f"std 길이가 {NUM_PREDS}이어야 합니다."
        assert len(result["models"]) == 2, "모델 예측 딕셔너리에 2개 항목이 있어야 합니다."

    def test_ensemble_mean_is_average_of_models(self) -> None:
        """앙상블 mean이 개별 모델 예측의 평균인지 확인."""
        from maiupbit.models.ensemble import EnsemblePredictor

        t1 = self._make_trained_transformer(seed=1)
        t2 = self._make_trained_transformer(seed=2)

        ensemble = EnsemblePredictor(models=[t1, t2])
        data = _make_price_data()
        result = ensemble.predict(data, num_predictions=NUM_PREDS)

        model_keys = list(result["models"].keys())
        p1 = np.array(result["models"][model_keys[0]])
        p2 = np.array(result["models"][model_keys[1]])
        expected_mean = ((p1 + p2) / 2).tolist()

        for i, (got, exp) in enumerate(zip(result["mean"], expected_mean)):
            assert abs(got - exp) < 1e-5, (
                f"[{i}] mean({got:.4f}) ≠ 수동 평균({exp:.4f})"
            )

    def test_ensemble_add_model(self) -> None:
        """add_model()로 TransformerPredictor를 동적으로 추가 후 예측 확인."""
        from maiupbit.models.ensemble import EnsemblePredictor

        t1 = self._make_trained_transformer(seed=10)
        t2 = self._make_trained_transformer(seed=20)
        t3 = self._make_trained_transformer(seed=30)

        # 처음에 1개로 초기화
        ensemble = EnsemblePredictor(models=[t1])

        # add_model로 2개 추가
        ensemble.add_model("transformer_b", t2)
        ensemble.add_model("transformer_c", t3)

        data = _make_price_data()
        result = ensemble.predict(data, num_predictions=NUM_PREDS)

        assert len(result["models"]) == 3, "3개 모델 예측이 있어야 합니다."
        assert "transformer_b" in result["models"], "'transformer_b' 키가 있어야 합니다."
        assert "transformer_c" in result["models"], "'transformer_c' 키가 있어야 합니다."

    def test_ensemble_add_model_duplicate_name_raises(self) -> None:
        """동일한 이름으로 add_model() 시 ValueError 발생 확인."""
        from maiupbit.models.ensemble import EnsemblePredictor

        t1 = self._make_trained_transformer(seed=10)
        t2 = self._make_trained_transformer(seed=20)

        ensemble = EnsemblePredictor(models=[t1])
        ensemble.add_model("extra", t2)

        with pytest.raises(ValueError, match="extra"):
            ensemble.add_model("extra", t2)

    def test_ensemble_empty_models_raises(self) -> None:
        """빈 모델 리스트로 초기화 시 ValueError 발생 확인."""
        from maiupbit.models.ensemble import EnsemblePredictor

        with pytest.raises(ValueError):
            EnsemblePredictor(models=[])
