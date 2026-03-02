# -*- coding: utf-8 -*-
"""
maiupbit.models.ensemble
~~~~~~~~~~~~~~~~~~~~~~~~~

A module for combining the outputs of multiple prediction models to produce an ensemble prediction.

Usage example::

    lstm1 = LSTMPredictor(lookback=720)
    lstm1.train(data1)
    lstm2 = LSTMPredictor(lookback=360)
    lstm2.train(data2)

    ensemble = EnsemblePredictor(models=[lstm1, lstm2])
    result = ensemble.predict(data, num_predictions=48)
    # result: {'mean': [...], 'std': [...], 'models': {'model_0': [...], 'model_1': [...]}}
"""

from __future__ import annotations

import logging
from typing import Any, Protocol, runtime_checkable

import numpy as np

logger = logging.getLogger(__name__)


@runtime_checkable
class Predictor(Protocol):
    """A protocol for prediction models with a predict() interface."""

    def predict(self, data: np.ndarray, num_predictions: int = 48) -> list[float]:
        """Predict future prices."""
        ...


class EnsemblePredictor:
    """An ensemble predictor that combines predictions from multiple models.

    Collects the predictions of each model for the same input data and calculates the mean (mean)
    and standard deviation (std) to provide uncertainty as well.

    Attributes:
        models (list): A list of prediction models with a predict() method.
    """

    def __init__(self, models: list) -> None:
        """Initialize EnsemblePredictor.

        Args:
            models: List of prediction model instances.
                Each model must have a ``predict(data, num_predictions)`` method.

        Raises:
            ValueError: If the model list is empty.
        """
        if not models:
            raise ValueError("The models list cannot be empty. Please provide at least one model.")
        self.models: list[Any] = list(models)
        self._model_names: list[str] = [f"model_{i}" for i in range(len(self.models))]

    def add_model(self, name: str, model: Any) -> None:
        """Add a new prediction model to the ensemble.

        Can add any type of model that implements the predict() method.
        Supports TransformerPredictor, LSTMPredictor, etc.

        Args:
            name: A unique name for the model.
                Used as a key in the ``models`` dictionary returned by predict().
            model: An instance of a prediction model with a predict(data, num_predictions) method.

        Raises:
            ValueError: If a model with the same name already exists.
        """
        if name in self._model_names:
            raise ValueError(f"A model named '{name}' already exists.")
        self.models.append(model)
        self._model_names.append(name)
        logger.info("EnsemblePredictor: Model '%s' added (total %d)", name, len(self.models))

    def predict(
        self,
        data: np.ndarray,
        num_predictions: int = 48,
    ) -> dict:
        """Collect predictions from all models and calculate ensemble statistics.

        Args:
            data: An array of closing prices. Shape (n_samples,) or (n_samples, 1).
            num_predictions: Number of future time steps to predict. Default is 48.

        Returns:
            A dictionary with the ensemble results::

                {
                    'mean': list[float],   # Average predicted price per time step
                    'std':  list[float],   # Standard deviation (uncertainty) per time step
                    'models': {
                        'model_0': list[float],   # Individual model predictions
                        'model_1': list[float],
                        ...
                    }
                }

        Raises:
            RuntimeError: If prediction fails for all models.
        """
        all_predictions: dict[str, list[float]] = {}
        errors: list[str] = []

        for idx, model in enumerate(self.models):
            model_key = self._model_names[idx] if idx < len(self._model_names) else f"model_{idx}"
            try:
                preds = model.predict(data, num_predictions=num_predictions)
                all_predictions[model_key] = list(preds)
                logger.info(
                    "EnsemblePredictor: %s prediction complete (%d steps)",
                    model_key,
                    num_predictions,
                )
            except Exception as exc:  # noqa: BLE001
                errors.append(f"{model_key}: {exc}")
                logger.warning("EnsemblePredictor: %s prediction failed — %s", model_key, exc)

        if not all_predictions:
            raise RuntimeError(
                f"Prediction failed for all models:\n" + "\n".join(errors)
            )

        # Prediction matrix (n_models × num_predictions)
        matrix = np.array(list(all_predictions.values()))  # shape: (n_models, num_predictions)

        mean_preds: list[float] = matrix.mean(axis=0).tolist()
        std_preds: list[float] = matrix.std(axis=0).tolist()

        logger.info(
            "EnsemblePredictor: Ensemble completed with %d models — mean[0]=%.2f, std[0]=%.2f",
            len(all_predictions),
            mean_preds[0] if mean_preds else float("nan"),
            std_preds[0] if std_preds else float("nan"),
        )

        return {
            "mean": mean_preds,
            "std": std_preds,
            "models": all_predictions,
        }