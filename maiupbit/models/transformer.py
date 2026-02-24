# -*- coding: utf-8 -*-
"""
maiupbit.models.transformer
~~~~~~~~~~~~~~~~~~~~~~~~~~~

PyTorch Transformer 기반 암호화폐 가격 예측 모델.

사용 예::

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

# GPU 사용 가능하면 GPU, 아니면 CPU
_DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")


# ---------------------------------------------------------------------------
# 내부 PyTorch 모듈
# ---------------------------------------------------------------------------

class _PositionalEncoding(nn.Module):
    """사인/코사인 위치 인코딩 (Transformer 표준 구현).

    Args:
        d_model: 임베딩 차원.
        max_len: 지원할 최대 시퀀스 길이.
        dropout: 드롭아웃 확률.
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

        # (1, max_len, d_model) — 배치 차원 추가
        pe = pe.unsqueeze(0)
        self.register_buffer("pe", pe)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """위치 인코딩 더하기.

        Args:
            x: shape (batch, seq_len, d_model)

        Returns:
            shape (batch, seq_len, d_model)
        """
        x = x + self.pe[:, : x.size(1), :]  # type: ignore[index]
        return self.dropout(x)


class _PriceTransformer(nn.Module):
    """가격 예측용 Transformer 모델.

    구조:
        입력 투영 (Linear 1→d_model)
        → Positional Encoding
        → N × (Multi-Head Self-Attention + Feed-Forward)
        → 출력 투영 (Linear d_model→1)

    Args:
        lookback: 입력 시퀀스 길이 (타임스텝 수).
        d_model: 임베딩 차원.
        nhead: Multi-Head Attention 헤드 수.
        num_layers: Transformer Encoder 레이어 수.
        dim_feedforward: FFN 내부 차원 (기본값 d_model × 4).
        dropout: 드롭아웃 확률.
    """

    def __init__(
        self,
        lookback: int,
        d_model: int = 64,
        nhead: int = 4,
        num_layers: int = 2,
        dim_feedforward: Optional[int] = None,
        dropout: float = 0.1,
    ) -> None:
        super().__init__()
        if dim_feedforward is None:
            dim_feedforward = d_model * 4

        self.input_proj = nn.Linear(1, d_model)
        self.pos_enc = _PositionalEncoding(d_model, max_len=lookback + 10, dropout=dropout)

        encoder_layer = nn.TransformerEncoderLayer(
            d_model=d_model,
            nhead=nhead,
            dim_feedforward=dim_feedforward,
            dropout=dropout,
            batch_first=True,   # (batch, seq, feature)
        )
        self.transformer_encoder = nn.TransformerEncoder(encoder_layer, num_layers=num_layers)
        self.output_proj = nn.Linear(d_model, 1)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """순전파.

        Args:
            x: shape (batch, lookback, 1) — 정규화된 가격 시퀀스.

        Returns:
            shape (batch, 1) — 다음 타임스텝 예측값.
        """
        # (batch, lookback, d_model)
        x = self.input_proj(x)
        x = self.pos_enc(x)
        x = self.transformer_encoder(x)
        # 마지막 타임스텝만 사용해서 다음 값 예측
        x = self.output_proj(x[:, -1, :])  # (batch, 1)
        return x


# ---------------------------------------------------------------------------
# 공개 클래스
# ---------------------------------------------------------------------------

