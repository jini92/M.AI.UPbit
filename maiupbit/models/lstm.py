# -*- coding: utf-8 -*-
"""
maiupbit.models.lstm
~~~~~~~~~~~~~~~~~~~~

LSTM(Long Short-Term Memory) 기반 암호화폐 가격 예측 모델.

사용 예::

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
    """LSTM 기반 가격 예측 모델.

    Attributes:
        lookback (int): 예측에 사용할 과거 데이터 포인트 수.
        model (Sequential | None): 학습된 Keras Sequential 모델.
        scaler (MinMaxScaler | None): 데이터 정규화에 사용하는 스케일러.
    """

    def __init__(
        self,
        lookback: int = 720,
        model_path: Optional[str] = None,
    ) -> None:
        """LSTMPredictor 초기화.

        Args:
            lookback: 과거 데이터 포인트 수.
                기본값 720 = 24시간 × 30일 (시간 단위 데이터 기준).
            model_path: 사전 학습된 모델 파일 경로.
                None 이면 새 모델을 생성하고, 값이 있으면 해당 경로에서 로드.
        """
        self.lookback: int = lookback
        self.model: Optional[Sequential] = None
        self.scaler: Optional[MinMaxScaler] = None

        if model_path is not None:
            self.load(model_path)

    # ------------------------------------------------------------------
    # 내부 헬퍼
    # ------------------------------------------------------------------

    def _prepare_data(
        self,
        data: np.ndarray,
    ) -> tuple[np.ndarray, np.ndarray]:
        """정규화된 시계열 데이터를 지도학습용 (X, Y) 쌍으로 변환.

        Args:
            data: 이미 MinMaxScaler 로 변환된 1-D 또는 2-D 배열.
                shape: (n_samples,) 또는 (n_samples, 1).

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
        """2-layer LSTM 모델 생성.

        Args:
            input_shape: (timesteps, features) 튜플.

        Returns:
            컴파일된 Keras Sequential 모델.
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
    # 공개 API
    # ------------------------------------------------------------------

    def train(
        self,
        data: np.ndarray,
        epochs: int = 100,
        batch_size: int = 16,
    ) -> dict:
        """LSTM 모델을 학습.

        데이터를 MinMaxScaler 로 [0, 1] 범위로 정규화한 뒤
        (X, Y) 슬라이딩 윈도우를 생성하여 모델을 학습합니다.

        Args:
            data: 종가 배열. shape (n_samples,) 또는 (n_samples, 1).
            epochs: 학습 에포크 수. 기본값 100.
            batch_size: 미니배치 크기. 기본값 16.

        Returns:
            학습 결과 딕셔너리 ``{'loss': float, 'epochs': int}``.
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
        """학습된 모델로 미래 가격을 예측.

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
                "모델이 학습되지 않았습니다. train() 을 먼저 호출하세요."
            )

        data = np.array(data, dtype=float).reshape(-1, 1)
        scaled = self.scaler.transform(data)

        # 슬라이딩 윈도우 초기값 (lookback × 1 × 1)
        window = scaled[-self.lookback :].reshape(1, self.lookback, 1)

        predictions: list[float] = []
        for _ in range(num_predictions):
            pred_scaled = self.model.predict(window, verbose=0)          # (1, 1)
            pred_price: float = float(
                self.scaler.inverse_transform(pred_scaled)[0][0]
            )
            predictions.append(pred_price)

            # 윈도우 슬라이드
            window = np.append(
                window[:, 1:, :],
                pred_scaled.reshape(1, 1, 1),
                axis=1,
            )

        logger.info("LSTM prediction complete — %d steps", num_predictions)
        return predictions

    def save(self, path: str) -> None:
        """학습된 모델을 파일로 저장.

        Args:
            path: 저장 경로 (.keras 또는 .h5 형식).

        Raises:
            RuntimeError: 저장할 모델이 없는 경우.
        """
        if self.model is None:
            raise RuntimeError("저장할 모델이 없습니다. 먼저 train() 을 호출하세요.")

        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        self.model.save(path)
        logger.info("LSTM model saved → %s", path)

    def load(self, path: str) -> None:
        """저장된 모델을 파일에서 로드.

        Args:
            path: 모델 파일 경로.

        Raises:
            FileNotFoundError: 파일이 존재하지 않는 경우.
        """
        if not os.path.exists(path):
            raise FileNotFoundError(f"모델 파일을 찾을 수 없습니다: {path}")

        self.model = load_model(path)
        logger.info("LSTM model loaded ← %s", path)
