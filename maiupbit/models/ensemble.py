# -*- coding: utf-8 -*-
"""
maiupbit.models.ensemble
~~~~~~~~~~~~~~~~~~~~~~~~~

여러 예측 모델의 출력을 결합하여 앙상블 예측값을 산출하는 모듈.

사용 예::

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
    """predict() 인터페이스를 가진 예측 모델 프로토콜."""

    def predict(self, data: np.ndarray, num_predictions: int = 48) -> list[float]:
        """미래 가격 예측."""
        ...


class EnsemblePredictor:
    """여러 모델의 예측을 결합하는 앙상블 예측기.

    동일한 입력 데이터에 대해 각 모델의 예측값을 수집하고,
    그 평균(mean)과 표준편차(std)를 계산하여 불확실성까지 제공합니다.

    Attributes:
        models (list): predict() 메서드를 가진 예측 모델 목록.
    """

    def __init__(self, models: list) -> None:
        """EnsemblePredictor 초기화.

        Args:
            models: 예측 모델 인스턴스 목록.
                각 모델은 ``predict(data, num_predictions)`` 메서드를 가져야 합니다.

        Raises:
            ValueError: 모델 목록이 비어있는 경우.
        """
        if not models:
            raise ValueError("models 목록이 비어있습니다. 하나 이상의 모델을 제공하세요.")
        self.models: list[Any] = models

    def predict(
        self,
        data: np.ndarray,
        num_predictions: int = 48,
    ) -> dict:
        """모든 모델에서 예측값을 수집하고 앙상블 통계를 계산.

        Args:
            data: 종가 배열. shape (n_samples,) 또는 (n_samples, 1).
            num_predictions: 예측할 미래 시간 스텝 수. 기본값 48.

        Returns:
            앙상블 결과 딕셔너리::

                {
                    'mean': list[float],   # 시간 스텝별 평균 예측 가격
                    'std':  list[float],   # 시간 스텝별 표준편차 (불확실성)
                    'models': {
                        'model_0': list[float],   # 개별 모델 예측값
                        'model_1': list[float],
                        ...
                    }
                }

        Raises:
            RuntimeError: 모든 모델 예측이 실패한 경우.
        """
        all_predictions: dict[str, list[float]] = {}
        errors: list[str] = []

        for idx, model in enumerate(self.models):
            model_key = f"model_{idx}"
            try:
                preds = model.predict(data, num_predictions=num_predictions)
                all_predictions[model_key] = list(preds)
                logger.info(
                    "EnsemblePredictor: %s 예측 완료 (%d steps)",
                    model_key,
                    num_predictions,
                )
            except Exception as exc:  # noqa: BLE001
                errors.append(f"{model_key}: {exc}")
                logger.warning("EnsemblePredictor: %s 예측 실패 — %s", model_key, exc)

        if not all_predictions:
            raise RuntimeError(
                f"모든 모델 예측이 실패했습니다:\n" + "\n".join(errors)
            )

        # 예측 행렬 (n_models × num_predictions)
        matrix = np.array(list(all_predictions.values()))  # shape: (n_models, num_predictions)

        mean_preds: list[float] = matrix.mean(axis=0).tolist()
        std_preds: list[float] = matrix.std(axis=0).tolist()

        logger.info(
            "EnsemblePredictor: %d 개 모델 앙상블 완료 — mean[0]=%.2f, std[0]=%.2f",
            len(all_predictions),
            mean_preds[0] if mean_preds else float("nan"),
            std_preds[0] if std_preds else float("nan"),
        )

        return {
            "mean": mean_preds,
            "std": std_preds,
            "models": all_predictions,
        }
