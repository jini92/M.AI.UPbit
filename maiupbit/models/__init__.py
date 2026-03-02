# -*- coding: utf-8 -*-
"""
maiupbit.models
~~~~~~~~~~~~~~~

Package for ML prediction models.

Modules:
    lstm        - Price prediction model based on LSTM (TensorFlow/Keras)
    transformer - Price prediction model based on Transformer (PyTorch)
    ensemble    - Ensemble prediction (combination of multiple models)
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