class TransformerPredictor:
    """PyTorch Transformer 기반 가격 예측 모델.

    LSTMPredictor와 동일한 퍼블릭 인터페이스를 제공합니다.

    Attributes:
        lookback (int): 예측에 사용할 과거 데이터 포인트 수.
        d_model (int): Transformer 임베딩 차원.
        nhead (int): Multi-Head Attention 헤드 수.
        num_layers (int): Transformer Encoder 레이어 수.
        model (_PriceTransformer | None): 학습된 PyTorch 모델.
        scaler (MinMaxScaler | None): 데이터 정규화에 사용하는 스케일러.
    """

    def __init__(
        self,
        lookback: int = 720,
        d_model: int = 64,
        nhead: int = 4,
        num_layers: int = 2,
        model_path: Optional[str] = None,
    ) -> None:
        """TransformerPredictor 초기화.

        Args:
            lookback: 과거 데이터 포인트 수.
                기본값 720 = 24시간 × 30일 (시간 단위 데이터 기준).
            d_model: Transformer 임베딩 차원. nhead의 배수여야 합니다.
            nhead: Multi-Head Attention 헤드 수.
            num_layers: Transformer Encoder 레이어 수.
            model_path: 사전 학습된 모델 파일 경로 (.pt).
                None이면 새 모델을 생성하고, 값이 있으면 해당 경로에서 로드.
        """
        self.lookback: int = lookback
        self.d_model: int = d_model
        self.nhead: int = nhead
        self.num_layers: int = num_layers
        self.model: Optional[_PriceTransformer] = None
        self.scaler: Optional[MinMaxScaler] = None

        if model_path is not None:
            self.load(model_path)

    # ------------------------------------------------------------------
    # 내부 헬퍼
    # ------------------------------------------------------------------

    def _prepare_data(
        self,
        scaled: np.ndarray,
    ) -> tuple[np.ndarray, np.ndarray]:
        """정규화된 1-D 배열을 슬라이딩 윈도우 (X, Y) 쌍으로 변환.

        Args:
            scaled: MinMaxScaler로 변환된 1-D 배열. shape (n_samples,)

        Returns:
            X: shape (n_windows, lookback, 1)
            Y: shape (n_windows, 1)
        """
        flat = scaled.flatten()
        X, Y = [], []
        for i in range(len(flat) - self.lookback):
            X.append(flat[i : i + self.lookback])
            Y.append(flat[i + self.lookback])
        X_arr = np.array(X, dtype=np.float32).reshape(-1, self.lookback, 1)
        Y_arr = np.array(Y, dtype=np.float32).reshape(-1, 1)
        return X_arr, Y_arr

    def _build_model(self) -> _PriceTransformer:
        """하이퍼파라미터를 사용하여 _PriceTransformer 생성 후 device 이동.

        Returns:
            초기화된 _PriceTransformer 인스턴스.
        """
        return _PriceTransformer(
            lookback=self.lookback,
            d_model=self.d_model,
            nhead=self.nhead,
            num_layers=self.num_layers,
        ).to(_DEVICE)

    # ------------------------------------------------------------------
    # 공개 API
    # ------------------------------------------------------------------

    def train(
        self,
        data: np.ndarray,
        epochs: int = 100,
        batch_size: int = 16,
        lr: float = 0.001,
    ) -> dict:
        """Transformer 모델을 학습.

        데이터를 MinMaxScaler로 [0, 1] 범위로 정규화한 뒤
        슬라이딩 윈도우 (X, Y)를 생성하여 모델을 학습합니다.

        Args:
            data: 종가 배열. shape (n_samples,) 또는 (n_samples, 1).
            epochs: 학습 에포크 수. 기본값 100.
            batch_size: 미니배치 크기. 기본값 16.
            lr: Adam 옵티마이저 학습률. 기본값 0.001.

        Returns:
            학습 결과 딕셔너리 ``{'loss': float, 'epochs': int}``.

        Raises:
            ValueError: 데이터가 lookback보다 짧은 경우.
        """
        data = np.array(data, dtype=float).reshape(-1, 1)
        if len(data) <= self.lookback:
            raise ValueError(
                f"데이터 길이({len(data)})가 lookback({self.lookback})보다 커야 합니다."
            )

        # 정규화
        self.scaler = MinMaxScaler(feature_range=(0, 1))
        scaled = self.scaler.fit_transform(data).flatten()

        # 슬라이딩 윈도우
        X_arr, Y_arr = self._prepare_data(scaled)

        # PyTorch Tensor → DataLoader
        X_tensor = torch.from_numpy(X_arr).to(_DEVICE)
        Y_tensor = torch.from_numpy(Y_arr).to(_DEVICE)
        dataset = TensorDataset(X_tensor, Y_tensor)
        loader = DataLoader(dataset, batch_size=batch_size, shuffle=True)

        # 모델, 옵티마이저, 손실함수
        self.model = self._build_model()
        optimizer = torch.optim.Adam(self.model.parameters(), lr=lr)
        criterion = nn.MSELoss()

        self.model.train()
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
        """학습된 모델로 미래 가격을 순차적으로 예측 (autoregressive).

        마지막 ``lookback`` 개의 데이터를 시작점으로 삼아
        ``num_predictions`` 개의 미래 가격을 순차적으로 예측합니다.

        Args:
            data: 종가 배열. shape (n_samples,) 또는 (n_samples, 1).
                최소 ``lookback`` 개 이상의 데이터가 필요합니다.
            num_predictions: 예측할 미래 시간 스텝 수. 기본값 48.

        Returns:
            예측 가격 리스트 (원래 스케일로 역변환된 값).

        Raises:
            RuntimeError: 모델 또는 스케일러가 초기화되지 않은 경우.
        """
        if self.model is None or self.scaler is None:
            raise RuntimeError(
                "모델이 학습되지 않았습니다. train()을 먼저 호출하세요."
            )

        data = np.array(data, dtype=float).reshape(-1, 1)
        scaled = self.scaler.transform(data).flatten()

        # 슬라이딩 윈도우 초기값 (마지막 lookback개)
        window = scaled[-self.lookback :].astype(np.float32)  # (lookback,)

        self.model.eval()
        predictions: list[float] = []

        with torch.no_grad():
            for _ in range(num_predictions):
                x = torch.from_numpy(window).reshape(1, self.lookback, 1).to(_DEVICE)
                pred_scaled = self.model(x).cpu().numpy()[0, 0]  # scalar

                # 역변환
                pred_price: float = float(
                    self.scaler.inverse_transform([[pred_scaled]])[0][0]
                )
                predictions.append(pred_price)

                # 윈도우 한 칸 슬라이드
                window = np.append(window[1:], pred_scaled)

        logger.info("Transformer prediction complete — %d steps", num_predictions)
        return predictions

    def save(self, path: str) -> None:
        """학습된 모델을 파일로 저장 (state_dict + scaler + config).

        Args:
            path: 저장 경로 (.pt 형식 권장).

        Raises:
            RuntimeError: 저장할 모델이 없는 경우.
        """
        if self.model is None or self.scaler is None:
            raise RuntimeError("저장할 모델이 없습니다. 먼저 train()을 호출하세요.")

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
        """저장된 모델을 파일에서 로드.

        Args:
            path: 모델 파일 경로 (.pt).

        Raises:
            FileNotFoundError: 파일이 존재하지 않는 경우.
        """
        if not os.path.exists(path):
            raise FileNotFoundError(f"모델 파일을 찾을 수 없습니다: {path}")

        checkpoint = torch.load(path, map_location=_DEVICE, weights_only=False)

        config = checkpoint["config"]
        self.lookback = config["lookback"]
        self.d_model = config["d_model"]
        self.nhead = config["nhead"]
        self.num_layers = config["num_layers"]

        self.model = self._build_model()
        self.model.load_state_dict(checkpoint["state_dict"])
        self.model.eval()

        self.scaler = checkpoint["scaler"]
        logger.info("Transformer model loaded ← %s", path)
