# -*- coding: utf-8 -*-
"""
maiupbit.models.lstm
~~~~~~~~~~~~~~~~~~~~

An LSTM (Long Short-Term Memory) based cryptocurrency price prediction model.

Usage example::

    predictor = LSTMPredictor(lookback=720)
    predictor.train(close_prices)
    preds = predictor.predict(close_prices, num_predictions=48)
"""

from __future__ import annotations

import logging
import os
from typing import Optional

import numpy as np
from sklearn.preprocessing import MinMaxScaler
from keras.models import Sequential, load_model
from keras.layers import LSTM, Dense

logger = logging.getLogger(__name__)


class LSTMPredictor:
    """An LSTM-based price prediction model.

    Attributes:
        lookback (int): Number of past data points used for predictions.
        model (Sequential | None): Trained Keras Sequential model.
        scaler (MinMaxScaler | None): Normalization scaler used on the data.
    """

    def __init__(
        self,
        lookback: int = 720,
        model_path: Optional[str] = None,
    ) -> None:
        """Initialize LSTMPredictor.

        Args:
            lookback: Number of past data points.
                Default value 720 = 24 hours × 30 days (time-based data).
            model_path: Path to a pre-trained model file.
                If None, creates a new model; if provided, loads from the path.
        """
        self.lookback: int = lookback
        self.model: Optional[Sequential] = None
        self.scaler: Optional[MinMaxScaler] = None

        if model_path is not None:
            self.load(model_path)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _prepare_data(
        self,
        data: np.ndarray,
    ) -> tuple[np.ndarray, np.ndarray]:
        """Convert normalized time series data into supervised learning (X, Y) pairs.

        Args:
            data: 1-D or 2-D array already transformed by MinMaxScaler.
                shape: (n_samples,) or (n_samples, 1).

        Returns:
            X: shape (n_windows, lookback, 1)
            Y: shape (n_windows,)
        """
        flat = data.flatten()
        X, Y = [], []
        for i in range(len(flat) - self.lookback):
            X.append(flat[i : i + self.lookback])
            Y.append(flat[i + self.lookback])
        X_arr = np.array(X).reshape(-1, self.lookback, 1)
        Y_arr = np.array(Y)
        return X_arr, Y_arr

    def _build_model(self, input_shape: tuple[int, int]) -> Sequential:
        """Build a two-layer LSTM model.

        Args:
            input_shape: Tuple (timesteps, features).

        Returns:
            Compiled Keras Sequential model.
        """
        model = Sequential(
            [
                LSTM(
                    50,
                    return_sequences=True,
                    input_shape=input_shape,
                ),
                LSTM(50),
                Dense(1),
            ]
        )
        model.compile(loss="mean_squared_error", optimizer="adam")
        return model

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def train(
        self,
        data: np.ndarray,
        epochs: int = 100,
        batch_size: int = 16,
    ) -> dict:
        """Train the LSTM model.

        The data is normalized to [0, 1] range using MinMaxScaler
        and then (X, Y) sliding windows are created for training the model.

        Args:
            data: Array of closing prices. shape (n_samples,) or (n_samples, 1).
            epochs: Number of training epochs. Default value 100.
            batch_size: Mini-batch size. Default value 16.

        Returns:
            Dictionary with training results ``{'loss': float, 'epochs': int}``.
        """
        data = np.array(data, dtype=float).reshape(-1, 1)

        self.scaler = MinMaxScaler(feature_range=(0, 1))
        scaled = self.scaler.fit_transform(data)

        X, Y = self._prepare_data(scaled)
        self.model = self._build_model(input_shape=(X.shape[1], 1))

        history = self.model.fit(
            X,
            Y,
            epochs=epochs,
            batch_size=batch_size,
            verbose=0,
        )

        final_loss: float = float(history.history["loss"][-1])
        logger.info("LSTM training complete — loss=%.6f, epochs=%d", final_loss, epochs)

        return {"loss": final_loss, "epochs": epochs}

    def predict(
        self,
        data: np.ndarray,
        num_predictions: int = 48,
    ) -> list[float]:
        """Predict future prices using the trained model.

        Starting from the last ``lookback`` number of data points,
        it predicts ``num_predictions`` steps into the future sequentially.

        Args:
            data: Array of closing prices. shape (n_samples,) or (n_samples, 1).
                At least ``lookback`` number of data points are required.
            num_predictions: Number of future time steps to predict. Default value 48.

        Returns:
            List of predicted prices (inverted back to original scale).

        Raises:
            RuntimeError: If the model or scaler is not initialized.
        """
        if self.model is None or self.scaler is None:
            raise RuntimeError(
                "The model has not been trained. Call train() first."
            )

        data = np.array(data, dtype=float).reshape(-1, 1)
        scaled = self.scaler.transform(data)

        # Initial sliding window (lookback × 1 × 1)
        window = scaled[-self.lookback :].reshape(1, self.lookback, 1)

        predictions: list[float] = []
        for _ in range(num_predictions):
            pred_scaled = self.model.predict(window, verbose=0)          # (1, 1)
            pred_price: float = float(
                self.scaler.inverse_transform(pred_scaled)[0][0]
            )
            predictions.append(pred_price)

            # Slide the window
            window = np.append(
                window[:, 1:, :],
                pred_scaled.reshape(1, 1, 1),
                axis=1,
            )

        logger.info("LSTM prediction complete — %d steps", num_predictions)
        return predictions

    def save(self, path: str) -> None:
        """Save the trained model to a file.

        Args:
            path: Path to save the model (.keras or .h5 format).

        Raises:
            RuntimeError: If there is no model to save.
        """
        if self.model is None:
            raise RuntimeError("No model to save. Call train() first.")

        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        self.model.save(path)
        logger.info("LSTM model saved → %s", path)

    def load(self, path: str) -> None:
        """Load a saved model from file.

        Args:
            path: Path to the model file.

        Raises:
            FileNotFoundError: If the file does not exist.
        """
        if not os.path.exists(path):
            raise FileNotFoundError(f"Model file not found: {path}")

        self.model = load_model(path)
        logger.info("LSTM model loaded ← %s", path)