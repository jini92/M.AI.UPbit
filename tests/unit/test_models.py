# -*- coding: utf-8 -*-
"""
tests.unit.test_models
~~~~~~~~~~~~~~~~~~~~~~~

unit tests for maiupbit.models package.

Contents:
- TransformerPredictor (PyTorch) — full testing
- LSTMPredictor (TensorFlow/Keras) — skipped if tensorflow is not installed
- EnsemblePredictor — ensemble testing with two TransformerPredictors
"""

from __future__ import annotations

import os
import tempfile

import numpy as np
import pytest

# ---------------------------------------------------------------------------
# TensorFlow availability check (LSTM skip condition)
# ---------------------------------------------------------------------------
try:
    import tensorflow as _tf  # noqa: F401

    HAS_TENSORFLOW = True
except ImportError:
    HAS_TENSORFLOW = False

# ---------------------------------------------------------------------------
# Test constants
# ---------------------------------------------------------------------------
LOOKBACK = 30          # Use small value for quick execution
DATA_SIZE = 100        # Number of test data points
EPOCHS = 5             # Minimum epochs for fast training
BATCH_SIZE = 8
NUM_PREDS = 10


def _make_price_data(n: int = DATA_SIZE, seed: int = 42) -> np.ndarray:
    """Generate a virtual price array for testing.

    Args:
        n: Number of data points.
        seed: Random seed.

    Returns:
        shape (n,) float64 array — positive price data.
    """
    rng = np.random.default_rng(seed)
    prices = 50000 + np.cumsum(rng.standard_normal(n) * 500)
    return prices.astype(np.float64)


# ===========================================================================
# TransformerPredictor tests
# ===========================================================================

class TestTransformerPredictor:
    """Unit tests for TransformerPredictor."""

    def test_train_returns_loss_dict(self) -> None:
        """Check that training returns a dictionary with loss and epochs keys."""
        from maiupbit.models.transformer import TransformerPredictor

        predictor = TransformerPredictor(lookback=LOOKBACK)
        data = _make_price_data()

        result = predictor.train(data, epochs=EPOCHS, batch_size=BATCH_SIZE)

        assert isinstance(result, dict), "Return value should be a dictionary."
        assert "loss" in result, "'loss' key must exist."
        assert "epochs" in result, "'epochs' key must exist."
        assert isinstance(result["loss"], float), "Loss should be a float."
        assert result["loss"] >= 0.0, "Loss cannot be negative."
        assert result["epochs"] == EPOCHS, f"EPOCHS value should be {EPOCHS}."

    def test_predict_returns_list(self) -> None:
        """Check that prediction results are of the correct type and length."""
        from maiupbit.models.transformer import TransformerPredictor

        predictor = TransformerPredictor(lookback=LOOKBACK)
        data = _make_price_data()
        predictor.train(data, epochs=EPOCHS, batch_size=BATCH_SIZE)

        preds = predictor.predict(data, num_predictions=NUM_PREDS)

        assert isinstance(preds, list), "Prediction results should be a list."
        assert len(preds) == NUM_PREDS, f"Prediction length should be {NUM_PREDS}."
        assert all(isinstance(p, float) for p in preds), "All predictions should be floats."
        # Check that prediction values are within reasonable range (positive)
        assert all(p > 0 for p in preds), "Price predictions must be positive."

    def test_predict_without_train_raises(self) -> None:
        """Check RuntimeError is raised when predict() is called before training."""
        from maiupbit.models.transformer import TransformerPredictor

        predictor = TransformerPredictor(lookback=LOOKBACK)
        data = _make_price_data()

        with pytest.raises(RuntimeError):
            predictor.predict(data)

    def test_ensemble_predict_returns_mean_std_models(self) -> None:
        """Check the structure of ensemble prediction results."""
        from maiupbit.models.ensemble import EnsemblePredictor

        t1 = self._make_trained_transformer(seed=42)
        t2 = self._make_trained_transformer(seed=99)

        ensemble = EnsemblePredictor(models=[t1, t2])
        data = _make_price_data()

        result = ensemble.predict(data, num_predictions=NUM_PREDS)

        assert isinstance(result, dict), "Ensemble results should be a dictionary."
        assert "mean" in result, "'mean' key must exist."
        assert "std" in result, "'std' key must exist."
        assert "models" in result, "'models' key must exist."

        assert len(result["mean"]) == NUM_PREDS, f"Mean length should be {NUM_PREDS}."
        assert len(result["std"]) == NUM_PREDS, f"Std length should be {NUM_PREDS}."
        assert len(result["models"]) == 2, "Model prediction dictionary should have two items."

    def test_ensemble_mean_is_average_of_models(self) -> None:
        """Check that ensemble mean is the average of individual model predictions."""
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
                f"[{i}] mean({got:.4f}) ≠ manual average({exp:.4f})"
            )

    def test_ensemble_add_model(self) -> None:
        """Check adding TransformerPredictor dynamically with add_model() and predict."""
        from maiupbit.models.ensemble import EnsemblePredictor

        t1 = self._make_trained_transformer(seed=10)
        t2 = self._make_trained_transformer(seed=20)
        t3 = self._make_trained_transformer(seed=30)

        # Initialize with one model
        ensemble = EnsemblePredictor(models=[t1])

        # Add two more models dynamically
        ensemble.add_model("transformer_b", t2)
        ensemble.add_model("transformer_c", t3)

        data = _make_price_data()
        result = ensemble.predict(data, num_predictions=NUM_PREDS)

        assert len(result["models"]) == 3, "Three model predictions should exist."
        assert "transformer_b" in result["models"], "'transformer_b' key must exist."
        assert "transformer_c" in result["models"], "'transformer_c' key must exist."

    def test_ensemble_add_model_duplicate_name_raises(self) -> None:
        """Check ValueError is raised when adding a model with the same name."""
        from maiupbit.models.ensemble import EnsemblePredictor

        t1 = self._make_trained_transformer(seed=10)
        t2 = self._make_trained_transformer(seed=20)

        ensemble = EnsemblePredictor(models=[t1])
        ensemble.add_model("extra", t2)

        with pytest.raises(ValueError, match="extra"):
            ensemble.add_model("extra", t2)

    def test_ensemble_empty_models_raises(self) -> None:
        """Check ValueError is raised when initializing with an empty model list."""
        from maiupbit.models.ensemble import EnsemblePredictor

        with pytest.raises(ValueError):
            EnsemblePredictor(models=[])

    def _make_trained_transformer(
        self,
        lookback: int = LOOKBACK,
        d_model: int = 32,
        nhead: int = 2,
        num_layers: int = 1,
        seed: int = 42,
    ):
        """Helper to create a trained TransformerPredictor instance."""
        from maiupbit.models.transformer import TransformerPredictor

        predictor = TransformerPredictor(
            lookback=lookback, d_model=d_model, nhead=nhead, num_layers=num_layers
        )
        data = _make_price_data(seed=seed)
        predictor.train(data, epochs=EPOCHS, batch_size=BATCH_SIZE)
        return predictor


