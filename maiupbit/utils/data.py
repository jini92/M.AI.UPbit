"""Utility module for data preparation.

Provides functions to add indicators/signals to OHLCV DataFrames and serialize
them into JSON, as well as a function to read instruction files.
"""

import json
import logging
from typing import Optional

import pandas as pd

from maiupbit.indicators.signals import add_all_signals

logger = logging.getLogger(__name__)


def prepare_data(df_daily: pd.DataFrame, df_hourly: pd.DataFrame) -> str:
    """Adds indicators and signals to daily/hourly DataFrames and returns them
    as a JSON string.

    Workflow:
        1. Add technical indicator + signal columns to daily data.
        2. Add technical indicator + signal columns to hourly data.
        3. Combine the two DataFrames with 'daily'/'hourly' keys and serialize
           into JSON.

    Args:
        df_daily: Daily OHLCV DataFrame.
        df_hourly: Hourly OHLCV DataFrame.

    Returns:
        JSON string of combined DataFrame (orient='split').
        Can be directly passed to an analysis engine like GPT-4.
    """
    df_daily = add_all_signals(df_daily)
    df_hourly = add_all_signals(df_hourly)

    combined_df = pd.concat([df_daily, df_hourly], keys=["daily", "hourly"])
    return json.dumps(combined_df.to_json(orient="split"))


def get_instructions(file_path: str) -> Optional[str]:
    """Reads analysis instructions (system prompts) from a file and returns
    them.

    Args:
        file_path: Path to the instruction file (UTF-8 encoded text file).

    Returns:
        String content of the file. Returns None if file is not found or read
        error occurs.
    """
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        logger.error("File not found: %s", file_path)
    except IOError as exc:
        logger.error("Read error: %s", exc)
    return None