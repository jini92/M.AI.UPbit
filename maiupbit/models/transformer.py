# -*- coding: utf-8 -*-
"""
maiupbit.models.transformer
~~~~~~~~~~~~~~~~~~~~~~~~~~~

PyTorch Transformer based cryptocurrency price prediction model.

Usage example::

    predictor = TransformerPredictor(lookback=720, d_model=64, nhead=4, num_layers=2)
    predictor.train(close_prices, epochs=50)
    preds = predictor.predict(close_prices, num_predictions=48)
"""

from __future__ import annotations

import logging
import math
import os
from typing import Optional

import numpy as np
import torch
import torch.nn as nn
from sklearn.preprocessing import MinMaxScaler
from torch.utils.data import DataLoader, TensorDataset

logger = logging.getLogger(__name__)

# Use GPU if available, otherwise use CPU
_DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")


# ---------------------------------------------------------------------------
# Internal PyTorch modules
# ---------------------------------------------------------------------------

class _PositionalEncoding(nn.Module):
    """Sinusoidal/cosine positional encoding (standard Transformer implementation).

    Args:
        d_model: Embedding dimension.
        max_len: Maximum supported sequence length.
        dropout: Dropout probability.
    """

    def __init__(self, d_model: int, max_len: int = 5000, dropout: float = 0.1) -> None:
        super().__init__()
        self.dropout = nn.Dropout(p=dropout)

        # shape: (max_len, d_model)
        pe = torch.zeros(max_len, d_model)
        position = torch.arange(0, max_len, dtype=torch.float).unsqueeze(1)  # (max_len, 1)
        div_term = torch.exp(
            torch.arange(0, d_model, 2, dtype=torch.float)
            * (-math.log(10000.0) / d_model)
        )  # (d_model/2,)

        pe[:, 0::2] = torch.sin(position * div_term)
        pe[:, 1::2] = torch.cos(position * div_term[: d_model // 2])

        # (1, max_len, d_model) — Add batch dimension
        pe = pe.unsqueeze(0)
        self.register_buffer("pe", pe)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """Add positional encoding.

        Args:
            x: shape (batch, seq_len, d_model)

        Returns:
            shape (batch, seq_len, d_model)
        """
        x = x + self.pe[:, : x.size(1), :]  # type: ignore[index]
        return self.dropout(x)


class _PriceTransformer(nn.Module):
    """Price prediction Transformer model.

    Args:
        lookback: Number of past data points to use as input.
        d_model: Embedding dimension for the transformer layers.
        nhead: Number of attention heads in each layer.
        num_layers: Number of transformer encoder layers.
    """

    def __init__(self, lookback: int, d_model: int = 64, nhead: int = 4, num_layers: int = 2) -> None:
        super().__init__()
        self.positional_encoding = _PositionalEncoding(d_model)
        self.transformer_encoder = nn.TransformerEncoder(
            nn.TransformerEncoderLayer(d_model=d_model, nhead=nhead), num_layers=num_layers
        )

    def forward(self, src: torch.Tensor) -> torch.Tensor:
        """Forward pass through the model.

        Args:
            src: shape (seq_len, batch_size, d_model)

        Returns:
            shape (seq_len, batch_size, d_model)
        """
        src = self.positional_encoding(src)
        output = self.transformer_encoder(src)
        return output


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

class TransformerPredictor:
    """Transformer model for cryptocurrency price prediction.

    Args:
        lookback: Number of past data points to use as input.
        d_model: Embedding dimension for the transformer layers.
        nhead: Number of attention heads in each layer.
        num_layers: Number of transformer encoder layers.
    """

    def __init__(self, lookback: int = 720, d_model: int = 64, nhead: int = 4, num_layers: int = 2) -> None:
        self.lookback = lookback
        self.d_model = d_model
        self.nhead = nhead
        self.num_layers = num_layers
        self.model = _PriceTransformer(lookback=self.lookback, d_model=d_model, nhead=nhead, num_layers=num_layers)
        self.scaler = None

    def train(
        self,
        data: np.ndarray,
        epochs: int = 100,
        batch_size: int = 16,
        lr: float = 0.001,
    ) -> dict:
        """Train the Transformer model.

        The data is normalized using MinMaxScaler to [0, 1] range and then
        sliding window (X, Y) pairs are created for training the model.

        Args:
            data: Close price array. shape (n_samples,) or (n_samples, 1).
            epochs: Number of training epochs. Default is 100.
            batch_size: Mini-batch size. Default is 16.
            lr: Adam optimizer learning rate. Default is 0.001.

        Returns:
            Training result dictionary ``{'loss': float, 'epochs': int}``.

        Raises:
            ValueError: If the data length is less than lookback.
        """
        data = np.array(data, dtype=float).reshape(-1, 1)
        if len(data) <= self.lookback:
            raise ValueError(
                f"Data length({len(data)}) must be greater than lookback({self.lookback})."
            )

        # Normalize
        self.scaler = MinMaxScaler(feature_range=(0, 1))
        scaled_data = self.scaler.fit_transform(data).flatten()

        # Sliding window
        X_arr, Y_arr = self._prepare_data(scaled_data)

        # PyTorch Tensor → DataLoader
        X_tensor = torch.from_numpy(X_arr).to(_DEVICE)
        Y_tensor = torch.from_numpy(Y_arr).to(_DEVICE)
        dataset = TensorDataset(X_tensor, Y_tensor)
        loader = DataLoader(dataset, batch_size=batch_size, shuffle=True)

        # Model, optimizer, loss function
        self.model = _PriceTransformer(lookback=self.lookback, d_model=self.d_model, nhead=self.nhead, num_layers=self.num_layers).to(_DEVICE)
        optimizer = torch.optim.Adam(self.model.parameters(), lr=lr)
        criterion = nn.MSELoss()

        final_loss = 0.0
        for epoch in range(epochs):
            epoch_loss = 0.0
            for xb, yb in loader:
                optimizer.zero_grad()
                pred = self.model(xb)
                loss = criterion(pred, yb)
                loss.backward()
                optimizer.step()
                epoch_loss += loss.item() * len(xb)
            final_loss = epoch_loss / len(dataset)

        logger.info(
            "Transformer training complete — loss=%.6f, epochs=%d",
            final_loss,
            epochs,
        )
        return {"loss": final_loss, "epochs": epochs}

    def predict(
        self,
        data: np.ndarray,
        num_predictions: int = 48,
    ) -> list[float]:
        """Predict future prices using the trained model (autoregressive).

        Starting from the last ``lookback`` number of data points,
        it predicts ``num_predictions`` number of future price steps sequentially.

        Args:
            data: Close price array. shape (n_samples,) or (n_samples, 1).
                At least ``lookback`` number of data is required.
            num_predictions: Number of future time steps to predict. Default is 48.

        Returns:
            List of predicted prices (inverted transformed values).

        Raises:
            RuntimeError: If the model or scaler has not been initialized.
        """
        if self.model is None or self.scaler is None:
            raise RuntimeError(
                "Model has not been trained yet. Call train() first."
            )

        data = np.array(data, dtype=float).reshape(-1, 1)
        scaled_data = self.scaler.transform(data).flatten()

        # Initial sliding window (last lookback elements)
        window = scaled_data[-self.lookback:].astype(np.float32)  # (lookback,)

        predictions: list[float] = []

        with torch.no_grad():
            for _ in range(num_predictions):
                x = torch.from_numpy(window).reshape(1, self.lookback, 1).to(_DEVICE)
                pred_scaled = self.model(x).cpu().numpy()[0, 0]  # scalar

                # Inverse transform
                pred_price: float = float(
                    self.scaler.inverse_transform([[pred_scaled]])[0][0]
                )
                predictions.append(pred_price)

                # Slide the window by one step
                window = np.append(window[1:], pred_scaled)

        logger.info("Transformer prediction complete — %d steps", num_predictions)
        return predictions

    def save(self, path: str) -> None:
        """Save trained model to file (state_dict + scaler + config).

        Args:
            path: Save path (.pt format recommended).

        Raises:
            RuntimeError: If there is no model to save.
        """
        if self.model is None or self.scaler is None:
            raise RuntimeError("No model to save. Call train() first.")

        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)

        checkpoint = {
            "state_dict": self.model.state_dict(),
            "scaler": self.scaler,
            "config": {
                "lookback": self.lookback,
                "d_model": self.d_model,
                "nhead": self.nhead,
                "num_layers": self.num_layers,
            },
        }
        torch.save(checkpoint, path)
        logger.info("Transformer model saved → %s", path)

    def load(self, path: str) -> None:
        """Load a saved model from file.

        Args:
            path: Model file path (.pt).

        Raises:
            FileNotFoundError: If the file does not exist.
        """
        if not os.path.exists(path):
            raise FileNotFoundError(f"Model file not found: {path}")

        checkpoint = torch.load(path, map_location=_DEVICE)

        config = checkpoint["config"]
        self.lookback = config["lookback"]
        self.d_model = config["d_model"]
        self.nhead = config["nhead"]
        self.num_layers = config["num_layers"]

        self.model = _PriceTransformer(lookback=self.lookback, d_model=self.d_model, nhead=self.nhead, num_layers=self.num_layers).to(_DEVICE)
        self.model.load_state_dict(checkpoint["state_dict"])
        self.model.eval()

        self.scaler = checkpoint["scaler"]
        logger.info("Transformer model loaded ← %s", path)