# ===========================================================================
# LSTMPredictor tests (skipped if tensorflow is not installed)
# ===========================================================================

class TestLSTMPredictor:
    """Unit tests for LSTMPredictor."""

    @pytest.mark.skipif(not HAS_TENSORFLOW, reason="TensorFlow is required")
    def test_train_returns_loss_dict(self) -> None:
        """Check that training returns a dictionary with loss and epochs keys."""
        from maiupbit.models.lstm import LSTMPredictor

        predictor = LSTMPredictor(lookback=LOOKBACK)
        data = _make_price_data()

        result = predictor.train(data, epochs=EPOCHS, batch_size=BATCH_SIZE)

        assert isinstance(result, dict), "Return value should be a dictionary."
        assert "loss" in result, "'loss' key must exist."
        assert "epochs" in result, "'epochs' key must exist."
        assert isinstance(result["loss"], float), "Loss should be a float."
        assert result["loss"] >= 0.0, "Loss cannot be negative."
        assert result["epochs"] == EPOCHS, f"EPOCHS value should be {EPOCHS}."

    @pytest.mark.skipif(not HAS_TENSORFLOW, reason="TensorFlow is required")
    def test_predict_returns_list(self) -> None:
        """Check that prediction results are of the correct type and length."""
        from maiupbit.models.lstm import LSTMPredictor

        predictor = LSTMPredictor(lookback=LOOKBACK)
        data = _make_price_data()
        predictor.train(data, epochs=EPOCHS, batch_size=BATCH_SIZE)

        preds = predictor.predict(data, num_predictions=NUM_PREDS)

        assert isinstance(preds, list), "Prediction results should be a list."
        assert len(preds) == NUM_PREDS, f"Prediction length should be {NUM_PREDS}."
        assert all(isinstance(p, float) for p in preds), "All predictions should be floats."

    @pytest.mark.skipif(not HAS_TENSORFLOW, reason="TensorFlow is required")
    def test_predict_without_train_raises(self) -> None:
        """Check RuntimeError is raised when predict() is called before training."""
        from maiupbit.models.lstm import LSTMPredictor

        predictor = LSTMPredictor(lookback=LOOKBACK)
        data = _make_price_data()

        with pytest.raises(RuntimeError):
            predictor.predict(data)