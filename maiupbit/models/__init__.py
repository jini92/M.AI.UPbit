# -*- coding: utf-8 -*-
"""
maiupbit.models
~~~~~~~~~~~~~~~

ML 예측 모델 패키지.

Modules:
    lstm        - LSTM 기반 가격 예측 모델 (TensorFlow/Keras)
    transformer - Transformer 기반 가격 예측 모델 (PyTorch)
    ensemble    - 앙상블 예측 (다중 모델 결합)
"""

try:
    from .lstm import LSTMPredictor
except ImportError:
    LSTMPredictor = None  # tensorflow/keras not installed — pip install maiupbit[ml]

try:
    from .transformer import TransformerPredictor
except ImportError:
    TransformerPredictor = None  # torch not installed — pip install torch

from .ensemble import EnsemblePredictor

__all__ = ["LSTMPredictor", "TransformerPredictor", "EnsemblePredictor"]
